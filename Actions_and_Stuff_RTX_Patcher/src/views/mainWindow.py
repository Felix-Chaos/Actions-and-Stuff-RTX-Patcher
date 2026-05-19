import tkinter as tk
from typing import Callable, List, Tuple
import customtkinter as ctk
from src.gui.theme import *
from src.version import VERSION


class MainWindow(ctk.CTk):
    def __init__(self, title: str, _theme: str = "dark", onClose: Callable = None):
        super().__init__()

        # Apply Theme
        apply_theme()

        self.title(title)
        self.geometry("900x700")
        self.configure(fg_color=COLOR_BG_BOTTOM)

        self.onCloseCallback = onClose
        if self.onCloseCallback:
            self.protocol("WM_DELETE_WINDOW", self.onCloseCallback)

        # Menu Bar (Native - CTK doesn't fully style this on Windows yet, but it works)
        # We keep it for now as per plan to adhere to "minimal disruption" for menus
        self.menuBar = tk.Menu(self)
        self.config(menu=self.menuBar)

        self.toolsMenu = tk.Menu(self.menuBar, tearoff=False)
        self.menuBar.add_cascade(label="Creator Tools", menu=self.toolsMenu)

        self.depMenu = tk.Menu(self.menuBar, tearoff=False)
        self.menuBar.add_cascade(label="Dependencies", menu=self.depMenu)

        self.helpMenu = tk.Menu(self.menuBar, tearoff=False)
        self.menuBar.add_cascade(label="Help", menu=self.helpMenu)

        # Container (Transparent to show gradient)
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        # Footer (Minimalist/Transparent)
        self.footer = ctk.CTkFrame(
            self, height=30, fg_color="#111111", corner_radius=0)  # Dark bar at bottom
        self.footer.pack(fill="x", side="bottom")

        self.versionLabel = ctk.CTkLabel(
            self.footer, text=f"v{VERSION}", text_color="gray", font=(FONT_FAMILY, 10))
        self.versionLabel.pack(side="left", padx=10)

        self.advancedVar = ctk.BooleanVar(value=False)
        self.advancedSwitch = ctk.CTkSwitch(self.footer, text="Advanced Mode", command=self.toggleAdvanced,
                                            progress_color=COLOR_ACCENT_1, fg_color="#333333", button_color="white",
                                            font=(FONT_FAMILY, 11), text_color="gray", variable=self.advancedVar)
        self.advancedSwitch.pack(side="right", padx=10, pady=5)

        # The original advancedSwitch and version label were replaced/modified by the snippet.
        # The snippet had a duplicate `text_color=COLOR_TEXT` and a version label.
        # I've integrated the new advSwitch and versionLabel, and removed the old ones.

        self.frames = {}
        self.currentFrame = None

    def addFrame(self, name: str, frame: ctk.CTkFrame):
        self.frames[name] = frame
        frame.place(relwidth=1, relheight=1)

    def showFrame(self, name: str):
        if name in self.frames:
            frame = self.frames[name]
            frame.tkraise()
            self.currentFrame = frame

    def setIcon(self, iconPath: str):
        if not iconPath:
            return
        try:
            self.iconbitmap(iconPath)
        except Exception:
            pass

    def populateToolsMenu(self, scripts: List[Tuple[str, str, Callable]]):
        if not scripts:
            self.toolsMenu.add_command(
                label="No scripts found", state="disabled")
            return
        for label, _, command in scripts:
            self.toolsMenu.add_command(label=label, command=command)

    def populateDepMenu(self, commands: List[Tuple[str, Callable]]):
        for label, command in commands:
            self.depMenu.add_command(label=label, command=command)

    def populateHelpMenu(self, commands: List[Tuple[str, Callable]]):
        for label, command in commands:
            self.helpMenu.add_command(label=label, command=command)

    def toggleAdvanced(self):
        """Called when the advanced mode switch is toggled."""
    def setAdvancedSwitchVisible(self, visible: bool):
        """Show or hide the advanced mode switch."""
        if visible:
            if not self.advancedSwitch.winfo_ismapped():
                self.advancedSwitch.pack(side="right", padx=10, pady=5)
        else:
            self.advancedSwitch.pack_forget()

    def bindAdvancedToggle(self, callback: Callable):
        def wrapped_callback():
            callback(self.advancedVar.get())

        self.advancedSwitch.configure(command=wrapped_callback)
