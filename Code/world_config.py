"""
world_config.py — Shared coordinate constants for BuildDavis scripts.

If you re-render the world with a different arnis bbox, update WORLD_BBOX here.
All scripts that convert lat/lon → MC XZ import from this module.

Derived from station reference:
  OSM centroid lat=38.543387, lon=-121.737811 → MC X=1929, Z=1290
  World size: 3043 × 2779 blocks
"""

import math
from pathlib import Path

# ── Coordinate configuration ────────────────────────────────────────────────

# Bounding box of the rendered Minecraft world (arnis --bbox input)
WORLD_BBOX = {
    "min_lat":  38.530,
    "min_lon": -121.760,
    "max_lat":  38.555,
    "max_lon": -121.725,
}

# Ground level Y in the Tour Server world
GROUND_Y = 49

# ── RCON configuration ───────────────────────────────────────────────────────

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / '.env')
RCON_HOST = os.environ.get('RCON_HOST', '127.0.0.1')
RCON_PORT = int(os.environ.get('RCON_PORT', '25575'))
RCON_PASS = os.environ['RCON_PASS']

# ── Data paths ───────────────────────────────────────────────────────────────

# Root of the repository
REPO_ROOT = Path(__file__).parent.parent
DATA_DIR  = REPO_ROOT / "data"

CREDITS_JSON = DATA_DIR / "credits.json"
ZONES_JSON   = DATA_DIR / "zones.json"

# enriched_overpass.json is large (>50 MB); scripts open it with json.load()
ENRICHED_OSM = DATA_DIR / "enriched_overpass.json"

# ── Coordinate conversion ────────────────────────────────────────────────────

_R = 6_371_000  # Earth radius in metres


def _haversine_dist(lat1, lon1, lat2, lon2) -> float:
    """Return distance in metres between two lat/lon points."""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return _R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _world_scale():
    """Return (sfx, sfz) — width and depth of the world in blocks/metres."""
    bb = WORLD_BBOX
    mid_lat = (bb["min_lat"] + bb["max_lat"]) / 2
    sfx = _haversine_dist(mid_lat, bb["min_lon"], mid_lat, bb["max_lon"])
    sfz = _haversine_dist(bb["min_lat"], bb["min_lon"], bb["max_lat"], bb["min_lon"])
    return sfx, sfz


def geo_to_mc(lat: float, lon: float) -> tuple[int, int]:
    """
    Convert a geographic coordinate to Minecraft XZ (ground level = GROUND_Y).

    Returns (mc_x, mc_z) as integers.
    """
    bb = WORLD_BBOX
    sfx, sfz = _world_scale()
    mc_x = int((lon - bb["min_lon"]) / (bb["max_lon"] - bb["min_lon"]) * sfx)
    mc_z = int((1.0 - (lat - bb["min_lat"]) / (bb["max_lat"] - bb["min_lat"])) * sfz)
    return mc_x, mc_z


# ── OSM query bbox (wider than world — covers all of Davis) ──────────────────

OSM_DAVIS_BBOX = "-121.80,38.51,-121.69,38.59"   # west,south,east,north
OSM_MIN_CHANGESETS = 10                            # minimum changesets in Davis bbox to earn credit
