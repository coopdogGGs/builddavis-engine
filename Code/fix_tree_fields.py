# fix_tree_fields.py - Updates fetch_ucdavis_trees.py to use correct UC Davis field names
# Run from Anaconda Prompt:
#   python REDACTED_PATH\Downloads\fix_tree_fields.py

path = r'REDACTED_PATH\builddavis-world\src\builddavis\fetch_ucdavis_trees.py'

with open(path, 'r', encoding='utf-8') as f:
    src = f.read()

old = '''        scientific = (
            props.get("ScientificName") or
            props.get("scientificname") or
            props.get("SCIENTIFIC_NAME") or
            props.get("Genus_Species") or
            props.get("genus_species") or
            ""
        )
        common = (
            props.get("CommonName") or
            props.get("commonname") or
            props.get("COMMON_NAME") or
            props.get("common_name") or
            ""
        )'''

new = '''        # UC Davis field names confirmed from API
        genus = (props.get("Genus") or "").strip()
        epithet = (props.get("SpecificEpithet") or "").strip()
        scientific = (props.get("ScientificName") or "").strip()
        common = (props.get("CommonName") or "").strip()
        status = (props.get("Status") or "").strip()
        height_ft = props.get("Height_ft")

        # Skip removed/dead trees
        if status.lower() in ("removed", "dead", "stump"):
            skipped += 1
            continue

        # Build full scientific name from parts if ScientificName missing
        if not scientific and genus:
            scientific = (genus + " " + epithet).strip()'''

if old in src:
    src = src.replace(old, new)

    # Also update the species_to_osm_tags call to pass genus directly
    old2 = '        species_tags = species_to_osm_tags(scientific, common)'
    new2 = '        species_tags = species_to_osm_tags(scientific + " " + genus, common)'
    src = src.replace(old2, new2)

    # Add height tag injection
    old3 = '        osm_tags = {\n            "natural": "tree",\n            **species_tags,\n        }'
    new3 = '''        osm_tags = {
            "natural": "tree",
            **species_tags,
        }
        # Inject height if available (convert feet to metres)
        if height_ft and str(height_ft).strip() not in ("", "None", "0"):
            try:
                height_m = round(float(height_ft) * 0.3048, 1)
                osm_tags["height"] = str(height_m)
            except (ValueError, TypeError):
                pass'''
    src = src.replace(old3, new3)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(src)
    print("PATCHED OK - field names, status filter, and height conversion applied")
else:
    print("NOT FOUND - fetch_ucdavis_trees.py may already be patched or has different content")
    idx = src.find('props.get("ScientificName")')
    if idx < 0:
        idx = src.find('props.get("Genus")')
    print("Nearest match at:", idx)
    if idx > 0:
        print(repr(src[idx:idx+200]))
