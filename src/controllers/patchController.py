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
            sorted_keys = sorted(list(raw_versions.keys()), reverse=True)
            
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
             os.path.join(os.path.expandvars(self.config.get_path("minecraftUwp")), "premium_cache", "resource_packs"),
             os.path.join(os.path.expandvars(self.config.get_path("minecraftUwpPreview")), "premium_cache", "resource_packs"),
             os.path.join(os.path.expandvars(self.config.get_path("minecraftBedrock")), "premium_cache", "resource_packs"),
             os.path.join(os.path.expandvars(self.config.get_path("minecraftBedrockPreview")), "premium_cache", "resource_packs")
        ]

        target_versions = self.config.config["patchVersions"]
        found_folder = None
        detected_version_data = None
        detected_version_key = None
        detection_method = 'unknown'
        
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
                with open(lang_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
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

        for path in paths_to_check:
            if self.cancel_event.is_set(): return
            if not os.path.exists(path): continue

            try:
                for folder in os.listdir(path):
                    full_path = os.path.join(path, folder)
                    if not os.path.isdir(full_path): continue

                    # --- Multi-Level Verification ---
                    score = 0
                    
                    # 1. Manifest Check
                    is_manifest_match = check_manifest(full_path)
                    if is_manifest_match: score += 1
                    
                    # 2. Logo Check (SHA256)
                    # We need a reference hash. We can get it from the latest version config or use a hardcoded fallback.
                    # Ideally, validation data is in the config.
                    
                    # Get latest verification data for reference
                    latest_ver_data = self.config.get_latest_version_data()
                    target_logo_hash = "d4d088d108cd635116215134ad40e97272f9fbe17ead8a03ba4155b1f58fecd4" # Default fallback (v1.9)
                    
                    if latest_ver_data and "validation" in latest_ver_data:
                        target_logo_hash = latest_ver_data["validation"].get("logo_hash", target_logo_hash)

                    logo_path = os.path.join(full_path, "pack_icon.png")
                    is_logo_match = False
                    if os.path.exists(logo_path):
                        current_hash = calculate_file_hash(logo_path)
                        if current_hash == target_logo_hash:
                            is_logo_match = True
                            score += 1
                        
                    # 3. Lang Check
                    is_lang_match, lang_version_str = check_lang_file(full_path)
                    if is_lang_match: score += 1

                    # 4. Stats Check (Version Specific)
                    curr_stats = self.fs.getFolderStats(full_path)
                    stats_match_version_key = None
                    stats_match_data = None
                    
                    # Iterate Latest -> Oldest
                    for ver_key, patch_list in target_versions.items():
                        for ver_data in patch_list:
                             stats = ver_data.get("stats")
                             if stats and curr_stats[0] == stats["files"] and curr_stats[1] == stats["dirs"]:
                                 stats_match_version_key = ver_key
                                 stats_match_data = ver_data
                                 break
                        if stats_match_version_key: break
                    
                    if stats_match_version_key:
                        score += 1

                    # FINAL DECISION LOGIC
                    # We need at least 2 indicators to confirm it is A&S
                    if score >= 2:
                        self._log(f"Pack Detected! Score: {score}/4 (Manifest={is_manifest_match}, Logo={is_logo_match}, Lang={is_lang_match}, Stats={bool(stats_match_version_key)})")
                        found_folder = full_path
                        
                        # Determine Version
                        
                        # Case A: User selected specific version in Manual Mode
                        if target_patch_data:
                            detected_version_data = target_patch_data
                            detected_version_key = target_ver_key
                            detection_method = 'forced'
                            self._log(f"  -> Using selected version configuration.")
                        
                        # Case B: Stats matched a known version
                        elif stats_match_version_key:
                            detected_version_data = stats_match_data
                            detected_version_key = stats_match_version_key
                            detection_method = 'stats'
                            self._log(f"  -> Identified Version: {detected_version_key} (via Stats)")
                            
                        # Case C: Lang file provided a version string (e.g. "1.9")
                        elif lang_version_str:
                             # Try to map "1.9" to "v1.9" key
                             potential_key = f"v{lang_version_str}"
                             if potential_key in target_versions:
                                 detected_version_key = potential_key
                                 detected_version_data = target_versions[potential_key][0] # use latest patch for that version
                                 detection_method = 'lang_string'
                                 self._log(f"  -> Identified Version: {detected_version_key} (via Language File)")
                             else:
                                 # Version string found but not in config -> Unknown new version?
                                 self._log(f"  -> Version string found '{lang_version_str}' but no config match.")
                        
                        # Case D: Fallback to Latest
                        if not detected_version_data and target_versions:
                             first_key = next(iter(target_versions))
                             detected_version_data = target_versions[first_key][0]
                             detected_version_key = first_key
                             detection_method = 'fallback_latest'
                             self._log(f"  -> Version inferred (Fallback to Latest): {first_key}")

                        break # Stop searching candidate folders
            
            except OSError:
                continue
            if found_folder: break

        if not found_folder:
            self.view.after(0, lambda: messagebox.showerror("Error", "Could not find Actions & Stuff in premium_cache.\nMake sure you have downloaded it from the Marketplace."))
            self.view.after(0, self.view.onBack)
            return

        self.view.after(0, lambda: self.view.setStatus("Found pack."))

        # INTERACTIVE SELECTION LOGIC
        def confirmVersionAndProceed():
            # 1. Determine "Latest" available version key
            # Assuming keys are like "v1.9", "v1.8": sort descending
            available_keys = sorted(target_versions.keys(), reverse=True)
            latest_key = available_keys[0] if available_keys else None
            
            target_key = detected_version_key

            # Warn about stats mismatch if applicable
            if detection_method == 'lang':
                messagebox.showinfo("Warning", "Folder statistics did not match known configurations.\nHowever, the Language file confirmed this is Actions & Stuff.\nProceeding with detected version logic.")

            # STEP A: Version Selection (Detailed vs Latest)
            if detected_version_key != latest_key:
                msg = f"Version Mismatch Detected.\n\nDetected Installed: {detected_version_key}\nLatest Supported: {latest_key}\n\n"
                msg += "You are not on the latest version supported by this patcher.\n"
                msg += "Do you want to FORCE the LATEST patch?"
                
                # Ask: Yes = Force Latest, No = Use Detected
                if messagebox.askyesno("Version Selection", msg):
                     messagebox.showinfo("Notice", "You have chosen to force the Latest Patch on an older Pack version.\nThis is allowed but may have unexpected results.")
                     target_key = latest_key
                     self._log(f"User forced latest version: {target_key}")
                else:
                     self._log(f"User kept detected version: {target_key}")

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
