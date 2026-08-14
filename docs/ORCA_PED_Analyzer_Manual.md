---
title: "ORCA PED Analyzer"
subtitle: "User and Method Manual"
author: "Sebastiano Romi"
date: "Version 2.9.3"
geometry: margin=22mm
fontsize: 10pt
header-includes:
  - |
    \usepackage{longtable}
    \usepackage{booktabs}
    \usepackage{microtype}
    \usepackage{amsmath}
---

**Author:** Sebastiano Romi  
**Affiliation:** European Laboratory for non-Linear Spectroscopy (LENS), Università degli Studi di Firenze (UNIFI)  
**Contact:** [romi@lens.unifi.it](mailto:romi@lens.unifi.it)

# Purpose

**ORCA PED Analyzer** performs a molecule-agnostic analysis of ORCA normal modes using a normalized diagonal potential-energy distribution (PED) in internal coordinates. It adds hierarchical/topological assignments, optional VPT2/GVPT2 post-processing, broadened IR spectra, CSV exports, and an Avogadro CJSON file containing all harmonic normal modes.

The program is designed around a conservative principle: **assignments are derived from the calculated atomic motion and the internal-coordinate energy decomposition, not from empirical frequency windows.**

## Main input

```text
molecule.hess      # always the CENTRAL ORCA Hessian
molecule.out       # optional VPT2/GVPT2 output; auto-detected for same basename
```

Never use displaced VPT2 Hessians such as:

```text
molecule_D001.hess
molecule_D002.hess
...
```

as input to the analyzer.

## Main output

By default, the script creates:

```text
molecule_analysis/
  molecule_summary.csv
  molecule_families.csv
  molecule_ped.csv
  molecule_IR_fundamentals.dat
  molecule_IR_anharmonic.dat       # if valid VPT2 is available
  molecule_IR_complete.dat         # if valid VPT2 is available
  molecule_avogadro_vibrations.cjson
  molecule_vpt2_bands.csv          # if valid VPT2 is available
  molecule_fermi.txt               # if a Fermi block is present
  molecule_manifest.txt
```

The PED and Avogadro vectors describe **harmonic normal modes**. When a valid VPT2 calculation is available, VPT2 fundamental frequencies are used in the relevant tables and spectra, while overtone and combination bands are read directly from the ORCA VPT2 output.

# 1. Main features of version 2.9.3

- **Desktop applications.** Pre-built Linux AppImage, Windows executable and macOS DMG packages provide a graphical interface without requiring a local Python installation.
- **Single output directory.** All generated files are written to `BASENAME_analysis/` by default.
- **Three IR spectra.** Fundamentals; anharmonic-only overtone/combination bands; complete spectrum.
- **Automatic VPT2 preference.** If VPT2 is complete and numerically valid, fundamental spectra and tables use the VPT2 fundamental frequencies; otherwise harmonic frequencies are retained.
- **Numerical VPT2 validation.** A normally terminated ORCA job containing `inf` or `nan` in the VPT2 fundamentals is classified as complete but invalid, and its anharmonic data are ignored.
- **Avogadro CJSON.** One native CJSON file stores geometry, harmonic intensities, harmonic frequencies and all harmonic normal-mode vectors.
- **Consistent Avogadro numbering.** Translational/rotational entries preceding the true vibrations are retained in the CJSON so that Avogadro mode numbers match the ORCA/PED mode numbers. For a nonlinear molecule, the first true vibration is normally displayed as mode 6.
- **Manifest.** Each run records the script version, inputs, VPT2 state, IR broadening parameters and generated files.
- **Molecule-agnostic PED.** Topological assignments, generic families and primitive internal coordinates with phase remain available.

# 2. Ways to run ORCA PED Analyzer

ORCA PED Analyzer can be used either as a **pre-built desktop application** or directly from the Python source code. For most users, the desktop application is the simplest option because it does not require a Python environment or terminal commands.

## 2.1 Pre-built desktop applications - recommended for most users

Ready-to-run applications are provided on the GitHub Releases page:

<https://github.com/SebRoLENS/orca-ped-analyzer/releases/latest>

The current release provides:

- **Linux x86_64:** `ORCA-PED-Analyzer-Linux-x86_64.AppImage` - portable AppImage.
- **Windows x86_64:** `ORCA-PED-Analyzer.exe` - standalone executable.
- **macOS Apple Silicon:** `ORCA-PED-Analyzer-macOS-arm64.dmg` - for Apple M-series Macs.
- **macOS Intel x86_64:** `ORCA-PED-Analyzer-macOS-x86_64.dmg` - for Intel-based Macs.

The packaged applications already contain Python and the required Python dependencies. Therefore, when using these builds, **Python, NumPy and a terminal are not required**.

### Linux

1. Download `ORCA-PED-Analyzer-Linux-x86_64.AppImage` from the latest GitHub release.
2. Mark the file as executable. This can usually be done from the file manager under **Properties -> Permissions**, or from a terminal with:

```bash
chmod +x ORCA-PED-Analyzer-Linux-x86_64.AppImage
```

3. Double-click the AppImage to launch ORCA PED Analyzer.

The AppImage is portable and does not require a traditional installation. It can be kept in any convenient directory.

### Windows

1. Download `ORCA-PED-Analyzer.exe` from the latest GitHub release.
2. Save it in a convenient directory.
3. Double-click the executable to launch the program.

No Python installation or separate installer is required.

### macOS - Apple Silicon or Intel

1. Select the DMG matching the Mac architecture:
   - `ORCA-PED-Analyzer-macOS-arm64.dmg` for Apple Silicon (M-series);
   - `ORCA-PED-Analyzer-macOS-x86_64.dmg` for Intel Macs.
2. Open the downloaded DMG.
3. Copy **ORCA PED Analyzer.app** to the `Applications` folder or another preferred location.
4. Launch the application normally from Finder.

No Python installation is required.

## 2.2 Using the graphical application

The graphical launcher is intentionally simple and runs the same scientific analysis engine as the command-line program.

1. Select the **central ORCA `.hess` file**.
2. If available, select the completed VPT2/GVPT2 `.out` file. This step is optional.
3. Select an output directory if a location different from the default is desired.
4. Start the analysis.

The generated PED tables, assignments, spectra, VPT2 information and Avogadro CJSON files are the same scientific outputs produced by the corresponding command-line analysis.

The central Hessian rule remains unchanged when using the GUI: displaced VPT2 Hessians such as `molecule_D001.hess` must not be used as the main input.

## 2.3 Security warnings and unsigned builds

The current desktop applications are **not digitally code-signed or notarized**. Consequently, operating-system security mechanisms may display a warning when the application is launched for the first time.

- **Windows:** Microsoft SmartScreen may report that the publisher is unknown or ask for confirmation before running the application.
- **macOS:** Gatekeeper may report that the developer cannot be verified and may require the user to explicitly allow or open the application.
- **Linux:** AppImage files are not normally affected by an equivalent publisher-signing warning, but the executable permission may need to be enabled before first use.

These warnings are expected for unsigned software downloaded from the Internet and indicate that the operating system cannot verify a code-signing identity for the publisher. They are separate from the scientific operation of the program.

For additional verification, each GitHub release includes `SHA256SUMS.txt`, containing SHA-256 checksums for the distributed application files. Users who require strict software provenance can compare the checksum of the downloaded file with the value published in the release.

The application source code and the GitHub Actions build workflow used to create the distributed packages are public in this repository.

## 2.4 Running from source / command line

The Python source version remains the preferred interface for advanced command-line options, scripting and reproducible automated workflows.

Requirements for the **source version only**:

- Python 3.9 or newer
- NumPy

Install the dependency with:

```bash
python3 -m pip install -r requirements.txt
```

On Debian, NumPy can alternatively be installed with:

```bash
sudo apt install python3-numpy
```

Check the script version and available options with:

```bash
python3 orca_ped_analyzer.py --version
python3 orca_ped_analyzer.py --help
```

Expected public version:

```text
orca_ped_analyzer.py 2.9.3
```

# 3. Which Hessian should be used?

## 3.1 Central Hessian

The PED always uses the central ORCA Hessian:

```text
molecule.hess
```

The script reads or derives from this file:

- molecular geometry,
- Cartesian Hessian,
- harmonic frequencies,
- harmonic normal-mode eigenvectors,
- harmonic IR information.

The central Hessian is also the source of the vectors exported to Avogadro.

## 3.2 Displaced VPT2 Hessians

Files such as:

```text
molecule_D001.hess
molecule_D002.hess
...
```

are intermediate ORCA files used to construct the anharmonic force field. They are **not** input files for the PED analyzer.

**Practical rule:** use one central `.hess` for the PED. Add VPT2 information by supplying the associated ORCA `.out`; do not switch to a displaced Hessian.

# 4. Command-line quick start

## 4.1 Minimum command

```bash
python3 orca_ped_analyzer.py molecule.hess
```

If `molecule.out` exists beside the Hessian, it is automatically inspected. A complete and numerically valid VPT2 analysis is incorporated.

## 4.2 VPT2 output with another name

Useful after a restarted calculation:

```bash
python3 orca_ped_analyzer.py molecule.hess \
    --vpt2-out molecule_restart.out
```

## 4.3 Disable automatic VPT2 detection

```bash
python3 orca_ped_analyzer.py molecule.hess --no-auto-vpt2
```

## 4.4 Recommended detailed run

```bash
python3 orca_ped_analyzer.py molecule.hess \
    --show-generic --show-raw \
    --family-top 6 --family-min-percent 2 \
    --top 10 --min-percent 1 \
    --ir-fwhm 5
```

# 5. Output directory and manifest

By default the output directory is:

```text
BASENAME_analysis/
```

For `propanamine_VPT2.hess`, for example:

```text
propanamine_VPT2_analysis/
  propanamine_VPT2_summary.csv
  propanamine_VPT2_families.csv
  propanamine_VPT2_ped.csv
  propanamine_VPT2_IR_fundamentals.dat
  propanamine_VPT2_IR_anharmonic.dat
  propanamine_VPT2_IR_complete.dat
  propanamine_VPT2_avogadro_vibrations.cjson
  propanamine_VPT2_vpt2_bands.csv
  propanamine_VPT2_fermi.txt
  propanamine_VPT2_manifest.txt
```

Conditional files appear only when the required information is available and valid.

Choose another output directory with:

```bash
python3 orca_ped_analyzer.py molecule.hess \
    --output-dir vibrational_analysis
```

A relative path is interpreted relative to the Hessian directory.

The manifest records the script version, central Hessian, selected VPT2 output, VPT2 status, IR FWHM and generated files. It is useful for reproducibility.

# 6. VPT2 detection and validation

The program distinguishes **program termination** from **numerical validity**. A VPT2 job can terminate normally but still contain non-finite anharmonic corrections.

| State | Typical message | Analyzer behavior |
|---|---|---|
| Not available | no matching `.out` / no VPT2 section | PED + harmonic fundamentals |
| Incomplete/running | `INCOMPLETE/RUNNING` | partial VPT2 data ignored |
| Complete but invalid | `COMPLETE BUT NUMERICALLY INVALID` | `inf`/`nan` ignored; harmonic data retained |
| Complete and valid | `COMPLETE + VALID` | VPT2 fundamentals, overtone/combination bands and Fermi information integrated |

## 6.1 Complete but numerically invalid

Example diagnostic:

```text
# VPT2: COMPLETE BUT NUMERICALLY INVALID in molecule.out
# fundamental rows=30/30; non-finite fundamentals=30; ...
```

The harmonic PED and CJSON remain usable. The fundamentals spectrum is produced using harmonic frequencies, while the anharmonic-only and complete spectra are not generated.

## 6.2 Mapping VPT2 fundamentals to Hessian modes

ORCA's VPT2 table numbers only vibrational modes, while the Hessian mode list normally also contains translational and rotational entries. The analyzer therefore maps VPT2 fundamentals to the central Hessian by comparing harmonic frequencies.

Default tolerance:

```text
--vpt2-match-tol 10
```

that is, 10 cm^-1. If mapping fails, first verify that the `.hess` and `.out` belong to the same calculation.

# 7. How the PED is calculated

The analyzer creates primitive internal coordinates, numerically constructs the Wilson `B` matrix and selects an independent set spanning the vibrational space: `3N-6` coordinates for a nonlinear molecule or `3N-5` for a linear molecule.

For harmonic normal-mode vector \(l\), the internal-coordinate displacement is

$$
D = B l
$$

The selected internal-coordinate force-constant representation is

$$
F = (B^+)^T H B^+
$$

where \(B^+\) is the pseudoinverse of `B` and `H` is the Cartesian Hessian.

The implemented PED is a normalized diagonal decomposition:

$$
PED_i = 100\,\frac{F_{ii}D_i^2}{\sum_j F_{jj}D_j^2}.
$$

**Important:** the PED describes the mechanical/energetic character of a harmonic normal mode. It is not an IR-intensity percentage and it depends on the chosen internal-coordinate representation.

# 8. Three assignment levels

## 8.1 Topological assignment - default

Primitive internal coordinates are grouped into conservative families that can be inferred from connectivity and graph topology, for example:

- `cyclic C-C stretching`,
- `inter-ring C-C torsion`,
- `ring-site C-H in-plane bending`,
- `exocyclic C-N stretching`.

The analyzer does not invent aromaticity or bond orders such as C=C or C=N from the Hessian alone.

## 8.2 Generic assignment - `--show-generic`

```bash
--show-generic
```

Displays chemistry-independent element/type families such as:

- `C-C stretching`,
- `C-H bending`,
- `C-N stretching`.

## 8.3 Primitive internal coordinates - `--show-raw`

```bash
--show-raw
```

Displays individual coordinates with percentage and relative phase, for example:

```text
nu(C5-C6) 20.84%[+]
```

# 9. Pure, mixed and phase-qualified modes

The assignment does not simply choose the largest individual primitive coordinate. Primitive contributions are first grouped by family; then the program evaluates whether one family dominates or whether the mode should be described as mixed.

Main defaults:

| Parameter | Default | Meaning |
|---|---:|---|
| `--pure-threshold` | 70% | threshold for a non-mixed assignment |
| `--mixed-second` | 20% | sufficiently large second family triggers a mixed assignment |
| `--family-top` | 4 | maximum number of grouped families printed |
| `--family-min-percent` | 2% | grouped families below this threshold are not printed |

For equivalent or closely related stretches, the relative sign of the internal-coordinate displacement can qualify a motion as `in-phase`, `opposite-phase`, or `mixed-phase` when the criterion is sufficiently robust.

# 10. Avogadro CJSON

Unless disabled with `--no-avogadro-cjson`, each run writes:

```text
BASENAME_avogadro_vibrations.cjson
```

It contains:

- geometry,
- inferred connectivity,
- harmonic frequencies,
- harmonic IR intensities,
- all harmonic Cartesian normal-mode vectors.

Open it with Avogadro 2:

```bash
avogadro2 "/full/path/BASENAME_analysis/BASENAME_avogadro_vibrations.cjson"
```

## 10.1 Why are the CJSON frequencies harmonic?

VPT2 corrects state energies and transition frequencies but does not provide the analyzer with a replacement Cartesian normal-mode eigenvector set. The animated vectors therefore remain the harmonic normal modes.

## 10.2 Why does Avogadro start the first real vibration at mode 6?

Avogadro numbers vibration entries sequentially. Version 2.9.3 keeps the preceding translational/rotational entries in the CJSON so that the number displayed by Avogadro matches the ORCA/PED Hessian mode number. For a typical nonlinear molecule:

```text
Avogadro mode 1-5  -> translational/rotational near-zero entries
Avogadro mode 6    -> first true vibration, ORCA/PED mode 6
Avogadro mode 7    -> ORCA/PED mode 7
...
```

This avoids the previous numbering offset.

# 11. Automatically generated IR spectra

The analyzer writes up to three `.dat` files. They are positive-going Gaussian-broadened curves represented as **relative absorbance**, with increasing wavenumber in the output grid.

| File | When | Contents |
|---|---|---|
| `*_IR_fundamentals.dat` | whenever central Hessian IR data are available | fundamentals only; VPT2 frequencies if valid, otherwise harmonic |
| `*_IR_anharmonic.dat` | valid completed VPT2 only | VPT2 overtone + combination bands only |
| `*_IR_complete.dat` | valid completed VPT2 only | VPT2 fundamentals + overtone/combination bands |

## 11.1 Frequency-source rule

```text
complete + valid VPT2 -> VPT2 fundamental frequencies
missing/incomplete/invalid VPT2 -> harmonic Hessian frequencies
```

Fundamental intensities are taken from the IR information in the central harmonic Hessian. Overtone/combination frequencies and intensities come from the ORCA VPT2 output.

## 11.2 Relative absorbance

Each spectrum contains two columns:

```text
wavenumber_cm-1    absorbance_relative
```

The absorbance is relative, not absolute Beer-Lambert absorbance. Concentration and optical path length are not known. Spectra generated in the same run share the same normalization convention, allowing relative visual comparison.

## 11.3 Bandwidth

```bash
python3 orca_ped_analyzer.py molecule.hess --ir-fwhm 5
```

`--ir-fwhm` is the Gaussian full width at half maximum in cm^-1. Default: 10 cm^-1.

## 11.4 Grid range and spacing

```text
--ir-xmin 400 --ir-xmax 4000 --ir-step 0.5
```

If limits are omitted, the range is selected automatically from the available bands and FWHM.

# 12. Example FTIR workflow

For a 400-4000 cm^-1 range, 5 cm^-1 FWHM and 0.5 cm^-1 grid spacing:

```bash
python3 orca_ped_analyzer.py molecule.hess \
    --ir-fwhm 5 \
    --ir-xmin 400 --ir-xmax 4000 --ir-step 0.5
```

With a complete and valid VPT2 output, all three spectra are produced. Otherwise only the fundamentals spectrum is written, using harmonic frequencies.

# 13. Overtones, combination bands and Fermi resonance

For valid VPT2 data, the analyzer reads ORCA overtone and combination-band frequencies and intensities. The textual assignment is derived from the **zero-order harmonic constituents**.

Conceptually:

```text
State       Freq/cm-1    Int/km mol-1    Assignment
2nu0        ...          ...             overtone of ...
nu0+nu1     ...          ...             ... + ...
```

If ORCA prints a Fermi-resonance analysis block, the script records its presence. With:

```bash
--show-fermi
```

it is also printed to the terminal and stored in `*_fermi.txt` when file output is enabled.

**Interpretation:** PED and Avogadro animations describe harmonic zero-order modes. A strongly resonant observed state may be a mixture of zero-order states and should not be treated as a pure fundamental solely from its PED label.

# 14. CSV tables

CSV output is enabled by default.

| File | When | Content |
|---|---|---|
| `*_summary.csv` | always | one row per mode: harmonic frequency, optional VPT2 fundamental, assignment, grouped PED |
| `*_families.csv` | always | topological/generic families and percentages |
| `*_ped.csv` | always | primitive IC, percentage, phase, `D_value`, `F_diagonal` |
| `*_vpt2_bands.csv` | valid VPT2 | overtone/combination data, intensity and assignment |
| `*_fermi.txt` | Fermi block present | original ORCA Fermi-analysis block |

Change the CSV prefix with:

```text
--csv-prefix vib
```

Disable CSV output with:

```text
--no-csv
```

# 15. Selected internal-coordinate set

The terminal output prints the independent internal-coordinate set actually used for the PED, for example:

```text
# Selected internal-coordinate set:
#   1 nu(C1-C2)
#   2 delta(C1-C2-C3)
#   3 tau(C1-C2-C3-C4)
...
```

Inspect this especially for complex molecules, metal-containing systems, unusually long bonds, clusters, or unconventional topology.

# 16. Command-line reference

| Option | Default | Function |
|---|---|---|
| `--vpt2-out FILE` | - | explicitly select VPT2 output |
| `--no-auto-vpt2` | off | do not search for same-basename `.out` |
| `--vpt2-match-tol` | 10 cm^-1 | VPT2 -> Hessian mapping tolerance |
| `--bond-scale` | 1.25 | distance factor for bond detection |
| `--linear-cut` | 175 deg | angles at/above threshold treated as linear bends |
| `--min-freq` | 20 cm^-1 | ignore modes with absolute frequency below threshold |
| `--top` | 5 | number of primitive coordinates shown with `--show-raw` |
| `--min-percent` | 1% | primitive-coordinate reporting threshold |
| `--family-top` | 4 | maximum grouped families displayed |
| `--family-min-percent` | 2% | grouped-family reporting threshold |
| `--pure-threshold` | 70% | non-mixed assignment threshold |
| `--mixed-second` | 20% | second-family threshold for mixed assignment |
| `--show-generic` | off | show generic molecule-agnostic families |
| `--show-raw` | off | show primitive internal coordinates and phase |
| `--show-fermi` | off | print ORCA Fermi block |
| `--output-dir DIR` | `BASENAME_analysis` | directory for generated files |
| `--csv-prefix PREFIX` | Hessian basename | CSV prefix |
| `--no-csv` | off | disable CSV files |
| `--no-avogadro-cjson` | off | disable Avogadro CJSON |
| `--cjson-name FILE` | `*_avogadro_vibrations.cjson` | custom CJSON name |
| `--no-ir-spectra` | off | disable IR spectra |
| `--ir-prefix PREFIX` | Hessian basename | IR file prefix |
| `--ir-fwhm` | 10 cm^-1 | Gaussian FWHM |
| `--ir-xmin / --ir-xmax` | automatic | spectrum range |
| `--ir-step` | 1 cm^-1 | IR grid spacing |

# 17. Quality control and troubleshooting

## 17.1 Cartesian-Hessian reconstruction error

The program reports, for example:

```text
# Cartesian-Hessian reconstruction relative error: 4.462e-06
```

A very small value indicates that the selected internal-coordinate representation reproduces the original Cartesian Hessian well. The script warns above approximately `1e-3`.

| Order of magnitude | Practical interpretation |
|---|---|
| `1e-6` to `1e-4` | very good |
| around `1e-3` | inspect carefully |
| greater than `1e-3` | possible connectivity/internal-coordinate problem |

## 17.2 Degenerate and collective modes

Within an exactly or nearly degenerate subspace, individual eigenvectors can rotate without changing the physical subspace. Primitive-coordinate percentages can therefore be basis-dependent. Grouped assignments and the degenerate set as a whole are usually more robust.

## 17.3 VPT2 containing `inf`/`nan`

This is not treated as a parsing error. It means the anharmonic result is numerically unusable. The analyzer classifies it as `COMPLETE BUT NUMERICALLY INVALID` and discards VPT2 frequencies/bands.

## 17.4 A `_Dxxx.hess` was supplied accidentally

The analyzer reports that the file looks like a displaced VPT2 Hessian and asks for the central Hessian instead.

## 17.5 Multiple fragments or unusual connectivity

Bond recognition uses distances and covalent radii. For clusters, noncovalent contacts, metal systems or multiple fragments, inspect `--bond-scale` and the selected internal-coordinate set carefully.

# 18. Recommended workflow

1. Optimize the geometry to a well-converged minimum.
2. Compute and inspect the central Hessian; check for imaginary frequencies.
3. Run `orca_ped_analyzer.py` on the central Hessian.
4. Inspect the reconstruction error and selected internal-coordinate set.
5. For complex systems, use `--show-generic --show-raw`.
6. If VPT2 is still running, use the harmonic outputs safely; partial anharmonic data are ignored.
7. When VPT2 finishes, rerun the analyzer. If the result is valid, VPT2 fundamental frequencies automatically take priority in the relevant tables and spectra.
8. Open the CJSON in Avogadro to inspect all harmonic normal modes using the same mode numbering as the PED output.
9. Use the three IR spectra to separate fundamentals, anharmonic-only additional bands and the complete simulated spectrum.
10. Archive the entire `*_analysis` directory with the calculation data.

# 19. Reporting results in a scientific publication

For a main-text assignment table, a useful minimal structure is:

| Experimental / cm^-1 | VPT2 / cm^-1 | Assignment |
|---:|---:|---|
| ... | ... | `cyclic C-C stretching` |
| ... | ... | `mixed C-N stretching / cyclic C-C stretching` |

For Supporting Information, retain more detail:

| Mode | Harmonic / cm^-1 | VPT2 / cm^-1 | Anharmonic shift | Calculated IR intensity | Assignment | Grouped PED |
|---:|---:|---:|---:|---:|---|---|
| ... | ... | ... | ... | ... | ... | ... |

Recommended reporting principles:

- use VPT2 fundamentals when the VPT2 result is valid;
- keep harmonic frequencies in the Supporting Information because the PED belongs to the harmonic zero-order modes;
- report multiple grouped PED contributions when no family dominates clearly;
- avoid reporting every primitive coordinate in the main paper;
- provide the complete primitive PED as machine-readable Supporting Data when useful;
- keep overtone/combination assignments separate from fundamentals;
- explicitly discuss Fermi mixing when it materially affects a spectral assignment.

# 20. Quick reference

Check version:

```bash
python3 orca_ped_analyzer.py --version
python3 orca_ped_analyzer.py --help
```

Standard analysis with automatic VPT2 detection:

```bash
python3 orca_ped_analyzer.py molecule.hess
```

Detailed analysis with 5 cm^-1 IR FWHM:

```bash
python3 orca_ped_analyzer.py molecule.hess \
  --show-generic --show-raw \
  --family-top 6 --family-min-percent 2 \
  --top 10 --min-percent 1 \
  --ir-fwhm 5
```

IR range 400-4000 cm^-1:

```bash
python3 orca_ped_analyzer.py molecule.hess \
  --ir-fwhm 5 --ir-xmin 400 --ir-xmax 4000 --ir-step 0.5
```

Custom output directory:

```bash
python3 orca_ped_analyzer.py molecule.hess \
  --output-dir vibrational_analysis
```

Open vibrations in Avogadro:

```bash
avogadro2 "$(realpath molecule_analysis/molecule_avogadro_vibrations.cjson)"
```

Remember: **one central Hessian only**. VPT2 is added through the ORCA output file; animated vectors remain harmonic. When VPT2 is valid, VPT2 fundamentals take priority in the corresponding spectra and tables.

# 21. Development and validation disclaimer

I am primarily a **user of computational chemistry software and an amateur programmer**, rather than a professional software developer. The development of ORCA PED Analyzer made extensive use of **AI-assisted programming**. To reduce the risk of introducing unnoticed errors, I developed the program incrementally, testing individual components and successive versions against real computational outputs and checking the consistency of the results at each stage.

For the systems tested so far, the results and vibrational assignments produced by the program have been fully consistent with the expected behaviour. Nevertheless, users are strongly encouraged to validate the software on **well-understood computational test cases** before relying on it for new scientific problems. This is good practice for any scientific software, and is particularly valuable here because independent testing can reveal implementation bugs, problematic assignments, edge cases, or methodological mistakes that I may have overlooked.

If you find any such issue, please report it. Identifying and correcting errors will only make the software more reliable and useful to the wider community. Contributions, validation cases, criticism, and suggested improvements are therefore sincerely appreciated. **Thank you for helping improve this open-source project.**


\newpage

# Appendix A - How the script assigns normal modes: from the Hessian to a chemical label

## A1. Key idea

The analyzer does not assign a vibration merely by comparing its frequency with an empirical table such as “1600 cm^-1 = C=C”. Instead, it starts from the **actual atomic motion calculated by ORCA**, transforms that motion into chemically readable internal coordinates, and estimates how much each internal coordinate contributes energetically to the mode.

This section explains the procedure from first principles.

## A2. What is a normal mode?

A molecule with \(N\) atoms has \(3N\) Cartesian coordinates. For a nonlinear molecule, three degrees of freedom correspond to translation and three to overall rotation. The remaining number of independent vibrations is therefore

$$
3N-6.
$$

For a linear molecule it is \(3N-5\).

Each independent vibration is a **normal mode**. Water, for example, has three atoms and therefore three vibrational normal modes: H-O-H bending and two O-H stretching combinations.

## A3. Where frequencies and atomic motions come from: the Hessian

The Cartesian Hessian contains second derivatives of the energy with respect to Cartesian atomic coordinates:

$$
H_{ij}=\frac{\partial^2 E}{\partial x_i\partial x_j}.
$$

Intuitively, the Hessian describes how energetically expensive small atomic displacements are and how different displacements are coupled.

After mass weighting and diagonalization, ORCA obtains for each normal mode:

- a harmonic frequency;
- a Cartesian eigenvector specifying the direction and relative amplitude of every atomic displacement.

This Cartesian eigenvector is the motion animated by Avogadro.

However, a Cartesian vector does not automatically have a chemical name. ORCA may return “Mode 37, 1285 cm^-1”, but the vector itself does not immediately say whether the motion is predominantly C-N stretching, C-C stretching, C-H bending, torsion, or a mixture.

## A4. Reconstructing molecular connectivity

The `.hess` file contains atomic elements and geometry but does not provide a complete chemical bond-order model. The analyzer therefore reconstructs connectivity from interatomic distances and covalent radii.

Atoms \(i\) and \(j\) are considered connected when

$$
d_{ij} \leq s\,[r_{\mathrm{cov},i}+r_{\mathrm{cov},j}],
$$

where the default scale factor is

```text
--bond-scale 1.25
```

This tells the program that two atoms are connected. It does **not** justify assigning a bond order such as single, double or aromatic. For that reason the program deliberately prefers conservative labels such as `cyclic C-C stretching` rather than automatically claiming `aromatic C=C stretching`.

## A5. Constructing primitive internal coordinates

Once connectivity is known, the program generates chemically meaningful primitive internal coordinates:

- **stretching:** change in a bond length, e.g. `nu(C1-C2)`;
- **bending:** change in a three-atom angle, e.g. `delta(C1-C2-H3)`;
- **torsion:** change in a four-atom dihedral angle;
- **out-of-plane motion:** displacement relative to a local plane;
- **linear bends:** two orthogonal bending coordinates when an angle is close to 180 degrees and an ordinary angular coordinate would become numerically ill-conditioned.

These are candidate coordinates. Their number can be substantially larger than the number of vibrational degrees of freedom, so the candidate set is generally redundant.

## A6. Why exactly `3N-6` independent coordinates are needed

For a nonlinear 26-atom molecule:

$$
3\times 26-6=72.
$$

The analyzer may initially generate far more than 72 stretches, bends, torsions and out-of-plane coordinates. It must therefore select an independent set of 72 coordinates that spans the vibrational space without redundancy.

## A7. The Wilson B matrix: Cartesian motion to internal-coordinate motion

The Wilson matrix \(B\) connects two descriptions of the same infinitesimal displacement:

$$
\Delta q = B\,\Delta x,
$$

where \(\Delta x\) contains Cartesian atomic displacements and \(\Delta q\) contains changes in bond lengths, angles, torsions and other internal coordinates.

The analyzer evaluates \(B\) numerically by central finite differences. Each Cartesian coordinate is displaced by a very small step \(h\), the internal coordinate is evaluated at \(+h\) and \(-h\), and the derivative is approximated by

$$
\frac{\partial q}{\partial x}\approx\frac{q(x+h)-q(x-h)}{2h}.
$$

The numerical step in the code is of order \(10^{-5}\).

## A8. Selecting the independent internal-coordinate set

The candidate `B` matrix is used to select a linearly independent subset using a numerical orthogonalization/pivoting procedure. For a nonlinear molecule, exactly `3N-6` coordinates are retained.

There is a small ordering preference toward stretches and bends, but the decisive criterion is mathematical independence and coverage of the vibrational space.

## A9. Transforming the Hessian to internal coordinates

The original Hessian is Cartesian. Using the pseudoinverse \(B^+\), the analyzer constructs

$$
F=(B^+)^T H B^+.
$$

The matrix \(F\) is the selected internal-coordinate representation of the force constants. Its diagonal elements indicate the energetic stiffness associated with the selected internal coordinates, while off-diagonal elements describe coupling between them.

## A10. Quality control: reconstructing the Cartesian Hessian

The analyzer reconstructs

$$
H_{\mathrm{rec}}=B^T F B
$$

and compares it with the original ORCA Hessian.

The reported

```text
Cartesian-Hessian reconstruction relative error
```

quantifies the relative difference. A value such as `4.5e-06` indicates that the selected internal-coordinate set reproduces the Cartesian Hessian extremely well.

## A11. Projecting one normal mode onto internal coordinates

Let \(l\) be the Cartesian eigenvector of one harmonic normal mode. The analyzer calculates

$$
D=B l.
$$

Each component of \(D\) tells how strongly one selected internal coordinate changes when the molecule moves along that normal mode.

A mode may therefore show, for example, a large change in a C-N bond length, moderate changes in several C-C distances, a small C-H bend and almost no torsion.

## A12. From geometrical displacement to energetic PED

Geometrical amplitude alone is not enough. A large displacement of a soft coordinate can have a different energetic significance from a smaller displacement of a stiff coordinate.

The analyzer combines internal-coordinate displacement with the diagonal internal force constant:

$$
raw_i=F_{ii}D_i^2.
$$

The values are then normalized to 100%:

$$
PED_i=100\,\frac{F_{ii}D_i^2}{\sum_j F_{jj}D_j^2}.
$$

If the output reports

```text
nu(C12-N13) = 43.6%
```

this does **not** mean that the bond “moves by 43.6%”. It means that, within the normalized diagonal energy decomposition used by the analyzer, that internal coordinate accounts for 43.6% of the assigned mechanical/energetic character of the mode.

## A13. Why it is called a normalized diagonal PED

The full internal force-constant matrix also contains off-diagonal terms \(F_{ij}\), which describe coupling between different internal coordinates. The percentages used by this analyzer are constructed from the diagonal terms \(F_{ii}\) and then normalized.

The precise methodological description is therefore:

> **normalized diagonal internal-coordinate potential-energy distribution**

The PED is not a unique observable. It depends in part on the chosen internal-coordinate set. Two reasonable internal-coordinate representations can give somewhat different individual percentages while describing the same Cartesian normal mode. This dependence should be acknowledged in scientific reporting.

## A14. From primitive PED to chemical/topological families

A primitive PED can contain many individual entries such as `nu(C1-C2)`, `nu(C2-C3)`, `nu(C3-C4)`, etc. This is quantitatively useful but difficult to read.

The analyzer therefore creates a second interpretation level by grouping primitive coordinates into chemically/topologically meaningful families inferred conservatively from the connectivity graph.

Examples include:

- `cyclic C-C stretching`;
- `ring-site C-H stretching`;
- `ring-site C-H in-plane bending`;
- `ring-site C-H out-of-plane bending`;
- `cyclic-ring deformation`;
- `inter-ring C-C stretching`;
- `inter-ring C-C torsion`;
- `exocyclic C-N stretching`.

If four cyclic C-C stretches contribute 18%, 15%, 14% and 11%, the grouped contribution becomes

```text
cyclic C-C stretching = 58%
```

## A15. Rules for the final assignment

The final label is derived from the grouped PED. Main defaults are:

```text
--pure-threshold 70
--mixed-second 20
```

If one family clearly dominates, for example:

```text
cyclic C-C stretching 82%
```

with all other contributions small, the final assignment is simply `cyclic C-C stretching`.

If the mode contains two important families, for example:

```text
cyclic C-C stretching       56%
ring-site C-H bending       31%
```

then the analyzer reports a mixed label such as

```text
mixed cyclic C-C stretching / ring-site C-H in-plane bending
```

For particularly mixed modes, a third family can also be retained when the leading family is below about 50% and the third contribution remains significant (about 15% or more). The philosophy is intentionally conservative: it is preferable to report a mixed mode than to force a false pure assignment.

## A16. Relative phase: in-phase and opposite-phase motion

The sign of the components of \(D\) can be used to compare the relative phase of equivalent or closely related internal coordinates.

If two stretches change in the same direction, the analyzer may describe them as `in-phase`. If one bond length increases while the other decreases, the motion may be described as `opposite-phase`. More complicated patterns are reported conservatively as `mixed-phase`.

The program deliberately avoids automatically calling these motions “symmetric” and “antisymmetric”, because those are symmetry labels that require an explicit group-theoretical classification.

## A17. Minimal example: water

For water the main internal coordinates are two O-H stretches and one H-O-H bend. In the validation test, the analyzer gives approximately:

| Mode | Harmonic frequency | PED character |
|---:|---:|---|
| 6 | ~1616 cm^-1 | H-O-H bending ~97.5% |
| 7 | ~3782 cm^-1 | in-phase O-H stretching ~100% |
| 8 | ~3886 cm^-1 | opposite-phase O-H stretching ~100% |

The assignment is **not** made because 3800 cm^-1 is a typical O-H stretching region. It is made because projection of the calculated normal-mode vectors onto the internal coordinates shows that almost all of the relevant energy decomposition belongs to the two O-H stretches.

## A18. Where VPT2 enters

The PED is calculated from the **harmonic normal modes of the central Hessian**.

Suppose the analyzer has:

```text
Mode 37
Harmonic frequency = 1302 cm^-1
PED assignment      = mixed C-N stretching / C-C stretching
```

and ORCA VPT2 reports the corresponding fundamental at

```text
VPT2 fundamental = 1267 cm^-1
```

The analyzer associates the VPT2 fundamental frequency with the same **zero-order harmonic mode**. The frequency changes, but the PED remains the PED of the harmonic mode.

This distinction is essential because VPT2 does not provide the analyzer with a replacement set of Cartesian normal-mode vectors suitable for recomputing a new PED or new Avogadro animation vectors.

## A19. How VPT2 modes are matched

The VPT2 fundamentals table contains the harmonic reference frequency and the corrected fundamental frequency. The analyzer compares the VPT2 harmonic reference with the central-Hessian harmonic frequencies and establishes a one-to-one mapping within the configured tolerance:

```text
--vpt2-match-tol 10
```

This also acts as a safeguard against accidentally combining an unrelated `.hess` and `.out` file.

## A20. Overtones and combination bands

The analyzer does not invent an anharmonic PED for an overtone or combination state.

If ORCA identifies a state as an overtone of mode \(i\), the analyzer describes it using the assignment of that zero-order harmonic constituent. Likewise, a combination band \(\nu_i+\nu_j\) is labeled from the assignments of modes \(i\) and \(j\).

These labels therefore describe the **zero-order constituents**, not necessarily the exact eigenstate composition after strong resonance mixing.

## A21. Fermi resonance

In the presence of a strong Fermi resonance, the actual anharmonic eigenstate can be a mixture of a fundamental and an overtone/combination state. In such a case it can be misleading to call the observed band a pure fundamental solely because one zero-order constituent carries that PED label.

For this reason the analyzer preserves and optionally prints the Fermi-resonance information reported by ORCA, while continuing to state clearly that the PED belongs to the harmonic zero-order modes.

## A22. Complete algorithm in one flow

```text
ORCA central .hess
        |
        v
geometry + Cartesian Hessian + harmonic normal modes
        |
        v
geometrical connectivity reconstruction
        |
        v
candidate internal coordinates
(stretch, bend, torsion, out-of-plane, linear bend)
        |
        v
numerical Wilson B matrix
        |
        v
selection of 3N-6 (or 3N-5) independent coordinates
        |
        v
Cartesian Hessian H -> internal force matrix F
        |
        v
for each harmonic normal mode l:
D = B l
        |
        v
raw diagonal energetic contribution = Fii * Di^2
        |
        v
normalization to 100%
        |
        v
primitive PED
        |
        v
grouping into generic/topological chemical families
        |
        v
threshold rules for pure/mixed assignment
        |
        v
FINAL HARMONIC MODE ASSIGNMENT
        |
        +---- if valid VPT2 is available ---->
              map VPT2 fundamental to the same zero-order harmonic mode
```

The most important single sentence is:

> **The analyzer assigns normal modes from the internal-coordinate energetic decomposition of the calculated harmonic atomic motion, not from an empirical frequency-to-functional-group lookup table.**
