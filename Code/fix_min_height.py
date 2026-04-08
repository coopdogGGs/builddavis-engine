"""
Fix: Add minimum height check for university and dormitory buildings.

Overture underestimates UC Davis campus buildings at 4-6m when they're
actually 8-12m (2-3 storeys). The validator currently only checks
"is this too tall?" — now also checks "is this too short?"

University building >200m2 at 5m = implausible, should be at least 8m.
Dormitory at 5m = implausible, should be at least 10m (3 storey).
"""

VALIDATOR_PATH = r'REDACTED_PATH\builddavis-world\src\builddavis\height_validator.py'

# Insert minimum plausibility check right after the max plausibility check
OLD = '''            if h > max_plausible:'''

NEW = '''            # ── Minimum plausibility check ─────────────────────────
            # Overture underestimates some building types (flat roofs
            # on satellite imagery look shorter than they are)
            min_plausible = PLAUSIBILITY_MIN_HEIGHT_M.get(subtype)
            if min_plausible and footprint_area_m2:
                for min_fp, min_h in min_plausible:
                    if footprint_area_m2 >= min_fp:
                        if h < min_h:
                            corrected = min_h
                            corrected_levels = max(1, int(corrected / METRES_PER_LEVEL))
                            tags["height"] = str(round(corrected, 1))
                            tags["building:levels"] = str(corrected_levels)
                            tags["_height_corrected"] = (
                                f"{h}m->{corrected}m "
                                f"(type={subtype}, fp={footprint_area_m2 or '?'}m2, min_plausible)"
                            )
                            tags["_height_source"] = "overture_corrected_up"
                            log.info(
                                f"  Height raised: {h}m -> {corrected}m "
                                f"({subtype}, {footprint_area_m2}m2)")
                            return tags
                        break

            if h > max_plausible:'''


def patch():
    with open(VALIDATOR_PATH, 'r', encoding='utf-8') as f:
        src = f.read()

    changes = 0

    # Step 1: Add the PLAUSIBILITY_MIN_HEIGHT_M table after the max table
    min_table = '''
# ── Minimum plausibility heights ──────────────────────────────────
# Overture ML underestimates flat-roofed campus buildings.
# Format: list of (min_footprint_m2, min_plausible_height_m)
# "If footprint is larger than X m2, height should be at least Y m"
PLAUSIBILITY_MIN_HEIGHT_M = {
    "university": [
        (500,   10.0),   # large university building — at least 3 storey
        (200,    8.0),   # medium university building — at least 2 storey
        (0,      6.0),   # small university structure — at least 1.5 storey
    ],
    "college": [
        (500,   10.0),
        (200,    8.0),
        (0,      6.0),
    ],
    "dormitory": [
        (300,   10.5),   # dorm buildings are 3-4 storey
        (100,    8.0),   # smaller dorm wing — at least 2 storey
        (0,      7.0),
    ],
    "apartments": [
        (300,   10.5),   # apartment complex — at least 3 storey
        (150,    7.0),   # smaller apartments — at least 2 storey
        (0,      5.0),
    ],
}
'''

    # Insert after the FOOTPRINT_RATIO_CHECKS block
    marker = '# ── Default heights when no data exists'
    if 'PLAUSIBILITY_MIN_HEIGHT_M' not in src:
        idx = src.find(marker)
        if idx != -1:
            src = src[:idx] + min_table + '\n' + src[idx:]
            changes += 1
            print("Step 1: Added PLAUSIBILITY_MIN_HEIGHT_M table")
        else:
            print("WARNING: Could not find insertion point for min table")
    else:
        print("Step 1: Min table already present")

    # Step 2: Add the minimum check before the maximum check
    if OLD in src and 'min_plausible' not in src:
        src = src.replace(OLD, NEW)
        changes += 1
        print("Step 2: Added minimum plausibility check")
    elif 'min_plausible' in src:
        print("Step 2: Min check already present")
    else:
        print("WARNING: Could not find max check insertion point")

    if changes > 0:
        with open(VALIDATOR_PATH, 'w', encoding='utf-8') as f:
            f.write(src)
        print(f"\nPATCHED OK - {changes} changes")
        print("\nResult:")
        print("  university 500m2+ at 5m -> raised to 10m (3 levels)")
        print("  university 200m2+ at 5m -> raised to 8m (2 levels)")
        print("  dormitory  300m2+ at 5m -> raised to 10.5m (3 levels)")
        print("  apartments 300m2+ at 5m -> raised to 10.5m (3 levels)")
    else:
        print("\nNo changes made")


if __name__ == '__main__':
    patch()
