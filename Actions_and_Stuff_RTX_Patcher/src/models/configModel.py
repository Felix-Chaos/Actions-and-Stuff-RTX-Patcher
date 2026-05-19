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

        # Load local config overrides if present
        self.load_external_config("config.json")

    def load_patch_versions(self):
        """
        Scans 'assets/Patches' for patch_config.json files and builds the patchVersions dict.
        """
        base_dir = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
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
                        with open(config_file, "r", encoding="utf-8") as f:
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
                                elif "stats" in data["marketplace_pack_stats"]:
                                    # Handle case where "stats" is nested inside "marketplace_pack_stats" (Seen in 1.9b2)
                                    patch_entry["stats"] = data["marketplace_pack_stats"]["stats"]
                                else:
                                    # Fallback
                                    patch_entry["stats"] = data["marketplace_pack_stats"]

                            elif "stats" in data:
                                patch_entry["stats"] = data["stats"]
                            else:
                                continue  # No stats, useless for detection

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

                            patch_entry["patchVersion"] = data.get(
                                "patchVersion", "1.0")

                            # Load validation data if present
                            if "validation" in data:
                                patch_entry["validation"] = data["validation"]

                            if ver_key not in loaded_versions:
                                loaded_versions[ver_key] = []
                            loaded_versions[ver_key].append(patch_entry)

                    except Exception as e:
                        print(f"Failed to load patch config from {item}: {e}")

        # If we found versions, update config.
        # Sort patches by patchVersion descending for each version
        if loaded_versions:
            for _, versions_list in loaded_versions.items():
                versions_list.sort(
                    key=lambda x: x.get("patchVersion", "0"), reverse=True)
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

    def get_latest_version_data(self) -> Optional[Dict[str, Any]]:
        """
        Retrieves the configuration for the latest available patch version.
        Useful for fallback when auto-detection fails or is skipped.
        """
        versions = self.config.get("patchVersions", {})
        if not versions:
            return None

        # Sort version keys (e.g. "v1.9", "v1.8") descending
        sorted_keys = sorted(versions.keys(), reverse=True)
        latest_key = sorted_keys[0]

        # Get the list of patches for this version
        patches_list = versions[latest_key]

        # The list is already sorted by patchVersion descending in load_patch_versions
        if patches_list:
            return patches_list[0]

        return None

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
            with open(config_path, 'r', encoding="utf-8") as f:
                loaded_config = json.load(f)

            # Deep merge logic could go here, but for now we basically override paths
            if "paths" in loaded_config:
                for k, v in loaded_config["paths"].items():
                    if k in self.config["paths"]:
                        self.config["paths"][k] = v

            # Merge other keys
            for k, v in loaded_config.items():
                if k != "paths":
                    self.config[k] = v

            return True
        except Exception:
            return False

    def save_config(self, config_path: str = "config.json") -> bool:
        """
        Saves the current configuration to a JSON file.
        """
        try:
            # We might want to filter out some runtime-only keys if any, but for now dump all
            # Except maybe 'patchVersions' which is huge and dynamic?
            # No, if we want to allow editing everything, we should dump everything.
            # However, 'patchVersions' is re-loaded from disk on init.
            # If we save it, we might duplicate or freeze it.
            # Let's exclude 'patchVersions' from the saved file to keep it clean,
            # unless the user explicitly wants to override it?
            # For now, let's exclude 'patchVersions' to avoid massive file bloat with redundant data.

            data_to_save = self.config.copy()
            if "patchVersions" in data_to_save:
                del data_to_save["patchVersions"]

            with open(config_path, 'w', encoding="utf-8") as f:
                json.dump(data_to_save, f, indent=4)
            return True
        except Exception as e:
            print(f"Failed to save config: {e}")
            return False

    def find_options_txt(self) -> str:
        """
        Attempts to locate options.txt in standard Minecraft Bedrock paths.
        Returns absolute path or None.
        """
        # Common locations
        user_home = os.path.expanduser("~")
        base_paths = [
            os.path.join(user_home, "AppData", "Roaming",
                         "Minecraft Bedrock", "Users"),
            os.path.join(user_home, "AppData", "Local", "Packages", "Microsoft.MinecraftUWP_8wekyb3d8bbwe",
                         "LocalState", "games", "com.mojang", "minecraftpe")
        ]

        # Check specific known path for this user first
        # Check Roaming/Minecraft Bedrock/Users/*
        roaming_users = base_paths[0]
        if os.path.exists(roaming_users):
            for userid in os.listdir(roaming_users):
                candidate = os.path.join(
                    roaming_users, userid, "games", "com.mojang", "minecraftpe", "options.txt")
                if os.path.exists(candidate):
                    return candidate

        # Check LocalState (UWP)
        uwp_options = os.path.join(base_paths[1], "options.txt")
        if os.path.exists(uwp_options):
            return uwp_options

        return None

    def find_all_options_txt(self) -> list:
        """
        Finds ALL options.txt files across known Minecraft Bedrock paths.
        Returns a list of (label, absolute_path) tuples.
        """
        results = []
        user_home = os.path.expanduser("~")

        # 1. GDK / Roaming path — each subfolder under Users/ is a profile
        roaming_users = os.path.join(
            user_home, "AppData", "Roaming", "Minecraft Bedrock", "Users"
        )
        if os.path.isdir(roaming_users):
            for userid in os.listdir(roaming_users):
                candidate = os.path.join(
                    roaming_users, userid, "games",
                    "com.mojang", "minecraftpe", "options.txt"
                )
                if os.path.isfile(candidate):
                    results.append((f"GDK — {userid}", candidate))

        # 2. UWP (Microsoft Store) path — single profile
        uwp_path = os.path.join(
            user_home, "AppData", "Local", "Packages",
            "Microsoft.MinecraftUWP_8wekyb3d8bbwe",
            "LocalState", "games", "com.mojang",
            "minecraftpe", "options.txt"
        )
        if os.path.isfile(uwp_path):
            results.append(("UWP (Microsoft Store)", uwp_path))

        return results

    def read_options_txt(self, path: str) -> dict:
        """
        Reads options.txt and returns a dictionary of key-value pairs.
        Handles both actual newlines and literal '\\n' sequences.
        """
        data = {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Some options.txt variants are entirely on one line with literal \n
            if "\\n" in content and "\n" not in content:
                lines = content.split("\\n")
            else:
                lines = content.splitlines()

            for line in lines:
                line = line.strip()
                if not line or ":" not in line:
                    continue

                key, value = line.split(":", 1)

                if value.lower() in ["true"]:
                    data[key] = 1
                elif value.lower() in ["false"]:
                    data[key] = 0
                else:
                    try:
                        data[key] = int(value)
                        continue
                    except ValueError:
                        pass
                    try:
                        data[key] = float(value)
                        continue
                    except ValueError:
                        pass
                    data[key] = value
        except Exception as e:
            print(f"Error reading options.txt: {e}")

        return data

    def write_options_txt(self, path: str, data: dict) -> bool:
        """
        Writes data back to options.txt, preserving existing lines and formatting where possible.
        """
        try:
            # First read all original lines
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            is_literal_newline = ("\\n" in content and "\n" not in content)

            if is_literal_newline:
                lines = content.split("\\n")
            else:
                lines = content.splitlines()

            new_lines = []
            keys_written = set()

            for line in lines:
                original_line = line.rstrip('\n')
                if not original_line or ":" not in original_line:
                    new_lines.append(original_line)
                    continue

                # Exact split
                key, _ = original_line.split(":", 1)

                # If this key is in our new data, update it
                if key in data:
                    new_val = data[key]
                    new_lines.append(f"{key}:{new_val}")
                    keys_written.add(key)
                else:
                    new_lines.append(original_line)

            # Append any keys that were in data but not in original file
            for k, v in data.items():
                if k not in keys_written:
                    new_lines.append(f"{k}:{v}")

            # Re-join with the same method it was split
            join_char = "\\n" if is_literal_newline else "\n"

            with open(path, 'w', encoding='utf-8') as f:
                f.write(join_char.join(new_lines))

            return True
        except Exception as e:
            print(f"Error writing options.txt: {e}")
            return False
