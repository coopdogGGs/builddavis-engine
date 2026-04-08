import re

path = r'REDACTED_PATH\builddavis-world\src\builddavis\adapter.py'
with open(path, 'r', encoding='utf-8') as f:
    src = f.read()

# Fix 1: tags reconstruction - handle None tags, always inject primary element tag
OLD1 = (
    '        # fuse.py excludes the raw "tags" dict from GeoJSON properties.\n'
    '        # It promotes selected tag values as osm_{key} top-level properties.\n'
    '        # Reconstruct the tags dict Arnis expects from these osm_* fields.\n'
    '        raw_tags = dict(props.get("tags", {}))  # may be empty for fused features\n'
    '        if not raw_tags:\n'
    '            OSM_TAG_KEYS = (\n'
    '                "building", "highway", "landuse", "waterway", "natural",\n'
    '                "amenity", "leisure", "name", "height", "building:levels",\n'
    '                "building:material", "roof:shape", "surface",\n'
    '            )\n'
    '            for tk in OSM_TAG_KEYS:\n'
    '                val = props.get(f"osm_{tk}")\n'
    '                if val is not None:\n'
    '                    raw_tags[tk] = str(val)\n'
    '            # Also pull subtype into the primary tag if still missing\n'
    '            subtype = props.get("subtype", "")\n'
    '            elem_tag = elem_type  # e.g. "highway", "building", etc.\n'
    '            if elem_tag and subtype and elem_tag not in raw_tags:\n'
    '                raw_tags[elem_tag] = subtype\n'
    '        tags = raw_tags  # mutable copy for enrichment'
)

NEW1 = (
    '        # fuse.py stores OSM tags in the "tags" dict for buildings,\n'
    '        # but highway and other non-building features may have tags=None.\n'
    '        # Reconstruct the tags dict Arnis expects from available fields.\n'
    '        raw_tags = dict(props.get("tags") or {})\n'
    '\n'
    '        if not raw_tags:\n'
    '            OSM_TAG_KEYS = (\n'
    '                "building", "highway", "landuse", "waterway", "natural",\n'
    '                "amenity", "leisure", "name", "height", "building:levels",\n'
    '                "building:material", "roof:shape", "surface",\n'
    '            )\n'
    '            for tk in OSM_TAG_KEYS:\n'
    '                val = props.get(f"osm_{tk}")\n'
    '                if val is not None:\n'
    '                    raw_tags[tk] = str(val)\n'
    '\n'
    '        # Always ensure the primary element tag is present.\n'
    '        subtype = props.get("subtype", "")\n'
    '        if elem_type and elem_type not in raw_tags:\n'
    '            raw_tags[elem_type] = subtype if subtype else "yes"\n'
    '\n'
    '        if name and "name" not in raw_tags:\n'
    '            raw_tags["name"] = name\n'
    '\n'
    '        tags = raw_tags  # mutable copy for enrichment'
)

# Fix 2: None-safe abandoned check
OLD2 = '    if feat.get("tags", {}).get("abandoned") == "yes":'
NEW2 = '    if (feat.get("tags") or {}).get("abandoned") == "yes":'

fixed = src
if OLD1 in fixed:
    fixed = fixed.replace(OLD1, NEW1)
    print("Fix 1 applied: tags reconstruction")
else:
    print("Fix 1 NOT FOUND")

if OLD2 in fixed:
    fixed = fixed.replace(OLD2, NEW2)
    print("Fix 2 applied: None-safe abandoned check")
else:
    print("Fix 2 NOT FOUND")

if fixed != src:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(fixed)
    print(f"Saved - lines now: {len(fixed.splitlines())}")
else:
    print("No changes made")
