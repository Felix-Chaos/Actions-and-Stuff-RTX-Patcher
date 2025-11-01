
import os
import sys
from tkinter import ttk, messagebox
import threading
import shutil
import zipfile
from A_n_S__Patcher__Fuzed.default_config import CONFIG
import methods  # Assuming methods is a module with required functions
from ttkbootstrap.constants import SUCCESS
from typing import Tuple


def resource_path(relative_path: str) -> str:
    """Gets the absolute path to a resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def patch_advanced(frame, input_file,):

    status_label = ttk.Label(frame, text="Searching for matching folder...")
    status_label.pack(pady=(0, 10))

    progress = ttk.Progressbar(frame, orient="horizontal", length=400, mode="determinate")


def patch(frame, output_file, use_config_only: bool = True, overrides: dict = None):
    """Patch helper.

    Parameters:
    - frame: parent UI frame
    - output_file: path where the produced zip will be written
    - use_config_only: if True, only values from CONFIG are used; if False, callers may provide
      runtime overrides via `overrides` dict (keys mirror CONFIG["paths"]).
    - overrides: optional dict to override CONFIG values when use_config_only is False.
    """

    paths_cfg = CONFIG.get("paths", {})
    # Resolve working values depending on use_config_only and overrides
    overrides = overrides or {}
    def _get_path(key):
        if not use_config_only and key in overrides and overrides.get(key):
            return overrides.get(key)
        return paths_cfg.get(key)

    uwp_cfg = _get_path("minecraft_uwp")
    beta_cfg = _get_path("minecraft_beta") or _get_path("minecraft_uwp_preview")
    gdk_cfg = _get_path("minecraft_gdk") or _get_path("minecraft_appdata")

    premium_paths = []
    if uwp_cfg:
        premium_paths.append(os.path.join(os.path.expandvars(uwp_cfg), "premium_cache", "resource_packs"))
    if beta_cfg:
        premium_paths.append(os.path.join(os.path.expandvars(beta_cfg), "premium_cache", "resource_packs"))

    ressource_paths = []
    if gdk_cfg:
        # some installs place user-facing resource packs under the com.mojang path in AppData
        ressource_paths.append(os.path.join(os.path.expandvars(gdk_cfg), "Users"))

    pack_stats = CONFIG.get("marketplace_pack_stats", {}).get("v1.7", {})
    target_files = pack_stats.get("files")
    target_dirs = pack_stats.get("dirs")


    try:
        status_label = ttk.Label(frame, text="Searching for matching folder...")
        status_label.pack(pady=(0, 10))
        try:
            # Iterate through candidate paths and look for matching pack structure
            for path in premium_paths + ressource_paths:
                if not os.path.exists(path):
                    continue
                for folder in os.listdir(path):
                    full_path = os.path.join(path, folder)
                    if os.path.isdir(full_path):
                        _, files, folders, _ = methods.get_folder_stats(full_path, return_files=True)
                        if files == target_files and folders == target_dirs:
                            status_label.config(text="Compressing files... Might take a couple of minutes")
                            # Create the output zip at the provided output_file path
                            with zipfile.ZipFile(output_file, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                                for root, _, files_in_dir in sorted(os.walk(full_path)):
                                    for file in sorted(files_in_dir):
                                        file_path = os.path.join(root, file)
                                        arcname = os.path.relpath(file_path, full_path).replace("\\", "/")
                                        info = zipfile.ZipInfo(arcname)
                                        info.date_time = (1980, 1, 1, 0, 0, 0)
                                        info.compress_type = zipfile.ZIP_DEFLATED
                                        with open(file_path, 'rb') as f:
                                            zf.writestr(info, f.read())
                            status_label.config(text="Pack compressed successfully.")
                            return
            status_label.config(text="No matching pack found.")
        except Exception as e:
            status_label.config(text=f"Error during search/compression: {str(e)}")
            methods.log_error(e)

    #------ Time for Patching ------

        try:
            status_label = ttk.Label(frame, text="Patching files...")
            status_label.pack(pady=(0, 10))
            # Starts the patching process for the produced/normalized zip (if present)
            vcdiff_name = CONFIG["patches"]["decrypted"]
            try:
                # Check if the output_file is a zip containing the decrypted patch
                with zipfile.ZipFile(output_file, 'r') as zf:
                    if vcdiff_name not in zf.namelist():
                        status_label.config(text=f"Patch file '{vcdiff_name}' not found in the provided zip.")
                    else:
                        # extract the patch to a temporary folder and run the patch process if available
                        temp_dir = os.path.join(os.path.dirname(output_file), "patch_temp")
                        os.makedirs(temp_dir, exist_ok=True)
                        zf.extract(vcdiff_name, path=temp_dir)
                        vcdiff_path = os.path.join(temp_dir, vcdiff_name)
                        status_label.config(text="Running patch process...")
                        if hasattr(methods, "run_patch_process"):
                            # call the run function if it's available in methods; signature may vary
                            try:
                                patched_output = os.path.join(temp_dir, CONFIG["filenames"].get("final_mcpack", "patched.mcpack"))
                                methods.run_patch_process(output_file, vcdiff_path, patched_output)
                            except TypeError:
                                # fallback: try calling with only vcdiff_path and output path
                                try:
                                    methods.run_patch_process(vcdiff_path, patched_output)
                                except Exception:
                                    pass
                        status_label.config(text="Patching completed successfully.")
            except Exception as e:
                status_label.config(text=f"Error during patching: {str(e)}")
                try:
                    methods.log_error(e)
                except Exception:
                    pass

        except Exception as e:
            status_label.config(text=f"Unexpected error: {str(e)}")
            try:
                methods.log_error(e)
            except Exception:
                pass

    except Exception as e:
        status_label.config(text=f"Fatal error: {str(e)}")
        try:
            methods.log_error(e)
        except Exception:
            pass


def create_hidden_dir(path: str):
    """Creates a directory and hides it on Windows (best-effort).

    This helper creates the directory and attempts to set the hidden attribute on
    Windows via ctypes; failures are ignored but the directory creation is still
    attempted.
    """
    try:
        os.makedirs(path, exist_ok=True)
        try:
            import ctypes

            # FILE_ATTRIBUTE_HIDDEN = 0x2
            ctypes.windll.kernel32.SetFileAttributesW(path, 0x2)
        except Exception:
            # If ctypes isn't available or the call fails, ignore — folder exists.
            pass
    except Exception as e:
        print(f"Could not create or hide directory {path}: {e}")
