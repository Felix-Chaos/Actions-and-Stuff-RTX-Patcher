import os
import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import patch
import patcher_methods

def create_normal_patcher_window(ui_manager):
    win = ttk.Toplevel()
    win.title("Normal Patcher")
    win.geometry("500x320")
    patcher_methods.center_window(win)

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
    patcher_methods.center_window(top)

    output_file = os.path.join(os.getcwd(), "Actions n Stuff RTX + Dynamic lights.mcpack")

    status_label = ttk.Label(frame, text="Searching for Actions & Stuff encrypted folder...")
    status_label.pack(pady=(0, 10))

    progress = ttk.Progressbar(frame, mode='determinate', length=300, bootstyle=INFO, maximum=100)
    progress.pack(pady=(10, 0))
    progress["value"] = 0
    
    patch_btn = ttk.Button(frame, text="Patch", width=30, state="disabled", bootstyle=SUCCESS)
    patch_btn.pack(pady=(10, 0))

    def patch_completion(success, message):
        if success:
            messagebox.showinfo("🎉 Done!", message)
            top.destroy()
            ui_manager.show_main_menu()
        else:
            messagebox.showerror("Error", message)
        patch_btn.config(state="normal")

    def run_patch_command():
        patch_btn.config(state="disabled")
        patch.patch_marketplace(output_file,
                                 lambda msg: status_label.config(text=msg),
                                 patch_completion)

    patch_btn.config(command=run_patch_command)
    run_patch_command()


def show_zip_patcher(parent, ui_manager):
    top = ttk.Toplevel(parent)
    top.title("Patch from .zip/.mcpack")
    top.geometry("500x250")
    top.attributes("-topmost", True)
    patcher_methods.center_window(top)

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
            filetypes=[("Minecraft Packs", "*.zip" )],
            title="Choose an A&S zip"
        )
        if not file_path:
            top.destroy()
            parent.deiconify()
            return

        patch_btn.config(state="normal")

        def patch_completion(success, message):
            if success:
                messagebox.showinfo("🎉 Done!", message)
                top.destroy()
                ui_manager.show_main_menu()
            else:
                messagebox.showerror("Error", message)
            patch_btn.config(state="normal")

        def run_patch_command():
            patch_btn.config(state="disabled")
            output_file = os.path.join(os.getcwd(), "Actions & Stuff Enhanced RTX.zip")
            patch.patch_zip(file_path, output_file,
                              lambda msg: status_label.config(text=msg),
                              patch_completion)
            

        patch_btn.config(command=run_patch_command)
        run_patch_command()

    choose_and_prepare()
