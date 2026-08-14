#!/usr/bin/env python3
"""Prepare metadata for an automatic ORCA PED Analyzer release."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "orca_ped_analyzer.py"
README = ROOT / "README.md"
CITATION = ROOT / "CITATION.cff"

VERSION_RE = re.compile(r'^__version__\s*=\s*"(\d+\.\d+\.\d+)"', re.M)
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def read_version(text: str) -> str:
    m = VERSION_RE.search(text)
    if not m:
        raise SystemExit("Could not find __version__ in orca_ped_analyzer.py")
    return m.group(1)


def git_previous_script() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", "HEAD^:orca_ped_analyzer.py"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None


def tuple_version(v: str) -> tuple[int, int, int]:
    m = SEMVER_RE.fullmatch(v)
    if not m:
        raise SystemExit(f"Unsupported version format: {v}")
    return tuple(map(int, m.groups()))


def choose_version() -> tuple[str, str]:
    current = read_version(SCRIPT.read_text())
    previous_text = git_previous_script()
    previous = read_version(previous_text) if previous_text else current

    # Respect an explicit manual version bump in the same user commit.
    if current != previous:
        if tuple_version(current) <= tuple_version(previous):
            raise SystemExit(
                f"Manual version {current} must be newer than previous version {previous}"
            )
        return previous, current

    major, minor, patch = tuple_version(current)
    return current, f"{major}.{minor}.{patch + 1}"


def replace_section(text: str, heading: str, next_heading: str, body: str) -> str:
    pattern = re.compile(
        rf"(?ms)^{re.escape(heading)}\n.*?(?=^{re.escape(next_heading)}\n)"
    )
    if not pattern.search(text):
        raise SystemExit(f"Could not find README section {heading!r}")
    return pattern.sub(body.rstrip() + "\n\n", text, count=1)


def update_readme(old_version: str, new_version: str) -> None:
    text = README.read_text()
    text = text.replace(old_version, new_version)

    # Never show the previous release DOI as if it belonged to the new release.
    text = re.sub(
        r"^\[!\[DOI\]\(https://zenodo\.org/badge/DOI/[^)]+\.svg\)\]\(https://doi\.org/[^)]+\)\s*$",
        "[![Latest release](https://img.shields.io/github/v/release/SebRoLENS/orca-ped-analyzer)]"
        "(https://github.com/SebRoLENS/orca-ped-analyzer/releases/latest)",
        text,
        flags=re.M,
    )

    cite = f"""## How to cite

If ORCA PED Analyzer contributes to published research, please acknowledge or cite the software. GitHub also provides a **Cite this repository** entry from [`CITATION.cff`](CITATION.cff).

Version **{new_version}** is archived automatically on Zenodo after the GitHub release is published. The DOI for this release is being assigned and will be inserted here automatically.

> Romi, S. (2026). *ORCA PED Analyzer* (Version {new_version}) [Computer software]. GitHub. https://github.com/SebRoLENS/orca-ped-analyzer/releases/tag/v{new_version}

Previous releases remain archived separately on Zenodo.
"""
    text = replace_section(text, "## How to cite", "## Contributions", cite)
    README.write_text(text)


def update_citation(new_version: str) -> None:
    text = CITATION.read_text()
    text = re.sub(r"^doi:\s*.*\n", "", text, flags=re.M)
    text = re.sub(
        r'^url:\s*".*"$',
        f'url: "https://github.com/SebRoLENS/orca-ped-analyzer/releases/tag/v{new_version}"',
        text,
        flags=re.M,
    )
    text = re.sub(
        r'^version:\s*".*"$', f'version: "{new_version}"', text, flags=re.M
    )
    text = re.sub(
        r"^date-released:\s*.*$",
        f"date-released: {dt.date.today().isoformat()}",
        text,
        flags=re.M,
    )
    CITATION.write_text(text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version-only", action="store_true")
    args = parser.parse_args()

    old_version, new_version = choose_version()
    if args.version_only:
        print(new_version)
        return

    script_text = SCRIPT.read_text()
    script_text = VERSION_RE.sub(f'__version__ = "{new_version}"', script_text, count=1)
    SCRIPT.write_text(script_text)
    update_readme(old_version, new_version)
    update_citation(new_version)
    print(new_version)


if __name__ == "__main__":
    main()
