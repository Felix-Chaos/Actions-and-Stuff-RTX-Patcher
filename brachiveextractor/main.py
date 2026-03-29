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
        ctk.CTkLabel(self.tab_extract, text="Input Pack / Folder:").grid(
            row=0, column=0, padx=10, pady=10, sticky="w"
        )
        self.input_entry = ctk.CTkEntry(self.tab_extract)
        self.input_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(self.tab_extract, text="Browse", command=self._browse_input).grid(
            row=0, column=2, padx=10, pady=10
        )

        # Output folder
        ctk.CTkLabel(self.tab_extract, text="Output Folder:").grid(
            row=1, column=0, padx=10, pady=10, sticky="w"
        )
        self.output_entry = ctk.CTkEntry(self.tab_extract)
        self.output_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(
            self.tab_extract, text="Browse", command=self._browse_output
        ).grid(row=1, column=2, padx=10, pady=10)

        # Custom Name
        ctk.CTkLabel(self.tab_extract, text="Custom Job Name:").grid(
            row=2, column=0, padx=10, pady=10, sticky="w"
        )
        self.name_entry = ctk.CTkEntry(
            self.tab_extract, placeholder_text="e.g. MyModdedPack"
        )
        self.name_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")

        # Pack Version
        ctk.CTkLabel(self.tab_extract, text="Pack Version:").grid(
            row=3, column=0, padx=10, pady=10, sticky="w"
        )
        self.version_combo = ctk.CTkComboBox(self.tab_extract, values=["Unknown"])
        self.version_combo.grid(row=3, column=1, padx=10, pady=10, sticky="ew")

        self.save_version_var = ctk.BooleanVar(value=False)
        self.save_version_checkbox = ctk.CTkCheckBox(
            self.tab_extract, text="Save as new version", variable=self.save_version_var
        )
        self.save_version_checkbox.grid(row=3, column=2, padx=10, pady=10)

        # Extract Button
        self.extract_btn = ctk.CTkButton(
            self.tab_extract, text="Extract Brarchives", command=self._start_extract
        )
        self.extract_btn.grid(row=4, column=0, columnspan=3, pady=20)

        self._refresh_versions()

    def _refresh_versions(self):
        self.core.versions_db = self.core._load_versions()
        versions = list(self.core.versions_db.keys())
        if not versions:
            versions = ["Unknown"]
        else:
            versions.insert(0, "Unknown")

        current = self.version_combo.get()
        self.version_combo.configure(values=versions)
        if current not in versions and current == "Unknown":
            self.version_combo.set(versions[0])

    def _setup_repack_tab(self):
        self.tab_repack.grid_columnconfigure(0, weight=1)
        self.tab_repack.grid_rowconfigure(1, weight=1)

        # Arbitrary folder repack section
        top_frame = ctk.CTkFrame(self.tab_repack)
        top_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(top_frame, text="Repack an arbitrary extracted folder:").pack(
            side="left", padx=10, pady=10
        )

        self.repack_folder_entry = ctk.CTkEntry(
            top_frame, width=250, placeholder_text="Select folder..."
        )
        self.repack_folder_entry.pack(side="left", padx=10, pady=10)

        ctk.CTkButton(
            top_frame, text="Browse", width=80, command=self._browse_repack_folder
        ).pack(side="left", padx=5, pady=10)
        self.repack_folder_btn = ctk.CTkButton(
            top_frame,
            text="Reverse To .mcpack",
            width=120,
            command=self._start_repack_folder,
        )
        self.repack_folder_btn.pack(side="left", padx=5, pady=10)

        # DB Jobs list
        self.jobs_frame = ctk.CTkScrollableFrame(self.tab_repack)
        self.jobs_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        self.refresh_btn = ctk.CTkButton(
            self.tab_repack, text="Refresh DB Jobs", command=self._refresh_jobs
        )
        self.refresh_btn.grid(row=2, column=0, pady=10)

        self._refresh_jobs()

    def _refresh_jobs(self):
        for widget in self.jobs_frame.winfo_children():
            widget.destroy()

        jobs = self.core.get_jobs()
        if not jobs:
            ctk.CTkLabel(self.jobs_frame, text="No extraction jobs found in DB.").pack(
                pady=20
            )
            return

        for job_id, data in jobs.items():
            frame = ctk.CTkFrame(self.jobs_frame)
            frame.pack(fill="x", pady=5, padx=5)

            info = f"Name: {data['custom_name']} | Date: {data['timestamp'][:19]}\nOriginal: {data['original_input']}"
            ctk.CTkLabel(frame, text=info, justify="left").pack(
                side="left", padx=10, pady=10
            )

            btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
            btn_frame.pack(side="right", padx=10)

            ctk.CTkButton(
                btn_frame,
                text="Reverse To .mcpack",
                width=120,
                command=lambda j=job_id: self._start_repack(j),
            ).pack(side="left", padx=5)
            ctk.CTkButton(
                btn_frame,
                text="Delete Job",
                fg_color="red",
                hover_color="darkred",
                width=80,
                command=lambda j=job_id: self._delete_job(j),
            ).pack(side="left", padx=5)

    def _browse_input(self):
        path = filedialog.askopenfilename(
            title="Select .zip or .mcpack",
            filetypes=[("Pack Files", "*.zip *.mcpack"), ("All Files", "*.*")],
        )
        if not path:
            path = filedialog.askdirectory(title="Select Extracted Pack Folder")

        if path:
            self.input_entry.delete(0, "end")
            self.input_entry.insert(0, path)
            self._scan_version(path)

    def view_after(self, delay, callback):
        self.after(delay, callback)

    def _scan_version(self, path):
        self.log(f"Scanning '{os.path.basename(path)}' for version matching...")

        def worker():
            ver = self.core.detect_version(path, logger_callback=self.log)
            if ver:
                self.log(f"Detected version: {ver}")
                self.view_after(0, lambda: self.version_combo.set(ver))
            else:
                self.log("Version not found in DB. Set to Unknown.")
                self.view_after(0, lambda: self.version_combo.set("Unknown"))

        threading.Thread(target=worker, daemon=True).start()

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

        clean_name = re.sub(r'[\\/:*?"<>|]', "_", name)
        workspace = os.path.join(out_path, clean_name)
        if os.path.exists(workspace):
            if not messagebox.askyesno(
                "Confirm Overwrite",
                f"The folder '{clean_name}' already exists.\n\nExtracting will overwrite and DELETE any existing modifications inside this folder. Continue?",
            ):
                return

        self.extract_btn.configure(state="disabled")
        self.log(f"--- Starting Extraction: {name} ---")

        def worker():
            try:
                save_new = self.save_version_var.get()
                version_name = self.version_combo.get().strip()
                stats_before = None

                if save_new:
                    if version_name == "Unknown" or not version_name:
                        self.log(
                            "Cannot save stats as 'Unknown' version. Skipping stats save."
                        )
                        save_new = False
                    else:
                        f, d = self.core.get_folder_stats(in_path)
                        stats_before = {"files": f, "dirs": d}
                        self.log(f"Recorded before-stats: Files={f}, Dirs={d}")

                # Run extraction
                success = self.core.process_pack(
                    in_path, out_path, name, logger_callback=self.log
                )

                if success and save_new and stats_before:
                    workspace = os.path.join(out_path, name)
                    f, d = self.core.get_folder_stats(workspace)
                    stats_after = {"files": f, "dirs": d}
                    self.log(f"Recorded after-stats: Files={f}, Dirs={d}")

                    saved_key = self.core.save_new_version(
                        version_name, stats_before, stats_after
                    )
                    self.log(f"Saved version configuration as '{saved_key}'.")
                    self.view_after(0, self._refresh_versions)

            except Exception as e:
                self.log(f"Critical Error: {e}")
            finally:
                self.view_after(0, lambda: self.extract_btn.configure(state="normal"))
                self.view_after(0, self._refresh_jobs)

        threading.Thread(target=worker, daemon=True).start()

    def _browse_repack_folder(self):
        path = filedialog.askdirectory(title="Select Extracted Pack Folder")
        if path:
            self.repack_folder_entry.delete(0, "end")
            self.repack_folder_entry.insert(0, path)

    def _start_repack_folder(self):
        path = self.repack_folder_entry.get().strip()
        if not path or not os.path.exists(path):
            messagebox.showerror("Error", "Please select a valid folder.")
            return

        self.repack_folder_btn.configure(state="disabled")
        self.log(f"--- Starting Arbitrary Repack for '{os.path.basename(path)}' ---")

        def worker():
            try:
                success = self.core.reverse_folder(
                    path, os.path.basename(path), logger_callback=self.log
                )
                if success:
                    self.log("Successfully repacked to .mcpack!")
                else:
                    self.log("Repacking failed or was aborted.")
            except Exception as e:
                self.log(f"Critical Error: {e}")
            finally:
                self.view_after(
                    0, lambda: self.repack_folder_btn.configure(state="normal")
                )

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
        if messagebox.askyesno(
            "Confirm", "Delete this job and its temporary workspace?"
        ):
            self.core.delete_job(job_id)
            self._refresh_jobs()
            self.log(f"Deleted job {job_id}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
