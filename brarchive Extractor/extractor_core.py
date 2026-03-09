import os
import shutil
import zipfile
import json
from datetime import datetime
from pathlib import Path
from brarchive_format import serialize, deserialize, BrArchiveError

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db.json")
TEMP_WORKSPACE = "temp_workspace"

class ExtractorCore:
    def __init__(self):
        self.db = self._load_db()

    def _load_db(self):
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_db(self):
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.db, f, indent=4)

    def process_pack(self, input_path: str, output_folder: str, custom_name: str, logger_callback=print):
        """
        Extracts brarchives from a .zip/.mcpack or folder.
        Saves extracted files to output_folder.
        Records job to db.json.
        """
        input_path = os.path.abspath(input_path)
        output_folder = os.path.abspath(output_folder)
        
        # 1. Normalize mapping to a workspace
        workspace = os.path.join(output_folder, custom_name)
        if os.path.exists(workspace):
            shutil.rmtree(workspace)
        os.makedirs(workspace, exist_ok=True)
        
        logger_callback("Normalizing input...")
        if os.path.isfile(input_path) and input_path.endswith(('.zip', '.mcpack')):
            try:
                with zipfile.ZipFile(input_path, 'r') as zip_ref:
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
        
        mapping = {} # relative path of brarchive -> list of extracted files
        
        for root, dirs, files in os.walk(workspace):
            for file in files:
                if file.endswith('.brarchive'):
                    brarchives_found += 1
                    brarchive_path = os.path.join(root, file)
                    rel_path = os.path.relpath(brarchive_path, workspace)
                    
                    logger_callback(f"Found brarchive: {rel_path}")
                    
                    try:
                        with open(brarchive_path, 'rb') as f:
                            data = f.read()
                        
                        entry_map = deserialize(data)
                        mapping[rel_path] = []
                        
                        # Create an extraction folder for this specific brarchive's contents IN PLACE
                        base_name = os.path.splitext(os.path.basename(brarchive_path))[0]
                        extract_dir = os.path.join(os.path.dirname(brarchive_path), base_name)
                        if os.path.isfile(extract_dir):
                            extract_dir += "_extracted"
                            
                        os.makedirs(extract_dir, exist_ok=True)
                        
                        for entry_name, content in entry_map.items():
                            extracted_files += 1
                            out_file = os.path.join(extract_dir, entry_name)
                            os.makedirs(os.path.dirname(out_file), exist_ok=True)
                            
                            with open(out_file, 'wb') as out_f:
                                out_f.write(content)
                                
                            mapping[rel_path].append({
                                'entry_name': entry_name,
                                'extracted_path': os.path.relpath(out_file, workspace) # save path relative to workspace!
                            })
                            
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
            'custom_name': custom_name,
            'timestamp': datetime.now().isoformat(),
            'original_input': input_path,
            'mapping': mapping,
            'workspace': workspace # We keep the workspace to repack easily
        }
        self._save_db()
        
        logger_callback(f"Successfully processed {brarchives_found} brarchives.")
        logger_callback(f"Extracted {extracted_files} total files to: {os.path.join(output_folder, custom_name)}")
        return True

    def reverse_process(self, job_id: str, logger_callback=print):
        """
        Reads modified files and repacks them into the workspace's .brarchives.
        Then zips the workspace into a new .mcpack.
        """
        if job_id not in self.db:
            logger_callback("Job not found in database.")
            return False
            
        job = self.db[job_id]
        workspace = job['workspace']
        mapping = job['mapping']
        
        if not os.path.exists(workspace):
            logger_callback("Workspace no longer exists. Cannot reverse.")
            return False
            
        logger_callback("Re-packing modified files into .brarchives...")
        
        success_count = 0
        for rel_path, entries in mapping.items():
            brarchive_path = os.path.join(workspace, rel_path)
            
            # Read all files
            data_dict = {}
            extract_dirs = set()
            for entry in entries:
                entry_name = entry['entry_name']
                # reconstructed path from relative workspace path
                extracted_path = os.path.join(workspace, entry['extracted_path'])
                extract_dirs.add(os.path.dirname(extracted_path))
                
                if os.path.exists(extracted_path):
                    with open(extracted_path, 'rb') as f:
                        data_dict[entry_name] = f.read()
                else:
                    logger_callback(f"Warning: File missing {extracted_path}, skipping packing this file.")
            
            if data_dict:
                try:
                    new_bytes = serialize(data_dict)
                    with open(brarchive_path, 'wb') as f:
                        f.write(new_bytes)
                    success_count += 1
                    
                    # Cleanup loose files and the .bak
                    bak_path = brarchive_path + ".bak"
                    if os.path.exists(bak_path):
                        os.remove(bak_path)
                        
                    for entry in entries:
                        extracted_path = os.path.join(workspace, entry['extracted_path'])
                        if os.path.exists(extracted_path):
                            os.remove(extracted_path)
                            
                    # Remove the populated extracted directories if empty
                    for d in extract_dirs:
                        if os.path.exists(d) and not os.listdir(d):
                            os.rmdir(d)
                            
                except Exception as e:
                    logger_callback(f"Failed to serialize {rel_path}: {e}")
                    
        # Zip workspace to .mcpack
        out_mcpack = os.path.join(os.path.dirname(workspace), f"{job['custom_name']}_modified.mcpack")
        logger_callback(f"Zipping workspace to {out_mcpack}...")
        
        try:
            with zipfile.ZipFile(out_mcpack, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(workspace):
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
            workspace = self.db[job_id].get('workspace')
            if workspace and os.path.exists(workspace):
                try:
                    shutil.rmtree(workspace)
                except:
                    pass
            del self.db[job_id]
            self._save_db()
