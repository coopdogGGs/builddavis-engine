"""
provision_builder.py — One-command builder onboarding.

Usage:
    python provision_builder.py --username <mc_username> --zone <zone_id>

What it does:
  1. Looks up the zone bbox in data/zones.json
  2. Converts the bbox to Minecraft XZ coordinates (via world_config.py)
  3. Fires RCON commands:
       • whitelist add <username>
       • lp user <username> parent add builder
  4. Prints the WorldGuard /rg define command to run in-game (console can't set WE selection)
  5. Appends to data/credits.json (type: "builder")
  6. Updates data/zones.json: sets assignee + assigned_date

After running this script:
  • The player can join the server immediately.
  • Copy and run the printed /rg command in-game as admin.
  • Credits plaque is NOT updated automatically — run update_credits_plaque.py separately.

List available zones:
    python zone_status.py
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from world_config import (
    RCON_HOST, RCON_PORT, RCON_PASS,
    CREDITS_JSON, ZONES_JSON, GROUND_Y,
    geo_to_mc,
)
from rcon_cmd import rcon


def load_zones() -> list[dict]:
    if not ZONES_JSON.exists():
        print(f"[error] {ZONES_JSON} not found.")
        sys.exit(1)
    return json.loads(ZONES_JSON.read_text(encoding="utf-8"))


def find_zone(zones: list[dict], zone_id: str) -> dict | None:
    return next((z for z in zones if z["id"] == zone_id), None)


def zone_to_mc_region(zone: dict) -> tuple[int, int, int, int]:
    """
    Return (x1, z1, x2, z2) in Minecraft coordinates for a zone bbox.
    bbox = [min_lat, min_lon, max_lat, max_lon]
    """
    min_lat, min_lon, max_lat, max_lon = zone["bbox"]
    # Bottom-left corner (min lat = south, min lon = west)
    x1, z2 = geo_to_mc(min_lat, min_lon)
    # Top-right corner (max lat = north, max lon = east)
    x2, z1 = geo_to_mc(max_lat, max_lon)
    return min(x1, x2), min(z1, z2), max(x1, x2), max(z1, z2)


def already_credited(mc_username: str) -> bool:
    if not CREDITS_JSON.exists():
        return False
    credits = json.loads(CREDITS_JSON.read_text(encoding="utf-8"))
    return any(
        c.get("minecraft_username", "").lower() == mc_username.lower()
        and c.get("type") == "builder"
        for c in credits
    )


def append_credit(mc_username: str, zone_id: str) -> None:
    if not CREDITS_JSON.exists():
        CREDITS_JSON.write_text("[]", encoding="utf-8")
    credits = json.loads(CREDITS_JSON.read_text(encoding="utf-8"))
    credits.append({
        "minecraft_username": mc_username,
        "date_verified":      date.today().isoformat(),
        "type":               "builder",
        "zone":               zone_id,
    })
    CREDITS_JSON.write_text(
        json.dumps(credits, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def assign_zone(zones: list[dict], zone_id: str, mc_username: str) -> list[dict]:
    for z in zones:
        if z["id"] == zone_id:
            z["assignee"]      = mc_username
            z["assigned_date"] = date.today().isoformat()
    return zones


def save_zones(zones: list[dict]) -> None:
    ZONES_JSON.write_text(
        json.dumps(zones, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Provision a new BuildDavis builder (whitelist + permissions + zone assignment)."
    )
    parser.add_argument("--username", required=True, metavar="MC_USERNAME",
                        help="Minecraft username")
    parser.add_argument("--zone",     required=True, metavar="ZONE_ID",
                        help="Zone ID from zones.json (e.g. 'downtown'). Run zone_status.py to list.")
    args = parser.parse_args()

    username = args.username.strip()
    zone_id  = args.zone.strip()

    # ── Load and validate zone ─────────────────────────────────────────────
    zones = load_zones()
    zone  = find_zone(zones, zone_id)
    if zone is None:
        print(f"[error] Zone '{zone_id}' not found in zones.json.")
        print("        Available zones:", ", ".join(z["id"] for z in zones))
        sys.exit(1)

    if zone["assignee"] is not None:
        print(
            f"[warn]  Zone '{zone_id}' is already assigned to '{zone['assignee']}' "
            f"(since {zone['assigned_date']})."
        )
        confirm = input("Reassign anyway? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Cancelled.")
            sys.exit(0)

    # ── Compute MC region coordinates ──────────────────────────────────────
    x1, z1, x2, z2 = zone_to_mc_region(zone)
    y1, y2 = GROUND_Y - 5, GROUND_Y + 50   # generous vertical range

    # ── Fire RCON commands ─────────────────────────────────────────────────
    print(f"\nProvisioning '{username}' → zone '{zone_id}' ({zone['name']}) ...")
    print("-" * 60)
    rcon(RCON_HOST, RCON_PORT, RCON_PASS, [
        f"whitelist add {username}",
        f"lp user {username} parent add builder",
    ])

    # ── WorldGuard region — must be run in-game (WE selection required) ───
    rg_cmd = f"/rg define {zone_id} {username}"
    print()
    print("── WorldGuard region ─────────────────────────────────────────────")
    print(f"  Zone MC bounds:  X {x1}–{x2}, Y {y1}–{y2}, Z {z1}–{z2}")
    print()
    print("  Option A — In-game with WorldEdit wand:")
    print(f"    1. Stand in creative, use //wand")
    print(f"    2. Left-click pos1 at roughly  X={x1} Y={y1} Z={z1}")
    print(f"    3. Right-click pos2 at roughly X={x2} Y={y2} Z={z2}")
    print(f"    4. Run:  {rg_cmd}")
    print()
    print("  Option B — In-game commands (no wand):")
    print(f"    //pos1 {x1},{y1},{z1}")
    print(f"    //pos2 {x2},{y2},{z2}")
    print(f"    {rg_cmd}")
    print("-" * 60)

    # ── Update JSON files ──────────────────────────────────────────────────
    if already_credited(username):
        print(f"\n[skip] {username} already in credits.json as builder — skipping credit append.")
    else:
        append_credit(username, zone_id)
        print(f"\n[ok]   Added {username} to credits.json (type: builder, zone: {zone_id}).")

    zones = assign_zone(zones, zone_id, username)
    save_zones(zones)
    print(f"[ok]   zones.json updated: '{zone_id}' → {username}.")

    print()
    print(f"✓ Done — {username} whitelisted + builder role granted.")
    print("  Next: run the WorldGuard commands above, then:")
    print("        python Code\\update_credits_plaque.py")


if __name__ == "__main__":
    main()
