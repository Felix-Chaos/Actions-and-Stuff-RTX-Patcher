# pylint: disable=missing-docstring, line-too-long, broad-exception-caught, too-many-locals, too-many-branches, too-many-statements, bare-except, too-few-public-methods, too-many-instance-attributes
import threading
import os
import re
from tkinter import filedialog, messagebox

import customtkinter as ctk
from extractor_core import ExtractorCore

# Use the same theme as the main tool if possible
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class RedirectText:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, string):
        self.text_widget.configure(state="normal")
        self.text_widget.insert("end", string)
        self.text_widget.see("end")
        self.text_widget.configure(state="disabled")

    def flush(self):
        pass

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("A&S Brarchive Extractor")
        self.geometry("800x600")

        self.core = ExtractorCore()

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        self.tab_extract = self.tabview.add("Extract")
        self.tab_repack = self.tabview.add("Repack Jobs")

        self._setup_extract_tab()
        self._setup_repack_tab()

        # Log Box shared
        self.log_textbox = ctk.CTkTextbox(self, height=150)
        self.log_textbox.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.log_textbox.configure(state="disabled")

        self.logger = RedirectText(self.log_textbox)

    def log(self, text):
        self.logger.write(text + "\n")

    def _setup_extract_tab(self):
        self.tab_extract.grid_columnconfigure(1, weight=1)

        # Input pack
        ctk.CTkLabel(self.tab_extract, text="Input Pack / Folder:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.input_entry = ctk.CTkEntry(self.tab_extract)
        self.input_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(self.tab_extract, text="Browse", command=self._browse_input).grid(row=0, column=2, padx=10, pady=10)

        # Output folder
        ctk.CTkLabel(self.tab_extract, text="Output Folder:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.output_entry = ctk.CTkEntry(self.tab_extract)
        self.output_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(self.tab_extract, text="Browse", command=self._browse_output).grid(row=1, column=2, padx=10, pady=10)

        # Custom Name
        ctk.CTkLabel(self.tab_extract, text="Custom Job Name:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.name_entry = ctk.CTkEntry(self.tab_extract, placeholder_text="e.g. MyModdedPack")
        self.name_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")

        # Extract Button
        self.extract_btn = ctk.CTkButton(self.tab_extract, text="Extract Brarchives", command=self._start_extract)
        self.extract_btn.grid(row=3, column=0, columnspan=3, pady=20)

    def _setup_repack_tab(self):
        self.tab_repack.grid_columnconfigure(0, weight=1)
        self.tab_repack.grid_rowconfigure(0, weight=1)

        self.jobs_frame = ctk.CTkScrollableFrame(self.tab_repack)
        self.jobs_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        self.refresh_btn = ctk.CTkButton(self.tab_repack, text="Refresh DB", command=self._refresh_jobs)
        self.refresh_btn.grid(row=1, column=0, pady=10)

        self._refresh_jobs()

    def _refresh_jobs(self):
        for widget in self.jobs_frame.winfo_children():
            widget.destroy()

        jobs = self.core.get_jobs()
        if not jobs:
            ctk.CTkLabel(self.jobs_frame, text="No extraction jobs found in DB.").pack(pady=20)
            return

        for job_id, data in jobs.items():
            frame = ctk.CTkFrame(self.jobs_frame)
            frame.pack(fill="x", pady=5, padx=5)

            info = f"Name: {data['custom_name']} | Date: {data['timestamp'][:19]}\nOriginal: {data['original_input']}"
            ctk.CTkLabel(frame, text=info, justify="left").pack(side="left", padx=10, pady=10)

            btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
            btn_frame.pack(side="right", padx=10)

            ctk.CTkButton(btn_frame, text="Reverse To .mcpack", width=120,
                          command=lambda j=job_id: self._start_repack(j)).pack(side="left", padx=5)
            ctk.CTkButton(btn_frame, text="Delete Job", fg_color="red", hover_color="darkred", width=80,
                          command=lambda j=job_id: self._delete_job(j)).pack(side="left", padx=5)

    def _browse_input(self):
        path = filedialog.askopenfilename(title="Select .zip or .mcpack", filetypes=[("Pack Files", "*.zip *.mcpack"), ("All Files", "*.*")])
        if path:
            self.input_entry.delete(0, "end")
            self.input_entry.insert(0, path)

    def _browse_output(self):
        path = filedialog.askdirectory(title="Select Output Folder")
        if path:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, path)

    def _start_extract(self):
        in_path = self.input_entry.get().strip()
        out_path = self.output_entry.get().strip()
        name = self.name_entry.get().strip()

        if not in_path or not out_path or not name:
            messagebox.showerror("Error", "Please fill all fields.")
            return

        clean_name = re.sub(r'[\\/:*?"<>|]', '_', name)
        workspace = os.path.join(out_path, clean_name)
        if os.path.exists(workspace):
            if not messagebox.askyesno("Confirm Overwrite", f"The folder '{clean_name}' already exists.\n\nExtracting will overwrite and DELETE any existing modifications inside this folder. Continue?"):
                return

        self.extract_btn.configure(state="disabled")
        self.log(f"--- Starting Extraction: {name} ---")

        def worker():
            try:
                self.core.process_pack(in_path, out_path, name, logger_callback=self.log)
            except Exception as e:
                self.log(f"Critical Error: {e}")
            finally:
                self.extract_btn.configure(state="normal")
                self._refresh_jobs()

        threading.Thread(target=worker, daemon=True).start()

    def _start_repack(self, job_id):
        self.log(f"--- Starting Repack for Job {job_id} ---")

        def worker():
            try:
                self.core.reverse_process(job_id, logger_callback=self.log)
            except Exception as e:
                self.log(f"Critical Error: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _delete_job(self, job_id):
        if messagebox.askyesno("Confirm", "Delete this job and its temporary workspace?"):
            self.core.delete_job(job_id)
            self._refresh_jobs()
            self.log(f"Deleted job {job_id}")

if __name__ == "__main__":
    app = App()
    app.mainloop()
