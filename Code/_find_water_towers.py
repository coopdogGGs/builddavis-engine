# WARNING: Uses parse.py coordinate system (Amtrak station = MC origin 0,0).
# Outputs RELATIVE OFFSETS only — NOT absolute MC coords.
# DO NOT use these values for placement or /tp commands.
# For real placement coordinates use: python Code/mc_locate.py --name "..."

"""Find all water towers in OSM data and compute Minecraft coordinates."""
import json, math

data = json.load(open("data/osm_raw.json"))
bbox = (38.510, -121.780, 38.590, -121.690)
min_lat, min_lon, max_lat, max_lon = bbox
scale_x = math.floor(abs(max_lon - min_lon) * 111319 * math.cos(math.radians((min_lat + max_lat) / 2)))
scale_z = math.floor(abs(max_lat - min_lat) * 111319)

for el in data["elements"]:
    tags = el.get("tags", {})
    if tags.get("man_made") == "water_tower":
        lat, lon = el["lat"], el["lon"]
        rx = (lon - min_lon) / (max_lon - min_lon)
        rz = 1.0 - (lat - min_lat) / (max_lat - min_lat)
        x = int(rx * scale_x)
        z = int(rz * scale_z)
        op = tags.get("operator", "?")
        print(f"ID={el['id']}  lat={lat} lon={lon}  MC X={x} Z={z}  operator={op}")
