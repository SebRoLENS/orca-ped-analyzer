#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Could not find expected block: {label}")
    return text.replace(old, new, 1)


def update_gui() -> None:
    path = Path("orca_ped_analyzer_gui.py")
    text = path.read_text()

    text = replace_once(
        text,
        """import multiprocessing as mp
import queue
from pathlib import Path
import sys
import traceback
import webbrowser
""",
        """import multiprocessing as mp
import os
import queue
from pathlib import Path
import subprocess
import sys
import traceback
""",
        "GUI imports",
    )

    text = replace_once(
        text,
        """MANUAL_URL = "https://github.com/SebRoLENS/orca-ped-analyzer/blob/main/docs/ORCA_PED_Analyzer_Manual.md"
GITHUB_URL = "https://github.com/SebRoLENS/orca-ped-analyzer"
""",
        """MANUAL_URL = "https://github.com/SebRoLENS/orca-ped-analyzer/blob/main/docs/ORCA_PED_Analyzer_Manual.md"
GITHUB_URL = "https://github.com/SebRoLENS/orca-ped-analyzer"
CONTACT_EMAIL = "romi@lens.unifi.it"
""",
        "GUI constants",
    )

    helper = '''

def _clean_external_environment() -> dict[str, str]:
    """Remove frozen-app variables that can break external browser launchers."""
    env = os.environ.copy()
    if sys.platform.startswith("linux"):
        original = env.pop("LD_LIBRARY_PATH_ORIG", None)
        if original is None:
            env.pop("LD_LIBRARY_PATH", None)
        else:
            env["LD_LIBRARY_PATH"] = original
        for key in ("PYTHONHOME", "PYTHONPATH", "QT_PLUGIN_PATH", "QML2_IMPORT_PATH"):
            env.pop(key, None)
    elif sys.platform == "darwin":
        env.pop("DYLD_LIBRARY_PATH", None)
        env.pop("DYLD_FALLBACK_LIBRARY_PATH", None)
    return env


def _open_external_url(parent: tk.Misc, url: str) -> None:
    """Open a URL with the operating system and show the explicit URL on failure."""
    try:
        if sys.platform == "win32":
            os.startfile(url)  # type: ignore[attr-defined]
            return

        env = _clean_external_environment()
        commands = [["open", url]] if sys.platform == "darwin" else [
            ["xdg-open", url],
            ["gio", "open", url],
        ]

        last_error: Exception | None = None
        for command in commands:
            try:
                result = subprocess.run(
                    command,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    check=False,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
                last_error = exc
                continue
            if result.returncode == 0:
                return
            last_error = RuntimeError(
                f"{command[0]} exited with code {result.returncode}"
            )
        raise last_error or RuntimeError("No URL opener is available")
    except Exception:
        messagebox.showwarning(
            "Could not open link",
            "The link could not be opened automatically.\n\n"
            "If this does not work, copy this link into your browser:\n\n"
            f"{url}",
            parent=parent,
        )
'''

    text = replace_once(
        text,
        "\n\nclass _QueueStream:",
        helper + "\n\nclass _QueueStream:",
        "GUI URL helper insertion point",
    )

    text = replace_once(
        text,
        "command=lambda: webbrowser.open(MANUAL_URL),",
        "command=lambda: _open_external_url(self.root, MANUAL_URL),",
        "manual button",
    )
    text = replace_once(
        text,
        "command=lambda: webbrowser.open(GITHUB_URL),",
        "command=lambda: _open_external_url(self.root, GITHUB_URL),",
        "GitHub button",
    )

    text = replace_once(
        text,
        """                "Normalized diagonal internal-coordinate PED with optional ORCA "
                "VPT2/GVPT2 integration. The GUI uses the same analysis engine as "
                "the command-line program."
""",
        """                "Normalized diagonal internal-coordinate PED with optional ORCA "
                "VPT2/GVPT2 integration. The GUI uses the same analysis engine as "
                "the command-line program.\\n"
                f"Contact: {CONTACT_EMAIL}"
""",
        "GUI description/contact",
    )

    text = replace_once(
        text,
        """    print(f"ORCA PED Analyzer {core.__version__}")
    print(f"Manual: {MANUAL_URL}")
""",
        """    print(f"ORCA PED Analyzer {core.__version__}")
    print(f"Contact: {CONTACT_EMAIL}")
    print(f"Manual: {MANUAL_URL}")
""",
        "GUI terminal contact",
    )

    path.write_text(text)


def update_core() -> None:
    path = Path("orca_ped_analyzer.py")
    text = path.read_text()

    text = replace_once(
        text,
        'GITHUB_URL = "https://github.com/SebRoLENS/orca-ped-analyzer"\n',
        'GITHUB_URL = "https://github.com/SebRoLENS/orca-ped-analyzer"\n'
        'CONTACT_EMAIL = "romi@lens.unifi.it"\n',
        "core contact constant",
    )

    text = replace_once(
        text,
        """            f"Manual: {MANUAL_URL}\\n"
            f"Check GitHub for updates and new releases: {GITHUB_URL}"
""",
        """            f"Contact: {CONTACT_EMAIL}\\n"
            f"Manual: {MANUAL_URL}\\n"
            f"Check GitHub for updates and new releases: {GITHUB_URL}"
""",
        "CLI help epilog",
    )

    text = replace_once(
        text,
        """            f"%(prog)s {__version__}\\n"
            f"Manual: {MANUAL_URL}\\n"
""",
        """            f"%(prog)s {__version__}\\n"
            f"Contact: {CONTACT_EMAIL}\\n"
            f"Manual: {MANUAL_URL}\\n"
""",
        "CLI version output",
    )

    text = replace_once(
        text,
        '    print(f"# Manual: {MANUAL_URL}")\n',
        '    print(f"# Contact: {CONTACT_EMAIL}")\n'
        '    print(f"# Manual: {MANUAL_URL}")\n',
        "normal CLI output",
    )

    path.write_text(text)


if __name__ == "__main__":
    update_gui()
    update_core()
