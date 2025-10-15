import os
import shutil
import subprocess
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import patcher_methods as methods

def show_gen_patcher_window(parent):
    win = ttk.Toplevel(parent)
    win.title("General Patcher")
    win.geometry("500x320")
    methods.center_window(win)

    frame = ttk.Frame(win, padding=30)
    frame.pack()

    ttk.Label(frame, text="General Patcher", font=("Segoe UI", 16, "bold")).pack(pady=(0, 20))

    btn_patch_marketplace = ttk.Button(
        frame,
        text="Patch from marketplace",
        width=30,
        command=lambda: [win.withdraw(), show_marketplace_patcher(win)],
        bootstyle=INFO
    )
    btn_patch_decrypted = ttk.Button(
        frame,
        text="Patch from .zip/.mcpack",
        width=30,
        command=lambda: [win.withdraw(), show_zip_patcher(win)],
        bootstyle=PRIMARY
    )
    
    btn_patch_marketplace.pack(pady=10)
    btn_patch_decrypted.pack(pady=10)


def show_marketplace_patcher(parent):
    top = ttk.Toplevel(parent)
    top.title("Patch from Marketplace")
    top.geometry("500x250")
    top.attributes('-topmost', True)
    frame = ttk.Frame(top, padding=20)
    frame.pack()
    methods.center_window(top)

    target_files = 12951 #! Old 1.4 Value: 16661
    target_dirs = 161 #! Old 1.4 Value: 301

    resource_paths = [
        os.path.expandvars(
            r"%LocalAppData%\\Packages\\Microsoft.MinecraftUWP_8wekyb3d8bbwe\\LocalState\\premium_cache\\resource_packs"
        ),
        os.path.expandvars(
            r"%LocalAppData%\\Packages\\Microsoft.MinecraftWindowsBeta_8wekyb3d8bbwe\\LocalState\\premium_cache\\resource_packs"
        )
    ]

    output_dir = os.path.join(os.getcwd(), "xdelta3", "original")
    output_zip = os.path.join(output_dir, "Actions & Stuff encrypted.zip")
    exe_path = methods.resource_path(os.path.join("xdelta3", "exec", "xdelta3_x86_64_win.exe"))
    vcdiff_path = methods.resource_path(os.path.join("xdelta3", "vcdiff", "Actions & Stuff encrypted.zip.vcdiff"))
    patched_output = os.path.join(os.getcwd(), "xdelta3", "output", "Actions n Stuff RTX + Dynamic lights.mcpack")

    status_label = ttk.Label(frame, text="Searching for Actions & Stuff encrypted folder...")
    status_label.pack(pady=(0, 10))

    progress = ttk.Progressbar(frame, mode='determinate', length=300, bootstyle=INFO, maximum=100)
    progress.pack(pady=(10, 0))
    progress["value"] = 0
    
    patch_btn = ttk.Button(frame, text="Patch", width=30, state="disabled", bootstyle=SUCCESS)
    patch_btn.pack(pady=(10, 0))


    def search_and_compress():
        found = False
        for path in resource_paths:
            if not os.path.exists(path):
                continue
            for folder in os.listdir(path):
                full_path = os.path.join(path, folder)
                if os.path.isdir(full_path):
                    size, files, folders, file_list = methods.get_folder_stats(full_path, return_files=True)
                    if files == target_files and folders == target_dirs:
                        os.makedirs(output_dir, exist_ok=True)

                        total = len(file_list)
                        for idx, fp in enumerate(file_list):
                            try:
                                os.path.getsize(fp)  # Simulate activity
                            except:
                                pass
                            progress["value"] = (idx + 1) / total * 80

                        progress["value"] = 85
                        status_label.config(text="Compressing files... Might take a couple of minutes")
                        methods.compress_deterministic(full_path, output_zip)

                        progress["value"] = 100
                        found = True
                        break
            if found:
                break

        if found:
            if patch_btn.winfo_exists():
                patch_btn.config(state="normal")
                status_label.config(text="Encrypted files ready for patching.")
        else:
            if status_label.winfo_exists():
                status_label.config(text="No matching folder found.")
            progress["value"] = 0

    def run_patch():
        if not os.path.exists(output_zip):
            messagebox.showerror("Error", "Missing encrypted.zip in original folder.")
            return

        # Check file size to decide which vcdiff to use
        try:
            file_size = os.path.getsize(output_zip)
        except Exception as e:
            messagebox.showerror("Error", f"Couldn't read zip file size:\\n{e}")
            return
        #! Old 1.4 Value=>36014510
        #Todo: Remove if statement if it is not needed anymore
        if file_size == 31510910: 
            vcdiff_path_to_use = methods.resource_path(os.path.join("xdelta3", "vcdiff", "Actions & Stuff encrypted.zip.vcdiff"))
        else:
            messagebox.showerror("Error", f"No file size match for encrypted.zip ({file_size} bytes). Cannot determine correct patch.")

        if not os.path.exists(vcdiff_path_to_use):
            messagebox.showerror("Error", f"Missing patch file:\\n{vcdiff_path_to_use}")
            return

        try:
            progress.start()
            patch_btn.config(state="disabled")

            def patch_thread():
                try:
                    os.makedirs(os.path.dirname(patched_output), exist_ok=True)
                    subprocess.run([
                        exe_path,
                        "-v", "-d",
                        "-s", output_zip,
                        vcdiff_path_to_use,
                        patched_output
                    ], check=True)

                    final_output = os.path.join(os.getcwd(), "Actions & Stuff Enhanced RTX.mcpack")
                    shutil.move(patched_output, final_output)

                    messagebox.showinfo("🎉 Done!", f"Patched successfully!\\nSaved as:\\n{final_output}")
                    shutil.rmtree(os.path.join(os.getcwd(), "xdelta3"), ignore_errors=True)

                    top.destroy()
                    parent.deiconify()
                except subprocess.CalledProcessError as e:
                    messagebox.showerror("Error", f"Patching failed:\\n{str(e)}")
                finally:
                    progress.stop()
                    patch_btn.config(state="normal")

            threading.Thread(target=patch_thread, daemon=True).start()

        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error:\\n{str(e)}")
            progress.stop()

    patch_btn.config(command=run_patch)
    threading.Thread(target=search_and_compress, daemon=True).start()


def show_zip_patcher(parent):
    top = ttk.Toplevel(parent)
    top.title("Patch from .zip/.mcpack")
    top.geometry("500x250")
    top.attributes("-topmost", True)
    methods.center_window(top)

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
            top.destroy()
            parent.deiconify()
            return

        normalized_dir = os.path.join(os.getcwd(), "extracted_mcpack_temp")
        normalized_zip = os.path.join(os.getcwd(), "mcpack_normalized.zip")

        try:
            progress["value"] = 10
            status_label.config(text="Normalizing for patching...")

            shutil.unpack_archive(file_path, normalized_dir, format="zip")
            time.sleep(0.5)
            progress["value"] = 20

            # 🆕 Flatten if there's only one folder at the top level
            top_items = os.listdir(normalized_dir)
            top_dirs = [d for d in top_items if os.path.isdir(os.path.join(normalized_dir, d))]

            if len(top_dirs) == 1:
                only_folder = os.path.join(normalized_dir, top_dirs[0])
                try:
                    for item in os.listdir(only_folder):
                        shutil.move(os.path.join(only_folder, item), normalized_dir)
                    os.rmdir(only_folder)
                except Exception as e:
                    messagebox.showwarning("Warning", f"Failed to flatten single-folder structure:\\n{e}")

            progress["value"] = 30

            # Remove marketplace-specific files
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

            # Replace the top-level manifest.json
            custom_manifest = methods.resource_path(os.path.join("xdelta3", "manifest", "manifest.json"))
            target_manifest = os.path.join(normalized_dir, "manifest.json")

            if os.path.isfile(custom_manifest):
                try:
                    shutil.copy2(custom_manifest, target_manifest)
                except Exception as e:
                    print(f"Error copying manifest: {e}")

            progress["value"] = 50
            status_label.config(text="Compressing... Might take a couple of minutes")
            methods.compress_deterministic(normalized_dir, normalized_zip)
            shutil.rmtree(normalized_dir)
            progress["value"] = 100

            status_label.config(text="Ready to patch.")
            patch_btn.config(state="normal")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to process the pack:\\n{str(e)}")
            top.destroy()
            parent.deiconify()

    def run_patch():
        vcdiff_path = methods.resource_path(os.path.join("xdelta3", "vcdiff", "Actions & Stuff decrypted.zip.vcdiff"))  
        exe_path = methods.resource_path(os.path.join("xdelta3", "exec", "xdelta3_x86_64_win.exe"))
        output_file = os.path.join(os.getcwd(), "Actions & Stuff Enhanced RTX.mcpack")

        if not os.path.exists(vcdiff_path):
            messagebox.showerror("Error", "Missing decrypted vcdiff patch.")
            return

        patch_btn.config(state="disabled")
        progress.start()

        def patch_thread():
            try:
                os.makedirs(os.path.dirname(output_file), exist_ok=True)

                # Properly quote paths and run using shell
                cmd = f'"{exe_path}" -v -d -s "{os.path.join(os.getcwd(), "mcpack_normalized.zip")}" "{vcdiff_path}" "{output_file}"'
                subprocess.run(cmd, shell=True, check=True)

                messagebox.showinfo("🎉 Done!", f"Patched successfully!\\nSaved as:\\n{output_file}")
                os.remove(os.path.join(os.getcwd(), "mcpack_normalized.zip"))

                top.destroy()
                parent.deiconify()
            except subprocess.CalledProcessError as e:
                messagebox.showerror("Error", f"Patching failed:\\n{str(e)}")
            finally:
                progress.stop()
                patch_btn.config(state="normal")

        threading.Thread(target=patch_thread, daemon=True).start()

    patch_btn.config(command=run_patch)
    threading.Thread(target=choose_and_prepare, daemon=True).start()