"""
mc_locate.py — Canonical tool for finding where a building goes in the MC world.

ALWAYS use this (or stage.py --live --osm-id) to get placement coordinates.
DO NOT use _find_*.py scripts for placement — they output relative offsets only.

Usage:
  python Code/mc_locate.py --name "Varsity Theatre"
  python Code/mc_locate.py --osm-id 45208396
  python Code/mc_locate.py --name "Davis Amtrak Station" --tp
  python Code/mc_locate.py --osm-id 45208396 --tp --y 52

Examples:
  # Find where Varsity Theatre goes, just print coords
  python Code/mc_locate.py --name "Varsity Theatre"

  # Find AND teleport player to the site
  python Code/mc_locate.py --osm-id 45208396 --tp

  # Look up the Amtrak station (should match place_amtrak.mcfunction first block ~X=1823)
  python Code/mc_locate.py --name "Davis Amtrak"
"""

import argparse
import sys
import os

# Allow running from repo root or Code/ directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from deploy_iconic import geo_to_mc, locate_osm_feature
from server_mgr import rcon_cmd


def find_by_name(name: str) -> tuple[int, float, float]:
    """Search enriched_overpass.json for an OSM way matching name (case-insensitive).

    Returns (osm_id, lat, lon) of the first match.
    Raises ValueError if no match found.
    """
    import json
    from pathlib import Path

    data_dir = Path(__file__).parent.parent / "data"
    eo_path = data_dir / "enriched_overpass.json"

    if not eo_path.exists():
        raise FileNotFoundError(f"enriched_overpass.json not found at {eo_path}")

    data = json.loads(eo_path.read_text(encoding="utf-8"))

    # Build node lookup (same as locate_osm_feature)
    node_map = {}
    for el in data["elements"]:
        if el.get("type") == "node" and "lat" in el:
            node_map[el["id"]] = (el["lat"], el["lon"])

    name_lower = name.lower()
    matches = []

    for el in data["elements"]:
        if el.get("type") != "way":
            continue
        tags = el.get("tags", {})
        el_name = tags.get("name", "")
        if name_lower in el_name.lower():
            # Compute centroid
            lats, lons = [], []
            for nid in el.get("nodes", []):
                if nid in node_map:
                    lat, lon = node_map[nid]
                    lats.append(lat)
                    lons.append(lon)
            if lats:
                matches.append((el["id"], sum(lats) / len(lats), sum(lons) / len(lons), el_name))

    if not matches:
        raise ValueError(
            f"No OSM way found matching '{name}'.\n"
            "Try a shorter search term, or use --osm-id directly."
        )

    if len(matches) > 1:
        print(f"[mc_locate] Multiple matches for '{name}':")
        for osm_id, lat, lon, el_name in matches:
            x, z = geo_to_mc(lat, lon)
            print(f"  OSM {osm_id}: '{el_name}' → MC X={x}, Z={z}")
        print(f"[mc_locate] Using first match: OSM {matches[0][0]}")

    osm_id, lat, lon, _ = matches[0]
    return osm_id, lat, lon


def main():
    parser = argparse.ArgumentParser(
        description="Find the Minecraft coordinates for a building by name or OSM ID."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--name", metavar="NAME",
                       help="OSM name to search (case-insensitive substring match)")
    group.add_argument("--osm-id", type=int, metavar="ID",
                       help="OSM way ID (exact)")
    parser.add_argument("--tp", action="store_true",
                        help="Teleport player to the location via RCON")
    parser.add_argument("--y", type=int, default=80,
                        help="Y coordinate for teleport (default: 80 — above terrain for a clear view)")
    args = parser.parse_args()

    # ── Locate the feature ────────────────────────────────────────────────────
    try:
        if args.osm_id:
            lat, lon = locate_osm_feature(args.osm_id)
            osm_id = args.osm_id
        else:
            osm_id, lat, lon = find_by_name(args.name)
    except (FileNotFoundError, ValueError) as e:
        print(f"[mc_locate] ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    x, z = geo_to_mc(lat, lon)

    print(f"[mc_locate] OSM way {osm_id}")
    print(f"[mc_locate] Geo:  lat={lat:.6f}, lon={lon:.6f}")
    print(f"[mc_locate] MC:   X={x}, Z={z}  (Y={args.y} for TP)")

    # ── Teleport player ───────────────────────────────────────────────────────
    if args.tp:
        cmd = f"tp @a[limit=1] {x} {args.y} {z}"
        print(f"[mc_locate] Sending RCON: {cmd}")
        try:
            resp = rcon_cmd(cmd)
            print(f"[mc_locate] Server: {resp}")
        except Exception as e:
            print(f"[mc_locate] RCON error: {e}", file=sys.stderr)
            print("[mc_locate] Is the local server running? Try: python Code/server_mgr.py status")
            sys.exit(1)


if __name__ == "__main__":
    main()
