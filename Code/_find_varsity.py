# WARNING: Uses parse.py coordinate system (Amtrak station = MC origin 0,0).
# Outputs RELATIVE OFFSETS only — NOT absolute MC coords.
# DO NOT use these values for placement or /tp commands.
# For real placement coordinates use: python Code/mc_locate.py --name "..."

import json

with open("data/enriched_overpass.json", "r") as f:
    data = json.load(f)

target_nodes = None
for el in data["elements"]:
    if el.get("type") == "way" and el.get("tags", {}).get("name") == "Varsity Theatre":
        target_nodes = el["nodes"]
        print("Way:", el["id"], "Nodes:", target_nodes)
        print("Tags:", el["tags"])
        break

if target_nodes:
    lats = []
    lons = []
    for el in data["elements"]:
        if el.get("type") == "node" and el.get("id") in target_nodes:
            lat = el["lat"]
            lon = el["lon"]
            lats.append(lat)
            lons.append(lon)
            print(f"Node {el['id']}: lat={lat}, lon={lon}")
    
    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)
    print(f"\nCenter: lat={center_lat}, lon={center_lon}")
    
    # Convert to Minecraft coords using Davis origin
    # Origin: 38.5435, -121.7377 (Amtrak station)
    import math
    origin_lat = 38.5435
    origin_lon = -121.7377
    
    # 1 degree lat ≈ 111,320 meters
    # 1 degree lon ≈ 111,320 * cos(lat) meters
    # 1 block = 1 meter
    dz = (center_lat - origin_lat) * 111320
    dx = (center_lon - origin_lon) * 111320 * math.cos(math.radians(center_lat))
    
    print(f"\nMinecraft offset from origin: dx={dx:.0f}, dz={-dz:.0f}")
    print(f"Note: Z is inverted (north = -Z in MC)")
    
    # Footprint size in meters
    lat_span = (max(lats) - min(lats)) * 111320
    lon_span = (max(lons) - min(lons)) * 111320 * math.cos(math.radians(center_lat))
    print(f"\nFootprint: {lon_span:.1f}m x {lat_span:.1f}m (E-W x N-S)")
