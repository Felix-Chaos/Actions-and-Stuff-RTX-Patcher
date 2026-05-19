import os
import shutil
import logging
from .brarchive_format import deserialize, BrArchiveError

def extract_brarchives_from_workspace(workspace: str, logger_callback=print):
    """
    Finds all __brarchive folders in the workspace, extracts their .brarchive files
    into their respective loose folders, and deletes the __brarchive folders and
    any placeholder .brarchive files at the root level.
    """
    brarchive_dirs = []
    for root, dirs, _ in os.walk(workspace):
        if "__brarchive" in dirs:
            br_dir = os.path.join(root, "__brarchive")
            brarchive_dirs.append(br_dir)

    if not brarchive_dirs:
        logger_callback("No __brarchive directories found. Nothing to extract.")
        return False

    logger_callback(f"Found {len(brarchive_dirs)} __brarchive directory(s). Extracting...")

    brarchives_found = 0
    extracted_files = 0
    skipped_placeholders = 0

    for brarchive_root in brarchive_dirs:
        pack_context = os.path.dirname(brarchive_root)
        
        for root, _, files in os.walk(brarchive_root):
            for file in sorted(files):
                if not file.endswith(".brarchive"):
                    continue

                brarchives_found += 1
                brarchive_path = os.path.join(root, file)
                rel_to_brarchive_root = os.path.relpath(brarchive_path, brarchive_root)
                target_rel = os.path.splitext(rel_to_brarchive_root)[0]
                extract_dir = os.path.join(pack_context, target_rel)

                try:
                    with open(brarchive_path, "rb") as f:
                        data = f.read()

                    if len(data) <= 16:
                        continue

                    entry_map = deserialize(data)
                    os.makedirs(extract_dir, exist_ok=True)

                    for entry_name, content in entry_map.items():
                        out_file = os.path.join(extract_dir, entry_name)
                        if len(content) == 0:
                            skipped_placeholders += 1
                            continue

                        extracted_files += 1
                        os.makedirs(os.path.dirname(out_file), exist_ok=True)
                        with open(out_file, "wb") as out_f:
                            out_f.write(content)

                except BrArchiveError as e:
                    logger_callback(f"    Error parsing {file}: {e}")
                except Exception as e:
                    logger_callback(f"    Unexpected error in {file}: {e}")

    # Remove all __brarchive directories now that everything is extracted
    for brarchive_root in brarchive_dirs:
        try:
            shutil.rmtree(brarchive_root)
        except Exception as e:
            logger_callback(f"Failed to remove {brarchive_root}: {e}")

    # Remove loose .brarchive pointers
    for root, _, files in os.walk(workspace):
        # We don't want to walk into newly created directories and accidentally delete things?
        # Actually any .brarchive file remaining outside __brarchive is just a pointer file (16 bytes).
        for file in files:
            if file.endswith(".brarchive"):
                try:
                    os.remove(os.path.join(root, file))
                except Exception:
                    pass

    logger_callback(f"Brarchive extraction complete! Extracted {extracted_files} files from {brarchives_found} archives.")
    return True
