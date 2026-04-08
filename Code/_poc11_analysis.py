"""Analyze POC11: parks, greenbelts, trees, and large structures."""
import json, math

with open(r'REDACTED_PATH\BuildDavis\poc11_north_davis\data\enriched_overpass.json', 'r') as f:
    data = json.load(f)

park_ids = [25027935, 247490849, 23634487]

print("=== NAMED PARKS ===")
for el in data.get('elements', []):
    if el.get('id') in park_ids:
        tags = el.get('tags', {})
        geom = el.get('geometry', [])
        lats = [n['lat'] for n in geom if 'lat' in n]
        lngs = [n['lon'] for n in geom if 'lon' in n]
        if lats and lngs:
            dlat = (max(lats) - min(lats)) * 111319
            dlng = (max(lngs) - min(lngs)) * 87000
            name = tags.get('name', 'unnamed')
            clat = sum(lats) / len(lats)
            clng = sum(lngs) / len(lngs)
            print("  %s (way %d): %.0fm x %.0fm center=(%.5f,%.5f)" % (name, el['id'], dlng, dlat, clat, clng))

# Count all grass polygons
grass_ways = [e for e in data['elements'] if e.get('tags', {}).get('landuse') == 'grass']
print("\nGrass polygons: %d" % len(grass_ways))

# Count trees
all_trees = [e for e in data['elements'] if e.get('tags', {}).get('natural') == 'tree']
print("Total tree nodes: %d" % len(all_trees))

# Synthetic trees
synth = [e for e in data['elements'] if e.get('tags', {}).get('source') == 'synthetic_street_tree']
print("Synthetic street trees: %d" % len(synth))

# Check if any trees land inside park polygons
print("\n=== GREENBELT TREES CHECK ===")
for el in data.get('elements', []):
    if el.get('id') in park_ids:
        tags = el.get('tags', {})
        geom = el.get('geometry', [])
        lats = [n['lat'] for n in geom if 'lat' in n]
        lngs = [n['lon'] for n in geom if 'lon' in n]
        if lats and lngs:
            min_lat, max_lat = min(lats), max(lats)
            min_lng, max_lng = min(lngs), max(lngs)
            count = 0
            for t in all_trees:
                tlat = t.get('lat', 0)
                tlng = t.get('lon', 0)
                if min_lat <= tlat <= max_lat and min_lng <= tlng <= max_lng:
                    count += 1
            name = tags.get('name', 'unnamed')
            print("  %s: %d trees inside bbox" % (name, count))

# Image 2: Find the widest way or unusually wide structure near Ipanema
print("\n=== COVELL BLVD DETAILS ===")
for el in data.get('elements', []):
    tags = el.get('tags', {})
    hw = tags.get('highway', '')
    name = tags.get('name', '')
    if 'covell' in name.lower():
        lanes = tags.get('lanes', '?')
        bridge = tags.get('bridge', '')
        layer = tags.get('layer', '')
        print("  way %s: %s lanes=%s bridge=%s layer=%s" % (el['id'], name, lanes, bridge, layer))
