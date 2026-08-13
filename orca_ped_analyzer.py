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

__version__ = "2026.08.11-vpt2.8"

BOHR_TO_ANG = 0.529177210903
FREQ_FACTOR = 5140.487143715827  # sqrt(Eh/(bohr^2*amu))/(2*pi*c) -> cm^-1

# Approximate single-bond covalent radii (Angstrom), mostly Cordero/Pyykko-like.
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
'Tl':1.45,'Pb':1.46,'Bi':1.48
}

# Atomic numbers for Avogadro CJSON export.
_PERIODIC = [
    'H','He','Li','Be','B','C','N','O','F','Ne','Na','Mg','Al','Si','P','S','Cl','Ar',
    'K','Ca','Sc','Ti','V','Cr','Mn','Fe','Co','Ni','Cu','Zn','Ga','Ge','As','Se','Br','Kr',
    'Rb','Sr','Y','Zr','Nb','Mo','Tc','Ru','Rh','Pd','Ag','Cd','In','Sn','Sb','Te','I','Xe',
    'Cs','Ba','La','Ce','Pr','Nd','Pm','Sm','Eu','Gd','Tb','Dy','Ho','Er','Tm','Yb','Lu',
    'Hf','Ta','W','Re','Os','Ir','Pt','Au','Hg','Tl','Pb','Bi','Po','At','Rn'
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

# NOTE: Full source omitted from this API payload in chat context.
# The repository version should contain the complete v2.8 source file.
