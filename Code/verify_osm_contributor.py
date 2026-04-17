"""
verify_osm_contributor.py — Verify an OSM contributor meets the credits threshold.

Usage:
    python verify_osm_contributor.py --osm <osm_username> --minecraft <mc_username>

What it does:
  1. Counts how many changesets <osm_username> has submitted inside the Davis bbox.
  2. If the count is >= OSM_MIN_CHANGESETS (10), appends their entry to data/credits.json.
  3. Prints a clear pass/fail result with the changeset count.

Run this after someone fills out the OSM contributor form.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

# Allow direct execution from any directory
sys.path.insert(0, str(Path(__file__).parent))
from world_config import CREDITS_JSON, OSM_DAVIS_BBOX, OSM_MIN_CHANGESETS

OSM_API = "https://api.openstreetmap.org/api/0.6"
USER_AGENT = "BuildDavis-Credits/1.0 (https://github.com/coopdogGGs/builddavis-engine)"


def count_changesets(osm_username: str) -> int:
    """
    Return the total number of changesets the user has submitted inside the Davis bbox.

    The OSM changesets endpoint returns up to 100 results per call; we page through
    until we get fewer than 100 (last page) or exceed the threshold.
    """
    total = 0
    max_id: int | None = None
    page_limit = 100

    while True:
        url = (
            f"{OSM_API}/changesets.json"
            f"?display_name={osm_username}"
            f"&bbox={OSM_DAVIS_BBOX}"
            f"&limit={page_limit}"
            f"&closed=true"
        )
        if max_id is not None:
            url += f"&max_changeset_id={max_id - 1}"

        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
        except URLError as exc:
            print(f"[error] OSM API request failed: {exc}")
            sys.exit(1)

        changesets = data.get("changesets", [])
        total += len(changesets)

        # If we already exceed the threshold, no need to page further
        if total >= OSM_MIN_CHANGESETS:
            break

        # Last page — stop paging
        if len(changesets) < page_limit:
            break

        # Prepare next page request: use lowest changeset id from this page
        max_id = min(c["id"] for c in changesets)

    return total


def already_credited(osm_username: str) -> bool:
    """Return True if this OSM user is already in credits.json."""
    if not CREDITS_JSON.exists():
        return False
    credits = json.loads(CREDITS_JSON.read_text(encoding="utf-8"))
    return any(
        c.get("osm_username", "").lower() == osm_username.lower()
        for c in credits
    )


def append_credit(osm_username: str, display_name: str) -> None:
    """Add the contributor to data/credits.json."""
    if not CREDITS_JSON.exists():
        CREDITS_JSON.write_text("[]", encoding="utf-8")
    credits = json.loads(CREDITS_JSON.read_text(encoding="utf-8"))
    credits.append({
        "name":          display_name,
        "osm_username":  osm_username,
        "date_verified": date.today().isoformat(),
        "type":          "osm"
    })
    CREDITS_JSON.write_text(
        json.dumps(credits, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Verify an OSM contributor and add them to the credits list."
    )
    parser.add_argument("--osm",  required=True, metavar="OSM_USERNAME",
                        help="OpenStreetMap username")
    parser.add_argument("--name", required=False, metavar="DISPLAY_NAME",
                        help="Display name for credits (defaults to OSM username)")
    args = parser.parse_args()

    osm_user  = args.osm.strip()
    mc_user   = (args.name or args.osm).strip()  # reuse variable name for compat

    # ── Already credited? ──────────────────────────────────────────────────
    if already_credited(osm_user):
        print(f"[skip] {osm_user} is already in credits.json — no action taken.")
        sys.exit(0)

    # ── Count changesets ───────────────────────────────────────────────────
    print(f"Checking OSM changesets for '{osm_user}' in Davis bbox ...")
    count = count_changesets(osm_user)

    if count >= OSM_MIN_CHANGESETS:
        append_credit(osm_user, mc_user)
        print(f"[PASS] {osm_user} has {count} changeset(s) — added to credits.json as '{mc_user}'.")
        print("       Run 'python Code\\update_credits_plaque.py' to refresh the in-world sign.")
    else:
        print(
            f"[FAIL] {osm_user} has only {count} changeset(s) in Davis "
            f"(need {OSM_MIN_CHANGESETS}). Not yet eligible."
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
