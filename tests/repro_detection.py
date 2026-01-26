
# repro_detection.py
# Simulates the logic inside _marketplaceSearchWorker to reproduce the priority issue.

class MockConfig:
    def __init__(self):
        self.config = {
            "patchVersions": {
                "v1.9": [{"stats": {"files": 100, "dirs": 10}}],
                "v1.6": [{"stats": {"files": 200, "dirs": 20}}]
            }
        }

def simulate_detection(mock_lang_version, mock_stats_version_key):
    print(f"--- Simulation: Lang='{mock_lang_version}', StatsKey='{mock_stats_version_key}' ---")
    
    target_versions = {
        "v1.9": [{"stats": {"files": 100, "dirs": 10}}],
        "v1.6": [{"stats": {"files": 200, "dirs": 20}}]
    }
    
    detected_version_key = None
    detection_method = 'unknown'
    
    # Mocking the decision logic from patchController.py
    
    # Case B: Stats matched
    if mock_stats_version_key:
        detected_version_key = mock_stats_version_key
        detection_method = 'stats'
        print(f"  -> Identified Version: {detected_version_key} (via Stats)")
        
    # Case C: Lang file
    elif mock_lang_version:
        potential_key = f"v{mock_lang_version}"
        if potential_key in target_versions:
            detected_version_key = potential_key
            detection_method = 'lang_string'
            print(f"  -> Identified Version: {detected_version_key} (via Language File)")

    print(f"Result: Detected {detected_version_key} via {detection_method}")
    return detected_version_key

# Scenario: Stats match 1.6 (collision), but Lang says 1.9
# This reproduces the user's issue where 1.6 is detected despite 1.9 being installed.
result = simulate_detection(mock_lang_version="1.9", mock_stats_version_key="v1.6")

if result == "v1.6":
    print("FAIL: Prioritized Stats (1.6) over Lang (1.9)")
elif result == "v1.9":
    print("PASS: Prioritized Lang (1.9) over Stats")
else:
    print(f"FAIL: Unexpected result {result}")
