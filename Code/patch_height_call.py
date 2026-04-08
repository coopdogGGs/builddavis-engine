"""
Insert validate_height call at the exact right location in adapter.py
(after enrich_4a_height, before enrich_4c_colour)
"""

ADAPTER_PATH = r'REDACTED_PATH\builddavis-world\src\builddavis\adapter.py'

OLD = '            enrich_4a_height(props, tags, record)\n            enrich_4c_colour(props, tags, record, colour_cache)'

NEW = '''            enrich_4a_height(props, tags, record)

            # ── Height validation (trust hierarchy + footprint plausibility) ──
            _fp_area = props.get("area_blocks") or props.get("footprint_area")
            _h_src = "osm" if props.get("osm_building_levels") or props.get("osm_height") else (
                     "overture" if props.get("height_m") else "none")
            tags = validate_height(tags, subtype, _fp_area, {"height_source": _h_src})

            enrich_4c_colour(props, tags, record, colour_cache)'''

def patch():
    with open(ADAPTER_PATH, 'r', encoding='utf-8') as f:
        src = f.read()

    if 'validate_height(tags, subtype' in src:
        print("validate_height call already present — no changes needed")
        return

    if OLD not in src:
        print("ERROR: Could not find the exact insertion point.")
        print("Looking for:")
        print(repr(OLD))
        # Try to find partial match
        if 'enrich_4a_height' in src and 'enrich_4c_colour' in src:
            print("\nBoth functions exist but the exact text between them differs.")
            idx = src.find('enrich_4a_height')
            print("Context around enrich_4a_height:")
            print(repr(src[idx:idx+200]))
        return

    src = src.replace(OLD, NEW)

    with open(ADAPTER_PATH, 'w', encoding='utf-8') as f:
        f.write(src)

    print("PATCHED OK")
    print(f"Lines: {src.count(chr(10)) + 1}")
    print("validate_height now called after enrich_4a_height, before enrich_4c_colour")
    print("Uses footprint area + height source to determine trust level")


if __name__ == '__main__':
    patch()
