import sys
import os
import tkinter as tk
from tkinter import ttk
import subprocess
import threading
from tkinter import messagebox

def resourcePath(relativePath: str) -> str:
    """Gets the absolute path to a resource, works for dev and for PyInstaller."""
    try:
        basePath = sys._MEIPASS
    except AttributeError:
        # Use path relative to this file (src/utils/helpers.py) -> Go up 2 levels to app root
        currentDir = os.path.dirname(os.path.abspath(__file__))
        basePath = os.path.dirname(os.path.dirname(currentDir))
        
    return os.path.join(basePath, relativePath)

def centerWindow(window: tk.Toplevel | tk.Tk) -> None:
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
                    subprocess.run(["py", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                    python_exe = "py"
                except Exception:
                    python_exe = "python"
            else:
                python_exe = sys.executable

            cmd = [python_exe, scriptPath]
            
            proc = subprocess.Popen(cmd, creationflags=creationFlags)
            exitCode = proc.wait()
            
            # Callback to main thread
            root.after(0, lambda: onDone(exitCode))
        except Exception as e:
            root.after(0, lambda: onErr(e))

    def onDone(exitCode):
        if exitCode == 0:
            messagebox.showinfo("Success", f"'{scriptLabel}' finished successfully.")
        else:
            messagebox.showwarning("Finished with errors", f"'{scriptLabel}' finished with exit code {exitCode}.")

    def onErr(e):
        messagebox.showerror("Execution Error", f"Failed to run '{scriptLabel}':\n{e}")

    threading.Thread(target=worker, daemon=True).start()

def showErrorWithCopy(title: str, message: str, parent=None):
    """Shows an error dialog with a Copy button."""
    # Use top-level
    if parent:
        win = tk.Toplevel(parent)
    else:
        win = tk.Toplevel()
        
    win.title(title)
    win.geometry("500x300")
    centerWindow(win)
    
    # Message area
    lbl = ttk.Label(win, text="An error occurred:", font=("Segoe UI", 10, "bold"))
    lbl.pack(pady=(15, 5), padx=15, anchor="w")
    
    # Text widget for message (copyable)
    txtFrame = ttk.Frame(win)
    txtFrame.pack(fill="both", expand=True, padx=15, pady=5)
    
    scroll = ttk.Scrollbar(txtFrame)
    scroll.pack(side="right", fill="y")
    
    txt = tk.Text(txtFrame, height=8, width=50, wrap="word", yscrollcommand=scroll.set, font=("Segoe UI", 9))
    txt.pack(side="left", fill="both", expand=True)
    scroll.config(command=txt.yview)
    
    txt.insert("1.0", message)
    txt.config(state="disabled") # Read-only
    
    # Buttons
    btnFrame = ttk.Frame(win)
    btnFrame.pack(fill="x", pady=20, padx=15)
    
    def copyToClipboard():
        win.clipboard_clear()
        win.clipboard_append(message)
        win.update() # Required for clipboard to finalize
        
    # Copy Button
    ttk.Button(btnFrame, text="📋 Copy Error", command=copyToClipboard).pack(side="left")
    
    # OK Button
    ttk.Button(btnFrame, text="OK", command=win.destroy, width=15).pack(side="right")
    
    # Modal behavior
    win.transient(parent) if parent else None
    win.grab_set()
    parent.wait_window(win) if parent else None
