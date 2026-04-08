"""
Tighten height plausibility thresholds based on Holmes POC3 v2 observations:
- School buildings 100-400m2 still showing as 3 storey (should be 1)
- Houses under 300m2 still too tall at 9m

New thresholds:
  Schools: any footprint over 80m2 caps at 6m (gym exception at very specific size)
  Houses: tighter progression - large ranch capped at 6m, medium at 7.5m
"""

VALIDATOR_PATH = r'REDACTED_PATH\builddavis-world\src\builddavis\height_validator.py'

OLD_SCHOOL = '''    "school": [
        (500,   6.0),    # large school wing is almost certainly single storey
        (200,  10.0),    # medium building could be gym with high ceiling
        (0,    12.0),    # small structure could be 2 storey
    ],'''

NEW_SCHOOL = '''    "school": [
        (400,   6.0),    # large classroom wing — single storey
        (150,   7.5),    # medium building — could be gym (high ceiling, still 1 storey from outside)
        (80,    8.0),    # small classroom or portable — 1 storey, maybe high ceiling
        (0,    10.0),    # very small structure — could be 2-storey stairwell or utility
    ],'''

OLD_HOUSE = '''    "house": [
        (300,   7.0),    # very large footprint = rambling ranch, not tall
        (150,   9.0),    # medium house, could be 2 storey
        (0,    10.0),    # small footprint, could be taller narrow house
    ],
    "residential": [
        (300,   7.0),
        (150,   9.0),
        (0,    10.0),
    ],'''

NEW_HOUSE = '''    "house": [
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


def patch():
    with open(VALIDATOR_PATH, 'r', encoding='utf-8') as f:
        src = f.read()

    changes = 0

    if OLD_SCHOOL in src:
        src = src.replace(OLD_SCHOOL, NEW_SCHOOL)
        changes += 1
        print("School thresholds tightened:")
        print("  400m2+ -> 6m (was 500m2+)")
        print("  150m2+ -> 7.5m (was 200m2+ -> 10m)")
        print("  80m2+  -> 8m (new)")
    else:
        print("WARNING: Could not find school thresholds to replace")

    if OLD_HOUSE in src:
        src = src.replace(OLD_HOUSE, NEW_HOUSE)
        changes += 1
        print("House thresholds tightened:")
        print("  250m2+ -> 6m (was 300m2+ -> 7m)")
        print("  150m2+ -> 7.5m (was 150m2+ -> 9m)")
        print("  80m2+  -> 9m (new)")
    else:
        print("WARNING: Could not find house thresholds to replace")

    if changes > 0:
        with open(VALIDATOR_PATH, 'w', encoding='utf-8') as f:
            f.write(src)
        print(f"\nPATCHED OK - {changes} threshold groups updated")
    else:
        print("\nNo changes made")


if __name__ == '__main__':
    patch()
