import json
from collections import Counter

feats = json.load(open('REDACTED_PATH/BuildDavis/poc/data/fused_features.geojson'))['features']
buildings = [f['properties'] for f in feats if f.get('properties', {}).get('type') == 'building']

print(f'Total buildings: {len(buildings)}')
print()

# Height coverage
with_height_m = [b for b in buildings if b.get('height_m')]
with_height_blocks = [b for b in buildings if b.get('height_blocks')]
print(f'height_m populated:      {len(with_height_m)} / {len(buildings)} ({len(with_height_m)/len(buildings)*100:.0f}%)')
print(f'height_blocks populated: {len(with_height_blocks)} / {len(buildings)} ({len(with_height_blocks)/len(buildings)*100:.0f}%)')
print()

# Height values
if with_height_m:
    heights = [b['height_m'] for b in with_height_m]
    print(f'height_m range: {min(heights):.1f} to {max(heights):.1f}m')
    print(f'height_m avg:   {sum(heights)/len(heights):.1f}m')
print()

# Subtype breakdown
subtypes = Counter(b.get('subtype', 'none') for b in buildings)
print('Subtypes:')
for s, count in subtypes.most_common():
    print(f'  {s}: {count}')
print()

# mc_coords coverage
with_coords = [b for b in buildings if b.get('mc_coords_json')]
print(f'mc_coords_json present: {len(with_coords)} / {len(buildings)}')
print()

# Show a building WITH height data
print('=== Sample building WITH height_m ===')
for b in buildings:
    if b.get('height_m'):
        print(f"  name={b.get('name','?')}")
        print(f"  subtype={b.get('subtype','?')}")
        print(f"  height_m={b.get('height_m')}")
        print(f"  height_blocks={b.get('height_blocks')}")
        print(f"  floors={b.get('floors')}")
        print(f"  mc_coords_json (first 80 chars): {str(b.get('mc_coords_json',''))[:80]}")
        break

print()
print('=== Varsity Theatre ===')
for b in buildings:
    if 'varsity' in str(b.get('name', '')).lower():
        for k, v in b.items():
            if v not in (None, '', False, 0):
                print(f'  {k}: {v}')
        break
