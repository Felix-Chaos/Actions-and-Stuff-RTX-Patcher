import subprocess
import sys

def main():
    print("==================================================")
    print("  Starting Actions & Stuff RTX Patcher...")
    print("==================================================")
    print("Executing: npm run tauri dev\n")
    
    try:
        # Run the Tauri dev server
        subprocess.run(["npm", "run", "tauri", "dev"], shell=True, check=True)
    except subprocess.CalledProcessError:
        print("\n[INFO] Application closed or encountered an error.")
    except KeyboardInterrupt:
        print("\n[INFO] Application stopped by user.")

if __name__ == "__main__":
    main()
