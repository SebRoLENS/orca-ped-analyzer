#!/usr/bin/env python3
"""Cross-platform desktop launcher for ORCA PED Analyzer.

The GUI collects files/options from the user and runs the existing
orca_ped_analyzer.main() analysis engine in a separate process.  Keeping the
analysis outside the GUI process makes the interface responsive and allows a
running analysis to be stopped safely from the launcher.

The scientific PED/VPT2 implementation remains in orca_ped_analyzer.py.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import queue
from pathlib import Path
import subprocess
import sys
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import orca_ped_analyzer as core

MANUAL_URL = "https://github.com/SebRoLENS/orca-ped-analyzer/blob/main/docs/ORCA_PED_Analyzer_Manual.md"
GITHUB_URL = "https://github.com/SebRoLENS/orca-ped-analyzer"
CONTACT_EMAIL = "romi@lens.unifi.it"


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


class _QueueStream:
    """File-like stream that forwards stdout/stderr text to the GUI process."""

    def __init__(self, message_queue, stream_name: str) -> None:
        self.message_queue = message_queue
        self.stream_name = stream_name

    def write(self, text: str) -> int:
        if text:
            self.message_queue.put(("log", self.stream_name, text))
        return len(text)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False


def _analysis_process(argv: list[str], message_queue) -> None:
    """Run the analysis in a child process and stream its output to the GUI."""
    old_argv = sys.argv[:]
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    exit_code = 0

    try:
        sys.argv = ["orca_ped_analyzer"] + argv
        sys.stdout = _QueueStream(message_queue, "stdout")
        sys.stderr = _QueueStream(message_queue, "stderr")

        try:
            core.main()
        except SystemExit as exc:
            if isinstance(exc.code, str):
                print(exc.code, file=sys.stderr)
                exit_code = 1
            elif exc.code is None:
                exit_code = 0
            else:
                try:
                    exit_code = int(exc.code)
                except (TypeError, ValueError):
                    print(f"Unexpected SystemExit code: {exc.code!r}", file=sys.stderr)
                    exit_code = 1
        except BaseException:
            traceback.print_exc(file=sys.stderr)
            exit_code = 1
    finally:
        sys.argv = old_argv
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    # Send the completion marker last.  Closing/joining the queue feeder here
    # helps ensure that the parent receives the final log messages first.
    try:
        message_queue.put(("done", exit_code, ""))
        message_queue.close()
        message_queue.join_thread()
    except Exception:
        pass


class AnalyzerGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"ORCA PED Analyzer {core.__version__}")
        self.root.minsize(760, 560)

        self.hess_var = tk.StringVar()
        self.vpt2_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.fwhm_var = tk.StringVar(value="10")
        self.auto_vpt2_var = tk.BooleanVar(value=True)
        self.generic_var = tk.BooleanVar(value=False)
        self.raw_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Select a central ORCA .hess file.")

        self.last_output_dir: Path | None = None

        self._mp_context = mp.get_context("spawn")
        self._process = None
        self._message_queue = None
        self._worker_exit_code: int | None = None
        self._stop_requested = False
        self._stderr_header_written = False

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        if len(sys.argv) > 1 and str(sys.argv[1]).lower().endswith(".hess"):
            self.hess_var.set(str(Path(sys.argv[1]).expanduser()))

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=14)
        outer.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(8, weight=1)

        ttk.Label(
            outer,
            text="ORCA PED Analyzer",
            font=("TkDefaultFont", 16, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))

        ttk.Button(
            outer,
            text="User manual",
            command=lambda: _open_external_url(self.root, MANUAL_URL),
        ).grid(row=0, column=1, sticky="e", padx=(8, 0), pady=(0, 4))
        ttk.Button(
            outer,
            text="Check GitHub for updates",
            command=lambda: _open_external_url(self.root, GITHUB_URL),
        ).grid(row=0, column=2, sticky="e", padx=(8, 0), pady=(0, 4))

        ttk.Label(
            outer,
            text=(
                "Normalized diagonal internal-coordinate PED with optional ORCA "
                "VPT2/GVPT2 integration. The GUI uses the same analysis engine as "
                "the command-line program.\n"
                f"Contact: {CONTACT_EMAIL}"
            ),
            wraplength=720,
            justify="left",
        ).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 14))

        ttk.Label(outer, text="Central Hessian (.hess):").grid(
            row=2, column=0, sticky="w", padx=(0, 8), pady=4
        )
        ttk.Entry(outer, textvariable=self.hess_var).grid(
            row=2, column=1, sticky="ew", pady=4
        )
        ttk.Button(outer, text="Browse…", command=self._choose_hess).grid(
            row=2, column=2, padx=(8, 0), pady=4
        )

        ttk.Label(outer, text="VPT2/GVPT2 output (.out):").grid(
            row=3, column=0, sticky="w", padx=(0, 8), pady=4
        )
        ttk.Entry(outer, textvariable=self.vpt2_var).grid(
            row=3, column=1, sticky="ew", pady=4
        )
        ttk.Button(outer, text="Browse…", command=self._choose_vpt2).grid(
            row=3, column=2, padx=(8, 0), pady=4
        )

        ttk.Label(outer, text="Output directory:").grid(
            row=4, column=0, sticky="w", padx=(0, 8), pady=4
        )
        ttk.Entry(outer, textvariable=self.output_var).grid(
            row=4, column=1, sticky="ew", pady=4
        )
        ttk.Button(outer, text="Browse…", command=self._choose_output).grid(
            row=4, column=2, padx=(8, 0), pady=4
        )

        options = ttk.LabelFrame(outer, text="Options", padding=10)
        options.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(10, 8))

        ttk.Checkbutton(
            options,
            text="Auto-detect matching .out",
            variable=self.auto_vpt2_var,
        ).grid(row=0, column=0, sticky="w", padx=(0, 14))
        ttk.Checkbutton(
            options,
            text="Show generic groups",
            variable=self.generic_var,
        ).grid(row=0, column=1, sticky="w", padx=(0, 14))
        ttk.Checkbutton(
            options,
            text="Show raw ICs",
            variable=self.raw_var,
        ).grid(row=0, column=2, sticky="w", padx=(0, 14))
        ttk.Label(options, text="IR FWHM (cm⁻¹):").grid(
            row=0, column=3, sticky="e", padx=(8, 5)
        )
        ttk.Entry(options, textvariable=self.fwhm_var, width=7).grid(
            row=0, column=4, sticky="w"
        )

        buttons = ttk.Frame(outer)
        buttons.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(4, 8))

        self.run_button = ttk.Button(
            buttons,
            text="Run analysis",
            command=self._start_analysis,
        )
        self.run_button.pack(side="left")

        self.stop_button = ttk.Button(
            buttons,
            text="Stop analysis",
            command=self._stop_analysis,
            state="disabled",
        )
        self.stop_button.pack(side="left", padx=(8, 0))

        ttk.Label(buttons, textvariable=self.status_var).pack(
            side="left", padx=(14, 0)
        )

        ttk.Label(outer, text="Analysis log:").grid(
            row=7, column=0, columnspan=3, sticky="w"
        )

        log_frame = ttk.Frame(outer)
        log_frame.grid(
            row=8, column=0, columnspan=3, sticky="nsew", pady=(4, 0)
        )
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log = tk.Text(log_frame, wrap="word", height=18)
        scroll = ttk.Scrollbar(
            log_frame,
            orient="vertical",
            command=self.log.yview,
        )
        self.log.configure(yscrollcommand=scroll.set)
        self.log.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

    def _initial_dir(self) -> str:
        h = self.hess_var.get().strip()
        if h:
            p = Path(h).expanduser()
            if p.parent.exists():
                return str(p.parent)
        return str(Path.home())

    def _choose_hess(self) -> None:
        path = filedialog.askopenfilename(
            title="Select the central ORCA Hessian",
            initialdir=self._initial_dir(),
            filetypes=[("ORCA Hessian", "*.hess"), ("All files", "*")],
        )
        if path:
            self.hess_var.set(path)

    def _choose_vpt2(self) -> None:
        path = filedialog.askopenfilename(
            title="Select an ORCA VPT2/GVPT2 output (optional)",
            initialdir=self._initial_dir(),
            filetypes=[("ORCA output", "*.out"), ("All files", "*")],
        )
        if path:
            self.vpt2_var.set(path)

    def _choose_output(self) -> None:
        path = filedialog.askdirectory(
            title="Select output directory",
            initialdir=self._initial_dir(),
        )
        if path:
            self.output_var.set(path)

    def _start_analysis(self) -> None:
        if self._process is not None and self._process.is_alive():
            return

        hess_text = self.hess_var.get().strip()
        if not hess_text:
            messagebox.showerror(
                "Missing Hessian",
                "Please select the central ORCA .hess file.",
            )
            return

        hess = Path(hess_text).expanduser()
        if not hess.is_file():
            messagebox.showerror(
                "File not found",
                f"Hessian file not found:\n{hess}",
            )
            return

        try:
            fwhm = float(self.fwhm_var.get().strip())
            if fwhm <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Invalid FWHM",
                "IR FWHM must be a positive number.",
            )
            return

        argv = [str(hess.resolve()), "--ir-fwhm", str(fwhm)]

        vpt2_text = self.vpt2_var.get().strip()
        if vpt2_text:
            vpt2 = Path(vpt2_text).expanduser()
            if not vpt2.is_file():
                messagebox.showerror(
                    "File not found",
                    f"VPT2/GVPT2 output not found:\n{vpt2}",
                )
                return
            argv += ["--vpt2-out", str(vpt2.resolve())]
        elif not self.auto_vpt2_var.get():
            argv.append("--no-auto-vpt2")

        output_text = self.output_var.get().strip()
        if output_text:
            outdir = Path(output_text).expanduser().resolve()
            argv += ["--output-dir", str(outdir)]
        else:
            outdir = hess.resolve().parent / f"{hess.stem}_analysis"

        if self.generic_var.get():
            argv.append("--show-generic")
        if self.raw_var.get():
            argv.append("--show-raw")

        self.last_output_dir = outdir
        self._stop_requested = False
        self._worker_exit_code = None
        self._stderr_header_written = False

        self.run_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_var.set("Running…")

        self.log.delete("1.0", "end")
        self.log.insert(
            "end",
            f"ORCA PED Analyzer {core.__version__}\n"
            f"Input: {hess.resolve()}\n\n",
        )
        self.log.see("end")

        self._message_queue = self._mp_context.Queue()
        self._process = self._mp_context.Process(
            target=_analysis_process,
            args=(argv, self._message_queue),
            daemon=True,
        )

        try:
            self._process.start()
        except Exception:
            self.run_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self.status_var.set("Could not start analysis.")
            self.log.insert("end", "\n--- error while starting analysis ---\n")
            self.log.insert("end", traceback.format_exc())
            self.log.see("end")
            self._cleanup_process()
            messagebox.showerror(
                "Could not start analysis",
                "The analysis process could not be started. See the log for details.",
            )
            return

        self.root.after(75, self._poll_process)

    def _append_log(self, stream_name: str, text: str) -> None:
        if stream_name == "stderr" and not self._stderr_header_written:
            if self.log.index("end-1c") != "1.0":
                self.log.insert("end", "\n")
            self.log.insert("end", "--- warnings / errors ---\n")
            self._stderr_header_written = True

        self.log.insert("end", text)
        self.log.see("end")

    def _drain_messages(self) -> None:
        if self._message_queue is None:
            return

        while True:
            try:
                message = self._message_queue.get_nowait()
            except queue.Empty:
                break
            except (EOFError, OSError):
                break

            if not message:
                continue

            kind = message[0]
            if kind == "log":
                _, stream_name, text = message
                self._append_log(stream_name, text)
            elif kind == "done":
                _, exit_code, _ = message
                self._worker_exit_code = int(exit_code)

    def _poll_process(self) -> None:
        process = self._process
        if process is None:
            return

        self._drain_messages()

        if process.is_alive():
            self.root.after(100, self._poll_process)
            return

        # The process has exited. Drain once more after the queue feeder has had
        # a moment to flush any final stdout/stderr messages.
        self.root.after(75, self._finalize_process)

    def _finalize_process(self) -> None:
        process = self._process
        if process is None:
            return

        self._drain_messages()
        try:
            process.join(timeout=0)
        except Exception:
            pass

        process_exit_code = process.exitcode
        reported_exit_code = self._worker_exit_code
        exit_code = (
            reported_exit_code
            if reported_exit_code is not None
            else (process_exit_code if process_exit_code is not None else 1)
        )

        self.run_button.configure(state="normal")
        self.stop_button.configure(state="disabled")

        if self._stop_requested:
            self.status_var.set("Analysis stopped by user.")
            self.log.insert(
                "end",
                "\n\n--- analysis stopped by user ---\n"
                "The analysis process was terminated. Partial output files may "
                "remain in the output directory.\n",
            )
        elif exit_code == 0:
            self.status_var.set(
                f"Analysis completed. Output: {self.last_output_dir}"
            )
        else:
            self.status_var.set("Analysis failed; see the log.")
            self.log.insert(
                "end",
                f"\n\n--- analysis exited with code {exit_code} ---\n",
            )
            messagebox.showerror(
                "Analysis failed",
                "ORCA PED Analyzer reported an error. "
                "See the analysis log for details.",
            )

        self.log.see("end")
        self._cleanup_process()

    def _stop_analysis(self) -> None:
        process = self._process
        if process is None or not process.is_alive():
            return

        self._stop_requested = True
        self.stop_button.configure(state="disabled")
        self.status_var.set("Stopping analysis…")
        self.log.insert("end", "\n\nStop requested by user…\n")
        self.log.see("end")

        try:
            process.terminate()
        except Exception:
            self.log.insert(
                "end",
                "\nCould not terminate the analysis process:\n"
                + traceback.format_exc(),
            )

        # terminate() is normally sufficient.  If a platform does not stop the
        # child promptly, fall back to kill() where available.
        self.root.after(1000, self._force_stop_if_needed)

    def _force_stop_if_needed(self) -> None:
        process = self._process
        if process is None or not process.is_alive():
            return

        try:
            if hasattr(process, "kill"):
                process.kill()
            else:
                process.terminate()
        except Exception:
            self.log.insert(
                "end",
                "\nCould not force-stop the analysis process:\n"
                + traceback.format_exc(),
            )
            self.log.see("end")

    def _cleanup_process(self) -> None:
        if self._message_queue is not None:
            try:
                self._message_queue.close()
            except Exception:
                pass

        self._message_queue = None
        self._process = None
        self._worker_exit_code = None
        self._stop_requested = False

    def _on_close(self) -> None:
        process = self._process
        if process is not None and process.is_alive():
            try:
                process.terminate()
                process.join(timeout=0.5)
                if process.is_alive() and hasattr(process, "kill"):
                    process.kill()
            except Exception:
                pass
        self.root.destroy()


def _print_terminal_resources() -> None:
    if getattr(sys, "stdout", None) is None:
        return
    print(f"ORCA PED Analyzer {core.__version__}")
    print(f"Contact: {CONTACT_EMAIL}")
    print(f"Manual: {MANUAL_URL}")
    print(f"Check GitHub for updates and new releases: {GITHUB_URL}")
    print()


def main() -> None:
    _print_terminal_resources()
    root = tk.Tk()
    AnalyzerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    mp.freeze_support()
    main()
