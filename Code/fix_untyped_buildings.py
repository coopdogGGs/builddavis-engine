"""
Fix: building=yes and untyped Overture buildings get treated as
residential in the height validator. In Davis, an untyped building
in a residential area is almost always a house.

Also tightens the 'yes' and 'default' plausibility limits and
adds 'yes' to the footprint ratio checks.
"""

VALIDATOR_PATH = r'REDACTED_PATH\builddavis-world\src\builddavis\height_validator.py'


def patch():
    with open(VALIDATOR_PATH, 'r', encoding='utf-8') as f:
        src = f.read()

    changes = 0

    # Fix 1: Lower plausibility max for 'yes' and 'default' types
    old1 = '    "yes":               12.0,'
    new1 = '    "yes":                7.5,    # untyped in Davis = likely house, cap conservatively'
    if old1 in src:
        src = src.replace(old1, new1)
        changes += 1
        print("Fix 1: 'yes' plausibility 12m -> 7.5m")

    old2 = '    "default":           14.0,'
    new2 = '    "default":            8.0,    # unknown type in Davis = cap conservatively'
    if old2 in src:
        src = src.replace(old2, new2)
        changes += 1
        print("Fix 2: 'default' plausibility 14m -> 8m")

    # Fix 3: Add 'yes' to footprint ratio checks (treat like house)
    old3 = '''    "kindergarten": [
        (200,   4.5),
        (0,     6.0),
    ],'''
    new3 = '''    "kindergarten": [
        (200,   4.5),
        (0,     6.0),
    ],
    "yes": [
        (250,   6.0),    # large untyped building = probably ranch house
        (150,   7.5),    # medium = could be 2 storey
        (80,    8.0),
        (0,     9.0),
    ],'''
    if old3 in src:
        src = src.replace(old3, new3)
        changes += 1
        print("Fix 3: Added 'yes' to footprint ratio checks (same as house)")

    # Fix 4: Lower default height for 'yes' when no data exists
    old4 = '    "yes":          5.0,'
    new4 = '    "yes":          4.5,    # untyped = assume single storey house'
    if old4 in src:
        src = src.replace(old4, new4)
        changes += 1
        print("Fix 4: 'yes' default height 5m -> 4.5m")

    if changes > 0:
        with open(VALIDATOR_PATH, 'w', encoding='utf-8') as f:
            f.write(src)
        print(f"\nPATCHED OK - {changes} fixes applied")
        print("\nResult: building=yes at 8.1m will now be corrected to ~7.5m")
        print("        building=yes at 6.9m with large footprint -> 6.0m")
    else:
        print("No changes made - check file contents")


if __name__ == '__main__':
    patch()
