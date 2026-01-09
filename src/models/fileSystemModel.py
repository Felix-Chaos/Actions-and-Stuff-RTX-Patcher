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
            Tuple[int, int]: A tuple containing (fileCount, folderCount).
                             Returns (0, 0) if the folder cannot be accessed.
        """
        fileCount, folderCount = 0, 0
        try:
            for _, dirs, files in os.walk(folder):
                folderCount += len(dirs)
                fileCount += len(files)
        except OSError as e:
            # Silently fail for now, but in a robust system we might want to log this.
            return 0, 0
        return fileCount, folderCount

    def robustCleanup(self, folderPath: str, retries: int = 3, delay: float = 0.5) -> bool:
        """
        Safely deletes a directory tree, handling potential file locks or permission issues.
        
        Args:
            folderPath (str): The path to the directory to delete.
            retries (int): Number of times to retry deletion (default: 3).
            delay (float): Seconds to wait between retries (default: 0.5).

        Returns:
            bool: True if deletion was successful (or path didn't exist), False otherwise.
        """
        for i in range(retries):
            try:
                if os.path.exists(folderPath):
                    shutil.rmtree(folderPath)
                return True
            except OSError:
                # File might be locked by another process (e.g. Explorer or Antivirus)
                # Wait a bit and try again
                time.sleep(delay)
        return False

    def compressDeterministic(self, folderPath: str, outputZip: str, cancelEvent: threading.Event = None, progressCallback: Optional[Callable[[int, int], None]] = None, logCallback: Optional[Callable[[str], None]] = None) -> bool:
        """
        Compresses a directory into a ZIP file with deterministic settings (fixed timestamps).
        
        This ensures that zipping the same content always produces the exact same binary output,
        which is crucial for consistent hashing and patching.

        Args:
            folderPath (str): Source directory to compress.
            outputZip (str): Destination ZIP file path.
            cancelEvent (threading.Event, optional): Event to check for user cancellation.
            progressCallback (Callable, optional): Function accepting (current, total) for progress updates.
            logCallback (Callable, optional): Function accepting a string message for logging.

        Returns:
            bool: True if compression completed successfully, False if cancelled or failed.
        """
        try:
            # 1. Count total files for progress tracking
            totalFiles = sum(len(files) for _, _, files in os.walk(folderPath))
            if totalFiles == 0:
                if logCallback: logCallback("Warning: Source folder is empty.")
                return True # Nothing to zip, but not technically a failure
            
            processedFiles = 0
            
            # 2. Create the ZIP file
            # ZIP_DEFLATED provides standard compression.
            with zipfile.ZipFile(outputZip, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                
                # Walk the directory tree (sorted for deterministic order)
                for root, _, files in sorted(os.walk(folderPath)):
                    if cancelEvent and cancelEvent.is_set():
                        if logCallback: logCallback("Compression cancelled by user.")
                        return False
                    
                    for file in sorted(files):
                        if cancelEvent and cancelEvent.is_set(): return False
                        
                        filePath = os.path.join(root, file)
                        
                        # Normalize path separators to forward slashes for ZIP compatibility
                        arcname = os.path.relpath(filePath, folderPath).replace("\\", "/")
                        
                        # Create ZipInfo with fixed timestamp (Jan 1, 1980)
                        # This removes timestamp metadata variations
                        info = zipfile.ZipInfo(arcname)
                        info.date_time = (1980, 1, 1, 0, 0, 0)
                        info.compress_type = zipfile.ZIP_DEFLATED
                        
                        # Read and write file data
                        try:
                            with open(filePath, 'rb') as f:
                                zf.writestr(info, f.read())
                        except OSError as e:
                            if logCallback: logCallback(f"Error reading file {file}: {e}")
                            return False
                        
                        processedFiles += 1
                        
                        # Update progress (less frequently to reduce UI overhead)
                        if logCallback and processedFiles % 50 == 0: 
                             logCallback(f"Zipping: {arcname}")
                        if progressCallback:
                            progressCallback(processedFiles, totalFiles)
                            
            return True
            
        except (OSError, zipfile.BadZipFile) as e:
            if logCallback: logCallback(f"Critical Zip Error: {e}")
            return False

    def scanDirectory(self, path: str, prefixes: List[str], cancelEvent: threading.Event = None) -> List[str]:
        """
        Scans a directory for subfolders that start with any of the provided prefixes.
        
        Used to find installed versions of the resource pack (e.g. "Actions & Stuff...").

        Args:
            path (str): The root directory to scan.
            prefixes (List[str]): List of folder name prefixes to look for.
            cancelEvent (threading.Event, optional): To stop scanning early.

        Returns:
            List[str]: A list of absolute paths to matching folders.
        """
        foundFolders = []
        if not os.path.exists(path):
            return foundFolders
        
        try:
            for folder in os.listdir(path):
                if cancelEvent and cancelEvent.is_set(): return foundFolders
                
                # Check if folder name matches any prefix
                if any(folder.startswith(p) for p in prefixes):
                    fullPath = os.path.join(path, folder)
                    if os.path.isdir(fullPath):
                        foundFolders.append(fullPath)
        except OSError:
            # Permission warnings or access errors
            pass
            
        return foundFolders
