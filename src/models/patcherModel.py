"""
PatcherModel Module

This module provides the PatcherModel class which handles the interaction
with external patching tools (xdelta3) and packaging the final Minecraft files.
"""

import subprocess
import os
import ctypes
from typing import Tuple, Optional, Callable

class PatcherModel:
    """
    Handles the interaction with external patching tools (xdelta3) and Minecraft packaging.
    """

    def runPatch(self, xdelta_path: str, source_zip: str, patch_file: str, output_file: str, log_callback: Optional[Callable[[str], None]] = None) -> Tuple[bool, str]:
        """
        Executes the XDelta3 patch process to apply a VCDIFF patch to a source ZIP file.

        Args:
            xdelta_path (str): Absolute path to the xdelta3 executable.
            source_zip (str): Input ZIP file (vanilla content).
            patch_file (str): VCDIFF patch file absolute path.
            output_file (str): Path where the patched file will be written.
            log_callback (Callable, optional): Function to receive stdout logging from xdelta.

        Returns:
            Tuple[bool, str]: (Success, Message/Error Details).
        """
        try:
            if not os.path.exists(xdelta_path):
                return False, f"Patcher executable not found at: {xdelta_path}"

            # Ensure the output directory exists preventing IO errors
            os.makedirs(os.path.dirname(output_file), exist_ok=True)

            # Check if output file exists and is locked
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except OSError:
                    return False, f"Output file is locked: {output_file}\nPlease close Minecraft or any program using this file and try again."

            # Construct the command arguments for xdelta3
            # -v: verbose, -d: decompress, -s: source, -f: force overwrite
            command = [xdelta_path, "-f", "-v", "-d", "-s", source_zip, patch_file, output_file]

            # Configure subprocess to suppress the window on Windows
            creation_flags = 0
            startupinfo = None
            if os.name == 'nt':
                creation_flags = subprocess.CREATE_NO_WINDOW
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            # Execute the process
            with subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Merge stderr into stdout to capture errors
                text=True,
                creationflags=creation_flags,
                startupinfo=startupinfo,
                bufsize=1,            # Line buffered for real-time logging
                universal_newlines=True
            ) as process:

                # Read output stream line by line
                accumulated_logs = []
                if process.stdout:
                    for line in process.stdout:
                        line = line.strip()
                        if line:
                            accumulated_logs.append(line)
                            if log_callback:
                                log_callback(line)

                process.wait()

                if process.returncode != 0:
                    # Include last 5 lines of log in error message for debugging
                    error_tail = "\n".join(accumulated_logs[-5:]) if accumulated_logs else "No output."
                    return False, f"Patching failed with exit code {process.returncode}\nDetails:\n{error_tail}"

            return True, "Patch applied successfully."

        except subprocess.CalledProcessError as e:
            # Captures potential failures if check=True was used (not used here, but good practice to handle)
            details = e.stderr.strip() if e.stderr else "No additional details."
            return False, f"Patching execution failed: {details}"
        except Exception as e:
            return False, f"Unexpected system error during patch: {str(e)}"

    def createMcPack(self, output_file: str) -> Tuple[bool, str]:
        """
        Finalizes the patched file by remaining it to .mcpack and launching it.

        Args:
            output_file (str): The path to the patched output file (usually .zip or .mcpack).

        Returns:
            Tuple[bool, str]: (Success, Final Filename OR Error Message).
        """
        try:
            # Change extension to .mcpack which Minecraft recognizes
            mcpack_file = os.path.splitext(output_file)[0] + ".mcpack"

            # Atomic-ish rename
            if output_file != mcpack_file:
                # Remove existing target if present to allow restart/overwrite
                if os.path.exists(mcpack_file):
                    os.remove(mcpack_file)
                os.rename(output_file, mcpack_file)
            else:
                # File already has correct name/extension
                mcpack_file = output_file

            # Windows Specific: Hide the file to keep the folder clean for the user
            # (Requested feature: "The zip patcher seems broken... hidden file logic")
            try:
                if os.name == 'nt':
                    # FILE_ATTRIBUTE_HIDDEN = 2
                    ctypes.windll.kernel32.SetFileAttributesW(mcpack_file, 2)
            except Exception:
                pass # Non-critical if attribute setting fails

            # Launch the file with the associated program (Minecraft)
            os.startfile(mcpack_file)
            return True, mcpack_file

        except Exception as e:
            return False, f"Failed to install/launch pack: {str(e)}"
