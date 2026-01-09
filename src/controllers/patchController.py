import os
import threading
import tempfile
import shutil
from tkinter import messagebox, filedialog
from ..models.configModel import ConfigModel
from ..models.patcherModel import PatcherModel
from ..models.fileSystemModel import FileSystemModel
from ..models.fileSystemModel import FileSystemModel
from ..utils.helpers import resourcePath, showErrorWithCopy

class PatchController:
    def __init__(self, config: ConfigModel, patcher: PatcherModel, fs: FileSystemModel, view):
        self.config = config
        self.patcher = patcher
        self.fs = fs
        self.view = view # PatchProgressFrame
        self.cancelEvent = threading.Event()
        self.tempDir = os.path.join(tempfile.gettempdir(), "AnSPatcherFuzed")
        self.isAdvanced = False

    def setAdvancedMode(self, enabled: bool):
        self.isAdvanced = enabled
        self.view.setAdvancedMode(enabled)

    def _log(self, message: str):
        """Thread-safe logging helper."""
        if self.isAdvanced:
            # Marshal to main thread
            self.view.after(0, lambda: self.view.appendLog(message))

    def startMarketplacePatch(self):
        # self.view is PatchProgressFrame
        patchFrame = self.view
        
        # Access MainWindow's advancedVar
        isAdvanced = False
        try:
            isAdvanced = patchFrame.winfo_toplevel().advancedVar.get()
        except AttributeError:
             pass # Fallback

        if isAdvanced:
            patchFrame.setStatus("Ready. properties below.")
            patchFrame.modeVar.set("marketplace")
            patchFrame.onModeChanged()
            patchFrame.setActionCommand(self.startAdvancedLogic, "Start Patch")
            patchFrame.setActionState("normal")
            return

        patchFrame.setStatus("Searching for Marketplace Content...")
        patchFrame.setProgress(0, 'indeterminate')
        patchFrame.setActionState("disabled")
        self.cancelEvent.clear()
        threading.Thread(target=self._marketplaceSearchWorker, daemon=True).start()

    def _marketplaceSearchWorker(self):
        pathsToCheck = [
             os.path.join(os.path.expandvars(self.config.getPath("minecraftUwp")), "premium_cache", "resource_packs"),
             os.path.join(os.path.expandvars(self.config.getPath("minecraftUwpPreview")), "premium_cache", "resource_packs"),
             os.path.join(os.path.expandvars(self.config.getPath("minecraftBedrock")), "premium_cache", "resource_packs"),
             os.path.join(os.path.expandvars(self.config.getPath("minecraftBedrockPreview")), "premium_cache", "resource_packs")
        ]
        
        targetVersions = self.config.config["patchVersions"]
        foundFolder = None
        detectedVersionData = None
        
        for path in pathsToCheck:
            if self.cancelEvent.is_set(): return
            if not os.path.exists(path): continue
            
            for folder in os.listdir(path):
                fullPath = os.path.join(path, folder)
                if os.path.isdir(fullPath):
                    fCount, dCount = self.fs.getFolderStats(fullPath)
                    
                    # Check against all configured versions
                    for verKey, verData in targetVersions.items():
                        stats = verData["stats"]
                        if fCount == stats["files"] and dCount == stats["dirs"]:
                            foundFolder = fullPath
                            detectedVersionData = verData
                            self._log(f"Detected version {verKey} at {fullPath}")
                            break
                    if foundFolder: break
            if foundFolder: break

        if not foundFolder:
            self.view.after(0, lambda: messagebox.showerror("Error", "Could not find Actions & Stuff in premium_cache.\nMake sure you have downloaded it from the Marketplace."))
            self.view.after(0, self.view.onBack)
            return

        self.view.after(0, lambda: self.view.setStatus("Found pack. Preparing..."))
        
        # NOTE: Marketplace patching generally assumes we patch the original encrypted content or a copy.
        # However, if the user implies custom manifest logic typically applies to getting *ready* to patch (like with zip),
        # marketplace flow is slightly different as we typically compress the found folder directly.
        # But if we want to add a custom manifest, we need a writable copy.
        # Since `compressDeterministic` takes a source folder, we might need to copy/extract if we want to modify manifest.
        # Re-reading user request: "Patcher itself patches the files with a custom manifest... add that to the deterministic zipper"
        # Since 'Marketplace' flow compresses existing read-only (?) files, inserting a file requires a temp copy.
        
        # Let's create a temp copy for marketplace too if custom manifest is requested.
        # Actually, let's ask here too for consistency, or maybe just for Zip as per "decrypted zip" logic usually.
        # The user said "add that to the deterministic zipper".
        # Let's assume standard Zip flow first. If marketplace flow needs it, we'd need to copy 12000 files which is slow.
        # Given "patch_decrypted_zip" had it, I will add it to `_zipProcessWorker`.
        
        os.makedirs(self.tempDir, exist_ok=True)
        tempZip = os.path.join(self.tempDir, "temp_vanilla.zip")
        
        self._log(f"Found Marketplace content at: {foundFolder}")
        self._log("Starting compression/backup...")
        
        success = self.fs.compressDeterministic(foundFolder, tempZip, self.cancelEvent, logCallback=self._log)
        if not success or self.cancelEvent.is_set():
            return

        self.view.after(0, lambda: self._onReadyToPatch(tempZip, "marketplace", detectedVersionData))

    def startZipPatch(self):
        patchFrame = self.view
        
        isAdvanced = False
        try:
            isAdvanced = patchFrame.winfo_toplevel().advancedVar.get()
        except AttributeError:
             pass

        if isAdvanced:
            patchFrame.setStatus("Ready. Select Zip below.")
            patchFrame.modeVar.set("zip")
            patchFrame.onModeChanged()
            patchFrame.setActionCommand(self.startAdvancedLogic, "Start Patch")
            patchFrame.setActionState("normal")
            return

        filePath = filedialog.askopenfilename(filetypes=[("Minecraft Packs", "*.zip *.mcpack")], title="Select Pack")
        if not filePath:
            return

        patchFrame.setStatus("Processing Zip...")
        patchFrame.setProgress(0, 'indeterminate')
        patchFrame.setActionState("disabled")
        self.cancelEvent.clear()
        threading.Thread(target=self._zipProcessWorker, args=(filePath,), daemon=True).start()

    def _zipProcessWorker(self, filePath: str):
        extractDir = os.path.join(self.tempDir, "extracted")
        self.fs.robustCleanup(extractDir)
        os.makedirs(extractDir, exist_ok=True)
        
        try:
            shutil.unpack_archive(filePath, extractDir, format="zip")
            
            items = os.listdir(extractDir)
            if len(items) == 1 and os.path.isdir(os.path.join(extractDir, items[0])):
                singleDir = os.path.join(extractDir, items[0])
                for item in os.listdir(singleDir):
                    shutil.move(os.path.join(singleDir, item), extractDir)
                os.rmdir(singleDir)
            
            for root, dirs, files in os.walk(extractDir):
                for f in files:
                    if f in self.config.config["filesToRemove"]:
                        os.remove(os.path.join(root, f))
                for d in list(dirs):
                    if d in self.config.config["dirsToRemove"]:
                        shutil.rmtree(os.path.join(root, d))
                        dirs.remove(d)
            
            # --- CUSTOM MANIFEST LOGIC ---
            # Ask via main thread callback (blocking-ish) logic is tricky from thread. 
            # We'll use a variable signal or just `after` and wait? No, messagebox can be called from thread in Tkinter (usually safe-ish in simple cases, or blocks thread).
            # Best practice: invoke in main thread.
            
            shouldApplyManifest = [False]
            manifestEvent = threading.Event()
            
            def askManifest():
                if messagebox.askyesno("Custom Manifest", "Do you want to use the custom A&S manifest.json?\n(Fixes some import issues)"):
                    shouldApplyManifest[0] = True
                manifestEvent.set()
                
            self.view.after(0, askManifest)
            manifestEvent.wait() # Block thread until user answers
            
            if shouldApplyManifest[0]:
                manifestPath = resourcePath("resources/manifest.json")
                if os.path.exists(manifestPath):
                    shutil.copyfile(manifestPath, os.path.join(extractDir, "manifest.json"))
            # -----------------------------

            normalizedZip = os.path.join(self.tempDir, "normalized.zip")
            self._log("Starting deterministic compression (this may take a while)...")
            self.fs.compressDeterministic(extractDir, normalizedZip, self.cancelEvent, logCallback=self._log)
            
            self.view.after(0, lambda: self._onReadyToPatch(normalizedZip, "zip"))
            
        except Exception as e:
             self.view.after(0, lambda: messagebox.showerror("Error", f"Failed to process zip: {e}"))
             self.view.after(0, self.view.onBack)

    def _onReadyToPatch(self, sourceZip: str, mode: str, detectedVersionData: dict = None):
        self.view.setStatus("Ready to Patch.")
        self.view.setProgress(100, 'determinate')
        
        def runPatchAction():
            if messagebox.askyesno("Clean Update?", "Do you want to clean old versions of the pack before patching?\n(Recommended for updates)"):
                self.view.setStatus("Cleaning old versions...")
                stdRp = os.path.join(os.path.expandvars(self.config.getPath("minecraftUwp")), "games", "com.mojang", "resource_packs")
                found = self.fs.scanDirectory(stdRp, self.config.getCleanupPrefixes())
                for f in found:
                    self.fs.robustCleanup(f)

            patchType = "marketplaceEncrypted" if mode == "marketplace" else "zipDecrypted"
            patchFileRelative = self.config.getPatchPath(patchType)
            
            # Use detected patch file if available (overrides default marketplace config)
            if detectedVersionData and "patches" in detectedVersionData:
                key = "encrypted" if mode == "marketplace" else "decrypted"
                if key in detectedVersionData["patches"]:
                    patchFileRelative = detectedVersionData["patches"][key]

            patchFile = resourcePath(patchFileRelative)
            
            if self.isAdvanced:
                custom = self.view.customPatchVar.get()
                if custom and os.path.exists(custom):
                    patchFile = custom
            
            self.view.setActionState("disabled")
            self.view.setStatus("Patching...")
            self.view.setProgress(0, 'indeterminate')
            threading.Thread(target=self._patchWorker, args=(sourceZip, patchFile), daemon=True).start()
            
        self.view.setActionCommand(runPatchAction)
        self.view.setActionState("normal")

    def _patchWorker(self, sourceZip: str, patchFile: str):
        outputFile = os.path.join(self.tempDir, self.config.getFilename("finalMcPack"))
        xdelta = self.config.getExecutable("xdelta")
        xdeltaParams = resourcePath(xdelta)
        
        self._log("Starting XDelta patch...")
        success, msg = self.patcher.runPatch(xdeltaParams, sourceZip, patchFile, outputFile, logCallback=self._log)
        
        if success:
            self.view.after(0, lambda: self.view.setStatus("Patch Successful!"))
            
            def install():
                self._log("Installing pack...")
                success, result = self.patcher.createMcPack(outputFile)
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
             self.view.after(0, self.view.onBack)

    def startAdvancedLogic(self):
        patchFrame = self.view
        mode = patchFrame.modeVar.get()
        
        patchFrame.setActionState("disabled")
        self.cancelEvent.clear()
        
        if mode == "marketplace":
            patchFrame.setStatus("Searching for Marketplace Content...")
            patchFrame.setProgress(0, 'indeterminate')
            threading.Thread(target=self._marketplaceSearchWorker, daemon=True).start()
            
        elif mode == "zip":
            # If in advanced mode, we might need to ask for file NOW if not already set?
            # Or assume we asked? The UI doesn't have a file picker for Zip mode in the new design (it hides custom fields).
            # So, ask dialog.
            filePath = filedialog.askopenfilename(filetypes=[("Minecraft Packs", "*.zip *.mcpack")], title="Select Pack")
            if not filePath:
                patchFrame.setActionState("normal")
                return
                
            patchFrame.setStatus("Processing Zip...")
            patchFrame.setProgress(0, 'indeterminate')
            threading.Thread(target=self._zipProcessWorker, args=(filePath,), daemon=True).start()
            
        elif mode == "custom":
            # Read fields
            src = patchFrame.srcVar.get()
            tgt = patchFrame.tgtVar.get()
            patch = patchFrame.patchVar.get()
            
            if not src or not tgt or not patch:
                showErrorWithCopy("Error", "Please fill all fields.", self.view)
                patchFrame.setActionState("normal")
                return
                
            # If src is folder, compress it? If zip, use it.
            # For simplicity, if folder -> compress to temp. if zip -> copy to temp.
            
            self._log("Starting Custom Patch...")
            threading.Thread(target=self._customProcessWorker, args=(src, tgt, patch), daemon=True).start()

    def _customProcessWorker(self, src, tgt, patchFile):
        # 1. Prepare Source
        os.makedirs(self.tempDir, exist_ok=True)
        tempZip = os.path.join(self.tempDir, "custom_source.zip")
        
        if os.path.isdir(src):
            self._log(f"Compressing source: {src}")
            self.fs.compressDeterministic(src, tempZip, self.cancelEvent, logCallback=self._log)
        else:
            self._log(f"Using source zip: {src}")
            shutil.copyfile(src, tempZip)
            
        if self.cancelEvent.is_set(): return
        
        # 2. Patch
        # Need absolute path for patch file
        patchAbs = os.path.abspath(patchFile) if not os.path.isabs(patchFile) else patchFile
        
        # 3. Run Patch
        try:
            xdelta = self.config.getExecutable("xdelta")
            xdeltaParams = resourcePath(xdelta)
            
            # Use custom target name/path
            # If tgt is just filename, save to doc folder? Or Desktop? Or keep typical behavior?
            # User said "file path for everything can be edited".
            outputAbs = os.path.abspath(tgt)
            
            self._log(f"Applying patch: {patchAbs}")
            success, msg = self.patcher.runPatch(xdeltaParams, tempZip, patchAbs, outputAbs, logCallback=self._log)
            
            if success:
                self.view.after(0, lambda: self.view.setStatus("Patch Successful!"))
                
                def install():
                    self._log("Installing pack...")
                    success, result = self.patcher.createMcPack(outputAbs)
                    if success:
                         self._log(f"launched {result}")
                    else:
                         self._log(f"Install failed: {result}")
                         showErrorWithCopy("Install Failed", f"Could not launch pack:\n{result}", self.view)
                
                patchFrame = self.view
                self.view.after(0, lambda: patchFrame.setActionCommand(install, "Install Pack"))
                self.view.after(0, lambda: patchFrame.setActionState("normal"))
                self.view.after(0, lambda: patchFrame.setProgress(100, 'determinate'))
                self.view.after(0, lambda: messagebox.showinfo("Success", "Patch created successfully! Click Install to launch."))
                
            else:
                 self.view.after(0, lambda: showErrorWithCopy("Patch Failed", msg, self.view))
                 self.view.after(0, lambda: self.view.setActionState("normal"))

        except Exception as e:
            self.view.after(0, lambda: showErrorWithCopy("Error", str(e), self.view))
