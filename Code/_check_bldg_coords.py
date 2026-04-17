"""Quick diagnostic: check building coordinates in enriched_overpass.json."""
import json

d = json.load(open("data/north_davis/enriched_overpass.json"))
elems = d["elements"]
bldgs = [e for e in elems if e.get("type") == "way" and "building" in e.get("tags", {})]
nodes_map = {e["id"]: e for e in elems if e.get("type") == "node"}

bbox = [38.560, -121.755, 38.572, -121.738]
lat_min, lon_min, lat_max, lon_max = bbox

# Compute MC coords the same way Arnis does (simple linear transform)
# scale_factor_x = 1.0 / (lon_max - lon_min) * world_width_approx
# But we just want relative positions in the world

print(f"Bbox: lat {lat_min}-{lat_max}, lon {lon_min}-{lon_max}")
print(f"Total buildings: {len(bldgs)}")

# Check spatial distribution across the bbox
lat_bins = [0] * 10
lon_bins = [0] * 10
outside = 0

for b in bldgs:
    hnodes = [nodes_map[nid] for nid in b["nodes"] if nid in nodes_map]
    if not hnodes:
        continue
    clat = sum(n["lat"] for n in hnodes) / len(hnodes)
    clon = sum(n["lon"] for n in hnodes) / len(hnodes)
    
    if not (lat_min <= clat <= lat_max and lon_min <= clon <= lon_max):
        outside += 1
        continue
    
    lat_idx = min(9, int((clat - lat_min) / (lat_max - lat_min) * 10))
    lon_idx = min(9, int((clon - lon_min) / (lon_max - lon_min) * 10))
    lat_bins[lat_idx] += 1
    lon_bins[lon_idx] += 1

print(f"\nOutside bbox: {outside}")
print(f"Lat distribution (S→N): {lat_bins}")
print(f"Lon distribution (W→E): {lon_bins}")

# Show a few sample houses with their footprint sizes
print("\nSample houses:")
houses = [b for b in bldgs if b["tags"].get("building") in ("house", "yes", "residential")]
for h in houses[:5]:
    hnodes = [nodes_map[nid] for nid in h["nodes"] if nid in nodes_map]
    lats = [n["lat"] for n in hnodes]
    lons = [n["lon"] for n in hnodes]
    dlat = max(lats) - min(lats)
    dlon = max(lons) - min(lons)
    # Rough size in meters
    h_m = dlat * 111000
    w_m = dlon * 111000 * 0.77  # cos(38.5°) ≈ 0.77
    print(f"  id={h['id']} type={h['tags']['building']} "
          f"size={w_m:.1f}x{h_m:.1f}m nodes={len(hnodes)} "
          f"lat={sum(lats)/len(lats):.6f} lon={sum(lons)/len(lons):.6f}")
