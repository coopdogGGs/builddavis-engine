#!/usr/bin/env python3
"""Capture Google Maps satellite screenshots for all Davis iconic landmarks.

Saves to _satellite_review/ staging folder for manual review before
moving to per-landmark reference folders. Educational/research use only.

Usage:
    python capture_satellite_review.py                # capture all
    python capture_satellite_review.py aggie_stadium  # capture one
    python capture_satellite_review.py --batch 1      # capture batch 1 (items 1-10)
    python capture_satellite_review.py --batch 2      # capture batch 2 (items 11-20)
    python capture_satellite_review.py --batch 3      # capture batch 3 (items 21-30)
    python capture_satellite_review.py --batch 4      # capture batch 4 (items 31-37)
"""

import pathlib, time, sys
from playwright.sync_api import sync_playwright

BASE = pathlib.Path(__file__).parent
REVIEW_DIR = BASE / "_satellite_review"

# ============================================================================
# GPS COORDINATES — Verified from Wikipedia, OSM Nominatim, and known addresses
# Format: (latitude, longitude, google_maps_zoom)
#
# Zoom guide:
#   z20 = ~20ft   (max detail, individual small buildings)
#   z19 = ~100ft  (individual buildings/structures)
#   z18 = ~200ft  (building complexes, parks, neighborhoods)
#   z17 = ~0.25mi (large campuses, golf courses)
#   z16 = ~0.5mi  (infrastructure corridors)
#
# Source key:
#   [W] = Wikipedia verified
#   [N] = OSM Nominatim verified
#   [A] = Address geocoded
#   [E] = Estimated from campus/city maps
# ============================================================================
LANDMARKS = {
    "aggie_stadium":            (38.5365, -121.7628, 18),  # [W] UC Davis Health Stadium
    "arboretum_waterway":       (38.5320, -121.7510, 18),  # [E] UC Davis Arboretum central
    "bike_barn":                (38.5393, -121.7477, 19),  # [E] Near Silo, Bioletti Way
    "central_park":             (38.5454, -121.7446, 19),  # [N] Downtown Davis civic park
    "covell_bicycle_overpass":  (38.5581, -121.7502, 19),  # [E] Bike overpass over Covell Blvd
    "davis_amtrak_station":     (38.5434, -121.7378, 20),  # [N] 840 2nd St, Mission Revival depot
    "davis_food_coop":          (38.5496, -121.7398, 19),  # [N] 620 G Street
    "davis_municipal_golf":     (38.5331, -121.7587, 18),  # [E] Fairway Dr, south Davis
    "dresbach_mansion":         (38.5432, -121.7409, 19),  # [A] 604 2nd Street
    "e_street_plaza":           (38.5437, -121.7389, 19),  # [E] E St & 2nd St, Clepsydra clock
    "egghead_sculptures":       (38.5366, -121.7493, 19),  # [E] Near Mrak Hall, campus core
    "el_macero_golf":           (38.5440, -121.6891, 17),  # [N] El Macero Country Club
    "Farmers Market":           (38.5454, -121.7446, 19),  # [N] Central Park (same location)
    "flying_carousel":          (38.5452, -121.7440, 19),  # [E] In Central Park
    "i80_richards_interchange": (38.5390, -121.7420, 17),  # [E] I-80 x Richards Blvd overpass
    "lake_spafford":            (38.5375, -121.7508, 19),  # [E] Near Mrak Hall, campus
    "mace_ranch":               (38.5569, -121.7100, 18),  # [N] Mace Ranch Community Park
    "manetti_shrem_museum":     (38.5335, -121.7478, 19),  # [W] UC Davis art museum + canopy
    "manor_pool":               (38.5606, -121.7174, 19),  # [A] 1525 Tulip Lane, Manor area
    "memorial_union":           (38.5422, -121.7478, 19),  # [E] 1 Shields Ave, student center
    "mondavi_center":           (38.5344, -121.7488, 19),  # [W] Performing arts, SW campus
    "old_east_davis":           (38.5440, -121.7330, 18),  # [E] Historic neighborhood, L St area
    "putah_creek":              (38.5290, -121.7520, 18),  # [E] Creek corridor south of campus
    "richards_underpass":       (38.5448, -121.7418, 19),  # [E] Railroad underpass, Color Study mural
    "shields_library":          (38.5397, -121.7492, 19),  # [W] Peter J. Shields Library
    "slide_hill_park":          (38.5606, -121.7164, 19),  # [N] Slide Hill Park, east Davis
    "ssh_deathstar":            (38.5370, -121.7493, 19),  # [E] Social Sciences & Humanities bldg
    "sycamore_park_skatepark":  (38.5544, -121.7670, 19),  # [N] Sycamore Park, west Davis
    "the_silo":                 (38.5390, -121.7500, 19),  # [E] Historic dairy barn, campus
    "toad_tunnel":              (38.5443, -121.7270, 19),  # [E] Pole Line Rd / I-80 overpass
    "uc_davis_water_tower":     (38.5385, -121.7510, 19),  # [E] Iconic elevated tank, campus
    "unitrans_bus":             (38.5406, -121.7445, 19),  # [E] Unitrans depot, Hutchison Dr
    "varsity_theater":          (38.5431, -121.7403, 19),  # [N] 616 2nd St, downtown
    "village_homes":            (38.5475, -121.7805, 18),  # [W] Solar planned community, W Davis
    "whole_earth_festival":     (38.5420, -121.7490, 19),  # [E] UC Davis Quad
    "wildhorse_golf":           (38.5714, -121.7209, 18),  # [N] 2323 Rockwell Dr
    "yolo_causeway":            (38.5635, -121.6384, 16),  # [W] I-80 bridge over Yolo Bypass
}

# CSS to hide Google Maps UI overlays for clean satellite screenshots
HIDE_UI_CSS = """
/* Hide all Google Maps UI elements for clean satellite capture */
.app-viewcard-strip,
.scene-footer, .scene-footer-container,
#omnibox-container, .omnibox-container, #searchbox-container,
.widget-zoom, .widget-minimap, .widget-streetview,
.widget-settings-button, .widget-settings,
.gm-bundled-control, .gm-style-cc, .gmnoprint,
.app-bottom-content-anchor, .app-horizontal-widget,
.id-omnibox-container, .id-content-container,
.vasquette, .scene-action-bar,
.watermark, .google-maps-link,
button[jsaction], [data-tooltip],
.section-layout, .noprint,
div[class*="searchbox"], div[class*="directions"],
.widget-pane, .widget-pane-toggle-button,
#assistive-chips, .assistive-chips,
.app-viewcard-strip, #runway-expand-button,
div[jscontroller][class*="widget"],
.scene-footer *, #scene .scene-footer,
.app-bit-areapano,
.minimap, #minimap,
.zoom, #zoom,
.ml-promotion-no-thanks, .ml-promotion-container,
div[role="dialog"],
.watermark-text, .rscontainer,
header, [role="banner"]
{
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
}
"""


def dismiss_consent(page):
    """Try to dismiss Google consent / cookie dialogs."""
    selectors = [
        'button:has-text("Accept all")',
        'button:has-text("Accept")',
        'button:has-text("I agree")',
        'button:has-text("Reject all")',
        'form[action*="consent"] button:first-of-type',
        '[aria-label="Accept all"]',
        'button:has-text("Got it")',
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1500):
                btn.click()
                time.sleep(1)
                return True
        except Exception:
            pass
    return False


def capture_landmark(page, name, lat, lon, zoom, dst):
    """Capture a single landmark satellite screenshot."""
    url = f"https://www.google.com/maps/@{lat},{lon},{zoom}z/data=!3m1!1e3"

    try:
        page.goto(url, wait_until="load", timeout=30000)
    except Exception as e:
        print(f"  FAIL {name}: page load error: {e}")
        return False

    # Dismiss any consent dialogs
    dismiss_consent(page)

    # Wait for satellite tiles to fully render
    time.sleep(8)

    # Inject CSS to hide all UI overlays
    try:
        page.add_style_tag(content=HIDE_UI_CSS)
    except Exception:
        pass

    time.sleep(1)

    # Take screenshot
    try:
        page.screenshot(path=str(dst), type="png")
        kb = dst.stat().st_size // 1024
        print(f"  OK   {name} ({kb}KB) [z{zoom}] @ {lat},{lon}")
        return True
    except Exception as e:
        print(f"  FAIL {name}: screenshot error: {e}")
        return False


def get_batch(batch_num):
    """Get landmarks for a specific batch (1-4)."""
    sorted_names = sorted(LANDMARKS.keys())
    batch_size = 10
    start = (batch_num - 1) * batch_size
    end = start + batch_size
    return sorted_names[start:end]


def main():
    REVIEW_DIR.mkdir(exist_ok=True)

    # Parse arguments
    specific = None
    batch = None
    args = sys.argv[1:]

    if args:
        if args[0] == "--batch" and len(args) > 1:
            batch = int(args[1])
            names = get_batch(batch)
            print(f"Batch {batch}: {len(names)} landmarks")
        else:
            specific = args[0]
            if specific not in LANDMARKS:
                print(f"Unknown landmark: {specific}")
                print(f"Available: {', '.join(sorted(LANDMARKS.keys()))}")
                return
            names = [specific]
    else:
        names = sorted(LANDMARKS.keys())

    total = len(names)
    print(f"Capturing Google Maps satellite screenshots for {total} landmarks...")
    print(f"Output: {REVIEW_DIR}/")
    print()

    done = skipped = failed = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 1280},
            locale="en-US",
            geolocation={"latitude": 38.5449, "longitude": -121.7405},
            permissions=["geolocation"],
        )
        page = context.new_page()

        for i, name in enumerate(names, 1):
            lat, lon, zoom = LANDMARKS[name]
            dst = REVIEW_DIR / f"{name}_z{zoom}.png"

            if dst.exists() and not specific:
                print(f"  SKIP {name} (already exists)")
                skipped += 1
                continue

            print(f"[{i}/{total}] {name}...", end="", flush=True)

            if capture_landmark(page, name, lat, lon, zoom, dst):
                done += 1
            else:
                failed += 1

            # Brief pause between captures
            if i < total:
                time.sleep(2)

        browser.close()

    print()
    print(f"Done: {done} captured, {skipped} skipped, {failed} failed")
    print(f"Review screenshots in: {REVIEW_DIR}/")


if __name__ == "__main__":
    main()
