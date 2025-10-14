from typing import Dict, Any
import os

# --- DEFAULT CONFIGURATION CONSTANTS ---
CONFIG: Dict[str, Any] = {
    "paths": {
        "minecraft_uwp": os.path.expandvars(r"%LocalAppData%/Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState"),
        "minecraft_beta": os.path.expandvars(r"%LocalAppData%/Packages/Microsoft.MinecraftWindowsBeta_8wekyb3d8bbwe/LocalState"),
        "xdelta_dir": "xdelta3",
    },
    "executables": {
        "xdelta": os.path.abspath("xdelta3/exec/xdelta3_x86_64_win.exe")
    },
    "filenames": {
        "encrypted_zip": "Actions & Stuff encrypted.zip",
        "normalized_zip": "Actions & Stuff decrypted.zip", # --- CHANGE: Updated filename ---
        "final_mcpack": "Actions & Stuff Enhanced RTX.mcpack",
        "icon": "AnSPatchericon.ico",
        "manifest": "manifest.json",
        "patch_config": "patch_config.json",
    },
    "patches": {
        "encrypted_v1": "Actions & Stuff encrypted.zip.vcdiff",
        "decrypted": "Actions & Stuff decrypted.zip.vcdiff",
    },
    "marketplace_pack_stats": {
        "v1": {"files": 16661, "dirs": 301}
    },
    "cleanup_prefixes": ["A&SforRTX", "Actions & Stuff Enhanced"],
    "files_to_remove": ["contents.json", "signatures.json", "splashes.json", "sounds.json"],
    "dirs_to_remove": ["texts"],
}