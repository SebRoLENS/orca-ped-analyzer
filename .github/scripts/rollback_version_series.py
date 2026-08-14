#!/usr/bin/env python3
"""One-time rollback from the temporary 1.x renumbering to the original 2.x series."""

from __future__ import annotations
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = os.environ.get("GITHUB_REPOSITORY", "SebRoLENS/orca-ped-analyzer")

MAPPING = [
    ("1.0.0", "2.8.0", "rollback/version-2.8.0"),
    ("1.1.0", "2.9.0", "rollback/version-2.9.0"),
    ("1.1.1", "2.9.1", "rollback/version-2.9.1"),
    ("1.1.2", "2.9.2", "rollback/version-2.9.2"),
    ("1.1.3", "2.9.3", "rollback/version-2.9.3"),
    ("1.1.4", "2.9.4", "rollback/version-2.9.4"),
]
CURRENT_NEW = "1.1.4"
CURRENT_OLD = "2.9.4"
CURRENT_FILES = [
    ROOT / "orca_ped_analyzer.py",
    ROOT / "README.md",
    ROOT / "CITATION.cff",
    ROOT / "docs" / "ORCA_PED_Analyzer_Manual.md",
]


def run(*args: str, check: bool = True, input_text: str | None = None):
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
        raise subprocess.CalledProcessError(result.returncode, result.args, output=result.stdout, stderr=result.stderr)
    return result


def remote_tag_sha(version: str) -> str | None:
    r = run("git", "ls-remote", "--tags", "origin", f"refs/tags/v{version}", check=False)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return r.stdout.split()[0]


def find_release(current: str, original: str) -> dict:
    for version in (original, current):
        r = run("gh", "api", f"repos/{REPO}/releases/tags/v{version}", check=False)
        if r.returncode == 0:
            return json.loads(r.stdout)
    raise SystemExit(f"Could not find release v{current}/v{original}")


def restore_releases() -> None:
    for current, original, target in MAPPING:
        release = find_release(current, original)
        release_id = str(release["id"])
        current_tag = str(release.get("tag_name") or "")
        current_name = str(release.get("name") or f"ORCA PED Analyzer v{current}")
        current_body = str(release.get("body") or "")
        restored_name = current_name.replace(f"v{current}", f"v{original}").replace(current, original)
        restored_body = current_body.replace(f"v{current}", f"v{original}").replace(current, original)

        payload: dict[str, object] = {
            "tag_name": f"v{original}",
            "name": restored_name,
            "body": restored_body,
        }
        if remote_tag_sha(original) is None:
            payload["target_commitish"] = target

        if current_tag != f"v{original}" or current_name != restored_name or current_body != restored_body:
            run(
                "gh", "api", "--method", "PATCH",
                f"repos/{REPO}/releases/{release_id}",
                "--input", "-",
                input_text=json.dumps(payload),
            )
        if remote_tag_sha(original) is None:
            raise SystemExit(f"GitHub did not create expected tag v{original}")
        print(f"Release v{current} -> v{original}")


def delete_temporary_1x_tags() -> None:
    for _current, original, _target in MAPPING:
        if remote_tag_sha(original) is None:
            raise SystemExit(f"Refusing cleanup: v{original} is missing")
    for current, _original, _target in MAPPING:
        if remote_tag_sha(current):
            run("gh", "api", "--method", "DELETE", f"repos/{REPO}/git/refs/tags/v{current}")


def restore_current_metadata() -> None:
    for path in CURRENT_FILES:
        text = path.read_text(encoding="utf-8")
        if CURRENT_NEW in text:
            path.write_text(text.replace(CURRENT_NEW, CURRENT_OLD), encoding="utf-8")
        elif CURRENT_OLD not in text:
            raise SystemExit(f"Neither {CURRENT_NEW} nor {CURRENT_OLD} found in {path.relative_to(ROOT)}")
    source = (ROOT / "orca_ped_analyzer.py").read_text(encoding="utf-8")
    if f'__version__ = "{CURRENT_OLD}"' not in source:
        raise SystemExit("Source version was not restored to 2.9.4")


def cleanup_branches() -> None:
    for _current, _original, target in MAPPING:
        run("gh", "api", "--method", "DELETE", f"repos/{REPO}/git/refs/heads/{target}", check=False)


def main() -> None:
    restore_releases()
    delete_temporary_1x_tags()
    restore_current_metadata()
    cleanup_branches()
    print("Original 2.x versioning restored on GitHub metadata.")


if __name__ == "__main__":
    main()
