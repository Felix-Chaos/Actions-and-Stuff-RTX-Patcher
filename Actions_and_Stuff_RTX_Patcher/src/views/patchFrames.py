import os
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from PIL import Image
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
        primaryFrame = ctk.CTkFrame(
            contentFrame, fg_color="#1a1a1a", border_width=1, border_color="#333333", corner_radius=12)
        primaryFrame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        ctk.CTkLabel(primaryFrame, text="Patching", font=(
            FONT_FAMILY, 18, "bold"), text_color="#FFFFFF").pack(pady=(20, 15))

        # 1. Normal Patcher (Marketplace) - FILLED GREEN BUTTON
        ctk.CTkButton(primaryFrame, text="⚡ Patch from Marketplace", command=self.callbacks.get("marketplace"),
                      fg_color=COLOR_ACCENT_1, text_color="#000000", hover_color="#32cc12",
                      height=45, font=(FONT_FAMILY, 14, "bold"), corner_radius=8).pack(pady=(0, 10), padx=25, fill="x")

        # 2. Zip/Custom Patcher (Hidden by default) - FILLED CYAN BUTTON
        self.zipBtn = ctk.CTkButton(primaryFrame, text="📦 Patch from Local File (Zip/Folder)", command=self.callbacks.get("manual"),
                                    fg_color=COLOR_ACCENT_2, text_color="#000000", hover_color="#00c4d4",
                                    height=45, font=(FONT_FAMILY, 14, "bold"), corner_radius=8)
        # self.zipBtn.pack(pady=10, padx=25, fill="x") # Hidden by default

        # Cleanup checkbox — subtle, smaller, below buttons
        self.cleanOldVersionsVar = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(primaryFrame, text="Clean old versions before patching",
                        variable=self.cleanOldVersionsVar,
                        fg_color="#555555", hover_color="#666666",
                        checkmark_color="#cccccc", border_color="#555555",
                        text_color="#777777",
                        font=(FONT_FAMILY, 11)).pack(pady=(0, 15), padx=25, anchor="w")

        # Brarchive Extractor checkbox [Beta]
        self.extractBrarchivesVar = ctk.BooleanVar(value=False)
        self.extractBrarchivesCheck = ctk.CTkCheckBox(primaryFrame, text="[Beta] Extract Brachives",
                                                      variable=self.extractBrarchivesVar, 
                                                      fg_color="#555555", hover_color="#666666",
                        checkmark_color="#cccccc", border_color="#555555",
                        text_color="#777777",
                        font=(FONT_FAMILY, 11))
        self.extractBrarchivesHint = ctk.CTkLabel(primaryFrame, text="Info: Not needed right now. A notification will be published when it's needed.\nExtracts .brarchive data from the source and patches directly against it.", 
                                                  text_color="#888888", font=(FONT_FAMILY, 10), justify="left")

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

        # Adjust RTX Settings - FILLED CYAN BUTTON
        self.rtxBtn = ctk.CTkButton(maintFrame, text="🎮 Adjust Settings for RTX", command=self.callbacks.get("rtx_settings"),
                                    fg_color=COLOR_ACCENT_2, text_color="#000000", hover_color="#00c4d4",
                                    height=45, font=(FONT_FAMILY, 14, "bold"), corner_radius=8)
        self.rtxBtn.pack(pady=10, padx=25, fill="x")

        # Adjust All Settings (Advanced only) - OUTLINED GRAY
        self.allSettingsBtn = ctk.CTkButton(maintFrame, text="⚙️ Adjust All Settings", command=self.callbacks.get("all_settings"),
                                            fg_color="transparent", border_width=2, border_color="#666666",
                                            text_color="#AAAAAA", hover_color="#2a2a2a",
                                            height=40, font=(FONT_FAMILY, 13), corner_radius=8)
        # Hidden by default

        # Exit Button (Bottom)
        ctk.CTkButton(self, text="Exit Application", command=self.callbacks.get("exit"),
                      fg_color="transparent", text_color="#888888", hover_color="#1a1a1a",
                      font=(FONT_FAMILY, 12)).pack(pady=20)

    def setAdvancedMode(self, enabled: bool):
        if enabled:
            if not self.zipBtn.winfo_ismapped():
                self.zipBtn.pack(pady=10, padx=20, fill="x",
                                 after=self.zipBtn.master.winfo_children()[1])
            if not self.extractBrarchivesCheck.winfo_ismapped():
                self.extractBrarchivesCheck.pack(pady=(0, 5), padx=25, anchor="w")
                self.extractBrarchivesHint.pack(pady=(0, 15), padx=45, anchor="w")
            if not self.allSettingsBtn.winfo_ismapped():
                self.allSettingsBtn.pack(pady=10, padx=20, fill="x")
        else:
            self.zipBtn.pack_forget()
            self.extractBrarchivesCheck.pack_forget()
            self.extractBrarchivesHint.pack_forget()
            self.allSettingsBtn.pack_forget()


class PatchProgressFrame(ctk.CTkFrame):
    def __init__(self, parent, title: str, onBack: callable):
        super().__init__(parent, fg_color="transparent")
        self.onBack = onBack
        self.is_patching = False  # Track if patching is in progress
        self.is_advanced = False  # Track if advanced mode is active
        self.actionBtnVisible = False
        self.secondaryBtnVisible = False

        container = ctk.CTkFrame(
            self, fg_color=COLOR_SURFACE, corner_radius=15)
        container.pack(expand=True, fill="both", padx=40, pady=10)

        self.titleLabel = ctk.CTkLabel(container, text=title, font=(
            FONT_FAMILY, 20, "bold"), text_color=COLOR_TEXT)

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
        self.logArea = ctk.CTkTextbox(self.logFrame, height=100, font=(
            "Consolas", 10), text_color="#dddddd", fg_color="#111111")
        self.logArea.pack(fill="both", expand=True)
        self.logArea.configure(state='disabled')

        self.logBtnRow = ctk.CTkFrame(self.logFrame, fg_color="transparent")
        self.logBtnRow.pack(fill="x", pady=(5, 0))
        ctk.CTkButton(self.logBtnRow, text="📋 Copy Log", width=100,
                      command=self.copyLog, **get_button_style("secondary")).pack(side="right")

        self.statusLabel = ctk.CTkLabel(
            container, text="Ready...", text_color=COLOR_ACCENT_1, font=(FONT_FAMILY, 14, "bold"))

        # Progress Row (Progress Bar + Percentage Label)
        self.progressRow = ctk.CTkFrame(container, fg_color="transparent")
        self.progressBar = ctk.CTkProgressBar(
            self.progressRow, orientation="horizontal", progress_color=COLOR_ACCENT_1, height=12)
        self.progressBar.set(0)
        self.progressBar.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.percentageLabel = ctk.CTkLabel(
            self.progressRow, text="0%", font=(FONT_FAMILY, 12, "bold"), text_color=COLOR_ACCENT_1, width=40)
        self.percentageLabel.pack(side="right")

        # Step checklist container
        self.stepFrame = ctk.CTkFrame(container, fg_color="transparent")
        self.steps = [
            {"text": "Preparing source pack...", "indicator": None, "text_lbl": None},
            {"text": "Normalizing & zipping textures...", "indicator": None, "text_lbl": None},
            {"text": "Applying RTX community patch...", "indicator": None, "text_lbl": None},
            {"text": "Installing texture pack...", "indicator": None, "text_lbl": None}
        ]
        for step in self.steps:
            row = ctk.CTkFrame(self.stepFrame, fg_color="transparent")
            row.pack(fill="x", pady=3)
            
            indicator = ctk.CTkLabel(row, text="○", font=(FONT_FAMILY, 14, "bold"), text_color="#666666", width=25)
            indicator.pack(side="left")
            
            text_lbl = ctk.CTkLabel(row, text=step["text"], font=(FONT_FAMILY, 12), text_color="#888888")
            text_lbl.pack(side="left", padx=5)
            
            step["indicator"] = indicator
            step["text_lbl"] = text_lbl

        # Simple status hint shown in non-advanced mode only
        self.simpleHintLabel = ctk.CTkLabel(
            container, text="", text_color="#888888",
            font=(FONT_FAMILY, 11), wraplength=500)

        # Cleanup checkbox kept here for advanced mode
        self.cleanOldVersionsVar = ctk.BooleanVar(value=True)
        self.cleanCheck = ctk.CTkCheckBox(container, text="Clean old versions before patching",
                                          variable=self.cleanOldVersionsVar, fg_color=COLOR_ACCENT_1, hover_color=COLOR_ACCENT_1)

        self.btnFrame = ctk.CTkFrame(container, fg_color="transparent")

        # Action button hidden in simple mode (auto-patch), shown in advanced mode
        self.actionBtn = ctk.CTkButton(
            self.btnFrame, text="Start", width=120, state="disabled", **get_button_style("filled-primary"))

        self.secondaryBtn = ctk.CTkButton(
            self.btnFrame, text="Open Folder", width=120, **get_button_style("secondary"))

        self.backBtn = ctk.CTkButton(self.btnFrame, text="Back", width=120, command=self._handleBack,
                                     **get_button_style("danger"))

        self._repack()

    def _repack(self):
        # 1. Unpack everything
        self.titleLabel.pack_forget()
        self.advFrame.pack_forget()
        self.statusLabel.pack_forget()
        self.progressRow.pack_forget()
        self.stepFrame.pack_forget()
        self.simpleHintLabel.pack_forget()
        self.cleanCheck.pack_forget()
        self.logFrame.pack_forget()
        self.btnFrame.pack_forget()

        # Unpack inner buttons
        self.actionBtn.pack_forget()
        self.secondaryBtn.pack_forget()
        self.backBtn.pack_forget()

        # 2. Pack title
        self.titleLabel.pack(side="top", pady=(10, 5))

        # 3. Pack buttons inside btnFrame
        if self.actionBtnVisible:
            self.actionBtn.pack(side="left", padx=5)
        if self.secondaryBtnVisible:
            self.secondaryBtn.pack(side="left", padx=5)
        self.backBtn.pack(side="left", padx=5)

        # 4. Pack buttons at the bottom (guaranteed visibility)
        self.btnFrame.pack(side="bottom", pady=(0, 10))

        # 5. Pack content top-down
        is_mp = getattr(self, "patch_mode", None) == "marketplace"
        
        if self.is_advanced and not is_mp:
            self.advFrame.pack(side="top", pady=(0, 10), fill="x")
            self.statusLabel.pack(side="top", pady=(5, 5))
            self.progressRow.pack(side="top", pady=(0, 10), fill="x", padx=40)
            self.cleanCheck.pack(side="top", pady=(0, 10))
            self.logFrame.pack(side="top", pady=(5, 5), fill="both", expand=True, padx=20)
        elif self.is_advanced and is_mp:
            self.statusLabel.pack(side="top", pady=(20, 5))
            self.progressRow.pack(side="top", pady=(0, 10), fill="x", padx=40)
            self.stepFrame.pack(side="top", pady=(10, 15), fill="x", padx=60)
            self.logFrame.pack(side="top", pady=(5, 5), fill="both", expand=True, padx=20)
            self.simpleHintLabel.pack(side="top", pady=(0, 5))
        else:
            self.statusLabel.pack(side="top", pady=(20, 5))
            self.progressRow.pack(side="top", pady=(0, 10), fill="x", padx=40)
            self.stepFrame.pack(side="top", pady=(10, 15), fill="x", padx=60)
            self.simpleHintLabel.pack(side="top", pady=(0, 5))

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
        self.secondaryBtnVisible = True
        self._repack()

    def hideSecondaryAction(self):
        self.secondaryBtnVisible = False
        self._repack()

    def showActionBtn(self):
        self.actionBtnVisible = True
        self._repack()

    def hideActionBtn(self):
        self.actionBtnVisible = False
        self._repack()

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
        self.is_advanced = enabled
        self.actionBtnVisible = enabled
        if enabled:
            self.onModeChanged()
        self._repack()

    def appendLog(self, text: str):
        self.logArea.configure(state='normal')
        self.logArea.insert(tk.END, text + "\n")
        self.logArea.see(tk.END)
        self.logArea.configure(state='disabled')
        
    def clearLog(self):
        self.logArea.configure(state='normal')
        self.logArea.delete("1.0", tk.END)
        self.logArea.configure(state='disabled')

    def getLogText(self) -> str:
        """Returns the full log text."""
        return self.logArea.get("1.0", tk.END)

    def copyLog(self):
        text = self.logArea.get("1.0", tk.END)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()

    def setSimpleHint(self, text: str):
        """Update the simple-mode hint label shown below the progress bar."""
        self.simpleHintLabel.configure(text=text)

    def setStatus(self, text: str):
        self.statusLabel.configure(text=text)

    def setProgress(self, value: float, mode: str = 'determinate'):
        # value 0-100 -> 0.0-1.0
        if mode == 'indeterminate':
            self.progressBar.configure(mode='indeterminate')
            self.progressBar.start()
            self.percentageLabel.configure(text="...")
        else:
            self.progressBar.configure(mode='determinate')
            self.progressBar.stop()
            self.progressBar.set(value / 100.0)
            self.percentageLabel.configure(text=f"{int(value)}%")

    def resetSteps(self):
        """Reset all steps to pending state."""
        for i in range(len(self.steps)):
            self.updateStep(i, 'pending')

    def updateStep(self, step_idx: int, state: str):
        """Update the visual state of a specific progress step."""
        if step_idx < 0 or step_idx >= len(self.steps):
            return
            
        step = self.steps[step_idx]
        indicator = step["indicator"]
        text_lbl = step["text_lbl"]
        
        if state == 'pending':
            indicator.configure(text="○", text_color="#666666")
            text_lbl.configure(text_color="#888888", font=(FONT_FAMILY, 12))
        elif state == 'active':
            indicator.configure(text="▶", text_color=COLOR_ACCENT_1)
            text_lbl.configure(text_color=COLOR_TEXT, font=(FONT_FAMILY, 12, "bold"))
        elif state == 'completed':
            indicator.configure(text="✓", text_color="#00FF00")
            text_lbl.configure(text_color="#888888", font=(FONT_FAMILY, 12))
        elif state == 'failed':
            indicator.configure(text="✗", text_color="#FF0000")
            text_lbl.configure(text_color="#FF5555", font=(FONT_FAMILY, 12, "bold"))

    def setActionCommand(self, command: callable, text: str = "Patch"):
        self.actionBtn.configure(command=command, text=text)

    def setActionState(self, state: str):
        self.actionBtn.configure(state=state)

    def setVersions(self, versions: list):
        self.versionCombo.configure(values=versions)
        if versions:
            self.versionCombo.set(versions[0])
