"""
fuse_trees_patch2.py - Patches fuse.py to merge UC Davis tree data.
Uses the correct text found in Ryan's actual fuse.py.
"""
import re

path = r'REDACTED_PATH\builddavis-world\src\builddavis\fuse.py'

with open(path, 'r', encoding='utf-8') as f:
    src = f.read()

# Check if already patched
if 'ucdavis_trees' in src:
    print("fuse.py already patched for UC Davis trees")
else:
    # Find the combine/sort section using regex to handle whitespace variations
    pattern = r'(    # ── Combine and sort ─+\s+all_fused = enriched_non_buildings \+ fused_buildings)'
    match = re.search(pattern, src)
    if match:
        old = match.group(0)
        new = '''    # ── Merge UC Davis tree database ─────────────────────────────
    # If ucdavis_trees.geojson exists alongside the output, merge it in.
    import json as _json
    from pathlib import Path as _Path
    _tree_path = _Path(output_dir) / "ucdavis_trees.geojson"
    if _tree_path.exists():
        try:
            _tree_data = _json.load(open(_tree_path))
            _tree_feats = _tree_data.get("features", [])
            _tree_elements = [f.get("properties", {}) for f in _tree_feats if f.get("properties")]
            log.info("  Merged %d UC Davis trees into pipeline", len(_tree_elements))
            enriched_non_buildings = enriched_non_buildings + _tree_elements
        except Exception as _exc:
            log.warning("  UC Davis tree merge failed: %s", _exc)
    else:
        log.info("  No UC Davis tree database found at %s", _tree_path)

''' + old
        src = src.replace(old, new)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(src)
        print("PATCHED OK - fuse.py will now merge UC Davis trees")
    else:
        # Show what we found around combine/sort
        idx = src.find('all_fused = enriched_non_buildings')
        if idx >= 0:
            print("Found all_fused at index", idx)
            print("Context:")
            print(repr(src[max(0, idx-200):idx+100]))
            print()
            # Try direct injection before all_fused line
            old2 = '    all_fused = enriched_non_buildings + fused_buildings'
            if old2 in src:
                new2 = '''    # ── Merge UC Davis tree database ─────────────────────────────
    import json as _json
    from pathlib import Path as _Path
    _tree_path = _Path(output_dir) / "ucdavis_trees.geojson"
    if _tree_path.exists():
        try:
            _tree_data = _json.load(open(_tree_path))
            _tree_elements = [f.get("properties", {}) for f in _tree_data.get("features", []) if f.get("properties")]
            log.info("  Merged %d UC Davis trees", len(_tree_elements))
            enriched_non_buildings = enriched_non_buildings + _tree_elements
        except Exception as _exc:
            log.warning("  UC Davis tree merge failed: %s", _exc)
    all_fused = enriched_non_buildings + fused_buildings'''
                src = src.replace(old2, new2, 1)
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(src)
                print("PATCHED OK (direct injection)")
            else:
                print("Could not find injection point - manual edit required")
        else:
            print("all_fused not found in fuse.py at all")
            print("Check fuse.py manually")
