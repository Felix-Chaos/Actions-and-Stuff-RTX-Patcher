import os
import threading
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from PIL import Image, ImageTk
import webbrowser
import subprocess
import sys
import time

# --- Determine project base path ---
base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, base_path)

# --- Import custom modules ---
import patcher_methods
import normal_patcher.normal_patcher as normal_patcher
import advanced_patcher.advanced_patcher as advanced_patcher
from ui_manager import UIManager
print(f"📂 Base path: {base_path}")

# Platform-specific creation flags (Windows only)
CREATE_NEW_CONSOLE = 0
if os.name == "nt":
    CREATE_NEW_CONSOLE = subprocess.CREATE_NEW_CONSOLE

# Utility: run subprocess in background thread
def run_subprocess_in_thread(root, cmd, script_label):
    def worker():
        try:
            creationflags = CREATE_NEW_CONSOLE if os.name == "nt" else 0
            proc = subprocess.Popen(cmd, creationflags=creationflags)
            exit_code = proc.wait()
            root.after(0, lambda: on_done(exit_code))
        except Exception as e:
            root.after(0, lambda: on_err(e))

    def on_done(exit_code):
        if exit_code == 0:
            messagebox.showinfo("Success", f"'{script_label}' finished successfully.")
        else:
            messagebox.showwarning("Finished with errors", f"'{script_label}' finished with exit code {exit_code}.")

    def on_err(e):
        messagebox.showerror("Execution Error", f"Failed to run '{script_label}':\n{e}")

    threading.Thread(target=worker, daemon=True).start()

# -------------------------------------------------------------------
#                           MAIN WINDOW
# -------------------------------------------------------------------
def create_main_window(ui_manager):
    root = ttk.Window(themename="darkly")
    root.title("A.n.S Patcher by Felix")

    icon_path = os.path.join(base_path, "resources", "icon.ico")
    if os.path.exists(icon_path):
        try:
            root.iconbitmap(icon_path)
        except Exception as e:
            print(f"⚠ Could not set icon: {e}")
    else:
        print(f"⚠ Icon not found: {icon_path}")

    root.geometry("600x400")
    root.resizable(False, False)
    patcher_methods.center_window(root)

    # --- MENUBAR ---
    menubar = ttk.Menu(root)
    root.config(menu=menubar)

    tools_menu = ttk.Menu(menubar, tearoff=False)
    menubar.add_cascade(label="Tools", menu=tools_menu)

    def confirm_clean_for_update():
        if messagebox.askokcancel("Confirm Cleanup", "This will remove all A&SforRTX folders.\nBackup important data before continuing."):
            if messagebox.askokcancel("Final Confirmation", "Are you ABSOLUTELY sure? This cannot be undone."):
                patcher_methods.clean_for_update(root)
    tools_menu.add_command(label="Clean for Update", command=confirm_clean_for_update)

    sub_tools_menu = ttk.Menu(tools_menu, tearoff=False)
    tools_menu.add_cascade(label="Creator Tools", menu=sub_tools_menu)

    search_tools_path = os.path.join(base_path, "tools")
    found_scripts = []
    if os.path.isdir(search_tools_path):
        for f in sorted(os.listdir(search_tools_path)):
            if f.endswith(".py") and f != "__init__.py":
                found_scripts.append(os.path.join(search_tools_path, f))

    if not found_scripts:
        sub_tools_menu.add_command(label="No scripts found", state="disabled")
    else:
        for script_path in found_scripts:
            label = os.path.basename(script_path).replace(".py", "")
            def make_command(path, lbl):
                return lambda: run_subprocess_in_thread(root, [sys.executable, path], lbl)
            sub_tools_menu.add_command(label=label, command=make_command(script_path, label))

    dependencies_menu = ttk.Menu(menubar, tearoff=False)
    menubar.add_cascade(label="Dependencies", menu=dependencies_menu)

    def confirm_visit_url():
        if messagebox.askokcancel("Visit Website", "This will open your browser to the Vanilla Reforged RTX download page.\nContinue?"):
            webbrowser.open("https://www.curseforge.com/minecraft-bedrock/texture-packs/vanilla-reforged-rtx")
    dependencies_menu.add_command(label="Install Vanilla Reforged RTX", command=confirm_visit_url)

    help_menu = ttk.Menu(menubar, tearoff=False)
    menubar.add_cascade(label="Help", menu=help_menu)
    help_menu.add_command(label="About", command=lambda: messagebox.showinfo("About", "A.n.S Patcher by Felix\nVersion 1.0"))

    # --- MAIN CONTENT ---
    main_frame = ttk.Frame(root, padding=10)
    main_frame.pack(expand=True, fill=BOTH)

    image_path = os.path.join(base_path, "resources", "logo.png")
    if os.path.exists(image_path):
        pil_image = Image.open(image_path).resize((200, 100))
        image = ImageTk.PhotoImage(pil_image)
        image_label = ttk.Label(main_frame, image=image)
        image_label.image = image
        image_label.pack(pady=10)

    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=20)

    ttk.Button(button_frame, text="Leave Patcher", command=root.quit, bootstyle="danger").pack(side=LEFT, padx=10)
    ttk.Button(
        button_frame,
        text="Start patching",
        command=lambda: ui_manager.show_tool_window(normal_patcher.create_normal_patcher_window),
        bootstyle="success"
    ).pack(side=LEFT, padx=10)
    ttk.Button(
        main_frame,
        text="Advanced setup",
        command=lambda: ui_manager.show_tool_window(advanced_patcher.create_advanced_patcher_window),
        bootstyle="link"
    ).pack(side=RIGHT, anchor=SE, padx=10, pady=10)

    return root

# -------------------------------------------------------------------
#                            MAIN
# -------------------------------------------------------------------
if __name__ == "__main__":
    # Add the parent directory to the Python path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    ui_manager = UIManager(create_main_window)
    ui_manager.show_main_menu()
