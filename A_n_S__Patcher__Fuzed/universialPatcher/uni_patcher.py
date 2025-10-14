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

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import patcher_methods as patcher_methods
class MainMenuFrame(ttk.Frame):
    """The main menu view with buttons for each action."""
    def __init__(self, parent: tk.Widget, controller: 'App'):
        super().__init__(parent)
        self.controller = controller
        
        container = ttk.Frame(self, padding=30)
        container.pack(expand=True)

        ttk.Label(container, text="AnS RTX Patcher", font=("Segoe UI", 16, "bold")).pack(pady=(0, 20))
        ttk.Button(container, text="Patch from Marketplace", width=40, command=lambda: controller.show_frame("MarketplacePatcherFrame"), bootstyle=INFO).pack(pady=8)
        ttk.Button(container, text="Patch from .zip/.mcpack", width=40, command=lambda: controller.show_frame("ZipPatcherFrame"), bootstyle=PRIMARY).pack(pady=8)
        ttk.Button(container, text="Clean Old Versions for Update", width=40, command=lambda: controller.show_frame("UpdateCleanerFrame"), bootstyle=WARNING).pack(pady=8)
        ttk.Button(container, text="Exit", width=40, command=controller.on_close, bootstyle=(DANGER, OUTLINE)).pack(pady=(20, 0))

class App(ttk.Window):
    """The main application that holds and manages all the view frames."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title("AnS RTX Patcher")
        self.geometry("700x400")
        patcher_methods.center_window(self)
        self._setup_theme_and_icon()
        self.container = ttk.Frame(self)
        self.container.pack(side="top", fill="both", expand=True)
        self.frames: Dict[str, type] = {F.__name__: F for F in (MainMenuFrame, MessageFrame, PatchSelectionFrame, MarketplacePatcherFrame, ZipPatcherFrame, UpdateCleanerFrame)}
        self.current_frame: Optional[ttk.Frame] = None
        
        self.patch_temp_dir = os.path.join(tempfile.gettempdir(), "AnSPatcher", "patches")
        self.output_temp_dir = os.path.join(tempfile.gettempdir(), "AnSPatcher", "output")
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self.show_frame, "PatchSelectionFrame")