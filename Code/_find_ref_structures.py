# WARNING: Uses parse.py coordinate system (Amtrak station = MC origin 0,0).
# Outputs RELATIVE OFFSETS only — NOT absolute MC coords.
# DO NOT use these values for placement or /tp commands.
# For real placement coordinates use: python Code/mc_locate.py --name "..."

"""Find Varsity Theater and Amtrak Station in enriched_overpass.json to get exact lat/lon for bbox verification."""
import json, math

with open("data/enriched_overpass.json") as f:
    data = json.load(f)

BBOX_MIN_LAT, BBOX_MAX_LAT = 38.530, 38.555
BBOX_MIN_LON, BBOX_MAX_LON = -121.760, -121.725
WORLD_X, WORLD_Z = 3043, 2779

def geo_to_mc(lat, lon):
    rx = (lon - BBOX_MIN_LON) / (BBOX_MAX_LON - BBOX_MIN_LON)
    rz = 1.0 - (lat - BBOX_MIN_LAT) / (BBOX_MAX_LAT - BBOX_MIN_LAT)
    return int(rx * WORLD_X), int(rz * WORLD_Z)

# Build node lookup
node_map = {}
for el in data["elements"]:
    if el.get("type") == "node" and "lat" in el:
        node_map[el["id"]] = (el["lat"], el["lon"])

TARGET_IDS = {62095055, 378657301, 378657446}
TARGET_NAMES = ["varsity", "theater", "theatre", "amtrak", "station", "depot"]

for el in data.get("elements", []):
    tags = el.get("tags", {})
    name = tags.get("name", "")
    osm_id = el.get("id")
    if osm_id in TARGET_IDS or any(t in name.lower() for t in TARGET_NAMES):
        lat = el.get("lat")
        lon = el.get("lon")
        # For ways, compute centroid
        if el.get("type") == "way":
            lats, lons = [], []
            for nid in el.get("nodes", []):
                if nid in node_map:
                    nlat, nlon = node_map[nid]
                    lats.append(nlat)
                    lons.append(nlon)
            if lats:
                lat = sum(lats) / len(lats)
                lon = sum(lons) / len(lons)
        if lat is not None:
            mc_x, mc_z = geo_to_mc(lat, lon)
            print(f"id={osm_id} type={el['type']} name={name!r}")
            print(f"  lat={lat:.7f} lon={lon:.7f} -> MC({mc_x}, {mc_z})")
            print(f"  origin_x={mc_x - 16} origin_z={mc_z - 9}  (Amtrak offsets)")
            print(f"  origin_x={mc_x - 17} origin_z={mc_z - 17} (WaterTower offsets)")
