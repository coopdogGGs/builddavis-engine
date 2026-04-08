"""Check exact MC coordinates for station building nodes."""
import json, math

R = 6_371_000.0

def lat_distance(lat1, lat2):
    d = math.radians(lat2 - lat1)
    a = math.sin(d / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def lon_distance(lat, lon1, lon2):
    d = math.radians(lon2 - lon1)
    a = math.cos(math.radians(lat)) ** 2 * math.sin(d / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

min_lat, min_lng = 38.541, -121.742
max_lat, max_lng = 38.546, -121.734

sfx = math.floor(lon_distance((min_lat + max_lat) / 2, min_lng, max_lng))
sfz = math.floor(lat_distance(min_lat, max_lat))
print(f"sfx={sfx}, sfz={sfz}")

data = json.load(open(r"REDACTED_PATH\BuildDavis\poc10_amtrak\data\enriched_overpass.json"))
elems = data["elements"]
nodes = {}
for e in elems:
    if e["type"] == "node":
        nodes[e["id"]] = (e.get("lat", 0), e.get("lon", 0))

# Find station way 62095055
for e in elems:
    if e.get("type") == "way" and e.get("id") == 62095055:
        nids = e.get("nodes", [])
        tags = e.get("tags", {})
        print(f"Station way 62095055: {len(nids)} nodes")
        print(f"Tags: name={tags.get('name')}, building={tags.get('building')}")
        xs, zs = [], []
        for nid in nids:
            if nid in nodes:
                lat, lon = nodes[nid]
                rel_x = (lon - min_lng) / (max_lng - min_lng)
                rel_z = 1.0 - (lat - min_lat) / (max_lat - min_lat)
                x = int(rel_x * sfx)
                z = int(rel_z * sfz)
                xs.append(x)
                zs.append(z)
                print(f"  Node {nid}: ({lat:.7f}, {lon:.7f}) -> MC ({x}, {z})")
        print(f"MC bbox: X=[{min(xs)}, {max(xs)}], Z=[{min(zs)}, {max(zs)}]")
        print(f"Center: X={sum(xs)//len(xs)}, Z={sum(zs)//len(zs)}")
        print(f"Size: {max(xs)-min(xs)+1}x{max(zs)-min(zs)+1} blocks")
        break

# Also check Davis Tower (391700872) for another reference point
print()
for e in elems:
    if e.get("type") == "way" and e.get("id") == 391700872:
        nids = e.get("nodes", [])
        tags = e.get("tags", {})
        print(f"Davis Tower 391700872: {len(nids)} nodes")
        xs, zs = [], []
        for nid in nids:
            if nid in nodes:
                lat, lon = nodes[nid]
                rel_x = (lon - min_lng) / (max_lng - min_lng)
                rel_z = 1.0 - (lat - min_lat) / (max_lat - min_lat)
                x = int(rel_x * sfx)
                z = int(rel_z * sfz)
                xs.append(x)
                zs.append(z)
                print(f"  Node {nid}: ({lat:.7f}, {lon:.7f}) -> MC ({x}, {z})")
        print(f"MC bbox: X=[{min(xs)}, {max(xs)}], Z=[{min(zs)}, {max(zs)}]")
        break
