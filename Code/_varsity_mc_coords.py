"""Compute Minecraft coordinates for Varsity Theatre using arnis CoordTransformer.

Uses the full-city Arnis World 1 bbox from metadata.json:
  lat 38.51-38.59, lon -121.78 - -121.69, MC 0-7826 x 0-8895
"""
import math, json

# --- Haversine helpers (from arnis pipeline) ---
R = 6_371_000.0  # Earth radius in meters

def haversine_lat(lat1, lat2):
    d = math.radians(lat2 - lat1)
    a = math.sin(d/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def haversine_lon(lat, lon1, lon2):
    d = math.radians(lon2 - lon1)
    a = math.cos(math.radians(lat))**2 * math.sin(d/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

class CoordTransformer:
    def __init__(self, bbox):
        self.min_lat, self.min_lon, self.max_lat, self.max_lon = bbox
        self.len_lat = self.max_lat - self.min_lat
        self.len_lon = self.max_lon - self.min_lon
        lat_m = haversine_lat(self.min_lat, self.max_lat)
        avg_lat = (self.min_lat + self.max_lat) / 2
        lon_m = haversine_lon(avg_lat, self.min_lon, self.max_lon)
        self.scale_z = math.floor(lat_m)
        self.scale_x = math.floor(lon_m)
        print(f"World size: {self.scale_x} x {self.scale_z} blocks (haversine)")
        print(f"  Metadata says: 7826 x 8895")

    def transform(self, lat, lon):
        rel_x = (lon - self.min_lon) / self.len_lon
        rel_z = 1.0 - (lat - self.min_lat) / self.len_lat
        return int(rel_x * self.scale_x), int(rel_z * self.scale_z)

# Full-city Arnis World 1 bbox (from world/Arnis World 1/metadata.json)
bbox = (38.51, -121.78, 38.59, -121.69)
ct = CoordTransformer(bbox)

# --- Load OSM data ---
with open("data/enriched_overpass.json", "r") as f:
    osm = json.load(f)

# Also load osm_raw.json for geometry (enriched may only have node IDs)
with open("data/osm_raw.json", "r") as f:
    osm_raw = json.load(f)

# Build node lookup from osm_raw
node_lookup = {}
for el in osm_raw.get("elements", []):
    if el.get("type") == "node":
        node_lookup[el["id"]] = (el["lat"], el["lon"])

# --- Verify against known placements ---
# Amtrak station building centroid (from fix_station_coords.py: way 62095055)
station_lat, station_lon = 38.543387, -121.737811
print(f"\n=== VERIFICATION: Amtrak Station (way 62095055) ===")
print(f"Station centroid: ({station_lat}, {station_lon})")
amtrak_mc = ct.transform(station_lat, station_lon)
print(f"  -> MC centroid: X={amtrak_mc[0]}, Z={amtrak_mc[1]}")
print(f"  Structure: 33w x 19d -> half = (16, 9)")
print(f"  Predicted placement: X={amtrak_mc[0]-16}, Z={amtrak_mc[1]-9}")
print(f"  Known placement:     X=3656, Z=5179")
print(f"  Delta: dX={amtrak_mc[0]-16 - 3656}, dZ={amtrak_mc[1]-9 - 5179}")

# --- Find Varsity Theatre ---
print(f"\n=== VARSITY THEATRE (way 45208396) ===")

# Get geometry from osm_raw first
varsity_raw = None
for el in osm_raw.get("elements", []):
    if el.get("type") == "way" and el.get("id") == 45208396:
        varsity_raw = el
        break

if varsity_raw:
    raw_node_ids = varsity_raw.get("nodes", [])
    raw_geom = varsity_raw.get("geometry", [])
    
    # Try geometry array first, fall back to node lookup
    if raw_geom:
        coords = [(g["lat"], g["lon"]) for g in raw_geom]
        print(f"Got {len(coords)} nodes from geometry array")
    elif raw_node_ids:
        coords = []
        for nid in raw_node_ids:
            if nid in node_lookup:
                coords.append(node_lookup[nid])
            else:
                print(f"  WARNING: node {nid} not in lookup!")
        print(f"Got {len(coords)} nodes from node ID lookup")
    else:
        coords = []
        print("No geometry found!")
    
    if coords:
        mc_coords = []
        for lat, lon in coords:
            mx, mz = ct.transform(lat, lon)
            mc_coords.append((mx, mz))
            print(f"  ({lat:.7f}, {lon:.7f}) -> MC ({mx}, {mz})")
        
        min_x = min(c[0] for c in mc_coords)
        max_x = max(c[0] for c in mc_coords)
        min_z = min(c[1] for c in mc_coords)
        max_z = max(c[1] for c in mc_coords)
        cx = (min_x + max_x) // 2
        cz = (min_z + max_z) // 2
        
        print(f"\nMC Bounding Box: X=[{min_x}, {max_x}], Z=[{min_z}, {max_z}]")
        print(f"MC Footprint Size: {max_x - min_x + 1} W x {max_z - min_z + 1} D blocks")
        print(f"MC Center: X={cx}, Z={cz}")
        
        # Recommended placement origin (SW corner = min_x, min_z)
        print(f"\nRecommended placement: X={min_x}, Y=49, Z={min_z}")
        print(f"  (this aligns with where arnis placed the building)")

# --- Find neighbors ---
print(f"\n=== NEIGHBORING BUILDINGS ===")
neighbor_ids = [45208395, 120379171, 45208330]
for el in osm_raw.get("elements", []):
    if el.get("type") != "way":
        continue
    eid = el["id"]
    # Check enriched for name/tags
    tags = {}
    for eel in osm.get("elements", []):
        if eel.get("type") == "way" and eel.get("id") == eid:
            tags = eel.get("tags", {})
            break
    if not tags:
        tags = el.get("tags", {})
    
    name = tags.get("name", "")
    if eid in neighbor_ids or "mishka" in name.lower():
        geom = el.get("geometry", [])
        node_ids = el.get("nodes", [])
        ncoords = []
        if geom:
            ncoords = [(g["lat"], g["lon"]) for g in geom]
        elif node_ids:
            for nid in node_ids:
                if nid in node_lookup:
                    ncoords.append(node_lookup[nid])
        
        if not ncoords:
            continue
        nmc = [ct.transform(lat, lon) for lat, lon in ncoords]
        nx1 = min(c[0] for c in nmc)
        nx2 = max(c[0] for c in nmc)
        nz1 = min(c[1] for c in nmc)
        nz2 = max(c[1] for c in nmc)
        label = name if name else f"way {eid}"
        btype = tags.get("building", "yes")
        print(f"  {label} ({btype}): MC X=[{nx1},{nx2}] Z=[{nz1},{nz2}] ({nx2-nx1+1}x{nz2-nz1+1})")
