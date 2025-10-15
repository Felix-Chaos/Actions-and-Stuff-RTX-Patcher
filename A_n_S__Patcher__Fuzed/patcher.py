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

# --- Import custom modules ---
import patcher_methods
import universialPatcher.uni_patcher as uni_patcher
import generalPatcher.gen_patcher as general_patcher

# --- Determine project base path ---
base_path = os.path.dirname(os.path.abspath(__file__))
print(f"📂 Base path: {base_path}")

# Platform-specific creation flags (Windows only)
CREATE_NEW_CONSOLE = 0
DETACHED_PROCESS = 0
if os.name == "nt":
    # Import constants lazily (Windows only)
    CREATE_NEW_CONSOLE = subprocess.CREATE_NEW_CONSOLE
    # DETACHED_PROCESS = 0x00000008  # optional alternative

# Utility: run subprocess in background thread and report back on GUI thread
def run_subprocess_in_thread(root, cmd, script_label):
    """
    Runs `cmd` (list) in a background thread. When finished, uses root.after(...)
    to show a messagebox back on the GUI thread.
    """
    def worker():
        try:
            # Use Popen so we don't block the GUI; wait() in the worker thread.
            # On Windows create a new console so the child doesn't interfere with GUI focus.
            creationflags = CREATE_NEW_CONSOLE if os.name == "nt" else 0
            proc = subprocess.Popen(cmd, creationflags=creationflags)
            exit_code = proc.wait()
            def on_done():
                if exit_code == 0:
                    messagebox.showinfo("Success", f"'{script_label}' finished (exit code 0).")
                else:
                    messagebox.showwarning("Finished with errors", f"'{script_label}' finished with exit code {exit_code}.")
            root.after(0, on_done)
        except Exception as e:
            def on_err():
                messagebox.showerror("Execution Error", f"Failed to run '{script_label}':\n{e}")
            root.after(0, on_err)

    t = threading.Thread(target=worker, daemon=True)
    t.start()

# -------------------------------------------------------------------
#                           MAIN WINDOW
# -------------------------------------------------------------------
def show_main_window():
    root = ttk.Window(themename="darkly")
    root.title("A.n.S Patcher by Felix")

    # ---- App icon ----
    icon_path = os.path.join(base_path, "assets", "icon.ico")
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

    # ----------------------------------------------------------------
    #                            MENUBAR
    # ----------------------------------------------------------------
    menubar = ttk.Menu(root)
    root.config(menu=menubar)

    # ---------------------- Tools Menu -------------------------------
    tools_menu = ttk.Menu(menubar, tearoff=False)
    menubar.add_cascade(label="Tools", menu=tools_menu)

    # --- Clean for Update ---
    def confirm_clean_for_update():
        if messagebox.askokcancel(
            "Confirm Cleanup",
            "This will remove all A&SforRTX folders.\nMake sure to back up important data before continuing.",
        ):
            if messagebox.askokcancel(
                "Final Confirmation",
                "Are you ABSOLUTELY sure? This cannot be undone.",
            ):
                patcher_methods.clean_for_update(root)

    tools_menu.add_command(label="Clean for Update", command=confirm_clean_for_update)

    # --- Creator Tools submenu ---
    sub_tools_menu = ttk.Menu(tools_menu, tearoff=False)
    tools_menu.add_cascade(label="Creator Tools", menu=sub_tools_menu)

    # ----------------------------------------------------------------
    #               SEARCH AND ADD CREATOR TOOLS SCRIPTS
    # ----------------------------------------------------------------
    # We will check both:
    #   <base>/PatcherTools/search_tools
    #   <base>/PatcherTools/search_tools/outputsearch
    search_tools_path = os.path.join(base_path, "PatcherTools")
  

    found_scripts = []

    for d in [search_tools_path]:
        if os.path.exists(d) and os.path.isdir(d):
            print(f"✅ Scanning: {d}")
            for f in sorted(os.listdir(d)):
                if not f.endswith(".py"):
                    continue
                # Skip obvious noise
                if f in ("__init__.py",):
                    continue
                full = os.path.join(d, f)
                # Only add files (not directories)
                if os.path.isfile(full):
                    found_scripts.append(full)
        else:
            print(f"⚠ Not found or not a dir: {d}")

    if not found_scripts:
        print("⚠ No scripts found in search_tools or outputsearch.")
        # still keep the menu but with a disabled entry
        sub_tools_menu.add_command(label="No scripts found", state="disabled")
    else:
        print(f"📜 Found {len(found_scripts)} script(s).")
        # For each script add a menu item
        for script_path in found_scripts:
            label = os.path.basename(script_path).replace(".py", "")

            def make_command(path, lbl):
                # closure to bind values correctly
                def cmd():
                    # Build the command: run with the same python interpreter you're using
                    cmd_list = [sys.executable, path]
                    # Start the script in a background thread so GUI doesn't block
                    run_subprocess_in_thread(root, cmd_list, lbl)
                return cmd

            sub_tools_menu.add_command(label=label, command=make_command(script_path, label))

    # ---------------------- Dependencies Menu ------------------------
    dependencies_menu = ttk.Menu(menubar, tearoff=False)
    menubar.add_cascade(label="Dependencies", menu=dependencies_menu)

    def confirm_visit_url():
        if messagebox.askokcancel(
            "Visit Website",
            "This will open your browser to the Vanilla Reforged RTX download page.\nContinue?",
        ):
            webbrowser.open(
                "https://www.curseforge.com/minecraft-bedrock/texture-packs/vanilla-reforged-rtx"
            )

    dependencies_menu.add_command(
        label="Install Vanilla Reforged RTX", command=confirm_visit_url
    )

    # ---------------------- Help Menu --------------------------------
    help_menu = ttk.Menu(menubar, tearoff=False)
    menubar.add_cascade(label="Help", menu=help_menu)
    help_menu.add_command(
        label="About",
        command=lambda: messagebox.showinfo(
            "About", "A.n.S Patcher by Felix\nVersion 1.0"
        ),
    )

    # ----------------------------------------------------------------
    #                       MAIN CONTENT AREA
    # ----------------------------------------------------------------
    main_frame = ttk.Frame(root, padding=10)
    main_frame.pack(expand=True, fill=BOTH)

    # --- Logo ---
    image_path = os.path.join(base_path, "assets", "logo.png")
    if os.path.exists(image_path):
        pil_image = Image.open(image_path).resize((200, 100))
        image = ImageTk.PhotoImage(pil_image)
        image_label = ttk.Label(main_frame, image=image)
        image_label.image = image  # Keep a reference
        image_label.pack(pady=10)
    else:
        print(f"⚠ Image not found: {image_path}")

    # --- Buttons ---
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=20)

    ttk.Button(
        button_frame, text="Leave Patcher", command=root.quit, bootstyle="danger"
    ).pack(side=LEFT, padx=10)

    ttk.Button(
        button_frame,
        text="Start patching",
        command=lambda: general_patcher.show_gen_patcher_window(root),
        bootstyle="success",
    ).pack(side=LEFT, padx=10)

    ttk.Button(
        main_frame,
        text="Advanced setup",
        command=lambda: uni_patcher.show_uni_patcher_window(root),
        bootstyle="link",
    ).pack(side=RIGHT, anchor=SE, padx=10, pady=10)

    root.mainloop()


# -------------------------------------------------------------------
#                            MAIN
# -------------------------------------------------------------------
if __name__ == "__main__":
    show_main_window()
