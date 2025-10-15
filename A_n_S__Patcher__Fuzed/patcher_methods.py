import os
import shutil
import subprocess
import sys
import zipfile
import time
import tkinter as tk
from tkinter import messagebox
from collections import defaultdict
import ttkbootstrap as ttk


import default_config as config

def resource_path(relative_path: str) -> str:
    """Gets the absolute path to a resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def center_window(window):
    """Centers a tkinter window on the screen."""
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
                arcname = os.path.relpath(file_path, folder_path).replace("\\\\", "/")
                
                # Consistent DOS-compatible timestamp: Jan 1, 1980
                info = zipfile.ZipInfo(arcname)
                info.date_time = (1980, 1, 1, 0, 0, 0)
                info.compress_type = zipfile.ZIP_DEFLATED

                with open(file_path, 'rb') as f:
                    zf.writestr(info, f.read())

def clean_for_update(root):
    top = ttk.Toplevel(root)
    top.title("Clean for Update")
    top.geometry("550x350")
    top.attributes("-topmost", True)
    center_window(top)

    frame = ttk.Frame(top, padding=20)
    frame.pack(fill="both", expand=True)

    label = ttk.Label(frame, text="Looking for A&SforRTX folders...", font=("Segoe UI", 12))
    label.pack(pady=(0, 10))

    progress = ttk.Progressbar(frame, mode='indeterminate', length=400, bootstyle=ttk.INFO)
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
        bootstyle=ttk.SUCCESS
    )
    confirm_btn.pack(pady=(5, 10))

    def log_grouped_paths(grouped):
        results_box.configure(state="normal")
        for parent, children in grouped.items():
            results_box.insert("end", f"├─ {parent}\\n")
            for i, child in enumerate(children):
                symbol = "└─" if i == len(children) - 1 else "├─"
                results_box.insert("end", f"    {symbol} {child}\\n")
        results_box.configure(state="disabled")

    def confirm_deletion(folders, results_box, top):
        deleted = 0
        for path in folders:
            try:
                shutil.rmtree(path)
                deleted += 1
            except Exception as e:
                results_box.configure(state="normal")
                results_box.insert("end", f"❌ Failed: {path} ({e})\\n")
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
            config.CONFIG['paths']['minecraft_uwp'],
            config.CONFIG['paths']['minecraft_beta']
        ]

        grouped_paths = defaultdict(list)

        for base_path in base_paths:
            resource_packs = os.path.join(base_path, "resource_packs")
            if os.path.exists(resource_packs):
                for folder in os.listdir(resource_packs):
                    if folder.startswith(tuple(config.CONFIG['cleanup_prefixes'])):
                        full_path = os.path.join(resource_packs, folder)
                        found_folders.append(full_path)
                        grouped_paths[os.path.relpath(resource_packs)].append(folder)

            worlds_dir = os.path.join(base_path, "minecraftWorlds")
            if os.path.exists(worlds_dir):
                for world in os.listdir(worlds_dir):
                    world_rp = os.path.join(worlds_dir, world, "resource_packs")
                    if os.path.exists(world_rp):
                        for folder in os.listdir(world_rp):
                            if folder.startswith(tuple(config.CONFIG['cleanup_prefixes'])):
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
            results_box.insert("end", "No matching folders found.\\n")
            results_box.configure(state="disabled")
            messagebox.showinfo("Nothing to Clean", "No folders were found.")
            top.destroy()

    found_folders = []
    scan_and_confirm()