"""
Deterministic Zipper Tool

This script provides a GUI to compress a folder into a ZIP file with
deterministic timestamps (Jan 1, 1980), ensuring identical builds
for identical content.
"""

import os
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox

def compress_deterministic(folder_path, output_zip):
    """
    Compresses a folder into a zip file with fixed timestamps.

    Args:
        folder_path (str): Source directory.
        output_zip (str): Output zip file path.
    """
    with zipfile.ZipFile(output_zip, 'w', compression=zipfile.ZIP_STORED) as zf:
        for root, _, files in sorted(os.walk(folder_path)):
            for file in sorted(files):
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path).replace("\\", "/")

                # Consistent DOS-compatible timestamp: Jan 1, 1980
                info = zipfile.ZipInfo(arcname)
                info.date_time = (1980, 1, 1, 0, 0, 0)
                info.compress_type = zipfile.ZIP_STORED

                with open(file_path, 'rb') as f:
                    zf.writestr(info, f.read())

def select_and_compress(status_label):
    """
    Opens file dialogs to select folder and save location, then triggers compression.
    """
    folder_path = filedialog.askdirectory(title="Select a folder to compress")
    if not folder_path:
        return

    output_zip = filedialog.asksaveasfilename(
        title="Save As",
        defaultextension=".zip",
        filetypes=[("Zip files", "*.zip")],
    )
    if not output_zip:
        return

    try:
        status_label.config(text=f"Compressing {os.path.basename(folder_path)}...")
        compress_deterministic(folder_path, output_zip)
        messagebox.showinfo("Success", f"Successfully compressed to {output_zip}")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")
    finally:
        status_label.config(text="Select a folder to compress.")

def main():
    """Main entry point for the GUI."""
    print("Starting Deterministic Zipper GUI...")
    root = tk.Tk()
    root.title("A&S RTX Deterministic Zipper")
    root.geometry("400x150")

    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.abspath(os.path.join(base_dir, "..", "assets", "resources", "icon.ico"))
        root.iconbitmap(icon_path)
    except: pass

    status_label = tk.Label(root, text="Select a folder to compress.", padx=10, pady=10)
    status_label.pack()

    compress_button = tk.Button(
        root,
        text="Select Folder and Compress",
        command=lambda: select_and_compress(status_label)
    )
    compress_button.pack(pady=20)

    root.mainloop()

if __name__ == "__main__":
    main()
