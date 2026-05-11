import hashlib
import os

def get_hash(filepath):
    if not os.path.exists(filepath): return None
    sha256 = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for block in iter(lambda: f.read(65536), b""):
                sha256.update(block)
        return sha256.hexdigest()
    except:
        return None

patched_dir = "B:/Download/A&SforRTX (2)/A&SforRTX"
decrypted_dir = "B:/Download/Tools.and.stuff (1)/output/Actions & Stuff 1.9.1 (resources)"

dec_hashes = {}
for r, d, files in os.walk(decrypted_dir):
    for f in files:
        path = os.path.join(r, f)
        h = get_hash(path)
        if h:
            dec_hashes[h] = os.path.relpath(path, decrypted_dir)

print(f"Loaded {len(dec_hashes)} hashes from vanilla.")

for r, d, files in os.walk(patched_dir):
    for f in files:
        if f == "textures_list.json":
            path = os.path.join(r, f)
            h = get_hash(path)
            rel = os.path.relpath(path, patched_dir)
            print(f"\nChecking: {rel}")
            print(f"Hash: {h}")
            if h in dec_hashes:
                print(f"  -> MATCH FOUND! It perfectly matches Vanilla file: {dec_hashes[h]}")
                print(f"  -> Because of this match, create_patch_v2.py will REPLACE this file with the ENCRYPTED version of '{dec_hashes[h]}'.")
            else:
                print("  -> NO MATCH. This file should remain UNENCRYPTED in the mix.")
