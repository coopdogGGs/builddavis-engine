import os

base = os.path.join(os.environ['APPDATA'], '.minecraft', 'saves', 'BuildDavis',
                    'datapacks', 'builddavis', 'data', 'builddavis', 'function')

wt = open(os.path.join(base, 'place_water_tower.mcfunction'), 'rb').read()
am = open(os.path.join(base, 'place_amtrak.mcfunction'), 'rb').read()

print(f"WT: {len(wt)} bytes, CR={wt.count(b'\\r')}, LF={wt.count(b'\\n')}")
print(f"AM: {len(am)} bytes, CR={am.count(b'\\r')}, LF={am.count(b'\\n')}")

# Check for non-ASCII
bad = [(i, b) for i, b in enumerate(wt) if b > 127]
if bad:
    for i, b in bad[:5]:
        print(f"Non-ASCII byte {b} at pos {i}")
else:
    print("No non-ASCII bytes in WT")

# Check for invalid block IDs
lines = wt.decode('utf-8').splitlines()
print(f"\nWT lines: {len(lines)}")
print(f"AM lines: {am.decode('utf-8').count(chr(10))}")

# Look for any lines that aren't comments, setblock, fill, or forceload
for i, line in enumerate(lines):
    line = line.strip()
    if not line:
        continue
    if line.startswith('#'):
        continue
    if line.startswith(('setblock ', 'fill ', 'forceload ')):
        continue
    print(f"Unusual line {i}: {line[:100]}")
