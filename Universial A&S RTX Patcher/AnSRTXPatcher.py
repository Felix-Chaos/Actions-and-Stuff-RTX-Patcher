import ctypes
import json
import locale
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import zipfile
from collections import defaultdict
from tkinter import filedialog
from typing import Any, Callable, Dict, List, Optional, Tuple

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

# --- DEFAULT CONFIGURATION CONSTANTS ---
CONFIG: Dict[str, Any] = {
    "paths": {
        "minecraft_uwp": os.path.expandvars(r"%LocalAppData%/Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState"),
        "minecraft_beta": os.path.expandvars(r"%LocalAppData%/Packages/Microsoft.MinecraftWindowsBeta_8wekyb3d8bbwe/LocalState"),
        "xdelta_dir": "xdelta3",
    },
    "executables": {
        "xdelta": "xdelta3_x86_64_win.exe",
    },
    "filenames": {
        "encrypted_zip": "Actions & Stuff encrypted.zip",
        "normalized_zip": "Actions & Stuff decrypted.zip", # --- CHANGE: Updated filename ---
        "final_mcpack": "Actions & Stuff Enhanced RTX.mcpack",
        "icon": "AnSPatchericon.ico",
        "manifest": "manifest.json",
        "patch_config": "patch_config.json",
    },
    "patches": {
        "encrypted_v1": "Actions & Stuff encrypted.zip.vcdiff",
        "decrypted": "Actions & Stuff decrypted.zip.vcdiff",
    },
    "marketplace_pack_stats": {
        "v1": {"files": 16661, "dirs": 301}
    },
    "cleanup_prefixes": ["A&SforRTX", "Actions & Stuff Enhanced"],
    "files_to_remove": ["contents.json", "signatures.json", "splashes.json", "sounds.json"],
    "dirs_to_remove": ["texts"],
}

# --- UTILITY FUNCTIONS ---

def resource_path(relative_path: str) -> str:
    """Gets the absolute path to a resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

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

def center_window(window: tk.Toplevel | tk.Tk) -> None:
    """Centers a tkinter window on the screen."""
    window.update_idletasks()
    width, height = window.winfo_width(), window.winfo_height()
    ws, hs = window.winfo_screenwidth(), window.winfo_screenheight()
    x, y = (ws // 2) - (width // 2), (hs // 2) - (height // 2)
    window.geometry(f'{width}x{height}+{x}+{y}')

def compress_deterministic(
    folder_path: str, output_zip: str, cancel_event: threading.Event,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> bool:
    """Creates a zip file with a fixed timestamp and correct file order."""
    try:
        total_files = sum(len(files) for _, _, files in os.walk(folder_path))
        if total_files == 0: return True
        processed_files = 0
        with zipfile.ZipFile(output_zip, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in sorted(os.walk(folder_path)):
                if cancel_event.is_set(): return False
                for file in sorted(files):
                    if cancel_event.is_set(): return False
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, folder_path).replace("\\", "/")
                    info = zipfile.ZipInfo(arcname)
                    info.date_time = (1980, 1, 1, 0, 0, 0)
                    info.compress_type = zipfile.ZIP_DEFLATED
                    with open(file_path, 'rb') as f:
                        zf.writestr(info, f.read())
                    processed_files += 1
                    if progress_callback: progress_callback(processed_files, total_files)
        return True
    except (OSError, zipfile.BadZipFile):
        return False

def robust_cleanup(folder_path: str, retries: int = 3, delay: float = 0.5) -> None:
    """Attempts to delete a folder multiple times to overcome potential file locks."""
    for i in range(retries):
        try:
            if os.path.exists(folder_path):
                shutil.rmtree(folder_path)
            return
        except OSError:
            time.sleep(delay)

# --- VIEW FRAMES ---

class MainMenuFrame(ttk.Frame):
    """The main menu view with buttons for each action."""
    def __init__(self, parent: tk.Widget, controller: 'App'):
        super().__init__(parent)
        self.controller = controller
        
        container = ttk.Frame(self, padding=30)
        container.pack(expand=True)

        ttk.Label(container, text="AnS RTX Patcher", font=("Segoe UI", 16, "bold")).pack(pady=(0, 20))
        ttk.Button(container, text="Patch from Marketplace", width=40, command=lambda: controller.show_frame("MarketplacePatcherFrame"), bootstyle=INFO).pack(pady=8)
        ttk.Button(container, text="Patch from .zip/.mcpack", width=40, command=lambda: controller.show_frame("ZipPatcherFrame"), bootstyle=PRIMARY).pack(pady=8)
        ttk.Button(container, text="Clean Old Versions for Update", width=40, command=lambda: controller.show_frame("UpdateCleanerFrame"), bootstyle=WARNING).pack(pady=8)
        ttk.Button(container, text="Exit", width=40, command=controller.on_close, bootstyle=(DANGER, OUTLINE)).pack(pady=(20, 0))

class MessageFrame(ttk.Frame):
    """A generic frame to display messages and confirmation dialogs."""
    def __init__(self, parent: tk.Widget, controller: 'App'):
        super().__init__(parent)
        self.controller = controller
        
        container = ttk.Frame(self, padding=30)
        container.pack(expand=True)
        
        self.title_label = ttk.Label(container, text="", font=("Segoe UI", 16, "bold"))
        self.title_label.pack(pady=(0, 10))
        
        self.message_label = ttk.Label(container, text="", wraplength=400, justify="center")
        self.message_label.pack(pady=(0, 20))
        
        self.button_frame = ttk.Frame(container)
        self.button_frame.pack()

    def set_content(self, title: str, message: str, callbacks: Dict[str, Callable]):
        """Configures the message frame with new text and button actions."""
        self.title_label.config(text=title)
        self.message_label.config(text=message)
        
        for widget in self.button_frame.winfo_children():
            widget.destroy()
            
        for text, command in callbacks.items():
            bootstyle = SUCCESS if text.lower() == "yes" else (DANGER, OUTLINE) if text.lower() == "no" else PRIMARY
            ttk.Button(self.button_frame, text=text, command=command, bootstyle=bootstyle, width=15).pack(side="left", padx=5)

class PatchSelectionFrame(ttk.Frame):
    """The initial view prompting the user to select the patch zip file."""
    def __init__(self, parent: tk.Widget, controller: 'App'):
        super().__init__(parent)
        self.controller = controller

        container = ttk.Frame(self, padding=30)
        container.pack(expand=True)

        ttk.Label(container, text="Welcome to the Actions & Stuff for RTX Patcher", font=("Segoe UI", 16, "bold")).pack(pady=(0, 10))
        ttk.Label(container, text="To begin, please select the .zip file that contains the patch data.", wraplength=400, justify="center").pack(pady=(0, 20))

        btn_frame = ttk.Frame(container)
        btn_frame.pack()
        ttk.Button(btn_frame, text="Select Patch File", command=self.select_and_process_zip, bootstyle=SUCCESS, width=20).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Exit", command=controller.on_close, bootstyle=(DANGER, OUTLINE), width=20).pack(side="left", padx=5)

    def select_and_process_zip(self):
        """Opens a file dialog and processes the selected zip file."""
        patch_zip_path = filedialog.askopenfilename(
            title="Please select the zip file containing the patch data",
            filetypes=[("Zip Archives", "*.zip")]
        )
        if not patch_zip_path:
            return

        try:
            robust_cleanup(self.controller.patch_temp_dir)
            os.makedirs(self.controller.patch_temp_dir, exist_ok=True)
            with zipfile.ZipFile(patch_zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.controller.patch_temp_dir)
            
            if self.controller.load_patch_config() and self.controller.preflight_checks():
                self.controller.show_frame("MainMenuFrame")

        except Exception as e:
            self.controller.show_message("Error", f"Could not extract the patch zip file:\n{e}", {"OK": self.controller.on_close})

class MarketplacePatcherFrame(ttk.Frame):
    """The view for patching from the Marketplace cache."""
    def __init__(self, parent: tk.Widget, controller: 'App'):
        super().__init__(parent)
        self.controller = controller
        self.cancel_event = threading.Event()
        self.output_dir = os.path.join(os.getcwd(), "temp_mp_patcher")
        self.output_zip = os.path.join(self.output_dir, CONFIG["filenames"]["encrypted_zip"])
        
        container = ttk.Frame(self, padding=30)
        container.pack(expand=True)
        
        self.status_label = ttk.Label(container, text="Searching for encrypted pack folder...")
        self.status_label.pack(pady=(0, 10))
        self.progress = ttk.Progressbar(container, mode='determinate', length=300, bootstyle=INFO)
        self.progress.pack(pady=(10, 0))
        
        btn_frame = ttk.Frame(container)
        btn_frame.pack(pady=(20, 0))
        self.patch_btn = ttk.Button(btn_frame, text="Patch", width=20, state="disabled", command=self.run_patch, bootstyle=SUCCESS)
        self.patch_btn.pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Back to Menu", width=20, command=self.cancel_and_go_back, bootstyle=(DANGER, OUTLINE)).pack(side="left", padx=5)
        
        threading.Thread(target=self.search_and_compress, daemon=True).start()

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

class ZipPatcherFrame(ttk.Frame):
    """The view for patching from a user-provided .zip file."""
    def __init__(self, parent: tk.Widget, controller: 'App'):
        super().__init__(parent)
        self.controller = controller
        self.cancel_event = threading.Event()
        self.temp_dir = os.path.join(os.getcwd(), "temp_zip_patcher")
        self.normalized_zip = os.path.join(self.temp_dir, CONFIG["filenames"]["normalized_zip"])
        
        container = ttk.Frame(self, padding=30)
        container.pack(expand=True)
        
        self.status_label = ttk.Label(container, text="Select an A&S .zip or .mcpack")
        self.status_label.pack(pady=(0, 10))
        self.progress = ttk.Progressbar(container, mode='determinate', length=300, bootstyle=INFO)
        self.progress.pack(pady=(5, 10))
        
        btn_frame = ttk.Frame(container)
        btn_frame.pack(pady=(20, 0))
        self.patch_btn = ttk.Button(btn_frame, text="Patch", width=20, state="disabled", command=self.run_patch, bootstyle=SUCCESS)
        self.patch_btn.pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Back to Menu", width=20, command=self.cancel_and_go_back, bootstyle=(DANGER, OUTLINE)).pack(side="left", padx=5)
        
        self.after(100, self.choose_and_prepare)

    def choose_and_prepare(self) -> None:
        """Opens file dialog and starts processing in a background thread."""
        file_path = filedialog.askopenfilename(filetypes=[("Minecraft Packs", "*.zip *.mcpack")], title="Choose an A&S .zip or .mcpack")
        if not file_path:
            self.controller.show_frame("MainMenuFrame")
            return
        threading.Thread(target=self._process_file, args=(file_path,), daemon=True).start()

    def _process_file(self, file_path: str) -> None:
        """Worker thread for unpacking, cleaning, and re-compressing the file."""
        normalized_dir = os.path.join(self.temp_dir, "extracted")
        robust_cleanup(self.temp_dir)
        os.makedirs(normalized_dir, exist_ok=True)
        try:
            self.status_label.config(text="Unpacking archive..."); self.progress.config(value=10)
            shutil.unpack_archive(file_path, normalized_dir, format="zip")
            if self.cancel_event.is_set(): raise InterruptedError
            
            self.status_label.config(text="Cleaning and preparing files..."); self.progress.config(value=30)
            self._cleanup_and_prepare_files(normalized_dir)
            if self.cancel_event.is_set(): raise InterruptedError
            
            self.status_label.config(text="Compressing files..."); self.progress.config(value=50)
            success = compress_deterministic(normalized_dir, self.normalized_zip, self.cancel_event, lambda c, t: self.progress.configure(value=50 + (c/t)*50))
            if not success: raise InterruptedError
            
            self.status_label.config(text="✅ Ready to patch.")
            self.patch_btn.config(state="normal")
        except InterruptedError: pass
        except Exception as e:
            if not self.cancel_event.is_set(): self.controller.show_message("Error", f"Failed to process the pack:\n{e}", {"OK": lambda: self.controller.show_frame("MainMenuFrame")})
        finally:
            if self.cancel_event.is_set(): robust_cleanup(self.temp_dir)

    def _cleanup_and_prepare_files(self, directory: str) -> None:
        """Removes unwanted files and replaces the manifest."""
        top_items, top_dirs = os.listdir(directory), [d for d in os.listdir(directory) if os.path.isdir(os.path.join(directory, d))]
        if len(top_dirs) == 1:
            only_folder = os.path.join(directory, top_dirs[0])
            for item in os.listdir(only_folder): shutil.move(os.path.join(only_folder, item), directory)
            os.rmdir(only_folder)
        for root, dirs, files in os.walk(directory):
            for f in files:
                if f in CONFIG["files_to_remove"]: os.remove(os.path.join(root, f))
            for d in list(dirs):
                if d in CONFIG["dirs_to_remove"]: shutil.rmtree(os.path.join(root, d)); dirs.remove(d)
        
        custom_manifest = resource_path(os.path.join(CONFIG["paths"]["xdelta_dir"], "manifest", CONFIG["filenames"]["manifest"]))
        if os.path.isfile(custom_manifest): shutil.copy2(custom_manifest, os.path.join(directory, CONFIG["filenames"]["manifest"]))

    def run_patch(self) -> None:
        """Starts the patching process for the normalized zip."""
        vcdiff_path = os.path.join(self.controller.patch_temp_dir, CONFIG["patches"]["decrypted"])
        if not os.path.exists(vcdiff_path):
            self.controller.show_message("Error", f"Patch file '{CONFIG['patches']['decrypted']}' not found in the provided zip.", {"OK": lambda: self.controller.show_frame("MainMenuFrame")})
            return

        patched_output = os.path.join(self.controller.output_temp_dir, CONFIG["filenames"]["final_mcpack"])
        self.controller.create_hidden_dir(self.controller.output_temp_dir)
        
        self.patch_btn.config(state="disabled")
        self.progress.config(value=0, mode="indeterminate"); self.progress.start()
        self.controller.run_patch_process(self.normalized_zip, vcdiff_path, patched_output)

    def cancel_and_go_back(self):
        self.cancel_event.set()
        robust_cleanup(self.temp_dir)
        self.controller.show_frame("MainMenuFrame")

class UpdateCleanerFrame(ttk.Frame):
    """The view for finding and cleaning old pack versions."""
    def __init__(self, parent: tk.Widget, controller: 'App'):
        super().__init__(parent)
        self.controller = controller
        self.cancel_event = threading.Event()
        self.found_folders: List[str] = []
        container = ttk.Frame(self, padding=30)
        container.pack(expand=True)
        self.label = ttk.Label(container, text="Looking for old pack folders...", font=("Segoe UI", 12))
        self.label.pack(pady=(0, 10))
        self.progress = ttk.Progressbar(container, mode='indeterminate', length=400, bootstyle=INFO)
        self.progress.pack(pady=(0, 10)); self.progress.start()
        self.results_box = tk.Text(container, height=8, width=70, state="disabled", wrap="none")
        self.results_box.pack(pady=(5, 5))
        btn_frame = ttk.Frame(container)
        btn_frame.pack(pady=(10, 0))
        self.confirm_btn = ttk.Button(btn_frame, text="Confirm Deletion", width=20, state="disabled", command=self.confirm_deletion, bootstyle=SUCCESS)
        self.confirm_btn.pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Back to Menu", width=20, command=self.cancel_and_go_back, bootstyle=(DANGER, OUTLINE)).pack(side="left", padx=5)
        threading.Thread(target=self.scan_for_folders, daemon=True).start()

    def log_grouped_paths(self, grouped: Dict[str, List[str]]) -> None:
        """Displays found folders in the text box."""
        self.results_box.configure(state="normal")
        self.results_box.delete("1.0", "end")
        for parent, children in grouped.items():
            self.results_box.insert("end", f"├─ {parent}\n")
            for i, child in enumerate(children):
                self.results_box.insert("end", f"    {'└─' if i == len(children) - 1 else '├─'} {child}\n")
        self.results_box.configure(state="disabled")

    def confirm_deletion(self) -> None:
        """Deletes the found folders after user confirmation."""
        deleted_count = sum(1 for path in self.found_folders if self._delete_folder(path))
        self.controller.show_message("✅ Done", f"{deleted_count} folders deleted successfully.", {"OK": lambda: self.controller.show_frame("MainMenuFrame")})

    def _delete_folder(self, path: str) -> bool:
        try:
            shutil.rmtree(path)
            return True
        except Exception as e:
            self.controller.show_message("Deletion Error", f"Failed to delete {path}:\n{e}", {"OK": lambda: self.controller.show_frame("MainMenuFrame")})
            return False

    def scan_for_folders(self) -> None:
        """Scans for old pack versions in a background thread."""
        base_paths = [
            os.path.join(os.path.expandvars(CONFIG["paths"]["minecraft_uwp"]), "games", "com.mojang"),
            os.path.join(os.path.expandvars(CONFIG["paths"]["minecraft_beta"]), "games", "com.mojang")
        ]
        grouped_paths = defaultdict(list)
        for base_path in base_paths:
            if self.cancel_event.is_set(): return
            if not os.path.exists(base_path): continue
            for dir_name in ["resource_packs", "minecraftWorlds"]:
                if self.cancel_event.is_set(): return
                target_dir = os.path.join(base_path, dir_name)
                if os.path.exists(target_dir): self._scan_directory(target_dir, grouped_paths)
        if self.cancel_event.is_set(): return
        self.progress.stop(); self.progress.pack_forget()
        if self.found_folders:
            self.label.config(text="Folders Found (Confirm Deletion)")
            self.log_grouped_paths(grouped_paths)
            self.confirm_btn.config(state="normal")
        else:
            self.controller.show_message("Nothing to Clean", "No old pack folders were found.", {"OK": lambda: self.controller.show_frame("MainMenuFrame")})

    def _scan_directory(self, path: str, grouped: Dict[str, List[str]]) -> None:
        if "minecraftWorlds" in os.path.basename(os.path.dirname(path)) and os.path.basename(path) != "resource_packs":
            for item in os.listdir(path):
                if self.cancel_event.is_set(): return
                world_rp = os.path.join(path, item, "resource_packs")
                if os.path.isdir(world_rp): self._scan_directory(world_rp, grouped)
            return
        for folder in os.listdir(path):
            if self.cancel_event.is_set(): return
            if any(folder.startswith(p) for p in CONFIG["cleanup_prefixes"]):
                full_path = os.path.join(path, folder)
                self.found_folders.append(full_path)
                grouped[os.path.relpath(path)].append(folder)

    def cancel_and_go_back(self):
        """Signals the background thread to stop and returns to the main menu."""
        self.cancel_event.set()
        self.controller.show_frame("MainMenuFrame")

# --- MAIN APPLICATION CLASS ---

class App(ttk.Window):
    """The main application that holds and manages all the view frames."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title("AnS RTX Patcher")
        self.geometry("700x400")
        center_window(self)
        self._setup_theme_and_icon()
        self.container = ttk.Frame(self)
        self.container.pack(side="top", fill="both", expand=True)
        self.frames: Dict[str, type] = {F.__name__: F for F in (MainMenuFrame, MessageFrame, PatchSelectionFrame, MarketplacePatcherFrame, ZipPatcherFrame, UpdateCleanerFrame)}
        self.current_frame: Optional[ttk.Frame] = None
        
        self.patch_temp_dir = os.path.join(tempfile.gettempdir(), "AnSPatcher", "patches")
        self.output_temp_dir = os.path.join(tempfile.gettempdir(), "AnSPatcher", "output")
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self.show_frame, "PatchSelectionFrame")

    def on_close(self):
        """Cleans up temporary files and closes the application."""
        robust_cleanup(os.path.dirname(self.patch_temp_dir)) # Clean parent AnSPatcher folder
        self.destroy()

    def show_frame(self, frame_name: str) -> None:
        """Destroys the current frame and shows a new one."""
        if self.current_frame:
            self.current_frame.destroy()
        frame_class = self.frames[frame_name]
        self.current_frame = frame_class(self.container, self)
        self.current_frame.pack(fill="both", expand=True)

    def show_message(self, title: str, message: str, callbacks: Dict[str, Callable]):
        """Shows the special message frame with custom content."""
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = MessageFrame(self.container, self)
        self.current_frame.set_content(title, message, callbacks)
        self.current_frame.pack(fill="both", expand=True)

    def _setup_theme_and_icon(self) -> None:
        """Sets the application locale and window icon."""
        try: locale.setlocale(locale.LC_ALL, 'English_United States.1252')
        except locale.Error: locale.setlocale(locale.LC_ALL, 'C')
        icon_path = resource_path(CONFIG["filenames"]["icon"])
        if os.path.exists(icon_path):
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(u"AnSPatcher")
            self.iconbitmap(icon_path)
            
    def preflight_checks(self) -> bool:
        """Checks for essential files (xdelta and extracted patches)."""
        exe_path = resource_path(os.path.join(CONFIG["paths"]["xdelta_dir"], "exec", CONFIG["executables"]["xdelta"]))
        if not os.path.exists(exe_path):
            self.show_message("Missing Files", f"{CONFIG['executables']['xdelta']} is missing.", {"OK": self.on_close})
            return False
        
        missing_patches = [name for name in CONFIG["patches"].values() if not os.path.exists(os.path.join(self.patch_temp_dir, name))]
        if missing_patches:
            self.show_message("Missing Patches", "The selected zip file is missing required patch files:\n\n" + "\n".join(missing_patches), {"OK": self.on_close})
            return False
        return True

    def load_patch_config(self) -> bool:
        """Loads and applies settings from the patch_config.json file."""
        config_path = os.path.join(self.patch_temp_dir, CONFIG["filenames"]["patch_config"])
        if not os.path.exists(config_path):
            self.show_message("Missing Config", "The patch zip is missing the required 'patch_config.json' file.", {"OK": self.on_close})
            return False
        try:
            with open(config_path, 'r') as f:
                loaded_config = json.load(f)
            if "paths" in loaded_config:
                CONFIG["paths"]["minecraft_uwp"] = loaded_config["paths"].get("minecraft_uwp", CONFIG["paths"]["minecraft_uwp"])
                CONFIG["paths"]["minecraft_beta"] = loaded_config["paths"].get("minecraft_beta", CONFIG["paths"]["minecraft_beta"])
            if "marketplace_pack_stats" in loaded_config:
                CONFIG["marketplace_pack_stats"] = loaded_config["marketplace_pack_stats"]
            return True
        except Exception as e:
            self.show_message("Config Error", f"Failed to load or parse 'patch_config.json':\n{e}", {"OK": self.on_close})
            return False

    def create_hidden_dir(self, path: str):
        """Creates a directory and hides it on Windows."""
        try:
            os.makedirs(path, exist_ok=True)
            ctypes.windll.kernel32.SetFileAttributesW(path, 2) # FILE_ATTRIBUTE_HIDDEN
        except Exception as e:
            print(f"Could not create or hide directory {path}: {e}")

    def run_patch_process(self, source_zip: str, patch_file: str, output_file: str):
        """Wrapper to run the patching process and handle the callback chain for messages."""
        exe_path = resource_path(os.path.join(CONFIG["paths"]["xdelta_dir"], "exec", CONFIG["executables"]["xdelta"]))
        if not os.path.exists(exe_path):
            self.show_message("Error", f"Patcher executable not found:\n{exe_path}", {"OK": lambda: self.show_frame("MainMenuFrame")})
            return
        def patch_thread():
            try:
                command = [exe_path, "-v", "-d", "-s", source_zip, patch_file, output_file]
                subprocess.run(command, check=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                self.after(0, lambda: self.on_patch_success(output_file, source_zip))
            except subprocess.CalledProcessError as e:
                details = e.stderr.strip() if e.stderr else "No additional details from patcher."
                self.after(0, lambda: self.on_patch_failure(f"Patching failed, likely due to a version mismatch.\n\nDetails: {details}", source_zip))
            except Exception as e:
                self.after(0, lambda: self.on_patch_failure(f"An unexpected error occurred:\n{str(e)}", source_zip))
        threading.Thread(target=patch_thread, daemon=True).start()

    def on_patch_success(self, output_file: str, source_zip: str):
        """Callback chain for successful patching with delayed cleanup."""
        def delayed_cleanup():
            def final_cleanup_and_return():
                robust_cleanup(os.path.dirname(source_zip))
                robust_cleanup(self.output_temp_dir)
                self.show_frame("MainMenuFrame")
            
            self.show_message("Waiting for Installation", "Please wait 15 seconds for Minecraft to import the pack. This window will close automatically.", {})
            self.after(15000, final_cleanup_and_return)

        def ask_install():
            callbacks = {
                "Yes": lambda: (os.startfile(output_file, 'open'), delayed_cleanup()),
                "No": lambda: (robust_cleanup(os.path.dirname(source_zip)), robust_cleanup(self.output_temp_dir), self.show_frame("MainMenuFrame"))
            }
            self.show_message("Install Pack?", "The pack has been created and is ready to install. Would you like to open it now?", callbacks)

        self.show_message("🎉 Done!", "Patched successfully!", {"OK": ask_install})

    def on_patch_failure(self, error_message: str, source_zip: str):
        """Callback for failed patching with automatic cleanup."""
        def final_step():
            robust_cleanup(os.path.dirname(source_zip))
            robust_cleanup(self.output_temp_dir)
            self.show_frame("MainMenuFrame")
        callbacks = {"OK": final_step}
        self.show_message("Error", error_message, callbacks)

def main():
    """Main entry point for the application."""
    app = App(themename="superhero")
    app.mainloop()

if __name__ == "__main__":
    main()

