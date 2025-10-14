import os
import shutil
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

from typing import Any, Callable, Dict, List, Optional, Tuple


import default_config as config


def center_window(window: tk.Toplevel | tk.Tk) -> None:
    """Centers a tkinter window on the screen."""
    window.update_idletasks()
    width, height = window.winfo_width(), window.winfo_height()
    ws, hs = window.winfo_screenwidth(), window.winfo_screenheight()
    x, y = (ws // 2) - (width // 2), (hs // 2) - (height // 2)
    window.geometry(f'{width}x{height}+{x}+{y}')


def get_folder_stats(folder: str) -> Tuple[int, int]:
    """Calculates the number of files and subfolders within a directory."""
    file_count, folder_count = 0, 0
    try:
        for _, dirs, files in os.walk(folder):
            folder_count += len(dirs)
            file_count += len(files)
    except OSError:
        return 0, 0
    return file_count, folder_count


def resource_path(relative_path: str) -> str:
    """Gets the absolute path to a resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def marketplace_patcher_frame():
    root = ttk.Window(themename="darkly")
    root.title("Marketplace Patcher")

    cancel_event = threading.Event()
    output_dir = os.path.join(os.getcwd(), "temp_mp_patcher")
    output_zip = os.path.join(output_dir, "encrypted_zip_placeholder.zip")

    container = ttk.Frame(root, padding=30)
    container.pack(expand=True)

    status_label = ttk.Label(container, text="Searching for encrypted pack folder...")
    status_label.pack(pady=(0, 10))

    progress = ttk.Progressbar(container, mode='determinate', length=300, bootstyle=INFO)
    progress.pack(pady=(10, 0))

    btn_frame = ttk.Frame(container)
    btn_frame.pack(pady=(20, 0))

    def run_patch():
        print("Patch läuft...")  # Patch Logik hier

    def cancel_and_go_back():
        print("Zurück zum Menü")
        root.destroy()

    patch_btn = ttk.Button(btn_frame, text="Patch", width=20, state="disabled", command=run_patch, bootstyle=SUCCESS)
    patch_btn.pack(side="left", padx=5)

    ttk.Button(btn_frame, text="Back to Menu", width=20, command=cancel_and_go_back, bootstyle=(DANGER, OUTLINE)).pack(side="left", padx=5)

    def search_and_compress():
        import time
        for i in range(101):
            progress['value'] = i
            status_label.config(text=f"Fortschritt: {i}%")
            time.sleep(0.02)
        patch_btn.config(state="normal")

    threading.Thread(target=search_and_compress, daemon=True).start()


    def search_and_compress(self) -> None:
        """Searches for the pack and compresses it in a background thread."""
        premium_paths = [
            os.path.join(os.path.expandvars(CONFIG["paths"]["minecraft_uwp"]), "premium_cache", "resource_packs"),
            os.path.join(os.path.expandvars(CONFIG["paths"]["minecraft_beta"]), "premium_cache", "resource_packs")
        ]
        pack_stats = CONFIG["marketplace_pack_stats"]["v1"]
        found_path = None
        for path in premium_paths:
            if self.cancel_event.is_set(): return
            if not os.path.exists(path): continue
            for folder in os.listdir(path):
                if self.cancel_event.is_set(): return
                full_path = os.path.join(path, folder)
                if os.path.isdir(full_path):
                    num_files, num_dirs = get_folder_stats(full_path)
                    if num_files == pack_stats["files"] and num_dirs == pack_stats["dirs"]:
                        found_path = full_path; break
            if found_path: break

        if self.cancel_event.is_set(): return
        if not found_path:
            self.status_label.config(text="❌ No matching folder found.")
            return

        os.makedirs(self.output_dir, exist_ok=True)
        self.status_label.config(text="Compressing files...")
        success = compress_deterministic(found_path, self.output_zip, self.cancel_event, lambda c, t: self.progress.configure(value=(c/t)*100))
        if not success:
            robust_cleanup(self.output_dir)
            return

        self.status_label.config(text="✅ Encrypted files ready for patching.")
        self.patch_btn.config(state="normal")

    def run_patch(self) -> None:
        """Validates and starts the patching process."""
        if not os.path.exists(self.output_zip):
            self.controller.show_message("Error", "Missing encrypted source zip file.", {"OK": lambda: self.controller.show_frame("MarketplacePatcherFrame")})
            return
        
        patch_name = CONFIG["patches"]["encrypted_v1"]
        vcdiff_path = os.path.join(self.controller.patch_temp_dir, patch_name)
        if not os.path.exists(vcdiff_path):
            self.controller.show_message("Error", f"Patch file '{patch_name}' not found in the provided zip.", {"OK": lambda: self.controller.show_frame("MarketplacePatcherFrame")})
            return
            
        patched_output = os.path.join(self.controller.output_temp_dir, CONFIG["filenames"]["final_mcpack"])
        self.controller.create_hidden_dir(self.controller.output_temp_dir)
        
        self.patch_btn.config(state="disabled")
        self.status_label.config(text="Patching...")
        self.progress.config(value=0, mode="indeterminate"); self.progress.start()
        self.controller.run_patch_process(self.output_zip, vcdiff_path, patched_output)

    def cancel_and_go_back(self):
        """Signals the background thread to stop and returns to the main menu."""
        self.cancel_event.set()
        robust_cleanup(self.output_dir)
        self.controller.show_frame("MainMenuFrame")