"""
ConfigModel Module

This module manages the application configuration, including paths,
filenames, and version-specific patch data.
"""

from typing import Dict, Any, Optional
import os
import json

class ConfigModel:
    """
    Manages application configuration and resource paths.
    """
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
                "marketplaceEncrypted": "assets/Patches/A&S Patch File for 1.7 (do not Unzip)/Actions & Stuff encrypted.zip.vcdiff",
                "zipDecrypted": "assets/Patches/A&S Patch File for 1.7 (do not Unzip)/Actions & Stuff decrypted.zip.vcdiff",
            },
            "patchVersions": {
                "v1.7": {
                    "patches": {
                        "encrypted": "assets/Patches/A&S Patch File for 1.7 (do not Unzip)/Actions & Stuff encrypted.zip.vcdiff",
                        "decrypted": "assets/Patches/A&S Patch File for 1.7 (do not Unzip)/Actions & Stuff decrypted.zip.vcdiff"
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

    def get_path(self, key: str) -> Optional[str]:
        """Retrieves a path from the configuration by key."""
        return self.config["paths"].get(key)

    def get_filename(self, key: str) -> str:
        """Retrieves a filename from the configuration by key."""
        return self.config["filenames"].get(key, "")

    def get_executable(self, key: str) -> str:
        """Retrieves an executable path from the configuration by key."""
        return self.config["executables"].get(key, "")

    def get_patch_path(self, key: str) -> str:
        """Retrieves a patch file path from the configuration by key."""
        return self.config["patches"].get(key, "")

    def get_cleanup_prefixes(self):
        """Retrieves the list of folder prefixes to clean up."""
        return self.config["cleanupPrefixes"]

    def load_external_config(self, config_path: str) -> bool:
        """
        Loads and updates config from an external JSON file.

        Args:
            config_path (str): Path to the JSON configuration file.

        Returns:
            bool: True if loaded successfully, False otherwise.
        """
        if not os.path.exists(config_path):
            return False
        try:
            with open(config_path, 'r') as f:
                loaded_config = json.load(f)

            # Deep merge logic could go here, but for now we basically override paths
            if "paths" in loaded_config:
                for k, v in loaded_config["paths"].items():
                    if k in self.config["paths"]:
                        self.config["paths"][k] = v
            return True
        except Exception:
            return False
