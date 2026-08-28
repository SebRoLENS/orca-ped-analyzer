# ORCA PED Analyzer

[![Version](https://img.shields.io/github/v/release/SebRoLENS/orca-ped-analyzer)](https://github.com/SebRoLENS/orca-ped-analyzer/releases/latest)
[![DOI](https://img.shields.io/badge/DOI-pending-lightgrey)](https://github.com/SebRoLENS/orca-ped-analyzer/releases/latest)

**ORCA PED Analyzer** is a molecule-agnostic tool for assigning ORCA harmonic normal modes through selectable potential-energy-distribution (**PED**) or total-energy-distribution (**TED**) analysis, with optional VPT2/GVPT2 integration, IR-spectrum generation, CSV export, and Avogadro CJSON export.

Assignments are derived from the **calculated atomic motion and an internal-coordinate energy decomposition**, rather than from empirical frequency windows.

## Graphical interface

![ORCA PED Analyzer graphical interface](docs/orca_ped_analyzer_gui.png)

The desktop interface exposes the most commonly used analysis options without requiring terminal commands. It uses the same scientific analysis engine as the command-line program.

From the GUI you can:

- select the central ORCA `.hess` file;
- optionally select a VPT2/GVPT2 `.out` file or let the program auto-detect the matching output;
- choose a custom output directory;
- choose **PED** (default) or **TED** energy-distribution analysis;
- set the IR broadening FWHM;
- enable generic grouped assignments and/or raw internal-coordinate contributions;
- follow the analysis through a live log;
- stop a running analysis;
- open the user manual or the GitHub update page directly from the application.

After a successful run, if broadened IR `.dat` files are available, the GUI automatically opens an **interactive IR spectrum viewer**. The available spectra can be shown or hidden independently, and the embedded Matplotlib toolbar provides the usual zoom, pan, navigation and save controls.

## Download and run

For most users, the easiest way to use ORCA PED Analyzer is through the pre-built desktop application.

**No Python installation, terminal, or separate NumPy installation is required when using the packaged applications.**

**[Download the latest release](https://github.com/SebRoLENS/orca-ped-analyzer/releases/latest)**

Looking for an older version? **[Browse all releases and previous versions](https://github.com/SebRoLENS/orca-ped-analyzer/releases)**.

Available builds:

- **Linux x86_64:** AppImage
- **Windows x86_64:** standalone `.exe`
- **macOS Apple Silicon:** `.dmg` containing the `.app`
- **macOS Intel x86_64:** `.dmg` containing the `.app`

Typical GUI workflow:

1. Select the central ORCA `.hess` file.
2. Optionally select a completed VPT2/GVPT2 `.out` file, or leave auto-detection enabled.
3. Choose the output directory if desired.
4. Choose PED or TED and adjust optional assignment/IR settings.
5. Run the analysis and follow progress in the log.
6. Inspect the generated IR spectra in the spectrum viewer when available.

> **Note:** the current desktop builds are unsigned. Windows SmartScreen or macOS Gatekeeper may therefore display a warning on first launch. On Linux, the AppImage may need to be marked as executable before running it.

## Main features

- Selectable **PED** or **TED** analysis of ORCA harmonic normal modes; PED remains the backward-compatible default.
- TED combines potential- and kinetic-energy contributions through the Wilson G matrix using a modern diagonal Rytter-type formulation.
- Automatic molecule-agnostic internal-coordinate representation.
- Conservative topology-aware vibrational assignments.
- Detection and reporting of mixed modes.
- Optional ORCA VPT2/GVPT2 integration.
- Analysis of fundamentals, overtones, and combination bands.
- Generation of broadened IR spectra.
- Interactive graphical visualization of generated IR spectra.
- Configurable IR FWHM from the GUI or command line.
- CSV export of assignments and the selected PED/TED contributions.
- Avogadro CJSON export for visualization of harmonic normal modes.
- Live GUI analysis log and the ability to stop a running analysis.

## Input and output

The main input is always the **central ORCA `.hess` file**.

If a completed VPT2/GVPT2 calculation is available, its `.out` file can also be supplied. Displaced VPT2 Hessians such as `molecule_D001.hess` are not intended as input.

For a file named `molecule.hess`, the default output directory is:

```text
molecule_analysis/
```

Depending on the selected method and available data, the analysis can produce PED or TED assignment tables, IR spectra, VPT2 band information, Fermi-resonance information, an Avogadro CJSON file, and a run manifest.

## Command-line use

The Python command-line version remains available for advanced options, scripting, and reproducible automated workflows.

For the source version only, the requirements are:

- Python >= 3.9
- NumPy
- Matplotlib

Install the dependencies with:

```bash
python3 -m pip install -r requirements.txt
```

Basic usage:

```bash
python3 orca_ped_analyzer.py molecule.hess
```

With an explicitly selected VPT2/GVPT2 output:

```bash
python3 orca_ped_analyzer.py molecule.hess \
    --vpt2-out molecule_restart.out
```

Select TED instead of the default PED analysis with:

```bash
python3 orca_ped_analyzer.py molecule.hess --energy-distribution ted
```

For all available command-line options:

```bash
python3 orca_ped_analyzer.py --help
```

## Method and scientific interpretation

ORCA PED Analyzer can calculate either a **normalized diagonal internal-coordinate PED** or a **normalized diagonal total-energy distribution (TED)** for the harmonic normal modes. PED is the default and preserves the behaviour of previous versions. TED additionally includes the kinetic-energy contribution through the Wilson matrix \(G = B M^{-1} B^T\) and its inverse. The implemented TED uses the modern diagonal Rytter-type expression, with weights proportional to \([F_{ii}/\lambda_k + (G^{-1})_{ii}]D_{ik}^2\), followed by normalization to 100% for each mode.

Both PED and TED describe the mechanical/energetic character of **harmonic zero-order modes**. They are not IR-intensity decompositions and their percentages depend on the selected internal-coordinate representation. The diagonal TED is an approximation because off-diagonal coupling terms are omitted; this limitation is discussed explicitly in the manual.

When valid VPT2/GVPT2 results are supplied, anharmonic frequencies and intensities are associated with the corresponding harmonic zero-order modes. The PED/TED decomposition and normal-mode vectors themselves remain harmonic.

The TED option follows the total-energy-distribution concept introduced by E. Rytter, *J. Chem. Phys.* **60**, 3882–3883 (1974), DOI: `10.1063/1.1680833`, using the corrected/modern formulation discussed by Oenen, Dinu and Liedl, *J. Chem. Phys.* **160**, 014104 (2024), DOI: `10.1063/5.0180657`.

The detailed methodology — including internal-coordinate construction, the Wilson matrix, PED definition, assignment hierarchy, VPT2 mapping, Avogadro numbering, validation, and scientific limitations — is described in the **full manual** rather than duplicated here.

## Documentation

Detailed methodological and user documentation is available in:

- [`docs/ORCA_PED_Analyzer_Manual.md`](docs/ORCA_PED_Analyzer_Manual.md)
- [PDF manual](docs/ORCA_PED_Analyzer_Manual.pdf)

## Compatibility and future development

ORCA PED Analyzer has been tested with **ORCA 6.1.1**. It should also work with earlier and later ORCA versions provided that the relevant output formats remain compatible.

If you believe the software would benefit from supporting vibrational outputs generated by other computational chemistry packages, please open an issue and, if possible, provide a representative test case. Contributions toward broader interoperability are welcome.

## Version

Current public version: **2.10.0**

```bash
python3 orca_ped_analyzer.py --version
```

## How to cite

If ORCA PED Analyzer contributes to published research, please acknowledge or cite the software. GitHub also provides a **Cite this repository** entry from [`CITATION.cff`](CITATION.cff).

Version **2.10.0** will be archived automatically on Zenodo after the GitHub release is published. The DOI for this release will be inserted automatically.

> Romi, S. (2026). *ORCA PED Analyzer* (Version 2.10.0) [Computer software]. GitHub. https://github.com/SebRoLENS/orca-ped-analyzer/releases/tag/v2.10.0

Previous releases remain archived separately on Zenodo.

## Contributions

Testing on different molecular systems is especially valuable. **Bug reports, validation results, suggestions, documentation improvements, and code contributions are very welcome.**

If you observe unexpected behaviour, obtain an interesting validation case, or would like to improve the project, please open a GitHub issue or submit a pull request.

## License

MIT License. See [`LICENSE`](LICENSE).

## Disclaimer

This is an independent analysis utility and is not an official ORCA/FACCTs or Avogadro project. ORCA and Avogadro remain subject to their respective licenses and terms.

I am primarily a **user of computational chemistry software and an amateur programmer**, rather than a professional software developer. The development of ORCA PED Analyzer made extensive use of **AI-assisted programming**. To reduce the risk of introducing unnoticed errors, I developed the program incrementally, testing individual components and successive versions against real computational outputs and checking the consistency of the results at each stage.

For the systems tested so far, the results and vibrational assignments produced by the program have been fully consistent with the expected behaviour. Nevertheless, users are strongly encouraged to validate the software on **well-understood computational test cases** before relying on it for new scientific problems. This is good practice for any scientific software, and is particularly valuable here because independent testing can reveal implementation bugs, problematic assignments, edge cases, or methodological mistakes that I may have overlooked.

If you find any such issue, please report it. Identifying and correcting errors will only make the software more reliable and useful to the wider community. Contributions, validation cases, criticism, and suggested improvements are therefore sincerely appreciated. **Thank you for helping improve this open-source project.**
