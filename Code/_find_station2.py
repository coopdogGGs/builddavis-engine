# WARNING: Uses parse.py coordinate system (Amtrak station = MC origin 0,0).
# Outputs RELATIVE OFFSETS only — NOT absolute MC coords.
# DO NOT use these values for placement or /tp commands.
# For real placement coordinates use: python Code/mc_locate.py --name "..."

"""Check if station way 62095055 exists in osm_raw.json."""
import json

with open("data/osm_raw.json", "r") as f:
    data = json.load(f)

elements = data.get("elements", data) if isinstance(data, dict) else data
print(f"Total raw elements: {len(elements)}")

found = [e for e in elements if e.get("id") == 62095055]
if found:
    e = found[0]
    print("FOUND in osm_raw.json:")
    print(f"  type: {e.get('type')}")
    print(f"  tags: {json.dumps(e.get('tags', {}), indent=2)}")
    if "nodes" in e:
        print(f"  nodes count: {len(e['nodes'])}")
else:
    print("MISSING from osm_raw.json")
    # Search for any station-tagged ways
    for e in elements:
        tags = e.get("tags", {})
        if e.get("type") == "way" and ("station" in str(tags).lower() or tags.get("building") == "train_station"):
            print(f"  station-way: id={e['id']} building={tags.get('building','N/A')} name={tags.get('name','N/A')} railway={tags.get('railway','N/A')}")
