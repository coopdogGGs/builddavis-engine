"""
Overpass Tag Key Inventory — Full Davis Bbox
Reports all tag keys present in OSM for Davis, CA.
Highlights keys not currently in the fetch.py pipeline.
"""
import requests, json, collections, sys, os
from pathlib import Path

MIRRORS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
]

# Full Davis bbox
QUERY = """[out:json][timeout:120];
(
  node(38.520,-121.780,38.590,-121.700);
  way(38.520,-121.780,38.590,-121.700);
  relation(38.520,-121.780,38.590,-121.700);
);
out tags;
"""

OUT_DIR = Path("data/test_infra_fetch")
OUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE = OUT_DIR / "overpass_tags_inventory.json"

print("Querying Overpass for full Davis bbox tag inventory...")

# Use cache if fresh
data = None
if CACHE.exists():
    age_s = (Path(".").stat().st_mtime - CACHE.stat().st_mtime)
    # just always reload if running this script
    pass

for mirror in MIRRORS:
    try:
        print(f"  Trying {mirror}...")
        r = requests.post(mirror, data={"data": QUERY}, timeout=130,
                          headers={"User-Agent": "BuildDavis/1.0"})
        r.raise_for_status()
        data = r.json()
        n = len(data["elements"])
        print(f"  Got {n} elements from {mirror}")
        break
    except Exception as e:
        print(f"  Failed: {e}")

if not data:
    print("All mirrors failed")
    sys.exit(1)

CACHE.write_text(json.dumps(data))
print(f"  Saved to {CACHE}")

# ── Aggregate ────────────────────────────────────────────────────────────────
key_counts  = collections.Counter()
key_by_type = collections.defaultdict(set)   # key -> {node, way, relation}
key_values  = collections.defaultdict(collections.Counter)

for e in data["elements"]:
    etype = e["type"]
    for k, v in e.get("tags", {}).items():
        key_counts[k] += 1
        key_by_type[k].add(etype)
        key_values[k][v] += 1

# Keys our fetch.py pipeline currently queries
KNOWN_KEYS = {
    "building", "highway", "waterway", "railway", "amenity", "landuse",
    "natural", "leisure", "name", "tourism", "historic",
    "addr:housenumber", "addr:street",
    "surface", "layer", "barrier", "cycleway", "footway", "service",
    "oneway", "maxspeed", "power", "man_made", "emergency", "advertising",
    "public_transport", "shop", "park",
}

# Prefixes to suppress from gap report (noisy / not actionable)
SKIP_PREFIXES = ("tiger:", "addr:", "brand", "contact", "name", "source",
                 "note", "fixme", "check_date", "survey:", "gnis:", "ref:",
                 "is_in", "wikidata", "wikipedia",)

print()
print(f"=== FULL DAVIS TAG KEY INVENTORY  "
      f"({len(key_counts)} unique keys, {len(data['elements'])} elements) ===")
print(f"{'KEY':<38} {'COUNT':>7}  {'TYPES':<25}  TOP VALUES")
print("-" * 100)
for k, cnt in key_counts.most_common(80):
    types = "+".join(sorted(key_by_type[k]))
    top_v = ", ".join(f"{v}x{c}" for v, c in key_values[k].most_common(3))
    flag = ""
    if k not in KNOWN_KEYS:
        skip = any(k.startswith(p) for p in SKIP_PREFIXES)
        if not skip:
            flag = "  <-- PIPELINE GAP?"
    print(f"{k:<38} {cnt:>7}  {types:<25}  {top_v[:40]}{flag}")

# ── Gap report ────────────────────────────────────────────────────────────────
print()
print("=== PIPELINE GAPS — keys with 5+ elements not currently fetched ===")
print(f"{'KEY':<35} {'COUNT':>6}  TOP VALUES")
print("-" * 80)
gaps = [
    (k, cnt) for k, cnt in key_counts.most_common()
    if k not in KNOWN_KEYS
    and cnt >= 5
    and not any(k.startswith(p) for p in SKIP_PREFIXES)
]
for k, cnt in gaps:
    top_v = ", ".join(f"{v}x{c}" for v, c in key_values[k].most_common(3))
    print(f"  {cnt:>5}  {k:<33}  {top_v[:50]}")

print(f"\nTotal gap keys (5+ elements): {len(gaps)}")
