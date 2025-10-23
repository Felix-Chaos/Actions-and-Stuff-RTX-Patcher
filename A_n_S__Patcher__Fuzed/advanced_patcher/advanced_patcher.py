import os
import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import patcher_methods as methods

def create_advanced_patcher_window(ui_manager):
    win = ttk.Toplevel()
    win.title("Advanced Patcher")
    win.geometry("600x400")
    methods.center_window(win)

    frame = ttk.Frame(win, padding=20)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text="Advanced Patcher", font=("Segoe UI", 16, "bold")).pack(pady=(0, 20))

    # --- File Selection ---
    source_file_var = tk.StringVar(value="path/to/source/file")
    patch_file_var = tk.StringVar(value="path/to/patch/file")
    output_file_var = tk.StringVar(value="path/to/output/file")

    def create_file_input(parent, label_text, textvariable):
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=5)
        ttk.Label(row, text=label_text, width=15).pack(side=tk.LEFT)
        entry = ttk.Entry(row, textvariable=textvariable)
        entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        button = ttk.Button(row, text="Browse...", command=lambda: browse_file(textvariable, label_text))
        button.pack(side=tk.LEFT)
        return entry

    def browse_file(textvariable, title):
        file_path = filedialog.askopenfilename(title=f"Select {title}")
        if file_path:
            textvariable.set(file_path)

    create_file_input(frame, "Source File", source_file_var)
    create_file_input(frame, "Patch File", patch_file_var)
    create_file_input(frame, "Output File", output_file_var)

    patch_btn = ttk.Button(frame, text="Apply Patch", bootstyle=SUCCESS)
    patch_btn.pack(pady=20)

    status_label = ttk.Label(frame, text="")
    status_label.pack(pady=5)
    progress = ttk.Progressbar(frame, mode='determinate', length=300)
    progress.pack(pady=5)

    def patch_completion(success, message):
        if success:
            messagebox.showinfo("Success", message)
            win.destroy()
            ui_manager.show_main_menu()
        else:
            messagebox.showerror("Error", message)
        patch_btn.config(state="normal")
        progress.stop()

    def run_patch_command():
        source_file = source_file_var.get()
        patch_file = patch_file_var.get()
        output_file = output_file_var.get()

        if not all([source_file, patch_file, output_file]):
            messagebox.showerror("Error", "Please select all three files.")
            return

        patch_btn.config(state="disabled")
        progress.start()
        methods.run_patch(source_file, patch_file, output_file,
                          lambda msg: status_label.config(text=msg),
                          patch_completion)

    patch_btn.config(command=run_patch_command)

    return win
