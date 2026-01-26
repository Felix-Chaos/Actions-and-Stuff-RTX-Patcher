
# repro_sorting.py
# This script reproduces the version sorting issue.
# Current behavior: "v1.9" > "v1.10" (String sort)
# Desired behavior: "v1.10" > "v1.9" (SemVer sort)

def parse_version(v_str):
    """
    Parses 'vX.Y' or 'vX.Y.Z' into a tuple of integers.
    Removes 'v' prefix.
    """
    try:
        clean = v_str.lstrip('v')
        return tuple(map(int, clean.split('.')))
    except:
        return (0,)

versions = ["v1.6", "v1.9", "v1.10", "v1.8"]

print("--- Current Sorting (String) ---")
sorted_str = sorted(versions, reverse=True)
print(f"Sorted: {sorted_str}")
# Expectation: v1.9 comes before v1.10 because '9' > '1'

if sorted_str.index("v1.9") < sorted_str.index("v1.10"):
    print("FAIL: v1.9 is ranked higher than v1.10")
else:
    print("PASS: v1.10 is ranked higher than v1.9")

print("\n--- Proposed Sorting (SemVer) ---")
sorted_sem = sorted(versions, key=parse_version, reverse=True)
print(f"Sorted: {sorted_sem}")

if sorted_sem.index("v1.10") < sorted_sem.index("v1.9"):
    print("PASS: v1.10 is ranked higher than v1.9")
else:
    print("FAIL: v1.9 is ranked higher than v1.10")
