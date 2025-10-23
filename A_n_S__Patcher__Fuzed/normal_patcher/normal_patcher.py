import os
import shutil
import subprocess
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import patcher_methods as methods

def create_normal_patcher_window(ui_manager):
    win = ttk.Toplevel()
    win.title("Normal Patcher")
    win.geometry("500x320")
    methods.center_window(win)

    frame = ttk.Frame(win, padding=30)
    frame.pack()

    ttk.Label(frame, text="General Patcher", font=("Segoe UI", 16, "bold")).pack(pady=(0, 20))

    btn_patch_marketplace = ttk.Button(
        frame,
        text="Patch from marketplace",
        width=30,
        command=lambda: [win.withdraw(), show_marketplace_patcher(win, ui_manager)],
        bootstyle=INFO
    )
    btn_patch_decrypted = ttk.Button(
        frame,
        text="Patch from .zip/.mcpack",
        width=30,
        command=lambda: [win.withdraw(), show_zip_patcher(win, ui_manager)],
        bootstyle=PRIMARY
    )
    
    btn_patch_marketplace.pack(pady=10)
    btn_patch_decrypted.pack(pady=10)

    return win


def show_marketplace_patcher(parent, ui_manager):
    top = ttk.Toplevel(parent)
    top.title("Patch from Marketplace")
    top.geometry("500x250")
    top.attributes('-topmost', True)
    frame = ttk.Frame(top, padding=20)
    frame.pack()
    methods.center_window(top)

    target_files = 12951
    target_dirs = 161

    resource_paths = [
        os.path.expandvars(r"%LocalAppData%\\Packages\\Microsoft.MinecraftUWP_8wekyb3d8bbwe\\LocalState\\premium_cache\\resource_packs"),
        os.path.expandvars(r"%LocalAppData%\\Packages\\Microsoft.MinecraftWindowsBeta_8wekyb3d8bbwe\\LocalState\\premium_cache\\resource_packs")
    ]

    output_dir = os.path.join(os.getcwd(), "xdelta3", "original")
    output_zip = os.path.join(output_dir, "Actions & Stuff encrypted.zip")
    vcdiff_path = methods.resource_path(os.path.join("xdelta3", "vcdiff", "Actions & Stuff encrypted.zip.vcdiff"))
    patched_output = os.path.join(os.getcwd(), "xdelta3", "output", "Actions n Stuff RTX + Dynamic lights.mcpack")

    status_label = ttk.Label(frame, text="Searching for Actions & Stuff encrypted folder...")
    status_label.pack(pady=(0, 10))

    progress = ttk.Progressbar(frame, mode='determinate', length=300, bootstyle=INFO, maximum=100)
    progress.pack(pady=(10, 0))
    progress["value"] = 0
    
    patch_btn = ttk.Button(frame, text="Patch", width=30, state="disabled", bootstyle=SUCCESS)
    patch_btn.pack(pady=(10, 0))

    def search_and_compress():
        found = False
        for path in resource_paths:
            if not os.path.exists(path):
                continue
            for folder in os.listdir(path):
                full_path = os.path.join(path, folder)
                if os.path.isdir(full_path):
                    _, files, folders, file_list = methods.get_folder_stats(full_path, return_files=True)
                    if files == target_files and folders == target_dirs:
                        os.makedirs(output_dir, exist_ok=True)
                        status_label.config(text="Compressing files... Might take a couple of minutes")
                        methods.compress_deterministic(full_path, output_zip)
                        found = True
                        break
            if found:
                break

        if found:
            patch_btn.config(state="normal")
            status_label.config(text="Encrypted files ready for patching.")
        else:
            status_label.config(text="No matching folder found.")

    def patch_completion(success, message):
        if success:
            messagebox.showinfo("🎉 Done!", message)
            shutil.rmtree(os.path.join(os.getcwd(), "xdelta3"), ignore_errors=True)
            top.destroy()
            ui_manager.show_main_menu()
        else:
            messagebox.showerror("Error", message)
        patch_btn.config(state="normal")

    def run_patch_command():
        patch_btn.config(state="disabled")
        methods.run_patch(output_zip, vcdiff_path, patched_output,
                          lambda msg: status_label.config(text=msg),
                          patch_completion)

    patch_btn.config(command=run_patch_command)
    threading.Thread(target=search_and_compress, daemon=True).start()


def show_zip_patcher(parent, ui_manager):
    top = ttk.Toplevel(parent)
    top.title("Patch from .zip/.mcpack")
    top.geometry("500x250")
    top.attributes("-topmost", True)
    methods.center_window(top)

    frame = ttk.Frame(top, padding=20)
    frame.pack(fill="both", expand=True)

    status_label = ttk.Label(frame, text="Select an A&S .zip or .mcpack")
    status_label.pack(pady=(0, 10))

    progress = ttk.Progressbar(frame, mode='determinate', length=300, bootstyle=INFO, maximum=100)
    progress.pack(pady=(5, 10))

    patch_btn = ttk.Button(frame, text="Patch", width=30, state="disabled", bootstyle=SUCCESS)
    patch_btn.pack(pady=(10, 0))

    def choose_and_prepare():
        file_path = filedialog.askopenfilename(
            filetypes=[("Minecraft Packs", "*.zip *.mcpack")],
            title="Choose an A&S zip or mcpack"
        )
        if not file_path:
            top.destroy()
            parent.deiconify()
            return

        normalized_zip = os.path.join(os.getcwd(), "mcpack_normalized.zip")

        status_label.config(text="Ready to patch.")
        patch_btn.config(state="normal")

        def patch_completion(success, message):
            if success:
                messagebox.showinfo("🎉 Done!", message)
                os.remove(normalized_zip)
                top.destroy()
                ui_manager.show_main_menu()
            else:
                messagebox.showerror("Error", message)
            patch_btn.config(state="normal")

        def run_patch_command():
            patch_btn.config(state="disabled")
            vcdiff_path = methods.resource_path(os.path.join("xdelta3", "vcdiff", "Actions & Stuff decrypted.zip.vcdiff"))
            output_file = os.path.join(os.getcwd(), "Actions & Stuff Enhanced RTX.mcpack")
            methods.run_patch(normalized_zip, vcdiff_path, output_file,
                              lambda msg: status_label.config(text=msg),
                              patch_completion)

        patch_btn.config(command=run_patch_command)

    threading.Thread(target=choose_and_prepare, daemon=True).start()
