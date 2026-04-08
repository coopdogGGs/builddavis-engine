# fix_park_grass.py - Fix tall grass on open park areas
# Changes mixed-density parks to landuse=grass instead of leisure=park
# Run from Anaconda Prompt: python REDACTED_PATH\Downloads\fix_park_grass.py

path = r'REDACTED_PATH\builddavis-world\src\builddavis\adapter.py'
with open(path, 'r', encoding='utf-8') as f:
    src = f.read()

# Fix 1: Lower the open lawn threshold so more parks classify as grass
old1 = 'PARK_OPEN_THRESHOLD_PER_100SQM         = 0.05  # trees per 100 m² → open'
new1 = 'PARK_OPEN_THRESHOLD_PER_100SQM         = 0.3   # trees per 100 m² → open (raised to catch mixed areas)'

# Fix 2: Change the mixed case to also become grass rather than staying as park
old2 = '''    else:
        # Mixed — keep as leisure=park (Arnis moderate density is correct)
        record.add_enrichment(
            "landuse_type", "tree_density_analysis",
            "leisure=park", "leisure=park (mixed, unchanged)",
            confidence=0.6,
            note=f"Tree density {density_per_100sqm:.2f}/100m² → mixed"
        )'''

new2 = '''    else:
        # Mixed density — reclassify as grass to prevent Arnis tall grass fill
        # UC Davis trees not yet in mc_coord space so density is underestimated
        # Defaulting to clean grass is correct for Davis open spaces
        tags["landuse"] = "grass"
        tags.pop("leisure", None)
        record.add_enrichment(
            "landuse_type", "tree_density_analysis",
            "leisure=park", "landuse=grass (mixed→grass default)",
            confidence=0.6,
            note=f"Tree density {density_per_100sqm:.2f}/100m² → grass (mixed default)"
        )'''

patched = src
count = 0
if old1 in patched:
    patched = patched.replace(old1, new1)
    count += 1
    print("Fix 1 applied: raised PARK_OPEN_THRESHOLD to 0.3")
else:
    print("Fix 1 NOT FOUND")

if old2 in patched:
    patched = patched.replace(old2, new2)
    count += 1
    print("Fix 2 applied: mixed parks now reclassify to landuse=grass")
else:
    print("Fix 2 NOT FOUND")

if count > 0:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(patched)
    print(f"Saved - {count} fixes applied")
else:
    print("Nothing patched")
