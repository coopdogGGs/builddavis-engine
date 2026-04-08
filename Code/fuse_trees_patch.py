"""
fuse_trees_patch.py - Patches fuse.py to merge UC Davis tree data.
Run once after downloading adapter_fixed.py.
"""
import os

path = r'REDACTED_PATH\builddavis-world\src\builddavis\fuse.py'
with open(path, 'r', encoding='utf-8') as f:
    src = f.read()

# Find the main() function entry point where we can inject tree merging
# We'll add it just before the final sort/return of all_fused

OLD = '''    # ── Combine and sort ──────────────────────────────────────────
    all_fused = enriched_non_buildings + fused_buildings'''

NEW = '''    # ── Merge UC Davis tree database ─────────────────────────────
    # If ucdavis_trees.geojson exists in output_dir, merge it in.
    # Trees are already in OSM-compatible format from fetch_ucdavis_trees.py
    ucdavis_trees_path = Path(output_dir) / "ucdavis_trees.geojson"
    if ucdavis_trees_path.exists():
        try:
            with open(ucdavis_trees_path) as tf:
                tree_data = json.load(tf)
            tree_feats = tree_data.get("features", [])
            # Convert GeoJSON Feature wrappers to flat dicts matching our format
            tree_elements = []
            for feat in tree_feats:
                props = feat.get("properties", {})
                if props:
                    tree_elements.append(props)
            log.info("  Merged %d UC Davis trees into pipeline", len(tree_elements))
            enriched_non_buildings = enriched_non_buildings + tree_elements
        except Exception as exc:
            log.warning("  UC Davis tree merge failed: %s", exc)
    else:
        log.info("  UC Davis tree database not found at %s — skipping", ucdavis_trees_path)

    # ── Combine and sort ──────────────────────────────────────────
    all_fused = enriched_non_buildings + fused_buildings'''

if OLD in src:
    src = src.replace(OLD, NEW)
    # Also ensure Path and json are imported (they likely already are)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(src)
    print('PATCHED OK - fuse.py now merges UC Davis trees')
else:
    print('NOT FOUND - checking fuse.py structure')
    idx = src.find('all_fused = enriched_non_buildings')
    print(repr(src[max(0,idx-100):idx+200]))
