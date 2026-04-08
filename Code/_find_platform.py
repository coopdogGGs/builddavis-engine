# WARNING: Uses parse.py coordinate system (Amtrak station = MC origin 0,0).
# Outputs RELATIVE OFFSETS only — NOT absolute MC coords.
# DO NOT use these values for placement or /tp commands.
# For real placement coordinates use: python Code/mc_locate.py --name "..."

"""Find railway=platform and station features in enriched_overpass.json."""
import json

with open("data/enriched_overpass.json") as f:
    data = json.load(f)

# Build node lookup from all node elements
nodes = {}
for el in data.get("elements", []):
    if el["type"] == "node" and "lat" in el:
        nodes[el["id"]] = (el["lat"], el["lon"])

print(f"Loaded {len(nodes)} nodes")

# Find station-related features
target_ids = set()
platforms = []
for el in data.get("elements", []):
    tags = el.get("tags", {})
    match = False
    if tags.get("railway") == "platform":
        match = True
    elif tags.get("public_transport") == "platform":
        match = True
    elif tags.get("building") == "train_station":
        match = True
    elif "amtrak" in tags.get("name", "").lower():
        match = True
    elif tags.get("railway") == "station":
        match = True
    if match:
        platforms.append(el)
        target_ids.add(el["id"])

print(f"Found {len(platforms)} platform/station features")

bbox_min_lat, bbox_min_lon = 38.530, -121.760
bbox_max_lat, bbox_max_lon = 38.555, -121.725
world_x, world_z = 3043, 2779

for p in platforms:
    eid = p["id"]
    etype = p["type"]
    tags = p.get("tags", {})
    name = tags.get("name", "unnamed")
    print(f"\n--- {name} (type={etype}, id={eid}) ---")
    print(f"  tags: {tags}")

    clat, clon = None, None

    # Try inline geometry first
    if "geometry" in p:
        lats = [n["lat"] for n in p["geometry"]]
        lons = [n["lon"] for n in p["geometry"]]
        clat = sum(lats) / len(lats)
        clon = sum(lons) / len(lons)
        print(f"  geometry: {len(lats)} points")

    # Try node references
    elif "nodes" in p:
        nids = p["nodes"]
        lats, lons = [], []
        for nid in nids:
            if nid in nodes:
                lats.append(nodes[nid][0])
                lons.append(nodes[nid][1])
        if lats:
            clat = sum(lats) / len(lats)
            clon = sum(lons) / len(lons)
            print(f"  nodes: {len(nids)} refs, {len(lats)} resolved")
        else:
            print(f"  nodes: {len(nids)} refs, NONE resolved")

    # Try direct lat/lon
    elif "lat" in p:
        clat = p["lat"]
        clon = p["lon"]
        print(f"  direct point")

    if clat and clon:
        print(f"  centroid: lat={clat:.6f}, lon={clon:.6f}")
        rx = (clon - bbox_min_lon) / (bbox_max_lon - bbox_min_lon)
        rz = 1.0 - (clat - bbox_min_lat) / (bbox_max_lat - bbox_min_lat)
        mc_x = int(rx * world_x)
        mc_z = int(rz * world_z)
        print(f"  MC centroid: X={mc_x}, Z={mc_z}")
        # Structure placement (33x19 with center at X+16, Z+9)
        sx = mc_x - 16
        sz = mc_z - 9
        print(f"  Structure placement (33x19 centered): X={sx}, Y=49, Z={sz}")
    else:
        print(f"  NO COORDINATES FOUND")
