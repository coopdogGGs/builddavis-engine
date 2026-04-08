"""
Analyze the Varsity Theatre footprint and neighboring buildings from OSM data,
and figure out exactly how the arnis pipeline maps lat/lon -> MC coordinates.
"""
import json, math

with open("data/enriched_overpass.json", "r") as f:
    data = json.load(f)

# Build node lookup
nodes = {}
for el in data["elements"]:
    if el.get("type") == "node":
        nodes[el["id"]] = (el["lat"], el["lon"])

# Find Varsity Theatre way
varsity = None
for el in data["elements"]:
    if el.get("type") == "way" and el.get("tags", {}).get("name") == "Varsity Theatre":
        varsity = el
        break

print("=" * 70)
print("VARSITY THEATRE BUILDING POLYGON")
print("=" * 70)
print(f"OSM way id: {varsity['id']}")
print(f"Tags: {varsity['tags']}")
print(f"Nodes ({len(varsity['nodes'])}):")
for nid in varsity["nodes"]:
    lat, lon = nodes[nid]
    print(f"  {nid}: ({lat:.7f}, {lon:.7f})")

# Calculate footprint
lats = [nodes[nid][0] for nid in varsity["nodes"]]
lons = [nodes[nid][1] for nid in varsity["nodes"]]
center_lat = sum(lats) / len(lats)
center_lon = sum(lons) / len(lons)

# Meters
cos_lat = math.cos(math.radians(center_lat))
lat_span_m = (max(lats) - min(lats)) * 111320
lon_span_m = (max(lons) - min(lons)) * 111320 * cos_lat

print(f"\nBounding box:")
print(f"  Lat: {min(lats):.7f} to {max(lats):.7f}  ({lat_span_m:.1f}m N-S)")
print(f"  Lon: {min(lons):.7f} to {max(lons):.7f}  ({lon_span_m:.1f}m E-W)")
print(f"  Center: ({center_lat:.7f}, {center_lon:.7f})")

# Print polygon in relative meters (for understanding shape)
print(f"\nPolygon in meters (relative to SW corner):")
min_lat, min_lon = min(lats), min(lons)
for nid in varsity["nodes"]:
    lat, lon = nodes[nid]
    dx = (lon - min_lon) * 111320 * cos_lat
    dy = (lat - min_lat) * 111320
    print(f"  ({dx:.1f}, {dy:.1f})")

# ── Find neighboring buildings ──
print("\n" + "=" * 70)
print("NEIGHBORING BUILDINGS (within ~50m of Varsity Theatre center)")
print("=" * 70)

nearby = []
for el in data["elements"]:
    if el.get("type") != "way":
        continue
    tags = el.get("tags", {})
    if "building" not in tags:
        continue
    if el["id"] == varsity["id"]:
        continue
    
    # Get center of this building
    blats = []
    blons = []
    for nid in el["nodes"]:
        if nid in nodes:
            blats.append(nodes[nid][0])
            blons.append(nodes[nid][1])
    if not blats:
        continue
    
    bc_lat = sum(blats) / len(blats)
    bc_lon = sum(blons) / len(blons)
    
    dist_m = math.sqrt(
        ((bc_lat - center_lat) * 111320) ** 2 +
        ((bc_lon - center_lon) * 111320 * cos_lat) ** 2
    )
    
    if dist_m < 50:
        name = tags.get("name", "(unnamed)")
        btype = tags.get("building", "yes")
        ht = tags.get("height", "?")
        levels = tags.get("building:levels", "?")
        
        # Bounding box
        blat_span = (max(blats) - min(blats)) * 111320
        blon_span = (max(blons) - min(blons)) * 111320 * cos_lat
        
        nearby.append((dist_m, name, btype, ht, levels, blon_span, blat_span, bc_lat, bc_lon, el["id"]))

nearby.sort()
for dist, name, btype, ht, levels, ew, ns, blat, blon, wid in nearby:
    direction = ""
    dlat = blat - center_lat
    dlon = blon - center_lon
    if abs(dlat) > abs(dlon):
        direction = "N" if dlat > 0 else "S"
    else:
        direction = "E" if dlon > 0 else "W"
    
    print(f"\n  {name} (way {wid})")
    print(f"    Type: {btype}, Height: {ht}m, Levels: {levels}")
    print(f"    Size: {ew:.1f}m x {ns:.1f}m (E-W x N-S)")
    print(f"    Distance: {dist:.1f}m {direction} of Varsity")
    print(f"    Center: ({blat:.7f}, {blon:.7f})")

# ── Now figure out arnis coordinate mapping ──
print("\n" + "=" * 70)
print("COORDINATE MAPPING (checking how arnis maps coords)")
print("=" * 70)

# The amtrak station config says x=3656, y=49, z=5179
# Let's find the amtrak station in OSM and see its center lat/lon
amtrak = None
for el in data["elements"]:
    if el.get("type") == "way" and "Amtrak" in el.get("tags", {}).get("name", ""):
        amtrak = el
        print(f"Found Amtrak: way {el['id']} - {el['tags'].get('name')}")
        alats = [nodes[nid][0] for nid in el["nodes"] if nid in nodes]
        alons = [nodes[nid][1] for nid in el["nodes"] if nid in nodes]
        if alats:
            ac_lat = sum(alats) / len(alats)
            ac_lon = sum(alons) / len(alons)
            print(f"  Center: ({ac_lat:.7f}, {ac_lon:.7f})")
            print(f"  MC placement: x=3656, z=5179")
            
            # Known: amtrak center -> MC (3656, 5179)
            # If we can find another building with known MC coords...
            # Water tower config: x=2515, z=6096
            break

# Find water tower in OSM
for el in data["elements"]:
    if el.get("type") == "way" and "water" in el.get("tags", {}).get("name", "").lower() and "tower" in el.get("tags", {}).get("name", "").lower():
        print(f"\nFound: way {el['id']} - {el['tags'].get('name')}")
        wlats = [nodes[nid][0] for nid in el["nodes"] if nid in nodes]
        wlons = [nodes[nid][1] for nid in el["nodes"] if nid in nodes]
        if wlats:
            wc_lat = sum(wlats) / len(wlats)
            wc_lon = sum(wlons) / len(wlons)
            print(f"  Center: ({wc_lat:.7f}, {wc_lon:.7f})")
            print(f"  MC placement: x=2515, z=6096")

# Try to derive the mapping
# amtrak: lat=?, lon=? -> MC(3656, 5179)
# water_tower: lat=?, lon=? -> MC(2515, 6096)
# From these two points we can derive the linear mapping

print("\n--- Deriving coordinate mapping ---")
# We need the actual amtrak station building, not just any Amtrak reference
# Let me search more broadly
for el in data["elements"]:
    if el.get("type") != "way":
        continue
    tags = el.get("tags", {})
    name = tags.get("name", "")
    if "amtrak" in name.lower() or "train station" in name.lower() or "davis station" in name.lower():
        blats = [nodes[nid][0] for nid in el["nodes"] if nid in nodes]
        blons = [nodes[nid][1] for nid in el["nodes"] if nid in nodes]
        if blats:
            print(f"  Candidate: way {el['id']} '{name}' center=({sum(blats)/len(blats):.7f}, {sum(blons)/len(blons):.7f})")
