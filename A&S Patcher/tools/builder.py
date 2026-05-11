"""
Python Build Manager for AnS RTX Patcher
Replaces build.bat with enhanced logging, coloring, and process management.
"""

import os
import sys
import subprocess
import time
import shutil
# import threading

# Add current directory to sys.path to ensure we can import tools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from tools import logger
    from tools.logger import Colors
    from tools import version_editor
except ImportError:
    # Fallback if running from tools/ dir directly
    import logger
    from logger import Colors
    import version_editor

# Configuration
SCRIPT_NAME = "main.py"
ICON_NAME = os.path.join("assets", "resources", "icon.ico")
OUTPUT_NAME = "AnS_RTX_Patcher_V2.exe"
DIST_FOLDER = "dist"


def cls():
    os.system("cls" if os.name == "nt" else "clear")


def check_dependencies():
    logger.log("INFO", "Checking Python dependencies...")
    required = ["PyInstaller", "PIL", "ttkbootstrap"]
    missing = []

    for req in required:
        try:
            if req == "PyInstaller":
                subprocess.check_call(
                    [sys.executable, "-c", "import PyInstaller"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            elif req == "PIL":
                subprocess.check_call(
                    [sys.executable, "-c", "import PIL"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.check_call(
                    [sys.executable, "-c", f"import {req}"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            logger.log("SUCCESS", f"{req} found.")
        except subprocess.CalledProcessError:
            logger.log("ERROR", f"{req} is MISSING.")
            missing.append(req)

    return missing


def install_dependencies(missing_list):
    logger.log("INFO", f"Attempting to install: {', '.join(missing_list)}")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pypiwin32"] + missing_list
        )
        logger.log("SUCCESS", "Dependencies installed successfully.")
        return True
    except subprocess.CalledProcessError:
        logger.log("ERROR", "Failed to install dependencies.")
        return False


def clean_build_files():
    logger.log("INFO", "Cleaning build artifacts...")
    dirs_to_clean = ["build", "dist"]
    files_to_clean = [f for f in os.listdir(".") if f.endswith(".spec")]

    for d in dirs_to_clean:
        if os.path.exists(d):
            try:
                shutil.rmtree(d)
                logger.log("INFO", f"Removed directory: {d}")
            except Exception as e:
                logger.log("ERROR", f"Failed to remove {d}: {e}")

    for f in files_to_clean:
        try:
            os.remove(f)
            logger.log("INFO", f"Removed file: {f}")
        except Exception as e:
            logger.log("WARNING", f"Failed to remove {f}: {e}")

    logger.log("SUCCESS", "Cleanup finished.")
    input("\nPress Enter to continue...")


def process_stream(pipe, prefix=""):
    """
    Reads from a pipe line by line and prints with color.
    """
    for line in iter(pipe.readline, ""):
        line_str = line.strip()
        if not line_str:
            continue

        # Color Logic
        if "ERROR:" in line_str or "Traceback" in line_str:
            print(f"{Colors.FAIL}{prefix}{line_str}{Colors.ENDC}")
        elif "WARNING:" in line_str:
            print(f"{Colors.WARNING}{prefix}{line_str}{Colors.ENDC}")
        elif "INFO:" in line_str:
            # Highlight INFO lines gently, or keep white?
            # User wanted colors. Let's make INFO typically blue/cyan if meaningful.
            # PyInstaller logs are ALL "INFO: ...", so maybe keep them standard or dim
            # unless specific keywords appear.
            print(f"{Colors.CYAN}{prefix}{line_str}{Colors.ENDC}")
        else:
            print(f"{prefix}{line_str}")

    pipe.close()


def run_build(console_mode=False):
    cls()
    mode_str = "DEBUG (Console)" if console_mode else "RELEASE (Windowed)"
    logger.log("INFO", f"Starting Build Process: {mode_str}")
    time.sleep(1)

    console_arg = "--console" if console_mode else "--windowed"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        console_arg,
        "--name",
        OUTPUT_NAME,
        "--icon",
        ICON_NAME,
        "--add-data",
        "assets;assets",
        "--add-data",
        "tools;tools",
        SCRIPT_NAME,
    ]

    logger.log("INFO", f"Executing: {' '.join(cmd)}")
    print("-" * 50)

    with subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # Merge stderr into stdout for single stream
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
    ) as process:
        # Process output in real-time
        process_stream(process.stdout)
        return_code = process.wait()
    print("-" * 50)

    if return_code == 0:
        logger.log("SUCCESS", "Build completed successfully!")
        dist_path = os.path.abspath(DIST_FOLDER)
        exe_path = os.path.join(dist_path, OUTPUT_NAME)
        logger.log("INFO", f"Output: {exe_path}")

        msg = input("\nOpen output folder? (Y/n): ").lower()
        if msg != "n":
            os.startfile(dist_path)
    else:
        logger.log("ERROR", f"Build failed with exit code {return_code}.")

    input("\nPress Enter to return to menu...")


def main_menu():
    while True:
        cls()
        print(f"{Colors.HEADER}======================================{Colors.ENDC}")
        print(f"{Colors.HEADER}    A.n.S RTX Patcher Build Manager    {Colors.ENDC}")
        print(f"{Colors.HEADER}======================================{Colors.ENDC}")
        print("")
        print(f"    [1] {Colors.GREEN}BUILD - Release (Windowed){Colors.ENDC}")
        print(f"    [2] {Colors.WARNING}BUILD - Debug (Console){Colors.ENDC}")
        print(f"    [3] {Colors.CYAN}UTILS - Version Editor{Colors.ENDC}")
        print(f"    [4] {Colors.BLUE}UTILS - Clean Artifacts{Colors.ENDC}")
        print(f"    [5] {Colors.FAIL}EXIT{Colors.ENDC}")
        print("")

        choice = input("Select an option: ")

        if choice == "1":
            run_build(console_mode=False)
        elif choice == "2":
            run_build(console_mode=True)
        elif choice == "3":
            version_editor.main()
        elif choice == "4":
            clean_build_files()
        elif choice == "5":
            sys.exit(0)


if __name__ == "__main__":
    # Ensure dependencies
    missing = check_dependencies()
    if missing:
        do_install = input("\nInstall missing? (Y/n): ").lower()
        if do_install != "n":
            install_dependencies(missing)
            input("\nInstalled. Press Enter...")

    main_menu()
