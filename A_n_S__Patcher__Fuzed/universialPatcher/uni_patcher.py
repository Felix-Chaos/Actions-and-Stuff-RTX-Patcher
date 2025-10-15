import os
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import patcher_methods as methods

def show_uni_patcher_window(parent):
    top = ttk.Toplevel(parent)
    top.title("Universal Patcher")
    top.geometry("600x400")
    methods.center_window(top)

    frame = ttk.Frame(top, padding=20)
    frame.pack(fill="both", expand=True)

    # --- File Selection ---
    source_file_var = tk.StringVar()
    patch_file_var = tk.StringVar()
    output_file_var = tk.StringVar()

    def create_file_input(parent, label_text, textvariable):
        row = ttk.Frame(parent)
        row.pack(fill=X, pady=5)
        ttk.Label(row, text=label_text, width=15).pack(side=LEFT)
        entry = ttk.Entry(row, textvariable=textvariable)
        entry.pack(side=LEFT, expand=True, fill=X, padx=5)
        button = ttk.Button(row, text="Browse...", command=lambda: browse_file(textvariable, label_text))
        button.pack(side=LEFT)
        return entry

    def browse_file(textvariable, title):
        file_path = filedialog.askopenfilename(title=f"Select {title}")
        if file_path:
            textvariable.set(file_path)

    create_file_input(frame, "Source File", source_file_var)
    create_file_input(frame, "Patch File", patch_file_var)
    create_file_input(frame, "Output File", output_file_var)

    # --- Patch Button ---
    patch_btn = ttk.Button(frame, text="Apply Patch", bootstyle=SUCCESS)
    patch_btn.pack(pady=20)

    # --- Progress Bar & Status ---
    status_label = ttk.Label(frame, text="")
    status_label.pack(pady=5)
    progress = ttk.Progressbar(frame, mode='determinate', length=300)
    progress.pack(pady=5)

    def run_patch():
        source_file = source_file_var.get()
        patch_file = patch_file_var.get()
        output_file = output_file_var.get()

        if not all([source_file, patch_file, output_file]):
            messagebox.showerror("Error", "Please select all three files.")
            return

        exe_path = methods.resource_path(os.path.join("xdelta3", "exec", "xdelta3_x86_64_win.exe"))
        if not os.path.exists(exe_path):
            messagebox.showerror("Error", "xdelta3 executable not found.")
            return

        patch_btn.config(state="disabled")
        status_label.config(text="Patching...")
        progress.config(mode='indeterminate')
        progress.start()

        def patch_thread():
            try:
                cmd = f'"{exe_path}" -v -d -s "{source_file}" "{patch_file}" "{output_file}"'
                subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
                status_label.config(text="Patch applied successfully!")
                messagebox.showinfo("Success", "Patch applied successfully!")
            except subprocess.CalledProcessError as e:
                status_label.config(text="Error during patching.")
                messagebox.showerror("Error", f"Patching failed:\n{e.stderr}")
            finally:
                progress.stop()
                progress.config(mode='determinate')
                progress['value'] = 0
                patch_btn.config(state="normal")

        threading.Thread(target=patch_thread, daemon=True).start()

    patch_btn.config(command=run_patch)