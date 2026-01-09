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
        
        self.root = MainWindow(title="AnS RTX Patcher (Fuzed)", theme="superhero", onClose=self.quit)
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
        # Look for tools folder relative to main.py
        basePath = os.getcwd() # main.py running dir
        toolsPath = os.path.join(basePath, "tools")
        
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
        def openUrl():
            if messagebox.askokcancel("Visit Website", "Open Vanilla Reforged RTX page?"):
                webbrowser.open("https://www.curseforge.com/minecraft-bedrock/texture-packs/vanilla-reforged-rtx")
        self.root.populateDepMenu([("Install Vanilla Reforged RTX", openUrl)])

    def _loadHelpMenu(self):
        def about():
            messagebox.showinfo("About", "A.n.S Patcher Fuzed\nRefactored Edition")
        self.root.populateHelpMenu([("About", about)])

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
