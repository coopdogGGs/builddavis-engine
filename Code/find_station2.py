"""Find the Amtrak station building in OSM data and compute MC coordinates."""
import json, math

R = 6_371_000.0

def lat_distance(lat1, lat2):
    d_lat = math.radians(lat2 - lat1)
    a = math.sin(d_lat/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def lon_distance(lat, lon1, lon2):
    d_lon = math.radians(lon2 - lon1)
    a = math.cos(math.radians(lat))**2 * math.sin(d_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

min_lat, min_lng = 38.5410, -121.7420
max_lat, max_lng = 38.5460, -121.7340

sfz = math.floor(lat_distance(min_lat, max_lat))
sfx = math.floor(lon_distance((min_lat+max_lat)/2, min_lng, max_lng))

print(f"scale_factor_x = {sfx}, scale_factor_z = {sfz}")

data = json.load(open(r"REDACTED_PATH\BuildDavis\poc10_amtrak\data\enriched_overpass.json"))
elems = data["elements"]

# Build node lookup
nodes = {}
for e in elems:
    if e["type"] == "node":
        nodes[e["id"]] = (e.get("lat", 0), e.get("lon", 0))

# Find buildings near station
for e in elems:
    if e.get("type") != "way":
        continue
    tags = e.get("tags", {})
    if not tags.get("building"):
        continue
    
    nids = e.get("nodes", [])
    coords = [nodes[n] for n in nids if n in nodes]
    if not coords:
        continue
    
    clat = sum(c[0] for c in coords) / len(coords)
    clon = sum(c[1] for c in coords) / len(coords)
    
    if abs(clat - 38.5435) < 0.001 and abs(clon + 121.7377) < 0.001:
        rel_x = (clon - min_lng) / (max_lng - min_lng)
        rel_z = 1.0 - (clat - min_lat) / (max_lat - min_lat)
        mc_x = int(rel_x * sfx)
        mc_z = int(rel_z * sfz)
        
        lats = [c[0] for c in coords]
        lons = [c[1] for c in coords]
        bw = int(lon_distance(clat, min(lons), max(lons)))
        bd = int(lat_distance(min(lats), max(lats)))
        
        bid = e["id"]
        name = tags.get("name", "unnamed")
        btype = tags.get("building", "?")
        print(f"Building {bid}: {name} ({btype})")
        print(f"  centroid: {clat:.6f}, {clon:.6f}")
        print(f"  MC: X={mc_x}, Z={mc_z}")
        print(f"  footprint: ~{bw}x{bd}m")
        print()
