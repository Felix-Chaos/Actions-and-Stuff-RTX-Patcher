#!/usr/bin/env python3
"""Utility for preparing deterministic packs and vcdiff patches before compilation."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path
from typing import Callable, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# --- Path helpers -----------------------------------------------------------------

SCRIPT_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
if SCRIPT_DIR.name == "PreCompileScript":
    PROJECT_ROOT = SCRIPT_DIR.parent.parent
else:
    PROJECT_ROOT = SCRIPT_DIR.parent

DEFAULT_INPUTS = {
    "encrypted": "./EncryptedPack",
    "decrypted": "./DecryptedPack",
    "rtx": "./DecryptedRTXPack",
}

DEFAULT_ENCRYPTED_OUTPUT = PROJECT_ROOT / "A&S RTX Patcher" / "xdelta3" / "original" / "Actions & Stuff encrypted.zip"
DEFAULT_DECRYPTED_OUTPUT = PROJECT_ROOT / "A&S RTX Patcher" / "xdelta3" / "original" / "Actions & Stuff decrypted.zip"
DEFAULT_ENCRYPTED_VCDIFF = PROJECT_ROOT / "A&S RTX Patcher" / "xdelta3" / "vcdiff" / "Actions & Stuff encrypted.zip.vcdiff"
DEFAULT_DECRYPTED_VCDIFF = PROJECT_ROOT / "A&S RTX Patcher" / "xdelta3" / "vcdiff" / "Actions & Stuff decrypted.zip.vcdiff"

MANIFEST_CANDIDATES = (
    PROJECT_ROOT / "A&S RTX Patcher" / "xdelta3" / "manifest" / "manifest.json",
    PROJECT_ROOT / "Universial A&S RTX Patcher" / "xdelta3" / "manifest" / "manifest.json",
)
DEFAULT_MANIFEST = next((candidate for candidate in MANIFEST_CANDIDATES if candidate.exists()), MANIFEST_CANDIDATES[0])

BUILD_SCRIPTS = [
    Path("A&S RTX Patcher") / "build_patcher.bat",
    Path("Universial A&S RTX Patcher") / "build_patcher.bat",
]


def to_relative_display(path: Path) -> str:
    """Return a user-friendly relative path string for default display."""
    try:
        return str(path.relative_to(SCRIPT_DIR))
    except ValueError:
        try:
            return str(path.relative_to(PROJECT_ROOT))
        except ValueError:
            return str(path)


def resolve_user_path(value: str) -> Path:
    """Resolve a user-provided path relative to the script directory if needed."""
    candidate = Path(value.strip())
    if not candidate.is_absolute():
        candidate = (SCRIPT_DIR / candidate).resolve()
    return candidate


# --- Pack preparation -------------------------------------------------------------

def prepare_pack_tree(source: Path, destination: Path) -> Path:
    """Copy the provided pack directory into *destination*."""
    if destination.exists():
        shutil.rmtree(destination)
    if not source.is_dir():
        raise NotADirectoryError(f"Expected a folder but received: {source}")
    shutil.copytree(source, destination)
    return destination


def sanitize_decrypted_pack(pack_dir: Path, manifest_path: Path) -> None:
    """Apply the same cleanup rules used by the patchers before packaging."""
    removable_files = {"contents.json", "signatures.json", "splashes.json", "sounds.json"}
    for root, dirs, files in os.walk(pack_dir):
        root_path = Path(root)
        for file_name in files:
            if file_name in removable_files:
                try:
                    (root_path / file_name).unlink()
                except FileNotFoundError:
                    pass
        if "texts" in dirs:
            try:
                shutil.rmtree(root_path / "texts")
                dirs.remove("texts")
            except FileNotFoundError:
                pass
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_path}")
    shutil.copy2(manifest_path, pack_dir / "manifest.json")


def write_deterministic_zip(source_dir: Path, output_zip: Path) -> None:
    """Create a deterministic ZIP archive from *source_dir*."""
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    if output_zip.exists():
        output_zip.unlink()
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for root, dirs, files in os.walk(source_dir):
            dirs.sort()
            files.sort()
            for file_name in files:
                file_path = Path(root) / file_name
                arcname = file_path.relative_to(source_dir).as_posix()
                info = zipfile.ZipInfo(arcname)
                info.date_time = (1980, 1, 1, 0, 0, 0)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (file_path.stat().st_mode & 0xFFFF) << 16
                with file_path.open("rb") as handle:
                    archive.writestr(info, handle.read())


def ensure_xdelta3() -> Path:
    """Locate an xdelta3 executable within the repository or on PATH."""
    exec_dir = PROJECT_ROOT / "A&S RTX Patcher" / "xdelta3" / "exec"
    platform_candidates = []
    if sys.platform.startswith("win"):
        platform_candidates.append(exec_dir / "xdelta3_x86_64_win.exe")
    elif sys.platform == "darwin":
        platform_candidates.append(exec_dir / "xdelta3_mac")
    else:
        platform_candidates.append(exec_dir / "xdelta3_x64_linux")
    for candidate in platform_candidates:
        if candidate.exists():
            return candidate
    resolved = shutil.which("xdelta3")
    if resolved:
        return Path(resolved)
    raise FileNotFoundError("Unable to locate xdelta3 executable.")


def generate_vcdiff(source: Path, target: Path, output: Path, xdelta_exec: Path) -> None:
    """Create a VCDIFF patch by comparing *source* to *target*."""
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    command = [str(xdelta_exec), "-e", "-f", "-s", str(source), str(target), str(output)]
    print(f"Running: {' '.join(command)}")
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.stdout:
        print(completed.stdout.strip())
    if completed.stderr:
        print(completed.stderr.strip(), file=sys.stderr)
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(
            completed.returncode,
            command,
            output=completed.stdout,
            stderr=completed.stderr,
        )


def run_build_scripts(project_root: Path) -> None:
    """Execute known build scripts from the project root."""
    for script in BUILD_SCRIPTS:
        full_path = (project_root / script).resolve()
        if not full_path.exists():
            print(f"Skipping missing build script: {full_path}")
            continue
        print(f"Executing build script: {full_path}")
        if os.name == "nt":
            subprocess.run(["cmd", "/c", str(script)], cwd=str(project_root), check=True)
        else:
            subprocess.run([str(full_path)], cwd=str(project_root), check=True)


def process_packs(
    encrypted_input: Path,
    decrypted_input: Path,
    rtx_input: Path,
    encrypted_output: Path,
    decrypted_output: Path,
    manifest_path: Path,
    encrypted_vcdiff: Path,
    decrypted_vcdiff: Path,
    status_callback: Optional[Callable[[str], None]] = None,
) -> None:
    """Drive the deterministic zip creation and diff generation pipeline."""
    def update_status(message: str) -> None:
        print(message)
        if status_callback:
            status_callback(message)

    xdelta_exec = ensure_xdelta3()
    update_status("xdelta3 located.")

    with tempfile.TemporaryDirectory() as tmp_root:
        workspace = Path(tmp_root)
        update_status("Preparing input packs...")
        trees = {
            "encrypted": prepare_pack_tree(encrypted_input, workspace / "encrypted_src"),
            "decrypted": prepare_pack_tree(decrypted_input, workspace / "decrypted_src"),
            "rtx": prepare_pack_tree(rtx_input, workspace / "rtx_target"),
        }

        update_status("Sanitizing decrypted pack and copying manifest...")
        sanitize_decrypted_pack(trees["decrypted"], manifest_path)

        target_zip = workspace / "final_target.zip"

        update_status("Creating deterministic ZIP for encrypted pack...")
        write_deterministic_zip(trees["encrypted"], encrypted_output)

        update_status("Creating deterministic ZIP for decrypted pack...")
        write_deterministic_zip(trees["decrypted"], decrypted_output)

        update_status("Creating deterministic ZIP for RTX target pack...")
        write_deterministic_zip(trees["rtx"], target_zip)

        update_status("Generating vcdiff for encrypted pack...")
        generate_vcdiff(encrypted_output, target_zip, encrypted_vcdiff, xdelta_exec)

        update_status("Generating vcdiff for decrypted pack...")
        generate_vcdiff(decrypted_output, target_zip, decrypted_vcdiff, xdelta_exec)

    update_status("Running build scripts...")
    run_build_scripts(PROJECT_ROOT)
    update_status("Pre-compilation workflow completed successfully.")


# --- UI components ----------------------------------------------------------------

def create_directory_selector(
    parent: tk.Widget,
    label_text: str,
    text_variable: tk.StringVar,
) -> None:
    frame = ttk.Frame(parent)
    frame.pack(fill="x", pady=4)
    ttk.Label(frame, text=label_text, width=26, anchor="w").pack(side="left")
    entry = ttk.Entry(frame, textvariable=text_variable, width=60)
    entry.pack(side="left", padx=4, fill="x", expand=True)

    def on_browse() -> None:
        current = resolve_user_path(text_variable.get())
        initial_dir = current if current.exists() else SCRIPT_DIR
        chosen = filedialog.askdirectory(initialdir=str(initial_dir))
        if chosen:
            text_variable.set(to_relative_display(Path(chosen)))

    ttk.Button(frame, text="Browse", command=on_browse).pack(side="left")


def create_output_section(
    parent: tk.Widget,
    label_text: str,
    default_path: Path,
    *,
    defaultextension: str = "",
    filetypes: Optional[list[tuple[str, str]]] = None,
) -> tuple[tk.BooleanVar, tk.StringVar]:
    frame = ttk.Frame(parent)
    frame.pack(fill="x", pady=4)
    ttk.Label(frame, text=label_text, width=26, anchor="w").pack(side="left")
    var = tk.StringVar(value=to_relative_display(default_path))
    toggle = tk.BooleanVar(value=False)
    entry = ttk.Entry(frame, textvariable=var, width=60, state="disabled")
    entry.pack(side="left", padx=4, fill="x", expand=True)

    def on_toggle() -> None:
        state = "normal" if toggle.get() else "disabled"
        entry.configure(state=state)

    def on_browse() -> None:
        initial = resolve_user_path(var.get()) if toggle.get() else default_path
        chosen = filedialog.asksaveasfilename(
            initialfile=initial.name,
            initialdir=str(initial.parent),
            defaultextension=defaultextension,
            filetypes=filetypes or [("All files", "*.*")],
        )
        if chosen:
            var.set(to_relative_display(Path(chosen)))

    ttk.Checkbutton(frame, text="Custom path", variable=toggle, command=on_toggle).pack(side="left")
    ttk.Button(frame, text="Browse", command=on_browse).pack(side="left", padx=(4, 0))
    return toggle, var


def launch_ui() -> None:
    root = tk.Tk()
    root.title("Pre-Compile Pack Helper")

    main = ttk.Frame(root, padding=12)
    main.pack(fill="both", expand=True)

    ttk.Label(main, text="Input Packs", font=("Segoe UI", 11, "bold")).pack(anchor="w")

    encrypted_var = tk.StringVar(value=DEFAULT_INPUTS["encrypted"])
    decrypted_var = tk.StringVar(value=DEFAULT_INPUTS["decrypted"])
    rtx_var = tk.StringVar(value=DEFAULT_INPUTS["rtx"])

    create_directory_selector(main, "Encrypted pack", encrypted_var)
    create_directory_selector(main, "Decrypted pack", decrypted_var)
    create_directory_selector(main, "Decrypted RTX pack", rtx_var)

    ttk.Separator(main).pack(fill="x", pady=8)
    ttk.Label(main, text="Output Settings", font=("Segoe UI", 11, "bold")).pack(anchor="w")

    encrypted_toggle, encrypted_output_var = create_output_section(
        main,
        "Encrypted ZIP output",
        DEFAULT_ENCRYPTED_OUTPUT,
        defaultextension=".zip",
        filetypes=[("ZIP archive", "*.zip"), ("All files", "*.*")],
    )
    decrypted_toggle, decrypted_output_var = create_output_section(
        main,
        "Decrypted ZIP output",
        DEFAULT_DECRYPTED_OUTPUT,
        defaultextension=".zip",
        filetypes=[("ZIP archive", "*.zip"), ("All files", "*.*")],
    )

    ttk.Separator(main).pack(fill="x", pady=8)
    ttk.Label(main, text="VCDIFF Outputs", font=("Segoe UI", 11, "bold")).pack(anchor="w")

    encrypted_vcdiff_toggle, encrypted_vcdiff_var = create_output_section(
        main,
        "Encrypted VCDIFF output",
        DEFAULT_ENCRYPTED_VCDIFF,
        defaultextension=".vcdiff",
        filetypes=[("VCDIFF patch", "*.vcdiff"), ("All files", "*.*")],
    )
    decrypted_vcdiff_toggle, decrypted_vcdiff_var = create_output_section(
        main,
        "Decrypted VCDIFF output",
        DEFAULT_DECRYPTED_VCDIFF,
        defaultextension=".vcdiff",
        filetypes=[("VCDIFF patch", "*.vcdiff"), ("All files", "*.*")],
    )

    status_var = tk.StringVar(value="Idle")
    status_label = ttk.Label(main, textvariable=status_var)
    status_label.pack(anchor="w", pady=(8, 4))

    def set_status(message: str) -> None:
        status_var.set(message)
        status_label.update_idletasks()

    def on_run() -> None:
        try:
            inputs = {
                "encrypted": resolve_user_path(encrypted_var.get()),
                "decrypted": resolve_user_path(decrypted_var.get()),
                "rtx": resolve_user_path(rtx_var.get()),
            }

            outputs = {
                "encrypted": resolve_user_path(encrypted_output_var.get()) if encrypted_toggle.get() else DEFAULT_ENCRYPTED_OUTPUT,
                "decrypted": resolve_user_path(decrypted_output_var.get()) if decrypted_toggle.get() else DEFAULT_DECRYPTED_OUTPUT,
            }

            vcdiffs = {
                "encrypted": resolve_user_path(encrypted_vcdiff_var.get()) if encrypted_vcdiff_toggle.get() else DEFAULT_ENCRYPTED_VCDIFF,
                "decrypted": resolve_user_path(decrypted_vcdiff_var.get()) if decrypted_vcdiff_toggle.get() else DEFAULT_DECRYPTED_VCDIFF,
            }

            for path in inputs.values():
                if not path.exists():
                    raise FileNotFoundError(f"Input path not found: {path}")

            set_status("Starting pipeline...")
            root.config(cursor="watch")
            trigger_button.configure(state="disabled")
            process_packs(
                inputs["encrypted"],
                inputs["decrypted"],
                inputs["rtx"],
                outputs["encrypted"],
                outputs["decrypted"],
                DEFAULT_MANIFEST,
                vcdiffs["encrypted"],
                vcdiffs["decrypted"],
                status_callback=set_status,
            )
            messagebox.showinfo("Success", "Pre-compilation tasks completed successfully.")
            set_status("Done")
        except Exception as exc:  # pylint: disable=broad-except
            traceback.print_exc()
            messagebox.showerror("Error", str(exc))
            set_status("Failed")
        finally:
            trigger_button.configure(state="normal")
            root.config(cursor="")

    trigger_button = ttk.Button(main, text="Run", command=on_run)
    trigger_button.pack(pady=(8, 0))

    root.mainloop()


def main() -> None:
    launch_ui()


if __name__ == "__main__":
    main()
