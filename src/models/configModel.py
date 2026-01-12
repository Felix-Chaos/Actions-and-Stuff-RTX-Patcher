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
                # AppData locations (Prioritized)
                "minecraftBedrock": os.path.expandvars(r"%AppData%/Minecraft Bedrock"),
                "minecraftBedrockPreview": os.path.expandvars(r"%AppData%/Minecraft Bedrock Preview"),

                # Windows Store / Package LocalState folders
                "minecraftUwp": os.path.expandvars(r"%LocalAppData%/Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState"),
                "minecraftUwpPreview": os.path.expandvars(r"%LocalAppData%/Packages/Microsoft.MinecraftWindowsBeta_8wekyb3d8bbwe/LocalState"),

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
                "marketplaceEncrypted": "assets/Patches/Current/encrypted.vcdiff",
                "zipDecrypted": "assets/Patches/Current/decrypted.vcdiff",
            },
            "patchVersions": {},
            "cleanupPrefixes": ["A&SforRTX", "Actions & Stuff Enhanced"],
            "filesToRemove": ["contents.json", "signatures.json", "splashes.json", "sounds.json"],
            "dirsToRemove": ["texts"],
        }
        
        # Load dynamic patches after init
        self.load_patch_versions()
        
    def load_patch_versions(self):
        """
        Scans 'assets/Patches' for patch_config.json files and builds the patchVersions dict.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        patches_root = os.path.join(base_dir, "assets", "Patches")

        if not os.path.exists(patches_root):
            return

        loaded_versions = {}

        for item in os.listdir(patches_root):
            full_path = os.path.join(patches_root, item)
            if os.path.isdir(full_path):
                config_file = os.path.join(full_path, "patch_config.json")
                if os.path.exists(config_file):
                    try:
                        with open(config_file, "r") as f:
                            data = json.load(f)
                        
                        # We need packVersion to be the key
                        if "packVersion" in data:
                            ver_key = data["packVersion"]
                            
                            # Construct paths relative to assets if they aren't absolute or fully defined in JSON
                            # The previous format had explicit paths in config. Now we might infer them?
                            # Actually, let's keep it simple: we expect the JSON to contain the 'stats' and maybe 'patches'
                            # If 'patches' is missing, we infer it from the folder structure standard.
                            
                            patch_entry = {}
                            
                            # Stats are required
                            if "marketplace_pack_stats" in data:
                                # The current schema (from create_patch) puts stats under "marketplace_pack_stats" -> "v1"
                                # But main app expects "stats": {files, dirs} at root of version object
                                # We need to adapt.
                                
                                # Check formats:
                                if "v1" in data["marketplace_pack_stats"]:
                                    patch_entry["stats"] = data["marketplace_pack_stats"]["v1"]
                                else:
                                    patch_entry["stats"] = data["marketplace_pack_stats"] # Fallback
                                    
                            elif "stats" in data:
                                patch_entry["stats"] = data["stats"]
                            else:
                                continue # No stats, useless for detection
                            
                            # Patches
                            # If defined in JSON, use them. Else construct.
                            if "patches" in data:
                                patch_entry["patches"] = data["patches"]
                            else:
                                # Construct standard paths
                                # Path relative to project root: assets/Patches/<folder_name>/...
                                relative_base = f"assets/Patches/{item}"
                                # Check for new simplified filenames first (Current standard)
                                enc_new = "encrypted.vcdiff"
                                dec_new = "decrypted.vcdiff"
                                
                                # Legacy filenames
                                enc_old = "Actions & Stuff encrypted.zip.vcdiff"
                                dec_old = "Actions & Stuff decrypted.zip.vcdiff"
                                
                                enc_path = enc_old
                                if os.path.exists(os.path.join(full_path, enc_new)):
                                    enc_path = enc_new
                                    
                                dec_path = dec_old
                                if os.path.exists(os.path.join(full_path, dec_new)):
                                    dec_path = dec_new

                                patch_entry["patches"] = {
                                    "encrypted": f"{relative_base}/{enc_path}",
                                    "decrypted": f"{relative_base}/{dec_path}"
                                }
                            
                            patch_entry["patchVersion"] = data.get("patchVersion", "1.0")
                            
                            if ver_key not in loaded_versions:
                                loaded_versions[ver_key] = []
                            loaded_versions[ver_key].append(patch_entry)
                            
                    except Exception as e:
                        print(f"Failed to load patch config from {item}: {e}")

        # If we found versions, update config. 
        # Sort patches by patchVersion descending for each version
        if loaded_versions:
            for ver_key in loaded_versions:
                loaded_versions[ver_key].sort(key=lambda x: x.get("patchVersion", "0"), reverse=True)
            self.config["patchVersions"] = loaded_versions

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
