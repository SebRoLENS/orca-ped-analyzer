# ORCA PED Analyzer

**ORCA PED Analyzer** is a molecule-agnostic Python tool for assigning ORCA harmonic normal modes through a normalized diagonal potential-energy distribution (PED) in internal coordinates, with optional VPT2/GVPT2 integration, IR-spectrum generation, CSV export, and Avogadro CJSON export.

The central idea is deliberately conservative: assignments are derived from the **calculated atomic motion and an internal-coordinate energy decomposition**, not from empirical frequency windows such as “1600 cm⁻¹ = C=C”.

## Main features

- Reads the **central ORCA `.hess` file**.
- Builds primitive internal coordinates from molecular geometry and inferred connectivity: stretches, angle bends, torsions, out-of-plane coordinates, and linear bends when required.
- Constructs the Wilson `B` matrix numerically.
- Selects a non-redundant internal-coordinate set spanning `3N-6` vibrational degrees of freedom (`3N-5` for linear molecules).
- Transforms the Cartesian Hessian into the selected internal-coordinate representation.
- Computes a **normalized diagonal internal-coordinate PED** for each harmonic normal mode.
- Produces conservative topological assignments such as `cyclic C-C stretching`, `exocyclic C-N stretching`, `inter-ring C-C torsion`, and `ring-site C-H in-plane bending`.
- Detects mixed modes rather than forcing a single assignment.
- Optionally integrates completed ORCA **VPT2/GVPT2** results.
- Detects incomplete or numerically invalid (`inf`/`nan`) VPT2 calculations.
- Generates up to three broadened IR spectra: fundamentals, anharmonic-only overtone/combination bands, and complete spectrum.
- Exports a single **Avogadro CJSON** containing all harmonic normal modes.
- Keeps Avogadro mode numbering consistent with the ORCA/PED mode numbering by retaining the preceding translational/rotational entries in the CJSON.
- Writes detailed CSV tables and a run manifest.

## Requirements

- Python >= 3.9
- NumPy

Install the Python dependency with:

```bash
python3 -m pip install -r requirements.txt
```

On Debian, NumPy can also be installed with:

```bash
sudo apt install python3-numpy
```

## Quick start

Run the analysis on the **central Hessian**:

```bash
python3 orca_ped_analyzer.py molecule.hess
```

If `molecule.out` exists next to the Hessian, the script automatically checks whether it contains a completed and numerically valid VPT2/GVPT2 analysis.

If the VPT2 output has another name:

```bash
python3 orca_ped_analyzer.py molecule.hess \
    --vpt2-out molecule_restart.out
```

A more detailed analysis:

```bash
python3 orca_ped_analyzer.py molecule.hess \
    --show-generic --show-raw \
    --family-top 6 --family-min-percent 2 \
    --top 10 --min-percent 1 \
    --ir-fwhm 5
```

Do **not** use displaced VPT2 Hessians such as `molecule_D001.hess` as input. The script always uses the central Hessian.

## Default output

For `molecule.hess`, the default output directory is:

```text
molecule_analysis/
```

It may contain:

```text
molecule_summary.csv
molecule_families.csv
molecule_ped.csv
molecule_IR_fundamentals.dat
molecule_IR_anharmonic.dat
molecule_IR_complete.dat
molecule_avogadro_vibrations.cjson
molecule_vpt2_bands.csv
molecule_fermi.txt
molecule_manifest.txt
```

Conditional files are written only when the required data are available and valid.

## How the PED is defined

For a harmonic normal-mode displacement vector `l`, the internal-coordinate displacement is

$$D = B l$$

where `B` is the numerically constructed Wilson matrix.

The Cartesian Hessian `H` is transformed to an internal-coordinate force-constant representation using the pseudoinverse `B+`:

$$F = (B^+)^T H B^+$$

The contribution of internal coordinate `i` to a given mode is then defined as

$$PED_i = 100\,\frac{F_{ii}D_i^2}{\sum_j F_{jj}D_j^2}$$

This is therefore a **normalized diagonal internal-coordinate PED**.

The percentages describe the mechanical/energetic character of a **harmonic zero-order normal mode**. They are not IR-intensity percentages and are not unique observables: they depend in part on the selected internal-coordinate representation.

## Assignment hierarchy

The program reports three interpretation levels:

1. **Topological grouped assignment** (default): conservative families inferred from connectivity and graph topology.
2. **Generic grouped assignment** (`--show-generic`): element/type families such as `C-C stretching`, `C-H bending`, `C-N stretching`.
3. **Primitive internal-coordinate PED** (`--show-raw`): individual coordinates with percentages and relative phase.

Default assignment thresholds are:

```text
--pure-threshold 70
--mixed-second   20
```

If no family clearly dominates, the script reports a mixed assignment rather than forcing a pure one.

## VPT2/GVPT2 integration

The PED itself always describes the **harmonic normal modes** from the central Hessian.

When a VPT2/GVPT2 calculation is complete and numerically valid:

- VPT2 fundamental frequencies are mapped to the corresponding harmonic zero-order modes;
- VPT2 fundamental frequencies are preferred in the relevant tables and IR spectra;
- ORCA overtone and combination-band frequencies/intensities are imported;
- Fermi-resonance information is preserved when available.

The program does **not** invent anharmonic eigenvectors or state-mixing percentages that ORCA does not provide.

## Avogadro export

The generated `*_avogadro_vibrations.cjson` contains geometry, inferred connectivity, harmonic frequencies, harmonic IR intensities, and all harmonic Cartesian normal-mode eigenvectors.

Open it with Avogadro 2, for example:

```bash
avogadro2 "$(realpath molecule_analysis/molecule_avogadro_vibrations.cjson)"
```

The CJSON contains the preceding translational/rotational entries so that the mode number shown by Avogadro matches the ORCA/PED numbering (for example, the first true vibration of a nonlinear molecule is normally mode 6).

## Scientific limitations

- Connectivity is inferred geometrically from covalent radii and a distance scale factor; bond order is **not** inferred from the Hessian.
- Labels such as `aromatic C=C` are therefore intentionally avoided unless explicitly supported by external chemical information.
- The PED is a normalized **diagonal** decomposition; off-diagonal internal-coordinate coupling terms are not assigned separate percentages.
- PED percentages depend on the chosen internal-coordinate basis and should be interpreted as a quantitative analysis tool, not as uniquely defined observables.
- Degenerate modes can rotate within the degenerate subspace; grouped assignments are often more robust than individual primitive-coordinate percentages.
- VPT2 frequencies are associated with harmonic zero-order modes; the Avogadro vectors and PED remain harmonic.
- Strongly resonant states, especially those involved in Fermi resonance, should not automatically be interpreted as pure fundamentals.

## Documentation

A detailed English manual is included in:

- [`docs/ORCA_PED_Analyzer_Manual.md`](docs/ORCA_PED_Analyzer_Manual.md)
- `docs/ORCA_PED_Analyzer_Manual.pdf`

The manual explains the workflow from the Hessian to the Wilson `B` matrix, internal force constants, PED percentages, grouped chemical assignments, VPT2 mapping, IR spectra, and Avogadro visualization.

## Version

Current public version:

```text
2026.08.11-vpt2.8
```

Check the installed script with:

```bash
python3 orca_ped_analyzer.py --version
```

## License

MIT License. See [`LICENSE`](LICENSE).

## Disclaimer

This is an independent analysis utility and is not an official ORCA/FACCTs or Avogadro project. ORCA and Avogadro remain subject to their respective licenses and terms.
