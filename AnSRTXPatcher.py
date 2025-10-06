import locale

try:
    # This works on most English Windows systems
    locale.setlocale(locale.LC_ALL, 'English_United States.1252')
except locale.Error:
    # Safe fallback if the above isn't supported
    locale.setlocale(locale.LC_ALL, 'C')
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
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.themes import user
from ttkbootstrap import Toplevel
from ttkbootstrap import Button, Label, Frame, Toplevel



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

def compress_with_explorer(folder_path, output_path):
    vbs_path = "zip_script.vbs"
    with open(vbs_path, "w") as vbs:
        vbs.write(f'''
Set objArgs = WScript.Arguments
Set objFSO = CreateObject("Scripting.FileSystemObject")
Set objShell = CreateObject("Shell.Application")
Set zipFile = objFSO.CreateTextFile("{output_path}", True)
zipFile.Write "PK" & Chr(5) & Chr(6) & String(18, Chr(0))
zipFile.Close
Set zipFolder = objShell.NameSpace("{output_path}")
Set sourceFolder = objShell.NameSpace("{folder_path}")
zipFolder.CopyHere sourceFolder.Items, 4 + 16
Do Until zipFolder.Items.Count = sourceFolder.Items.Count
    WScript.Sleep 500
Loop
        ''')
    subprocess.call(["wscript", vbs_path])
    os.remove(vbs_path)

def compress_deterministic(folder_path, output_zip):
    with zipfile.ZipFile(output_zip, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in sorted(os.walk(folder_path)):
            for file in sorted(files):
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path).replace("\\", "/")
                
                # Consistent DOS-compatible timestamp: Jan 1, 1980
                info = zipfile.ZipInfo(arcname)
                info.date_time = (1980, 1, 1, 0, 0, 0)
                info.compress_type = zipfile.ZIP_DEFLATED

                with open(file_path, 'rb') as f:
                    zf.writestr(info, f.read())
    
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
        command=lambda: confirm_deletion(found_folders, results_box, top),
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
        top.destroy()

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
            confirm_btn.config(state="normal")
        else:
            results_box.configure(state="normal")
            results_box.insert("end", "No matching folders found.\n")
            results_box.configure(state="disabled")
            messagebox.showinfo("Nothing to Clean", "No folders starting with 'A&SforRTX' were found.")
            top.destroy()

    def delayed_scan():
        time.sleep(3)
        scan_and_confirm()

    found_folders = []
    threading.Thread(target=delayed_scan, daemon=True).start()


def patch_from_marketplace(root):
    top = ttk.Toplevel(root)
    top.title("Patch from Marketplace")
    top.geometry("500x250")
    top.attributes('-topmost', True)
    frame = ttk.Frame(top, padding=20)
    frame.pack()
    center_window(top)

    target_files = 16661
    target_dirs = 301

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
        found = False
        for path in resource_paths:
            if not os.path.exists(path):
                continue
            for folder in os.listdir(path):
                full_path = os.path.join(path, folder)
                if os.path.isdir(full_path):
                    size, files, folders, file_list = get_folder_stats(full_path, return_files=True)
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
                        compress_deterministic(full_path, output_zip)

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
            messagebox.showerror("Error", f"Couldn't read zip file size:\n{e}")
            return

        if file_size == 36014510:
            vcdiff_path_to_use = resource_path(os.path.join("xdelta3", "vcdiff", "Actions & Stuff encrypted.zip.vcdiff"))
        else:
            vcdiff_path_to_use = resource_path(os.path.join("xdelta3", "vcdiff", "Actions & Stuff encrypted 2.zip.vcdiff"))

        if not os.path.exists(vcdiff_path_to_use):
            messagebox.showerror("Error", f"Missing patch file:\n{vcdiff_path_to_use}")
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

                    messagebox.showinfo("🎉 Done!", f"Patched successfully!\nSaved as:\n{final_output}")
                    shutil.rmtree(os.path.join(os.getcwd(), "xdelta3"), ignore_errors=True)

                    top.destroy()
                    root.deiconify()
                except subprocess.CalledProcessError as e:
                    messagebox.showerror("Error", f"Patching failed:\n{str(e)}")
                finally:
                    progress.stop()
                    patch_btn.config(state="normal")

            threading.Thread(target=patch_thread, daemon=True).start()

        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error:\n{str(e)}")
            progress.stop()

    patch_btn.config(command=run_patch)
    threading.Thread(target=search_and_compress, daemon=True).start()
    
def patch_decrypted_zip(root):
    top = ttk.Toplevel(root)
    top.title("Patch from .zip/.mcpack")
    top.geometry("500x250")
    top.attributes("-topmost", True)
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
            top.destroy()
            root.deiconify()
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
                    messagebox.showwarning("Warning", f"Failed to flatten single-folder structure:\n{e}")

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
            custom_manifest = resource_path(os.path.join("xdelta3", "manifest", "manifest.json"))
            target_manifest = os.path.join(normalized_dir, "manifest.json")

            if os.path.isfile(custom_manifest):
                try:
                    shutil.copy2(custom_manifest, target_manifest)
                except Exception as e:
                    print(f"Error copying manifest: {e}")

            progress["value"] = 50
            status_label.config(text="Compressing... Might take a couple of minutes")
            compress_deterministic(normalized_dir, normalized_zip)
            shutil.rmtree(normalized_dir)
            progress["value"] = 100

            status_label.config(text="Ready to patch.")
            patch_btn.config(state="normal")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to process the pack:\n{str(e)}")
            top.destroy()
            root.deiconify()

    def run_patch():
        vcdiff_path = resource_path(os.path.join("xdelta3", "vcdiff", "Actions & Stuff decrypted.zip.vcdiff"))  
        exe_path = resource_path(os.path.join("xdelta3", "exec", "xdelta3_x86_64_win.exe"))
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

                messagebox.showinfo("🎉 Done!", f"Patched successfully!\nSaved as:\n{output_file}")
                os.remove(os.path.join(os.getcwd(), "mcpack_normalized.zip"))

                top.destroy()
                root.deiconify()
            except subprocess.CalledProcessError as e:
                messagebox.showerror("Error", f"Patching failed:\n{str(e)}")
            finally:
                progress.stop()
                patch_btn.config(state="normal")

        threading.Thread(target=patch_thread, daemon=True).start()

    patch_btn.config(command=run_patch)
    threading.Thread(target=choose_and_prepare, daemon=True).start()
    
def open_fix_window(root):
    top = ttk.Toplevel(root)
    top.title("Fix for 1.21.80")
    top.geometry("480x300")
    top.attributes('-topmost', True)
    center_window(top)

    frame = ttk.Frame(top, padding=20)
    frame.pack(expand=True, fill="both")

    ttk.Label(
        frame,
        text="USE ONLY IF YOU ARE USING A&S FROM THE MARKETPLACE AND AFTER PATCHING. FOR FUTURE UPDATES MAKE SURE TO USE RESTORE MARKETPLACE FOLDERS LOCATION BEFORE PATCHING SO THE PATCHER CAN FIND THE FOLDER",
        wraplength=440,
        font=("Segoe UI", 10, "bold")
    ).pack(pady=(0, 20))
    ttk.Label(
        frame,
        text="This fix moves ALL your marketplace texture packs from the PREMIUM_CACHE folder to the COM.MOJANG folder, this is a workaround for an issue with Minecraft 1.21.80 that prevents MER maps from any RTX resource pack to load while having a texture pack from the marketplace enabled.",
        wraplength=440,
        font=("Segoe UI", 10)
    ).pack(pady=(0, 20))

    button_frame = ttk.Frame(frame)
    button_frame.pack(pady=10)

    ttk.Button(
        button_frame,
        text="Move Marketplace Folders",
        bootstyle=SUCCESS,
        command=lambda: move_marketplace_folders(top)
    ).pack(side="left", padx=10)

    ttk.Button(
        button_frame,
        text="Restore Marketplace Folders Location",
        bootstyle=WARNING,
        command=lambda: revert_marketplace_folders(top)
    ).pack(side="left", padx=10)
def move_marketplace_folders(fix_window):
    src_dir = os.path.expandvars(r"%LocalAppData%\Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState\premium_cache\resource_packs")
    dst_dir = os.path.expandvars(r"%LocalAppData%\Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState\games\com.mojang\resource_packs")

    if not os.path.exists(src_dir):
        messagebox.showerror("Error", f"Source directory not found:\n{src_dir}")
        return

    os.makedirs(dst_dir, exist_ok=True)

    moved = 0
    for folder in os.listdir(src_dir):
        full_path = os.path.join(src_dir, folder)
        if os.path.isdir(full_path):
            contents_path = os.path.join(full_path, "contents.json")
            if os.path.exists(contents_path):
                try:
                    os.rename(contents_path, contents_path + ".bak")
                except Exception as e:
                    print(f"Failed to rename contents.json in {folder}: {e}")

            new_name = folder + "_mp"
            new_path = os.path.join(dst_dir, new_name)
            shutil.move(full_path, new_path)
            moved += 1

    messagebox.showinfo("Done", f"{moved} folder(s) moved to COM.MOJANG")
    fix_window.destroy()
    fix_window.master.deiconify()


def revert_marketplace_folders(fix_window):
    src_dir = os.path.expandvars(r"%LocalAppData%\Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState\games\com.mojang\resource_packs")
    dst_dir = os.path.expandvars(r"%LocalAppData%\Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState\premium_cache\resource_packs")

    if not os.path.exists(src_dir):
        messagebox.showerror("Error", f"Source directory not found:\n{src_dir}")
        return

    os.makedirs(dst_dir, exist_ok=True)

    moved = 0
    for folder in os.listdir(src_dir):
        if folder.endswith("_mp"):
            full_path = os.path.join(src_dir, folder)
            new_name = folder[:-3]  # Remove '_mp'
            new_path = os.path.join(dst_dir, new_name)
            shutil.move(full_path, new_path)

            contents_bak_path = os.path.join(new_path, "contents.json.bak")
            if os.path.exists(contents_bak_path):
                try:
                    os.rename(contents_bak_path, os.path.join(new_path, "contents.json"))
                except Exception as e:
                    print(f"Failed to restore contents.json in {new_name}: {e}")

            moved += 1

    messagebox.showinfo("Done", f"{moved} folder(s) moved back to PREMIUM_CACHE.")
    fix_window.destroy()
    fix_window.master.deiconify()

def show_main_menu():
    root = ttk.Window(themename="ansrtxpatcher1")
    root.title("AnS RTX Patcher")
    root.geometry("500x320")

    icon_path = resource_path("AnSPatchericon.ico")
    if os.path.exists(icon_path):
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(u"AnSPatcher")
        root.iconbitmap(icon_path)
        try:
            root.tk.call('wm', 'iconphoto', root._w, tk.PhotoImage(file=icon_path))
        except:
            pass

    frame = ttk.Frame(root, padding=30)
    frame.pack()
    center_window(root)

    ttk.Label(frame, text="AnS RTX Patcher", font=("Segoe UI", 16, "bold")).pack(pady=(0, 20))

    btn_patch_marketplace = ttk.Button(
        frame,
        text="Patch from marketplace",
        width=30,
        command=lambda: [root.withdraw(), patch_from_marketplace(root)],
        bootstyle=INFO
    )
    btn_patch_decrypted = ttk.Button(
        frame,
        text="Patch from .zip/.mcpack",
        width=30,
        command=lambda: [root.withdraw(), patch_decrypted_zip(root)],
        bootstyle=PRIMARY
    )
    btn_clean = ttk.Button(
    frame,
    text="Clean for Update (press before installing patched mcpack)",
    width=55,
    command=clean_for_update,
    bootstyle=WARNING
    )
    btn_exit = ttk.Button(
        frame,
        text="Exit",
        width=30,
        command=root.destroy,
        bootstyle=(DANGER, OUTLINE)
    )

    btn_patch_marketplace.pack(pady=10)
    btn_patch_decrypted.pack(pady=10)
    btn_clean.pack(pady=10)
    btn_exit.pack(pady=10)

    root.mainloop()

show_main_menu()