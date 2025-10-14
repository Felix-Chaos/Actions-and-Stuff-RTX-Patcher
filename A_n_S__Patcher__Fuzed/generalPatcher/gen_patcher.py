import ctypes
import json
import locale
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import zipfile
from collections import defaultdict
from tkinter import filedialog
from typing import Any, Callable, Dict, List, Optional, Tuple
import patcher_methods as patcher_methods
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
def show_main_menu():
    root = ttk.Window(themename="darkly")
    root.title("AnS RTX Patcher")
    root.geometry("500x320")

    icon_path = patcher_methods.resource_path("AnSPatchericon.ico")
    if os.path.exists(icon_path):
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(u"AnSPatcher")
        root.iconbitmap(icon_path)
        try:
            root.tk.call('wm', 'iconphoto', root._w, tk.PhotoImage(file=icon_path))
        except:
            pass

    frame = ttk.Frame(root, padding=30)
    frame.pack()
    patcher_methods.center_window(root)

    ttk.Label(frame, text="AnS RTX Patcher", font=("Segoe UI", 16, "bold")).pack(pady=(0, 20))

    btn_patch_marketplace = ttk.Button(
        frame,
        text="Patch from marketplace",
        width=30,
        command=lambda: [root.withdraw(), patch_from_marketplace(root)],
        bootstyle=INFO
    )
    btn_patch_decrypted = ttk.Button(
        frame,
        text="Patch from .zip/.mcpack",
        width=30,
        command=lambda: [root.withdraw(), patch_decrypted_zip(root)],
        bootstyle=PRIMARY
    )
    btn_clean = ttk.Button(
    frame,
    text="Clean for Update (press before installing patched mcpack)",
    width=55,
    command=clean_for_update,
    bootstyle=WARNING
    )
    btn_exit = ttk.Button(
        frame,
        text="Exit",
        width=30,
        command=root.destroy,
        bootstyle=(DANGER, OUTLINE)
    )

    btn_patch_marketplace.pack(pady=10)
    btn_patch_decrypted.pack(pady=10)
    btn_clean.pack(pady=10)
    btn_exit.pack(pady=10)
