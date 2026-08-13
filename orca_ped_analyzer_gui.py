#!/usr/bin/env python3
"""Cross-platform desktop launcher for ORCA PED Analyzer.

This GUI is intentionally thin: it collects file/options from the user and
calls the existing orca_ped_analyzer.main() analysis engine. The scientific
PED/VPT2 implementation remains in orca_ped_analyzer.py.
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path
import sys
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import orca_ped_analyzer as core


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
        self._build_ui()
        if len(sys.argv) > 1 and str(sys.argv[1]).lower().endswith(".hess"):
            self.hess_var.set(str(Path(sys.argv[1]).expanduser()))

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=14)
        outer.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(8, weight=1)

        ttk.Label(outer, text="ORCA PED Analyzer", font=("TkDefaultFont", 16, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
        ttk.Label(
            outer,
            text=("Normalized diagonal internal-coordinate PED with optional ORCA VPT2/GVPT2 integration. "
                  "The GUI uses the same analysis engine as the command-line program."),
            wraplength=720,
            justify="left",
        ).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 14))

        ttk.Label(outer, text="Central Hessian (.hess):").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(outer, textvariable=self.hess_var).grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Button(outer, text="Browse…", command=self._choose_hess).grid(row=2, column=2, padx=(8, 0), pady=4)

        ttk.Label(outer, text="VPT2/GVPT2 output (.out):").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(outer, textvariable=self.vpt2_var).grid(row=3, column=1, sticky="ew", pady=4)
        ttk.Button(outer, text="Browse…", command=self._choose_vpt2).grid(row=3, column=2, padx=(8, 0), pady=4)

        ttk.Label(outer, text="Output directory:").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(outer, textvariable=self.output_var).grid(row=4, column=1, sticky="ew", pady=4)
        ttk.Button(outer, text="Browse…", command=self._choose_output).grid(row=4, column=2, padx=(8, 0), pady=4)

        options = ttk.LabelFrame(outer, text="Options", padding=10)
        options.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(10, 8))
        ttk.Checkbutton(options, text="Auto-detect matching .out", variable=self.auto_vpt2_var).grid(row=0, column=0, sticky="w", padx=(0, 14))
        ttk.Checkbutton(options, text="Show generic groups", variable=self.generic_var).grid(row=0, column=1, sticky="w", padx=(0, 14))
        ttk.Checkbutton(options, text="Show raw ICs", variable=self.raw_var).grid(row=0, column=2, sticky="w", padx=(0, 14))
        ttk.Label(options, text="IR FWHM (cm⁻¹):").grid(row=0, column=3, sticky="e", padx=(8, 5))
        ttk.Entry(options, textvariable=self.fwhm_var, width=7).grid(row=0, column=4, sticky="w")

        buttons = ttk.Frame(outer)
        buttons.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(4, 8))
        self.run_button = ttk.Button(buttons, text="Run analysis", command=self._start_analysis)
        self.run_button.pack(side="left")
        ttk.Label(buttons, textvariable=self.status_var).pack(side="left", padx=(14, 0))

        ttk.Label(outer, text="Analysis log:").grid(row=7, column=0, columnspan=3, sticky="w")
        log_frame = ttk.Frame(outer)
        log_frame.grid(row=8, column=0, columnspan=3, sticky="nsew", pady=(4, 0))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log = tk.Text(log_frame, wrap="word", height=18)
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
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
        path = filedialog.askopenfilename(title="Select the central ORCA Hessian", initialdir=self._initial_dir(), filetypes=[("ORCA Hessian", "*.hess"), ("All files", "*")])
        if path:
            self.hess_var.set(path)

    def _choose_vpt2(self) -> None:
        path = filedialog.askopenfilename(title="Select an ORCA VPT2/GVPT2 output (optional)", initialdir=self._initial_dir(), filetypes=[("ORCA output", "*.out"), ("All files", "*")])
        if path:
            self.vpt2_var.set(path)

    def _choose_output(self) -> None:
        path = filedialog.askdirectory(title="Select output directory", initialdir=self._initial_dir())
        if path:
            self.output_var.set(path)

    def _start_analysis(self) -> None:
        hess_text = self.hess_var.get().strip()
        if not hess_text:
            messagebox.showerror("Missing Hessian", "Please select the central ORCA .hess file.")
            return
        hess = Path(hess_text).expanduser()
        if not hess.is_file():
            messagebox.showerror("File not found", f"Hessian file not found:\n{hess}")
            return
        try:
            fwhm = float(self.fwhm_var.get().strip())
            if fwhm <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid FWHM", "IR FWHM must be a positive number.")
            return

        argv = [str(hess.resolve()), "--ir-fwhm", str(fwhm)]
        vpt2_text = self.vpt2_var.get().strip()
        if vpt2_text:
            vpt2 = Path(vpt2_text).expanduser()
            if not vpt2.is_file():
                messagebox.showerror("File not found", f"VPT2/GVPT2 output not found:\n{vpt2}")
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
        self.run_button.configure(state="disabled")
        self.status_var.set("Running…")
        self.log.delete("1.0", "end")
        self.log.insert("end", f"ORCA PED Analyzer {core.__version__}\nInput: {hess.resolve()}\n\n")
        threading.Thread(target=self._worker, args=(argv,), daemon=True).start()

    def _worker(self, argv: list[str]) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        old_argv = sys.argv[:]
        exit_code = 0
        try:
            sys.argv = ["orca_ped_analyzer"] + argv
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                try:
                    core.main()
                except SystemExit as exc:
                    if isinstance(exc.code, str):
                        print(exc.code, file=sys.stderr)
                        exit_code = 1
                    elif exc.code is None:
                        exit_code = 0
                    else:
                        exit_code = int(exc.code)
                except Exception:
                    traceback.print_exc(file=sys.stderr)
                    exit_code = 1
        finally:
            sys.argv = old_argv
        text = stdout.getvalue()
        err = stderr.getvalue()
        if err:
            text += ("\n" if text and not text.endswith("\n") else "") + "\n--- warnings/errors ---\n" + err
        self.root.after(0, lambda: self._finish(exit_code, text))

    def _finish(self, exit_code: int, text: str) -> None:
        self.log.insert("end", text)
        self.log.see("end")
        self.run_button.configure(state="normal")
        if exit_code == 0:
            self.status_var.set(f"Analysis completed. Output: {self.last_output_dir}")
        else:
            self.status_var.set("Analysis failed; see the log.")
            messagebox.showerror("Analysis failed", "ORCA PED Analyzer reported an error. See the analysis log for details.")


def main() -> None:
    root = tk.Tk()
    AnalyzerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
