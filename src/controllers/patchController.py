import os
import json
import threading
import hashlib
import tempfile
import shutil
import tkinter as tk
import ttkbootstrap as ttk
from tkinter import messagebox, filedialog
from ..models.configModel import ConfigModel
from ..models.patcherModel import PatcherModel
from ..models.fileSystemModel import FileSystemModel
from ..utils.helpers import resourcePath, showErrorWithCopy

class PatchController:
    """
    Controller handling the main patching flows: Marketplace, Zip, and Custom.
    """
    def __init__(self, config: ConfigModel, patcher: PatcherModel, fs: FileSystemModel, view):
        self.config = config
        self.patcher = patcher
        self.fs = fs
        self.view = view # PatchProgressFrame
        self.cancel_event = threading.Event()
        self.temp_dir = os.path.join(tempfile.gettempdir(), "AnSPatcherFuzed")
        self.is_advanced = False
        self.version_map = {} # Display String -> (ver_key, patch_data_dict)

    def setAdvancedMode(self, enabled: bool):
        self.is_advanced = enabled
        self.view.setAdvancedMode(enabled)
        if enabled:
            # Populate versions
            raw_versions = self.config.config.get("patchVersions", {})
            
            # Helper for SemVer sorting
            def parse_ver(v_str):
                try:
                    clean = v_str.lstrip('v')
                    return tuple(map(int, clean.split('.')))
                except:
                    return (0,)

            sorted_keys = sorted(list(raw_versions.keys()), key=parse_ver, reverse=True)
            
            display_list = ["Auto (Default)"]
            self.version_map = {}

            for ver_key in sorted_keys:
                patches = raw_versions[ver_key]
                # If only one patch version, just show "v1.9"
                # If multiple, show "v1.9 (Patch 1.0)", "v1.9 (Patch 1.1)" etc.
                if len(patches) == 1:
                    lbl = ver_key
                    display_list.append(lbl)
                    self.version_map[lbl] = (ver_key, patches[0])
                else:
                    for p in patches:
                        p_ver = p.get("patchVersion", "?")
                        lbl = f"{ver_key} (Patch {p_ver})"
                        display_list.append(lbl)
                        self.version_map[lbl] = (ver_key, p)
            
            self.view.setVersions(display_list)
            # Default to Auto
            self.view.versionCombo.current(0)



    def _showVersionMismatchDialog(self, detected_ver, target_ver, path, is_manual=False, allow_force=True):
        """
        Shows a custom dialog for resolving version mismatch.
        Returns: 'detected', 'latest', or None (cancel).
        """
        dialog = tk.Toplevel(self.view)
        
        # Context-Aware Text
        title_text = "Selection Mismatch" if is_manual else "Version Mismatch"
        header_text = "Selection Not Found" if is_manual else "Older Version Detected"
        target_label = "Selected:" if is_manual else "Latest:"
        target_btn_text = f"Force Selected ({target_ver})" if is_manual else f"Force Latest ({target_ver})"
        
        dialog.title(title_text)
        dialog.geometry("450x400")
        dialog.resizable(False, False)
        
        # Center Logic
        try:
            dialog.update_idletasks()
            x = self.view.winfo_rootx() + (self.view.winfo_width() // 2) - (450 // 2)
            y = self.view.winfo_rooty() + (self.view.winfo_height() // 2) - (400 // 2)
            dialog.geometry(f"+{x}+{y}")
        except: pass

        container = ttk.Frame(dialog, padding=20)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text=header_text, font=("Segoe UI", 12, "bold"), bootstyle="warning").pack(pady=(0, 15))
        
        info_frame = ttk.Labelframe(container, text="Details", padding=10)
        info_frame.pack(fill="x", pady=5)
        
        grid_opts = {'padx': 5, 'pady': 2, 'sticky': 'w'}
        
        ttk.Label(info_frame, text="Detected:", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, **grid_opts)
        ttk.Label(info_frame, text=f"{detected_ver}", bootstyle="warning").grid(row=0, column=1, **grid_opts)
        
        ttk.Label(info_frame, text=target_label, font=("Segoe UI", 9, "bold")).grid(row=1, column=0, **grid_opts)
        ttk.Label(info_frame, text=f"{target_ver}", bootstyle="success").grid(row=1, column=1, **grid_opts)

        ttk.Label(info_frame, text="Location:", font=("Segoe UI", 9, "bold")).grid(row=2, column=0, **grid_opts)
        
        # Truncate path if too long
        display_path = path
        if len(display_path) > 40:
            display_path = "..." + display_path[-37:]
        ttk.Label(info_frame, text=display_path, font=("Consolas", 8)).grid(row=2, column=1, **grid_opts)

        if is_manual:
            if allow_force:
                msg_text = "The selected version is not installed.\nYou can use the detected version or force your selection."
            else:
                msg_text = "The selected version is not installed.\nPlease use the detected version or browse for the correct folder."
        else:
            msg_text = "It is recommended to update to the latest version.\nHowever, you can choose to proceed with the detected version."

        ttk.Label(container, text=msg_text, justify="center", wraplength=400).pack(pady=15)

        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill="x", pady=10)

        result = {"value": None}

        def on_detected():
            result["value"] = "detected"
            dialog.destroy()
            
        def on_latest():
            result["value"] = "latest"
            dialog.destroy()

        def on_browse():
            result["value"] = "browse"
            dialog.destroy()
            
        def on_cancel():
            result["value"] = None
            dialog.destroy()

        # Buttons
        # Use fill='x' to ensure they have width, and ipady for height
        ttk.Button(btn_frame, text=f"Use Detected ({detected_ver})", command=on_detected, bootstyle="secondary").pack(side="left", expand=True, fill="x", padx=5, ipady=5)
        if allow_force:
            ttk.Button(btn_frame, text=target_btn_text, command=on_latest, bootstyle="success").pack(side="left", expand=True, fill="x", padx=5, ipady=5)
        ttk.Button(btn_frame, text="Browse Folder...", command=on_browse, bootstyle="info").pack(side="left", expand=True, fill="x", padx=5, ipady=5)
        
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        dialog.transient(self.view)
        dialog.grab_set()
        self.view.wait_window(dialog)
        
        return result["value"]

    def _showNotFoundDialog(self):
        """
        Shows a dialog when the pack is not found, offering to Browse.
        Returns: 'browse' or None.
        """
        dialog = tk.Toplevel(self.view)
        dialog.title("Pack Not Found")
        dialog.geometry("400x250")
        dialog.resizable(False, False)
        
        # Center Logic
        try:
            dialog.update_idletasks()
            x = self.view.winfo_rootx() + (self.view.winfo_width() // 2) - (400 // 2)
            y = self.view.winfo_rooty() + (self.view.winfo_height() // 2) - (250 // 2)
            dialog.geometry(f"+{x}+{y}")
        except: pass

        container = ttk.Frame(dialog, padding=20)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="Pack Not Found", font=("Segoe UI", 12, "bold"), bootstyle="danger").pack(pady=(0, 15))
        
        msg = "Could not automatically find 'Actions & Stuff' in the standard location.\n\nWould you like to browse for the folder manually?"
        ttk.Label(container, text=msg, justify="center", wraplength=350).pack(pady=10)

        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill="x", pady=20)

        result = {"value": None}

        def on_browse():
            result["value"] = "browse"
            dialog.destroy()
            
        def on_cancel():
            result["value"] = None
            dialog.destroy()
            
        ttk.Button(btn_frame, text="Browse Folder...", command=on_browse, bootstyle="info").pack(side="left", expand=True, fill="x", padx=5, ipady=5)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel, bootstyle="secondary").pack(side="left", expand=True, fill="x", padx=5, ipady=5)
        
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        dialog.transient(self.view)
        dialog.grab_set()
        self.view.wait_window(dialog)
        return result["value"]

    def _log(self, message: str):
        """Thread-safe logging helper."""
        if self.is_advanced:
            # Marshal to main thread
            self.view.after(0, lambda: self.view.appendLog(message))

    def startMarketplacePatch(self):
        # self.view is PatchProgressFrame
        patch_frame = self.view
        
        # Legacy: We rely on AppController calling configureView BEFORE this.
        # We just reset status and start.

        patch_frame.setStatus("Searching for Marketplace Content...")
        patch_frame.setProgress(0, 'indeterminate')
        patch_frame.setActionState("disabled")
        patch_frame.hideSecondaryAction()
        self.cancel_event.clear()
        threading.Thread(target=self._marketplaceSearchWorker, daemon=True).start()

    def _marketplaceSearchWorker(self, target_patch_data: dict = None, target_ver_key: str = None):
        paths_to_check = [
             os.path.join(os.path.expandvars(self.config.get_path("minecraftBedrock")), "premium_cache", "resource_packs"),
             os.path.join(os.path.expandvars(self.config.get_path("minecraftBedrockPreview")), "premium_cache", "resource_packs"),
             os.path.join(os.path.expandvars(self.config.get_path("minecraftUwp")), "premium_cache", "resource_packs"),
             os.path.join(os.path.expandvars(self.config.get_path("minecraftUwpPreview")), "premium_cache", "resource_packs")
        ]

        target_versions = self.config.config["patchVersions"]
        found_folder = None
        detected_version_data = None
        detected_version_key = None
        detection_method = 'unknown'
        
        candidates = []

        # Helper: Calculate SHA256 of a file
        def calculate_file_hash(filepath):
            sha256_hash = hashlib.sha256()
            try:
                with open(filepath, "rb") as f:
                    for byte_block in iter(lambda: f.read(4096), b""):
                        sha256_hash.update(byte_block)
                return sha256_hash.hexdigest().lower()
            except:
                return None

        # Helper: Check Manifest for Indicators
        def check_manifest(folder_path):
            manifest_path = os.path.join(folder_path, "manifest.json")
            if not os.path.exists(manifest_path): return False
            try:
                with open(manifest_path, 'r', encoding='utf-8', errors='ignore') as f:
                    data = json.load(f)
                    
                    # 1. Check UUID
                    # Using known A&S UUID
                    target_uuid = "22ed17a6-ea7c-5ccd-93b4-b90e86ce0046"
                    
                    # Check header (sometimes UUID is there)
                    if data.get("header", {}).get("uuid") == target_uuid:
                        return True

                    # Check modules
                    for module in data.get("modules", []):
                        if module.get("uuid") == target_uuid:
                            return True
                        # Check description for "Oreville Studios"
                        if "Oreville Studios" in module.get("description", ""):
                            return True
                            
                    # Check metadata authors
                    authors = data.get("metadata", {}).get("authors", [])
                    for author in authors:
                        if "Oreville Studios" in author:
                            return True

            except:
                pass
            return False

        # Helper: Check Language File and extract version
        def check_lang_file(folder_path):
            lang_path = os.path.join(folder_path, "texts", "en_US.lang")
            if not os.path.exists(lang_path): return False, None
            
            extracted_version = None
            try:
                # Limit read size to avoid memory issues with huge files (100KB is plenty for lang file)
                with open(lang_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(102400) 
                    if "pack.name=Actions & Stuff" in content:
                        # Try to extract version: "pack.name=Actions & Stuff 1.9"
                        for line in content.splitlines():
                            if line.startswith("pack.name="):
                                parts = line.split("Actions & Stuff")
                                if len(parts) > 1:
                                    extracted_version = parts[1].strip()
                        return True, extracted_version
            except:
                pass
            return False, None

        self._log("Starting Marketplace Search...")
        
        for path in paths_to_check:
            if self.cancel_event.is_set(): return
            
            self._log(f"Checking root path: {path}")
            if not os.path.exists(path): 
                self._log("  -> Path does not exist. Skipping.")
                continue

            try:
                folders = os.listdir(path)
                self._log(f"  -> Found {len(folders)} subfolders.")
                
                for folder in folders:
                    full_path = os.path.join(path, folder)
                    if not os.path.isdir(full_path): continue

                    self._log(f"    Scanning subfolder: {folder}")

                    # --- Multi-Level Verification ---
                    score = 0
                    
                    # 1. Manifest Check
                    is_manifest_match = check_manifest(full_path)
                    self._log(f"      [Manifest Check]: {'PASS' if is_manifest_match else 'FAIL'}")
                    if is_manifest_match: score += 1
                    
                    # 2. Logo Check (SHA256)
                    latest_ver_data = self.config.get_latest_version_data()
                    target_logo_hash = "d4d088d108cd635116215134ad40e97272f9fbe17ead8a03ba4155b1f58fecd4" # Default fallback (v1.9)
                    
                    if latest_ver_data and "validation" in latest_ver_data:
                        target_logo_hash = latest_ver_data["validation"].get("logo_hash", target_logo_hash)
                        
                    # OVERRIDE: If manual selection passed, use ITS logo hash
                    if target_patch_data and "validation" in target_patch_data:
                        target_logo_hash = target_patch_data["validation"].get("logo_hash", target_logo_hash)

                    logo_path = os.path.join(full_path, "pack_icon.png")
                    is_logo_match = False
                    if os.path.exists(logo_path):
                        current_hash = calculate_file_hash(logo_path)
                        match = current_hash == target_logo_hash
                        self._log(f"      [Logo Check]: {'Match' if match else 'Mismatch'} (Hash: {current_hash[:8]}...)")
                        if match:
                            is_logo_match = True
                            score += 1
                    else:
                         self._log("      [Logo Check]: No pack_icon.png found.")
                        
                    # 3. Lang Check
                    is_lang_match, lang_version_str = check_lang_file(full_path)
                    self._log(f"      [Lang Check]: {'PASS' if is_lang_match else 'FAIL'} (Detected: {lang_version_str})")
                    if is_lang_match: score += 1

                    # 4. Stats Check (Version Specific)
                    curr_stats = self.fs.getFolderStats(full_path)
                    self._log(f"      [Stats Check]: Found Files={curr_stats[0]}, Dirs={curr_stats[1]}")
                    
                    stats_match_version_key = None
                    stats_match_data = None
                    
                    # Iterate Latest -> Oldest (STRICT SEMVER SORT)
                    def parse_ver_local(v_str):
                        try:
                            clean = v_str.lstrip('v')
                            return tuple(map(int, clean.split('.')))
                        except:
                            return (0,)
                            
                    sorted_ver_keys = sorted(list(target_versions.keys()), key=parse_ver_local, reverse=True)
                    
                    # LOGIC CHANGE: If user selected a specific version manually, check THAT version first!
                    if target_ver_key and target_ver_key in sorted_ver_keys:
                        # Move to front
                        sorted_ver_keys.remove(target_ver_key)
                        sorted_ver_keys.insert(0, target_ver_key)
                        self._log(f"      [Stats Check] Prioritizing manual selection: {target_ver_key}")

                    for ver_key in sorted_ver_keys:
                        patch_list = target_versions[ver_key]
                        for ver_data in patch_list:
                             stats = ver_data.get("stats")
                             if stats and curr_stats[0] == stats["files"] and curr_stats[1] == stats["dirs"]:
                                 stats_match_version_key = ver_key
                                 stats_match_data = ver_data
                                 self._log(f"      [Stats Check] Matched version: {ver_key}")
                                 break
                        
                        if stats_match_version_key: break
                    
                    if stats_match_version_key:
                        score += 1
                    else:
                        self._log("      [Stats Check] No version configuration matched folder stats.")

                    # FINAL DECISION LOGIC
                    # We need at least 2 indicators to confirm it is A&S
                    if score >= 2:
                        self._log(f"Pack Candidate Found! Score: {score}/4")
                        
                        # Determine Version for this candidate
                        c_version_key = None
                        c_version_data = None
                        c_method = 'unknown'

                        # Case C: Lang file provided a version string (e.g. "1.9")
                        if lang_version_str:
                             potential_key = f"v{lang_version_str}"
                             if potential_key in target_versions:
                                 c_version_key = potential_key
                                 c_version_data = target_versions[potential_key][0]
                                 c_method = 'lang_string'
                             else:
                                 self._log(f"  -> Candidate Version string '{lang_version_str}' unknown.")

                        # Case B: Stats matched a known version
                        elif stats_match_version_key:
                            c_version_data = stats_match_data
                            c_version_key = stats_match_version_key
                            c_method = 'stats'
                        
                        # Case D: Fallback to Latest
                        if not c_version_data and target_versions:
                             first_key = next(iter(target_versions))
                             c_version_data = target_versions[first_key][0]
                             c_version_key = first_key
                             c_method = 'fallback_latest'
                        
                        candidates.append({
                            'path': full_path,
                            'version_key': c_version_key,
                            'version_data': c_version_data,
                            'method': c_method,
                            'score': score
                        })
                        self._log(f"  -> Helper: Candidate added. Version: {c_version_key}")

                    else:
                         self._log(f"    -> Verification Failed. Score: {score}")
            
            except OSError as e:
                self._log(f"Error scanning path: {e}")
                continue

        # SELECT BEST CANDIDATE
        if candidates:
            self._log(f"Found {len(candidates)} candidates. Selecting best...")
            
            # Sort candidates by Version (Hightest First)
            # Re-use parse_ver_local
            def candidate_sort_key(c):
                v_key = c['version_key']
                return parse_ver_local(v_key)

            candidates.sort(key=candidate_sort_key, reverse=True)
            
            best = candidates[0]
            found_folder = best['path']
            detected_version_key = best['version_key']
            detected_version_data = best['version_data']
            detection_method = best['method']
            
            self._log(f"Selected Candidate: {found_folder}")
            self._log(f"Detected Version: {detected_version_key} (Method: {detection_method})")
            
        else:
            self._log("No valid Actions & Stuff pack found.")

        if not found_folder:
            # New Logic: Prompt to Browse
            def prompt_not_found():
                choice = self._showNotFoundDialog()
                if choice == 'browse':
                    new_path = filedialog.askdirectory(title="Select Actions & Stuff Folder")
                    if new_path:
                        return new_path
                return None
            
            # Need to run dialog on main thread and get result?
            # actually we are in a worker thread. We can't block main thread easily from here without queue.
            # But we are using .transient() .wait_window() which REQUIRES main thread execution.
            # We must schedule it.
            
            # Solution: We can't easily wait for result in this worker thread structure without refactoring to passing callback.
            # BUT, we can schedule a specific "Retry/Manual" handler.
            
            # Simplified approach: Marshal the check to main thread, AND the subsequent logic.
            # Or just update UI to show "Not Found" with a Browse button?
            
            # Let's try to keeping it linear by using a shared mutable, but locking UI is tricky.
            # Better: Launch a separate "Ask User" procedure on main thread that *calls back* into the workflow.
            
            # Actually, `confirmVersionAndProceed` IS the next step. If we don't have a folder, we can't call it.
            # So we should call a "HandleNotFound" method on main thread.
            
            self.view.after(0, self._handleNotFoundOnMain)
            return
            
        self.view.after(0, lambda: self.view.setStatus("Found pack."))

        # INTERACTIVE SELECTION LOGIC
        def confirmVersionAndProceed():
            nonlocal found_folder # Fix for UnboundLocalError
            
            # 1. Determine "Latest" available version key
            # Assuming keys are like "v1.9", "v1.8": sort descending
            available_keys = sorted(target_versions.keys(), reverse=True)
            latest_key = available_keys[0] if available_keys else None
            
            target_key = detected_version_key

            # Warn about stats mismatch if applicable
            if detection_method == 'lang':
                messagebox.showinfo("Warning", "Folder statistics did not match known configurations.\nHowever, the Language file confirmed this is Actions & Stuff.\nProceeding with detected version logic.")

            # STEP A: Version Selection (Detailed vs Latest)
            
            # Logic Update: If user Manually Selected a version, compare it with DETECTED version.
            # If they differ, trigger the mismatch dialog to ask: "Use Detected (1.9)" or "Force Selected (1.7)"?
            
            if target_ver_key:
                 # Manual Mode Check
                 if detected_version_key != target_ver_key:
                     self._log(f"DEBUG: Manual Selection Mismatch. Detected: {detected_version_key}, Selected: {target_ver_key}")
                     # Pass is_manual=True
                     choice = self._showVersionMismatchDialog(detected_version_key, target_ver_key, found_folder, is_manual=True, allow_force=False)
                     
                     if choice == 'latest': 
                         target_key = target_ver_key
                         self._log(f"User forced selected version: {target_key}")
                     elif choice == 'detected':
                         target_key = detected_version_key
                         self._log(f"User switched to detected version: {target_key}")
                     elif choice == 'browse':
                         new_path = filedialog.askdirectory(title="Select Actions & Stuff Folder")
                         if new_path:
                             found_folder = new_path
                             target_key = target_ver_key
                             self._log(f"User manually selected folder: {found_folder}")
                         else:
                             self.view.onBack()
                             return
                     else: # Cancel
                         self.view.onBack()
                         return
                 else:
                     # Match!
                     self._log(f"Manual selection verified matches stats/lang.")
            
            elif detected_version_key != latest_key:
                # Normal Auto logic (Older detected)
                # Pass is_manual=False (default)
                choice = self._showVersionMismatchDialog(detected_version_key, latest_key, found_folder, is_manual=False)

                if choice == 'latest':
                    messagebox.showinfo("Notice", "You have chosen to force the Latest Patch on an older Pack version.\nThis is allowed but may have unexpected results.")
                    target_key = latest_key
                    self._log(f"User forced latest version: {target_key}")
                elif choice == 'detected':
                    self._log(f"User kept detected version: {target_key}")
                elif choice == 'browse':
                     new_path = filedialog.askdirectory(title="Select Actions & Stuff Folder")
                     if new_path:
                         found_folder = new_path
                         # If browsing in auto mode, what version do we target? 
                         # Prob safe to stick to 'latest' or re-detect? 
                         # Let's assume they want the latest patch if they browse manually in auto mode.
                         target_key = latest_key
                         self._log(f"User manually selected folder (Auto Mode): {found_folder}")
                     else:
                         self.view.onBack()
                         return
                else:
                    # Cancel
                    self.view.onBack()
                    return

            # Handle unknown version (detected but not in config)
            if target_key not in target_versions:
                 if messagebox.askyesno("Unknown Version", f"Detected version '{target_key}' has no known patches.\nTry using the latest patch ({latest_key})?"):
                     target_key = latest_key
                 else:
                     self.view.onBack()
                     return

            # STEP B: Patch Selection for Target Version
            # target_versions[target_key] is a LIST of patch dicts
            patch_options = target_versions[target_key]
            final_patch_data = patch_options[0] # Default to first (latest due to sort)

            if len(patch_options) > 1:
                # Create a selection list
                # Format: "v1.1" 
                options_map = {f"v{p.get('patchVersion', '?')}": p for p in patch_options}
                options_labels = list(options_map.keys())

                def ask_user_choice():
                    choice = tk.StringVar(value=options_labels[0])
                    dialog = tk.Toplevel(self.view)
                    dialog.title("Select Patch Version")
                    dialog.geometry("300x180")
                    dialog.resizable(False, False)
                    try:
                        dialog.update_idletasks()
                        x = self.view.winfo_rootx() + 50
                        y = self.view.winfo_rooty() + 50
                        dialog.geometry(f"+{x}+{y}")
                    except: pass

                    ttk.Label(dialog, text=f"Multiple patches found for {target_key}.\nPlease select a version:", justify="center").pack(pady=15)
                    
                    cbo = ttk.Combobox(dialog, values=options_labels, textvariable=choice, state="readonly")
                    cbo.pack(pady=5, padx=20, fill="x")
                    cbo.current(0)

                    result = {"value": None}

                    def on_ok():
                        result["value"] = choice.get()
                        dialog.destroy()
                    
                    ttk.Button(dialog, text="Select", command=on_ok, bootstyle="success").pack(pady=20)
                    
                    dialog.transient(self.view)
                    dialog.grab_set()
                    self.view.wait_window(dialog)
                    return result["value"]

                selected_label = ask_user_choice()
                if selected_label and selected_label in options_map:
                    final_patch_data = options_map[selected_label]
                    self._log(f"User selected patch: {selected_label}")

            # Proceed
            self._prepareAndPatch(found_folder, final_patch_data)

        # Marshal to main thread
        self.view.after(0, confirmVersionAndProceed)

    def _prepareAndPatch(self, found_folder, version_data):
        self._log(f"Preparing to patch using Patch Version: {version_data.get('patchVersion', 'Unknown')}")
        
        # Prepare temp directory
        os.makedirs(self.temp_dir, exist_ok=True)
        temp_zip = os.path.join(self.temp_dir, "temp_vanilla.zip")

        self.view.after(0, lambda: self.view.setStatus("Backing up Pack..."))
        self.view.after(0, lambda: self.view.setProgress(0, 'indeterminate'))
        
        # Spawn thread for compression
        threading.Thread(target=self._compressionWorker, args=(found_folder, temp_zip, version_data), daemon=True).start()

    def _compressionWorker(self, found_folder, temp_zip, version_data):
        self._log("Starting compression/backup...")

        # IMPORTANT: Use snake_case arguments for new API
        success = self.fs.compressDeterministic(
            folder_path=found_folder,
            output_zip=temp_zip,
            cancel_event=self.cancel_event,
            log_callback=self._log
        )

        if not success or self.cancel_event.is_set():
            return

        self.view.after(0, lambda: self._onReadyToPatch(temp_zip, "marketplace", version_data))

    def startZipPatch(self):
        patch_frame = self.view
        
        # Mode is already set to 'zip' or 'custom' by configureView if manual.
        # But if we want to allow switching, we should just let UI be.
        
        # If manual mode, user might want to choose "Zip" or "Custom" via radio.
        # If current mode selected is 'zip', and no file selected, we just wait?
        # Actually in 'manual' view, we have a "Start" button which triggers 'startAdvancedLogic'.
        
        # We need to wire the "Start" button for Manual Mode.
        patch_frame.setActionCommand(self.startAdvancedLogic, "Start Patch")
        patch_frame.setActionState("normal")
        patch_frame.hideSecondaryAction()
        patch_frame.setStatus("Ready. Select options above.")

    def _zipProcessWorker(self, file_path: str, target_patch_data: dict = None):
        # pylint: disable=too-many-locals
        extract_dir = os.path.join(self.temp_dir, "extracted")
        self.fs.robustCleanup(extract_dir)
        os.makedirs(extract_dir, exist_ok=True)

        try:
            shutil.unpack_archive(file_path, extract_dir, format="zip")

            # Smart Folder Detection: If zip contains single folder, move content up
            items = os.listdir(extract_dir)
            if len(items) == 1 and os.path.isdir(os.path.join(extract_dir, items[0])):
                single_dir = os.path.join(extract_dir, items[0])
                for item in os.listdir(single_dir):
                    shutil.move(os.path.join(single_dir, item), extract_dir)
                os.rmdir(single_dir)

            # Clean unwanted files
            for root, dirs, files in os.walk(extract_dir):
                for f in files:
                    if f in self.config.config["filesToRemove"]:
                        os.remove(os.path.join(root, f))
                for d in list(dirs):
                    if d in self.config.config["dirsToRemove"]:
                        shutil.rmtree(os.path.join(root, d))
                        dirs.remove(d)

            # FORCE MANIFEST INJECTION (Standardization)
            should_apply_manifest = [True]
            
            if should_apply_manifest[0]:
                manifest_path = resourcePath("assets/resources/manifest.json")
                if os.path.exists(manifest_path):
                    shutil.copyfile(manifest_path, os.path.join(extract_dir, "manifest.json"))
            # -----------------------------

            normalized_zip = os.path.join(self.temp_dir, "normalized.zip")
            self._log("Starting deterministic compression (this may take a while)...")

            # Use new API args
            self.fs.compressDeterministic(
                folder_path=extract_dir,
                output_zip=normalized_zip,
                cancel_event=self.cancel_event,
                log_callback=self._log
            )
            
            detected_version_data = target_patch_data
            if detected_version_data:
                self._log(f"Using selected version configuration.")
                # Verify content
                p_ver = detected_version_data.get('patchVersion', 'Unknown')
                self._log(f"DEBUG: ZipWorker using patch version: {p_ver}")
            else:
                 self._log("DEBUG: ZipWorker received NO target data.")

            self.view.after(0, lambda: self._onReadyToPatch(normalized_zip, "zip", detected_version_data))

        except Exception as e:
            self.view.after(0, lambda: messagebox.showerror("Error", f"Failed to process zip: {e}"))
            self.view.after(0, self.view.onBack)

    def _onReadyToPatch(self, source_zip: str, mode: str, detected_version_data: dict = None):
        self.view.setStatus("Ready to Patch.")
        self.view.setProgress(100, 'determinate')

        def runPatchAction():
            if messagebox.askyesno("Clean Update?", "Do you want to clean old versions of the pack before patching?\n(Recommended for updates)"):
                self.view.setStatus("Cleaning old versions...")
                self.view.setStatus("Cleaning old versions...")
                
                # Scan ALL possible paths (Mirrors CleanController logic)
                pathsToScan = [
                    os.path.join(os.path.expandvars(self.config.get_path("minecraftUwp")), "games", "com.mojang"),
                    os.path.join(os.path.expandvars(self.config.get_path("minecraftUwpPreview")), "games", "com.mojang"),
                    os.path.join(os.path.expandvars(self.config.get_path("minecraftBedrock")), "games", "com.mojang"),
                    os.path.join(os.path.expandvars(self.config.get_path("minecraftBedrock")), "Users", "Shared", "games", "com.mojang"),
                    os.path.join(os.path.expandvars(self.config.get_path("minecraftBedrockPreview")), "games", "com.mojang"),
                ]
                
                prefixes = self.config.get_cleanup_prefixes()
                
                for basePath in pathsToScan:
                    if not os.path.exists(basePath): continue
                    
                    rpPath = os.path.join(basePath, "resource_packs")
                    found = self.fs.scanDirectory(rpPath, prefixes)
                    for f in found:
                        self.fs.robustCleanup(f)
                        self._log(f"Cleaned: {os.path.basename(f)}")

            patch_type = "marketplaceEncrypted" if mode == "marketplace" else "zipDecrypted"
            patch_file_relative = self.config.get_patch_path(patch_type)

            # Fallback: If no version detected/selected, use the LATEST available version
            current_version_data = detected_version_data
            if not current_version_data:
                self._log("No specific version detected. Defaulting to latest version.")
                current_version_data = self.config.get_latest_version_data()
                if current_version_data:
                     self._log(f"Fallback Version Config: Patch {current_version_data.get('patchVersion', '?')}")
            else:
                self._log(f"DEBUG: Ready to patch with provided version data: {current_version_data.get('patchVersion', '?')}")

            # Use detected/fallback patch file if available
            if current_version_data and "patches" in current_version_data:
                key = "encrypted" if mode == "marketplace" else "decrypted"
                if key in current_version_data["patches"]:
                    patch_file_relative = current_version_data["patches"][key]

            patch_file = resourcePath(patch_file_relative)

            if self.is_advanced:
                custom = self.view.patchVar.get()
                if custom and os.path.exists(custom):
                    patch_file = custom

            self.view.setActionState("disabled")
            self.view.setStatus("Patching...")
            self.view.setProgress(0, 'indeterminate')
            threading.Thread(target=self._patchWorker, args=(source_zip, patch_file), daemon=True).start()

        self.view.setActionCommand(runPatchAction)
        self.view.setActionState("normal")

    def _patchWorker(self, source_zip: str, patch_file: str):
        output_file = os.path.join(self.temp_dir, self.config.get_filename("finalMcPack"))
        xdelta = self.config.get_executable("xdelta")
        xdelta_params = resourcePath(xdelta)

        self._log("Starting XDelta patch...")

        # Explicitly log the patch file as requested
        self._log("-" * 40)
        self._log(f"APPLYING PATCH FILE: {os.path.basename(patch_file)}")
        self._log(f"Path: {patch_file}")
        self._log("-" * 40)

        # New API Call
        success, msg = self.patcher.runPatch(
            xdelta_path=xdelta_params,
            source_zip=source_zip,
            patch_file=patch_file,
            output_file=output_file,
            log_callback=self._log
        )

        if success:
            # CLEANUP: Remove intermediate files so only the .mcpack remains
            try:
                target_name = os.path.basename(output_file)
                for item in os.listdir(self.temp_dir):
                    if item != target_name:
                        item_path = os.path.join(self.temp_dir, item)
                        self.fs.robustCleanup(item_path)
            except Exception as e:
                self._log(f"Warning: Cleanup failed: {e}")

            self.view.after(0, lambda: self.view.setStatus("Patch Successful!"))

            def install():
                self._log("Installing pack...")
                success, result = self.patcher.createMcPack(output_file)
                if success:
                    self._log(f"launched {result}")
                else:
                    self._log(f"Install failed: {result}")
                    showErrorWithCopy("Install Failed", f"Could not launch pack:\n{result}", self.view)

            self.view.after(0, lambda: self.view.setActionCommand(install, "Install Pack"))
            self.view.after(0, lambda: self.view.setActionState("normal"))
            
            if self.is_advanced:
                 def openFolder():
                     try:
                         folder = os.path.dirname(output_file)
                         os.startfile(folder)
                     except: pass
                 self.view.after(0, lambda: self.view.setSecondaryAction(openFolder, "Open Folder"))

            self.view.after(0, lambda: messagebox.showinfo("Success", "Patch created successfully! Click Install to launch Minecraft."))
        else:
            self.view.after(0, lambda: showErrorWithCopy("Patch Failed", msg, self.view))
            # self.view.after(0, self.view.onBack) # DISABLED FOR DEBUGGING

    def startAdvancedLogic(self):
        patch_frame = self.view
        mode = patch_frame.modeVar.get()
        
        # Get selected version
        selection = patch_frame.versionVar.get()
        target_patch_data = None
        target_ver_key = None
        
        if selection and selection in self.version_map:
            target_ver_key, target_patch_data = self.version_map[selection]

        self._log(f"DEBUG: Advanced Selection: '{selection}'")
        self._log(f"DEBUG: Target Key: {target_ver_key}")
        if target_patch_data:
            self._log(f"DEBUG: Target Data found for {target_ver_key}")
        else:
            self._log(f"DEBUG: No Target Data found (Auto/None)")

        patch_frame.setActionState("disabled")
        patch_frame.hideSecondaryAction()
        self.cancel_event.clear()

        if mode == "marketplace":
            lbl = target_ver_key if target_ver_key else 'Auto'
            patch_frame.setStatus(f"Searching for Marketplace Content ({lbl})...")
            patch_frame.setProgress(0, 'indeterminate')
            threading.Thread(target=self._marketplaceSearchWorker, args=(target_patch_data, target_ver_key), daemon=True).start()

        elif mode == "zip":
            file_path = filedialog.askopenfilename(filetypes=[("Minecraft Packs", "*.zip *.mcpack")], title="Select Pack")
            if not file_path:
                patch_frame.setActionState("normal")
                return

            lbl = target_ver_key if target_ver_key else 'Auto'
            patch_frame.setStatus(f"Processing Zip ({lbl})...")
            patch_frame.setProgress(0, 'indeterminate')
            threading.Thread(target=self._zipProcessWorker, args=(file_path, target_patch_data), daemon=True).start()

        elif mode == "custom":
            src = patch_frame.srcVar.get()
            tgt = patch_frame.tgtVar.get()
            patch = patch_frame.patchVar.get()

            if not src or not tgt or not patch:
                showErrorWithCopy("Error", "Please fill all fields.", self.view)
                patch_frame.setActionState("normal")
                return

            self._log("Starting Custom Patch...")
            threading.Thread(target=self._customProcessWorker, args=(src, tgt, patch), daemon=True).start()

    def _customProcessWorker(self, src, tgt, patch_file):
        # 1. Prepare Source
        os.makedirs(self.temp_dir, exist_ok=True)
        temp_zip = os.path.join(self.temp_dir, "custom_source.zip")

        if os.path.isdir(src):
            self._log(f"Compressing source: {src}")
            self.fs.compressDeterministic(
                folder_path=src,
                output_zip=temp_zip,
                cancel_event=self.cancel_event,
                log_callback=self._log
            )
        else:
            self._log(f"Using source zip: {src}")
            shutil.copyfile(src, temp_zip)

        if self.cancel_event.is_set(): return

        # 2. Patch
        patch_abs = os.path.abspath(patch_file) if not os.path.isabs(patch_file) else patch_file

        # 3. Run Patch
        try:
            xdelta = self.config.get_executable("xdelta")
            xdelta_params = resourcePath(xdelta)

            output_abs = os.path.abspath(tgt)

            self._log(f"Applying patch: {patch_abs}")
            success, msg = self.patcher.runPatch(
                xdelta_path=xdelta_params,
                source_zip=temp_zip,
                patch_file=patch_abs,
                output_file=output_abs,
                log_callback=self._log
            )

            if success:
                self.view.after(0, lambda: self.view.setStatus("Patch Successful!"))

                def install():
                    self._log("Installing pack...")
                    success, result = self.patcher.createMcPack(output_abs)
                    if success:
                        self._log(f"launched {result}")
                    else:
                        self._log(f"Install failed: {result}")
                        showErrorWithCopy("Install Failed", f"Could not launch pack:\n{result}", self.view)

                patch_frame = self.view
                self.view.after(0, lambda: patch_frame.setActionCommand(install, "Install Pack"))
                self.view.after(0, lambda: patch_frame.setActionState("normal"))
                self.view.after(0, lambda: patch_frame.setProgress(100, 'determinate'))
                self.view.after(0, lambda: messagebox.showinfo("Success", "Patch created successfully! Click Install to launch."))

            else:
                self.view.after(0, lambda: showErrorWithCopy("Patch Failed", msg, self.view))
                self.view.after(0, lambda: self.view.setActionState("normal"))

        except Exception as e:
            self.view.after(0, lambda: showErrorWithCopy("Error", str(e), self.view))
