# ORCA PED Analyzer v2.9.0

This release adds a graphical desktop launcher and native packaged builds while keeping the scientific PED analysis engine unchanged.

## New in v2.9.0

- Graphical launcher for selecting the central ORCA `.hess` file and optional VPT2/GVPT2 `.out` file.
- Linux x86_64 AppImage.
- Windows x86_64 standalone executable.
- macOS Apple Silicon DMG.
- macOS Intel x86_64 DMG.
- Automated cross-platform builds through GitHub Actions.
- SHA-256 checksums for all release binaries.

The command-line interface remains available and is the reference interface for advanced options and scripted workflows.

The packaged desktop builds are currently unsigned, so Windows SmartScreen or macOS Gatekeeper may display a warning on first launch.
