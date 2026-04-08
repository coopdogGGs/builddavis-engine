"""Quick script to find data density and station location."""
import json
from collections import Counter

data = json.load(open('data/arnis_input.json/enriched_overpass.json'))
elems = data['elements']
nodes = [e for e in elems if e['type'] == 'node']
ways  = [e for e in elems if e['type'] == 'way']

# Densest lat bands
lat_bands = Counter()
for n in nodes:
    lat_bands[round(n['lat'], 2)] += 1
print('Top lat bands:')
for band, cnt in lat_bands.most_common(10):
    print(f'  lat ~{band}: {cnt} nodes')

# Station way check
w62 = [e for e in elems if e.get('id') == 62095055]
print(f'\nWay 62095055 present: {len(w62)}')

# Build node map for centroid calc
nmap = {n['id']: n for n in nodes}
way_centroids = []
for w in ways:
    nids = w.get('nodes', [])
    wnodes = [nmap[nid] for nid in nids if nid in nmap]
    if wnodes:
        lat_avg = sum(n['lat'] for n in wnodes) / len(wnodes)
        lon_avg = sum(n['lon'] for n in wnodes) / len(wnodes)
        way_centroids.append((lat_avg, lon_avg, w))

# Find the densest cluster
print(f'\nTotal ways with resolved coords: {len(way_centroids)}')
if way_centroids:
    lats = [c[0] for c in way_centroids]
    lons = [c[1] for c in way_centroids]
    print(f'Way centroid lat range: {min(lats):.4f} to {max(lats):.4f}')
    print(f'Way centroid lon range: {min(lons):.4f} to {max(lons):.4f}')
    
    # Pick bbox that covers the actual data
    data_bbox = f'{min(lats)-.001:.4f},{min(lons)-.001:.4f},{max(lats)+.001:.4f},{max(lons)+.001:.4f}'
    print(f'\nData-fitting bbox: {data_bbox}')
    
    # Show a 2km x 2km bbox around center
    clat = (min(lats) + max(lats)) / 2
    clon = (min(lons) + max(lons)) / 2
    # ~0.009 deg lat = 1km, ~0.012 deg lon = 1km at this latitude
    small_bbox = f'{clat-0.009:.4f},{clon-0.012:.4f},{clat+0.009:.4f},{clon+0.012:.4f}'
    print(f'Center 2km bbox: {small_bbox}')
    
    # Count ways in small bbox
    in_small = sum(1 for la, lo, w in way_centroids 
                   if clat-0.009 <= la <= clat+0.009 and clon-0.012 <= lo <= clon+0.012)
    print(f'Ways in 2km center bbox: {in_small} / {len(way_centroids)}')
    
    # Show first 10 ways
    for lat_avg, lon_avg, w in way_centroids[:10]:
        tags = w.get('tags', {})
        desc = tags.get('building', '') or tags.get('highway', '') or tags.get('landuse', '') or tags.get('leisure', '')
        print(f'  Way {w["id"]}: lat={lat_avg:.4f} lon={lon_avg:.4f} => {desc} {tags.get("name", "")}')
