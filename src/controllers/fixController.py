import os
import shutil
from tkinter import messagebox
from ..models.configModel import ConfigModel

class FixController:
    def __init__(self, config: ConfigModel, view):
        self.config = config
        self.view = view # FixFrame instance

    def moveMarketplaceFolders(self):
        """Moves folders from premium_cache to com.mojang."""
        srcDir = os.path.join(os.path.expandvars(self.config.getPath("minecraftUwp")), "premium_cache", "resource_packs")
        dstDir = os.path.join(os.path.expandvars(self.config.getPath("minecraftUwp")), "games", "com.mojang", "resource_packs")

        if not os.path.exists(srcDir):
            messagebox.showerror("Error", f"Source directory not found:\n{srcDir}")
            return

        os.makedirs(dstDir, exist_ok=True)
        movedCount = 0

        try:
            for folder in os.listdir(srcDir):
                fullPath = os.path.join(srcDir, folder)
                if os.path.isdir(fullPath):
                    # Rename contents.json to .bak
                    contentsPath = os.path.join(fullPath, "contents.json")
                    if os.path.exists(contentsPath):
                        try:
                            os.rename(contentsPath, contentsPath + ".bak")
                        except OSError as e:
                            print(f"Failed to rename contents.json in {folder}: {e}")

                    # Move and rename folder
                    newName = folder + "_mp"
                    newPath = os.path.join(dstDir, newName)
                    
                    if os.path.exists(newPath):
                         # If it already exists, maybe we moved it before? Skip or overwrite?
                         # For safety, let's skip but warn
                         print(f"Skipping {folder}, target {newName} already exists.")
                         continue
                         
                    shutil.move(fullPath, newPath)
                    movedCount += 1
            
            messagebox.showinfo("Done", f"{movedCount} folder(s) moved to com.mojang.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to move folders: {str(e)}")

    def restoreMarketplaceFolders(self):
        """Restores folders from com.mojang back to premium_cache."""
        srcDir = os.path.join(os.path.expandvars(self.config.getPath("minecraftUwp")), "games", "com.mojang", "resource_packs")
        dstDir = os.path.join(os.path.expandvars(self.config.getPath("minecraftUwp")), "premium_cache", "resource_packs")

        if not os.path.exists(srcDir):
            messagebox.showerror("Error", f"Source directory not found:\n{srcDir}")
            return

        movedCount = 0
        try:
            for folder in os.listdir(srcDir):
                if folder.endswith("_mp"):
                    fullPath = os.path.join(srcDir, folder)
                    newName = folder[:-3] # Remove '_mp'
                    newPath = os.path.join(dstDir, newName)
                    
                    if os.path.exists(newPath):
                        # Clean destination if exists to allow move back
                        shutil.rmtree(newPath)
                        
                    shutil.move(fullPath, newPath)
                    
                    # Restore contents.json
                    contentsBakPath = os.path.join(newPath, "contents.json.bak")
                    if os.path.exists(contentsBakPath):
                        try:
                            os.rename(contentsBakPath, os.path.join(newPath, "contents.json"))
                        except OSError as e:
                            print(f"Failed to restore contents.json in {newName}: {e}")

                    movedCount += 1
            
            messagebox.showinfo("Done", f"{movedCount} folder(s) moved back to premium_cache.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to restore folders: {str(e)}")
