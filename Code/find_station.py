"""Find the Amtrak station in enriched_overpass.json and compute MC coordinates."""
import json

data = json.load(open("data/enriched_overpass.json"))
elems = data.get("elements", [])

# Search for station
for e in elems:
    tags = e.get("tags", {})
    name = tags.get("name", "").lower()
    btype = tags.get("building", "")
    rway = tags.get("railway", "")
    
    if any(k in name for k in ["amtrak", "train station", "davis station"]) or \
       btype == "train_station" or rway == "station":
        print(f"Found: id={e.get('id')}, name={tags.get('name','?')}, type={e.get('type')}")
        print(f"  building={btype}, railway={rway}")
        geom = e.get("geometry", [])
        if geom:
            lats = [n["lat"] for n in geom if "lat" in n]
            lons = [n["lon"] for n in geom if "lon" in n]
            if lats and lons:
                clat = sum(lats) / len(lats)
                clon = sum(lons) / len(lons)
                print(f"  center: lat={clat:.6f}, lon={clon:.6f}")
                
                # Convert to MC coords
                # Origin: 38.5435, -121.7377
                # 1 degree lat ~ 111,000m, 1 degree lon ~ 85,000m at this lat
                origin_lat, origin_lon = 38.5435, -121.7377
                dx = (clon - origin_lon) * 85000  # east-west = MC X
                dz = -(clat - origin_lat) * 111000  # north-south = MC Z (negative because MC Z goes south)
                print(f"  MC approx: X={dx:.0f}, Z={dz:.0f}")
        print()
