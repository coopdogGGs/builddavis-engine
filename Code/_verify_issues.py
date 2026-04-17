"""Quick verification: are GS-001 / colour / BL-001 actually issues?"""
import json

print("Loading enriched_overpass.json...")
with open("data/enriched_overpass.json") as f:
    data = json.load(f)

elements = data["elements"]
print(f"Total elements: {len(elements)}")

# --- ISSUE 2: Colour enrichment ---
buildings = [e for e in elements if e.get("tags", {}).get("building")]
print(f"\n=== COLOUR ENRICHMENT ===")
print(f"Buildings: {len(buildings)}")

clr = [e for e in buildings if e.get("tags", {}).get("building:colour")]
col = [e for e in buildings if e.get("tags", {}).get("building:color")]
mat = [e for e in buildings if e.get("tags", {}).get("building:material")]
wm  = [e for e in buildings if e.get("tags", {}).get("wall_material")]
print(f"  building:colour  = {len(clr)}")
print(f"  building:color   = {len(col)}")
print(f"  building:material= {len(mat)}")
print(f"  wall_material    = {len(wm)}")

if clr:
    print("\nSample building:colour values:")
    from collections import Counter
    vals = Counter(e["tags"]["building:colour"] for e in clr)
    for v, c in vals.most_common(15):
        print(f"  {v}: {c}")
elif wm:
    print("\nSample wall_material values:")
    from collections import Counter
    vals = Counter(e["tags"]["wall_material"] for e in wm)
    for v, c in vals.most_common(15):
        print(f"  {v}: {c}")
else:
    print("\n  >>> NO colour enrichment found — ISSUE CONFIRMED")

# --- ISSUE 1: Ground material (can't check from JSON, need engine flags) ---
print(f"\n=== GS-001 GROUND MATERIAL ===")
print("Arnis --land-cover defaults to true (confirmed in args.rs)")
print("Full-city run did NOT pass --land-cover=false")
print("ESA WorldCover classifies Davis urban area as LC_BUILT_UP → stone ground")
print("  >>> LIKELY STILL AN ISSUE — verify in-game")

# --- ISSUE 3: Trees in roads ---
print(f"\n=== BL-001 TREES IN ROADS ===")
trees = [e for e in elements if e.get("tags", {}).get("natural") == "tree"]
print(f"Trees in output: {len(trees)}")

# Check if roads exist for spatial comparison
roads = [e for e in elements if e.get("tags", {}).get("highway")]
print(f"Roads in output: {len(roads)}")
print("  >>> Need in-game visual check — can't verify from JSON alone")

# --- Summary ---
print(f"\n{'='*50}")
print("VERIFICATION SUMMARY:")
print(f"  GS-001 ground: --land-cover=true was active → CHECK IN-GAME")
print(f"  Colour:        {len(clr)} of {len(buildings)} buildings have building:colour")
pct = round(100*len(clr)/len(buildings),1) if buildings else 0
print(f"                 = {pct}% enriched")
print(f"  BL-001 trees:  {len(trees)} trees in data → CHECK IN-GAME")
