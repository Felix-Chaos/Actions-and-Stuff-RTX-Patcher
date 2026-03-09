"""
Interactive Version Editor
Manages src/version.py
"""

import os
import re
import datetime

VERSION_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "version.py")

def cls():
    os.system('cls' if os.name=='nt' else 'clear')

def get_current_version():
    if not os.path.exists(VERSION_FILE):
        return "0.0.0"
    
    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        content = f.read()
        match = re.search(r'VERSION = "(\d+)\.(\d+)\.(\d+)"', content)
        if match:
            return ".".join(match.groups())
    return "0.0.0"

def save_version(version_str):
    today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    content = f'# Auto-generated version file\nVERSION = "{version_str}"\nBUILD_DATE = "{today}"\n'
    
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\n[OK] Version updated to {version_str}")

def parse_version(v_str):
    try:
        return list(map(int, v_str.split(".")))
    except:
        return [0, 0, 0]

def main():
    while True:
        cls()
        current_ver = get_current_version()
        v_parts = parse_version(current_ver)
        
        print(f"==========================================")
        print(f"  VERSION MANAGER - Current: {current_ver}")
        print(f"==========================================\n")
        
        print(f"  [1] Bump PATCH ({v_parts[0]}.{v_parts[1]}.{v_parts[2]} -> {v_parts[0]}.{v_parts[1]}.{v_parts[2]+1})")
        print(f"  [2] Bump MINOR ({v_parts[0]}.{v_parts[1]}.{v_parts[2]} -> {v_parts[0]}.{v_parts[1]+1}.0)")
        print(f"  [3] Bump MAJOR ({v_parts[0]}.{v_parts[1]}.{v_parts[2]} -> {v_parts[0]+1}.0.0)")
        print(f"  [4] Set Custom Version")
        print(f"  [5] Exit\n")
        
        choice = input("Select an option: ")
        
        if choice == "1":
            v_parts[2] += 1
            save_version(f"{v_parts[0]}.{v_parts[1]}.{v_parts[2]}")
        elif choice == "2":
            v_parts[1] += 1
            v_parts[2] = 0
            save_version(f"{v_parts[0]}.{v_parts[1]}.{v_parts[2]}")
        elif choice == "3":
            v_parts[0] += 1
            v_parts[1] = 0
            v_parts[2] = 0
            save_version(f"{v_parts[0]}.{v_parts[1]}.{v_parts[2]}")
        elif choice == "4":
            new_ver = input("\nEnter version (X.Y.Z): ")
            if re.match(r'^\d+\.\d+\.\d+$', new_ver):
                save_version(new_ver)
            else:
                input("\n[ERROR] Invalid format. Press Enter...")
                continue
        elif choice == "5":
            break
            
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()
