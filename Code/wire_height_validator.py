"""
Wire height_validator.py into adapter.py

Run:
  1. Copy height_validator.py to src/builddavis/
  2. python wire_height_validator.py
"""

ADAPTER_PATH = r'REDACTED_PATH\builddavis-world\src\builddavis\adapter.py'


def patch():
    with open(ADAPTER_PATH, 'r', encoding='utf-8') as f:
        src = f.read()

    changes = 0

    # Step 1: Add import
    import_line = 'from height_validator import validate_height'
    if import_line not in src:
        lines = src.split('\n')
        last_import = 0
        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith('import ') or s.startswith('from '):
                last_import = i
            if s.startswith('def ') or s.startswith('class '):
                break
        lines.insert(last_import + 1, import_line)
        src = '\n'.join(lines)
        changes += 1
        print(f"Step 1: Added import after line {last_import + 1}")
    else:
        print("Step 1: Import already present")

    # Step 2: Add validate_height call before element output
    validate_call = 'raw_tags = validate_height('
    if validate_call not in src:
        # Find where elem_tag/subtype tags are injected
        target = 'if elem_tag and subtype'
        idx = src.find(target)
        if idx != -1:
            line_start = src.rfind('\n', 0, idx)
            rest = src[line_start + 1:idx]
            indent = rest[:len(rest) - len(rest.lstrip())]

            insert = (
                f'\n{indent}# ── Height validation (trust hierarchy + plausibility) ──\n'
                f'{indent}if raw_tags.get("building"):\n'
                f'{indent}    _fp = props.get("area_blocks", props.get("footprint_area"))\n'
                f'{indent}    _src = {{"height_source": "osm" if props.get("osm_height") else "overture" if props.get("height_m") else "none"}}\n'
                f'{indent}    raw_tags = validate_height(raw_tags, subtype, _fp, _src)\n'
            )
            src = src[:line_start + 1] + insert + src[line_start + 1:]
            changes += 1
            print(f"Step 2: Inserted validate_height call")
        else:
            # Fallback: try overpass append
            target2 = 'overpass["elements"].append'
            idx2 = src.find(target2)
            if idx2 != -1:
                line_start = src.rfind('\n', 0, idx2)
                indent = '        '
                insert = (
                    f'\n{indent}# ── Height validation ──\n'
                    f'{indent}if raw_tags.get("building"):\n'
                    f'{indent}    _fp = props.get("area_blocks")\n'
                    f'{indent}    _src = {{"height_source": "overture" if props.get("height_m") else "none"}}\n'
                    f'{indent}    raw_tags = validate_height(raw_tags, subtype, _fp, _src)\n'
                )
                src = src[:line_start + 1] + insert + src[line_start + 1:]
                changes += 1
                print(f"Step 2: Inserted via fallback location")
            else:
                print("Step 2: WARNING - could not find insertion point")
                print("  Manually add before element output:")
                print("    raw_tags = validate_height(raw_tags, subtype, footprint_area, source_info)")
    else:
        print("Step 2: validate_height already wired")

    if changes > 0:
        with open(ADAPTER_PATH, 'w', encoding='utf-8') as f:
            f.write(src)
        print(f"\nPATCHED OK - {changes} changes, {src.count(chr(10)) + 1} lines")
    else:
        print("\nNo changes needed")


if __name__ == '__main__':
    patch()
