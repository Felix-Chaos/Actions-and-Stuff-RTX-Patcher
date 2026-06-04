import os
import subprocess

env = os.environ.copy()
with open(".env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip("'\"")

print("Running npm run tauri build with .env loaded...")
subprocess.run(["npm", "run", "tauri", "build"], env=env, shell=True)
