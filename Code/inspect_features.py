import json

feats = json.load(open('REDACTED_PATH/BuildDavis/poc/data/fused_features.geojson'))['features']
buildings = [f for f in feats if f.get('properties', {}).get('type') == 'building']

print(f'Total buildings: {len(buildings)}')
print()

# Show height coverage
with_height = [b for b in buildings if b['properties'].get('height_m')]
print(f'Buildings with height_m: {len(with_height)} / {len(buildings)}')
print()

# Show Varsity Theatre specifically
varsity = [b for b in buildings if 'varsity' in str(b.get('properties', {})).lower()]
if varsity:
    print('=== Varsity Theatre ===')
    print(json.dumps(varsity[0]['properties'], indent=2))
else:
    print('Varsity Theatre not found')
    print()
    print('=== First 3 buildings (sample) ===')
    for b in buildings[:3]:
        p = b['properties']
        print(f"  name={p.get('name','?')} subtype={p.get('subtype','?')} height_m={p.get('height_m','?')} height_blocks={p.get('height_blocks','?')} mc_coords_json={str(p.get('mc_coords_json','?'))[:60]}")
