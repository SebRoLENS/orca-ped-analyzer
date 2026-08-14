#!/usr/bin/env python3
"""One-time migration of ORCA PED Analyzer release numbering.

Renumber GitHub releases/tags without changing their historical commits or assets,
update the current branch metadata to 1.1.4, and optionally update Zenodo record
metadata when a ZENODO_TOKEN secret is available.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = os.environ.get("GITHUB_REPOSITORY", "SebRoLENS/orca-ped-analyzer")

MAPPING = [
    ("2.8.0", "1.0.0"),
    ("2.9.0", "1.1.0"),
    ("2.9.1", "1.1.1"),
    ("2.9.2", "1.1.2"),
    ("2.9.3", "1.1.3"),
    ("2.9.4", "1.1.4"),
]
CURRENT_OLD = "2.9.4"
CURRENT_NEW = "1.1.4"

CURRENT_FILES = [
    ROOT / "orca_ped_analyzer.py",
    ROOT / "README.md",
    ROOT / "CITATION.cff",
    ROOT / "docs" / "ORCA_PED_Analyzer_Manual.md",
]


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(args), flush=True)
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def gh_json(endpoint: str) -> dict:
    result = run("gh", "api", endpoint)
    return json.loads(result.stdout)


def remote_tag_sha(tag: str) -> str | None:
    result = run("git", "ls-remote", "--tags", "origin", f"refs/tags/v{tag}", check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.split()[0]


def create_new_tags() -> None:
    run("git", "fetch", "origin", "--tags", "--force")
    for old, new in MAPPING:
        old_sha = remote_tag_sha(old)
        if not old_sha:
            raise SystemExit(f"Historical tag v{old} is missing")
        new_sha = remote_tag_sha(new)
        if new_sha:
            if new_sha != old_sha:
                raise SystemExit(
                    f"v{new} already exists at {new_sha}, expected historical commit {old_sha}"
                )
            print(f"v{new} already points to the expected commit")
            continue
        run("git", "tag", f"v{new}", old_sha)
        run("git", "push", "origin", f"refs/tags/v{new}")


def find_release(old: str, new: str) -> dict:
    for version in (old, new):
        result = run(
            "gh",
            "api",
            f"repos/{REPO}/releases/tags/v{version}",
            check=False,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    raise SystemExit(f"Could not find GitHub release for v{old}/v{new}")


def migrate_releases() -> None:
    for old, new in MAPPING:
        release = find_release(old, new)
        release_id = str(release["id"])
        current_tag = str(release.get("tag_name", ""))
        current_name = str(release.get("name") or f"ORCA PED Analyzer v{old}")
        current_body = str(release.get("body") or "")

        new_name = current_name.replace(f"v{old}", f"v{new}").replace(old, new)
        new_body = current_body.replace(f"v{old}", f"v{new}").replace(old, new)

        if current_tag != f"v{new}" or current_name != new_name or current_body != new_body:
            payload = json.dumps(
                {
                    "tag_name": f"v{new}",
                    "name": new_name,
                    "body": new_body,
                }
            )
            run(
                "gh",
                "api",
                "--method",
                "PATCH",
                f"repos/{REPO}/releases/{release_id}",
                "--input",
                "-",
                check=True,
            ) if False else subprocess.run(
                [
                    "gh",
                    "api",
                    "--method",
                    "PATCH",
                    f"repos/{REPO}/releases/{release_id}",
                    "--input",
                    "-",
                ],
                cwd=ROOT,
                input=payload,
                text=True,
                check=True,
            )
        print(f"Release v{old} -> v{new}")


def delete_old_tags() -> None:
    for old, _new in MAPPING:
        if remote_tag_sha(old):
            run("git", "push", "origin", f":refs/tags/v{old}")


def update_current_files() -> None:
    for path in CURRENT_FILES:
        text = path.read_text(encoding="utf-8")
        if CURRENT_OLD in text:
            text = text.replace(CURRENT_OLD, CURRENT_NEW)
            path.write_text(text, encoding="utf-8")
        elif CURRENT_NEW not in text:
            raise SystemExit(f"Neither {CURRENT_OLD} nor {CURRENT_NEW} found in {path}")

    source = (ROOT / "orca_ped_analyzer.py").read_text(encoding="utf-8")
    if f'__version__ = "{CURRENT_NEW}"' not in source:
        raise SystemExit("Current source version was not migrated to 1.1.4")


def _zenodo_request(method: str, url: str, token: str, data: dict | None = None):
    payload = None if data is None else json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "orca-ped-analyzer-version-migration/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            body = response.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"Zenodo HTTP {exc.code} for {url}: {detail}") from exc


def update_zenodo_metadata_if_possible() -> None:
    token = os.environ.get("ZENODO_TOKEN", "").strip()
    if not token:
        print("ZENODO_TOKEN is not configured; historical Zenodo metadata was not modified.")
        return

    deposits = _zenodo_request(
        "GET",
        "https://zenodo.org/api/deposit/depositions?all_versions=true&size=100",
        token,
    )
    if not isinstance(deposits, list):
        raise RuntimeError("Unexpected Zenodo depositions response")

    by_version: dict[str, dict] = {}
    for dep in deposits:
        md = dep.get("metadata") or {}
        if str(md.get("title", "")).strip() != "ORCA PED Analyzer":
            continue
        version = str(md.get("version", "")).lstrip("v")
        if version:
            by_version[version] = dep

    for old, new in MAPPING:
        dep = by_version.get(old)
        if dep is None:
            print(f"No owned Zenodo deposition found for v{old}; skipping")
            continue
        dep_id = dep["id"]
        edit_url = f"https://zenodo.org/api/deposit/depositions/{dep_id}/actions/edit"
        publish_url = f"https://zenodo.org/api/deposit/depositions/{dep_id}/actions/publish"
        deposit_url = f"https://zenodo.org/api/deposit/depositions/{dep_id}"

        try:
            editable = _zenodo_request("POST", edit_url, token)
        except RuntimeError as exc:
            # If it is already in edit mode, retrieve it and continue.
            if "400" not in str(exc):
                raise
            editable = _zenodo_request("GET", deposit_url, token)

        metadata = dict(editable.get("metadata") or dep.get("metadata") or {})
        metadata["version"] = new
        _zenodo_request("PUT", deposit_url, token, {"metadata": metadata})
        _zenodo_request("POST", publish_url, token)
        print(f"Zenodo metadata v{old} -> v{new}")


def main() -> None:
    create_new_tags()
    migrate_releases()
    delete_old_tags()
    update_current_files()
    update_zenodo_metadata_if_possible()

    print("Version migration completed.")


if __name__ == "__main__":
    main()
