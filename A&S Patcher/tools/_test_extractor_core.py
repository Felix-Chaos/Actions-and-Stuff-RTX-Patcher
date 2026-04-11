import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "brachiveextractor")))
from extractor_core import ExtractorCore

def run_test():
    core = ExtractorCore()
    input_pack = r"b:\Download\Tools.and.stuff (1)\output\Actions & Stuff 1.9.1 (resources) - Kopie"
    out_dir = r"b:\Dokumente\GitHub\A-S-Minecraft-RTX-Community-PatcherV2\brachiveextractor\test_output"
    custom_name = "test_pack_191"

    print("--- 1. Getting Before Stats ---")
    fb, db = core.get_folder_stats(input_pack)
    stats_before = {"files": fb, "dirs": db}
    print(stats_before)

    print("\n--- 2. Processing Pack (Extracting) ---")
    success = core.process_pack(input_pack, out_dir, custom_name, logger_callback=print)
    if not success:
        print("Extraction failed!")
        return

    print("\n--- 3. Getting After Stats ---")
    workspace = os.path.join(out_dir, custom_name)
    fa, da = core.get_folder_stats(workspace)
    stats_after = {"files": fa, "dirs": da}
    print(stats_after)

    print("\n--- 4. Saving New Version ---")
    version_key = core.save_new_version("1.9.1", stats_before, stats_after)
    print(f"Saved as {version_key}")

    print("\n--- 5. Detecting Version ---")
    detected = core.detect_version(input_pack, logger_callback=print)
    print(f"Detected version: {detected}")

    print("\n--- 6. Repacking ---")
    # find job_id
    jobs = core.get_jobs()
    job_id = None
    for jid, data in jobs.items():
        if data["custom_name"] == custom_name:
            job_id = jid
            break

    if job_id:
        success = core.reverse_process(job_id, logger_callback=print)
        print(f"Repacking success: {success}")
    else:
        print("Job not found!")

if __name__ == "__main__":
    run_test()
