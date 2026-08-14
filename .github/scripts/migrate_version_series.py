#!/usr/bin/env python3
"""One-time migration of ORCA PED Analyzer release numbering.

GitHub releases and tags are renumbered while preserving historical release
assets and DOI links. Historical scientific snapshots are left intact; temporary
branches only normalize GitHub Actions files so the GITHUB_TOKEN can create the
new tag refs under GitHub's workflow-protection rules.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = os.environ.get("GITHUB_REPOSITORY", "SebRoLENS/orca-ped-analyzer")

# old version, new version, target used only when the new tag does not yet exist
MAPPING = [
    ("2.8.0", "1.0.0", None),
    ("2.9.0", "1.1.0", "migration/version-1.1.0"),
    ("2.9.1", "1.1.1", "migration/version-1.1.1"),
    ("2.9.2", "1.1.2", "migration/version-1.1.2"),
    ("2.9.3", "1.1.3", "migration/version-1.1.3"),
    ("2.9.4", "1.1.4", "migration/version-1.1.4"),
]
CURRENT_OLD = "2.9.4"
CURRENT_NEW = "1.1.4"

CURRENT_FILES = [
    ROOT / "orca_ped_analyzer.py",
    ROOT / "README.md",
    ROOT / "CITATION.cff",
    ROOT / "docs" / "ORCA_PED_Analyzer_Manual.md",
]


def run(*args: str, check: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(args), flush=True)
    result = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0 and result.stderr.strip():
        print(result.stderr.strip(), file=os.sys.stderr)
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, result.args, output=result.stdout, stderr=result.stderr
        )
    return result


def remote_tag_sha(version: str) -> str | None:
    result = run(
        "git", "ls-remote", "--tags", "origin", f"refs/tags/v{version}", check=False
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.split()[0]


def release_for(old: str, new: str) -> dict:
    for version in (new, old):
        result = run(
            "gh", "api", f"repos/{REPO}/releases/tags/v{version}", check=False
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    raise SystemExit(f"Could not find release v{old} or v{new}")


def migrate_releases() -> None:
    for old, new, target in MAPPING:
        release = release_for(old, new)
        release_id = str(release["id"])
        current_tag = str(release.get("tag_name") or "")
        current_name = str(release.get("name") or f"ORCA PED Analyzer v{old}")
        current_body = str(release.get("body") or "")

        new_name = current_name.replace(f"v{old}", f"v{new}").replace(old, new)
        new_body = current_body.replace(f"v{old}", f"v{new}").replace(old, new)

        payload: dict[str, object] = {
            "tag_name": f"v{new}",
            "name": new_name,
            "body": new_body,
        }

        if remote_tag_sha(new) is None:
            if not target:
                raise SystemExit(
                    f"New tag v{new} does not exist and no safe target was configured"
                )
            payload["target_commitish"] = target

        if current_tag == f"v{new}" and current_name == new_name and current_body == new_body:
            print(f"Release v{new} already migrated")
            continue

        run(
            "gh",
            "api",
            "--method",
            "PATCH",
            f"repos/{REPO}/releases/{release_id}",
            "--input",
            "-",
            input_text=json.dumps(payload),
        )
        if remote_tag_sha(new) is None:
            raise SystemExit(f"GitHub did not create expected tag v{new}")
        print(f"Release v{old} -> v{new}")


def delete_old_tags() -> None:
    # Delete only after every release has a verified new tag.
    for _old, new, _target in MAPPING:
        if remote_tag_sha(new) is None:
            raise SystemExit(f"Refusing cleanup: v{new} is missing")

    for old, _new, _target in MAPPING:
        if remote_tag_sha(old):
            run(
                "gh",
                "api",
                "--method",
                "DELETE",
                f"repos/{REPO}/git/refs/tags/v{old}",
            )
            print(f"Deleted old tag v{old}")


def update_current_files() -> None:
    for path in CURRENT_FILES:
        text = path.read_text(encoding="utf-8")
        if CURRENT_OLD in text:
            path.write_text(text.replace(CURRENT_OLD, CURRENT_NEW), encoding="utf-8")
        elif CURRENT_NEW not in text:
            raise SystemExit(
                f"Neither {CURRENT_OLD} nor {CURRENT_NEW} found in {path.relative_to(ROOT)}"
            )

    source = (ROOT / "orca_ped_analyzer.py").read_text(encoding="utf-8")
    if f'__version__ = "{CURRENT_NEW}"' not in source:
        raise SystemExit("Current source version was not migrated to 1.1.4")


def cleanup_temporary_branches() -> None:
    for _old, new, target in MAPPING:
        if not target:
            continue
        result = run(
            "gh",
            "api",
            "--method",
            "DELETE",
            f"repos/{REPO}/git/refs/heads/{target}",
            check=False,
        )
        if result.returncode == 0:
            print(f"Deleted temporary branch {target}")
        else:
            print(f"Temporary branch {target} could not be deleted automatically")


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
            "User-Agent": "orca-ped-analyzer-version-migration/1.1",
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

    for old, new, _target in MAPPING:
        dep = by_version.get(old)
        if dep is None:
            continue
        dep_id = dep["id"]
        edit_url = f"https://zenodo.org/api/deposit/depositions/{dep_id}/actions/edit"
        publish_url = f"https://zenodo.org/api/deposit/depositions/{dep_id}/actions/publish"
        deposit_url = f"https://zenodo.org/api/deposit/depositions/{dep_id}"

        try:
            editable = _zenodo_request("POST", edit_url, token)
        except RuntimeError as exc:
            if "400" not in str(exc):
                raise
            editable = _zenodo_request("GET", deposit_url, token)

        metadata = dict(editable.get("metadata") or dep.get("metadata") or {})
        metadata["version"] = new
        _zenodo_request("PUT", deposit_url, token, {"metadata": metadata})
        _zenodo_request("POST", publish_url, token)
        print(f"Zenodo metadata v{old} -> v{new}")


def main() -> None:
    migrate_releases()
    delete_old_tags()
    update_current_files()
    update_zenodo_metadata_if_possible()
    cleanup_temporary_branches()
    print("Version migration completed.")


if __name__ == "__main__":
    main()
