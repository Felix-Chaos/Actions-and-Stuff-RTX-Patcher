import os
import shutil
import time
import zipfile
import threading
from typing import Tuple, List, Callable, Optional

class FileSystemModel:
    def getFolderStats(self, folder: str) -> Tuple[int, int]:
        """Calculates the number of files and subfolders within a directory."""
        fileCount, folderCount = 0, 0
        try:
            for _, dirs, files in os.walk(folder):
                folderCount += len(dirs)
                fileCount += len(files)
        except OSError:
            return 0, 0
        return fileCount, folderCount

    def robustCleanup(self, folderPath: str, retries: int = 3, delay: float = 0.5) -> bool:
        """Attempts to delete a folder multiple times to overcome potential file locks."""
        for i in range(retries):
            try:
                if os.path.exists(folderPath):
                    shutil.rmtree(folderPath)
                return True
            except OSError:
                time.sleep(delay)
        return False

    def compressDeterministic(self, folderPath: str, outputZip: str, cancelEvent: threading.Event = None, progressCallback: Optional[Callable[[int, int], None]] = None, logCallback: Optional[Callable[[str], None]] = None) -> bool:
        """Creates a zip file with a fixed timestamp and correct file order."""
        try:
            totalFiles = sum(len(files) for _, _, files in os.walk(folderPath))
            if totalFiles == 0: return True
            processedFiles = 0
            
            with zipfile.ZipFile(outputZip, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in sorted(os.walk(folderPath)):
                    if cancelEvent and cancelEvent.is_set(): return False
                    for file in sorted(files):
                        if cancelEvent and cancelEvent.is_set(): return False
                        
                        filePath = os.path.join(root, file)
                        # Ensure forward slashes for consistency across platforms/tools
                        arcname = os.path.relpath(filePath, folderPath).replace("\\", "/")
                        
                        info = zipfile.ZipInfo(arcname)
                        # Fixed timestamp: Jan 1, 1980
                        info.date_time = (1980, 1, 1, 0, 0, 0)
                        info.compress_type = zipfile.ZIP_DEFLATED
                        
                        with open(filePath, 'rb') as f:
                            zf.writestr(info, f.read())
                        
                        processedFiles += 1
                        if logCallback and processedFiles % 50 == 0: # Log every 50 files to avoid spamming UI too much
                             logCallback(f"Zipping: {arcname}")
                        if progressCallback:
                            progressCallback(processedFiles, totalFiles)
            return True
        except (OSError, zipfile.BadZipFile):
            return False

    def scanDirectory(self, path: str, prefixes: List[str], cancelEvent: threading.Event = None) -> List[str]:
        foundFolders = []
        if not os.path.exists(path):
            return foundFolders
        
        try:
            for folder in os.listdir(path):
                if cancelEvent and cancelEvent.is_set(): return foundFolders
                
                # Check prefixes
                if any(folder.startswith(p) for p in prefixes):
                    fullPath = os.path.join(path, folder)
                    foundFolders.append(fullPath)
        except OSError:
            pass
            
        return foundFolders
