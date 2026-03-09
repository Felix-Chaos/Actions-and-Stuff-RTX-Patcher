"""
FileSystemModel Module

This module provides the FileSystemModel class which handles all file system
operations including scanning, compressing, and cleaning up directories.
"""

import os
import shutil
import time
import zipfile
import threading
from typing import Tuple, List, Callable, Optional


class FileSystemModel:
    """
    Handles all file system operations including scanning, compressing,
    and cleaning up directories.

    This model abstracts the OS-level interactions to provide a clean interface
    for the controllers.
    """

    def getFolderStats(self, folder: str) -> Tuple[int, int]:
        """
        Calculates the total number of files and subdirectories within a given folder.

        Args:
            folder (str): The absolute path to the directory to scan.

        Returns:
            Tuple[int, int]: A tuple containing (file_count, folder_count).
                             Returns (0, 0) if the folder cannot be accessed.
        """
        file_count, folder_count = 0, 0
        try:
            for _, dirs, files in os.walk(folder):
                folder_count += len(dirs)
                file_count += len(files)
        except OSError:
            # Silently fail for now, but in a robust system we might want to log this.
            return 0, 0
        return file_count, folder_count

    def robustCleanup(self, folder_path: str, retries: int = 3, delay: float = 0.5) -> bool:
        """
        Safely deletes a directory tree, handling potential file locks or permission issues.

        Args:
            folder_path (str): The path to the directory to delete.
            retries (int): Number of times to retry deletion (default: 3).
            delay (float): Seconds to wait between retries (default: 0.5).

        Returns:
            bool: True if deletion was successful (or path didn't exist), False otherwise.
        """
        for _ in range(retries):
            try:
                if os.path.exists(folder_path):
                    shutil.rmtree(folder_path)
                return True
            except OSError:
                # File might be locked by another process (e.g. Explorer or Antivirus)
                # Wait a bit and try again
                time.sleep(delay)
        return False

    def compressDeterministic(self, folder_path: str, output_zip: str, cancel_event: threading.Event = None, progress_callback: Optional[Callable[[int, int], None]] = None, log_callback: Optional[Callable[[str], None]] = None) -> bool:
        # pylint: disable=too-many-locals
        """
        Compresses a directory into a ZIP file with deterministic settings (fixed timestamps).

        Args:
            folder_path (str): Source directory to compress.
            output_zip (str): Destination ZIP file path.
            cancel_event (threading.Event, optional): Event to check for user cancellation.
            progress_callback (Callable, optional): Function accepting (current, total) for progress updates.
            log_callback (Callable, optional): Function accepting a string message for logging.

        Returns:
            bool: True if compression completed successfully, False if cancelled or failed.
        """
        try:
            # 1. Count total files for progress tracking
            total_files = sum(len(files)
                              for _, _, files in os.walk(folder_path))
            if total_files == 0:
                if log_callback:
                    log_callback("Warning: Source folder is empty.")
                return True  # Nothing to zip, but not technically a failure

            processed_files = 0

            # 2. Create the ZIP file
            # ZIP_STORED ensures no compression for bit-perfect output matching across OS/Python versions.
            with zipfile.ZipFile(output_zip, 'w', compression=zipfile.ZIP_STORED) as zf:

                # Walk the directory tree (sorted for deterministic order)
                for root, _, files in sorted(os.walk(folder_path)):
                    if cancel_event and cancel_event.is_set():
                        if log_callback:
                            log_callback("Compression cancelled by user.")
                        return False

                    for file in sorted(files):
                        if cancel_event and cancel_event.is_set():
                            return False

                        file_path = os.path.join(root, file)

                        # Normalize path separators to forward slashes for ZIP compatibility
                        arcname = os.path.relpath(
                            file_path, folder_path).replace("\\", "/")

                        # Create ZipInfo with fixed timestamp (Jan 1, 1980)
                        info = zipfile.ZipInfo(arcname)
                        info.date_time = (1980, 1, 1, 0, 0, 0)
                        info.compress_type = zipfile.ZIP_STORED

                        # Read and write file data
                        try:
                            with open(file_path, 'rb') as f:
                                zf.writestr(info, f.read())
                        except OSError as e:
                            if log_callback:
                                log_callback(f"Error reading file {file}: {e}")
                            return False

                        processed_files += 1

                        # Update progress (less frequently to reduce UI overhead)
                        if log_callback and processed_files % 50 == 0:
                            log_callback(f"Zipping: {arcname}")
                        if progress_callback:
                            progress_callback(processed_files, total_files)

            return True

        except (OSError, zipfile.BadZipFile) as e:
            if log_callback:
                log_callback(f"Critical Zip Error: {e}")
            return False

    def scanDirectory(self, path: str, prefixes: List[str], cancel_event: threading.Event = None) -> List[str]:
        """
        Scans a directory for subfolders that start with any of the provided prefixes.

        Args:
            path (str): The root directory to scan.
            prefixes (List[str]): List of folder name prefixes to look for.
            cancel_event (threading.Event, optional): To stop scanning early.

        Returns:
            List[str]: A list of absolute paths to matching folders.
        """
        found_folders = []
        if not os.path.exists(path):
            return found_folders

        try:
            for folder in os.listdir(path):
                if cancel_event and cancel_event.is_set():
                    return found_folders

                # Check if folder name matches any prefix
                if any(folder.startswith(p) for p in prefixes):
                    full_path = os.path.join(path, folder)
                    if os.path.isdir(full_path):
                        found_folders.append(full_path)
        except OSError:
            # Permission warnings or access errors
            pass

        return found_folders
