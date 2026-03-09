import tkinter as tk
import customtkinter as ctk
from src.gui.theme import *


class CleanFrame(ctk.CTkFrame):
    def __init__(self, parent, onConfirm: callable, onBack: callable):
        super().__init__(parent, fg_color="transparent")
        self.onConfirm = onConfirm

        container = ctk.CTkFrame(self, fg_color=COLOR_SURFACE,
                                 corner_radius=15, border_width=2, border_color=COLOR_ACCENT_1)
        container.pack(expand=True, fill="both", padx=40, pady=40)

        self.label = ctk.CTkLabel(container, text="Searching for old packs...", font=(
            FONT_FAMILY, 20), text_color=COLOR_TEXT)
        self.label.pack(pady=(20, 10))

        self.progressBar = ctk.CTkProgressBar(
            container, orientation="horizontal", progress_color=COLOR_ACCENT_1, mode='indeterminate')
        self.progressBar.pack(pady=(0, 20), fill="x", padx=40)
        self.progressBar.start()

        self.resultsBox = ctk.CTkTextbox(container, height=200, font=(
            "Consolas", 10), text_color="#dddddd", fg_color="#111111")
        self.resultsBox.pack(pady=(5, 20), fill="both", expand=True, padx=20)
        self.resultsBox.configure(state="disabled")

        btnFrame = ctk.CTkFrame(container, fg_color="transparent")
        btnFrame.pack(pady=(0, 20))

        self.confirmBtn = ctk.CTkButton(btnFrame, text="Confirm Deletion", width=150, state="disabled",
                                        command=self.onConfirm, **get_button_style("filled-primary"))
        self.confirmBtn.pack(side="left", padx=10)

        ctk.CTkButton(btnFrame, text="Back", width=150, command=onBack,
                      **get_button_style("danger")).pack(side="left", padx=10)

    def updateResults(self, text: str):
        self.resultsBox.configure(state="normal")
        self.resultsBox.delete("1.0", "end")
        self.resultsBox.insert("end", text)
        self.resultsBox.configure(state="disabled")

    def enableConfirm(self):
        self.confirmBtn.configure(state="normal")
        self.progressBar.stop()
        self.progressBar.pack_forget()


class FixFrame(ctk.CTkFrame):
    def __init__(self, parent, onMove: callable, onRestore: callable, onBack: callable):
        super().__init__(parent, fg_color="transparent")

        container = ctk.CTkFrame(self, fg_color=COLOR_SURFACE,
                                 corner_radius=15, border_width=2, border_color="#FF8800")
        container.pack(expand=True, padx=40, pady=40)

        ctk.CTkLabel(container, text="Fix for 1.21.80 Issues", font=(
            FONT_FAMILY, 24, "bold"), text_color="#FF8800").pack(pady=(30, 20))

        infoText = (
            "This fix moves your Marketplace texture packs from the 'premium_cache' folder to 'com.mojang'.\n\n"
            "This is a workaround for Minecraft 1.21.80 preventing MER maps from loading when Marketplace packs are active."
        )
        ctk.CTkLabel(container, text=infoText, wraplength=450, justify="center", font=(
            FONT_FAMILY, 14)).pack(pady=(0, 30), padx=20)

        ctk.CTkLabel(container, text="⚠️ Use Restore BEFORE patching new updates!",
                     text_color="#FF5555", font=(FONT_FAMILY, 14, "bold")).pack(pady=(0, 20))

        self.moveBtn = ctk.CTkButton(container, text="Move Marketplace Folders", width=250, height=40,
                                     command=onMove, **get_button_style("filled-primary"))
        self.moveBtn.pack(pady=10)

        self.restoreBtn = ctk.CTkButton(container, text="Restore Marketplace Folders", width=250, height=40,
                                        command=onRestore, fg_color="#FF8800", text_color="black", hover_color="#CC6600")
        self.restoreBtn.pack(pady=10)

        ctk.CTkButton(container, text="Back", width=250, height=40,
                      command=onBack, **get_button_style("secondary")).pack(pady=30)
