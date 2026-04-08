"""
Fix: levels calculation uses round() which gives 6m -> 2 levels.
Should use int() (floor) so 6m -> 1 level.

6.0 / 3.5 = 1.71 -> round = 2 (WRONG, looks like 2-storey)
6.0 / 3.5 = 1.71 -> int   = 1 (CORRECT, single storey with high ceiling)
"""

VALIDATOR_PATH = r'REDACTED_PATH\builddavis-world\src\builddavis\height_validator.py'

OLD = 'corrected_levels = max(1, round(corrected / METRES_PER_LEVEL))'
NEW = 'corrected_levels = max(1, int(corrected / METRES_PER_LEVEL))'

def patch():
    with open(VALIDATOR_PATH, 'r', encoding='utf-8') as f:
        src = f.read()

    count = src.count(OLD)
    if count == 0:
        print("ERROR: Could not find the round() line to fix")
        return

    src = src.replace(OLD, NEW)

    with open(VALIDATOR_PATH, 'w', encoding='utf-8') as f:
        f.write(src)

    print(f"PATCHED OK - fixed {count} occurrence(s)")
    print("  6.0m / 3.5 = 1.71 -> was round()=2, now int()=1")
    print("  7.5m / 3.5 = 2.14 -> was round()=2, now int()=2")
    print("  10.5m / 3.5 = 3.0 -> unchanged at 3")

if __name__ == '__main__':
    patch()
