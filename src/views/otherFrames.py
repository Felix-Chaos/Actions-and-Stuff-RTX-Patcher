import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

class CleanFrame(ttk.Frame):
    def __init__(self, parent, onConfirm: callable, onBack: callable):
        super().__init__(parent)
        self.onConfirm = onConfirm

        container = ttk.Frame(self, padding=30)
        container.pack(expand=True, fill="both")

        self.label = ttk.Label(container, text="Searching for old packs...", font=("Segoe UI", 12))
        self.label.pack(pady=(0, 10))

        self.progressBar = ttk.Progressbar(container, mode='indeterminate', length=400, bootstyle=INFO)
        self.progressBar.pack(pady=(0, 10))
        self.progressBar.start()

        self.resultsBox = tk.Text(container, height=10, width=70, state="disabled", wrap="none")
        self.resultsBox.pack(pady=(5, 5))

        btnFrame = ttk.Frame(container)
        btnFrame.pack(pady=(10, 0))

        self.confirmBtn = ttk.Button(btnFrame, text="Confirm Deletion", width=20, state="disabled",
                                     command=self.onConfirm, bootstyle=SUCCESS)
        self.confirmBtn.pack(side="left", padx=5)

        ttk.Button(btnFrame, text="Back", width=20, command=onBack, bootstyle=(DANGER, OUTLINE)).pack(side="left", padx=5)

    def updateResults(self, text: str):
        self.resultsBox.config(state="normal")
        self.resultsBox.delete("1.0", "end")
        self.resultsBox.insert("end", text)
        self.resultsBox.config(state="disabled")

    def enableConfirm(self):
        self.confirmBtn.config(state="normal")
        self.progressBar.stop()
        self.progressBar.pack_forget()

class FixFrame(ttk.Frame):
    def __init__(self, parent, onMove: callable, onRestore: callable, onBack: callable):
        super().__init__(parent)

        container = ttk.Frame(self, padding=30)
        container.pack(expand=True)

        ttk.Label(container, text="Fix for 1.21.80 Issues", font=("Segoe UI", 16, "bold")).pack(pady=(0, 20))

        infoText = (
            "This fix moves your Marketplace texture packs from the 'premium_cache' folder to 'com.mojang'. "
            "This is a workaround for Minecraft 1.21.80 preventing MER maps from loading when Marketplace packs are active."
        )
        ttk.Label(container, text=infoText, wraplength=450, justify="center").pack(pady=(0, 20))

        ttk.Label(container, text="⚠️ Use Restore BEFORE patching new updates!", bootstyle=DANGER).pack(pady=(0, 20))

        self.moveBtn = ttk.Button(container, text="Move Marketplace Folders", width=30,
                                  command=onMove, bootstyle=SUCCESS)
        self.moveBtn.pack(pady=5)

        self.restoreBtn = ttk.Button(container, text="Restore Marketplace Folders", width=30,
                                     command=onRestore, bootstyle=WARNING)
        self.restoreBtn.pack(pady=5)

        ttk.Button(container, text="Back", width=30, command=onBack, bootstyle=(SECONDARY, OUTLINE)).pack(pady=20)
