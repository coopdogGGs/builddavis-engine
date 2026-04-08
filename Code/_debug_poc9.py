"""Quick debug: inspect POC9 enriched data for park/landuse/colour issues."""
import json
from collections import Counter

data = json.load(open(r"REDACTED_PATH\BuildDavis\poc9_covell\data\enriched_overpass.json"))
els = data["elements"]

print("=== NAMED LEISURE / LANDUSE AREAS ===")
for e in els:
    if e.get("type") != "way":
        continue
    tags = e.get("tags", {})
    name = tags.get("name", "")
    if not name:
        continue
    leisure = tags.get("leisure", "")
    landuse = tags.get("landuse", "")
    natural = tags.get("natural", "")
    if leisure or landuse or natural:
        nodes = len(e.get("nodes", []))
        surface = tags.get("surface", "")
        print(f"  {leisure} {landuse} {natural} surface={surface} name={name} nodes={nodes}")

print("\n=== LARGE UNNAMED AREAS (>20 nodes) ===")
for e in els:
    if e.get("type") != "way":
        continue
    tags = e.get("tags", {})
    name = tags.get("name", "")
    if name:
        continue
    leisure = tags.get("leisure", "")
    landuse = tags.get("landuse", "")
    natural = tags.get("natural", "")
    sport = tags.get("sport", "")
    src = tags.get("source", "")
    if (leisure and leisure != "garden") or landuse or natural:
        nodes = len(e.get("nodes", []))
        if nodes > 20:
            surface = tags.get("surface", "")
            print(f"  leisure={leisure} landuse={landuse} natural={natural} sport={sport} surface={surface} nodes={nodes} src={src}")

print("\n=== BUILDING COLOUR DISTRIBUTION ===")
colours = Counter()
for e in els:
    if e.get("type") != "way":
        continue
    tags = e.get("tags", {})
    if tags.get("building"):
        col = tags.get("building:colour", "(none)")
        colours[col] += 1

for col, count in colours.most_common(20):
    print(f"  {col}: {count}")
total_with = sum(v for k, v in colours.items() if k != "(none)")
print(f"  Total with colour: {total_with}")
print(f"  Total without: {colours.get('(none)', 0)}")
print(f"  Unique colours: {len([k for k in colours if k != '(none)'])}")
