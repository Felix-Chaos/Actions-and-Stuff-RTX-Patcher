import os
import threading
import tempfile
import shutil
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

    def setAdvancedMode(self, enabled: bool):
        self.is_advanced = enabled
        self.view.setAdvancedMode(enabled)

    def _log(self, message: str):
        """Thread-safe logging helper."""
        if self.is_advanced:
            # Marshal to main thread
            self.view.after(0, lambda: self.view.appendLog(message))

    def startMarketplacePatch(self):
        # self.view is PatchProgressFrame
        patch_frame = self.view

        # Access MainWindow's advancedVar
        is_advanced = False
        try:
            is_advanced = patch_frame.winfo_toplevel().advancedVar.get()
        except AttributeError:
            pass # Fallback

        if is_advanced:
            patch_frame.setStatus("Ready. properties below.")
            patch_frame.modeVar.set("marketplace")
            patch_frame.onModeChanged()
            patch_frame.setActionCommand(self.startAdvancedLogic, "Start Patch")
            patch_frame.setActionState("normal")
            return

        patch_frame.setStatus("Searching for Marketplace Content...")
        patch_frame.setProgress(0, 'indeterminate')
        patch_frame.setActionState("disabled")
        self.cancel_event.clear()
        threading.Thread(target=self._marketplaceSearchWorker, daemon=True).start()

    def _marketplaceSearchWorker(self):
        paths_to_check = [
             os.path.join(os.path.expandvars(self.config.get_path("minecraftUwp")), "premium_cache", "resource_packs"),
             os.path.join(os.path.expandvars(self.config.get_path("minecraftUwpPreview")), "premium_cache", "resource_packs"),
             os.path.join(os.path.expandvars(self.config.get_path("minecraftBedrock")), "premium_cache", "resource_packs"),
             os.path.join(os.path.expandvars(self.config.get_path("minecraftBedrockPreview")), "premium_cache", "resource_packs")
        ]

        target_versions = self.config.config["patchVersions"]
        found_folder = None
        detected_version_data = None

        for path in paths_to_check:
            if self.cancel_event.is_set(): return
            if not os.path.exists(path): continue

            try:
                for folder in os.listdir(path):
                    full_path = os.path.join(path, folder)
                    if os.path.isdir(full_path):
                        f_count, d_count = self.fs.getFolderStats(full_path)

                        # Check against all configured versions
                        for ver_key, ver_data in target_versions.items():
                            stats = ver_data["stats"]
                            if f_count == stats["files"] and d_count == stats["dirs"]:
                                found_folder = full_path
                                detected_version_data = ver_data
                                self._log(f"Detected version {ver_key} at {full_path}")
                                break
                        if found_folder: break
            except OSError:
                continue
            if found_folder: break

        if not found_folder:
            self.view.after(0, lambda: messagebox.showerror("Error", "Could not find Actions & Stuff in premium_cache.\nMake sure you have downloaded it from the Marketplace."))
            self.view.after(0, self.view.onBack)
            return

        self.view.after(0, lambda: self.view.setStatus("Found pack. Preparing..."))

        # Prepare temp directory
        os.makedirs(self.temp_dir, exist_ok=True)
        temp_zip = os.path.join(self.temp_dir, "temp_vanilla.zip")

        self._log(f"Found Marketplace content at: {found_folder}")
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

        self.view.after(0, lambda: self._onReadyToPatch(temp_zip, "marketplace", detected_version_data))

    def startZipPatch(self):
        patch_frame = self.view

        is_advanced = False
        try:
            is_advanced = patch_frame.winfo_toplevel().advancedVar.get()
        except AttributeError:
            pass

        if is_advanced:
            patch_frame.setStatus("Ready. Select Zip below.")
            patch_frame.modeVar.set("zip")
            patch_frame.onModeChanged()
            patch_frame.setActionCommand(self.startAdvancedLogic, "Start Patch")
            patch_frame.setActionState("normal")
            return

        # Default Mode: Wait for user to click "Select Pack"
        def selectAndPatch():
            file_path = filedialog.askopenfilename(filetypes=[("Minecraft Packs", "*.zip *.mcpack")], title="Select Pack")
            if not file_path:
                return

            patch_frame.setStatus("Processing Zip...")
            patch_frame.setProgress(0, 'indeterminate')
            patch_frame.setActionState("disabled")
            self.cancel_event.clear()
            threading.Thread(target=self._zipProcessWorker, args=(file_path,), daemon=True).start()

        patch_frame.setStatus("Ready. Please select your A&S Zip/McPack.")
        patch_frame.setActionCommand(selectAndPatch, "Select Pack")
        patch_frame.setActionState("normal")

    def _zipProcessWorker(self, file_path: str):
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
            
            # Removed User Prompt to ensure consistency with Patcher Tool
            # The Tool always assumes a normalized source with the standard manifest.
            
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
            
            self.view.after(0, lambda: self._onReadyToPatch(normalized_zip, "zip"))

        except Exception as e:
            self.view.after(0, lambda: messagebox.showerror("Error", f"Failed to process zip: {e}"))
            self.view.after(0, self.view.onBack)

    def _onReadyToPatch(self, source_zip: str, mode: str, detected_version_data: dict = None):
        self.view.setStatus("Ready to Patch.")
        self.view.setProgress(100, 'determinate')

        def runPatchAction():
            if messagebox.askyesno("Clean Update?", "Do you want to clean old versions of the pack before patching?\n(Recommended for updates)"):
                self.view.setStatus("Cleaning old versions...")
                std_rp = os.path.join(os.path.expandvars(self.config.get_path("minecraftUwp")), "games", "com.mojang", "resource_packs")
                found = self.fs.scanDirectory(std_rp, self.config.get_cleanup_prefixes())
                for f in found:
                    self.fs.robustCleanup(f)

            patch_type = "marketplaceEncrypted" if mode == "marketplace" else "zipDecrypted"
            patch_file_relative = self.config.get_patch_path(patch_type)

            # Use detected patch file if available
            if detected_version_data and "patches" in detected_version_data:
                key = "encrypted" if mode == "marketplace" else "decrypted"
                if key in detected_version_data["patches"]:
                    patch_file_relative = detected_version_data["patches"][key]

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

        # New API Call
        success, msg = self.patcher.runPatch(
            xdelta_path=xdelta_params,
            source_zip=source_zip,
            patch_file=patch_file,
            output_file=output_file,
            log_callback=self._log
        )

        if success:
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
            self.view.after(0, lambda: messagebox.showinfo("Success", "Patch created successfully! Click Install to launch Minecraft."))
        else:
            self.view.after(0, lambda: showErrorWithCopy("Patch Failed", msg, self.view))
            # self.view.after(0, self.view.onBack) # DISABLED FOR DEBUGGING

    def startAdvancedLogic(self):
        patch_frame = self.view
        mode = patch_frame.modeVar.get()

        patch_frame.setActionState("disabled")
        self.cancel_event.clear()

        if mode == "marketplace":
            patch_frame.setStatus("Searching for Marketplace Content...")
            patch_frame.setProgress(0, 'indeterminate')
            threading.Thread(target=self._marketplaceSearchWorker, daemon=True).start()

        elif mode == "zip":
            file_path = filedialog.askopenfilename(filetypes=[("Minecraft Packs", "*.zip *.mcpack")], title="Select Pack")
            if not file_path:
                patch_frame.setActionState("normal")
                return

            patch_frame.setStatus("Processing Zip...")
            patch_frame.setProgress(0, 'indeterminate')
            threading.Thread(target=self._zipProcessWorker, args=(file_path,), daemon=True).start()

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
