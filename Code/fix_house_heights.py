"""
Fix house heights so Arnis renders 1 window row instead of 2.

Arnis draws window rows based on absolute block height, not building:levels.
At 6-7 blocks (6-7m) it fits 2 rows. At 4-5 blocks (4-5m) it fits 1 row.
Davis ranch houses are 4-5m to the eave. The current thresholds allow 6-7.5m
which Arnis renders as 2-storey.

New thresholds:
  house 250m2+ -> 5.0m (was 6.0m) — large ranch, single storey
  house 150m2+ -> 5.5m (was 7.5m) — medium house, single storey  
  house 80m2+  -> 7.0m (was 9.0m) — small footprint, could be 2 storey
  yes   250m2+ -> 5.0m (was 6.0m)
  yes   150m2+ -> 5.5m (was 7.5m)
"""

VALIDATOR_PATH = r'REDACTED_PATH\builddavis-world\src\builddavis\height_validator.py'

OLD_HOUSE = '''    "house": [
        (250,   6.0),    # large ranch house — single storey, Davis typical
        (150,   7.5),    # medium house — could be 2 storey but uncommon in Davis
        (80,    9.0),    # smaller house — could be 2 storey narrow
        (0,    10.0),    # very small footprint — could be tall narrow
    ],
    "residential": [
        (250,   6.0),
        (150,   7.5),
        (80,    9.0),
        (0,    10.0),
    ],'''

NEW_HOUSE = '''    "house": [
        (250,   5.0),    # large ranch — single storey, 4-5m to eave
        (150,   5.5),    # medium house — single storey Davis typical
        (80,    7.0),    # smaller house — could be genuine 2 storey
        (0,     9.0),    # very small footprint — tall narrow house possible
    ],
    "residential": [
        (250,   5.0),
        (150,   5.5),
        (80,    7.0),
        (0,     9.0),
    ],'''

OLD_YES = '''    "yes": [
        (250,   6.0),    # large untyped building = probably ranch house
        (150,   7.5),    # medium = could be 2 storey
        (80,    8.0),
        (0,     9.0),
    ],'''

NEW_YES = '''    "yes": [
        (250,   5.0),    # large untyped = probably ranch house
        (150,   5.5),    # medium = probably single storey in Davis
        (80,    7.0),    # smaller = could be 2 storey
        (0,     9.0),
    ],'''


def patch():
    with open(VALIDATOR_PATH, 'r', encoding='utf-8') as f:
        src = f.read()

    changes = 0

    if OLD_HOUSE in src:
        src = src.replace(OLD_HOUSE, NEW_HOUSE)
        changes += 1
        print("House thresholds lowered:")
        print("  250m2+ : 6.0m -> 5.0m")
        print("  150m2+ : 7.5m -> 5.5m")
        print("  80m2+  : 9.0m -> 7.0m")
    else:
        print("WARNING: Could not find house thresholds")

    if OLD_YES in src:
        src = src.replace(OLD_YES, NEW_YES)
        changes += 1
        print("'yes' thresholds lowered to match house")
    else:
        print("WARNING: Could not find 'yes' thresholds")

    if changes > 0:
        with open(VALIDATOR_PATH, 'w', encoding='utf-8') as f:
            f.write(src)
        print(f"\nPATCHED OK - {changes} groups updated")
        print("\nAt 5.0m (5 blocks), Arnis can only fit 1 window row")
        print("Genuine 2-storey houses (small footprint) still allowed at 7m")
    else:
        print("\nNo changes made")


if __name__ == '__main__':
    patch()
