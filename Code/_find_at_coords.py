# WARNING: Uses parse.py coordinate system (Amtrak station = MC origin 0,0).
# Outputs RELATIVE OFFSETS only — NOT absolute MC coords.
# DO NOT use these values for placement or /tp commands.
# For real placement coordinates use: python Code/mc_locate.py --name "..."

"""Find what's at MC coordinates 615, 963 in POC11."""
import json, math

with open(r'REDACTED_PATH\BuildDavis\poc11_north_davis\data\enriched_overpass.json', 'r') as f:
    data = json.load(f)

# Convert MC to lat/lng (Arnis coordinate system)
# bbox: S=38.560 W=-121.755 N=38.572 E=-121.738
# Build area: ~1479 x 1335 blocks
x_mc, z_mc = 615, 963
# Arnis coordinate transform (haversine-based)
min_lat, max_lat = 38.560, 38.572
min_lng, max_lng = -121.755, -121.738
len_lat = max_lat - min_lat
len_lng = max_lng - min_lng
scale_x, scale_z = 1478, 1334
rel_x = x_mc / scale_x
rel_z = z_mc / scale_z
lng = min_lng + rel_x * len_lng
lat = min_lat + (1.0 - rel_z) * len_lat

print("Target: MC (%d, %d) = lat %.5f, lng %.5f" % (x_mc, z_mc, lat, lng))
print()

# Find nearest buildings and ways
def dist_ll(lat1, lng1, lat2, lng2):
    dlat = (lat2 - lat1) * 111319
    dlng = (lng2 - lng1) * 87000
    return math.sqrt(dlat*dlat + dlng*dlng)

print("=== NEAREST BUILDINGS (within 50m) ===")
hits = []
for el in data.get('elements', []):
    tags = el.get('tags', {})
    if not tags.get('building'):
        continue
    geom = el.get('geometry', [])
    if not geom:
        continue
    lats = [n['lat'] for n in geom if 'lat' in n]
    lngs = [n['lon'] for n in geom if 'lon' in n]
    if not lats:
        continue
    clat = sum(lats) / len(lats)
    clng = sum(lngs) / len(lngs)
    d = dist_ll(lat, lng, clat, clng)
    if d < 150:
        hits.append((d, el))

hits.sort(key=lambda x: x[0])
for d, el in hits[:15]:
    tags = el.get('tags', {})
    geom = el.get('geometry', [])
    lats = [n['lat'] for n in geom if 'lat' in n]
    lngs = [n['lon'] for n in geom if 'lon' in n]
    dlat_m = (max(lats) - min(lats)) * 111319
    dlng_m = (max(lngs) - min(lngs)) * 87000
    print("  %dm away: %s %s building=%s name=%s h=%s levels=%s size=%.0fx%.0fm" % (
        int(d), el['type'], el['id'],
        tags.get('building', ''), tags.get('name', ''),
        tags.get('height', '?'), tags.get('building:levels', '?'),
        dlng_m, dlat_m))

print()
print("=== NEAREST WAYS (non-building, within 50m) ===")
way_hits = []
for el in data.get('elements', []):
    tags = el.get('tags', {})
    if tags.get('building'):
        continue
    if el.get('type') != 'way':
        continue
    geom = el.get('geometry', [])
    if not geom:
        # Use nodes
        continue
    lats = [n.get('lat', 0) for n in geom if n.get('lat')]
    lngs = [n.get('lon', 0) for n in geom if n.get('lon')]
    if not lats:
        continue
    clat = sum(lats) / len(lats)
    clng = sum(lngs) / len(lngs)
    d = dist_ll(lat, lng, clat, clng)
    if d < 150:
        way_hits.append((d, el))

way_hits.sort(key=lambda x: x[0])
for d, el in way_hits[:15]:
    tags = el.get('tags', {})
    keys = ', '.join('%s=%s' % (k, v) for k, v in tags.items() if k not in ('source',))
    print("  %dm away: way %s: %s" % (int(d), el['id'], keys))
