import subprocess
import os
import ctypes
from typing import Tuple, Optional, Callable

class PatcherModel:
    def runPatch(self, xdeltaPath: str, sourceZip: str, patchFile: str, outputFile: str, logCallback: Optional[Callable[[str], None]] = None) -> Tuple[bool, str]:
        """Runs the xdelta3 patch command."""
        try:
            if not os.path.exists(xdeltaPath):
                 return False, f"Patcher executable not found: {xdeltaPath}"

            # Ensure directories exist
            os.makedirs(os.path.dirname(outputFile), exist_ok=True)

            command = [xdeltaPath, "-v", "-d", "-s", sourceZip, patchFile, outputFile]
            
            # Run without window but capture stdout
            creationFlags = 0
            startupinfo = None
            if os.name == 'nt':
                creationFlags = subprocess.CREATE_NO_WINDOW
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            process = subprocess.Popen(
                command, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True, 
                creationflags=creationFlags,
                startupinfo=startupinfo,
                bufsize=1,            # Line buffered
                universal_newlines=True
            )
            
            # Stream output
            for line in process.stdout:
                line = line.strip()
                if line and logCallback:
                    logCallback(line)
            
            process.wait()
            
            if process.returncode != 0:
                return False, f"Patching failed with code {process.returncode}"
                
            return True, "Patch success"
        except subprocess.CalledProcessError as e:
            details = e.stderr.strip() if e.stderr else "No additional details from patcher."
            return False, f"Patching failed. Details: {details}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

    def createMcPack(self, outputFile: str) -> Tuple[bool, str]:
        """Renames the output file to .mcpack and executes it."""
        try:
            # Change extension
            # Change extension
            mcpackFile = os.path.splitext(outputFile)[0] + ".mcpack"
            
            if outputFile != mcpackFile:
                if os.path.exists(mcpackFile):
                    os.remove(mcpackFile)
                os.rename(outputFile, mcpackFile)
            else:
                # File already has correct name/extension
                mcpackFile = outputFile
            
            # Hide the file (optional, but requested in original code)
            try:
                if os.name == 'nt':
                    ctypes.windll.kernel32.SetFileAttributesW(mcpackFile, 2) # FILE_ATTRIBUTE_HIDDEN
            except Exception:
                pass # Not critical

            # Launch
            os.startfile(mcpackFile)
            return True, mcpackFile
        except Exception as e:
            return False, str(e)
