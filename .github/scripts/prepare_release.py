#!/usr/bin/env python3
"""Prepare metadata for an automatic ORCA PED Analyzer release."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "orca_ped_analyzer.py"
README = ROOT / "README.md"
MANUAL = ROOT / "docs" / "ORCA_PED_Analyzer_Manual.md"
CITATION = ROOT / "CITATION.cff"
RELEASE_TRIGGER = ROOT / ".release-trigger"

VERSION_RE = re.compile(r'^__version__\s*=\s*"(\d+\.\d+\.\d+)"', re.M)
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
VERSION_BADGE_RE = re.compile(
    r"^\[!\[(?:Latest release|Version)\]\([^)]+\)\]\([^)]+\)[ \t]*$", re.M
)
DOI_BADGE_RE = re.compile(
    r"^\[!\[DOI\]\([^)]+\)\]\([^)]+\)[ \t]*$", re.M
)

VERSION_BADGE = (
    "[![Version](https://img.shields.io/github/v/release/SebRoLENS/orca-ped-analyzer)]"
    "(https://github.com/SebRoLENS/orca-ped-analyzer/releases/latest)"
)
DOI_PENDING_BADGE = (
    "[![DOI](https://img.shields.io/badge/DOI-pending-lightgrey)]"
    "(https://github.com/SebRoLENS/orca-ped-analyzer/releases/latest)"
)


def reject_stale_release_trigger() -> None:
    """Abort a delayed Actions run when a newer release trigger superseded it."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return

    event_sha = os.environ.get("GITHUB_SHA", "").strip()
    if not event_sha or not RELEASE_TRIGGER.exists():
        return

    try:
        event_trigger = subprocess.check_output(
            ["git", "show", f"{event_sha}:.release-trigger"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        # The triggering commit may have changed source code rather than the
        # release-trigger file. In that case there is nothing to compare.
        return

    current_trigger = RELEASE_TRIGGER.read_text()
    if event_trigger != current_trigger:
        raise SystemExit(
            "Stale automatic-release run: a newer .release-trigger is already "
            "present on main. Refusing to create an extra release."
        )


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


def update_badges_for_pending_doi(text: str) -> str:
    if VERSION_BADGE_RE.search(text):
        text = VERSION_BADGE_RE.sub(VERSION_BADGE, text, count=1)
    else:
        title = "# ORCA PED Analyzer\n"
        if title not in text:
            raise SystemExit("Could not find ORCA PED Analyzer README title")
        text = text.replace(title, title + "\n" + VERSION_BADGE + "\n", 1)

    if DOI_BADGE_RE.search(text):
        text = DOI_BADGE_RE.sub(DOI_PENDING_BADGE, text, count=1)
    else:
        text = text.replace(VERSION_BADGE, VERSION_BADGE + "\n" + DOI_PENDING_BADGE, 1)
    return text


def update_readme(old_version: str, new_version: str) -> None:
    text = README.read_text()
    text = text.replace(old_version, new_version)
    text = update_badges_for_pending_doi(text)

    cite = f"""## How to cite

If ORCA PED Analyzer contributes to published research, please acknowledge or cite the software. GitHub also provides a **Cite this repository** entry from [`CITATION.cff`](CITATION.cff).

Version **{new_version}** is archived automatically on Zenodo after the GitHub release is published. The DOI for this release is being assigned and will be inserted here automatically.

> Romi, S. (2026). *ORCA PED Analyzer* (Version {new_version}) [Computer software]. GitHub. https://github.com/SebRoLENS/orca-ped-analyzer/releases/tag/v{new_version}

Previous releases remain archived separately on Zenodo.
"""
    text = replace_section(text, "## How to cite", "## Contributions", cite)
    README.write_text(text)


def update_manual(old_version: str, new_version: str) -> None:
    text = MANUAL.read_text()
    if old_version not in text:
        raise SystemExit(
            f"Manual does not contain the current version {old_version}; refusing to tag an inconsistent release"
        )
    MANUAL.write_text(text.replace(old_version, new_version))


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

    reject_stale_release_trigger()
    old_version, new_version = choose_version()
    if args.version_only:
        print(new_version)
        return

    script_text = SCRIPT.read_text()
    script_text = VERSION_RE.sub(f'__version__ = "{new_version}"', script_text, count=1)
    SCRIPT.write_text(script_text)
    update_readme(old_version, new_version)
    update_manual(old_version, new_version)
    update_citation(new_version)
    print(new_version)


if __name__ == "__main__":
    main()
