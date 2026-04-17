#!/usr/bin/env python3
"""Download Google Maps satellite screenshots for all Davis iconic landmarks.

Uses Playwright to automate Google Maps satellite view at high zoom,
capturing screenshots showing roof shapes, footprints, and surroundings.
Educational/research use only.
"""

import pathlib, time
from playwright.sync_api import sync_playwright

BASE = pathlib.Path(__file__).parent

# Landmark: (lat, lon, google_maps_zoom)
# z20 = 20ft scale (individual buildings, max detail)
# z19 = ~50ft scale (larger buildings/complexes)
# z18 = ~100ft scale (blocks/neighborhoods/parks)
# z17 = ~200ft scale (large areas)
# z16 = ~1000ft scale (infrastructure corridors)
LANDMARKS = {
    "aggie_stadium":            (38.5405, -121.7500, 18),
    "arboretum_waterway":       (38.5330, -121.7520, 18),
    "bike_barn":                (38.5410, -121.7490, 19),
    "central_park":             (38.5445, -121.7400, 19),
    "covell_bicycle_overpass":  (38.5580, -121.7500, 19),
    "davis_amtrak_station":     (38.5435, -121.7377, 20),
    "davis_food_coop":          (38.5460, -121.7395, 19),
    "davis_municipal_golf":     (38.5340, -121.7610, 18),
    "dresbach_mansion":         (38.5440, -121.7420, 19),
    "e_street_plaza":           (38.5445, -121.7385, 19),
    "egghead_sculptures":       (38.5385, -121.7490, 19),
    "el_macero_golf":           (38.5250, -121.7200, 17),
    "Farmers Market":           (38.5445, -121.7405, 19),
    "flying_carousel":          (38.5460, -121.7397, 19),
    "i80_richards_interchange": (38.5412, -121.7393, 17),
    "lake_spafford":            (38.5390, -121.7500, 19),
    "mace_ranch":               (38.5500, -121.7100, 18),
    "manetti_shrem_museum":     (38.5422, -121.7490, 19),
    "manor_pool":               (38.5485, -121.7425, 19),
    "memorial_union":           (38.5420, -121.7475, 19),
    "mondavi_center":           (38.5365, -121.7545, 19),
    "old_east_davis":           (38.5450, -121.7320, 18),
    "putah_creek":              (38.5310, -121.7530, 18),
    "richards_underpass":       (38.5412, -121.7393, 19),
    "shields_library":          (38.5395, -121.7490, 19),
    "slide_hill_park":          (38.5360, -121.7300, 19),
    "ssh_deathstar":            (38.5375, -121.7480, 19),
    "sycamore_park_skatepark":  (38.5320, -121.7370, 19),
    "the_silo":                 (38.5405, -121.7510, 19),
    "toad_tunnel":              (38.5443, -121.7270, 19),
    "uc_davis_water_tower":     (38.5380, -121.7510, 19),
    "unitrans_bus":             (38.5430, -121.7440, 19),
    "varsity_theater":          (38.5445, -121.7405, 19),
    "village_homes":            (38.5560, -121.7700, 18),
    "whole_earth_festival":     (38.5410, -121.7480, 19),
    "wildhorse_golf":           (38.5570, -121.7050, 18),
    "yolo_causeway":            (38.5630, -121.6300, 16),
}


def main():
    print(f"Capturing Google Maps satellite screenshots for {len(LANDMARKS)} landmarks...")
    print()

    done = 0
    skipped = 0
    failed = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1024, "height": 1024})

        for folder, (lat, lon, zoom) in sorted(LANDMARKS.items()):
            dst_dir = BASE / folder
            dst_dir.mkdir(exist_ok=True)
            dst = dst_dir / "aerial_google_satellite.png"

            if dst.exists():
                print(f"  SKIP {folder} (already exists)")
                skipped += 1
                continue

            url = f"https://www.google.com/maps/@{lat},{lon},{zoom}z/data=!3m1!1e3"

            try:
                page.goto(url, wait_until="load", timeout=20000)
                # Wait for satellite tiles to fully render
                time.sleep(7)
                page.screenshot(path=str(dst), type="png")
                kb = dst.stat().st_size // 1024
                print(f"  OK   {folder}/aerial_google_satellite.png ({kb}KB) [z{zoom}]")
                done += 1
            except Exception as e:
                print(f"  FAIL {folder}: {e}")
                failed += 1

        browser.close()

    print()
    print(f"Done: {done} downloaded, {skipped} skipped, {failed} failed")


if __name__ == "__main__":
    main()
