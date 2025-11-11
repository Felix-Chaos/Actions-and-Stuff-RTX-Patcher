
import os
import sys
import zipfile
import subprocess
import threading
import ctypes
from typing import Tuple, Callable

from default_config import CONFIG


def resource_path(relative_path: str) -> str:
    """Gets the absolute path to a resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def get_folder_stats(folder: str, return_files: bool = False) -> Tuple[int, int, int, list]:
    """Calculates folder stats (size, file count, folder count)."""
    total_size = 0
    file_count = 0
    folder_count = 0
    file_list = []

    for root, dirs, files in os.walk(folder):
        folder_count += len(dirs)
        file_count += len(files)
        for f in files:
            try:
                fp = os.path.join(root, f)
                if return_files:
                    file_list.append(fp)
                total_size += os.path.getsize(fp)
            except OSError:
                pass
    return total_size, file_count, folder_count, file_list


def compress_deterministic(folder_path: str, output_zip: str):
    """Creates a deterministic zip file from a folder."""
    with zipfile.ZipFile(output_zip, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in sorted(os.walk(folder_path)):
            for file in sorted(files):
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path).replace("\\\\", "/")
                info = zipfile.ZipInfo(arcname)
                info.date_time = (1980, 1, 1, 0, 0, 0)
                info.compress_type = zipfile.ZIP_DEFLATED
                with open(file_path, 'rb') as f:
                    zf.writestr(info, f.read())


def run_patch(source_file: str, patch_file: str, output_file: str, status_callback: Callable, completion_callback: Callable):
    """Runs the xdelta3 patch in a separate thread."""
    def patch_thread():
        try:
            exe_path = resource_path(os.path.join("tools", "xdelta3.exe"))
            if not os.path.exists(exe_path):
                raise FileNotFoundError("xdelta3 executable not found at: " + exe_path)
            status_callback("Patching...")
            cmd = f'"{exe_path}" -v -d -s "{source_file}" "{patch_file}" "{output_file}"'
            subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
            status_callback("Patch applied successfully!")
            create_mcpack(output_file)
            completion_callback(True, "Patch applied successfully!")
        except subprocess.CalledProcessError as e:
            error_message = f"Patching failed:\\n{e.stderr}"
            status_callback("Error during patching.")
            completion_callback(False, error_message)
        except Exception as e:
            error_message = f"An unexpected error occurred:\\n{e}"
            status_callback("An unexpected error occurred.")
            completion_callback(False, error_message)
    threading.Thread(target=patch_thread, daemon=True).start()


def create_mcpack(output_file: str):
    """Renames the output file to .mcpack, hides it, and executes it."""
    try:
        mcpack_file = os.path.splitext(output_file)[0] + ".mcpack"
        os.rename(output_file, mcpack_file)
        ctypes.windll.kernel32.SetFileAttributesW(mcpack_file, 2)
        os.startfile(mcpack_file)
    except Exception as e:
        print(f"Failed to create or execute mcpack file: {e}")


def patch_marketplace(output_file: str, status_callback: Callable, completion_callback: Callable, use_config_only: bool = True, overrides: dict = None):
    """Patches from the marketplace."""
    paths_cfg = CONFIG.get("paths", {})
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

    resource_paths = []
    if gdk_cfg:
        resource_paths.append(os.path.join(os.path.expandvars(gdk_cfg), "Users"))

    patch_versions = CONFIG.get("patch_versions", {})
    found_folder = None
    selected_patch_file = None

    for version, version_data in patch_versions.items():
        target_files = version_data["stats"]["files"]
        target_dirs = version_data["stats"]["dirs"]
        for path in premium_paths + resource_paths:
            if not os.path.exists(path):
                continue
            for folder in os.listdir(path):
                full_path = os.path.join(path, folder)
                if os.path.isdir(full_path):
                    _, files, folders, _ = get_folder_stats(full_path, return_files=True)
                    if files == target_files and folders == target_dirs:
                        found_folder = full_path
                        selected_patch_file = resource_path(version_data["patch_file"])
                        break
            if found_folder:
                break
        if found_folder:
            break

    if not found_folder:
        status_callback("No matching pack found.")
        completion_callback(False, "No matching pack found.")
        return

    status_callback(f"Found matching pack, compressing files...")
    temp_zip = os.path.join(os.path.dirname(output_file), "temp_vanilla.zip")
    compress_deterministic(found_folder, temp_zip)
    status_callback("Pack compressed successfully.")

    patch_file = resource_path(CONFIG["patches"]["marketplace_encrypted"])
    run_patch(temp_zip, patch_file, output_file, status_callback, completion_callback)


def patch_zip(source_zip: str, output_file: str, status_callback: Callable, completion_callback: Callable):
    """Patches from a user-selected zip file."""
    patch_file = resource_path(CONFIG["patches"]["zip_decrypted"])
    run_patch(source_zip, patch_file, output_file, status_callback, completion_callback)


def patch_advanced(source_file: str, patch_file: str, output_file: str, status_callback: Callable, completion_callback: Callable):
    """Advanced patcher function."""
    patch_zip(source_file, output_file, status_callback, completion_callback)
