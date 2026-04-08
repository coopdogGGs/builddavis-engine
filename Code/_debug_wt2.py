import os, re

base = os.path.join(os.environ['APPDATA'], '.minecraft', 'saves', 'BuildDavis',
                    'datapacks', 'builddavis', 'data', 'builddavis', 'function')

wt = open(os.path.join(base, 'place_water_tower.mcfunction')).read()
am = open(os.path.join(base, 'place_amtrak.mcfunction')).read()

# Extract all block IDs from setblock/fill commands
def get_blocks(text):
    blocks = set()
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('setblock '):
            parts = line.split()
            if len(parts) >= 5:
                blocks.add(parts[4])
        elif line.startswith('fill '):
            parts = line.split()
            if len(parts) >= 8:
                blocks.add(parts[7])
    return blocks

wt_blocks = get_blocks(wt)
am_blocks = get_blocks(am)

print(f"Water tower unique blocks ({len(wt_blocks)}):")
for b in sorted(wt_blocks):
    print(f"  {b}")

print(f"\nAmtrak unique blocks ({len(am_blocks)}):")
for b in sorted(am_blocks):
    print(f"  {b}")

print(f"\nBlocks in WT but not in AM:")
for b in sorted(wt_blocks - am_blocks):
    print(f"  {b}")

# Also check line count of each type
lines = wt.splitlines()
print(f"\nWT total lines: {len(lines)}")
setblock_count = sum(1 for l in lines if l.strip().startswith('setblock'))
fill_count = sum(1 for l in lines if l.strip().startswith('fill'))
comment_count = sum(1 for l in lines if l.strip().startswith('#'))
forceload_count = sum(1 for l in lines if l.strip().startswith('forceload'))
tellraw_count = sum(1 for l in lines if l.strip().startswith('tellraw'))
empty_count = sum(1 for l in lines if not l.strip())
other_count = len(lines) - setblock_count - fill_count - comment_count - forceload_count - tellraw_count - empty_count
print(f"  setblock: {setblock_count}")
print(f"  fill: {fill_count}")
print(f"  comment: {comment_count}")
print(f"  forceload: {forceload_count}")
print(f"  tellraw: {tellraw_count}")
print(f"  empty: {empty_count}")
print(f"  other: {other_count}")
if other_count > 0:
    for l in lines:
        s = l.strip()
        if s and not s.startswith(('#', 'setblock', 'fill', 'forceload', 'tellraw')):
            print(f"    OTHER: {s[:120]}")
