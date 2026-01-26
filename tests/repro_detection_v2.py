
# repro_detection_v2.py
# Simulates the NEW logic inside _marketplaceSearchWorker.

def simulate_new_logic(mock_lang_version, mock_stats_version_key):
    print(f"--- Simulation V2: Lang='{mock_lang_version}', StatsKey='{mock_stats_version_key}' ---")
    
    target_versions = {
        "v1.9": [{"stats": {"files": 100, "dirs": 10}}],
        "v1.6": [{"stats": {"files": 200, "dirs": 20}}]
    }
    
    detected_version_key = None
    detection_method = 'unknown'
    
    # NEW LOGIC FLOW:
    
    # 1. Manual check (skipped for this test)
    
    # 2. Lang Check
    if mock_lang_version:
        potential_key = f"v{mock_lang_version}"
        if potential_key in target_versions:
            detected_version_key = potential_key
            detection_method = 'lang_string'
            print(f"  -> Identified Version: {detected_version_key} (via Language File)")
            
            if mock_stats_version_key and mock_stats_version_key != detected_version_key:
                print(f"  [Warning] Stats matched {mock_stats_version_key} but Lang file says {detected_version_key}.")
        else:
             print(f"  -> Version string found '{mock_lang_version}' but no config match.")

    # 3. Stats Check (Only if Lang didn't find anything -- effectively 'elif' in the loop if we restructure, 
    # OR if detected_version_key is still None?
    # Wait, the code uses "elif stats_match_version_key".
    # So if Lang matches, this block is SKIPPED.
    
    elif mock_stats_version_key:
        detected_version_key = mock_stats_version_key
        detection_method = 'stats'
        print(f"  -> Identified Version: {detected_version_key} (via Stats)")

    print(f"Result: Detected {detected_version_key} via {detection_method}")
    return detected_version_key

# Scenario: Stats match 1.6 (collision), but Lang says 1.9
result = simulate_new_logic(mock_lang_version="1.9", mock_stats_version_key="v1.6")

if result == "v1.9":
    print("PASS: Prioritized Lang (1.9) over Stats")
else:
    print(f"FAIL: Result was {result}")
