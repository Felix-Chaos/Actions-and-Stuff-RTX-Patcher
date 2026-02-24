import os
import hashlib
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

def md5_bytes(data):
    return hashlib.md5(data).hexdigest()

def get_pack_files(pack_path):
    files_data = {}
    
    if os.path.isfile(pack_path) and pack_path.lower().endswith('.zip'):
        try:
            with zipfile.ZipFile(pack_path, 'r') as z:
                for info in z.infolist():
                    if not info.is_dir():
                        with z.open(info) as f:
                            data = f.read()
                            files_data[info.filename] = md5_bytes(data)
        except Exception as e:
            raise Exception(f"Failed to read ZIP {pack_path}:\n{e}")
    elif os.path.isdir(pack_path):
        for root, dirs, files in os.walk(pack_path):
            for file in files:
                full_path = os.path.join(root, file)
                # Read relative to the pack_path
                rel_path = os.path.relpath(full_path, pack_path)
                # Normalize slashes to match zipfile format
                rel_path = rel_path.replace('\\', '/')
                try:
                    with open(full_path, 'rb') as f:
                        files_data[rel_path] = md5_bytes(f.read())
                except Exception as e:
                    # Skip problematic files
                    pass
    else:
        raise Exception(f"Invalid path: {pack_path}")
        
    return _normalize_pack_root(files_data)

def _normalize_pack_root(files_data):
    """
    Finds the root of the texture pack by looking for manifest.json.
    If manifest.json is inside a subfolder (like A&SforRTX/manifest.json),
    we strip that subfolder prefix so we can fairly compare it against 
    another pack that might just be extracted without the root folder.
    """
    manifest_paths = [p for p in files_data.keys() if p.lower().endswith('manifest.json')]
    
    if not manifest_paths:
        return files_data
    
    manifest_paths.sort(key=len)
    root_manifest = manifest_paths[0]
    
    root_prefix = ''
    if '/' in root_manifest:
        root_prefix = root_manifest.rsplit('/', 1)[0] + '/'
    
    if root_prefix:
        normalized_data = {}
        for path, file_hash in files_data.items():
            if path.startswith(root_prefix):
                new_path = path[len(root_prefix):]
                if new_path: # ignore the directory itself
                    normalized_data[new_path] = file_hash
            else:
                # Keep files outside root prefix just in case
                normalized_data[path] = file_hash
        return normalized_data
        
    return files_data

class DiffCheckerApp(ttk.Window):
    def __init__(self):
        super().__init__(themename="darkly", title="A&S RTX Diff Checker")
        self.geometry("850x650")
        
        self.create_widgets()
        
    def create_widgets(self):
        # Pack 1
        pack1_frame = ttk.Frame(self)
        pack1_frame.pack(fill=X, padx=10, pady=10)
        
        ttk.Label(pack1_frame, text="Texture Pack 1:", width=20).pack(side=LEFT)
        self.pack1_var = ttk.StringVar()
        ttk.Entry(pack1_frame, textvariable=self.pack1_var).pack(side=LEFT, fill=X, expand=True, padx=5)
        ttk.Button(pack1_frame, text="Folder", bootstyle=SECONDARY, command=lambda: self.browse_folder(self.pack1_var)).pack(side=LEFT, padx=2)
        ttk.Button(pack1_frame, text="ZIP", bootstyle=SECONDARY, command=lambda: self.browse_zip(self.pack1_var)).pack(side=LEFT, padx=2)
        
        # Pack 2
        pack2_frame = ttk.Frame(self)
        pack2_frame.pack(fill=X, padx=10, pady=5)
        
        ttk.Label(pack2_frame, text="Texture Pack 2:", width=20).pack(side=LEFT)
        self.pack2_var = ttk.StringVar()
        ttk.Entry(pack2_frame, textvariable=self.pack2_var).pack(side=LEFT, fill=X, expand=True, padx=5)
        ttk.Button(pack2_frame, text="Folder", bootstyle=SECONDARY, command=lambda: self.browse_folder(self.pack2_var)).pack(side=LEFT, padx=2)
        ttk.Button(pack2_frame, text="ZIP", bootstyle=SECONDARY, command=lambda: self.browse_zip(self.pack2_var)).pack(side=LEFT, padx=2)
        
        # Controls
        ctrl_frame = ttk.Frame(self)
        ctrl_frame.pack(fill=X, padx=10, pady=10)
        ttk.Button(ctrl_frame, text="Compare Packs", bootstyle=SUCCESS, command=self.compare_packs).pack(side=LEFT)
        self.status_var = ttk.StringVar(value="Ready.")
        ttk.Label(ctrl_frame, textvariable=self.status_var).pack(side=LEFT, padx=10)
        
        # Output
        self.output_text = ScrolledText(self, width=100, height=25, bg='#1e1e1e', fg='#d4d4d4', font=('Consolas', 10))
        self.output_text.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
    def browse_folder(self, string_var):
        path = filedialog.askdirectory(title="Select Texture Pack Folder")
        if path:
            string_var.set(path)
            
    def browse_zip(self, string_var):
        path = filedialog.askopenfilename(title="Select Texture Pack ZIP", filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")])
        if path:
            string_var.set(path)
            
    def compare_packs(self):
        p1 = self.pack1_var.get().strip()
        p2 = self.pack2_var.get().strip()
        
        if not p1 or not p2:
            messagebox.showerror("Error", "Please select both Texture Packs.")
            return
            
        if not os.path.exists(p1) or not os.path.exists(p2):
            messagebox.showerror("Error", "One or both selected paths do not exist. Please check the paths.")
            return
            
        self.output_text.delete(1.0, END)
        self.status_var.set("Reading files and calculating hashes...")
        self.update()
        
        try:
            dict1 = get_pack_files(p1)
            dict2 = get_pack_files(p2)
        except Exception as e:
            messagebox.showerror("Error reading packs", str(e))
            self.status_var.set("Error during comparison.")
            return
            
        self.status_var.set("Comparing...")
        self.update()
        
        set1 = set(dict1.keys())
        set2 = set(dict2.keys())
        
        added = sorted(list(set2 - set1))
        removed = sorted(list(set1 - set2))
        common = set1 & set2
        
        modified = []
        identical = []
        for f in common:
            if dict1[f] != dict2[f]:
                modified.append(f)
            else:
                identical.append(f)
        modified.sort()
        
        self.output_text.insert(END, f"--- Texture Pack Comparison Results ---\n")
        self.output_text.insert(END, f"Pack 1: {p1}\n")
        self.output_text.insert(END, f"Pack 2: {p2}\n\n")
        
        self.output_text.insert(END, f"Identical files : {len(identical)}\n")
        self.output_text.insert(END, f"Modified files  : {len(modified)}\n")
        self.output_text.insert(END, f"Added files     : {len(added)}\n")
        self.output_text.insert(END, f"Removed files   : {len(removed)}\n\n")
        
        if modified:
            self.output_text.insert(END, "=== MODIFIED FILES ===\n")
            for f in modified:
                self.output_text.insert(END, f" ~ {f}\n")
            self.output_text.insert(END, "\n")
            
        if added:
            self.output_text.insert(END, "=== ADDED FILES (Present in Pack 2, Missing in Pack 1) ===\n")
            for f in added:
                self.output_text.insert(END, f" + {f}\n")
            self.output_text.insert(END, "\n")
                
        if removed:
            self.output_text.insert(END, "=== REMOVED FILES (Present in Pack 1, Missing in Pack 2) ===\n")
            for f in removed:
                self.output_text.insert(END, f" - {f}\n")
            self.output_text.insert(END, "\n")
            
        self.status_var.set("Comparison complete.")

if __name__ == "__main__":
    app = DiffCheckerApp()
    app.mainloop()
