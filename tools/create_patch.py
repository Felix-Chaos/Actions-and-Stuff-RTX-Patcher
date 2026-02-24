import os
import sys
import shutil
import threading
import subprocess
import tempfile
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import json
from tkinter import filedialog, Listbox, END, messagebox

# Import deterministic compression logic
# Ensure the script directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from deterministic_zipper import compress_deterministic
except ImportError:
    # Fallback if running from root or elsewhere; try to find it
    pass

class PatchCreatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Patch Creator Tool")
        self.root.geometry("700x650")
        self.root.resizable(False, False)
        
        # Variables
        self.patched_dir = tb.StringVar()
        self.decrypted_dir = tb.StringVar()
        self.encrypted_dir = tb.StringVar()
        self.output_dir = tb.StringVar()

        self.check_env_and_setup_defaults()
        self.setup_ui()

    def check_env_and_setup_defaults(self):
        # Check if running as script (Dev Mode)
        if not getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Define paths
            input_root = os.path.join(base_dir, "_input")
            p_dir = os.path.join(input_root, "patched")
            d_dir = os.path.join(input_root, "decrypted")
            e_dir = os.path.join(input_root, "encrypted")
            
            # Output to ../assets/Patches/Current so App picks it up as default
            o_dir = os.path.abspath(os.path.join(base_dir, "..", "assets", "Patches", "Current"))
            
            # Create input dirs
            for path in [p_dir, d_dir]:
                os.makedirs(path, exist_ok=True)

            # Try to find Minecraft Encrypted pack
            # Prioritize "Minecraft Bedrock" (AppData) as UWP is becoming outdated
            candidates = [
                os.path.expandvars(r"%AppData%/Minecraft Bedrock/premium_cache/resource_packs"),
                os.path.expandvars(r"%LocalAppData%/Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState/premium_cache/resource_packs")
            ]
            
            mc_uuid = "7U5jWx4F4vc="
            found_mc = False
            for c in candidates:
                if os.path.exists(c):
                    # Check for specific UUID folder
                    uuid_path = os.path.join(c, mc_uuid)
                    if os.path.exists(uuid_path):
                         e_dir = uuid_path
                    else:
                         e_dir = c
                    found_mc = True
                    break
            
            if not found_mc:
                os.makedirs(e_dir, exist_ok=True)
            
            if not os.path.exists(o_dir):
                try:
                    os.makedirs(o_dir, exist_ok=True)
                except OSError:
                    pass # Output might be custom, but try to create default

            # Load persistent settings if available
            self.load_settings()

            # Set vars (only if not set by load_settings or if we want defaults to be fallbacks)
            # Actually, let's set defaults then override with settings
            if not self.patched_dir.get(): self.patched_dir.set(p_dir)
            if not self.decrypted_dir.get(): self.decrypted_dir.set(d_dir)
            if not self.encrypted_dir.get(): self.encrypted_dir.set(e_dir)
            if not self.output_dir.get(): self.output_dir.set(o_dir)

    def get_settings_path(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "tool_config.json")

    def load_settings(self):
        try:
            path = self.get_settings_path()
            if os.path.exists(path):
                with open(path, "r") as f:
                    data = json.load(f)
                    if "patched_dir" in data: self.patched_dir.set(data["patched_dir"])
                    if "decrypted_dir" in data: self.decrypted_dir.set(data["decrypted_dir"])
                    if "encrypted_dir" in data: self.encrypted_dir.set(data["encrypted_dir"])
                    # if "output_dir" in data: self.output_dir.set(data["output_dir"]) # Force default to ensure updates
                    if "inject_manifest" in data: self.inject_manifest.set(data["inject_manifest"])
        except Exception:
            pass

    def save_settings(self):
        try:
            data = {
                "patched_dir": self.patched_dir.get(),
                "decrypted_dir": self.decrypted_dir.get(),
                "encrypted_dir": self.encrypted_dir.get(),
                "output_dir": self.output_dir.get(),
                "inject_manifest": self.inject_manifest.get()
            }
            with open(self.get_settings_path(), "w") as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass
        
    def setup_ui(self):
        # Header
        lbl = tb.Label(self.root, text="Automated Patch Creator", font=("Helvetica", 16, "bold"))
        lbl.pack(pady=10)
        
        # 1. Patched Decrypted (Contains the changes - The "Goal" state)
        self.create_folder_input("1. Modified/Patched Folder (The result you want):", self.patched_dir)
        
        # 2. Decrypted (Original Reference)
        self.create_folder_input("2. Original Decrypted (Vanilla Reference):", self.decrypted_dir)
        
        # 3. Encrypted (Original Reference) + Stats
        self.create_folder_input("3. Original Encrypted (Vanilla Reference):", self.encrypted_dir, show_stats=True)

        # 4. Output Directory
        self.create_folder_input("Output Directory (For .xdelta files):", self.output_dir)

        # Options
        self.pack_version_var = tb.StringVar(value="v1.9.1")
        self.patch_version_var = tb.StringVar(value="1.0")

        input_frame = tb.Frame(self.root)
        input_frame.pack(fill=X, padx=10, pady=5)
        
        tb.Label(input_frame, text="Pack Version (e.g. v1.9.1):").pack(side=LEFT)
        tb.Entry(input_frame, textvariable=self.pack_version_var, width=15).pack(side=LEFT, padx=5)

        tb.Label(input_frame, text="Patch Version (e.g. 1.0):").pack(side=LEFT, padx=(10,0))
        tb.Entry(input_frame, textvariable=self.patch_version_var, width=15).pack(side=LEFT, padx=5)

        self.inject_manifest = tb.BooleanVar(value=True)
        tb.Checkbutton(input_frame, text="Inject Custom Manifest", 
                       variable=self.inject_manifest, bootstyle="round-toggle").pack(side=LEFT, padx=20)

        # Action Buttons
        btn_frame = tb.Frame(self.root)
        btn_frame.pack(pady=20)
        
        self.start_btn = tb.Button(btn_frame, text="Create Patches", bootstyle=SUCCESS, command=self.start_process)
        self.start_btn.pack(side=LEFT, padx=10)
        
        tb.Button(btn_frame, text="Clear Logs", bootstyle=SECONDARY, command=self.clear_logs).pack(side=LEFT, padx=10)
        
        # Log Box
        tb.Label(self.root, text="Progress Log:", bootstyle="secondary").pack(anchor=W, padx=10)
        self.log_box = Listbox(self.root, height=12, bg="#1e1e1e", fg="white", selectbackground="#444", highlightthickness=0)
        self.log_box.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

    def create_folder_input(self, label_text, variable, show_stats=False):
        frame = tb.Frame(self.root)
        frame.pack(fill=X, padx=10, pady=5)
        
        tb.Label(frame, text=label_text).pack(anchor=W)
        
        entry_frame = tb.Frame(frame)
        entry_frame.pack(fill=X)
        
        tb.Entry(entry_frame, textvariable=variable).pack(side=LEFT, fill=X, expand=True)
        tb.Button(entry_frame, text="Browse", command=lambda: self.browse_folder(variable)).pack(side=RIGHT, padx=5)

        if show_stats:
             tb.Button(entry_frame, text="Get Stats", bootstyle=INFO, 
                       command=lambda: self.show_stats(variable.get())).pack(side=RIGHT, padx=5)

    def show_stats(self, folder_path):
        if not folder_path or not os.path.exists(folder_path):
             messagebox.showerror("Error", "Folder does not exist.")
             return

        file_count = 0
        folder_count = 0
        try:
            for _, dirs, files in os.walk(folder_path):
                folder_count += len(dirs)
                file_count += len(files)
            
            msg = f"Stats for '{os.path.basename(folder_path)}':\n\nFiles: {file_count}\nFolders: {folder_count}"
            # Also print to log
            self.log_box.insert(END, f"Stats: Files={file_count}, Dirs={folder_count} ({folder_path})")
            self.log_box.yview_moveto(1.0)
            
            messagebox.showinfo("Folder Stats", msg)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to scan: {e}")

    def browse_folder(self, variable):
        path = filedialog.askdirectory()
        if path:
            variable.set(path)

    def log(self, message):
        self.log_box.insert(END, message)
        self.log_box.yview_moveto(1.0)
        
    def clear_logs(self):
        self.log_box.delete(0, END)

    def toggle_inputs(self, state):
        # Helper to disable buttons during processing
        state_val = "normal" if state else "disabled"
        self.start_btn.config(state=state_val)

    def start_process(self):
        # Validate
        p_dir = self.patched_dir.get()
        d_dir = self.decrypted_dir.get()
        e_dir = self.encrypted_dir.get()
        o_dir = self.output_dir.get()

        if not all([p_dir, d_dir, e_dir, o_dir]):
            messagebox.showerror("Error", "All folder paths are required.")
            return

        if not all([os.path.exists(p) for p in [p_dir, d_dir, e_dir]]):
             messagebox.showerror("Error", "One or more input paths do not exist.")
             return
        
        # Create output dir if it doesn't exist
        if not os.path.exists(o_dir):
            try:
                os.makedirs(o_dir, exist_ok=True)
            except OSError:
                messagebox.showerror("Error", f"Could not create output directory: {o_dir}")
                return

        self.save_settings()

        pack_ver = self.pack_version_var.get().strip() or "v1.9.1"
        patch_ver = self.patch_version_var.get().strip() or "1.0"

        self.toggle_inputs(False)
        threading.Thread(target=self.process_worker, args=(p_dir, d_dir, e_dir, o_dir, pack_ver, patch_ver), daemon=True).start()

    def process_worker(self, patched_dir, decrypted_dir, encrypted_dir, output_dir, pack_ver, patch_ver):
        try:
            temp_dir = os.path.join(tempfile.gettempdir(), "AnSPatcherTool")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)

            self.root.after(0, lambda: self.log("--- Starting Process ---"))
            
            # Paths for temporary zips
            target_zip = os.path.join(temp_dir, "target_patched.zip")
            source_dec_zip = os.path.join(temp_dir, "source_decrypted.zip")
            source_enc_zip = os.path.join(temp_dir, "source_encrypted.zip")

            # 1. Compress Patched Directory (Target)
            self.root.after(0, lambda: self.log("Preparing Patched Target (Copying)..."))
            temp_patched_target = os.path.join(temp_dir, "patched_target_files")
            if os.path.exists(temp_patched_target):
                shutil.rmtree(temp_patched_target)
            shutil.copytree(patched_dir, temp_patched_target)
            
            dir_to_compress_target = temp_patched_target

            if self.inject_manifest.get():
                self.root.after(0, lambda: self.log("Injecting manifest.json (Baseline) into Patched Target..."))
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                manifest_path = os.path.join(project_root, "assets", "resources", "manifest.json")
                if os.path.exists(manifest_path):
                    shutil.copyfile(manifest_path, os.path.join(dir_to_compress_target, "manifest.json"))
                    self.root.after(0, lambda: self.log("  ✓ Baseline Manifest injected into Patched Target."))
            
            self.root.after(0, lambda: self.log(f"Compressing Target: {os.path.basename(patched_dir)}..."))
            compress_deterministic(dir_to_compress_target, target_zip)
            
            # 2. Compress Decrypted Directory (Source 1)
            # Logic: Match patchController.py exactly (Cleanup + Manifest)
            
            # COPY to temp first so we can clean it without touching original
            self.root.after(0, lambda: self.log("Preparing Decrypted Source (Cleaning & Injecting)..."))
            temp_dec_source = os.path.join(temp_dir, "decrypted_source_files")
            if os.path.exists(temp_dec_source):
                shutil.rmtree(temp_dec_source)
            shutil.copytree(decrypted_dir, temp_dec_source)

            # CLEANUP: Must match ConfigModel.filesToRemove / dirsToRemove
            files_to_remove = ["contents.json", "signatures.json", "splashes.json", "sounds.json"]
            dirs_to_remove = ["texts"]

            for root, dirs, files in os.walk(temp_dec_source):
                for f in files:
                    if f in files_to_remove:
                        try:
                            os.remove(os.path.join(root, f))
                            # self.root.after(0, lambda: self.log(f"  - Removed {f}"))
                        except OSError: pass
                for d in list(dirs):
                    if d in dirs_to_remove:
                        try:
                            shutil.rmtree(os.path.join(root, d))
                            dirs.remove(d)
                            # self.root.after(0, lambda: self.log(f"  - Removed {d}/"))
                        except OSError: pass

            dir_to_compress_dec = temp_dec_source

            if self.inject_manifest.get():
                self.root.after(0, lambda: self.log("Injecting manifest.json (Baseline)..."))
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                # CRITICAL: Must use the SAME manifest as the App uses for normalization
                # App uses: assets/resources/manifest.json (Verified in patchController.py)
                manifest_path = os.path.join(project_root, "assets", "resources", "manifest.json")
                
                if os.path.exists(manifest_path):
                    shutil.copyfile(manifest_path, os.path.join(temp_dec_source, "manifest.json"))
                    self.root.after(0, lambda: self.log("  ✓ Baseline Manifest injected."))
                else:
                    self.root.after(0, lambda: self.log(f"  ⚠️ Warning: {manifest_path} not found."))
                
                dir_to_compress_dec = temp_dec_source

                # Dynamically update manifest if found (to match the Target if we want source to be versioned?)
                # WAIT. The App OVERWRITES the manifest with the generic one before patching.
                # So the Source used for patching MUST have the GENERIC manifest, unmodified.
                # If we modify it here with version numbers, it will MISMATCH the App which uses the static generic one.
                
                # So: We inject the manifest, but we do NOT modify it for the SOURCE.
                # The version info should be in the TARGET (Patched Directory).
                
                # ...Wait, if I don't modify it, how does the version get into the final pack?
                # The final pack comes from applying the patch to the source.
                # xdelta transforms Source -> Target.
                # If Target has version numbers, xdelta handles that diff.
                # Source MUST be the generic baseline.
                
                pass # removed the modification logic for SOURCE manifest to ensure hash match

                pass # removed the modification logic for SOURCE manifest to ensure hash match

            self.root.after(0, lambda: self.log(f"Compressing Source Decrypted: {os.path.basename(decrypted_dir)}..."))
            compress_deterministic(dir_to_compress_dec, source_dec_zip)
            
            # 3. Compress Encrypted Directory (Source 2)
            self.root.after(0, lambda: self.log(f"Compressing Source Encrypted: {os.path.basename(encrypted_dir)}..."))
            compress_deterministic(encrypted_dir, source_enc_zip)

            # 4. Generate Patches
            xdelta_path = os.path.join(os.path.dirname(__file__), "xdelta3.exe")
            if not os.path.exists(xdelta_path):
                 self.root.after(0, lambda: self.log("❌ xdelta3.exe not found in tools folder!"))
                 return

            # Use fixed filenames to match ConfigModel
            out_patch_dec = os.path.join(output_dir, "decrypted.vcdiff")
            out_patch_enc = os.path.join(output_dir, "encrypted.vcdiff")

             # Patch 1: Decrypted -> Patched
            self.root.after(0, lambda: self.log("Generating Patch: Decrypted -> Patched..."))
            self.run_xdelta(xdelta_path, source_dec_zip, target_zip, out_patch_dec)

            # Patch 2: Encrypted -> Patched

            self.root.after(0, lambda: self.log("Generating Patch: Encrypted -> Patched..."))
            self.run_xdelta(xdelta_path, source_enc_zip, target_zip, out_patch_enc)

            # Calculate stats for patched directory to put in config
            file_count = 0
            folder_count = 0
            for _, dirs, files in os.walk(patched_dir):
                folder_count += len(dirs)
                file_count += len(files)
            
            self.root.after(0, lambda: self.log(f"Calculated Patched Stats: {file_count} files, {folder_count} dirs"))

            # 5. Generate patch_config.json with Stats
            self.root.after(0, lambda: self.log("Generating patch_config.json..."))
            self.generate_patch_config(encrypted_dir, output_dir, pack_ver, patch_ver, file_count, folder_count)

            self.root.after(0, lambda: self.log("✅ All operations completed successfully!"))
            self.root.after(0, lambda: messagebox.showinfo("Done", "Patches created successfully."))

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.root.after(0, lambda err=e: self.log(f"❌ Error: {str(err)}"))
            self.root.after(0, lambda err=e: messagebox.showerror("Error", str(err)))
        finally:
            self.root.after(0, lambda: self.toggle_inputs(True))
            # Optional: cleanup temp_dir
            # shutil.rmtree(temp_dir, ignore_errors=True)

    def generate_patch_config(self, encrypted_dir, output_dir, pack_ver, patch_ver, patched_file_count, patched_folder_count):
        try:
            import hashlib
            # Calculate Validation Data (Logo Hash)
            logo_path = os.path.join(encrypted_dir, "pack_icon.png")
            logo_hash = None
            if os.path.exists(logo_path):
                 sha256 = hashlib.sha256()
                 with open(logo_path, "rb") as f:
                     for block in iter(lambda: f.read(4096), b""):
                         sha256.update(block)
                 logo_hash = sha256.hexdigest().lower()
                 self.root.after(0, lambda: self.log(f"  ✓ Calculated Logo Hash: {logo_hash[:8]}..."))

            # Check for Language File
            lang_path = os.path.join(encrypted_dir, "texts", "en_US.lang")
            has_lang = os.path.exists(lang_path)

            config_data = {
                "packVersion": pack_ver,
                "patchVersion": patch_ver,
                "marketplace_pack_stats": {
                    "v1": {
                        "files": patched_file_count,
                        "dirs": patched_folder_count
                    }
                },
                "validation": {
                    "logo_hash": logo_hash,
                    "has_lang_file": has_lang
                }
            }

            config_path = os.path.join(output_dir, "patch_config.json")
            with open(config_path, "w") as f:
                json.dump(config_data, f, indent=4)
            
            self.root.after(0, lambda: self.log(f"  ✓ Saved stats to {os.path.basename(config_path)}"))
        
        except Exception as e:
             self.root.after(0, lambda: self.log(f"  ⚠️ Failed to save patch_config.json: {e}"))

    def run_xdelta(self, exe, source, target, output):
        # xdelta3 -e -s <source> <target> <output>
        # -e: compress (encode)
        # -s: source file
        cmd = [exe, "-e", "-s", source, target, output]
        
        # Use subprocess to catch output if needed, or just run
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
             self.root.after(0, lambda: self.log(f"  ✓ Created {os.path.basename(output)}"))
        else:
             self.root.after(0, lambda: self.log(f"  ❌ Failed to create {os.path.basename(output)}"))
             self.root.after(0, lambda: self.log(f"     Stderr: {result.stderr}"))
             raise Exception(f"XDelta failed for {os.path.basename(output)}")

if __name__ == "__main__":
    app = tb.Window(themename="darkly")
    PatchCreatorApp(app)
    app.mainloop()
