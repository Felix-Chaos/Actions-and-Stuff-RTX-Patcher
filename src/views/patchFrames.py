import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog
from PIL import Image, ImageTk
from ..utils.helpers import resourcePath
import os
from tkinter.scrolledtext import ScrolledText

class MainMenuFrame(ttk.Frame):
    def __init__(self, parent, callbacks: dict):
        super().__init__(parent)
        self.callbacks = callbacks 

        # Main Layout: Top (Logo) -> Middle (Action Cards) -> Bottom (Buttons)
        
        # 1. Header (Logo)
        headerFrame = ttk.Frame(self, padding=20)
        headerFrame.pack(fill="x")
        
        try:
            # Try loading logo from assets/resources/icon.ico
            logoPath = resourcePath("assets/resources/icon.ico")
            if os.path.exists(logoPath):
                pilImg = Image.open(logoPath)
                # Resize to something reasonable (e.g. 150x150)
                pilImg = pilImg.resize((120, 120), Image.Resampling.LANCZOS)
                self.logoImg = ImageTk.PhotoImage(pilImg)
                logoLabel = ttk.Label(headerFrame, image=self.logoImg)
                logoLabel.pack()
        except Exception as e:
            print(f"Failed to load logo: {e}")
            
        ttk.Label(headerFrame, text="A&S RTX Patcher", font=("Segoe UI", 24, "bold"), bootstyle="info").pack(pady=10)

        # 2. Content Area (Grid)
        contentFrame = ttk.Frame(self)
        contentFrame.pack(expand=True, fill="both", padx=40, pady=20)
        
        # Grid Configuration
        contentFrame.columnconfigure(0, weight=1)
        contentFrame.columnconfigure(1, weight=1)
        
        # --- Primary Actions (Left Column) ---
        primaryFrame = ttk.Labelframe(contentFrame, text="Patching", padding=15, bootstyle="primary")
        primaryFrame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        ttk.Button(primaryFrame, text="⚡ Patch from Marketplace", command=self.callbacks.get("marketplace"), 
                   bootstyle="info-outline", width=25).pack(pady=10, fill="x")
        
        self.zipBtn = ttk.Button(primaryFrame, text="📦 Advanced / Zip Patcher", command=self.callbacks.get("zip"), 
                   bootstyle="primary-outline", width=25)
        # self.zipBtn.pack(pady=10, fill="x") # Hidden by default
        
        # --- Maintenance Actions (Right Column) ---
        maintFrame = ttk.Labelframe(contentFrame, text="Maintenance", padding=15, bootstyle="secondary")
        maintFrame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        ttk.Button(maintFrame, text="🧹 Clean Old Versions", command=self.callbacks.get("clean"), 
                   bootstyle="warning-outline", width=25).pack(pady=10, fill="x")

        # 3. Exit Button (Bottom)
        ttk.Button(self, text="Exit Application", command=self.callbacks.get("exit"), 
                   bootstyle="danger-link").pack(pady=20)

    def setAdvancedMode(self, enabled: bool):
        if enabled:
            if not self.zipBtn.winfo_ismapped():
                 self.zipBtn.pack(pady=10, fill="x", after=self.zipBtn.master.winfo_children()[0])
        else:
            self.zipBtn.pack_forget()

class PatchProgressFrame(ttk.Frame):
    def __init__(self, parent, title: str, onBack: callable):
        super().__init__(parent)
        self.onBack = onBack
        
        container = ttk.Frame(self, padding=30)
        container.pack(expand=True)
        
        self.titleLabel = ttk.Label(container, text=title, font=("Segoe UI", 12, "bold"))
        self.titleLabel.pack(pady=(0, 20))

        # --- Advanced: Mode Selection ---
        self.advFrame = ttk.Frame(container)
        
        self.modeVar = tk.StringVar(value="marketplace")
        
        modeRow = ttk.Frame(self.advFrame)
        modeRow.pack(fill="x", pady=(0, 10))
        
        ttk.Label(modeRow, text="Patch Method:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 10))
        
        ttk.Radiobutton(modeRow, text="Marketplace (Auto)", variable=self.modeVar, value="marketplace", 
                        command=self.onModeChanged).pack(side="left", padx=5)
        ttk.Radiobutton(modeRow, text="Zip (Manual)", variable=self.modeVar, value="zip", 
                        command=self.onModeChanged).pack(side="left", padx=5)
        ttk.Radiobutton(modeRow, text="Custom", variable=self.modeVar, value="custom", 
                        command=self.onModeChanged).pack(side="left", padx=5)

        # --- Advanced: Custom Fields ---
        self.customFieldsFrame = ttk.Frame(self.advFrame)
        
        # Source
        ttk.Label(self.customFieldsFrame, text="Source (Folder/Zip):").pack(anchor="w")
        srcRow = ttk.Frame(self.customFieldsFrame)
        srcRow.pack(fill="x", pady=(0, 5))
        self.srcVar = tk.StringVar()
        ttk.Entry(srcRow, textvariable=self.srcVar).pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(srcRow, text="...", width=3, command=lambda: self.browsePath(self.srcVar), bootstyle="secondary-outline").pack(side="left")

        # Target (Output Name)
        ttk.Label(self.customFieldsFrame, text="Output Filename (.mcpack):").pack(anchor="w")
        tgtRow = ttk.Frame(self.customFieldsFrame)
        tgtRow.pack(fill="x", pady=(0, 5))
        self.tgtVar = tk.StringVar()
        ttk.Entry(tgtRow, textvariable=self.tgtVar).pack(side="left", fill="x", expand=True)

        # Patch File
        ttk.Label(self.customFieldsFrame, text="Patch File (.vcdiff):").pack(anchor="w")
        patchRow = ttk.Frame(self.customFieldsFrame)
        patchRow.pack(fill="x", pady=(0, 5))
        self.patchVar = tk.StringVar()
        ttk.Entry(patchRow, textvariable=self.patchVar).pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(patchRow, text="...", width=3, command=lambda: self.browsePatchFile(self.patchVar), bootstyle="secondary-outline").pack(side="left")

        
        # Advanced: Log Area (Hidden by default)
        self.logFrame = ttk.Frame(container)
        ttk.Label(self.logFrame, text="Process Log:", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.logArea = ScrolledText(self.logFrame, height=8, width=60, state='disabled', font=("Consolas", 8))
        self.logArea.pack(fill="both", expand=True)

        self.statusLabel = ttk.Label(container, text="Ready...")
        self.statusLabel.pack(pady=(0, 10))
        
        self.progressBar = ttk.Progressbar(container, mode='determinate', length=300, bootstyle=INFO)
        self.progressBar.pack(pady=(10, 0))
        
        self.btnFrame = ttk.Frame(container)
        self.btnFrame.pack(pady=(20, 0))
        
        self.actionBtn = ttk.Button(self.btnFrame, text="Start", width=20, state="disabled", bootstyle=SUCCESS)
        self.actionBtn.pack(side="left", padx=5)
        
        ttk.Button(self.btnFrame, text="Back", width=20, command=self.onBack, bootstyle=(DANGER, OUTLINE)).pack(side="left", padx=5)

    def browsePatchFile(self, var):
        f = filedialog.askopenfilename(filetypes=[("VCDIFF Patch", "*.vcdiff"), ("All Files", "*.*")])
        if f: var.set(f)

    def browsePath(self, var):
        # Determine if folder or file based on mode? Simplification: Ask for file or directory
        # For now generic "Open"
        f = filedialog.askopenfilename()
        if not f:
             f = filedialog.askdirectory()
        if f: var.set(f)

    def onModeChanged(self):
        mode = self.modeVar.get()
        if mode == "custom":
            self.customFieldsFrame.pack(fill="x", pady=10)
        else:
            self.customFieldsFrame.pack_forget()

    def setAdvancedMode(self, enabled: bool):
        if enabled:
            self.advFrame.pack(after=self.titleLabel, pady=(0, 20), fill="x")
            self.logFrame.pack(before=self.btnFrame, pady=(10, 20), fill="both", expand=True)
            self.onModeChanged() # Refresh custom fields visibility
        else:
            self.advFrame.pack_forget()
            self.logFrame.pack_forget()

    def appendLog(self, text: str):
        self.logArea.config(state='normal')
        self.logArea.insert(tk.END, text + "\n")
        self.logArea.see(tk.END)
        self.logArea.config(state='disabled')

    def setStatus(self, text: str):
        self.statusLabel.config(text=text)

    def setProgress(self, value: float, mode: str = 'determinate'):
        self.progressBar.config(mode=mode, value=value)
        if mode == 'indeterminate':
            self.progressBar.start()
        else:
            self.progressBar.stop()

    def setActionCommand(self, command: callable, text: str = "Patch"):
        self.actionBtn.config(command=command, text=text)

    def setActionState(self, state: str):
        self.actionBtn.config(state=state)
