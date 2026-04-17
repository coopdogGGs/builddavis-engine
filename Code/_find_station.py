# WARNING: Uses parse.py coordinate system (Amtrak station = MC origin 0,0).
# Outputs RELATIVE OFFSETS only — NOT absolute MC coords.
# DO NOT use these values for placement or /tp commands.
# For real placement coordinates use: python Code/mc_locate.py --name "..."

"""Find station-related elements in enriched data and raw overpass data."""
import json, sys

def search_file(path, label):
    print(f"\n=== {label}: {path} ===")
    with open(path, "r") as f:
        data = json.load(f)
    elements = data.get("elements", data) if isinstance(data, dict) else data
    print(f"Total elements: {len(elements)}")

    # Search by ID
    station_ids = [62095055, 410979525, 391700872]
    for sid in station_ids:
        found = [e for e in elements if e.get("id") == sid]
        if found:
            e = found[0]
            tags = e.get("tags", {})
            bld = tags.get("building", "N/A")
            nm = tags.get("name", "N/A")
            tp = e.get("type", "?")
            print(f"  FOUND id={sid} type={tp} building={bld} name={nm}")
        else:
            print(f"  MISSING id={sid}")

    # Search by name
    for e in elements:
        tags = e.get("tags", {})
        name = tags.get("name", "")
        if "davis" in name.lower() and any(w in name.lower() for w in ["station", "amtrak", "depot", "train"]):
            bld = tags.get("building", "N/A")
            tp = e.get("type", "?")
            print(f"  BY_NAME id={e['id']} type={tp} building={bld} name={name}")

    # Search for railway=station
    for e in elements:
        tags = e.get("tags", {})
        if tags.get("railway") == "station" or tags.get("public_transport") == "station":
            nm = tags.get("name", "N/A")
            tp = e.get("type", "?")
            bld = tags.get("building", "N/A")
            print(f"  RAILWAY_STATION id={e['id']} type={tp} building={bld} name={nm}")

search_file("data/enriched_overpass.json", "ENRICHED")
search_file("data/overpass_raw.json", "RAW OVERPASS")
