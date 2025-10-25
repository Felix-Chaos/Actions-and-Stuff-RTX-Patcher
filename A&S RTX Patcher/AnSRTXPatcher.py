import locale
import os
import shutil
import subprocess
import threading
import sys
import zipfile
import ctypes
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import hashlib
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap import Toplevel, Button, Label, Frame

# Ensure locale works safely
try:
    locale.setlocale(locale.LC_ALL, 'English_United States.1252')
except locale.Error:
    locale.setlocale(locale.LC_ALL, 'C')


# Utility functions
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def center_window(window):
    window.update_idletasks()
    w = window.winfo_width()
    h = window.winfo_height()
    ws = window.winfo_screenwidth()
    hs = window.winfo_screenheight()
    x = (ws // 2) - (w // 2)
    y = (hs // 2) - (h // 2)
    window.geometry(f'{w}x{h}+{x}+{y}')
    window.attributes('-topmost', True)


def get_folder_stats(folder, return_files=False):
    total_size = 0
    file_count = 0
    folder_count = 0
    file_list = []

    for root, dirs, files in os.walk(folder):
        folder_count += len(dirs)
        file_count += len(files)
        for f in files:
            try:
                fp = os.path.join(root, f)
                if return_files:
                    file_list.append(fp)
                total_size += os.path.getsize(fp)
            except:
                pass

    return (total_size, file_count, folder_count, file_list) if return_files else (total_size, file_count, folder_count)


def compress_deterministic(folder_path, output_zip):
    with zipfile.ZipFile(output_zip, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in sorted(os.walk(folder_path)):
            for file in sorted(files):
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path).replace("\\", "/")

                info = zipfile.ZipInfo(arcname)
                info.date_time = (1980, 1, 1, 0, 0, 0)
                info.compress_type = zipfile.ZIP_DEFLATED

                with open(file_path, 'rb') as f:
                    zf.writestr(info, f.read())


def sha1_of_file(path):
    """Return SHA-1 hex digest of path or a message if unavailable."""
    if not os.path.exists(path):
        return "(not found)"
    h = hashlib.sha1()
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        return f"(error reading: {e})"


def show_error_and_exit(title, summary, details, files_checksums, exit_code=1):
    """
    Build a friendly multi-line error message that contains:
    - summary (short reason)
    - details (stderr/stdout)
    - files_checksums: dict name->path
    Then show messagebox and exit.
    """
    lines = []
    lines.append(f"{summary}\n")
    if details:
        lines.append("Details:\n")
        # keep details reasonably short
        lines.extend([details.strip(), "\n"])
    lines.append("File checksums (SHA-1):")
    for name, path in files_checksums.items():
        try:
            digest = sha1_of_file(path)
        except Exception as e:
            digest = f"(error computing: {e})"
        lines.append(f"- {name}: {digest}  [{path if path else 'N/A'}]")

    lines.append("\nTip: Verify the source pack matches the original/unmodified file (use sha1 or sha256).")
    lines.append("The program will now close.")
    message = "\n".join(lines)

    # Show error dialog (OK button)
    try:
        messagebox.showerror(title, message)
    except Exception:
        # If messagebox fails for some reason, print to stderr (still exit)
        print(message, file=sys.stderr)

    # Forcefully terminate everything
    os._exit(exit_code)


# --- CLEAN FOR UPDATE ---
def clean_for_update():
    top = ttk.Toplevel()
    top.title("Clean for Update")
    top.geometry("550x350")
    top.attributes("-topmost", True)
    center_window(top)

    frame = ttk.Frame(top, padding=20)
    frame.pack(fill="both", expand=True)

    label = ttk.Label(frame, text="Looking for A&SforRTX folders...", font=("Segoe UI", 12))
    label.pack(pady=(0, 10))

    progress = ttk.Progressbar(frame, mode='indeterminate', length=400, bootstyle=INFO)
    progress.pack(pady=(0, 10))
    progress.start()

    results_box = tk.Text(frame, height=8, width=70, state="disabled", wrap="none")
    results_box.pack(pady=(5, 5))

    confirm_btn = ttk.Button(
        frame,
        text="Confirm Deletion",
        width=30,
        state="disabled",
        bootstyle=SUCCESS
    )
    confirm_btn.pack(pady=(5, 10))

    from collections import defaultdict

    def log_grouped_paths(grouped):
        results_box.configure(state="normal")
        for parent, children in grouped.items():
            results_box.insert("end", f"├─ {parent}\n")
            for i, child in enumerate(children):
                symbol = "└─" if i == len(children) - 1 else "├─"
                results_box.insert("end", f"    {symbol} {child}\n")
        results_box.configure(state="disabled")

    def confirm_deletion(folders, results_box, top):
        deleted = 0
        for path in folders:
            try:
                shutil.rmtree(path)
                deleted += 1
            except Exception as e:
                results_box.configure(state="normal")
                results_box.insert("end", f"❌ Failed: {path} ({e})\n")
                results_box.configure(state="disabled")
        if deleted > 0:
            messagebox.showinfo("✅ Done", f"{deleted} folders deleted successfully.")
        else:
            messagebox.showinfo("Nothing to Clean", "No folders were deleted.")
        os._exit(0)

    def scan_and_confirm():
        nonlocal found_folders
        found_folders = []

        base_paths = [
            os.path.expandvars(
                r"%LocalAppData%\Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState\games\com.mojang"
            ),
            os.path.expandvars(
                r"%LocalAppData%\Packages\Microsoft.MinecraftWindowsBeta_8wekyb3d8bbwe\LocalState\games\com.mojang"
            )
        ]

        grouped_paths = defaultdict(list)

        for base_path in base_paths:
            resource_packs = os.path.join(base_path, "resource_packs")
            if os.path.exists(resource_packs):
                for folder in os.listdir(resource_packs):
                    if folder.startswith("A&SforRTX") or folder.startswith("Actions & Stuff Enhanced"):
                        full_path = os.path.join(resource_packs, folder)
                        found_folders.append(full_path)
                        grouped_paths[os.path.relpath(resource_packs)].append(folder)

            worlds_dir = os.path.join(base_path, "minecraftWorlds")
            if os.path.exists(worlds_dir):
                for world in os.listdir(worlds_dir):
                    world_rp = os.path.join(worlds_dir, world, "resource_packs")
                    if os.path.exists(world_rp):
                        for folder in os.listdir(world_rp):
                            if folder.startswith("A&SforRTX") or folder.startswith("Actions & Stuff Enhanced"):
                                full_path = os.path.join(world_rp, folder)
                                found_folders.append(full_path)
                                grouped_paths[os.path.relpath(world_rp)].append(folder)

        progress.stop()

        if found_folders:
            label.config(text="Folders Found")
            progress["value"] = 100
            progress.update()
            log_grouped_paths(grouped_paths)
            confirm_btn.config(state="normal", command=lambda: confirm_deletion(found_folders, results_box, top))
        else:
            results_box.configure(state="normal")
            results_box.insert("end", "No matching folders found.\n")
            results_box.configure(state="disabled")
            messagebox.showinfo("Nothing to Clean", "No folders starting with 'A&SforRTX' were found.")
            os._exit(0)

    found_folders = []
    threading.Thread(target=scan_and_confirm, daemon=True).start()


# --- PATCH FROM MARKETPLACE ---
def patch_from_marketplace(root):
    top = ttk.Toplevel(root)
    top.title("Patch from Marketplace")
    top.geometry("500x300")
    top.attributes('-topmost', True)
    frame = ttk.Frame(top, padding=20)
    frame.pack()
    center_window(top)

    target_files = 13049
    target_dirs = 159

    resource_paths = [
        os.path.expandvars(
            r"%LocalAppData%\Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState\premium_cache\resource_packs"
        ),
        os.path.expandvars(
            r"%LocalAppData%\Packages\Microsoft.MinecraftWindowsBeta_8wekyb3d8bbwe\LocalState\premium_cache\resource_packs"
        )
    ]

    output_dir = os.path.join(os.getcwd(), "xdelta3", "original")
    output_zip = os.path.join(output_dir, "Actions & Stuff encrypted.zip")
    exe_path = resource_path(os.path.join("xdelta3", "exec", "xdelta3_x86_64_win.exe"))
    vcdiff_path = resource_path(os.path.join("xdelta3", "vcdiff", "Actions & Stuff encrypted.zip.vcdiff"))
    patched_output = os.path.join(os.getcwd(), "xdelta3", "output", "Actions n Stuff RTX + Dynamic lights.mcpack")

    status_label = ttk.Label(frame, text="Searching for Actions & Stuff encrypted folder...")
    status_label.pack(pady=(0, 10))

    progress = ttk.Progressbar(frame, mode='determinate', length=300, bootstyle=INFO, maximum=100)
    progress.pack(pady=(10, 0))
    progress["value"] = 0

    patch_btn = ttk.Button(frame, text="Patch", width=30, state="disabled", bootstyle=SUCCESS)
    patch_btn.pack(pady=(10, 0))

    def search_and_compress():
        status_label.config(text="Searching resource_packs...")
        found = False
        for path in resource_paths:
            if not os.path.exists(path):
                continue
            for folder in os.listdir(path):
                full_path = os.path.join(path, folder)
                if os.path.isdir(full_path):
                    status_label.config(text=f"Checking folder: {folder}")
                    try:
                        size, files, folders, file_list = get_folder_stats(full_path, return_files=True)
                    except Exception:
                        size, files, folders, file_list = (0, 0, 0, [])
                    if files == target_files and folders == target_dirs:
                        os.makedirs(output_dir, exist_ok=True)

                        # Provide progress while enumerating files (simulate activity)
                        total = len(file_list) or 1
                        for idx, fp in enumerate(file_list):
                            try:
                                os.path.getsize(fp)  # simulate read/access
                            except:
                                pass
                            progress["value"] = (idx + 1) / total * 80
                            if (idx + 1) % max(1, total // 10) == 0 or idx == total - 1:
                                status_label.config(text=f"Preparing files... {idx + 1}/{total}")
                            # tiny sleep to keep UI responsive-ish
                            time.sleep(0.001)

                        progress["value"] = 85
                        status_label.config(text="Compressing files... Might take a couple of minutes")
                        progress.update()

                        # Compress deterministically
                        try:
                            compress_deterministic(full_path, output_zip)
                        except Exception as e:
                            show_error_and_exit(
                                "Compression Error",
                                "Failed while compressing.",
                                str(e),
                                {"Source (folder)": full_path, "Output (zip)": output_zip},
                                exit_code=1
                            )

                        progress["value"] = 100
                        progress.update()
                        status_label.config(text="Compression complete.")
                        found = True
                        break
            if found:
                break

        if found:
            patch_btn.config(state="normal")
            status_label.config(text="Encrypted files ready for patching.")
        else:
            status_label.config(text="No matching folder found.")
            messagebox.showinfo("Not Found", "No matching encrypted folder was found.")
            os._exit(1)

    def run_patch():
        if not os.path.exists(output_zip):
            messagebox.showerror("Error", "Missing encrypted.zip in original folder.")
            os._exit(1)

        if not os.path.exists(vcdiff_path):
            messagebox.showerror("Error", f"Missing patch file:\n{vcdiff_path}")
            os._exit(1)

        def patch_thread():
            try:
                progress.start()
                patch_btn.config(state="disabled")
                status_label.config(text="Applying patch...")

                os.makedirs(os.path.dirname(patched_output), exist_ok=True)

                result = subprocess.run([
                    exe_path,
                    "-v", "-d",
                    "-s", output_zip,
                    vcdiff_path,
                    patched_output
                ], capture_output=True, text=True)

                progress.stop()

                if result.returncode != 0:
                    # collect checksums
                    files_checksums = {
                        "Source (zip)": output_zip,
                        "Patch (.vcdiff)": vcdiff_path,
                        "Patched output (if created)": patched_output if os.path.exists(patched_output) else ""
                    }
                    # choose a short reason if we can spot it in stderr
                    stderr = (result.stderr or "").strip()
                    reason = "Patch failed (target/source mismatch or invalid input)."
                    if "target window checksum mismatch" in stderr.lower() or "xd3_invalid_input" in stderr.lower():
                        reason = "Target window checksum mismatch (source seems wrong)."
                    show_error_and_exit(
                        "Patching failed (exit code {}).".format(result.returncode),
                        reason,
                        stderr or (result.stdout or ""),
                        files_checksums,
                        exit_code=1
                    )

                status_label.config(text="Moving final file and cleaning up...")
                final_output = os.path.join(os.getcwd(), "Actions & Stuff Enhanced RTX.mcpack")
                try:
                    shutil.move(patched_output, final_output)
                except Exception as e:
                    show_error_and_exit(
                        "Finalize Error",
                        "Failed to move/rename final patched file.",
                        str(e),
                        {"Patched output": patched_output, "Expected final": final_output},
                        exit_code=1
                    )

                shutil.rmtree(os.path.join(os.getcwd(), "xdelta3"), ignore_errors=True)

                messagebox.showinfo("🎉 Done!", f"Patched successfully!\nSaved as:\n{final_output}")
                os._exit(0)

            except Exception as e:
                show_error_and_exit(
                    "Unexpected Error",
                    "An unexpected exception occurred during patching.",
                    str(e),
                    {"Source (zip)": output_zip, "Patch (.vcdiff)": vcdiff_path, "Patched output": patched_output},
                    exit_code=1
                )

        threading.Thread(target=patch_thread, daemon=True).start()

    patch_btn.config(command=run_patch)
    threading.Thread(target=search_and_compress, daemon=True).start()


# --- PATCH DECRYPTED ZIP ---
def patch_decrypted_zip(root):
    top = ttk.Toplevel(root)
    top.title("Patch from .zip/.mcpack")
    top.geometry("500x320")
    top.attributes('-topmost', True)
    center_window(top)

    frame = ttk.Frame(top, padding=20)
    frame.pack(fill="both", expand=True)

    status_label = ttk.Label(frame, text="Select an A&S .zip or .mcpack")
    status_label.pack(pady=(0, 10))

    progress = ttk.Progressbar(frame, mode='determinate', length=300, bootstyle=INFO, maximum=100)
    progress.pack(pady=(5, 10))
    progress["value"] = 0

    patch_btn = ttk.Button(
        frame,
        text="Patch",
        width=30,
        state="disabled",
        bootstyle=SUCCESS
    )
    patch_btn.pack(pady=(10, 0))

    def choose_and_prepare():
        file_path = filedialog.askopenfilename(
            filetypes=[("Minecraft Packs", "*.zip *.mcpack")],
            title="Choose an A&S zip or mcpack"
        )
        if not file_path:
            os._exit(0)

        normalized_dir = os.path.join(os.getcwd(), "extracted_mcpack_temp")
        normalized_zip = os.path.join(os.getcwd(), "mcpack_normalized.zip")

        try:
            status_label.config(text="Normalizing for patching...")
            progress["value"] = 10
            progress.update()

            shutil.unpack_archive(file_path, normalized_dir, format="zip")
            time.sleep(0.2)
            progress["value"] = 20
            progress.update()

            # Flatten if there's only one folder at the top level
            top_items = os.listdir(normalized_dir)
            top_dirs = [d for d in top_items if os.path.isdir(os.path.join(normalized_dir, d))]

            if len(top_dirs) == 1:
                only_folder = os.path.join(normalized_dir, top_dirs[0])
                try:
                    status_label.config(text="Flattening single-folder package...")
                    for item in os.listdir(only_folder):
                        shutil.move(os.path.join(only_folder, item), normalized_dir)
                    os.rmdir(only_folder)
                except Exception as e:
                    messagebox.showwarning("Warning", f"Failed to flatten single-folder structure:\n{e}")

            progress["value"] = 30
            progress.update()

            # Remove marketplace-specific files
            status_label.config(text="Removing marketplace-specific files...")
            for root_dir, dirs, files in os.walk(normalized_dir):
                for f in files:
                    if f in ("contents.json", "signatures.json", "splashes.json", "sounds.json"):
                        try:
                            os.remove(os.path.join(root_dir, f))
                        except:
                            pass
                if "texts" in dirs:
                    try:
                        shutil.rmtree(os.path.join(root_dir, "texts"))
                        dirs.remove("texts")
                    except:
                        pass

            progress["value"] = 40
            progress.update()

            # Replace the top-level manifest.json if we have a custom one
            custom_manifest = resource_path(os.path.join("xdelta3", "manifest", "manifest.json"))
            target_manifest = os.path.join(normalized_dir, "manifest.json")

            if os.path.isfile(custom_manifest):
                try:
                    status_label.config(text="Replacing manifest...")
                    shutil.copy2(custom_manifest, target_manifest)
                except Exception as e:
                    print(f"Error copying manifest: {e}")

            progress["value"] = 50
            progress.update()

            status_label.config(text="Compressing normalized pack... Might take a couple of minutes")
            compress_deterministic(normalized_dir, normalized_zip)
            # cleanup
            try:
                shutil.rmtree(normalized_dir)
            except:
                pass

            progress["value"] = 100
            progress.update()
            status_label.config(text="Ready to patch.")
            patch_btn.config(state="normal")

        except Exception as e:
            show_error_and_exit(
                "Prepare Failed",
                "Failed to process the pack for patching.",
                str(e),
                {"Selected pack": file_path, "Normalized zip": normalized_zip},
                exit_code=1
            )

    def run_patch():
        vcdiff_path = resource_path(os.path.join("xdelta3", "vcdiff", "Actions & Stuff decrypted.zip.vcdiff"))
        exe_path = resource_path(os.path.join("xdelta3", "exec", "xdelta3_x86_64_win.exe"))
        output_file = os.path.join(os.getcwd(), "Actions & Stuff Enhanced RTX.mcpack")

        if not os.path.exists(vcdiff_path):
            messagebox.showerror("Error", "Missing decrypted vcdiff patch.")
            os._exit(1)

        def patch_thread():
            try:
                status_label.config(text="Applying patch...")
                progress.start()

                src_zip = os.path.join(os.getcwd(), "mcpack_normalized.zip")
                cmd = f'"{exe_path}" -v -d -s "{src_zip}" "{vcdiff_path}" "{output_file}"'
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

                progress.stop()

                if result.returncode != 0:
                    files_checksums = {
                        "Source (normalized zip)": src_zip,
                        "Patch (.vcdiff)": vcdiff_path,
                        "Patched output (if created)": output_file if os.path.exists(output_file) else ""
                    }
                    stderr = (result.stderr or "").strip()
                    reason = "Patch failed (target/source mismatch or invalid input)."
                    if "target window checksum mismatch" in stderr.lower() or "xd3_invalid_input" in stderr.lower():
                        reason = "Target window checksum mismatch (source seems wrong)."
                    show_error_and_exit(
                        "Patching failed (exit code {}).".format(result.returncode),
                        reason,
                        stderr or (result.stdout or ""),
                        files_checksums,
                        exit_code=1
                    )

                status_label.config(text="Patch applied — saving output...")
                messagebox.showinfo("🎉 Done!", f"Patched successfully!\nSaved as:\n{output_file}")
                os._exit(0)

            except Exception as e:
                show_error_and_exit(
                    "Unexpected Error",
                    "An unexpected exception occurred during patching.",
                    str(e),
                    {"Source (normalized zip)": src_zip, "Patch (.vcdiff)": vcdiff_path, "Output": output_file},
                    exit_code=1
                )

        threading.Thread(target=patch_thread, daemon=True).start()

    patch_btn.config(command=run_patch)
    threading.Thread(target=choose_and_prepare, daemon=True).start()


# --- MAIN MENU ---
def show_main_menu():
    root = ttk.Window(themename="superhero")
    root.title("AnS RTX Patcher")
    root.geometry("500x320")

    icon_path = resource_path("AnSPatchericon.ico")
    if os.path.exists(icon_path):
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(u"AnSPatcher")
            root.iconbitmap(icon_path)
        except Exception:
            pass

    frame = ttk.Frame(root, padding=30)
    frame.pack()
    center_window(root)

    ttk.Label(frame, text="AnS RTX Patcher", font=("Segoe UI", 16, "bold")).pack(pady=(0, 20))

    ttk.Button(
        frame,
        text="Patch from marketplace",
        width=30,
        command=lambda: [root.withdraw(), patch_from_marketplace(root)],
        bootstyle=INFO
    ).pack(pady=10)

    ttk.Button(
        frame,
        text="Patch from .zip/.mcpack",
        width=30,
        command=lambda: [root.withdraw(), patch_decrypted_zip(root)],
        bootstyle=PRIMARY
    ).pack(pady=10)

    ttk.Button(
        frame,
        text="Clean for Update (press before installing patched mcpack)",
        width=55,
        command=clean_for_update,
        bootstyle=WARNING
    ).pack(pady=10)

    ttk.Button(
        frame,
        text="Exit",
        width=30,
        command=lambda: os._exit(0),
        bootstyle=(DANGER, OUTLINE)
    ).pack(pady=10)

    root.mainloop()


# --- Run ---
if __name__ == "__main__":
    show_main_menu()
