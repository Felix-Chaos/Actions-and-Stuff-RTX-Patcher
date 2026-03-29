import os
import sys
import shutil
import threading
import subprocess
import tempfile
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import json
import hashlib
import time
from tkinter import filedialog, Listbox, END, messagebox, StringVar

# Import deterministic compression logic
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from deterministic_zipper import compress_deterministic
except ImportError:
    pass

class PatchCreatorV2App:
    def __init__(self, root):
        self.root = root
        self.root.title("A&S RTX Patch Creator V2 - Optimized Mix")
        self.root.geometry("800x800")
        self.root.resizable(False, False)
        
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.abspath(os.path.join(base_dir, "..", "assets", "resources", "icon.ico"))
            self.root.iconbitmap(icon_path)
        except: pass
        
        # Variables
        self.patched_dir = tb.StringVar()
        self.decrypted_dir = tb.StringVar()
        self.encrypted_dir = tb.StringVar()
        self.output_dir = tb.StringVar()

        self.check_env_and_setup_defaults()
        self.setup_ui()

    def check_env_and_setup_defaults(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        user_profile = os.environ.get('USERPROFILE', os.path.expanduser('~'))
        downloads_dir = os.path.join(user_profile, 'Downloads')
        
        p_dir = downloads_dir
        d_dir = downloads_dir
        e_dir = os.path.join(base_dir, "_input", "encrypted")
        
        o_dir = os.path.abspath(os.path.join(base_dir, "..", "assets", "Patches", "Current"))
             
        # Fallback for Encrypted (Minecraft Premium Cache)
        candidates = [
            os.path.expandvars(r"%AppData%/Minecraft Bedrock/premium_cache/resource_packs"),
            os.path.expandvars(r"%LocalAppData%/Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState/premium_cache/resource_packs")
        ]
        mc_uuid = "7U5jWx4F4vc="
        found_mc = False
        for c in candidates:
            if os.path.exists(c):
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
            try: os.makedirs(o_dir, exist_ok=True)
            except OSError: pass

        self.load_settings()

        if not self.patched_dir.get(): self.patched_dir.set(p_dir)
        if not self.decrypted_dir.get(): self.decrypted_dir.set(d_dir)
        if not self.encrypted_dir.get(): self.encrypted_dir.set(e_dir)
        if not self.output_dir.get(): self.output_dir.set(o_dir)

    def get_settings_path(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "tool_config_v2.json")

    def load_settings(self):
        try:
            path = self.get_settings_path()
            if os.path.exists(path):
                with open(path, "r") as f:
                    data = json.load(f)
                    if "patched_dir" in data: self.patched_dir.set(data["patched_dir"])
                    if "decrypted_dir" in data: self.decrypted_dir.set(data["decrypted_dir"])
                    if "encrypted_dir" in data: self.encrypted_dir.set(data["encrypted_dir"])
        except Exception:
            pass

    def save_settings(self):
        try:
            data = {
                "patched_dir": self.patched_dir.get(),
                "decrypted_dir": self.decrypted_dir.get(),
                "encrypted_dir": self.encrypted_dir.get(),
                "output_dir": self.output_dir.get()
            }
            with open(self.get_settings_path(), "w") as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass
            
    def setup_ui(self):
        # Header
        lbl = tb.Label(self.root, text="Patch Creator V2 (Optimized xdelta3 Mix)", font=("Helvetica", 16, "bold"))
        lbl.pack(pady=5)
        
        # Inputs
        self.create_folder_input("1. Target Folder (Your modified A&S RTX):", self.patched_dir)
        self.create_folder_input("2. Source Decrypted (Vanilla extracted unencrypted):", self.decrypted_dir)
        self.create_folder_input("3. Source Encrypted (Vanilla from marketplace, extracted!):", self.encrypted_dir)
        self.create_folder_input("Output Directory (Where .vcdiff patches are saved):", self.output_dir)

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

        # --- LIVE STATS DASHBOARD ---
        dashboard = tb.LabelFrame(self.root, text="Live Dashboard")
        dashboard.pack(fill=X, padx=10, pady=10, ipadx=5, ipady=5)

        self.progress_var = tb.DoubleVar(value=0)
        self.progress_bar = tb.Progressbar(dashboard, variable=self.progress_var, maximum=100, bootstyle="success-striped")
        self.progress_bar.pack(fill=X, pady=5)

        stats_frame = tb.Frame(dashboard)
        stats_frame.pack(fill=X, pady=5)

        self.lbl_speed = tb.Label(stats_frame, text="Speed: 0 files/sec", font=("Helvetica", 11))
        self.lbl_speed.pack(side=LEFT, padx=10)

        self.lbl_unmod = tb.Label(stats_frame, text="Unmodified (Encrypted): 0", font=("Helvetica", 11), foreground="#5bc0de")
        self.lbl_unmod.pack(side=LEFT, padx=20)

        self.lbl_mod = tb.Label(stats_frame, text="Modified (RTX): 0", font=("Helvetica", 11), foreground="#f0ad4e")
        self.lbl_mod.pack(side=LEFT, padx=20)

        self.lbl_total = tb.Label(stats_frame, text="Total: 0 / 0", font=("Helvetica", 11))
        self.lbl_total.pack(side=RIGHT, padx=10)

        # Action Buttons
        btn_frame = tb.Frame(self.root)
        btn_frame.pack(pady=5)
        
        self.start_btn = tb.Button(btn_frame, text="Create Patches", bootstyle=SUCCESS, command=self.start_process)
        self.start_btn.pack(side=LEFT, padx=10)
        
        # Log Box
        tb.Label(self.root, text="Progress Log:", bootstyle="secondary").pack(anchor=W, padx=10)
        self.log_box = Listbox(self.root, height=10, bg="#1e1e1e", fg="white", selectbackground="#444", highlightthickness=0)
        self.log_box.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

    def create_folder_input(self, label_text, variable):
        frame = tb.Frame(self.root)
        frame.pack(fill=X, padx=10, pady=5)
        tb.Label(frame, text=label_text).pack(anchor=W)
        entry_frame = tb.Frame(frame)
        entry_frame.pack(fill=X)
        tb.Entry(entry_frame, textvariable=variable).pack(side=LEFT, fill=X, expand=True)
        tb.Button(entry_frame, text="Browse", command=lambda: self.browse_folder(variable)).pack(side=RIGHT, padx=5)

    def browse_folder(self, variable):
        path = filedialog.askdirectory()
        if path: variable.set(path)

    def log(self, message):
        self.log_box.insert(END, message)
        self.log_box.yview_moveto(1.0)

    def toggle_inputs(self, state):
        state_val = "normal" if state else "disabled"
        self.start_btn.config(state=state_val)

    def start_process(self):
        p_dir = self.patched_dir.get()
        d_dir = self.decrypted_dir.get()
        e_dir = self.encrypted_dir.get()
        o_dir = self.output_dir.get()

        if not all([p_dir, d_dir, e_dir, o_dir]):
            messagebox.showerror("Error", "All folder paths are required.")
            return

        if not all([os.path.exists(p) for p in [p_dir, d_dir, e_dir]]):
             messagebox.showerror("Error", "One or more input paths do not exist. Please double check they are extracted.")
             return

        os.makedirs(o_dir, exist_ok=True)
        self.save_settings()

        pack_ver = self.pack_version_var.get().strip() or "v1.9.1"
        patch_ver = self.patch_version_var.get().strip() or "1.0"

        self.toggle_inputs(False)
        self.progress_var.set(0)
        self.lbl_speed.config(text="Speed: 0 files/sec")
        self.lbl_unmod.config(text="Unmodified (Encrypted): 0")
        self.lbl_mod.config(text="Modified (RTX): 0")
        self.lbl_total.config(text="Total: 0 / 0")
        self.log_box.delete(0, END)

        threading.Thread(target=self.process_worker, args=(p_dir, d_dir, e_dir, o_dir, pack_ver, patch_ver), daemon=True).start()

    def update_dashboard(self, processed, total, speed, mod_cnt, unmod_cnt):
        pct = (processed / total) * 100 if total > 0 else 0
        self.progress_var.set(pct)
        self.lbl_speed.config(text=f"Speed: {speed} files/sec")
        self.lbl_unmod.config(text=f"Unmodified (Encrypted): {unmod_cnt}")
        self.lbl_mod.config(text=f"Modified (RTX): {mod_cnt}")
        self.lbl_total.config(text=f"Total: {processed} / {total}")

    def get_hash(self, filepath):
        if not os.path.exists(filepath): return None
        sha256 = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for block in iter(lambda: f.read(65536), b""):
                    sha256.update(block)
            return sha256.hexdigest()
        except:
            return None

    def process_worker(self, patched_dir, decrypted_dir, encrypted_dir, output_dir, pack_ver, patch_ver):
        try:
            temp_dir = os.path.join(tempfile.gettempdir(), "AnSPatcherToolV2")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)

            self.root.after(0, lambda: self.log("--- Starting V2 Process ---"))
            
            target_zip = os.path.join(temp_dir, "target_patched_mix.zip")
            source_dec_zip = os.path.join(temp_dir, "source_decrypted.zip")
            source_enc_zip = os.path.join(temp_dir, "source_encrypted.zip")

            self.root.after(0, lambda: self.log("Building Mixed Patched Target..."))
            temp_patched_target = os.path.join(temp_dir, "patched_target_files")
            os.makedirs(temp_patched_target)

            # Dashboard Setup
            all_files = []
            for r, d, files in os.walk(patched_dir):
                for f in files:
                    all_files.append(os.path.join(r, f))
            total_files = len(all_files)
            
            if total_files == 0:
                self.root.after(0, lambda: self.log("⚠️ WARNING: Target Folder is absolutely completely empty!"))
                self.root.after(0, lambda: self.log("Did you accidentally select an empty folder instead of the pack?"))

            self.root.after(0, lambda: self.update_dashboard(0, total_files, 0, 0, 0))
            self.root.after(0, lambda: self.log("Building Vanilla Content Hash Map (Please wait)..."))
            decrypted_hash_map = {}
            for r, d, files in os.walk(decrypted_dir):
                for f in files:
                    dec_path = os.path.join(r, f)
                    h = self.get_hash(dec_path)
                    if h:
                        decrypted_hash_map[h] = os.path.relpath(dec_path, decrypted_dir)
            self.root.after(0, lambda: self.log(f"Hash Map built with {len(decrypted_hash_map)} vanilla files."))

            processed = 0
            omitted_count = 0
            mod_count = 0
            start_time = time.time()

            for patched_path in all_files:
                rel_path = os.path.relpath(patched_path, patched_dir)
                mix_path = os.path.join(temp_patched_target, rel_path)
                
                os.makedirs(os.path.dirname(mix_path), exist_ok=True)
                h_patch = self.get_hash(patched_path)
                
                # Check if exact content exists anywhere in Vanilla (handles renamed files perfectly)
                if h_patch and h_patch in decrypted_hash_map:
                    vanilla_rel_path = decrypted_hash_map[h_patch]
                    encrypted_path = os.path.join(encrypted_dir, vanilla_rel_path)
                    
                    if os.path.exists(encrypted_path):
                        shutil.copyfile(encrypted_path, mix_path)
                        omitted_count += 1
                    else:
                        shutil.copyfile(patched_path, mix_path)
                        mod_count += 1
                else:
                    shutil.copyfile(patched_path, mix_path)
                    mod_count += 1
                    
                processed += 1
                elapsed = time.time() - start_time
                speed = int(processed / elapsed) if elapsed > 0 else 0
                
                if processed % 10 == 0 or processed == total_files:
                    self.root.after(0, lambda p=processed, t=total_files, s=speed, m=mod_count, u=omitted_count: self.update_dashboard(p, t, s, m, u))

            self.root.after(0, lambda: self.log(f"Mixed Target Build Complete. Processed {processed} files."))

            # Inject Manifest into Mix
            if self.inject_manifest.get():
                self.root.after(0, lambda: self.log("Injecting manifest.json into Mixed Target..."))
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                manifest_path = os.path.join(project_root, "assets", "resources", "manifest.json")
                if os.path.exists(manifest_path):
                    target_manifest_path = os.path.join(temp_patched_target, "manifest.json")
                    shutil.copyfile(manifest_path, target_manifest_path)
                    try:
                        with open(target_manifest_path, 'r', encoding='utf-8') as f:
                            manifest_data = json.load(f)
                        clean_pack_ver = ''.join(c if c.isdigit() or c == '.' else '' for c in pack_ver).strip('.')
                        if not clean_pack_ver: clean_pack_ver = "1.0.0"
                        ver_parts = [int(p) for p in clean_pack_ver.split('.') if p.isdigit()]
                        while len(ver_parts) < 3: ver_parts.append(0)
                        
                        if "header" in manifest_data:
                            manifest_data["header"]["version"] = ver_parts[:3]
                            if "name" in manifest_data["header"]:
                                manifest_data["header"]["name"] = f"{manifest_data['header']['name']} ({pack_ver} - Patch {patch_ver})"
                            if "description" in manifest_data["header"]:
                                manifest_data["header"]["description"] += f" | {pack_ver} Patch {patch_ver}"
                        if "modules" in manifest_data and isinstance(manifest_data["modules"], list):
                            for mod in manifest_data["modules"]:
                                if "version" in mod:
                                    mod["version"] = ver_parts[:3]

                        with open(target_manifest_path, 'w', encoding='utf-8') as f:
                            json.dump(manifest_data, f, indent=4)
                        self.root.after(0, lambda: self.log(f"  ✓ Modified Target Manifest injected."))
                    except Exception as e:
                        self.root.after(0, lambda: self.log(f"  ⚠️ Warning: Failed to modify manifest JSON: {e}"))
                else:
                    self.root.after(0, lambda: self.log(f"  ⚠️ Warning: {manifest_path} not found."))

            self.root.after(0, lambda: self.log(f"Compressing Target Zip..."))
            compress_deterministic(temp_patched_target, target_zip)

            # Build Cleaned Decrypted Source
            self.root.after(0, lambda: self.log("Preparing Decrypted Source (Cleaning & Injecting)..."))
            temp_dec_source = os.path.join(temp_dir, "decrypted_source_files")
            shutil.copytree(decrypted_dir, temp_dec_source)

            files_to_remove = ["contents.json", "signatures.json", "splashes.json", "sounds.json"]
            dirs_to_remove = ["texts"]

            for root_d, dirs, files in os.walk(temp_dec_source):
                for f in files:
                    if f in files_to_remove:
                        try: os.remove(os.path.join(root_d, f))
                        except OSError: pass
                for d in list(dirs):
                    if d in dirs_to_remove:
                        try:
                            shutil.rmtree(os.path.join(root_d, d))
                            dirs.remove(d)
                        except OSError: pass

            if self.inject_manifest.get():
                self.root.after(0, lambda: self.log("Injecting Baseline manifest into Source..."))
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                manifest_path = os.path.join(project_root, "assets", "resources", "manifest.json")
                if os.path.exists(manifest_path):
                    shutil.copyfile(manifest_path, os.path.join(temp_dec_source, "manifest.json"))
                    self.root.after(0, lambda: self.log("  ✓ Baseline Manifest injected."))
                else:
                    self.root.after(0, lambda: self.log(f"  ⚠️ Warning: {manifest_path} not found."))

            self.root.after(0, lambda: self.log(f"Compressing Source Decrypted..."))
            compress_deterministic(temp_dec_source, source_dec_zip)

            self.root.after(0, lambda: self.log(f"Compressing Source Encrypted..."))
            compress_deterministic(encrypted_dir, source_enc_zip)

            # Generate Patches
            xdelta_path = os.path.join(os.path.dirname(__file__), "xdelta3.exe")
            if not os.path.exists(xdelta_path):
                 self.root.after(0, lambda: self.log("❌ xdelta3.exe not found!"))
                 return

            out_patch_dec = os.path.join(output_dir, "decrypted.vcdiff")
            out_patch_enc = os.path.join(output_dir, "encrypted.vcdiff")

            self.root.after(0, lambda: self.log("Running xdelta3 (Decrypted -> Patched Mix)..."))
            self.run_xdelta(xdelta_path, source_dec_zip, target_zip, out_patch_dec)

            self.root.after(0, lambda: self.log("Running xdelta3 (Encrypted -> Patched Mix)..."))
            self.run_xdelta(xdelta_path, source_enc_zip, target_zip, out_patch_enc)

            # Generate configuration for Patcher
            file_count = 0; folder_count = 0
            for _, dirs, files in os.walk(encrypted_dir):
                folder_count += len(dirs)
                file_count += len(files)

            self.root.after(0, lambda: self.log("Generating patch_config.json..."))
            self.generate_patch_config(encrypted_dir, output_dir, pack_ver, patch_ver, file_count, folder_count)

            self.root.after(0, lambda: self.log("✅ All operations completed successfully!"))
            self.root.after(0, lambda: messagebox.showinfo("Done", "Optimized Patches created successfully!"))

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.root.after(0, lambda err=e: self.log(f"❌ Error: {str(err)}"))
            self.root.after(0, lambda err=e: messagebox.showerror("Error", str(err)))
        finally:
            self.root.after(0, lambda: self.toggle_inputs(True))

    def generate_patch_config(self, encrypted_dir, output_dir, pack_ver, patch_ver, patched_file_count, patched_folder_count):
        try:
            logo_path = os.path.join(encrypted_dir, "pack_icon.png")
            logo_hash = self.get_hash(logo_path)

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
        except Exception as e:
             self.root.after(0, lambda: self.log(f"  ⚠️ Failed to save config: {e}"))

    def run_xdelta(self, exe, source, target, output):
        cmd = [exe, "-e", "-s", source, target, output]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
             self.root.after(0, lambda: self.log(f"  ✓ Created {os.path.basename(output)}"))
        else:
             self.root.after(0, lambda: self.log(f"  ❌ Failed to create {os.path.basename(output)}\n     Stderr: {result.stderr}"))
             raise Exception(f"XDelta failed for {os.path.basename(output)}")

if __name__ == "__main__":
    app = tb.Window(themename="darkly")
    PatchCreatorV2App(app)
    app.mainloop()
