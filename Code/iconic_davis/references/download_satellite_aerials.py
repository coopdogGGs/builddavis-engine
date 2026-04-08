#!/usr/bin/env python3
"""Download satellite aerial images for all Davis iconic landmarks.

Uses ESRI World Imagery tiles (high-resolution satellite) composited
into a single overhead image per landmark. Educational/research use only.

Each landmark gets a ~640x640 satellite view at zoom 18-19 showing
roof shape, footprint, and immediate surroundings.
"""

import urllib.request, math, pathlib, io

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow required. Run: pip install Pillow")
    raise SystemExit(1)

BASE = pathlib.Path(__file__).parent
UA = "BuildDavis/1.0 (educational Minecraft research project)"

# ESRI World Imagery tile server (high-res satellite, free for educational use)
TILE_URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
TILE_SIZE = 256

# --- GPS coordinates and zoom for each landmark ---
# zoom 18 = ~1.2m/px (good for large structures)
# zoom 19 = ~0.6m/px (good for individual buildings)
LANDMARKS = {
    "aggie_stadium":          (38.5405, -121.7500, 18),
    "arboretum_waterway":     (38.5330, -121.7520, 18),
    "bike_barn":              (38.5410, -121.7490, 19),
    "central_park":           (38.5445, -121.7400, 19),
    "covell_bicycle_overpass":(38.5580, -121.7500, 19),
    "davis_amtrak_station":   (38.5435, -121.7377, 19),
    "davis_food_coop":        (38.5460, -121.7395, 19),
    "davis_municipal_golf":   (38.5340, -121.7610, 18),
    "dresbach_mansion":       (38.5440, -121.7420, 19),
    "e_street_plaza":         (38.5445, -121.7385, 19),
    "egghead_sculptures":     (38.5385, -121.7490, 19),
    "el_macero_golf":         (38.5250, -121.7200, 17),
    "Farmers Market":         (38.5445, -121.7405, 19),
    "flying_carousel":        (38.5445, -121.7395, 19),
    "i80_richards_interchange":(38.5412, -121.7393, 17),
    "lake_spafford":          (38.5390, -121.7500, 19),
    "mace_ranch":             (38.5500, -121.7100, 18),
    "manetti_shrem_museum":   (38.5422, -121.7490, 19),
    "manor_pool":             (38.5485, -121.7425, 19),
    "memorial_union":         (38.5420, -121.7475, 19),
    "mondavi_center":         (38.5365, -121.7545, 19),
    "old_east_davis":         (38.5450, -121.7320, 18),
    "putah_creek":            (38.5310, -121.7530, 18),
    "richards_underpass":     (38.5412, -121.7393, 19),
    "shields_library":        (38.5395, -121.7490, 19),
    "slide_hill_park":        (38.5360, -121.7300, 19),
    "ssh_deathstar":          (38.5375, -121.7480, 19),
    "sycamore_park_skatepark":(38.5320, -121.7370, 19),
    "the_silo":               (38.5405, -121.7510, 19),
    "toad_tunnel":            (38.5443, -121.7270, 19),
    "uc_davis_water_tower":   (38.5380, -121.7510, 19),
    "unitrans_bus":           (38.5430, -121.7440, 19),
    "varsity_theater":        (38.5445, -121.7405, 19),
    "village_homes":          (38.5560, -121.7700, 18),
    "whole_earth_festival":   (38.5410, -121.7480, 19),
    "wildhorse_golf":         (38.5570, -121.7050, 18),
    "yolo_causeway":          (38.5630, -121.6300, 16),
}


def lat_lon_to_tile(lat: float, lon: float, zoom: int) -> tuple:
    """Convert lat/lon to tile x, y coordinates."""
    lat_rad = math.radians(lat)
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def download_tile(z: int, x: int, y: int) -> Image.Image:
    """Download a single ESRI satellite tile."""
    url = TILE_URL.format(z=z, x=x, y=y)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    data = urllib.request.urlopen(req).read()
    return Image.open(io.BytesIO(data))


def get_satellite_image(lat: float, lon: float, zoom: int, grid: int = 3) -> Image.Image:
    """Download a grid of tiles centered on lat/lon and composite them."""
    cx, cy = lat_lon_to_tile(lat, lon, zoom)
    half = grid // 2
    img = Image.new("RGB", (grid * TILE_SIZE, grid * TILE_SIZE))
    for dy in range(-half, half + 1):
        for dx in range(-half, half + 1):
            tile = download_tile(zoom, cx + dx, cy + dy)
            px = (dx + half) * TILE_SIZE
            py = (dy + half) * TILE_SIZE
            img.paste(tile, (px, py))
    return img


def main():
    import time
    print("Downloading satellite aerial images for all landmarks...")
    print(f"Using ESRI World Imagery tiles (educational research use)")
    print()

    done = 0
    skipped = 0
    failed = 0

    for folder, (lat, lon, zoom) in sorted(LANDMARKS.items()):
        dst_dir = BASE / folder
        dst_dir.mkdir(exist_ok=True)
        dst = dst_dir / "aerial_satellite.jpg"

        if dst.exists():
            print(f"  SKIP {folder} (aerial_satellite.jpg exists)")
            skipped += 1
            continue

        try:
            img = get_satellite_image(lat, lon, zoom)
            img.save(str(dst), "JPEG", quality=90)
            kb = dst.stat().st_size // 1024
            print(f"  OK   {folder}/aerial_satellite.jpg ({kb}KB) [z{zoom}]")
            done += 1
            time.sleep(0.5)  # be polite to tile server
        except Exception as e:
            print(f"  FAIL {folder}: {e}")
            failed += 1

    print()
    print(f"Done: {done} downloaded, {skipped} skipped, {failed} failed")


if __name__ == "__main__":
    main()
