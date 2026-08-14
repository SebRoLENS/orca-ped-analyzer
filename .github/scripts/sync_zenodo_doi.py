#!/usr/bin/env python3
"""Find the Zenodo DOI for a released version and update project metadata."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "orca_ped_analyzer.py"
README = ROOT / "README.md"
CITATION = ROOT / "CITATION.cff"

VERSION_RE = re.compile(r'^__version__\s*=\s*"(\d+\.\d+\.\d+)"', re.M)
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


def current_version() -> str:
    m = VERSION_RE.search(SCRIPT.read_text())
    if not m:
        raise SystemExit("Could not find __version__")
    return m.group(1)


def version_matches(value: object, wanted: str) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return text == wanted or text == f"v{wanted}"


def extract_doi(record: dict) -> str | None:
    pids = record.get("pids") or {}
    doi = pids.get("doi") if isinstance(pids, dict) else None
    if isinstance(doi, dict) and doi.get("identifier"):
        return str(doi["identifier"])
    if isinstance(doi, str):
        return doi

    if record.get("doi"):
        return str(record["doi"])

    metadata = record.get("metadata") or {}
    if metadata.get("doi"):
        return str(metadata["doi"])
    return None


def zenodo_records(query: str) -> list[dict]:
    params = urllib.parse.urlencode({"q": query, "size": 25})
    url = f"https://zenodo.org/api/records?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "orca-ped-analyzer-release-bot/1.2",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace").strip()
        except Exception:
            pass
        message = f"Zenodo API request failed with HTTP {exc.code}"
        if detail:
            message += f": {detail}"
        raise RuntimeError(message) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Zenodo API request failed: {exc}") from exc

    return ((payload.get("hits") or {}).get("hits") or [])


def find_doi(version: str) -> str | None:
    queries = [
        '"ORCA PED Analyzer"',
        f'"ORCA PED Analyzer" AND "{version}"',
        version,
    ]

    candidates: list[dict] = []
    seen_ids: set[str] = set()
    last_error: RuntimeError | None = None

    for query in queries:
        try:
            hits = zenodo_records(query)
        except RuntimeError as exc:
            last_error = exc
            continue

        for rec in hits:
            rec_id = str(rec.get("id") or "")
            if rec_id and rec_id in seen_ids:
                continue
            if rec_id:
                seen_ids.add(rec_id)

            metadata = rec.get("metadata") or {}
            title = str(metadata.get("title", "")).strip()
            if title != "ORCA PED Analyzer":
                continue
            if not version_matches(metadata.get("version"), version):
                continue
            if extract_doi(rec):
                candidates.append(rec)

    if not candidates:
        if last_error is not None:
            raise last_error
        return None

    candidates.sort(
        key=lambda r: str(r.get("updated") or r.get("created") or ""),
        reverse=True,
    )
    return extract_doi(candidates[0])


def replace_section(text: str, heading: str, next_heading: str, body: str) -> str:
    pattern = re.compile(
        rf"(?ms)^{re.escape(heading)}\n.*?(?=^{re.escape(next_heading)}\n)"
    )
    if not pattern.search(text):
        raise SystemExit(f"Could not find README section {heading!r}")
    return pattern.sub(body.rstrip() + "\n\n", text, count=1)


def set_readme_badges(text: str, doi: str) -> str:
    doi_url = f"https://doi.org/{doi}"
    doi_badge = f"[![DOI](https://zenodo.org/badge/DOI/{doi}.svg)]({doi_url})"

    if VERSION_BADGE_RE.search(text):
        text = VERSION_BADGE_RE.sub(VERSION_BADGE, text, count=1)
    else:
        title = "# ORCA PED Analyzer\n"
        if title not in text:
            raise SystemExit("Could not find ORCA PED Analyzer README title")
        text = text.replace(title, title + "\n" + VERSION_BADGE + "\n", 1)

    if DOI_BADGE_RE.search(text):
        text = DOI_BADGE_RE.sub(doi_badge, text, count=1)
    else:
        text = text.replace(VERSION_BADGE, VERSION_BADGE + "\n" + doi_badge, 1)
    return text


def apply_metadata(version: str, doi: str) -> None:
    doi_url = f"https://doi.org/{doi}"

    text = README.read_text()
    text = set_readme_badges(text, doi)

    cite = f"""## How to cite

If ORCA PED Analyzer contributes to published research, please acknowledge or cite the software. GitHub also provides a **Cite this repository** entry from [`CITATION.cff`](CITATION.cff).

> Romi, S. (2026). *ORCA PED Analyzer* (Version {version}) [Computer software]. Zenodo. {doi_url}

DOI: [**{doi}**]({doi_url})

Previous releases remain archived separately on Zenodo.
"""
    text = replace_section(text, "## How to cite", "## Contributions", cite)
    README.write_text(text)

    cff = CITATION.read_text()
    cff = re.sub(r"^doi:\s*.*\n", "", cff, flags=re.M)
    lines = cff.splitlines()
    insert_at = next(
        (i + 1 for i, line in enumerate(lines) if line.startswith("repository-code:")),
        None,
    )
    if insert_at is None:
        raise SystemExit("Could not find repository-code in CITATION.cff")
    lines.insert(insert_at, f'doi: "{doi}"')
    cff = "\n".join(lines) + "\n"
    cff = re.sub(r'^url:\s*".*"$', f'url: "{doi_url}"', cff, flags=re.M)
    cff = re.sub(r'^version:\s*".*"$', f'version: "{version}"', cff, flags=re.M)
    CITATION.write_text(cff)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default=None)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    version = args.version or current_version()
    try:
        doi = find_doi(version)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(3)

    if not doi:
        print(f"Zenodo DOI for v{version} not found yet.", file=sys.stderr)
        raise SystemExit(2)

    if args.apply:
        apply_metadata(version, doi)
    print(doi)


if __name__ == "__main__":
    main()
