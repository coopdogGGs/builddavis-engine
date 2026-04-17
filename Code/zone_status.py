"""
zone_status.py — Print a quick-view table of all BuildDavis zones.

Usage:
    python zone_status.py              # show all zones
    python zone_status.py --available  # show only unassigned zones
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from world_config import ZONES_JSON, geo_to_mc


def main():
    parser = argparse.ArgumentParser(description="Print BuildDavis zone status table.")
    parser.add_argument("--available", action="store_true",
                        help="Show only unassigned zones")
    args = parser.parse_args()

    if not ZONES_JSON.exists():
        print(f"[error] {ZONES_JSON} not found.")
        sys.exit(1)

    zones = json.loads(ZONES_JSON.read_text(encoding="utf-8"))
    if args.available:
        zones = [z for z in zones if z["assignee"] is None]

    if not zones:
        print("No zones found." if not args.available else "All zones are assigned.")
        sys.exit(0)

    # ── Column widths ──────────────────────────────────────────────────────
    col_id   = max(len(z["id"])           for z in zones)
    col_name = max(len(z["name"])         for z in zones)
    col_who  = max(len(z["assignee"] or "—") for z in zones)
    col_date = 10   # YYYY-MM-DD

    # Enforce minimums
    col_id   = max(col_id,   4)
    col_name = max(col_name, 4)
    col_who  = max(col_who,  8)

    header = (
        f"{'Zone ID':<{col_id}}  "
        f"{'Name':<{col_name}}  "
        f"{'Assignee':<{col_who}}  "
        f"{'Assigned':<{col_date}}  "
        f"MC bounds"
    )
    sep = "-" * len(header)

    # ── Header ─────────────────────────────────────────────────────────────
    print()
    print(header)
    print(sep)

    assigned_count = 0
    for z in zones:
        assignee = z["assignee"] or "—"
        assigned_date = z["assigned_date"] or "—"

        # Compute MC bounding box for quick reference
        min_lat, min_lon, max_lat, max_lon = z["bbox"]
        x1, z2 = geo_to_mc(min_lat, min_lon)
        x2, z1 = geo_to_mc(max_lat, max_lon)
        mc_bounds = f"X {min(x1,x2)}–{max(x1,x2)}, Z {min(z1,z2)}–{max(z1,z2)}"

        print(
            f"{z['id']:<{col_id}}  "
            f"{z['name']:<{col_name}}  "
            f"{assignee:<{col_who}}  "
            f"{assigned_date:<{col_date}}  "
            f"{mc_bounds}"
        )

        if z["assignee"]:
            assigned_count += 1

    print(sep)
    print(f"  {assigned_count} assigned / {len(zones) - assigned_count} available / {len(zones)} total")
    print()


if __name__ == "__main__":
    main()
