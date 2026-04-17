"""Trace way 62095055 (Davis Amtrak station) through the pipeline."""
import json, os

STATION_ID = 62095055
DATA = "data"

# 1. Check osm_raw.json
print("=== 1. osm_raw.json ===")
with open(os.path.join(DATA, "osm_raw.json")) as f:
    raw = json.load(f)
found_raw = None
for el in raw.get("elements", []):
    if el.get("id") == STATION_ID:
        found_raw = el
        break
if found_raw:
    print(f"  FOUND: type={found_raw['type']}, tags={json.dumps(found_raw.get('tags',{}))}")
    if "nodes" in found_raw:
        print(f"  nodes: {len(found_raw['nodes'])}")
else:
    print("  NOT FOUND")

# 2. Check elements.json
print("\n=== 2. elements.json ===")
with open(os.path.join(DATA, "elements.json")) as f:
    elements = json.load(f)
found_elem = None
for el in elements:
    if el.get("osm_id") == STATION_ID or el.get("id") == STATION_ID:
        found_elem = el
        break
if found_elem:
    print(f"  FOUND: osm_type={found_elem.get('osm_type')}, name={found_elem.get('name')}")
else:
    print("  NOT FOUND")
    # Search by name
    for el in elements:
        n = el.get("name", "").lower()
        if "amtrak" in n or "train station" in n or "davis station" in n:
            print(f"  Similar: id={el.get('osm_id')} name={el.get('name')} type={el.get('osm_type')}")

# 3. Check fused_features.geojson
print("\n=== 3. fused_features.geojson ===")
fused_path = os.path.join(DATA, "fused_features.geojson")
if os.path.exists(fused_path):
    with open(fused_path) as f:
        fused = json.load(f)
    found_fused = None
    for feat in fused.get("features", []):
        props = feat.get("properties", {})
        if props.get("osm_id") == STATION_ID or props.get("id") == STATION_ID:
            found_fused = feat
            break
    if found_fused:
        print(f"  FOUND: {json.dumps(found_fused['properties'], indent=2)[:300]}")
    else:
        print("  NOT FOUND")
        for feat in fused.get("features", []):
            props = feat.get("properties", {})
            n = props.get("name", "").lower()
            if "amtrak" in n or "train station" in n or "davis station" in n:
                print(f"  Similar: id={props.get('osm_id')} name={props.get('name')}")
else:
    print("  File not found")

# 4. Check enriched_overpass.json
print("\n=== 4. enriched_overpass.json ===")
with open(os.path.join(DATA, "enriched_overpass.json")) as f:
    enriched = json.load(f)
found_enriched = None
for el in enriched.get("elements", []):
    if el.get("id") == STATION_ID:
        found_enriched = el
        break
if found_enriched:
    print(f"  FOUND: tags={json.dumps(found_enriched.get('tags',{}))[:200]}")
else:
    print("  NOT FOUND")
    # Check nearby station-like buildings
    for el in enriched.get("elements", []):
        tags = el.get("tags", {})
        n = tags.get("name", "").lower()
        bt = tags.get("building", "").lower()
        if "amtrak" in n or "train_station" in bt or "station" in bt or "transportation" in bt:
            print(f"  Similar: id={el['id']} type={el['type']} building={bt} name={tags.get('name','')}")
