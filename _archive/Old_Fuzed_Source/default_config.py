from typing import Dict, Any
import os

# --- DEFAULT CONFIGURATION CONSTANTS ---
CONFIG: Dict[str, Any] = {
    "paths": {
        # Windows Store / Package LocalState folders (used by some installs)
        "minecraft_uwp": os.path.expandvars(r"%LocalAppData%/Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState"),
        "minecraft_uwp_preview": os.path.expandvars(r"%LocalAppData%/Packages/Microsoft.MinecraftWindowsBeta_8wekyb3d8bbwe/LocalState"),
        # Roaming AppData locations used by some Bedrock installs
        "minecraft_gdk": os.path.expandvars(r"%AppData%/Minecraft Bedrock"),
        "minecraft_gdk_preview": os.path.expandvars(r"%AppData%/Minecraft Bedrock Preview"),
        # New AppData-style keys (some users expect AppData paths under these names)
        # Prefer the Bedrock AppData location first, then the Preview one.
        "minecraft_appdata": os.path.expandvars(r"%AppData%/Minecraft Bedrock"),
        "minecraft_beta": os.path.expandvars(r"%AppData%/Minecraft Bedrock Preview"),
        "xdelta_dir": "xdelta3",
    },
    "executables": {
        "xdelta": os.path.abspath("xdelta3/exec/xdelta3_x86_64_win.exe")
    },
    "filenames": {
        "encrypted_zip": "Actions & Stuff encrypted.zip",
        "normalized_zip": "Actions & Stuff decrypted.zip", # --- CHANGE: Updated filename ---
        "final_zip": "Actions & Stuff Enhanced RTX.zip",
        "icon": "AnSPatchericon.ico",
        "manifest": "manifest.json",
        "patch_config": "patch_config.json",
    },
    "patches": {
        "marketplace_encrypted": "Patches/Marketplace/v1.7/patch.vcdiff",
        "zip_decrypted": "Patches/Zip/v1.7/patch.vcdiff",
    },
    "patch_versions": {
        "v1.7": {
            "patch_file": "Patches/Marketplace/v1.7/patch.vcdiff",
            "stats": {"files": 16661, "dirs": 301}
        },
        "v1.8": {
            "patch_file": "Patches/Marketplace/v1.8/patch.vcdiff",
            "stats": {"files": 17000, "dirs": 320}
        }
    },
    "marketplace_pack_stats": {
        "v1.7": {"files": 16661, "dirs": 301}
    },
    "zip_pack_stats": {
        "v1.7": {"files": 12951, "dirs": 161}
    },
    "cleanup_prefixes": ["A&SforRTX", "Actions & Stuff Enhanced"],
    #"files_to_remove": ["contents.json", "signatures.json", "splashes.json", "sounds.json"],
    #"dirs_to_remove": ["texts"],
}