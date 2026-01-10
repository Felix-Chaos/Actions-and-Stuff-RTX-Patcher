import sys
import os

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.models.configModel import ConfigModel
from src.utils.helpers import resourcePath

def check_paths():
    print("Checking patch paths...")
    config = ConfigModel()
    versions = config.config.get("patchVersions", {})
    
    all_good = True
    
    for ver, data in versions.items():
        print(f"\nVer: {ver}")
        patches = data.get("patches", {})
        
        for key, relative_path in patches.items():
            abs_path = resourcePath(relative_path)
            exists = os.path.exists(abs_path)
            status = "OK" if exists else "MISSING"
            print(f"  [{status}] {key}: {relative_path}")
            if not exists:
                print(f"     -> Resolved closest: {abs_path}")
                all_good = False
                
    if all_good:
        print("\nAll patch files found.")
    else:
        print("\nSome patch files are missing.")

if __name__ == "__main__":
    check_paths()
