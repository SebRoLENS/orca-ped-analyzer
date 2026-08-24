#!/usr/bin/env python3
"""
orca_ped_analyzer.py - molecule-agnostic PED normal-mode assignment for ORCA,
with automatic optional VPT2/GVPT2 post-processing.

Input:
  - always the CENTRAL ORCA Hessian: basename.hess
  - optionally the completed VPT2 output: basename.out

If --vpt2-out is omitted, basename.out is searched automatically next to the
Hessian.  VPT2 output is classified as not detected, incomplete/running,
complete+valid, or complete but numerically invalid (inf/nan).

The displaced basename_Dxxx.hess files are NEVER input to this script; ORCA
uses them internally to build the anharmonic VPT2 result.

Main outputs:
  - harmonic normal-mode PED and molecule-agnostic/topological assignments
  - VPT2 fundamental frequencies when a completed VPT2 output is available
  - overtones and combination bands with ORCA anharmonic intensities
  - Fermi-resonance warning/raw block (optional)
  - three broadened positive-going IR spectra (.dat), when data permit:
    fundamentals; anharmonic-only (overtones+combinations); complete
    (VPT2 fundamentals + overtone/combination bands)
  - CSV assignment/PED tables
  - one native Avogadro CJSON containing all harmonic normal modes

All generated files are placed in one BASENAME_analysis subdirectory next to
the central Hessian (or in --output-dir).

Requirements:
  python >= 3.9
  numpy

Examples:
  python3 orca_ped_analyzer.py molecule.hess
  python3 orca_ped_analyzer.py molecule.hess --vpt2-out molecule.out
  python3 orca_ped_analyzer.py molecule.hess --show-generic --show-raw --csv-prefix vib

Method note:
  The PED is a diagonal normalized internal-coordinate decomposition.  Its
  percentages describe harmonic zero-order normal modes.  VPT2 frequencies and
  anharmonic overtone/combination intensities are read from ORCA; the script
  does not invent anharmonic state-mixing percentages when ORCA does not print
  the corresponding eigenvector coefficients.
"""

from __future__ import annotations
import argparse
import csv
import itertools
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
import numpy as np

__version__ = "2.9.7"
MANUAL_URL = "https://github.com/SebRoLENS/orca-ped-analyzer/blob/main/docs/ORCA_PED_Analyzer_Manual.md"
GITHUB_URL = "https://github.com/SebRoLENS/orca-ped-analyzer"
CONTACT_EMAIL = "romi@lens.unifi.it"

BOHR_TO_ANG = 0.529177210903
FREQ_FACTOR = 5140.487143715827  # sqrt(Eh/(bohr^2*amu))/(2*pi*c) -> cm^-1

# Approximate single-bond covalent radii (Angstrom), mostly Cordero/Pyykko-like.
# H-Cm (Z = 1-96).  Symbols absent here fall back to 0.77 A in infer_bonds(),
# with a warning, which silently distorts the inferred connectivity.
COV_RADII = {
'H':0.31,'He':0.28,'Li':1.28,'Be':0.96,'B':0.84,'C':0.76,'N':0.71,'O':0.66,'F':0.57,'Ne':0.58,
'Na':1.66,'Mg':1.41,'Al':1.21,'Si':1.11,'P':1.07,'S':1.05,'Cl':1.02,'Ar':1.06,
'K':2.03,'Ca':1.76,'Sc':1.70,'Ti':1.60,'V':1.53,'Cr':1.39,'Mn':1.39,'Fe':1.32,'Co':1.26,
'Ni':1.24,'Cu':1.32,'Zn':1.22,'Ga':1.22,'Ge':1.20,'As':1.19,'Se':1.20,'Br':1.20,'Kr':1.16,
'Rb':2.20,'Sr':1.95,'Y':1.90,'Zr':1.75,'Nb':1.64,'Mo':1.54,'Tc':1.47,'Ru':1.46,'Rh':1.42,
'Pd':1.39,'Ag':1.45,'Cd':1.44,'In':1.42,'Sn':1.39,'Sb':1.39,'Te':1.38,'I':1.39,'Xe':1.40,
'Cs':2.44,'Ba':2.15,'La':2.07,'Ce':2.04,'Pr':2.03,'Nd':2.01,'Pm':1.99,'Sm':1.98,'Eu':1.98,
'Gd':1.96,'Tb':1.94,'Dy':1.92,'Ho':1.92,'Er':1.89,'Tm':1.90,'Yb':1.87,'Lu':1.87,
'Hf':1.75,'Ta':1.70,'W':1.62,'Re':1.51,'Os':1.44,'Ir':1.41,'Pt':1.36,'Au':1.36,'Hg':1.32,
'Tl':1.45,'Pb':1.46,'Bi':1.48,'Po':1.40,'At':1.50,'Rn':1.50,
'Fr':2.60,'Ra':2.21,'Ac':2.15,'Th':2.06,'Pa':2.00,'U':1.96,'Np':1.90,'Pu':1.87,'Am':1.80,
'Cm':1.69
}

# Atomic numbers for Avogadro CJSON export.  Runs to Og (Z = 118) so that every
# symbol carrying a covalent radius above also has an atomic number; a symbol
# missing here makes write_avogadro_cjson() raise.
_PERIODIC = [
    'H','He','Li','Be','B','C','N','O','F','Ne','Na','Mg','Al','Si','P','S','Cl','Ar',
    'K','Ca','Sc','Ti','V','Cr','Mn','Fe','Co','Ni','Cu','Zn','Ga','Ge','As','Se','Br','Kr',
    'Rb','Sr','Y','Zr','Nb','Mo','Tc','Ru','Rh','Pd','Ag','Cd','In','Sn','Sb','Te','I','Xe',
    'Cs','Ba','La','Ce','Pr','Nd','Pm','Sm','Eu','Gd','Tb','Dy','Ho','Er','Tm','Yb','Lu',
    'Hf','Ta','W','Re','Os','Ir','Pt','Au','Hg','Tl','Pb','Bi','Po','At','Rn',
    'Fr','Ra','Ac','Th','Pa','U','Np','Pu','Am','Cm','Bk','Cf','Es','Fm','Md','No','Lr',
    'Rf','Db','Sg','Bh','Hs','Mt','Ds','Rg','Cn','Nh','Fl','Mc','Lv','Ts','Og'
]
ATOMIC_NUMBER = {sym:i+1 for i,sym in enumerate(_PERIODIC)}

@dataclass(frozen=True)
class IC:
    kind: str
    atoms: tuple[int, ...]
    aux: tuple[float, ...] = ()

def _section_index(lines, name):
    target = "$" + name
    for i, line in enumerate(lines):
        if line.strip().lower() == target.lower():
            return i
    return None

def parse_orca_matrix(lines, section):
    idx = _section_index(lines, section)
    if idx is None:
        return None
    dims = [int(x) for x in lines[idx+1].split()]
    nrow, ncol = (dims[0], dims[0]) if len(dims) == 1 else (dims[0], dims[1])
    mat = np.zeros((nrow, ncol), float)
    i = idx + 2
    while i < len(lines):
        toks = lines[i].split()
        if not toks:
            i += 1
            continue
        if toks[0].startswith("$") or toks[0].startswith("#"):
            break
        if all(re.fullmatch(r"\d+", t) for t in toks):
            cols = [int(t) for t in toks]
            i += 1
            while i < len(lines):
                rowtok = lines[i].split()
                if len(rowtok) == len(cols)+1 and re.fullmatch(r"\d+", rowtok[0]):
                    r = int(rowtok[0])
                    vals = [float(x) for x in rowtok[1:]]
                    for c, v in zip(cols, vals):
                        mat[r, c] = v
                    i += 1
                else:
                    break
            continue
        i += 1
    return mat

def parse_hess(path):
    text = Path(path).read_text(errors="replace")
    lines = text.splitlines()
    H = parse_orca_matrix(lines, "hessian")
    if H is None:
        raise ValueError("Section $hessian not found.")

    idx = _section_index(lines, "atoms")
    if idx is None:
        raise ValueError("Section $atoms not found.")
    n = int(lines[idx+1].split()[0])
    elems, masses, xyz = [], [], []
    for k in range(n):
        t = lines[idx+2+k].split()
        elems.append(t[0])
        masses.append(float(t[1]))
        xyz.append([float(t[2]), float(t[3]), float(t[4])])
    masses = np.asarray(masses)
    xyz = np.asarray(xyz)  # bohr

    freqs = None
    idx = _section_index(lines, "vibrational_frequencies")
    if idx is not None:
        nf = int(lines[idx+1].split()[0])
        f = []
        for k in range(nf):
            t = lines[idx+2+k].split()
            f.append(float(t[1]))
        freqs = np.asarray(f)

    modes = parse_orca_matrix(lines, "normal_modes")

    # ORCA .hess $ir_spectrum rows are:
    # wavenumber(cm-1), T**2(a.u.), Tx, Ty, Tz.
    # Keep the raw values.  Relative spectra are generated later from T**2.
    ir = []
    idx = _section_index(lines, "ir_spectrum")
    if idx is not None:
        try:
            nir = int(lines[idx+1].split()[0])
            for mode in range(nir):
                t = lines[idx+2+mode].split()
                if len(t) < 5:
                    continue
                ir.append({
                    "mode": mode,
                    "frequency": float(t[0]),
                    "t2": float(t[1]),
                    "tx": float(t[2]),
                    "ty": float(t[3]),
                    "tz": float(t[4]),
                })
        except Exception:
            ir = []

    return elems, masses, xyz, H, freqs, modes, ir

def _extract_vpt2_block(text, start_pattern, end_patterns):
    m = re.search(start_pattern, text, re.I | re.M)
    if not m:
        return ""
    start = m.start()
    tail = text[m.end():]
    end = len(text)
    for pat in end_patterns:
        em = re.search(pat, tail, re.I | re.M)
        if em:
            end = min(end, m.end() + em.start())
    return text[start:end]

def _parse_orca_number(token):
    """ORCA number parser accepting E/D notation and inf/nan."""
    s=token.strip().strip('(),:')
    sl=s.lower()
    if sl in {"inf", "+inf", "infinity", "+infinity"}:
        return float("inf")
    if sl in {"-inf", "-infinity"}:
        return float("-inf")
    if sl in {"nan", "+nan", "-nan"}:
        return float("nan")
    try:
        return float(s.replace('D','E').replace('d','e'))
    except ValueError:
        return None


def _bounded_section(text, start_match, stop_patterns):
    """Return text after start_match and before the first known following heading."""
    tail=text[start_match.end():]
    stop=len(tail)
    for pat in stop_patterns:
        m=re.search(pat, tail, re.I | re.M)
        if m:
            stop=min(stop,m.start())
    return tail[:stop]


def parse_vpt2_output(path, expected_fundamentals=None, expected_harmonics=None):
    """Parse ORCA 6.x VPT2/GVPT2 output without guessing completion from finiteness.

    States returned:
      not-detected       no VPT2 analysis found
      incomplete         VPT2 analysis has not reached a reliable end marker/table
      complete-invalid   calculation ended, but fundamental VPT2 values contain inf/nan
      complete-valid     calculation ended and all expected fundamentals are finite

    A normally terminated ORCA process can still be complete-invalid numerically.
    """
    path=Path(path)
    text=path.read_text(errors="replace")
    detected=bool(re.search(r"ORCA\s+VPT2/GVPT2\s+Analysis|VPT2 Settings:",text,re.I))
    normal_termination=bool(re.search(r"ORCA\s+TERMINATED\s+NORMALLY",text,re.I))

    fm=re.search(r"Fundamental transitions\s*\[1/cm\]",text,re.I)
    analysis_end=False
    if fm:
        analysis_end=bool(re.search(r"={8,}\s*End\s*={8,}",text[fm.end():],re.I))
    completion_marker=bool(analysis_end or normal_termination)

    # Parse exactly the Fundamental transitions block.  Do not search arbitrary
    # numeric triples: that caused the old 465-row benzene false positive.
    fundamental_rows=[]
    if fm:
        fblock=_bounded_section(text,fm,[
            r"Zero-point\s+ro-vibrational\s+energy",
            r"Overtones\s+and\s+combination\s+bands",
            r"={8,}\s*Geometry\s*={8,}",
            r"={8,}\s*End\s*={8,}",
        ])
        seen=set()
        for line in fblock.splitlines():
            mm=re.match(r"^\s*(\d+)(?:\s*\([^)]*\)|\s+[A-Za-z][A-Za-z0-9_'\"+\-]*)?\s+(.*)$",line)
            if not mm:
                continue
            mode=int(mm.group(1))
            if expected_fundamentals is not None and not (0 <= mode < int(expected_fundamentals)):
                continue
            vals=[]
            for tok in mm.group(2).replace('(',' ').replace(')',' ').split():
                v=_parse_orca_number(tok)
                if v is not None:
                    vals.append(v)
            if len(vals) < 3 or mode in seen:
                continue
            harmonic,fundamental,difference=vals[0],vals[1],vals[2]
            seen.add(mode)
            fundamental_rows.append({
                "vpt2_mode":mode,
                "harmonic":harmonic,
                "fundamental":fundamental,
                "difference":difference,
                "finite":bool(all(math.isfinite(x) for x in (harmonic,fundamental,difference))),
            })
        fundamental_rows.sort(key=lambda r:r["vpt2_mode"])

    raw_fundamental_count=len(fundamental_rows)
    expected_ok=bool(raw_fundamental_count)
    if expected_fundamentals is not None:
        expected_ok=(raw_fundamental_count == int(expected_fundamentals))

    # Check only the harmonic column against the central Hessian.  This is a
    # consistency check, not a completion criterion.
    harmonic_match=True
    harmonic_mismatches=[]
    if expected_harmonics is not None:
        for row in fundamental_rows:
            m=row["vpt2_mode"]
            if m < len(expected_harmonics) and math.isfinite(row["harmonic"]):
                delta=abs(float(row["harmonic"])-float(expected_harmonics[m]))
                if delta > 20.0:
                    harmonic_match=False
                    harmonic_mismatches.append((m,delta))

    finite_fundamentals=[r for r in fundamental_rows if r["finite"]]
    nonfinite_fundamentals=[r for r in fundamental_rows if not r["finite"]]

    # Overtone/combination rows are parsed separately.  Non-finite rows are
    # retained for diagnostics but never used to build an IR spectrum.
    bands=[]
    bm=re.search(r"Overtones\s+and\s+combination\s+bands",text,re.I)
    if bm:
        bblock=_bounded_section(text,bm,[
            r"={8,}\s*End\s*={8,}",
            r"Timings for individual modules",
            r"ORCA\s+TERMINATED\s+NORMALLY",
        ])
        for line in bblock.splitlines():
            mm=re.match(r"^\s*(\d+)\s+(\d+)\s+(.*)$",line)
            if not mm:
                continue
            vals=[]
            for tok in mm.group(3).replace('(',' ').replace(')',' ').split():
                v=_parse_orca_number(tok)
                if v is not None:
                    vals.append(v)
            if len(vals) < 7:
                continue
            freq,eps,intensity,t2,tx,ty,tz=vals[:7]
            bands.append({
                "mode1":int(mm.group(1)),"mode2":int(mm.group(2)),
                "frequency":freq,"eps":eps,"intensity":intensity,"t2":t2,
                "tx":tx,"ty":ty,"tz":tz,
                "finite":bool(all(math.isfinite(x) for x in (freq,eps,intensity,t2,tx,ty,tz))),
            })

    finite_bands=[b for b in bands if b["finite"]]
    invalid_bands=[b for b in bands if not b["finite"]]

    fermi_block=_extract_vpt2_block(
        text,
        r"Analysis of possible Fermi resonances with VPT2 denominators",
        [r"Generating anharmonicity constants",r"evaluating zero point vibrational energies",
         r"Overtones and combination bands",r"={10,}\s*Geometry\s*={10,}"])

    run_complete=bool(detected and completion_marker and expected_ok)
    numerically_valid=bool(run_complete and not nonfinite_fundamentals and harmonic_match)

    if not detected:
        status="not-detected"
    elif not run_complete:
        status="incomplete"
    elif not numerically_valid:
        status="complete-invalid"
    else:
        status="complete-valid"

    return {
        "path":str(path),"status":status,"detected":detected,
        "run_complete":run_complete,"valid":numerically_valid,
        "normal_termination":normal_termination,"analysis_end":analysis_end,
        "completion_marker":completion_marker,
        "expected_fundamentals":expected_fundamentals,
        "raw_fundamental_count":raw_fundamental_count,
        "finite_fundamental_count":len(finite_fundamentals),
        "nonfinite_fundamentals":nonfinite_fundamentals,
        "harmonic_match":harmonic_match,"harmonic_mismatches":harmonic_mismatches,
        "fundamentals":fundamental_rows,
        "bands":bands,"finite_bands":finite_bands,"invalid_bands":invalid_bands,
        "fermi_block":fermi_block,
    }


# Conversion used only to put harmonic .hess sticks on the same relative scale
# as ORCA's VPT2 eps values.  From ORCA's printed definitions/examples,
# eps is proportional to frequency*T**2.  Absolute absorbance additionally
# requires concentration and path length, which are not known here.
ORCA_EPS_FROM_FREQ_T2 = 0.003204


def harmonic_ir_sticks(ir_rows, vib_modes):
    vibset=set(int(x) for x in vib_modes)
    sticks=[]
    for row in ir_rows:
        mode=int(row["mode"])
        freq=float(row["frequency"])
        t2=float(row["t2"])
        if mode not in vibset or not (math.isfinite(freq) and math.isfinite(t2)) or freq <= 0:
            continue
        eps=max(0.0,ORCA_EPS_FROM_FREQ_T2*freq*t2)
        sticks.append({"mode":mode,"frequency":freq,"eps":eps,"source":"harmonic fundamental"})
    return sticks


# Approximate conversion from ORCA Hessian T**2 to integrated IR intensity
# (km/mol), consistent with ORCA's printed IR table.  The relative spectra use
# epsilon instead, so this conversion is only needed for Avogadro's vibration table.
ORCA_INT_FROM_FREQ_T2 = 16.194

def harmonic_ir_intensity_map(ir_rows):
    out={}
    for row in ir_rows:
        try:
            mode=int(row["mode"]); freq=float(row["frequency"]); t2=float(row["t2"])
        except Exception:
            continue
        if math.isfinite(freq) and math.isfinite(t2) and freq > 0 and t2 >= 0:
            out[mode]=max(0.0, ORCA_INT_FROM_FREQ_T2*freq*t2)
    return out

def write_avogadro_cjson(path, name, elems, xyz_bohr, bonds, freqs, modes, vib_modes, ir_rows):
    """Write one native Avogadro CJSON containing all harmonic normal modes.

    Frequencies and eigenvectors remain harmonic because VPT2 corrects state
    energies/frequencies but does not provide replacement Cartesian normal-mode
    vectors.  IR intensities are reconstructed from the central Hessian T**2 data.

    Numbering convention: Avogadro numbers imported CJSON vibration rows from 1,
    whereas the ORCA Hessian is indexed from 0.  We therefore export Hessian modes
    1..3N-1 (omitting only mode 0) so that all relevant vibrational mode numbers
    displayed by Avogadro exactly match the Hessian/PED mode indices.
    """
    atomic_numbers=[]
    for e in elems:
        z=ATOMIC_NUMBER.get(e)
        if z is None:
            raise ValueError(f"Cannot export CJSON: unknown element symbol {e!r}")
        atomic_numbers.append(z)

    xyz_ang=(np.asarray(xyz_bohr,dtype=float)*BOHR_TO_ANG).reshape(-1).tolist()
    vib_modes=[int(m) for m in vib_modes]
    intmap=harmonic_ir_intensity_map(ir_rows)

    # Avogadro 2 reads CJSON vibration arrays sequentially and numbers the
    # displayed modes 1, 2, 3, ...; it does not use vibrations["modes"] as
    # an arbitrary label/offset.  ORCA/.hess mode indices are instead 0-based.
    # To make every physically relevant vibrational mode keep the SAME number
    # in Avogadro as in the PED/Hessian output (e.g. nonlinear first vibration
    # = Hessian mode 6 -> Avogadro mode 6), export all Hessian modes starting
    # from index 1 and deliberately omit only Hessian mode 0.  Modes before the
    # vibrational manifold are genuine near-zero translation/rotation vectors
    # and are included only to preserve numbering alignment.
    if len(freqs) < 2:
        raise ValueError("Cannot export aligned Avogadro numbering: fewer than 2 Hessian modes.")
    export_modes=list(range(1, len(freqs)))

    vf=[]; vi=[]; vecs=[]
    for mi in export_modes:
        vf.append(float(freqs[mi]))
        vi.append(float(intmap.get(mi,0.0)))
        # ORCA $normal_modes stores Cartesian displacement vectors by columns.
        vec=np.asarray(modes[:,mi],dtype=float).reshape(-1)
        vecs.append([float(x) for x in vec])

    root={
        "chemicalJson": 1,
        "name": str(name),
        "atoms": {
            "elements": {"number": atomic_numbers},
            "coords": {"3d": xyz_ang},
        },
        "vibrations": {
            # Avogadro currently regenerates/displays sequential mode numbers;
            # keep this field consistent with the exported sequential rows.
            "modes": list(range(1,len(export_modes)+1)),
            "frequencies": vf,
            "intensities": vi,
            "eigenVectors": vecs,
        },
    }
    if bonds:
        conn=[]
        for i,j in bonds:
            conn.extend([int(i),int(j)])
        root["bonds"]={"connections":{"index":conn},"order":[1]*len(bonds)}

    path=Path(path)
    path.write_text(json.dumps(root,indent=2)+"\n")
    return str(path)

def gaussian_curve(x, sticks, fwhm):
    y=np.zeros_like(x,dtype=float)
    if fwhm <= 0:
        raise ValueError("IR FWHM must be > 0 cm^-1")
    alpha=4.0*math.log(2.0)/(fwhm*fwhm)
    for s in sticks:
        f=float(s["frequency"]); a=float(s["eps"])
        if math.isfinite(f) and math.isfinite(a) and a > 0:
            y += a*np.exp(-alpha*(x-f)**2)
    return y


def write_ir_dat(path,x,y,norm,metadata):
    path=Path(path)
    yn=y/norm if norm>0 else y.copy()
    with path.open('w') as fh:
        fh.write("# ORCA PED/VPT2 relative absorbance spectrum\n")
        fh.write("# Positive-going absorbance; wavenumbers increase left-to-right.\n")
        fh.write("# Relative absorbance is normalized with the same factor for all spectra from this run.\n")
        for line in metadata:
            fh.write(f"# {line}\n")
        fh.write("# wavenumber_cm-1   absorbance_relative\n")
        for xx,yy in zip(x,yn):
            fh.write(f"{xx:.6f} {yy:.10e}\n")
    return str(path)


def generate_ir_spectra(prefix, harmonic_sticks, vpt2_map, finite_bands, fwhm,
                         xmin=None, xmax=None, step=1.0):
    """Generate the three user-facing positive-going relative-absorbance spectra.

    Files/sets:
      fundamentals  - fundamentals only. If a complete, numerically valid VPT2
                      result is available, use VPT2 fundamental frequencies;
                      otherwise use harmonic frequencies. Fundamental IR
                      intensities always come from the central Hessian because
                      ORCA's full VPT2 table supplies corrected fundamental
                      frequencies but not replacement fundamental intensities.
      anharmonic    - only VPT2 overtone + combination bands (when available).
      complete      - VPT2 fundamentals + overtone/combination bands (only when
                      a complete, numerically valid VPT2 result is available).

    All spectra from one run use the same x grid and the same normalization
    factor, so their relative amplitudes can be compared directly.
    """
    if step <= 0:
        raise ValueError("IR grid step must be > 0 cm^-1")

    harmonic_sticks=list(harmonic_sticks or [])
    sets={}
    metadata_by_set={}

    # Fundamentals: prefer VPT2 frequencies whenever a valid mapping exists.
    fundamental_sticks=[]
    if vpt2_map:
        by_mode={int(s["mode"]):s for s in harmonic_sticks}
        for hm,row in sorted(vpt2_map.items()):
            hs=by_mode.get(int(hm))
            f=row.get("fundamental")
            if hs is None or f is None or not math.isfinite(float(f)):
                continue
            fundamental_sticks.append({
                "mode":int(hm),
                "frequency":float(f),
                "eps":float(hs["eps"]),
                "source":"VPT2 fundamental frequency; harmonic IR intensity",
            })
        # Accept VPT2 fundamentals only if every harmonic fundamental has a mapped
        # finite VPT2 counterpart. A partial set must never silently replace the
        # harmonic spectrum.
        if harmonic_sticks and len(fundamental_sticks) != len(harmonic_sticks):
            fundamental_sticks=[]

    if fundamental_sticks:
        sets["fundamentals"]=fundamental_sticks
        metadata_by_set["fundamentals"]=[
            "fundamental_frequency_source=VPT2",
            "fundamental_intensity_source=central_hessian_harmonic_IR",
        ]
    elif harmonic_sticks:
        sets["fundamentals"]=harmonic_sticks
        metadata_by_set["fundamentals"]=[
            "fundamental_frequency_source=harmonic_central_hessian",
            "fundamental_intensity_source=central_hessian_harmonic_IR",
        ]

    # Additional anharmonic bands: only overtone and combination transitions.
    anharmonic_sticks=[]
    for b in finite_bands or []:
        f=float(b["frequency"]); e=float(b["eps"])
        if math.isfinite(f) and math.isfinite(e) and f>0 and e>0:
            anharmonic_sticks.append({
                "mode":None,"frequency":f,"eps":e,
                "source":"VPT2 overtone/combination",
            })

    if anharmonic_sticks:
        sets["anharmonic"]=anharmonic_sticks
        metadata_by_set["anharmonic"]=[
            "contains=VPT2_overtone_and_combination_bands_only",
        ]

    # A genuinely complete anharmonic spectrum exists only when VPT2
    # fundamentals are valid; do not create a misleading 'complete' spectrum
    # from harmonic fundamentals plus VPT2 bands.
    if fundamental_sticks:
        sets["complete"]=fundamental_sticks+anharmonic_sticks
        metadata_by_set["complete"]=[
            "contains=VPT2_fundamentals_plus_VPT2_overtone_and_combination_bands",
            "fundamental_intensity_source=central_hessian_harmonic_IR",
        ]

    if not sets:
        return []

    allfreq=[float(s["frequency"]) for sticks in sets.values() for s in sticks
             if math.isfinite(float(s["frequency"])) and float(s["frequency"])>0]
    if not allfreq:
        return []
    pad=max(5.0*fwhm,25.0)
    x0=float(xmin) if xmin is not None else max(0.0,min(allfreq)-pad)
    x1=float(xmax) if xmax is not None else max(allfreq)+pad
    if x1 <= x0:
        raise ValueError("IR x-max must be greater than x-min")
    n=int(math.floor((x1-x0)/step))+1
    x=x0+np.arange(n,dtype=float)*step
    if x[-1] < x1-1e-9:
        x=np.append(x,x1)

    curves={name:gaussian_curve(x,sticks,fwhm) for name,sticks in sets.items()}
    # One common normalization preserves relative amplitudes between the three
    # spectra. Prefer the complete spectrum as reference when it exists.
    if "complete" in curves and float(np.max(curves["complete"])) > 0:
        ref=float(np.max(curves["complete"]))
    else:
        ref=max((float(np.max(y)) for y in curves.values()),default=0.0)
    if ref <= 0:
        ref=1.0

    written=[]
    for name in ("fundamentals","anharmonic","complete"):
        if name not in curves:
            continue
        y=curves[name]
        fn=f"{prefix}_IR_{name}.dat"
        meta=[f"spectrum={name}",f"gaussian_FWHM_cm-1={fwhm:g}",
              f"range_cm-1={x0:g}..{x1:g}",f"grid_step_cm-1={step:g}"]
        meta.extend(metadata_by_set.get(name,[]))
        written.append(write_ir_dat(fn,x,y,ref,meta))
    return written

def map_vpt2_fundamentals(vib_modes, harmonic_freqs, fundamentals, tolerance=10.0):
    """Map ORCA VPT2 mode numbers (0..Nvib-1) to .hess mode indices.

    ORCA's VPT2 table renumbers only the vibrational modes, whereas .hess
    normally keeps the 0..3N-1 indexing including translations/rotations.
    Mapping is primarily by order and verified by the harmonic frequencies; a
    nearest-unused fallback handles unusual output ordering.
    """
    vib_modes = [int(x) for x in vib_modes]
    rows = sorted(fundamentals, key=lambda r: r["vpt2_mode"])
    mapping = {}
    used = set()

    if len(rows) == len(vib_modes):
        ordered_ok = True
        for hm, row in zip(vib_modes, rows):
            if abs(float(harmonic_freqs[hm]) - row["harmonic"]) > tolerance:
                ordered_ok = False
                break
        if ordered_ok:
            for hm, row in zip(vib_modes, rows):
                mapping[hm] = row
            return mapping

    for row in rows:
        choices = [hm for hm in vib_modes if hm not in used]
        if not choices:
            break
        hm = min(choices, key=lambda x: abs(float(harmonic_freqs[x]) - row["harmonic"]))
        diff = abs(float(harmonic_freqs[hm]) - row["harmonic"])
        if diff <= tolerance:
            mapping[hm] = row
            used.add(hm)
    return mapping

def infer_bonds(elems, xyz_bohr, scale):
    xyz = xyz_bohr * BOHR_TO_ANG
    bonds = []
    unknown = set()
    for i in range(len(elems)):
        ri = COV_RADII.get(elems[i])
        if ri is None:
            unknown.add(elems[i]); ri = 0.77
        for j in range(i+1, len(elems)):
            rj = COV_RADII.get(elems[j])
            if rj is None:
                unknown.add(elems[j]); rj = 0.77
            d = np.linalg.norm(xyz[i]-xyz[j])
            if 0.35 < d <= scale*(ri+rj):
                bonds.append((i,j))
    if unknown:
        print("WARNING: missing covalent radii for: " + ", ".join(sorted(unknown)) +
              "; using 0.77 Å fallback.", file=sys.stderr)
    return bonds

def adjacency(n, bonds):
    adj = [set() for _ in range(n)]
    for i,j in bonds:
        adj[i].add(j); adj[j].add(i)
    return adj

def connected_components(adj):
    seen=set(); comps=[]
    for start in range(len(adj)):
        if start in seen: continue
        stack=[start]; seen.add(start); comp=[]
        while stack:
            u=stack.pop(); comp.append(u)
            for v in adj[u]:
                if v not in seen:
                    seen.add(v); stack.append(v)
        comps.append(comp)
    return comps

def unit(v):
    n=np.linalg.norm(v)
    if n < 1e-14: raise ValueError("Zero-length vector.")
    return v/n

def angle_value(x,i,j,k):
    u=x[i]-x[j]; v=x[k]-x[j]
    c=np.dot(u,v)/(np.linalg.norm(u)*np.linalg.norm(v))
    return math.acos(float(np.clip(c,-1.0,1.0)))

def dihedral_value(x,i,j,k,l):
    # signed torsion in [-pi, pi]
    b0 = x[j]-x[i]
    b1 = x[k]-x[j]
    b2 = x[l]-x[k]
    e1 = unit(b1)
    v = b0 - np.dot(b0,e1)*e1
    w = b2 - np.dot(b2,e1)*e1
    nv=np.linalg.norm(v); nw=np.linalg.norm(w)
    if nv < 1e-12 or nw < 1e-12:
        raise ValueError("Undefined dihedral around a linear arrangement.")
    v/=nv; w/=nw
    return math.atan2(np.dot(np.cross(e1,v),w), np.dot(v,w))

def oop_value(x,i,j,k,l):
    # atom i out of plane defined by center j and neighbors k,l
    u = unit(x[i]-x[j])
    n = np.cross(x[k]-x[j], x[l]-x[j])
    nn=np.linalg.norm(n)
    if nn < 1e-12:
        raise ValueError("Undefined out-of-plane coordinate.")
    n/=nn
    return math.asin(float(np.clip(np.dot(u,n),-1.0,1.0)))

def make_perp_basis(axis):
    axis=unit(axis)
    refs=np.eye(3)
    ref=refs[np.argmin(np.abs(refs@axis))]
    p=unit(np.cross(axis,ref))
    q=unit(np.cross(axis,p))
    return p,q

def ic_value(ic, x):
    a=ic.atoms
    if ic.kind=="bond":
        return np.linalg.norm(x[a[0]]-x[a[1]])
    if ic.kind=="angle":
        return angle_value(x,*a)
    if ic.kind=="dihedral":
        return dihedral_value(x,*a)
    if ic.kind=="oop":
        return oop_value(x,*a)
    if ic.kind.startswith("linbend"):
        p=np.asarray(ic.aux[:3])
        ui=unit(x[a[0]]-x[a[1]])
        uk=unit(x[a[2]]-x[a[1]])
        return float(np.dot(ui+uk,p))
    raise ValueError(ic.kind)

def wrapped_delta(vp, vm, kind):
    d=vp-vm
    if kind in ("dihedral",):
        d=(d+math.pi)%(2*math.pi)-math.pi
    return d

def b_row(ic, xyz, h=1e-5):
    flat=xyz.reshape(-1)
    row=np.zeros(flat.size)
    for p in range(flat.size):
        xp=flat.copy(); xm=flat.copy()
        xp[p]+=h; xm[p]-=h
        vp=ic_value(ic,xp.reshape(xyz.shape))
        vm=ic_value(ic,xm.reshape(xyz.shape))
        row[p]=wrapped_delta(vp,vm,ic.kind)/(2*h)
    return row

def generate_candidates(elems, xyz, bonds, linear_cut_deg=175.0):
    n=len(elems); adj=adjacency(n,bonds)
    out=[]
    # All inferred bonds
    for i,j in bonds:
        out.append(IC("bond",(i,j)))
    # Angles, with two linear-bend coordinates near 180 degrees
    for j in range(n):
        ns=sorted(adj[j])
        for i,k in itertools.combinations(ns,2):
            th=math.degrees(angle_value(xyz,i,j,k))
            if th >= linear_cut_deg:
                axis=xyz[i]-xyz[j]
                p,q=make_perp_basis(axis)
                out.append(IC("linbend1",(i,j,k),tuple(p)))
                out.append(IC("linbend2",(i,j,k),tuple(q)))
            else:
                out.append(IC("angle",(i,j,k)))
    # Proper torsions i-j-k-l
    seen=set()
    for j,k in bonds:
        for a,b in ((j,k),(k,j)):
            for i in adj[a]-{b}:
                for l in adj[b]-{a}:
                    if i==l: continue
                    tup=(i,a,b,l)
                    rev=tup[::-1]
                    key=min(tup,rev)
                    if key in seen: continue
                    # Avoid torsions with near-linear adjacent angles
                    th1=math.degrees(angle_value(xyz,i,a,b))
                    th2=math.degrees(angle_value(xyz,a,b,l))
                    if th1>linear_cut_deg or th2>linear_cut_deg:
                        continue
                    try:
                        dihedral_value(xyz,*tup)
                    except ValueError:
                        continue
                    seen.add(key)
                    out.append(IC("dihedral",tup))
    # Out-of-plane candidates for centers with >=3 neighbors.
    # Generate all three choices for each neighbor triplet; rank selection removes redundancy.
    for j in range(n):
        ns=sorted(adj[j])
        if len(ns)>=3:
            for tri in itertools.combinations(ns,3):
                for pos in range(3):
                    i=tri[pos]
                    k,l=[tri[t] for t in range(3) if t!=pos]
                    ic=IC("oop",(i,j,k,l))
                    try:
                        oop_value(xyz,*ic.atoms)
                    except ValueError:
                        continue
                    out.append(ic)
    return out

def is_linear_molecule(xyz, masses):
    if len(xyz)<=2: return True
    com=np.average(xyz,axis=0,weights=masses)
    r=xyz-com
    I=np.zeros((3,3))
    for m,v in zip(masses,r):
        I += m*((np.dot(v,v)*np.eye(3))-np.outer(v,v))
    ev=np.linalg.eigvalsh(I)
    return ev[0] <= max(ev[-1],1e-30)*1e-7

def select_nonredundant(candidates, Bcand, target_rank, tol=1e-8):
    # Row-pivoted modified Gram-Schmidt.
    norms=np.linalg.norm(Bcand,axis=1)
    valid=np.where(norms>1e-10)[0]
    if len(valid)<target_rank:
        raise RuntimeError("Too few valid internal coordinates.")
    U=[]; chosen=[]; remaining=list(valid)
    while len(chosen)<target_rank:
        best=None; best_res=-1.0; best_vec=None
        for idx in remaining:
            v=Bcand[idx]/norms[idx]
            r=v.copy()
            for u in U:
                r-=np.dot(r,u)*u
            nr=np.linalg.norm(r)
            # small preference for bonds, then angles/linear bends, then oop/torsion
            kind=candidates[idx].kind
            pref={"bond":1.04,"angle":1.02,"linbend1":1.02,"linbend2":1.02,
                  "oop":1.00,"dihedral":1.00}.get(kind,1.0)
            score=nr*pref
            if score>best_res:
                best_res=score; best=idx; best_vec=r
        if best is None or np.linalg.norm(best_vec)<tol:
            break
        u=best_vec/np.linalg.norm(best_vec)
        U.append(u); chosen.append(best); remaining.remove(best)
    if len(chosen)!=target_rank:
        rank=np.linalg.matrix_rank(Bcand,tol)
        raise RuntimeError(
            f"Could construct only {len(chosen)} independent ICs; need {target_rank}. "
            f"Candidate B rank={rank}. Geometry may contain unsupported topology/linearities."
        )
    return chosen

def reconstruct_modes(H,masses):
    invsqrt=np.repeat(1/np.sqrt(masses),3)
    Hmw=(invsqrt[:,None]*H)*invsqrt[None,:]
    lam,L=np.linalg.eigh(Hmw)
    modes=invsqrt[:,None]*L
    freqs=np.sign(lam)*np.sqrt(np.abs(lam))*FREQ_FACTOR
    return freqs,modes

def atom_name(elems,i):
    return f"{elems[i]}{i+1}"

def ic_label(ic, elems):
    a=ic.atoms
    names=[atom_name(elems,i) for i in a]
    if ic.kind=="bond": return f"nu({names[0]}-{names[1]})"
    if ic.kind=="angle": return f"delta({names[0]}-{names[1]}-{names[2]})"
    if ic.kind.startswith("linbend"):
        axis="1" if ic.kind.endswith("1") else "2"
        return f"delta_lin{axis}({names[0]}-{names[1]}-{names[2]})"
    if ic.kind=="dihedral": return f"tau({names[0]}-{names[1]}-{names[2]}-{names[3]})"
    if ic.kind=="oop":
        return f"gamma({names[0]};{names[1]},{names[2]},{names[3]})"
    return f"{ic.kind}{a}"

def cycle_edges_from_graph(n, bonds):
    """Return edges that belong to at least one graph cycle."""
    adj=adjacency(n,bonds)
    cyc=set()
    for u,v in bonds:
        stack=[u]; seen={u}; found=False
        while stack and not found:
            a=stack.pop()
            for b in adj[a]:
                if {a,b}=={u,v}:
                    continue
                if b==v:
                    cyc.add(tuple(sorted((u,v))))
                    found=True
                    break
                if b not in seen:
                    seen.add(b); stack.append(b)
    return cyc

def ring_systems_from_cycle_edges(n, ring_edges):
    """Connected components of the subgraph made only of cyclic edges.

    Two phenyl rings linked by a single bond are therefore two distinct ring
    systems; fused rings sharing cyclic edges/atoms form one ring system.
    """
    radj=[set() for _ in range(n)]
    for i,j in ring_edges:
        radj[i].add(j); radj[j].add(i)
    systems=[]; atom_to_system={}; seen=set()
    for a in range(n):
        if a in seen or not radj[a]:
            continue
        stack=[a]; seen.add(a); comp=[]
        while stack:
            u=stack.pop(); comp.append(u)
            for v in radj[u]:
                if v not in seen:
                    seen.add(v); stack.append(v)
        sid=len(systems)
        systems.append(set(comp))
        for x in comp:
            atom_to_system[x]=sid
    return systems, atom_to_system

def _pair_label(a,b):
    if a=='H' and b!='H':
        a,b=b,a
    elif b!='H' and a!='H' and a>b:
        a,b=b,a
    return f"{a}-{b}"

def _angle_el_label(ei,ej,ek):
    return f"{ei}-{ej}-{ek}"

def _inter_ring_edge(i,j,ring_edges,atom_to_system):
    edge=tuple(sorted((i,j)))
    if edge in ring_edges:
        return False
    si=atom_to_system.get(i); sj=atom_to_system.get(j)
    return si is not None and sj is not None and si != sj

def generic_family_key_and_label(ic, elems):
    """Molecule-agnostic family based only on element types and IC kind."""
    a=ic.atoms
    if ic.kind=='bond':
        pair=_pair_label(elems[a[0]],elems[a[1]])
        return ('stretch',pair), f"{pair} stretching"
    if ic.kind=='angle':
        i,j,k=a; ei,ej,ek=elems[i],elems[j],elems[k]
        if ei=='H' or ek=='H':
            return ('bend_xh',_pair_label(elems[j],'H')), f"{_pair_label(elems[j],'H')} bending"
        lbl=_angle_el_label(ei,ej,ek)
        return ('bend',lbl), f"{lbl} bending"
    if ic.kind.startswith('linbend'):
        i,j,k=a; lbl=_angle_el_label(elems[i],elems[j],elems[k])
        return ('linear_bend',lbl), f"{lbl} linear bending"
    if ic.kind=='dihedral':
        _,j,k,_=a; pair=_pair_label(elems[j],elems[k])
        return ('torsion',pair), f"{pair} torsion"
    if ic.kind=='oop':
        i,j,_,_=a
        pair=_pair_label(elems[j],elems[i])
        return ('oop',pair), f"{pair} out-of-plane bending"
    return (ic.kind,tuple(elems[i] for i in a)), ic.kind

def topology_family_key_and_label(ic, elems, ring_edges, ring_atoms,
                                  atom_to_system, adj):
    """Conservative topology-aware family.

    Uses only connectivity and graph cycles available from the .hess geometry.
    It deliberately does NOT infer aromaticity or bond order.
    """
    a=ic.atoms
    if ic.kind=='bond':
        i,j=a; pair=_pair_label(elems[i],elems[j]); edge=tuple(sorted((i,j)))
        if 'H' in (elems[i],elems[j]):
            heavy=j if elems[i]=='H' else i
            if heavy in ring_atoms:
                return ('stretch_ring_site_xh',pair), f"ring-site {pair} stretching"
            return ('stretch_xh',pair), f"{pair} stretching"
        if edge in ring_edges:
            return ('stretch_cyclic',pair), f"cyclic {pair} stretching"
        if _inter_ring_edge(i,j,ring_edges,atom_to_system):
            return ('stretch_inter_ring',pair), f"inter-ring {pair} stretching"
        if (i in ring_atoms) ^ (j in ring_atoms):
            return ('stretch_exocyclic',pair), f"exocyclic {pair} stretching"
        return ('stretch',pair), f"{pair} stretching"

    if ic.kind=='angle':
        i,j,k=a; ei,ej,ek=elems[i],elems[j],elems[k]
        if ei=='H' or ek=='H':
            other=k if ei=='H' else i
            pair=_pair_label(elems[j],'H')
            if j in ring_atoms and other in ring_atoms:
                return ('bend_ring_site_xh',pair), f"ring-site {pair} in-plane bending"
            return ('bend_xh',pair), f"{pair} bending"
        si=atom_to_system.get(i); sj=atom_to_system.get(j); sk=atom_to_system.get(k)
        if si is not None and si==sj==sk:
            lbl=_angle_el_label(ei,ej,ek)
            return ('ring_deformation',lbl), f"cyclic-ring deformation ({lbl} bend)"
        lbl=_angle_el_label(ei,ej,ek)
        return ('bend',lbl), f"{lbl} bending"

    if ic.kind.startswith('linbend'):
        i,j,k=a; lbl=_angle_el_label(elems[i],elems[j],elems[k])
        return ('linear_bend',lbl), f"{lbl} linear bending"

    if ic.kind=='dihedral':
        i,j,k,l=a; central=tuple(sorted((j,k))); pair=_pair_label(elems[j],elems[k])
        terminal_h=(elems[i]=='H' or elems[l]=='H')
        # A terminal H attached to a cyclic site and rotating about a cyclic bond
        # is naturally described as an out-of-plane/ring-site wag coordinate.
        if terminal_h and central in ring_edges:
            heavy=j if elems[i]=='H' else k
            xh=_pair_label(elems[heavy],'H')
            return ('oop_ring_site_xh',xh), f"ring-site {xh} out-of-plane bending"
        if _inter_ring_edge(j,k,ring_edges,atom_to_system):
            return ('torsion_inter_ring',pair), f"inter-ring {pair} torsion"
        if central in ring_edges:
            return ('torsion_cyclic',pair), "cyclic-ring torsional/out-of-plane deformation"
        return ('torsion',pair), f"{pair} torsion"

    if ic.kind=='oop':
        i,j,k,l=a
        if elems[i]=='H' and j in ring_atoms:
            pair=_pair_label(elems[j],'H')
            return ('oop_ring_site_xh',pair), f"ring-site {pair} out-of-plane bending"
        sids=[atom_to_system.get(x) for x in a]
        nonnull=[x for x in sids if x is not None]
        if len(nonnull)>=3 and len(set(nonnull))==1:
            return ('ring_oop','ring'), "cyclic-ring out-of-plane deformation"
        pair=_pair_label(elems[j],elems[i])
        return ('oop',pair), f"{pair} out-of-plane bending"

    return generic_family_key_and_label(ic,elems)

def grouped_ped(pct_col, D_col, ics, family_func):
    groups={}; members={}; labels={}
    for idx,ic in enumerate(ics):
        key,label=family_func(ic)
        groups[key]=groups.get(key,0.0)+float(pct_col[idx])
        members.setdefault(key,[]).append(idx)
        labels[key]=label
    order=sorted(groups,key=lambda k:groups[k],reverse=True)
    return [(k,labels[k],groups[k],members[k]) for k in order]

def _phase_qualified_family(label, key, members, pct_col, D_col):
    if 'stretch' not in key[0] or len(members)<2:
        return label
    fam_total=sum(pct_col[i] for i in members)
    active=[i for i in members if pct_col[i] >= max(1.0,0.05*fam_total)]
    if len(active)<2:
        return label
    vals=np.asarray([D_col[i] for i in active],float)
    signs=np.sign(vals); signs[signs==0]=1
    mags=np.abs(vals)
    uniform=(mags.max()/max(mags.min(),1e-30) < 1.35)
    base=label.replace(' stretching','')
    if np.all(signs==signs[0]) and uniform:
        return f"in-phase {base} stretching"
    if len(active)==2 and signs[0]!=signs[1] and uniform:
        return f"opposite-phase {base} stretching"
    if np.any(signs!=signs[0]):
        return f"mixed-phase {base} stretching"
    return label

def grouped_assignment(groups, pct_col, D_col, mixed_second=20.0, pure_threshold=70.0):
    if not groups:
        return "unassigned"
    k1,l1,p1,m1=groups[0]
    l1q=_phase_qualified_family(l1,k1,m1,pct_col,D_col)
    if len(groups)==1:
        return l1q
    k2,l2,p2,m2=groups[1]
    l2q=_phase_qualified_family(l2,k2,m2,pct_col,D_col)
    if p1 < pure_threshold or p2 >= mixed_second:
        labels=[l1q,l2q]
        if len(groups)>2 and p1<50.0 and groups[2][2]>=15.0:
            k3,l3,p3,m3=groups[2]
            labels.append(_phase_qualified_family(l3,k3,m3,pct_col,D_col))
        return "mixed " + " / ".join(labels)
    return l1q

def main():
    ap=argparse.ArgumentParser(
        description="Automatic molecule-agnostic PED assignment from an ORCA .hess file, with optional VPT2 integration",
        epilog=(
            f"Contact: {CONTACT_EMAIL}\n"
            f"Manual: {MANUAL_URL}\n"
            f"Check GitHub for updates and new releases: {GITHUB_URL}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("hess", help="central ORCA .hess file (never a _Dxxx displaced Hessian)")
    ap.add_argument(
        "--version",
        action="version",
        version=(
            f"%(prog)s {__version__}\n"
            f"Contact: {CONTACT_EMAIL}\n"
            f"Manual: {MANUAL_URL}\n"
            f"Check GitHub for updates and new releases: {GITHUB_URL}"
        ),
    )
    ap.add_argument("--vpt2-out",default=None,
                    help="ORCA VPT2 .out file. If omitted, SAME_BASENAME.out is auto-detected")
    ap.add_argument("--no-auto-vpt2",action="store_true",
                    help="do not auto-detect SAME_BASENAME.out")
    ap.add_argument("--vpt2-match-tol",type=float,default=10.0,
                    help="max harmonic-frequency mismatch for mapping VPT2 modes to .hess modes (default 10 cm^-1)")
    ap.add_argument("--bond-scale",type=float,default=1.25,
                    help="bond detection factor times sum of covalent radii (default 1.25)")
    ap.add_argument("--linear-cut",type=float,default=175.0,
                    help="angles >= this value are treated as linear bends (default 175)")
    ap.add_argument("--min-freq",type=float,default=20.0,
                    help="ignore modes with |frequency| below this cm^-1 (default 20)")
    ap.add_argument("--top",type=int,default=5,help="number of top primitive IC contributions to print")
    ap.add_argument("--min-percent",type=float,default=1.0,
                    help="do not print primitive-IC contributions below this percent")
    ap.add_argument("--family-top",type=int,default=4,
                    help="number of topology-aware grouped families to print (default 4)")
    ap.add_argument("--family-min-percent",type=float,default=2.0,
                    help="do not print grouped families below this percent (default 2)")
    ap.add_argument("--pure-threshold",type=float,default=70.0,
                    help="family percent required for a non-mixed assignment (default 70)")
    ap.add_argument("--mixed-second",type=float,default=20.0,
                    help="second-family percent that forces a mixed assignment (default 20)")
    ap.add_argument("--show-generic",action="store_true",
                    help="also print molecule-agnostic element/type families")
    ap.add_argument("--show-raw",action="store_true",
                    help="also print the top primitive internal-coordinate contributions")
    ap.add_argument("--show-fermi",action="store_true",
                    help="print the raw ORCA Fermi-resonance analysis block when available")
    ap.add_argument("--output-dir",default=None,
                    help="subdirectory for ALL generated files (default: BASENAME_analysis next to the .hess)")
    ap.add_argument("--csv-prefix",default=None,
                    help="basename for CSV tables inside the output directory (default: Hessian basename)")
    ap.add_argument("--no-csv",action="store_true",
                    help="do not write CSV assignment/PED tables")
    ap.add_argument("--no-avogadro-cjson",action="store_true",
                    help="do not write the Avogadro CJSON file containing all harmonic normal modes")
    ap.add_argument("--cjson-name",default=None,
                    help="filename for Avogadro CJSON inside the output directory")
    ap.add_argument("--no-ir-spectra",action="store_true",
                    help="do not write broadened IR .dat spectra")
    ap.add_argument("--ir-prefix",default=None,
                    help="prefix for IR .dat files (default: Hessian basename)")
    ap.add_argument("--ir-fwhm",type=float,default=10.0,
                    help="Gaussian IR band FWHM in cm^-1 (default 10)")
    ap.add_argument("--ir-xmin",type=float,default=None,
                    help="IR minimum wavenumber in cm^-1 (default automatic)")
    ap.add_argument("--ir-xmax",type=float,default=None,
                    help="IR maximum wavenumber in cm^-1 (default automatic)")
    ap.add_argument("--ir-step",type=float,default=1.0,
                    help="IR grid spacing in cm^-1 (default 1)")
    args=ap.parse_args()

    print(f"# Contact: {CONTACT_EMAIL}")
    print(f"# Manual: {MANUAL_URL}")
    print(f"# Check GitHub for updates and new releases: {GITHUB_URL}")
    print("#")

    hess_path=Path(args.hess).expanduser().resolve()
    if args.output_dir:
        od=Path(args.output_dir).expanduser()
        output_dir=od if od.is_absolute() else hess_path.parent/od
    else:
        output_dir=hess_path.parent/f"{hess_path.stem}_analysis"
    output_dir.mkdir(parents=True,exist_ok=True)
    generated_files=[]

    if re.search(r"_D\d+\.hess$",hess_path.name,re.I):
        raise SystemExit(
            "The supplied file looks like a displaced VPT2 Hessian (_Dxxx.hess). "
            "Use the central Hessian, e.g. basename.hess."
        )

    elems,masses,xyz,H,freqs,modes,ir_rows=parse_hess(hess_path)
    n=len(elems)
    if H.shape!=(3*n,3*n):
        raise SystemExit(f"Hessian is {H.shape}, expected {(3*n,3*n)}")

    if freqs is None or modes is None or modes.shape!=(3*n,3*n):
        print("Normal modes/frequencies absent or incomplete: diagonalizing Hessian.",file=sys.stderr)
        freqs,modes=reconstruct_modes(H,masses)

    bonds=infer_bonds(elems,xyz,args.bond_scale)
    adj=adjacency(n,bonds)
    comps=connected_components(adj)
    if len(comps)>1:
        raise SystemExit(
            f"Connectivity inference found {len(comps)} disconnected fragments. "
            "This script currently expects one connected molecule. "
            "Adjust --bond-scale or extend the coordinate definition for intermolecular modes."
        )

    linear=is_linear_molecule(xyz,masses)
    target=3*n-(5 if linear else 6)
    ring_edges=cycle_edges_from_graph(n,bonds)
    ring_atoms=set(i for e in ring_edges for i in e)
    ring_systems,atom_to_system=ring_systems_from_cycle_edges(n,ring_edges)

    candidates=generate_candidates(elems,xyz,bonds,args.linear_cut)
    if not candidates:
        raise SystemExit("No internal coordinates generated.")

    rows=[]; good=[]
    for ic in candidates:
        try:
            r=b_row(ic,xyz)
            if np.all(np.isfinite(r)):
                rows.append(r); good.append(ic)
        except Exception:
            pass
    candidates=good
    Bcand=np.vstack(rows)

    chosen_idx=select_nonredundant(candidates,Bcand,target)
    ics=[candidates[i] for i in chosen_idx]
    B=Bcand[chosen_idx,:]

    # Internal force constant matrix F from f = B^T F B.
    Binv=np.linalg.pinv(B,rcond=1e-10)
    F=Binv.T@H@Binv
    F=(F+F.T)/2

    Hrec=B.T@F@B
    relerr=np.linalg.norm(H-Hrec)/max(np.linalg.norm(H),1e-30)

    vib=np.where(np.abs(freqs)>=args.min_freq)[0]
    if len(vib)>target:
        vib=vib[np.argsort(np.abs(freqs[vib]))[-target:]]
        vib=np.sort(vib)
    if len(vib)<target:
        print(f"WARNING: found only {len(vib)} modes above threshold; expected {target}.",file=sys.stderr)

    l=modes[:,vib]
    D=B@l
    fdiag=np.diag(F)
    if np.any(fdiag < -1e-8):
        bad=np.where(fdiag<0)[0]
        raise SystemExit(
            "Negative diagonal internal force constants found for selected ICs: "
            + ", ".join(ic_label(ics[i],elems) for i in bad[:10])
            + ". The structure may not be a minimum or the IC set is unsuitable."
        )
    fdiag=np.maximum(fdiag,0.0)
    raw=fdiag[:,None]*D**2
    denom=raw.sum(axis=0)
    if np.any(denom<=0):
        raise SystemExit("PED normalization failed for one or more modes.")
    pct=100*raw/denom[None,:]

    # --- VPT2 auto-detection / validation ---
    vpt2=None
    vpt2_path=None
    if args.vpt2_out:
        vpt2_path=Path(args.vpt2_out)
    elif not args.no_auto_vpt2:
        auto=hess_path.with_suffix('.out')
        if auto.exists():
            vpt2_path=auto
    if vpt2_path is not None:
        if not vpt2_path.exists():
            print(f"WARNING: requested VPT2 output not found: {vpt2_path}",file=sys.stderr)
        else:
            vpt2=parse_vpt2_output(vpt2_path, expected_fundamentals=len(vib), expected_harmonics=[float(freqs[mi]) for mi in vib])

    vpt2_map={}
    if vpt2 and vpt2.get("valid"):
        vpt2_map=map_vpt2_fundamentals(vib,freqs,vpt2["fundamentals"],args.vpt2_match_tol)
        if len(vpt2_map)!=len(vpt2["fundamentals"]):
            print(
                f"WARNING: mapped {len(vpt2_map)}/{len(vpt2['fundamentals'])} VPT2 fundamentals "
                "to harmonic .hess modes. Check method/basename consistency or --vpt2-match-tol.",
                file=sys.stderr
            )

    print(f"# Molecule: {n} atoms | {'linear' if linear else 'non-linear'}")
    print(f"# Bonds inferred: {len(bonds)} | candidate ICs: {len(candidates)} | selected ICs: {len(ics)}")
    print(f"# Cartesian-Hessian reconstruction relative error: {relerr:.3e}")
    if relerr>1e-3:
        print("# WARNING: reconstruction error is relatively high; inspect geometry/connectivity.",file=sys.stderr)
    print(f"# Ring/cycle bonds detected: {len(ring_edges)} | ring atoms: {len(ring_atoms)} | ring systems: {len(ring_systems)}")

    if vpt2_path is None:
        print("# VPT2: no matching .out file supplied/found -> harmonic/PED analysis only")
    elif vpt2 is None:
        print(f"# VPT2: output unavailable ({vpt2_path}) -> harmonic/PED analysis only")
    elif vpt2["status"]=="not-detected":
        print(f"# VPT2: no VPT2 analysis detected in {vpt2_path.name} -> harmonic/PED analysis only")
    elif vpt2["status"]=="incomplete":
        exp=vpt2.get("expected_fundamentals")
        got=vpt2.get("raw_fundamental_count",0)
        print(f"# VPT2: INCOMPLETE/RUNNING in {vpt2_path.name} -> partial anharmonic data ignored")
        print(f"#       Diagnostics: fundamental rows={got}/{exp if exp is not None else '?'}; "
              f"VPT2-End={'yes' if vpt2.get('analysis_end') else 'no'}; "
              f"ORCA-normal-termination={'yes' if vpt2.get('normal_termination') else 'no'}")
    elif vpt2["status"]=="complete-invalid":
        bad=len(vpt2.get("nonfinite_fundamentals",[]))
        print(f"# VPT2: COMPLETE BUT NUMERICALLY INVALID in {vpt2_path.name}")
        print(f"#       fundamental rows={vpt2.get('raw_fundamental_count',0)}/{vpt2.get('expected_fundamentals','?')}; "
              f"non-finite fundamentals={bad}; VPT2-End={'yes' if vpt2.get('analysis_end') else 'no'}; "
              f"ORCA-normal-termination={'yes' if vpt2.get('normal_termination') else 'no'}")
        if bad:
            print("#       inf/nan values were found in the VPT2 fundamentals; all VPT2 frequencies/bands are ignored.")
        if not vpt2.get("harmonic_match",True):
            print("#       Harmonic frequencies in the VPT2 table do not match the central Hessian.")
    else:
        term="yes" if vpt2["normal_termination"] else "no"
        vend="yes" if vpt2.get("analysis_end") else "no"
        nbadbands=len(vpt2.get("invalid_bands",[]))
        print(f"# VPT2: COMPLETE + VALID in {vpt2_path.name} | fundamentals={len(vpt2['fundamentals'])} | "
              f"finite overtone/combination bands={len(vpt2.get('finite_bands',[]))} | "
              f"invalid bands omitted={nbadbands} | VPT2 End={vend} | ORCA normal termination={term}")
    print("#")

    # Integrated harmonic IR intensities (km/mol), reconstructed from the
    # central Hessian $ir_spectrum T**2 values using ORCA's convention.
    harmonic_intensity_map = harmonic_ir_intensity_map(ir_rows)

    topo_func=lambda ic: topology_family_key_and_label(
        ic,elems,ring_edges,ring_atoms,atom_to_system,adj)
    gen_func=lambda ic: generic_family_key_and_label(ic,elems)

    print(f"{'Mode':>5} {'Harm/cm-1':>11} {'VPT2/cm-1':>11} {'Harm.Int/km mol-1':>18}  {'Assignment':<62} Grouped PED")
    print("-"*192)
    summaries=[]; detailed=[]; family_rows=[]; mode_assignments={}; mode_groups={}

    for col,mi in enumerate(vib):
        groups=grouped_ped(pct[:,col],D[:,col],ics,topo_func)
        generic_groups=grouped_ped(pct[:,col],D[:,col],ics,gen_func)
        ass=grouped_assignment(groups,pct[:,col],D[:,col],
                               mixed_second=args.mixed_second,pure_threshold=args.pure_threshold)
        mode_assignments[int(mi)]=ass
        mode_groups[int(mi)]=groups

        gp=[]; nkeep=0
        for key,label,val,members in groups:
            if val < args.family_min_percent:
                continue
            shown_label=_phase_qualified_family(label,key,members,pct[:,col],D[:,col])
            gp.append(f"{shown_label} {val:.2f}%")
            family_rows.append([int(mi),float(freqs[mi]),ass,"topology",shown_label,key[0],float(val)])
            nkeep+=1
            if nkeep>=args.family_top:
                break

        vrow=vpt2_map.get(int(mi))
        vfreq=vrow["fundamental"] if vrow else None
        vtxt=f"{vfreq:11.2f}" if vfreq is not None else f"{'--':>11}"
        hint = harmonic_intensity_map.get(int(mi))
        hitxt = f"{hint:18.4f}" if hint is not None else f"{'--':>18}"
        print(f"{mi:5d} {freqs[mi]:11.2f} {vtxt} {hitxt}  {ass:<62} " + "; ".join(gp))

        if args.show_generic:
            gg=[]
            for key,label,val,members in generic_groups[:args.family_top]:
                if val < args.family_min_percent:
                    continue
                sl=_phase_qualified_family(label,key,members,pct[:,col],D[:,col])
                gg.append(f"{sl} {val:.2f}%")
                family_rows.append([int(mi),float(freqs[mi]),ass,"generic",sl,key[0],float(val)])
            print("      generic: " + "; ".join(gg))

        order=np.argsort(pct[:,col])[::-1]
        rawpieces=[]; rawkeep=0
        for r in order:
            if pct[r,col] < args.min_percent:
                continue
            phase="+" if D[r,col]>=0 else "-"
            rawpieces.append(f"{ic_label(ics[r],elems)} {pct[r,col]:.2f}%[{phase}]")
            detailed.append([int(mi),float(freqs[mi]),vfreq,
                             harmonic_intensity_map.get(int(mi),""),
                             ass,ic_label(ics[r],elems),
                             ics[r].kind,float(pct[r,col]),phase,float(D[r,col]),float(fdiag[r])])
            rawkeep+=1
            if rawkeep>=args.top:
                break
        if args.show_raw:
            print("      raw ICs: " + "; ".join(rawpieces))

        dominant_family=groups[0][2] if groups else float('nan')
        summaries.append([
            int(mi), vrow["vpt2_mode"] if vrow else "", float(freqs[mi]),
            harmonic_intensity_map.get(int(mi),""),
            vfreq if vfreq is not None else "", vrow["difference"] if vrow else "",
            (harmonic_intensity_map.get(int(mi),"") if vrow else ""),
            ("central_hessian_harmonic_IR" if vrow and int(mi) in harmonic_intensity_map else ""),
            ass, "; ".join(gp), "; ".join(rawpieces), float(dominant_family)
        ])

    # --- Anharmonic bands: use ORCA's frequencies/intensities; assignment is by zero-order constituents. ---
    band_rows=[]
    if vpt2 and vpt2.get("valid") and vpt2.get("finite_bands"):
        vpt2_to_hess={row["vpt2_mode"]:hm for hm,row in vpt2_map.items()}
        print("\n# VPT2 overtones and combination bands")
        print(f"{'State':>12} {'Freq/cm-1':>11} {'Int/km mol-1':>13}  Assignment (zero-order constituents)")
        print("-"*125)
        for b in vpt2["finite_bands"]:
            m1,m2=b["mode1"],b["mode2"]
            h1=vpt2_to_hess.get(m1); h2=vpt2_to_hess.get(m2)
            a1=mode_assignments.get(h1,f"VPT2 mode {m1}")
            a2=mode_assignments.get(h2,f"VPT2 mode {m2}")
            if m1==m2:
                state=f"2nu{m1}"
                assignment=f"overtone of {a1}"
            else:
                state=f"nu{m1}+nu{m2}"
                assignment=f"{a1} + {a2}"
            print(f"{state:>12} {b['frequency']:11.2f} {b['intensity']:13.2f}  {assignment}")
            band_rows.append([
                state,m1,m2,h1 if h1 is not None else "",h2 if h2 is not None else "",
                b["frequency"],b["eps"],b["intensity"],b["t2"],b["tx"],b["ty"],b["tz"],assignment
            ])

    if vpt2 and vpt2.get("valid") and vpt2["fermi_block"]:
        print("\n# Fermi-resonance analysis: present in ORCA VPT2 output.")
        print("# Important: PED percentages above describe harmonic zero-order normal modes;")
        print("# strongly resonant anharmonic states can mix and should not be interpreted as pure fundamentals.")
        if args.show_fermi:
            print("\n"+vpt2["fermi_block"].strip())

    # --- Broadened IR spectra (.dat), positive-going relative absorbance ---
    if not args.no_ir_spectra:
        harmonic_sticks=harmonic_ir_sticks(ir_rows,vib)
        irbase=Path(args.ir_prefix).name if args.ir_prefix else hess_path.stem
        irprefix=str(output_dir/irbase)
        finite_bands_for_ir=(vpt2.get("finite_bands",[]) if vpt2 and vpt2.get("valid") else [])
        try:
            irfiles=generate_ir_spectra(
                irprefix,harmonic_sticks,vpt2_map,finite_bands_for_ir,args.ir_fwhm,
                xmin=args.ir_xmin,xmax=args.ir_xmax,step=args.ir_step)
            if irfiles:
                print("\n# IR spectra written (relative absorbance, ascending wavenumber):")
                for fn in irfiles:
                    generated_files.append(str(Path(fn).resolve()))
                    print(f"#   {fn}")
            elif not harmonic_sticks:
                print("\n# IR spectra: $ir_spectrum data not found in central Hessian; no IR .dat written.")
        except ValueError as exc:
            print(f"\n# IR spectra not written: {exc}",file=sys.stderr)

    # --- Native Avogadro CJSON: one file, all selectable harmonic modes ---
    if not args.no_avogadro_cjson:
        cjson_name=Path(args.cjson_name).name if args.cjson_name else f"{hess_path.stem}_avogadro_vibrations.cjson"
        cjson_path=output_dir/cjson_name
        try:
            write_avogadro_cjson(cjson_path,hess_path.stem,elems,xyz,bonds,freqs,modes,vib,ir_rows)
            generated_files.append(str(cjson_path.resolve()))
            print(f"\n# Avogadro vibrations CJSON written: {cjson_path}")
            print("#   Open this single file in Avogadro, then use Analyze -> Vibrational Modes.")
            print("#   The displayed/animated vectors and frequencies are harmonic normal modes.")
            print("#   Avogadro numbering is aligned to Hessian/PED indices: mode 6 in Avogadro = mode 6 in the table.")
            print("#   Low-numbered rows before the vibrational manifold are translation/rotation modes included only for numbering alignment.")
        except Exception as exc:
            print(f"\n# Avogadro CJSON not written: {exc}",file=sys.stderr)

    print("\n# Selected internal-coordinate set:")
    for i,ic in enumerate(ics,1):
        print(f"# {i:3d}  {ic_label(ic,elems)}")

    if not args.no_csv:
        csvbase=Path(args.csv_prefix).name if args.csv_prefix else hess_path.stem
        p=output_dir/csvbase
        sfile=str(p)+"_summary.csv"
        ffile=str(p)+"_families.csv"
        dfile=str(p)+"_ped.csv"
        with open(sfile,"w",newline="") as fh:
            w=csv.writer(fh)
            w.writerow(["hess_mode","vpt2_mode",
                        "harmonic_frequency_cm-1","harmonic_intensity_km_mol",
                        "vpt2_fundamental_cm-1","vpt2_difference_cm-1",
                        "vpt2_fundamental_intensity_km_mol",
                        "vpt2_fundamental_intensity_source",
                        "assignment","grouped_contributions",
                        "top_primitive_ICs","dominant_family_percent"])
            w.writerows(summaries)
        with open(ffile,"w",newline="") as fh:
            w=csv.writer(fh)
            w.writerow(["mode","harmonic_frequency_cm-1","assignment","grouping_level",
                        "family","family_type","percent"])
            w.writerows(family_rows)
        with open(dfile,"w",newline="") as fh:
            w=csv.writer(fh)
            w.writerow(["mode","harmonic_frequency_cm-1","vpt2_fundamental_cm-1",
                        "harmonic_intensity_km_mol","assignment",
                        "internal_coordinate","type","percent","phase","D_value","F_diagonal"])
            w.writerows(detailed)
        generated_files.extend([str(Path(sfile).resolve()),str(Path(ffile).resolve()),str(Path(dfile).resolve())])
        print(f"\nWrote: {sfile}")
        print(f"Wrote: {ffile}")
        print(f"Wrote: {dfile}")

        # Unified IR transition table with both harmonic and anharmonic intensities.
        tfile=str(p)+"_ir_transitions.csv"
        with open(tfile,"w",newline="") as fh:
            w=csv.writer(fh)
            w.writerow([
                "transition_type","state","hess_mode","vpt2_mode1","vpt2_mode2",
                "frequency_cm-1","intensity_km_mol","intensity_level",
                "intensity_source","assignment"
            ])
            for mi in vib:
                mi=int(mi)
                hint=harmonic_intensity_map.get(mi,"")
                w.writerow([
                    "harmonic_fundamental",f"nu{mi}",mi,"","",
                    float(freqs[mi]),hint,"harmonic",
                    "central_hessian_$ir_spectrum",mode_assignments.get(mi,"")
                ])
                vr=vpt2_map.get(mi)
                if vr:
                    w.writerow([
                        "vpt2_fundamental",f"nu{vr['vpt2_mode']}",mi,
                        vr["vpt2_mode"],"",vr["fundamental"],hint,
                        "harmonic_intensity_at_VPT2_frequency",
                        "central_hessian_$ir_spectrum",
                        mode_assignments.get(mi,"")
                    ])
            for br in band_rows:
                state,m1,m2,h1,h2,freq,eps,inten,t2,tx,ty,tz,assignment=br
                w.writerow([
                    "vpt2_overtone" if m1==m2 else "vpt2_combination",
                    state,"",m1,m2,freq,inten,"anharmonic",
                    "ORCA_VPT2_overtone_combination_Int",assignment
                ])
        generated_files.append(str(Path(tfile).resolve()))
        print(f"Wrote: {tfile}")

        if vpt2 and vpt2.get("valid"):
            bfile=str(p)+"_vpt2_bands.csv"
            with open(bfile,"w",newline="") as fh:
                w=csv.writer(fh)
                w.writerow(["state","vpt2_mode1","vpt2_mode2","hess_mode1","hess_mode2",
                            "frequency_cm-1","eps_L_mol_cm","anharmonic_intensity_km_mol","T2","Tx","Ty","Tz",
                            "zero_order_assignment"])
                w.writerows(band_rows)
            generated_files.append(str(Path(bfile).resolve()))
            print(f"Wrote: {bfile}")
            if vpt2["fermi_block"]:
                rfile=str(p)+"_fermi.txt"
                Path(rfile).write_text(vpt2["fermi_block"].strip()+"\n")
                generated_files.append(str(Path(rfile).resolve()))
                print(f"Wrote: {rfile}")

    # --- Manifest: every file generated by this run lives in output_dir ---
    manifest_path=output_dir/f"{hess_path.stem}_manifest.txt"
    manifest_lines=[
        f"orca_ped_analyzer version: {__version__}",
        f"central_hessian: {hess_path}",
        f"vpt2_output: {vpt2_path if vpt2_path is not None else 'none'}",
        f"vpt2_status: {vpt2.get('status') if vpt2 else 'not-used'}",
        f"ir_fwhm_cm-1: {args.ir_fwhm}",
        f"output_directory: {output_dir}",
        "",
        "generated_files:",
    ] + [f"  {Path(x).name}" for x in generated_files]
    manifest_path.write_text("\n".join(manifest_lines)+"\n")
    print(f"\n# All generated files are in: {output_dir}")
    print(f"# Manifest: {manifest_path}")

if __name__=="__main__":
    main()
