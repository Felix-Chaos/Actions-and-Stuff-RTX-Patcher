import os
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from PIL import Image, ImageTk
from src.gui.theme import *
from ..utils.helpers import resourcePath


class MainMenuFrame(ctk.CTkFrame):
    def __init__(self, parent, callbacks: dict):
        super().__init__(parent, fg_color="transparent")
        self.callbacks = callbacks

        # Main Layout: Top (Logo) -> Middle (Action Cards) -> Bottom (Buttons)

        # 1. Header (Logo)
        headerFrame = ctk.CTkFrame(self, fg_color="transparent")
        headerFrame.pack(fill="x", pady=20)

        try:
            # Try loading logo from assets/resources/icon.ico
            logoPath = resourcePath("assets/resources/icon.ico")
            if os.path.exists(logoPath):
                pilImg = Image.open(logoPath)
                pilImg = pilImg.resize((120, 120), Image.Resampling.LANCZOS)
                self.logoImg = ctk.CTkImage(
                    light_image=pilImg, dark_image=pilImg, size=(120, 120))
                logoLabel = ctk.CTkLabel(
                    headerFrame, image=self.logoImg, text="")
                logoLabel.pack()
        except Exception as e:
            print(f"Failed to load logo: {e}")

        ctk.CTkLabel(headerFrame, text="A&S RTX Patcher", font=(
            FONT_FAMILY, 28, "bold"), text_color=COLOR_ACCENT_2).pack(pady=10)

        # 2. Content Area (Grid)
        contentFrame = ctk.CTkFrame(self, fg_color="transparent")
        contentFrame.pack(expand=True, fill="both", padx=40, pady=0)

        contentFrame.columnconfigure(0, weight=1)
        contentFrame.columnconfigure(1, weight=1)

        # --- Primary Actions (Left Column) ---
        # Clean dark card with subtle border
        primaryFrame = ctk.CTkFrame(
            contentFrame, fg_color="#1a1a1a", border_width=1, border_color="#333333", corner_radius=12)
        primaryFrame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        ctk.CTkLabel(primaryFrame, text="Patching", font=(
            FONT_FAMILY, 18, "bold"), text_color="#FFFFFF").pack(pady=(20, 15))

        # 1. Normal Patcher (Marketplace) - FILLED GREEN BUTTON
        ctk.CTkButton(primaryFrame, text="⚡ Patch from Marketplace", command=self.callbacks.get("marketplace"),
                      fg_color=COLOR_ACCENT_1, text_color="#000000", hover_color="#32cc12",
                      height=45, font=(FONT_FAMILY, 14, "bold"), corner_radius=8).pack(pady=10, padx=25, fill="x")

        # 2. Zip/Custom Patcher (Hidden by default) - FILLED CYAN BUTTON
        self.zipBtn = ctk.CTkButton(primaryFrame, text="📦 Patch from Local File (Zip/Folder)", command=self.callbacks.get("manual"),
                                    fg_color=COLOR_ACCENT_2, text_color="#000000", hover_color="#00c4d4",
                                    height=45, font=(FONT_FAMILY, 14, "bold"), corner_radius=8)
        # self.zipBtn.pack(pady=10, padx=25, fill="x") # Hidden by default

        # --- Maintenance Actions (Right Column) ---
        maintFrame = ctk.CTkFrame(contentFrame, fg_color="#1a1a1a",
                                  border_width=1, border_color="#333333", corner_radius=12)
        maintFrame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        ctk.CTkLabel(maintFrame, text="Maintenance", font=(
            FONT_FAMILY, 18, "bold"), text_color="#FFFFFF").pack(pady=(20, 15))

        # Clean Old Versions - FILLED RED/ORANGE BUTTON
        ctk.CTkButton(maintFrame, text="🧹 Clean Old Versions", command=self.callbacks.get("clean"),
                      fg_color="#FF4444", text_color="#FFFFFF", hover_color="#cc3333",
                      height=45, font=(FONT_FAMILY, 14, "bold"), corner_radius=8).pack(pady=10, padx=25, fill="x")

        # New: Adjust RTX Settings - FILLED CYAN BUTTON
        self.rtxBtn = ctk.CTkButton(maintFrame, text="🎮 Adjust Settings for RTX", command=self.callbacks.get("rtx_settings"),
                                    fg_color=COLOR_ACCENT_2, text_color="#000000", hover_color="#00c4d4",
                                    height=45, font=(FONT_FAMILY, 14, "bold"), corner_radius=8)
        self.rtxBtn.pack(pady=10, padx=25, fill="x")

        # New: Adjust All Settings (Advanced only) - OUTLINED GRAY
        self.allSettingsBtn = ctk.CTkButton(maintFrame, text="⚙️ Adjust All Settings", command=self.callbacks.get("all_settings"),
                                            fg_color="transparent", border_width=2, border_color="#666666",
                                            text_color="#AAAAAA", hover_color="#2a2a2a",
                                            height=40, font=(FONT_FAMILY, 13), corner_radius=8)
        # Hidden by default

        # 3. Exit Button (Bottom) - Subtle text button
        ctk.CTkButton(self, text="Exit Application", command=self.callbacks.get("exit"),
                      fg_color="transparent", text_color="#888888", hover_color="#1a1a1a",
                      font=(FONT_FAMILY, 12)).pack(pady=20)

    def setAdvancedMode(self, enabled: bool):
        if enabled:
            if not self.zipBtn.winfo_ismapped():
                self.zipBtn.pack(pady=10, padx=20, fill="x",
                                 after=self.zipBtn.master.winfo_children()[1])
            if not self.allSettingsBtn.winfo_ismapped():
                self.allSettingsBtn.pack(pady=10, padx=20, fill="x")
        else:
            self.zipBtn.pack_forget()
            self.allSettingsBtn.pack_forget()


class PatchProgressFrame(ctk.CTkFrame):
    def __init__(self, parent, title: str, onBack: callable):
        super().__init__(parent, fg_color="transparent")
        self.onBack = onBack
        self.is_patching = False  # Track if patching is in progress

        container = ctk.CTkFrame(
            self, fg_color=COLOR_SURFACE, corner_radius=15)
        container.pack(expand=True, fill="both", padx=40, pady=40)

        self.titleLabel = ctk.CTkLabel(container, text=title, font=(
            FONT_FAMILY, 20, "bold"), text_color=COLOR_TEXT)
        self.titleLabel.pack(pady=(20, 20))

        # --- Advanced: Mode Selection ---
        self.advFrame = ctk.CTkFrame(container, fg_color="transparent")
        self.modeVar = ctk.StringVar(value="marketplace")

        modeRow = ctk.CTkFrame(self.advFrame, fg_color="transparent")
        modeRow.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(modeRow, text="Patch Method:", font=(
            FONT_FAMILY, 12, "bold")).pack(side="left", padx=(0, 10))
        ctk.CTkRadioButton(modeRow, text="Zip (Manual)", variable=self.modeVar, value="zip", command=self.onModeChanged,
                           fg_color=COLOR_ACCENT_1, hover_color=COLOR_ACCENT_1).pack(side="left", padx=5)
        ctk.CTkRadioButton(modeRow, text="Custom", variable=self.modeVar, value="custom", command=self.onModeChanged,
                           fg_color=COLOR_ACCENT_1, hover_color=COLOR_ACCENT_1).pack(side="left", padx=5)

        # --- Advanced: Version Selection ---
        self.versionVar = ctk.StringVar()
        verRow = ctk.CTkFrame(self.advFrame, fg_color="transparent")
        verRow.pack(fill="x", pady=(5, 10))
        ctk.CTkLabel(verRow, text="Target Version:", font=(
            FONT_FAMILY, 12, "bold")).pack(side="left", padx=(0, 10))
        self.versionCombo = ctk.CTkComboBox(verRow, variable=self.versionVar, values=[], state="readonly", width=200,
                                            button_color=COLOR_ACCENT_1, border_color=COLOR_ACCENT_1)
        self.versionCombo.pack(side="left", padx=5)
        # Note: ComboBox values need to be string list

        # --- Advanced: Custom Fields ---
        self.customFieldsFrame = ctk.CTkFrame(
            self.advFrame, fg_color="transparent")

        # Source
        ctk.CTkLabel(self.customFieldsFrame,
                     text="Source (Folder/Zip):", anchor="w").pack(fill="x")
        srcRow = ctk.CTkFrame(self.customFieldsFrame, fg_color="transparent")
        srcRow.pack(fill="x", pady=(0, 5))
        self.srcVar = ctk.StringVar()
        ctk.CTkEntry(srcRow, textvariable=self.srcVar).pack(
            side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkButton(srcRow, text="...", width=40, command=lambda: self.browsePath(
            self.srcVar), **get_button_style("secondary")).pack(side="left")

        # Target
        ctk.CTkLabel(self.customFieldsFrame,
                     text="Output Filename (.mcpack):", anchor="w").pack(fill="x")
        tgtRow = ctk.CTkFrame(self.customFieldsFrame, fg_color="transparent")
        tgtRow.pack(fill="x", pady=(0, 5))
        self.tgtVar = ctk.StringVar()
        ctk.CTkEntry(tgtRow, textvariable=self.tgtVar).pack(
            side="left", fill="x", expand=True)

        # Patch File
        ctk.CTkLabel(self.customFieldsFrame,
                     text="Patch File (.vcdiff):", anchor="w").pack(fill="x")
        patchRow = ctk.CTkFrame(self.customFieldsFrame, fg_color="transparent")
        patchRow.pack(fill="x", pady=(0, 5))
        self.patchVar = ctk.StringVar()
        ctk.CTkEntry(patchRow, textvariable=self.patchVar).pack(
            side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkButton(patchRow, text="...", width=40, command=lambda: self.browsePatchFile(
            self.patchVar), **get_button_style("secondary")).pack(side="left")

        # --- Log Area ---
        self.logFrame = ctk.CTkFrame(container, fg_color="transparent")
        ctk.CTkLabel(self.logFrame, text="Process Log:", font=(
            FONT_FAMILY, 12, "bold"), anchor="w").pack(fill="x")
        self.logArea = ctk.CTkTextbox(self.logFrame, height=150, font=(
            "Consolas", 10), text_color="#dddddd", fg_color="#111111")
        self.logArea.pack(fill="both", expand=True)
        self.logArea.configure(state='disabled')

        self.logBtnRow = ctk.CTkFrame(self.logFrame, fg_color="transparent")
        self.logBtnRow.pack(fill="x", pady=(5, 0))
        ctk.CTkButton(self.logBtnRow, text="📋 Copy Log", width=100,
                      command=self.copyLog, **get_button_style("secondary")).pack(side="right")

        self.statusLabel = ctk.CTkLabel(
            container, text="Ready...", text_color=COLOR_ACCENT_1)
        self.statusLabel.pack(pady=(10, 5))

        self.progressBar = ctk.CTkProgressBar(
            container, orientation="horizontal", progress_color=COLOR_ACCENT_1)
        self.progressBar.set(0)
        self.progressBar.pack(pady=(0, 10), fill="x", padx=40)

        self.cleanOldVersionsVar = ctk.BooleanVar(value=True)
        self.cleanCheck = ctk.CTkCheckBox(container, text="Clean old versions before patching",
                                          variable=self.cleanOldVersionsVar, fg_color=COLOR_ACCENT_1, hover_color=COLOR_ACCENT_1)
        self.cleanCheck.pack(pady=(0, 20))

        self.btnFrame = ctk.CTkFrame(container, fg_color="transparent")
        self.btnFrame.pack(pady=(0, 20))

        self.actionBtn = ctk.CTkButton(
            self.btnFrame, text="Start", width=120, state="disabled", **get_button_style("filled-primary"))
        self.actionBtn.pack(side="left", padx=5)

        self.secondaryBtn = ctk.CTkButton(
            self.btnFrame, text="Open Folder", width=120, **get_button_style("secondary"))
        # Hidden by default

        ctk.CTkButton(self.btnFrame, text="Back", width=120, command=self._handleBack,
                      **get_button_style("danger")).pack(side="left", padx=5)

    def _handleBack(self):
        """Handle back button click with warning if patching is in progress."""
        if self.is_patching:
            from tkinter import messagebox
            result = messagebox.askyesno(
                "Cancel Patching?",
                "Patching is currently in progress.\n\n"
                "Going back will stop the patching process and clean up temporary files.\n\n"
                "Are you sure you want to cancel?",
                icon='warning'
            )
            if result:
                # User confirmed - call the back callback which should handle cleanup
                self.onBack()
        else:
            # Not patching, safe to go back
            self.onBack()

    def setSecondaryAction(self, command: callable, text: str = "Open Folder"):
        self.secondaryBtn.configure(command=command, text=text)
        if not self.secondaryBtn.winfo_ismapped():
            self.secondaryBtn.pack(side="left", padx=5,
                                   before=self.btnFrame.winfo_children()[-1])

    def hideSecondaryAction(self):
        self.secondaryBtn.pack_forget()

    def browsePatchFile(self, var):
        f = filedialog.askopenfilename(
            filetypes=[("VCDIFF Patch", "*.vcdiff"), ("All Files", "*.*")])
        if f:
            var.set(f)

    def browsePath(self, var):
        f = filedialog.askopenfilename()
        if not f:
            f = filedialog.askdirectory()
        if f:
            var.set(f)

    def onModeChanged(self):
        mode = self.modeVar.get()
        if mode == "custom":
            self.customFieldsFrame.pack(fill="x", pady=10)
        else:
            self.customFieldsFrame.pack_forget()

    def setAdvancedMode(self, enabled: bool):
        if enabled:
            self.advFrame.pack(after=self.titleLabel, pady=(0, 20), fill="x")
            self.logFrame.pack(before=self.btnFrame, pady=(
                10, 20), fill="both", expand=True)
            self.onModeChanged()
        else:
            self.advFrame.pack_forget()
            self.logFrame.pack_forget()

    def appendLog(self, text: str):
        self.logArea.configure(state='normal')
        self.logArea.insert(tk.END, text + "\n")
        self.logArea.see(tk.END)
        self.logArea.configure(state='disabled')

    def copyLog(self):
        text = self.logArea.get("1.0", tk.END)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()

    def setStatus(self, text: str):
        self.statusLabel.configure(text=text)

    def setProgress(self, value: float, mode: str = 'determinate'):
        # value 0-100 -> 0.0-1.0
        if mode == 'indeterminate':
            self.progressBar.configure(mode='indeterminate')
            self.progressBar.start()
        else:
            self.progressBar.configure(mode='determinate')
            self.progressBar.stop()
            self.progressBar.set(value / 100.0)

    def setActionCommand(self, command: callable, text: str = "Patch"):
        self.actionBtn.configure(command=command, text=text)

    def setActionState(self, state: str):
        self.actionBtn.configure(state=state)

    def setVersions(self, versions: list):
        self.versionCombo.configure(values=versions)
        if versions:
            self.versionCombo.set(versions[0])
