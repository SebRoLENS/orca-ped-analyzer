# Contributing to ORCA PED Analyzer

Contributions, validation cases, bug reports, and suggestions are very welcome.

ORCA PED Analyzer is intended to remain conservative, molecule-agnostic, and scientifically transparent. Contributions should preserve these principles and avoid assigning chemical information that cannot be supported by the ORCA Hessian, molecular geometry, or explicitly supplied data.

## Especially useful contributions

- Testing on chemically diverse molecules and reporting successful or problematic cases.
- Comparing assignments against trusted manual analyses or other established PED workflows.
- Reporting parsing failures for ORCA Hessian or VPT2/GVPT2 outputs.
- Reporting unusual molecular topologies for which the internal-coordinate construction is inadequate.
- Improving documentation and examples.
- Adding tests that reproduce a reported issue.
- Proposing code improvements that preserve backward compatibility where practical.

## Reporting a problem

Please open a GitHub issue and, when possible, include:

- ORCA version;
- command used to run ORCA PED Analyzer;
- relevant analyzer version (`python3 orca_ped_analyzer.py --version`);
- molecule/system description;
- the central `.hess` file or a minimal reproducible example, if redistribution is permitted;
- the relevant ORCA `.out` file when the issue concerns VPT2/GVPT2;
- the unexpected output and what you expected instead.

Please remove confidential, unpublished, or restricted information before uploading files publicly.

## Scientific validation

Validation against additional molecular systems is particularly appreciated. When reporting a validation case, please state what reference was used for comparison (manual mode inspection, literature assignment, another PED implementation, symmetry analysis, etc.).

PED percentages are representation-dependent and should not be treated as uniquely defined observables. A useful validation should therefore consider both the numerical decomposition and the chemically meaningful grouped assignment.

## Pull requests

Pull requests are welcome. Please keep changes focused, explain the scientific or technical motivation, and include a small test or reproducible example whenever feasible.

For changes affecting assignments, PED construction, VPT2 mapping, or file parsing, please describe how the change was validated and whether it alters existing output.

## Acknowledgement

If ORCA PED Analyzer contributes to published research, an acknowledgement or citation of the software is greatly appreciated. See [`CITATION.cff`](CITATION.cff) and the citation section in the README.
