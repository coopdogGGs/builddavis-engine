import json

blocks = json.load(open('REDACTED_PATH/BuildDavis/poc/data/blocks.json'))
xs = [b['x'] for b in blocks]
zs = [b['z'] for b in blocks]

print(f'Total blocks: {len(blocks)}')
print(f'X range: {min(xs)} to {max(xs)}')
print(f'Z range: {min(zs)} to {max(zs)}')
print(f'Negative X blocks: {sum(1 for x in xs if x < 0)}')
print(f'Negative Z blocks: {sum(1 for z in zs if z < 0)}')
print(f'Width needed: {max(xs) - min(xs)} blocks')
print(f'Depth needed: {max(zs) - min(zs)} blocks')
