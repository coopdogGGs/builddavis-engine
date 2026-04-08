"""
Fix: validator should always set building:levels when it's missing,
not just when correcting height. Otherwise Arnis uses its own formula
(height/4 + 2) which gives 2 floors for a 6.8m house.

Our formula: int(6.8 / 3.5) = 1 floor (correct for Davis ranch house)
Arnis formula: 6.8 / 4 + 2 = ~4 blocks per floor = 2 floors (wrong)
"""

VALIDATOR_PATH = r'REDACTED_PATH\builddavis-world\src\builddavis\height_validator.py'

# Find the "overture_accepted" block and add levels calculation
OLD = '''            else:
                tags["_height_source"] = "overture_accepted"

        return tags'''

NEW = '''            else:
                # Height is plausible — but always set levels if missing
                # so Arnis uses our calculation, not its own formula
                if not tags.get("building:levels"):
                    accepted_levels = max(1, int(h / METRES_PER_LEVEL))
                    tags["building:levels"] = str(accepted_levels)
                tags["_height_source"] = "overture_accepted"

        return tags'''


def patch():
    with open(VALIDATOR_PATH, 'r', encoding='utf-8') as f:
        src = f.read()

    if OLD not in src:
        print("ERROR: Could not find insertion point")
        # Show what's around overture_accepted
        idx = src.find('overture_accepted')
        if idx != -1:
            print(repr(src[idx-200:idx+200]))
        return

    src = src.replace(OLD, NEW)

    with open(VALIDATOR_PATH, 'w', encoding='utf-8') as f:
        f.write(src)

    print("PATCHED OK")
    print("  6.8m house: int(6.8/3.5) = 1 level (was unset -> Arnis chose 2)")
    print("  6.6m house: int(6.6/3.5) = 1 level")
    print("  6.9m house: int(6.9/3.5) = 1 level")
    print("  7.5m house: int(7.5/3.5) = 2 levels (correct for genuine 2-storey)")


if __name__ == '__main__':
    patch()
