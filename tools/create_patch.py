import os
import sys
import shutil
import threading
import subprocess
import tempfile
import ttkbootstrap as tb
from ttkbootstrap.constants import *
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
        
        self.setup_ui()
        
    def setup_ui(self):
        # Header
        lbl = tb.Label(self.root, text="Automated Patch Creator", font=("Helvetica", 16, "bold"))
        lbl.pack(pady=10)
        
        # 1. Patched Decrypted (Contains the changes - The "Goal" state)
        self.create_folder_input("1. Modified/Patched Folder (The result you want):", self.patched_dir)
        
        # 2. Decrypted (Original Reference)
        self.create_folder_input("2. Original Decrypted (Vanilla Reference):", self.decrypted_dir)
        
        # 3. Encrypted (Original Reference)
        self.create_folder_input("3. Original Encrypted (Vanilla Reference):", self.encrypted_dir)

        # 4. Output Directory
        self.create_folder_input("Output Directory (For .xdelta files):", self.output_dir)

        # Options
        self.inject_manifest = tb.BooleanVar(value=True)
        tb.Checkbutton(self.root, text="Inject Custom Manifest into Decrypted Source (Required for Zip Patcher compatibility)", 
                       variable=self.inject_manifest, bootstyle="round-toggle").pack(pady=10)

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

        if not all([os.path.exists(p) for p in [p_dir, d_dir, e_dir, o_dir]]):
             messagebox.showerror("Error", "One or more paths do not exist.")
             return

        self.toggle_inputs(False)
        threading.Thread(target=self.process_worker, args=(p_dir, d_dir, e_dir, o_dir), daemon=True).start()

    def process_worker(self, patched_dir, decrypted_dir, encrypted_dir, output_dir):
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
            self.root.after(0, lambda: self.log(f"Compressing Target: {os.path.basename(patched_dir)}..."))
            compress_deterministic(patched_dir, target_zip)
            
            # 2. Compress Decrypted Directory (Source 1)
            # Logic: If injecting manifest, copy decrypted_dir to temp, add manifest, then compress.
            dir_to_compress_dec = decrypted_dir
            if self.inject_manifest.get():
                self.root.after(0, lambda: self.log("Injecting manifest.json into Decrypted Source copy..."))
                temp_dec_source = os.path.join(temp_dir, "decrypted_source_files")
                shutil.copytree(decrypted_dir, temp_dec_source)
                
                # Find manifest in resources
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                manifest_path = os.path.join(project_root, "resources", "manifest.json")
                
                if os.path.exists(manifest_path):
                    shutil.copyfile(manifest_path, os.path.join(temp_dec_source, "manifest.json"))
                    self.root.after(0, lambda: self.log("  ✓ Manifest injected."))
                else:
                    self.root.after(0, lambda: self.log("  ⚠️ Warning: resources/manifest.json not found."))
                
                dir_to_compress_dec = temp_dec_source

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

            # Patch 1: Decrypted -> Patched
            out_patch_dec = os.path.join(output_dir, "patch_decrypted.xdelta")
            self.root.after(0, lambda: self.log("Generating Patch: Decrypted -> Patched..."))
            self.run_xdelta(xdelta_path, source_dec_zip, target_zip, out_patch_dec)

            # Patch 2: Encrypted -> Patched
            out_patch_enc = os.path.join(output_dir, "patch_encrypted.xdelta")
            self.root.after(0, lambda: self.log("Generating Patch: Encrypted -> Patched..."))
            self.run_xdelta(xdelta_path, source_enc_zip, target_zip, out_patch_enc)

            self.root.after(0, lambda: self.log("✅ All operations completed successfully!"))
            self.root.after(0, lambda: messagebox.showinfo("Done", "Patches created successfully."))

        except Exception as e:
            self.root.after(0, lambda: self.log(f"❌ Error: {str(e)}"))
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.root.after(0, lambda: self.toggle_inputs(True))
            # Optional: cleanup temp_dir
            # shutil.rmtree(temp_dir, ignore_errors=True)

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
