import os
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox

def scan_folder(folder_path):
    file_map = {}

    for root, _, files in os.walk(folder_path):
        for file in files:
            name, ext = os.path.splitext(file)
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(root, folder_path)
            if name not in file_map:
                file_map[name] = {"extensions": set(), "paths": set()}
            file_map[name]["extensions"].add(ext.lower())
            file_map[name]["paths"].add(rel_path if rel_path != "." else ".")  # Handle root dir

    # Filter base names with more than one extension
    duplicates = {k: v for k, v in file_map.items() if len(v["extensions"]) > 1}
    return duplicates

def browse_folder():
    path = filedialog.askdirectory(title="Select Folder")
    if path:
        folder_var.set(path)
        display_results(scan_folder(path), path)

def display_results(dupe_dict, base_path):
    for row in tree.get_children():
        tree.delete(row)

    if not dupe_dict:
        messagebox.showinfo("No Duplicates", "No files with same name but different extensions were found.")
        return

    for name, data in sorted(dupe_dict.items()):
        ext_str = ", ".join(sorted(data["extensions"]))
        path_str = "\n".join(sorted(data["paths"]))
        tree.insert("", END, text=name, values=(ext_str, path_str))

# GUI setup
app = ttk.Window("Extension Conflict Finder", themename="darkly", size=(800, 550))
app.resizable(False, False)

frame = ttk.Frame(app, padding=10)
frame.pack(fill=X)

folder_var = ttk.StringVar()

ttk.Label(frame, text="Folder to scan:").pack(anchor=W)
entry_frame = ttk.Frame(frame)
entry_frame.pack(fill=X, pady=5)
ttk.Entry(entry_frame, textvariable=folder_var, width=80).pack(side=LEFT, padx=(0, 10), fill=X, expand=True)
ttk.Button(entry_frame, text="Browse", command=browse_folder).pack(side=LEFT)

tree_frame = ttk.Frame(app, padding=(10, 0))
tree_frame.pack(fill=BOTH, expand=True)

tree = ttk.Treeview(tree_frame, columns=("extensions", "locations"), show="tree headings", height=20)
tree.heading("#0", text="Base Filename")
tree.heading("extensions", text="Extensions Found")
tree.heading("locations", text="Relative Paths")
tree.column("extensions", width=150, anchor=W)
tree.column("locations", width=500, anchor=W)

# Scrollbar
scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
tree.configure(yscrollcommand=scroll.set)
scroll.pack(side=RIGHT, fill=Y)

tree.pack(fill=BOTH, expand=True, pady=(10, 0))

app.mainloop()
