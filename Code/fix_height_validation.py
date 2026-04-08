"""
Patch adapter.py to add building height validation.

Fixes from POC3 (Holmes Junior High):
- Residential houses capped at 7m (single storey + roof)
- School buildings forced to 1 storey flat roof (1960s Davis style)  
- Apartments/commercial allowed up to Overture height
- Basketball courts get surface=asphalt when sport tag present
- School grounds get landuse=grass override
"""
import os, re

path = r'REDACTED_PATH\builddavis-world\src\builddavis\adapter.py'
if not os.path.exists(path):
    path = os.path.expanduser('~/builddavis-world/src/builddavis/adapter.py')

with open(path, 'r', encoding='utf-8') as f:
    src = f.read()

original_len = len(src)

# ── 1. Add the height validation function ────────────────────────────────────

validation_func = '''
# ── Height Validation (POC3 findings) ───────────────────────────────────────
# Overture ML heights overestimate single-storey Davis buildings.
# Validate and cap heights based on building type and context.

_HEIGHT_CAPS = {
    "house": 7.0, "residential": 7.0, "detached": 7.0,
    "semidetached_house": 8.0, "terrace": 8.0, "bungalow": 5.0,
    "cabin": 5.0, "static_caravan": 4.0,
    "garage": 4.0, "garages": 4.0, "shed": 3.0, "carport": 3.0,
    "roof": 4.0,
    "school": 5.0,
    "church": 15.0, "chapel": 10.0,
    "farm": 6.0, "barn": 8.0, "farm_auxiliary": 5.0,
    "_residential_default": 8.0,
}
_HEIGHT_TRUSTED = {
    "apartments", "commercial", "retail", "office", "industrial",
    "warehouse", "hotel", "hospital", "university", "civic",
    "government", "public", "train_station", "transportation", "parking",
}

def _validate_height(height_m, subtype, zone=None):
    """Return (validated_height, was_capped)."""
    if height_m is None:
        return None, False
    bt = (subtype or "").lower().strip()
    if bt in _HEIGHT_TRUSTED:
        return height_m, False
    cap = _HEIGHT_CAPS.get(bt)
    if cap is None and zone in ("residential", None):
        cap = _HEIGHT_CAPS.get("_residential_default")
    if cap and height_m > cap:
        return cap, True
    return height_m, False

'''

# Insert before the first class or function definition
inserted = False
for marker in ["class EnrichmentStats", "def convert(", "def build_tree_index("]:
    idx = src.find(marker)
    if idx >= 0:
        src = src[:idx] + validation_func + src[idx:]
        print(f"Step 1 OK: Inserted _validate_height before '{marker[:30]}...'")
        inserted = True
        break

if not inserted:
    print("ERROR: No insertion point found")
    exit(1)

# ── 2. Hook validation into height enrichment ────────────────────────────────

height_assign = re.search(
    r'([ \t]+)(height_m\s*=\s*props\.get\(["\']height_m["\']\s*(?:,\s*[^)]+)?\))',
    src
)

if height_assign:
    indent = height_assign.group(1)
    assign_end = height_assign.end()
    hook = f'\n{indent}# POC3 fix: validate height against building type\n'
    hook += f'{indent}height_m, _hcapped = _validate_height(height_m, props.get("subtype", ""), props.get("_spec003_zone"))\n'
    hook += f'{indent}if _hcapped: stats.height_capped = getattr(stats, "height_capped", 0) + 1\n'
    src = src[:assign_end] + hook + src[assign_end:]
    print("Step 2 OK: Hooked validation after height_m assignment")
else:
    alt = re.search(r'([ \t]+).*height_m.*=.*props', src)
    if alt:
        indent = alt.group(1)
        line_end = src.find('\n', alt.end())
        hook = f'\n{indent}# POC3 fix: validate height against building type\n'
        hook += f'{indent}if height_m is not None:\n'
        hook += f'{indent}    height_m, _hcapped = _validate_height(height_m, props.get("subtype", ""), props.get("_spec003_zone"))\n'
        hook += f'{indent}    if _hcapped: stats.height_capped = getattr(stats, "height_capped", 0) + 1\n'
        src = src[:line_end] + hook + src[line_end:]
        print("Step 2 OK (alt): Hooked validation after height reference")
    else:
        print("WARNING: Could not find height_m assignment - manual hook needed")

# ── 3. School building overrides ─────────────────────────────────────────────

tag_write = src.find('raw_tags[elem_tag] = subtype')
if tag_write < 0:
    tag_write = src.find('elem_tag] = subtype')

if tag_write > 0:
    line_end = src.find('\n', tag_write)
    school_block = '''
        # POC3 fix: school buildings = single storey flat roof
        if subtype == "school" or props.get("subtype") == "school":
            raw_tags["building:levels"] = "1"
            raw_tags["roof:shape"] = "flat"
            if "height" in raw_tags:
                try:
                    h = float(raw_tags["height"])
                    if h > 5.0:
                        raw_tags["height"] = "5.0"
                except ValueError:
                    pass
        # POC3 fix: basketball/tennis courts = asphalt surface
        if raw_tags.get("leisure") == "pitch":
            sport = raw_tags.get("sport", props.get("sport", ""))
            if sport in ("basketball", "tennis", "multi"):
                raw_tags["surface"] = "asphalt"
        # POC3 fix: school grounds = grass not urban stone
        if raw_tags.get("amenity") == "school" or raw_tags.get("building") == "school":
            if "landuse" not in raw_tags:
                raw_tags["landuse"] = "grass"
'''
    src = src[:line_end+1] + school_block + src[line_end+1:]
    print("Step 3 OK: Added school, court surface, and school grounds overrides")
else:
    print("WARNING: Could not find tag write section")

# ── Write ─────────────────────────────────────────────────────────────────────

with open(path, 'w', encoding='utf-8') as f:
    f.write(src)

line_count = src.count('\n') + 1
print(f"\nPATCHED OK - {line_count} lines (added {len(src) - original_len} chars)")
print("\nHeight caps:")
print("  house/residential:  7m max")
print("  school:             5m max (flat roof, levels=1)")
print("  garage/shed:        3-4m max")
print("  apartments/commercial: NO cap")
print("\nAlso fixed:")
print("  Basketball courts:  surface=asphalt")
print("  School grounds:     landuse=grass")
