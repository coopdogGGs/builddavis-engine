"""
Direct fix: insert minimum height check at line 200 in height_validator.py
"""

VALIDATOR_PATH = r'REDACTED_PATH\builddavis-world\src\builddavis\height_validator.py'

MIN_CHECK = '''
            # ── Minimum plausibility check ─────────────────────────
            # Overture underestimates flat-roofed campus buildings
            _min_rules = PLAUSIBILITY_MIN_HEIGHT_M.get(subtype)
            if _min_rules and footprint_area_m2:
                for _min_fp, _min_h in _min_rules:
                    if footprint_area_m2 >= _min_fp:
                        if h < _min_h:
                            corrected = _min_h
                            corrected_levels = max(1, int(corrected / METRES_PER_LEVEL))
                            tags["height"] = str(round(corrected, 1))
                            tags["building:levels"] = str(corrected_levels)
                            tags["_height_corrected"] = (
                                f"{h}m->{corrected}m "
                                f"(type={subtype}, fp={footprint_area_m2}m2, raised_min)")
                            tags["_height_source"] = "overture_corrected_up"
                            log.info(f"  Height raised: {h}m -> {corrected}m ({subtype}, {footprint_area_m2}m2)")
                            return tags
                        break

'''

def patch():
    with open(VALIDATOR_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Find the line "if h > max_plausible:"
    insert_idx = None
    for i, line in enumerate(lines):
        if 'if h > max_plausible:' in line:
            insert_idx = i
            break

    if insert_idx is None:
        print("ERROR: Could not find 'if h > max_plausible:' line")
        return

    # Check if min check already inserted
    nearby = ''.join(lines[max(0, insert_idx-20):insert_idx])
    if 'PLAUSIBILITY_MIN_HEIGHT_M.get' in nearby:
        print("Min check already inserted")
        return

    # Insert the min check before the max check
    min_lines = MIN_CHECK.split('\n')
    for j, ml in enumerate(min_lines):
        lines.insert(insert_idx + j, ml + '\n')

    with open(VALIDATOR_PATH, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print(f"PATCHED OK - inserted min check before line {insert_idx + 1}")
    print("  university 500m2+ at <10m -> raised to 10m")
    print("  university 200m2+ at <8m  -> raised to 8m")
    print("  dormitory  300m2+ at <10.5m -> raised to 10.5m")


if __name__ == '__main__':
    patch()
