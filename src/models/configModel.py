from typing import Dict, Any, Optional
import os
import json

class ConfigModel:
    def __init__(self):
        self.config: Dict[str, Any] = {
            "paths": {
                # Windows Store / Package LocalState folders
                "minecraftUwp": os.path.expandvars(r"%LocalAppData%/Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState"),
                "minecraftUwpPreview": os.path.expandvars(r"%LocalAppData%/Packages/Microsoft.MinecraftWindowsBeta_8wekyb3d8bbwe/LocalState"),
                
                # AppData locations
                "minecraftBedrock": os.path.expandvars(r"%AppData%/Minecraft Bedrock"),
                "minecraftBedrockPreview": os.path.expandvars(r"%AppData%/Minecraft Bedrock Preview"),
                
                "xdeltaDir": "assets/xdelta3",
            },
            "executables": {
                "xdelta": "assets/xdelta3/exec/xdelta3_x86_64_win.exe"
            },
            "filenames": {
                "encryptedZip": "Actions & Stuff encrypted.zip",
                "normalizedZip": "Actions & Stuff decrypted.zip",
                "finalMcPack": "Actions & Stuff Enhanced RTX.mcpack",
                "icon": "assets/resources/icon.ico",
                "manifest": "manifest.json",
                "patchConfig": "patch_config.json",
            },
            "patches": {
                "marketplaceEncrypted": "assets/Patches/Marketplace/v1.7/patch.vcdiff",
                "zipDecrypted": "assets/Patches/Zip/v1.7/patch.vcdiff",
            },
            "patchVersions": {
                "v1.7": {
                    "patches": {
                        "encrypted": "assets/Patches/Marketplace/v1.7/patch.vcdiff",
                        "decrypted": "assets/Patches/Zip/v1.7/patch.vcdiff"
                    },
                    "stats": {"files": 16661, "dirs": 301}
                },
                "v1.8": {
                    "patches": {
                        "encrypted": "assets/Patches/v1.8/encrypted.vcdiff",
                        "decrypted": "assets/Patches/v1.8/decrypted.vcdiff"
                    },
                    "stats": {"files": 10057, "dirs": 162}
                }
            },
            "cleanupPrefixes": ["A&SforRTX", "Actions & Stuff Enhanced"],
            "filesToRemove": ["contents.json", "signatures.json", "splashes.json", "sounds.json"],
            "dirsToRemove": ["texts"],
        }

    def getPath(self, key: str) -> Optional[str]:
        return self.config["paths"].get(key)
    
    def getFilename(self, key: str) -> str:
        return self.config["filenames"].get(key, "")

    def getExecutable(self, key: str) -> str:
        return self.config["executables"].get(key, "")

    def getPatchPath(self, key: str) -> str:
        return self.config["patches"].get(key, "")
    
    def getCleanupPrefixes(self):
        return self.config["cleanupPrefixes"]

    def loadExternalConfig(self, configPath: str) -> bool:
        """Loads and updates config from an external JSON file."""
        if not os.path.exists(configPath):
            return False
        try:
            with open(configPath, 'r') as f:
                loadedConfig = json.load(f)
            
            # Deep merge logic could go here, but for now we basically override paths
            if "paths" in loadedConfig:
                for k, v in loadedConfig["paths"].items():
                    if k in self.config["paths"]:
                        self.config["paths"][k] = v
            return True
        except Exception:
            return False
