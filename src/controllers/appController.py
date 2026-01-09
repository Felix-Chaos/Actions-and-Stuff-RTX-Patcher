import tkinter as tk
import os
import sys
import webbrowser
from tkinter import messagebox

from ..views.mainWindow import MainWindow
from ..views.patchFrames import MainMenuFrame, PatchProgressFrame
from ..views.otherFrames import CleanFrame, FixFrame

from ..models.configModel import ConfigModel
from ..models.fileSystemModel import FileSystemModel
from ..models.patcherModel import PatcherModel

from .patchController import PatchController
from .cleanController import CleanController
from .fixController import FixController
from ..utils.helpers import resourcePath, runScriptInThread

class AppController:
    def __init__(self):
        self.config = ConfigModel()
        self.fs = FileSystemModel()
        self.patcher = PatcherModel()
        
        self.root = MainWindow(title="A&S Minecraft RTX Community Patcher V2", theme="superhero", onClose=self.quit)
        self.root.setIcon(resourcePath(self.config.getFilename("icon")))
        
        # Load Menus
        self._loadToolsMenu()
        self._loadDependenciesMenu()
        self._loadHelpMenu()
        self.root.bindAdvancedToggle(self.onAdvancedToggle)
        
        self.isAdvanced = False

        self._initFrames()
        self.root.showFrame("MainMenu")

    def _loadToolsMenu(self):
        # Look for tools folder in bundled resources
        toolsPath = resourcePath("tools")
        
        scripts = []
        if os.path.isdir(toolsPath):
            for f in sorted(os.listdir(toolsPath)):
                if f.endswith(".py") and f != "__init__.py":
                    label = os.path.splitext(f)[0]
                    path = os.path.join(toolsPath, f)
                    # Create command closure
                    cmd = lambda p=path, l=label: runScriptInThread(self.root, p, l)
                    scripts.append((label, path, cmd))
        
        self.root.populateToolsMenu(scripts)

    def _loadDependenciesMenu(self):
        def openVanillaRtx():
            if messagebox.askokcancel("Visit Website", "Open Vanilla Reforged RTX page?"):
                webbrowser.open("https://www.curseforge.com/minecraft-bedrock/texture-packs/vanilla-reforged-rtx")

        def openBetterRtx():
            if messagebox.askokcancel("Visit Website", "Open BetterRTX (bedrock.graphics)?"):
                webbrowser.open("https://bedrock.graphics/")

        def openMarketplace():
            if messagebox.askokcancel("Visit Website", "Open Actions & Stuff (Marketplace)?"):
                webbrowser.open("https://www.minecraft.net/en-us/marketplace/pdp/oreville-studios/actions--stuff-1.6/61c7a786-d7ad-49e0-a710-817121cd9795")

        self.root.populateDepMenu([
            ("Install Vanilla Reforged RTX", openVanillaRtx),
            ("BetterRTX (Required)", openBetterRtx),
            ("Actions & Stuff (Marketplace)", openMarketplace)
        ])

    def _loadHelpMenu(self):
        def joinDiscord():
            if messagebox.askokcancel("Join Discord", "Open A&S RTX Community Discord?"):
                webbrowser.open("https://discord.gg/YrMMmN2kc7")

        def about():
            try:
                from .. import version
                ver_str = version.VERSION
                date_str = version.BUILD_DATE
            except ImportError:
                ver_str = "2.0.0 (Dev)"
                date_str = "Unknown"
                
            info = (
                f"A&S Minecraft RTX Community Patcher V2\n\n"
                f"Version: {ver_str}\n"
                f"Build Date: {date_str}\n\n"
                f"Created by Felix-Chaos & Community\n"
                f"Based on original work by Demente Parker"
            )
            messagebox.showinfo("About", info)
            
        self.root.populateHelpMenu([
            ("Join Discord Server", joinDiscord),
            ("About", about)
        ])

    def _initFrames(self):
        # 1. Main Menu
        menuCallbacks = {
            "marketplace": lambda: self.showPatchFrame("marketplace"),
            "zip": lambda: self.showPatchFrame("zip"),
            "clean": self.showCleanFrame,
            "fix": self.showFixFrame,
            "exit": self.quit
        }
        self.mainMenuFrame = MainMenuFrame(self.root.container, menuCallbacks)
        self.root.addFrame("MainMenu", self.mainMenuFrame)

        # 2. Patch Frame
        self.patchFrame = PatchProgressFrame(self.root.container, "Patching", self.showMainMenu)
        self.root.addFrame("PatchFrame", self.patchFrame)
        self.patchController = PatchController(self.config, self.patcher, self.fs, self.patchFrame)

        # 3. Clean Frame
        self.cleanFrame = CleanFrame(self.root.container, None, self.showMainMenu)
        self.root.addFrame("CleanFrame", self.cleanFrame)
        self.cleanController = CleanController(self.config, self.fs, self.cleanFrame)
        self.cleanFrame.confirmBtn.config(command=self.cleanController.deleteFolders)

        # 4. Fix Frame
        self.fixFrame = FixFrame(self.root.container, None, None, self.showMainMenu)
        self.root.addFrame("FixFrame", self.fixFrame)
        self.fixController = FixController(self.config, self.fixFrame)
        self.fixFrame.moveBtn.config(command=self.fixController.moveMarketplaceFolders)
        self.fixFrame.restoreBtn.config(command=self.fixController.restoreMarketplaceFolders)

    def onAdvancedToggle(self, enabled: bool):
        self.isAdvanced = enabled
        self.mainMenuFrame.setAdvancedMode(enabled)
        self.patchController.setAdvancedMode(enabled)

    def showMainMenu(self):
        self.root.showFrame("MainMenu")

    def showPatchFrame(self, mode: str):
        self.root.showFrame("PatchFrame")
        if mode == "marketplace":
            self.patchFrame.titleLabel.config(text="Patch from Marketplace")
            self.patchController.startMarketplacePatch()
        else:
            self.patchFrame.titleLabel.config(text="Patch from Zip/McPack")
            self.patchController.startZipPatch()

    def showCleanFrame(self):
        self.root.showFrame("CleanFrame")
        self.cleanController.startScan()

    def showFixFrame(self):
        self.root.showFrame("FixFrame")

    def run(self):
        self.root.mainloop()

    def quit(self):
        self.root.destroy()
