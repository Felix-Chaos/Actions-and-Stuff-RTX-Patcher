"""
Version Bumper Tool

This script updates the version information in `src/version.py` by incrementing
the patch version and updating the build date.
"""

import os
import re
import datetime

VERSION_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "version.py")

def bump_version():
    """
    Reads the current version, increments the patch number, and updates the file
    with the new version and current timestamp.
    """
    if not os.path.exists(VERSION_FILE):
        print(f"Error: {VERSION_FILE} not found.")
        return

    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract current version
    version_match = re.search(r'VERSION = "(\d+)\.(\d+)\.(\d+)"', content)
    if version_match:
        major, minor, patch = map(int, version_match.groups())
        # Simple logic: increment patch. You might want semantic logic later.
        patch += 1
        new_version = f"{major}.{minor}.{patch}"
    else:
        # Fallback if format is messed up
        new_version = "2.0.1"

    today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    new_content = f'# Auto-generated version file\nVERSION = "{new_version}"\nBUILD_DATE = "{today}"\n'

    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"Version bumped to {new_version} (Build Date: {today})")

if __name__ == "__main__":
    bump_version()
