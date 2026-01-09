import subprocess
import os
import ctypes
from typing import Tuple, Optional, Callable

class PatcherModel:
    """
    Handles the interaction with external patching tools (xdelta3) and Minecraft packaging.
    """

    def runPatch(self, xdeltaPath: str, sourceZip: str, patchFile: str, outputFile: str, logCallback: Optional[Callable[[str], None]] = None) -> Tuple[bool, str]:
        """
        Executes the XDelta3 patch process to apply a VCDIFF patch to a source ZIP file.

        Args:
            xdeltaPath (str): Absolute path to the xdelta3 executable.
            sourceZip (str): Input ZIP file (vanilla content).
            patchFile (str): VCDIFF patch file absolute path.
            outputFile (str): Path where the patched file will be written.
            logCallback (Callable, optional): Function to receive stdout logging from xdelta.

        Returns:
            Tuple[bool, str]: (Success, Message/Error Details).
        """
        try:
            if not os.path.exists(xdeltaPath):
                 return False, f"Patcher executable not found at: {xdeltaPath}"

            # Ensure the output directory exists preventing IO errors
            os.makedirs(os.path.dirname(outputFile), exist_ok=True)

            # Construct the command arguments for xdelta3
            # -v: verbose, -d: decompress, -s: source
            command = [xdeltaPath, "-v", "-d", "-s", sourceZip, patchFile, outputFile]
            
            # Configure subprocess to suppress the window on Windows
            creationFlags = 0
            startupinfo = None
            if os.name == 'nt':
                creationFlags = subprocess.CREATE_NO_WINDOW
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            # Execute the process
            process = subprocess.Popen(
                command, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, # Merge stderr into stdout to capture errors
                text=True, 
                creationflags=creationFlags,
                startupinfo=startupinfo,
                bufsize=1,            # Line buffered for real-time logging
                universal_newlines=True
            )
            
            # Read output stream line by line
            for line in process.stdout:
                line = line.strip()
                if line and logCallback:
                    logCallback(line)
            
            process.wait()
            
            if process.returncode != 0:
                return False, f"Patching failed with exit code {process.returncode}"
                
            return True, "Patch applied successfully."
            
        except subprocess.CalledProcessError as e:
            # Captures potential failures if check=True was used (not used here, but good practice to handle)
            details = e.stderr.strip() if e.stderr else "No additional details."
            return False, f"Patching execution failed: {details}"
        except Exception as e:
            return False, f"Unexpected system error during patch: {str(e)}"

    def createMcPack(self, outputFile: str) -> Tuple[bool, str]:
        """
        Finalizes the patched file by remaining it to .mcpack and launching it.
        
        Args:
            outputFile (str): The path to the patched output file (usually .zip or .mcpack).

        Returns:
            Tuple[bool, str]: (Success, Final Filename OR Error Message).
        """
        try:
            # Change extension to .mcpack which Minecraft recognizes
            mcpackFile = os.path.splitext(outputFile)[0] + ".mcpack"
            
            # Atomic-ish rename
            if outputFile != mcpackFile:
                # Remove existing target if present to allow restart/overwrite
                if os.path.exists(mcpackFile):
                    os.remove(mcpackFile)
                os.rename(outputFile, mcpackFile)
            else:
                # File already has correct name/extension
                mcpackFile = outputFile
            
            # Windows Specific: Hide the file to keep the folder clean for the user
            # (Requested feature: "The zip patcher seems broken... hidden file logic")
            try:
                if os.name == 'nt':
                    # FILE_ATTRIBUTE_HIDDEN = 2
                    ctypes.windll.kernel32.SetFileAttributesW(mcpackFile, 2) 
            except Exception:
                pass # Non-critical if attribute setting fails

            # Launch the file with the associated program (Minecraft)
            os.startfile(mcpackFile)
            return True, mcpackFile
            
        except Exception as e:
            return False, f"Failed to install/launch pack: {str(e)}"
