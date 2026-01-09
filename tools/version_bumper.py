import os
import re
import datetime

VERSION_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "version.py")

def bump_version():
    if not os.path.exists(VERSION_FILE):
        print(f"Error: {VERSION_FILE} not found.")
        return

    with open(VERSION_FILE, "r") as f:
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

    with open(VERSION_FILE, "w") as f:
        f.write(new_content)
    
    print(f"Version bumped to {new_version} (Build Date: {today})")

if __name__ == "__main__":
    bump_version()
