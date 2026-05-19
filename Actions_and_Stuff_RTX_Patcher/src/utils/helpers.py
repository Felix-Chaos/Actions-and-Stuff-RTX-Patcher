import sys
import os
import subprocess
import threading
import json
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

def resourcePath(relativePath: str) -> str:
    """Gets the absolute path to a resource, works for dev and for PyInstaller."""
    try:
        basePath = sys._MEIPASS
    except AttributeError:
        # Use path relative to this file (src/utils/helpers.py) -> Go up 2 levels to app root
        currentDir = os.path.dirname(os.path.abspath(__file__))
        basePath = os.path.dirname(os.path.dirname(currentDir))

    return os.path.join(basePath, relativePath)


def centerWindow(window) -> None:
    """Centers a tkinter window on the screen."""
    window.update_idletasks()
    width = window.winfo_width()
    height = window.winfo_height()
    ws = window.winfo_screenwidth()
    hs = window.winfo_screenheight()
    x = (ws // 2) - (width // 2)
    y = (hs // 2) - (height // 2)
    window.geometry(f'{width}x{height}+{x}+{y}')
    window.attributes('-topmost', True)


def runScriptInThread(root: tk.Widget, scriptPath: str, scriptLabel: str):
    """Runs a python script in a separate process/thread."""
    def worker():
        try:
            # Creation flags for new console window on Windows
            creationFlags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0

            # Determine python interpreter
            if getattr(sys, 'frozen', False):
                # If frozen, sys.executable is the exe itself. Try using system python.
                # Assuming 'py' launcher or 'python' is in PATH.
                try:
                    subprocess.run(
                        ["py", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                    python_exe = "py"
                except Exception:
                    python_exe = "python"
            else:
                python_exe = sys.executable

            cmd = [python_exe, scriptPath]

            # Use Popen context manager if possible, but Popen in Py < 3.2 didn't support it well.
            # Python 3+ supports it. It automatically closes streams, but doesn't wait.
            with subprocess.Popen(cmd, creationflags=creationFlags) as proc:
                exitCode = proc.wait()

            # Callback to main thread
            root.after(0, lambda: onDone(exitCode))
        except Exception as e:
            root.after(0, lambda: onErr(e))

    def onDone(exitCode):
        if exitCode == 0:
            messagebox.showinfo(
                "Success", f"'{scriptLabel}' finished successfully.")
        else:
            messagebox.showwarning(
                "Finished with errors", f"'{scriptLabel}' finished with exit code {exitCode}.")

    def onErr(e):
        messagebox.showerror(
            "Execution Error", f"Failed to run '{scriptLabel}':\n{e}")

    threading.Thread(target=worker, daemon=True).start()


def showErrorWithCopy(title: str, message: str, parent=None, log_text: str = None):
    """Shows an error dialog with a Copy button using customtkinter, referencing an errors.json file for explanations."""
    
    # Try to determine root/parent
    if parent:
        win = ctk.CTkToplevel(parent)
        win.transient(parent)
    else:
        win = ctk.CTkToplevel()

    win.title(title)
    win.geometry("550x450")
    
    # Apply icon after window creation
    icon_path = resourcePath("assets/resources/icon.ico")
    if os.path.exists(icon_path):
        win.after(200, lambda: win.iconbitmap(icon_path))

    centerWindow(win)

    if not log_text and parent and hasattr(parent, "getLogText"):
        try:
            log_text = parent.getLogText()
        except tk.TclError:
            pass

    # Load custom explanations
    explanation = None
    try:
        errors_path = resourcePath("assets/resources/errors.json")
        if os.path.exists(errors_path):
            with open(errors_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for err_obj in data.get("errors", []):
                    for kw in err_obj.get("keywords", []):
                        if kw.lower() in message.lower():
                            explanation = err_obj.get("explanation")
                            break
                    if explanation:
                        break
    except Exception:
        pass

    # Message area
    lbl = ctk.CTkLabel(win, text="An error occurred:", font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"))
    lbl.pack(pady=(20, 5), padx=20, anchor="w")

    if explanation:
        exp_lbl = ctk.CTkLabel(win, text=explanation, font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#FFB3B3", justify="left", wraplength=500)
        exp_lbl.pack(pady=(0, 10), padx=20, anchor="w")

    txt = ctk.CTkTextbox(win, height=200, width=500, font=ctk.CTkFont(family="Segoe UI", size=12))
    txt.pack(fill="both", expand=True, padx=20, pady=5)

    txt.insert("1.0", message)
    txt.configure(state="disabled")  # Read-only

    # Buttons
    btnFrame = ctk.CTkFrame(win, fg_color="transparent")
    btnFrame.pack(fill="x", pady=20, padx=20)

    def copyError():
        win.clipboard_clear()
        win.clipboard_append(message)
        win.update()

    def copyLog():
        win.clipboard_clear()
        win.clipboard_append(log_text if log_text else message)
        win.update()

    # Copy Error Button
    ctk.CTkButton(btnFrame, text="📋 Copy Error", command=copyError, width=120).pack(side="left")
    
    # Copy Log Button (only if log is provided)
    if log_text:
        ctk.CTkButton(btnFrame, text="📋 Copy Log", command=copyLog, width=120).pack(side="left", padx=10)

    # OK Button
    ctk.CTkButton(btnFrame, text="OK", command=win.destroy, width=120).pack(side="right")

    # Modal behavior
    win.grab_set()
    if parent:
        parent.wait_window(win)
