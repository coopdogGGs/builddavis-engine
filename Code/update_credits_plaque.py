"""
update_credits_plaque.py — Sync the in-world credits wall at City Hall.

Usage:
    python update_credits_plaque.py

What it does:
  1. Reads data/credits.json — the canonical contributor list
  2. Reads data/enriched_overpass.json — finds City Hall (OSM way 25400241)
  3. Computes City Hall's centroid + converts to MC XZ
  4. Places oak_wall_sign blocks on the north exterior wall facing north
  5. One sign per 3 names (4 lines: header + 3 names); auto-extends rightward

Signs are placed at:
  Y = GROUND_Y + 2 (eye level, approx 2m above ground)
  Z = city_hall_z - 1 (exterior north face)
  X = centroid_x, centroid_x+2, centroid_x+4 ... (one sign per group of names)
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from world_config import (
    RCON_HOST, RCON_PORT, RCON_PASS,
    CREDITS_JSON, ENRICHED_OSM, GROUND_Y,
    geo_to_mc,
)
from rcon_cmd import rcon

CITY_HALL_WAY_ID = 25400241
NAMES_PER_SIGN   = 3            # lines 2-4 on each sign (line 1 = header)
SIGN_SPACING     = 2            # blocks between consecutive signs
SIGN_Y_OFFSET    = 2            # y = GROUND_Y + this


def load_credits() -> list[str]:
    """Return list of Minecraft usernames from credits.json."""
    if not CREDITS_JSON.exists():
        return []
    data = json.loads(CREDITS_JSON.read_text(encoding="utf-8"))
    return [c["minecraft_username"] for c in data if c.get("minecraft_username")]


def find_city_hall_centroid(osm_path: Path) -> tuple[float, float]:
    """
    Stream-parse enriched_overpass.json to find City Hall centroid.
    Returns (lat, lon) of the centroid of way 25400241.
    """
    print("Scanning enriched_overpass.json for City Hall ...", flush=True)
    with open(osm_path, encoding="utf-8") as fh:
        data = json.load(fh)

    elements = data.get("elements", [])

    # Build a node lookup: id -> (lat, lon)
    node_coords: dict[int, tuple[float, float]] = {}
    city_hall_nodes: list[int] = []

    for elem in elements:
        if elem.get("type") == "node":
            node_coords[elem["id"]] = (elem["lat"], elem["lon"])
        elif elem.get("type") == "way" and elem.get("id") == CITY_HALL_WAY_ID:
            city_hall_nodes = elem.get("nodes", [])

    if not city_hall_nodes:
        raise ValueError(f"City Hall (way {CITY_HALL_WAY_ID}) not found in enriched_overpass.json.")

    lats, lons = [], []
    for nid in city_hall_nodes:
        if nid in node_coords:
            lat, lon = node_coords[nid]
            lats.append(lat)
            lons.append(lon)

    if not lats:
        raise ValueError("City Hall node coordinates not resolved.")

    return sum(lats) / len(lats), sum(lons) / len(lons)


def build_sign_nbt(header_line1: str, names: list[str]) -> str:
    """
    Build the NBT string for an oak_wall_sign with up to 3 names.
    Names list may have 1-3 entries; remaining lines are blank.
    """
    def j(text: str) -> str:
        # JSON text component — escape double quotes
        return json.dumps({"text": text})

    lines = [j(header_line1)] + [j(n) for n in names]
    # Pad to 4 lines
    while len(lines) < 4:
        lines.append(j(""))

    return (
        '{'
        f'Text1:{lines[0]},'
        f'Text2:{lines[1]},'
        f'Text3:{lines[2]},'
        f'Text4:{lines[3]}'
        '}'
    )


def main():
    # ── Load contributors ──────────────────────────────────────────────────
    names = load_credits()
    if not names:
        print("[info] credits.json is empty — nothing to place.")
        sys.exit(0)

    print(f"Found {len(names)} contributor(s): {', '.join(names)}")

    # ── Locate City Hall ───────────────────────────────────────────────────
    try:
        centroid_lat, centroid_lon = find_city_hall_centroid(ENRICHED_OSM)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[error] {exc}")
        sys.exit(1)

    cx, cz = geo_to_mc(centroid_lat, centroid_lon)
    sign_y  = GROUND_Y + SIGN_Y_OFFSET
    sign_z  = cz - 1   # one block north of the building face

    print(f"City Hall centroid: lat={centroid_lat:.6f}, lon={centroid_lon:.6f}")
    print(f"  → MC X={cx}, Z={cz}  |  Signs at Z={sign_z}, Y={sign_y}")

    # ── Build sign commands ────────────────────────────────────────────────
    cmds: list[str] = []

    # Group names into blocks of NAMES_PER_SIGN
    groups = [names[i:i + NAMES_PER_SIGN] for i in range(0, len(names), NAMES_PER_SIGN)]

    for idx, group in enumerate(groups):
        sign_x = cx + (idx * SIGN_SPACING)

        # First sign starts with "Special thanks" header; subsequent signs use "...continued"
        if idx == 0:
            header = "Special thanks"
            group_lines = group
        else:
            header = "for contributing:"
            group_lines = group

        nbt = build_sign_nbt(header, group_lines[:NAMES_PER_SIGN])

        # Place the sign block, then set NBT data
        block_cmd = (
            f"setblock {sign_x} {sign_y} {sign_z} "
            f"minecraft:oak_wall_sign[facing=north]{nbt}"
        )
        cmds.append(block_cmd)

    # ── Fire RCON ──────────────────────────────────────────────────────────
    print(f"\nSending {len(cmds)} setblock command(s) via RCON ...")
    rcon(RCON_HOST, RCON_PORT, RCON_PASS, cmds)
    print("\n✓ Credits plaque updated.")


if __name__ == "__main__":
    main()
