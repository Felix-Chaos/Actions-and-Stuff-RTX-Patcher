import os
import threading
from tkinter import messagebox
from ..models.configModel import ConfigModel
from ..models.fileSystemModel import FileSystemModel


class CleanController:
    def __init__(self, config: ConfigModel, fs: FileSystemModel, view):
        self.config = config
        self.fs = fs
        self.view = view  # CleanFrame
        self.foundFolders = []
        self.cancelEvent = threading.Event()

    def startScan(self):
        self.foundFolders = []
        self.cancelEvent.clear()
        threading.Thread(target=self._scanWorker, daemon=True).start()

    def _scanWorker(self):
        minecraft_bedrock_base = os.path.expandvars(self.config.get_path("minecraftBedrock"))
        users_dir = os.path.join(minecraft_bedrock_base, "Users")

        pathsToScan = [
            os.path.join(os.path.expandvars(self.config.get_path(
                "minecraftUwp")), "games", "com.mojang"),
            os.path.join(os.path.expandvars(self.config.get_path(
                "minecraftUwpPreview")), "games", "com.mojang"),
            os.path.join(minecraft_bedrock_base, "games", "com.mojang"),
            os.path.join(os.path.expandvars(self.config.get_path(
                "minecraftBedrockPreview")), "games", "com.mojang"),
        ]

        if os.path.exists(users_dir):
            try:
                for user_folder in os.listdir(users_dir):
                    user_path = os.path.join(users_dir, user_folder, "games", "com.mojang")
                    if os.path.exists(user_path) and user_path not in pathsToScan:
                        pathsToScan.append(user_path)
            except Exception:
                pass

        prefixes = self.config.get_cleanup_prefixes()
        resultsText = ""

        for basePath in pathsToScan:
            if self.cancelEvent.is_set():
                return
            if not os.path.exists(basePath):
                continue

            # Check resource_packs
            rpPath = os.path.join(basePath, "resource_packs")
            foundInRp = self.fs.scanDirectory(
                rpPath, prefixes, self.cancelEvent)
            if foundInRp:
                self.foundFolders.extend(foundInRp)
                resultsText += f"In {os.path.basename(basePath)}/resource_packs:\n"
                for f in foundInRp:
                    resultsText += f"  - {os.path.basename(f)}\n"

            # Check minecraftWorlds
            worldsPath = os.path.join(basePath, "minecraftWorlds")
            if os.path.exists(worldsPath):
                for world in os.listdir(worldsPath):
                    if self.cancelEvent.is_set():
                        return
                    worldRpPath = os.path.join(
                        worldsPath, world, "resource_packs")
                    foundInWorld = self.fs.scanDirectory(
                        worldRpPath, prefixes, self.cancelEvent)
                    if foundInWorld:
                        self.foundFolders.extend(foundInWorld)
                        resultsText += f"In World {world}:\n"
                        for f in foundInWorld:
                            resultsText += f"  - {os.path.basename(f)}\n"

        if resultsText:
            self.view.after(0, lambda: self.view.updateResults(resultsText))
            self.view.after(0, self.view.enableConfirm)
        else:
            self.view.after(0, lambda: self.view.updateResults(
                "No old packs found."))
            self.view.after(0, lambda: messagebox.showinfo(
                "Clean", "No old packs found."))

    def deleteFolders(self):
        deletedCount = 0
        for folder in self.foundFolders:
            if self.fs.robustCleanup(folder):
                deletedCount += 1

        messagebox.showinfo("Done", f"Deleted {deletedCount} folders.")
        # self.view.onConfirm() was causing a crash because it's None.
        # The user can just click Back.

    def cancel(self):
        self.cancelEvent.set()
