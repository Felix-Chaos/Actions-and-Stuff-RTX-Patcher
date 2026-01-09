import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from typing import Callable, List, Tuple

class MainWindow(ttk.Window):
    def __init__(self, title: str, theme: str = "cyborg", onClose: Callable = None):
        super().__init__(themename=theme)
        self.title(title)
        self.geometry("800x600") # Increased size for new design
        
        self.onCloseCallback = onClose
        if self.onCloseCallback:
            self.protocol("WM_DELETE_WINDOW", self.onCloseCallback)

        # Menu Bar
        self.menuBar = ttk.Menu(self)
        self.config(menu=self.menuBar)
        
        self.toolsMenu = ttk.Menu(self.menuBar, tearoff=False)
        self.menuBar.add_cascade(label="Creator Tools", menu=self.toolsMenu)
        
        self.depMenu = ttk.Menu(self.menuBar, tearoff=False)
        self.menuBar.add_cascade(label="Dependencies", menu=self.depMenu)

        self.helpMenu = ttk.Menu(self.menuBar, tearoff=False)
        self.menuBar.add_cascade(label="Help", menu=self.helpMenu)

        # Container
        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True)
        
        # Footer
        self.footer = ttk.Frame(self, padding=10)
        self.footer.pack(fill="x", side="bottom")
        
        self.advancedVar = tk.BooleanVar(value=False)
        self.advancedSwitch = ttk.Checkbutton(
            self.footer, 
            text="Advanced Mode", 
            variable=self.advancedVar, 
            bootstyle="round-toggle"
        )
        self.advancedSwitch.pack(side="right")
        
        ttk.Label(self.footer, text="v2.0 Reforged", font=("Segoe UI", 8), bootstyle="secondary").pack(side="left")

        self.frames = {}
        self.currentFrame = None

    def addFrame(self, name: str, frame: ttk.Frame):
        self.frames[name] = frame
        frame.place(relwidth=1, relheight=1)

    def showFrame(self, name: str):
        if name in self.frames:
            frame = self.frames[name]
            frame.tkraise()
            self.currentFrame = frame

    def setIcon(self, iconPath: str):
        if not iconPath: return
        try:
            self.iconbitmap(iconPath)
        except Exception:
            pass
            
    def populateToolsMenu(self, scripts: List[Tuple[str, str, Callable]]):
        if not scripts:
            self.toolsMenu.add_command(label="No scripts found", state="disabled")
            return
        for label, _, command in scripts:
            self.toolsMenu.add_command(label=label, command=command)

    def populateDepMenu(self, commands: List[Tuple[str, Callable]]):
        for label, command in commands:
            self.depMenu.add_command(label=label, command=command)
            
    def populateHelpMenu(self, commands: List[Tuple[str, Callable]]):
         for label, command in commands:
            self.helpMenu.add_command(label=label, command=command)

    def bindAdvancedToggle(self, callback: Callable):
        self.advancedSwitch.config(command=lambda: callback(self.advancedVar.get()))
