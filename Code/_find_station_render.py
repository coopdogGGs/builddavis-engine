# WARNING: Uses parse.py coordinate system (Amtrak station = MC origin 0,0).
# Outputs RELATIVE OFFSETS only — NOT absolute MC coords.
# DO NOT use these values for placement or /tp commands.
# For real placement coordinates use: python Code/mc_locate.py --name "..."

"""Check if Amtrak station building is in the rendered data."""
import json, math

with open("data/enriched_overpass.json") as f:
    data = json.load(f)

elems = data.get("elements", [])
nodes = {}
for e in elems:
    if e.get("type") == "node" and "lat" in e:
        nodes[e["id"]] = (e["lat"], e["lon"])

olat, olon = 38.5435, -121.7377

def to_mc(lat, lon):
    dx = (lon - olon) * math.cos(math.radians(olat)) * 111320
    dz = -(lat - olat) * 111320
    return int(dx), int(dz)

# Look for way 62095055 (Davis Station building from Chat15)
print("=== Looking for way 62095055 (Davis Station building) ===")
found = False
for e in elems:
    if e.get("id") == 62095055:
        tags = e.get("tags", {})
        etype = e.get("type", "?")
        name = tags.get("name", "")
        bld = tags.get("building", "")
        print(f"FOUND: type={etype} name={name} building={bld}")
        nids = e.get("nodes", [])
        lats = [nodes[n][0] for n in nids if n in nodes]
        lons = [nodes[n][1] for n in nids if n in nodes]
        if lats:
            x, z = to_mc(sum(lats)/len(lats), sum(lons)/len(lons))
            print(f"  /tp @s {x} 60 {z}")
        for k, v in tags.items():
            print(f"  {k}={v}")
        found = True
        break
if not found:
    print("NOT FOUND")

# Buildings within 100m of station
print("\n=== Buildings within 100m of station coords ===")
for e in elems:
    tags = e.get("tags", {})
    if not tags.get("building"):
        continue
    nids = e.get("nodes", [])
    lats = [nodes[n][0] for n in nids if n in nodes]
    lons = [nodes[n][1] for n in nids if n in nodes]
    if not lats:
        continue
    lat = sum(lats) / len(lats)
    lon = sum(lons) / len(lons)
    dist = math.sqrt(
        ((lat - 38.5435) * 111320) ** 2
        + ((lon - (-121.7377)) * math.cos(math.radians(38.5435)) * 111320) ** 2
    )
    if dist < 100:
        x, z = to_mc(lat, lon)
        name = tags.get("name", "unnamed")
        bld = tags["building"]
        lv = tags.get("building:levels", "?")
        print(f"  way {e['id']}: {name} building={bld} levels={lv} /tp @s {x} 60 {z}  (dist={dist:.0f}m)")
