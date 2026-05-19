import os
import hashlib
import zipfile
import tempfile
import shutil
import struct
import tkinter as tk
import concurrent.futures
import threading
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
import ttkbootstrap as ttk
from ttkbootstrap.constants import *


def md5_bytes(data):
    return hashlib.md5(data).hexdigest()


def md5_file_obj(file_obj):
    h = hashlib.md5()
    while chunk := file_obj.read(8192):
        h.update(chunk)
    return h.hexdigest()


def get_pack_files(
    pack_path,
    num_threads=None,
    set_total_callback=None,
    progress_callback=None,
    status_callback=None,
    keep_temp=False,
):
    files_data = {}
    processed = 0

    # We will do all our work inside this temporary directory
    temp_root = tempfile.mkdtemp(prefix="as_rtx_compare_")

    try:
        # STEP 1: Copy or Extract into temp_root
        if status_callback:
            status_callback("Copying/Extracting pack to temporary folder...")
        if os.path.isfile(pack_path) and pack_path.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(pack_path, "r") as z:
                    z.extractall(temp_root)
            except Exception as e:
                raise Exception(f"Failed to extract ZIP {pack_path}:\n{e}")
        elif os.path.isdir(pack_path):
            try:
                # Copy tree into temp_root
                # Since temp_root is already created, we copy contents into it
                for item in os.listdir(pack_path):
                    s = os.path.join(pack_path, item)
                    d = os.path.join(temp_root, item)
                    if os.path.isdir(s):
                        shutil.copytree(s, d, dirs_exist_ok=True)
                    else:
                        shutil.copy2(s, d)
            except Exception as e:
                raise Exception(f"Failed to copy directory {pack_path}:\n{e}")
        else:
            raise Exception(f"Invalid path: {pack_path}")

        # STEP 2: Find and extract all .brarchive files concurrently
        if status_callback:
            status_callback("Extracting .brarchive files...")
        brarchives = []
        for root, dirs, files in os.walk(temp_root):
            for file in files:
                if file.lower().endswith(".brarchive"):
                    brarchives.append(os.path.join(root, file))

        def extract_brarchive(br_path):
            # We must extract into a subfolder named after the brarchive to mirror VFS behavior
            # and prevent sibling brarchives from overwriting each other's files.
            # IMPORTANT: We add _extracted to the folder name because creating a folder
            # with the exact same name as the existing .brarchive file will throw WinError 183!
            base_name = os.path.basename(br_path)
            extract_dir = os.path.join(
                os.path.dirname(br_path), f"{base_name}_extracted"
            )
            try:
                with open(br_path, "rb") as f:
                    magic = f.read(8)
                    # Minecraft brarchive magic byte check
                    if magic != b"\x7d\x27\x25\xb1\xa0\x52\x70\x26":
                        print(f"[Warning] Not a valid brarchive magic bytes: {br_path}")
                        return False

                    num_entries, version = struct.unpack("<II", f.read(8))

                    entries = []
                    for _ in range(num_entries):
                        entry_data = f.read(256)
                        if len(entry_data) < 256:
                            break
                        name_len = entry_data[0]
                        name = entry_data[1 : 1 + name_len].decode(
                            "utf-8", errors="ignore"
                        )
                        offset, length = struct.unpack("<II", entry_data[248:256])
                        entries.append((name, offset, length))

                    for name, offset, length in entries:
                        f.seek(offset)
                        data = f.read(length)
                        out_path = os.path.join(extract_dir, name)
                        os.makedirs(os.path.dirname(out_path), exist_ok=True)
                        with open(out_path, "wb") as out_f:
                            out_f.write(data)

                # Remove the original .brarchive so we don't hash it as a binary blob
                os.remove(br_path)
                return True
            except Exception as e:
                print(f"[Error] Failed to extract {br_path}: {e}")
                return False

        if brarchives:
            success_count = 0
            fail_count = 0
            if status_callback:
                status_callback(f"Extracting {len(brarchives)} .brarchive files...")
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=num_threads
            ) as executor:
                futures = [executor.submit(extract_brarchive, br) for br in brarchives]
                for future in concurrent.futures.as_completed(futures):
                    if future.result():
                        success_count += 1
                    else:
                        fail_count += 1
            if status_callback:
                status_callback(
                    f"Extracted {success_count} brarchives ({fail_count} failed)"
                )

        # STEP 3: Hash all the files
        if status_callback:
            status_callback("Calculating file hashes...")
        tasks = []
        for root, dirs, files in os.walk(temp_root):
            for file in files:
                # Exclude .brarchive files entirely from the final hash calculation.
                # If they were successfully extracted earlier, we hash their contents.
                # If extraction failed, we just ignore the archive container rather than hashing it.
                if file.lower().endswith(".brarchive"):
                    continue

                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, temp_root).replace("\\", "/")
                tasks.append((full_path, rel_path))

        if set_total_callback:
            set_total_callback(len(tasks))

        def _process_fs_file(full_path, rel_path):
            try:
                with open(full_path, "rb") as f:
                    return rel_path, md5_file_obj(f)
            except Exception:
                return rel_path, None

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(_process_fs_file, fp, rp) for fp, rp in tasks]
            for future in concurrent.futures.as_completed(futures):
                rel_path, hash_val = future.result()
                if hash_val is not None:
                    files_data[rel_path] = hash_val
                processed += 1
                if progress_callback:
                    progress_callback(processed)

    finally:
        if not keep_temp:
            # STEP 4: Burn the evidence
            try:
                shutil.rmtree(temp_root, ignore_errors=True)
            except Exception:
                pass

    return _normalize_pack_root(files_data), temp_root


def _normalize_pack_root(files_data):
    """
    Finds the root of the texture pack by looking for manifest.json.
    If manifest.json is inside a subfolder (like A&SforRTX/manifest.json),
    we strip that subfolder prefix so we can fairly compare it against
    another pack that might just be extracted without the root folder.
    """
    manifest_paths = [
        p for p in files_data.keys() if p.lower().endswith("manifest.json")
    ]

    if not manifest_paths:
        return files_data

    manifest_paths.sort(key=len)
    root_manifest = manifest_paths[0]

    root_prefix = ""
    if "/" in root_manifest:
        root_prefix = root_manifest.rsplit("/", 1)[0] + "/"

    if root_prefix:
        normalized_data = {}
        for path, file_hash in files_data.items():
            if path.startswith(root_prefix):
                new_path = path[len(root_prefix) :]
                if new_path:  # ignore the directory itself
                    normalized_data[new_path] = file_hash
            else:
                # Keep files outside root prefix just in case
                normalized_data[path] = file_hash
        return normalized_data

    return files_data


class DiffCheckerApp(ttk.Window):
    def __init__(self):
        super().__init__(themename="darkly", title="A&S RTX Diff Checker")
        self.geometry("850x650")

        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.abspath(
                os.path.join(base_dir, "..", "assets", "resources", "icon.ico")
            )
            self.iconbitmap(icon_path)
        except:
            pass

        self.create_widgets()

    def create_widgets(self):
        # Pack 1
        pack1_frame = ttk.Frame(self)
        pack1_frame.pack(fill=X, padx=10, pady=10)

        ttk.Label(pack1_frame, text="Base Texture Pack:", width=20).pack(side=LEFT)
        self.pack1_var = ttk.StringVar()
        ttk.Entry(pack1_frame, textvariable=self.pack1_var).pack(
            side=LEFT, fill=X, expand=True, padx=5
        )
        ttk.Button(
            pack1_frame,
            text="Folder",
            bootstyle=SECONDARY,
            command=lambda: self.browse_folder(self.pack1_var),
        ).pack(side=LEFT, padx=2)
        ttk.Button(
            pack1_frame,
            text="ZIP",
            bootstyle=SECONDARY,
            command=lambda: self.browse_zip(self.pack1_var),
        ).pack(side=LEFT, padx=2)

        # Pack 2
        pack2_frame = ttk.Frame(self)
        pack2_frame.pack(fill=X, padx=10, pady=5)

        ttk.Label(pack2_frame, text="Target Texture Pack:", width=20).pack(side=LEFT)
        self.pack2_var = ttk.StringVar()
        ttk.Entry(pack2_frame, textvariable=self.pack2_var).pack(
            side=LEFT, fill=X, expand=True, padx=5
        )
        ttk.Button(
            pack2_frame,
            text="Folder",
            bootstyle=SECONDARY,
            command=lambda: self.browse_folder(self.pack2_var),
        ).pack(side=LEFT, padx=2)
        ttk.Button(
            pack2_frame,
            text="ZIP",
            bootstyle=SECONDARY,
            command=lambda: self.browse_zip(self.pack2_var),
        ).pack(side=LEFT, padx=2)

        # Controls
        ctrl_frame = ttk.Frame(self)
        ctrl_frame.pack(fill=X, padx=10, pady=10)

        ttk.Label(ctrl_frame, text="Threads:").pack(side=LEFT, padx=(0, 5))
        self.thread_var = ttk.StringVar(value="Auto")
        # CPU core count options; fallback to 4 if OS call fails
        thread_opts = ["Auto"] + [
            str(i) for i in range(1, (os.cpu_count() or 4) * 2 + 1)
        ]
        self.thread_combo = ttk.Combobox(
            ctrl_frame,
            textvariable=self.thread_var,
            values=thread_opts,
            width=5,
            state="readonly",
        )
        self.thread_combo.pack(side=LEFT, padx=(0, 15))

        self.keep_temp_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            ctrl_frame,
            text="Keep Temp Folders",
            variable=self.keep_temp_var,
            bootstyle="round-toggle",
        ).pack(side=LEFT, padx=(0, 15))

        ttk.Button(
            ctrl_frame,
            text="Compare Packs",
            bootstyle=SUCCESS,
            command=self.compare_packs,
        ).pack(side=LEFT)
        ttk.Button(
            ctrl_frame, text="Copy Report", bootstyle=INFO, command=self.copy_logs
        ).pack(side=LEFT, padx=5)
        self.status_var = ttk.StringVar(value="Ready.")
        ttk.Label(ctrl_frame, textvariable=self.status_var).pack(side=LEFT, padx=10)

        # Progress Bar and Debug Info Frame
        progress_frame = ttk.Frame(self)
        progress_frame.pack(fill=X, padx=10, pady=(0, 5))

        self.progress_var = ttk.IntVar(value=0)
        self.progress_bar = ttk.Progressbar(
            progress_frame, variable=self.progress_var, maximum=100
        )
        self.progress_bar.pack(fill=X, expand=True, pady=(0, 5))

        # Debug Info Labels
        debug_frame = ttk.Frame(progress_frame)
        debug_frame.pack(fill=X)

        self.debug_threads_var = ttk.StringVar(value="Threads: -")
        self.debug_elapsed_var = ttk.StringVar(value="Elapsed: 0.0s")
        self.debug_avg_var = ttk.StringVar(value="Avg/file: -")
        self.debug_eta_var = ttk.StringVar(value="ETA: -")

        ttk.Label(
            debug_frame, textvariable=self.debug_threads_var, font=("Consolas", 9)
        ).pack(side=LEFT, padx=(0, 15))
        ttk.Label(
            debug_frame, textvariable=self.debug_elapsed_var, font=("Consolas", 9)
        ).pack(side=LEFT, padx=(0, 15))
        ttk.Label(
            debug_frame, textvariable=self.debug_avg_var, font=("Consolas", 9)
        ).pack(side=LEFT, padx=(0, 15))
        ttk.Label(
            debug_frame, textvariable=self.debug_eta_var, font=("Consolas", 9)
        ).pack(side=LEFT)

        # Output
        self.output_text = ScrolledText(
            self,
            width=100,
            height=22,
            bg="#1e1e1e",
            fg="#d4d4d4",
            font=("Consolas", 10),
        )
        self.output_text.pack(fill=BOTH, expand=True, padx=10, pady=5)

    def browse_folder(self, string_var):
        path = filedialog.askdirectory(title="Select Texture Pack Folder")
        if path:
            string_var.set(path)

    def browse_zip(self, string_var):
        path = filedialog.askopenfilename(
            title="Select Texture Pack ZIP",
            filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")],
        )
        if path:
            string_var.set(path)

    def copy_logs(self):
        self.clipboard_clear()
        logs = self.output_text.get(1.0, END)
        self.clipboard_append(logs)
        self.update()

    def compare_packs(self):
        p1 = self.pack1_var.get().strip()
        p2 = self.pack2_var.get().strip()

        if not p1 or not p2:
            messagebox.showerror("Error", "Please select both Texture Packs.")
            return

        if not os.path.exists(p1) or not os.path.exists(p2):
            messagebox.showerror(
                "Error",
                "One or both selected paths do not exist. Please check the paths.",
            )
            return

        self.output_text.delete(1.0, END)
        self.status_var.set("Reading files and calculating hashes...")
        self.update()

        # Parse threads
        threads_str = self.thread_var.get()
        num_threads = None if threads_str == "Auto" else int(threads_str)
        keep_temp = self.keep_temp_var.get()

        # Run in a background thread to prevent GUI freezing
        threading.Thread(
            target=self._run_comparison,
            args=(p1, p2, num_threads, keep_temp),
            daemon=True,
        ).start()

    def _run_comparison(self, p1, p2, num_threads, keep_temp):
        import time

        actual_threads = (
            num_threads if num_threads is not None else (os.cpu_count() or 4) + 4
        )
        self.after(0, lambda: self.debug_threads_var.set(f"Threads: {actual_threads}"))

        def process_pack(p_num, path):
            self.after(0, lambda: self.status_var.set(f"Reading Pack {p_num}..."))
            self.after(0, lambda: self.progress_var.set(0))

            start_time = time.time()
            last_update_time = [0]
            pack_total = [0]

            def total_cb(total):
                pack_total[0] = total
                self.after(0, lambda v=total: self.progress_bar.configure(maximum=v))

            def progress_cb(processed_val):
                curr_time = time.time()
                # Update UI max 15 times a second to prevent freezing from event flood
                if curr_time - last_update_time[0] > 0.06:
                    elapsed = curr_time - start_time
                    avg_time = elapsed / processed_val if processed_val > 0 else 0

                    remaining_files = pack_total[0] - processed_val
                    eta = remaining_files * avg_time

                    self.after(0, lambda v=processed_val: self.progress_var.set(v))
                    self.after(
                        0,
                        lambda e=elapsed: self.debug_elapsed_var.set(
                            f"Elapsed: {e:.1f}s"
                        ),
                    )
                    self.after(
                        0,
                        lambda a=avg_time: self.debug_avg_var.set(
                            f"Avg/file: {a * 1000:.1f}ms"
                        ),
                    )
                    self.after(
                        0, lambda e_t=eta: self.debug_eta_var.set(f"ETA: {e_t:.1f}s")
                    )

                    last_update_time[0] = curr_time

            def status_cb(msg):
                self.after(0, lambda m=msg: self.status_var.set(f"Pack {p_num}: {m}"))

            res, temp_path = get_pack_files(
                path,
                num_threads,
                set_total_callback=total_cb,
                progress_callback=progress_cb,
                status_callback=status_cb,
                keep_temp=keep_temp,
            )

            # Final stats update for this pack
            end_time = time.time()
            total_elapsed = end_time - start_time
            avg_final = total_elapsed / pack_total[0] if pack_total[0] > 0 else 0

            self.after(0, lambda v=pack_total[0]: self.progress_var.set(v))
            self.after(
                0,
                lambda e=total_elapsed: self.debug_elapsed_var.set(
                    f"Elapsed: {e:.1f}s"
                ),
            )
            self.after(
                0,
                lambda a=avg_final: self.debug_avg_var.set(
                    f"Avg/file: {a * 1000:.1f}ms"
                ),
            )
            self.after(0, lambda: self.debug_eta_var.set("ETA: 0.0s"))

            return res, temp_path

        try:
            dict1, t1 = process_pack(1, p1)
            dict2, t2 = process_pack(2, p2)
        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda: messagebox.showerror("Error reading packs", err_msg))
            self.after(0, lambda: self.status_var.set("Error during comparison."))
            return

        self.after(0, lambda: self.status_var.set("Comparing..."))

        set1 = set(dict1.keys())
        set2 = set(dict2.keys())

        added = sorted(list(set2 - set1))
        removed = sorted(list(set1 - set2))
        common = set1 & set2

        modified = []
        identical = []
        for f in common:
            if dict1[f] != dict2[f]:
                modified.append(f)
            else:
                identical.append(f)
        modified.sort()

        lines = []
        lines.append(f"--- Texture Pack Comparison Results ---\n")
        lines.append(f"Pack 1: {p1}\n")
        lines.append(f"Pack 2: {p2}\n\n")

        if keep_temp:
            lines.append(f"--- Temporary Workspaces (KEPT) ---\n")
            lines.append(f"Pack 1 Temp: {t1}\n")
            lines.append(f"Pack 2 Temp: {t2}\n\n")

        lines.append(f"Identical files : {len(identical)}\n")
        lines.append(f"Modified files  : {len(modified)}\n")
        lines.append(f"Added files     : {len(added)}\n")
        lines.append(f"Removed files   : {len(removed)}\n\n")

        if modified:
            lines.append("=== MODIFIED FILES ===\n")
            for f in modified:
                lines.append(f" ~ {f}\n")
            lines.append("\n")

        if added:
            lines.append("=== ADDED FILES (Present in Pack 2, Missing in Pack 1) ===\n")
            for f in added:
                lines.append(f" + {f}\n")
            lines.append("\n")

        if removed:
            lines.append(
                "=== REMOVED FILES (Present in Pack 1, Missing in Pack 2) ===\n"
            )
            for f in removed:
                lines.append(f" - {f}\n")
            lines.append("\n")

        out_str = "".join(lines)
        self.after(0, lambda: self._update_results(out_str))

    def _update_results(self, text):
        self.output_text.insert(END, text)
        self.status_var.set("Comparison complete.")


if __name__ == "__main__":
    app = DiffCheckerApp()
    app.mainloop()
