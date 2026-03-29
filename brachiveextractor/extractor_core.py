# pylint: disable=missing-docstring, line-too-long, broad-exception-caught, too-many-locals, too-many-branches, too-many-statements, bare-except, too-few-public-methods, too-many-instance-attributes
import os
import shutil
import zipfile
import json
import sys
import re
from datetime import datetime
from brarchive_format import serialize, deserialize, BrArchiveError

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_FILE = os.path.join(BASE_DIR, "db.json")
VERSIONS_FILE = os.path.join(BASE_DIR, "versions.json")
TEMP_WORKSPACE = "temp_workspace"


class ExtractorCore:
    def __init__(self):
        self.db = self._load_db()
        self.versions_db = self._load_versions()

    def _load_db(self):
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_db(self):
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(self.db, f, indent=4)

    def _load_versions(self):
        if os.path.exists(VERSIONS_FILE):
            try:
                with open(VERSIONS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_versions(self):
        with open(VERSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.versions_db, f, indent=4)

    def get_folder_stats(self, folder: str):
        if os.path.isfile(folder) and folder.endswith((".zip", ".mcpack")):
            return self.get_stats_from_zip(folder)
        file_count, folder_count = 0, 0
        try:
            for _, dirs, files in os.walk(folder):
                folder_count += len(dirs)
                file_count += len(files)
        except Exception:
            pass
        return file_count, folder_count

    def get_stats_from_zip(self, zip_path: str):
        file_count, folder_count = 0, 0
        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                # To accurately count folders that might not have explicit entries
                dirs_set = set()
                for info in z.infolist():
                    if info.is_dir():
                        dirs_set.add(info.filename.rstrip("/"))
                    else:
                        file_count += 1
                        # Infer directories from file path
                        parts = info.filename.split("/")[:-1]
                        current = ""
                        for part in parts:
                            if current:
                                current += "/" + part
                            else:
                                current = part
                            dirs_set.add(current)
                folder_count = len(dirs_set)
        except Exception:
            pass
        return file_count, folder_count

    def detect_version(self, folder_path: str, logger_callback=print):
        # Calculate stats for the folder (this is the "before" state)
        f_count, d_count = self.get_folder_stats(folder_path)
        logger_callback(f"Scanning pack... Files: {f_count}, Dirs: {d_count}")

        # We need to sort versions descending (v1.9 before v1.8, etc.)
        def parse_ver_local(v_str):
            try:
                clean = v_str.lstrip("v")
                return tuple(map(int, clean.split(".")))
            except Exception:
                return (0,)

        sorted_ver_keys = sorted(
            list(self.versions_db.keys()), key=parse_ver_local, reverse=True
        )

        for ver_key in sorted_ver_keys:
            ver_data = self.versions_db[ver_key]
            stats_before = ver_data.get("stats_before", {})
            if stats_before:
                if f_count == stats_before.get("files") and d_count == stats_before.get(
                    "dirs"
                ):
                    return ver_key

        return None

    def save_new_version(self, version_key: str, stats_before: dict, stats_after: dict):
        # Use subversion logic if the version string already exists but stats differ
        final_key = version_key

        if final_key in self.versions_db:
            existing = self.versions_db[final_key]
            e_before = existing.get("stats_before", {})

            # If stats match, we just overwrite/update
            if e_before.get("files") == stats_before.get("files") and e_before.get(
                "dirs"
            ) == stats_before.get("dirs"):
                final_key = version_key
            else:
                # Stats differ, need a subversion
                sub_index = 1
                while f"{version_key}_sub{sub_index}" in self.versions_db:
                    sub_index += 1
                final_key = f"{version_key}_sub{sub_index}"

        self.versions_db[final_key] = {
            "stats_before": stats_before,
            "stats_after": stats_after,
            "timestamp": datetime.now().isoformat(),
        }
        self._save_versions()
        return final_key

    def process_pack(
        self,
        input_path: str,
        output_folder: str,
        custom_name: str,
        logger_callback=print,
    ):
        """
        Extracts brarchives from a .zip/.mcpack or folder.
        Saves extracted files to output_folder.
        Records job to db.json.
        """
        input_path = os.path.abspath(input_path)
        output_folder = os.path.abspath(output_folder)

        if not os.path.exists(input_path):
            logger_callback("Input path does not exist.")
            return False

        # Clean custom_name to prevent OS path errors/injection
        custom_name = re.sub(r'[\\/:*?"<>|]', "_", custom_name)

        # 1. Normalize mapping to a workspace
        workspace = os.path.join(output_folder, custom_name)
        if os.path.exists(workspace):
            shutil.rmtree(workspace)
        os.makedirs(workspace, exist_ok=True)

        logger_callback("Normalizing input...")
        if os.path.isfile(input_path) and input_path.endswith((".zip", ".mcpack")):
            try:
                with zipfile.ZipFile(input_path, "r") as zip_ref:
                    zip_ref.extractall(workspace)
            except Exception as e:
                logger_callback(f"Failed to extract zip: {e}")
                shutil.rmtree(workspace)
                return False
        elif os.path.isdir(input_path):
            shutil.copytree(input_path, workspace, dirs_exist_ok=True)
        else:
            logger_callback("Unsupported input format.")
            return False

        # 2. Find and extract brarchives
        brarchives_found = 0
        extracted_files = 0

        mapping = {}  # relative path of brarchive -> list of extracted files

        for root, _, files in os.walk(workspace):
            for file in files:
                if file.endswith(".brarchive"):
                    brarchives_found += 1
                    brarchive_path = os.path.join(root, file)
                    rel_path = os.path.relpath(brarchive_path, workspace)

                    logger_callback(f"Found brarchive: {rel_path}")

                    try:
                        with open(brarchive_path, "rb") as f:
                            data = f.read()

                        entry_map = deserialize(data)
                        mapping[rel_path] = []

                        # Create an extraction folder for this specific brarchive's contents IN PLACE
                        base_name = os.path.splitext(os.path.basename(brarchive_path))[
                            0
                        ]
                        extract_dir = os.path.join(
                            os.path.dirname(brarchive_path), base_name
                        )
                        if os.path.isfile(extract_dir):
                            extract_dir += "_extracted"

                        os.makedirs(extract_dir, exist_ok=True)

                        for entry_name, content in entry_map.items():
                            extracted_files += 1
                            out_file = os.path.join(extract_dir, entry_name)
                            os.makedirs(os.path.dirname(out_file), exist_ok=True)

                            with open(out_file, "wb") as out_f:
                                out_f.write(content)

                            mapping[rel_path].append(
                                {
                                    "entry_name": entry_name,
                                    "extracted_path": os.path.relpath(
                                        out_file, workspace
                                    ),  # save path relative to workspace!
                                }
                            )

                        # Rename original brarchive to .bak so Minecraft can load the loose files directly if tested inside game
                        bak_path = brarchive_path + ".bak"
                        if os.path.exists(bak_path):
                            os.remove(bak_path)
                        os.rename(brarchive_path, bak_path)

                    except BrArchiveError as e:
                        logger_callback(f"Error parsing {rel_path}: {e}")
                    except Exception as e:
                        logger_callback(f"Unexpected error: {e}")

        if brarchives_found == 0:
            logger_callback("No .brarchive files found in the pack.")
            shutil.rmtree(workspace)
            return False

        # 3. Save job to DB
        job_id = str(datetime.now().timestamp())
        self.db[job_id] = {
            "custom_name": custom_name,
            "timestamp": datetime.now().isoformat(),
            "original_input": input_path,
            "mapping": mapping,
            "workspace": workspace,  # We keep the workspace to repack easily
        }
        self._save_db()

        logger_callback(f"Successfully processed {brarchives_found} brarchives.")
        logger_callback(
            f"Extracted {extracted_files} total files to: {os.path.join(output_folder, custom_name)}"
        )
        return True

    def reverse_folder(self, workspace: str, custom_name: str, logger_callback=print):
        """
        Scans an arbitrary folder for loosely extracted brarchive contents + .bak files,
        rebuilds the mapping, and repacks them into an .mcpack.
        """
        if not os.path.exists(workspace):
            logger_callback("Folder does not exist.")
            return False

        logger_callback(
            f"Scanning '{custom_name}' for .bak files to rebuild DB mapping..."
        )
        mapping = {}

        for root, _, files in os.walk(workspace):
            for file in files:
                if file.endswith(".brarchive.bak"):
                    bak_path = os.path.join(root, file)
                    brarchive_path = bak_path[:-4]  # remove .bak
                    rel_path = os.path.relpath(brarchive_path, workspace)

                    try:
                        with open(bak_path, "rb") as f:
                            data = f.read()
                        entry_map = deserialize(data)

                        mapping[rel_path] = []
                        base_name = os.path.splitext(os.path.basename(brarchive_path))[
                            0
                        ]
                        extract_dir = os.path.join(
                            os.path.dirname(brarchive_path), base_name
                        )
                        if os.path.isfile(extract_dir):
                            extract_dir += "_extracted"

                        for entry_name in entry_map.keys():
                            out_file = os.path.join(extract_dir, entry_name)
                            mapping[rel_path].append(
                                {
                                    "entry_name": entry_name,
                                    "extracted_path": os.path.relpath(
                                        out_file, workspace
                                    ).replace("\\", "/"),  # normalize
                                }
                            )
                    except Exception as e:
                        logger_callback(f"Failed to read backup {file}: {e}")

        if not mapping:
            logger_callback(
                "No .brarchive.bak files found in the folder. Action aborted."
            )
            return False

        logger_callback(f"Successfully rebuilt mapping for {len(mapping)} brarchives.")

        job = {"workspace": workspace, "mapping": mapping, "custom_name": custom_name}
        return self._reverse_core(job, logger_callback)

    def reverse_process(self, job_id: str, logger_callback=print):
        """
        Reads modified files from a saved DB job and repacks them into the workspace's .brarchives.
        Then zips the workspace into a new .mcpack.
        """
        if job_id not in self.db:
            logger_callback("Job not found in database.")
            return False

        job = self.db[job_id]
        if not os.path.exists(job["workspace"]):
            logger_callback("Workspace no longer exists. Cannot reverse.")
            return False

        return self._reverse_core(job, logger_callback)

    def _reverse_core(self, job: dict, logger_callback=print):
        workspace = job["workspace"]
        mapping = job["mapping"]

        total_brarchives = len(mapping)
        logger_callback(f"Re-packing {total_brarchives} .brarchives...")

        success_count = 0
        failed_count = 0
        warning_count = 0
        dirs_to_clean = set()

        for idx, (rel_path, entries) in enumerate(mapping.items(), 1):
            brarchive_path = os.path.join(workspace, rel_path)

            if idx % 10 == 0 or idx == total_brarchives:
                logger_callback(f"Processing progress: {idx}/{total_brarchives}...")

            # Read all files
            data_dict = {}
            extract_dirs = set()
            known_extracted_paths = set()

            # 1. First process known entries from mapping to preserve exact entry_names
            for entry in entries:
                entry_name = entry["entry_name"]
                # reconstructed path from relative workspace path
                extracted_path = os.path.join(workspace, entry["extracted_path"])
                extract_dirs.add(os.path.dirname(extracted_path))
                known_extracted_paths.add(os.path.abspath(extracted_path))

                if os.path.exists(extracted_path):
                    with open(extracted_path, "rb") as f:
                        data_dict[entry_name] = f.read()
                else:
                    warning_count += 1
                    logger_callback(
                        f"Warning: File missing {extracted_path}, skipping packing this file."
                    )

            # 2. Re-derive the base extract_dir to find NEW files
            base_name = os.path.splitext(os.path.basename(brarchive_path))[0]
            extract_dir = os.path.join(os.path.dirname(brarchive_path), base_name)
            if os.path.isfile(extract_dir):
                extract_dir += "_extracted"

            if os.path.isdir(extract_dir):
                extract_dirs.add(extract_dir)
                for root, _, files in os.walk(extract_dir):
                    for file in files:
                        file_path = os.path.abspath(os.path.join(root, file))
                        if file_path not in known_extracted_paths:
                            # It's a new file!
                            new_entry_name = os.path.relpath(
                                file_path, os.path.abspath(extract_dir)
                            )
                            new_entry_name = new_entry_name.replace(os.sep, "/")
                            with open(file_path, "rb") as f:
                                data_dict[new_entry_name] = f.read()

            if data_dict:
                try:
                    new_bytes = serialize(data_dict)
                    with open(brarchive_path, "wb") as f:
                        f.write(new_bytes)
                    success_count += 1

                    # Cleanup loose files and the .bak
                    bak_path = brarchive_path + ".bak"
                    if os.path.exists(bak_path):
                        os.remove(bak_path)

                    if os.path.isdir(extract_dir):
                        dirs_to_clean.add(extract_dir)

                except Exception as e:
                    failed_count += 1
                    logger_callback(f"Failed to serialize {rel_path}: {e}")
            else:
                failed_count += 1
                logger_callback(f"Failed to serialize {rel_path}: No files found.")

        # --- Dashboard ---
        logger_callback("")
        logger_callback("--- Repacking Dashboard ---")
        logger_callback(f"Total Brarchives: {total_brarchives}")
        logger_callback(f"Successfully Packed: {success_count}")
        logger_callback(f"Failed to Pack:    {failed_count}")
        logger_callback(f"Missing File Warnings: {warning_count}")
        logger_callback("---------------------------")
        logger_callback("")

        # Clean up directories after all brarchives have been serialized
        for d in sorted(dirs_to_clean, reverse=True):
            if os.path.isdir(d):
                try:
                    shutil.rmtree(d)
                except Exception as e:
                    logger_callback(f"Failed to clean up {d}: {e}")

        # Zip workspace to .mcpack
        out_mcpack = os.path.join(
            os.path.dirname(workspace), f"{job['custom_name']}_modified.mcpack"
        )
        logger_callback(f"Zipping workspace to {out_mcpack}...")

        try:
            with zipfile.ZipFile(out_mcpack, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(workspace):
                    for file in files:
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, workspace)
                        zipf.write(file_path, rel_path)
            logger_callback(f"Successfully repacked {success_count} brarchives.")
            logger_callback(f"Output saved to: {out_mcpack}")
            return True
        except Exception as e:
            logger_callback(f"Failed to create mcpack: {e}")
            return False

    def get_jobs(self):
        return self.db

    def delete_job(self, job_id: str):
        if job_id in self.db:
            workspace = self.db[job_id].get("workspace")
            if workspace and os.path.exists(workspace):
                try:
                    shutil.rmtree(workspace)
                except:  # noqa: E722
                    pass
            del self.db[job_id]
            self._save_db()
