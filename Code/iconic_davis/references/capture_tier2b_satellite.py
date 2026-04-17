#!/usr/bin/env python3
"""Capture Google Maps satellite screenshots for Tier 2 batch 2 (landmarks #43-47).

North Hall, South Hall, Hart Hall, King Hall, The Pavilion at ARC.
Saves to per-landmark folders as google_satellite.png.
"""

import pathlib, time
from playwright.sync_api import sync_playwright

BASE = pathlib.Path(__file__).parent

LANDMARKS = {
    "north_hall":    (38.5414, -121.7490, 19),  # UC Davis Quad, built 1908
    "south_hall":    (38.5410, -121.7490, 19),  # UC Davis Quad, built 1912
    "hart_hall":     (38.5405, -121.7486, 19),  # Near Quad, built 1928
    "king_hall":     (38.5394, -121.7462, 19),  # School of Law
    "pavilion_arc":  (38.5423, -121.7611, 19),  # ARC & Pavilion
}

HIDE_UI_CSS = """
.app-viewcard-strip, .scene-footer, .scene-footer-container,
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
div[jscontroller][class*="widget"],
.scene-footer *, #scene .scene-footer,
.app-bit-areapano, .minimap, #minimap, .zoom, #zoom,
.ml-promotion-no-thanks, .ml-promotion-container,
div[role="dialog"], .watermark-text, .rscontainer,
header, [role="banner"]
{ display: none !important; visibility: hidden !important;
  opacity: 0 !important; pointer-events: none !important; }
"""

def dismiss_consent(page):
    for sel in ['button:has-text("Accept all")', 'button:has-text("Reject all")',
                '[aria-label="Accept all"]', 'button:has-text("Got it")']:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1500):
                btn.click(); time.sleep(1); return
        except Exception:
            pass

def capture(page, name, lat, lon, zoom, dst):
    url = f"https://www.google.com/maps/@{lat},{lon},{zoom}z/data=!3m1!1e3"
    try:
        page.goto(url, wait_until="load", timeout=30000)
    except Exception as e:
        print(f"  FAIL {name}: {e}"); return False
    dismiss_consent(page)
    time.sleep(8)
    try: page.add_style_tag(content=HIDE_UI_CSS)
    except: pass
    time.sleep(1)
    try:
        page.screenshot(path=str(dst), type="png")
        print(f"  OK   {name} ({dst.stat().st_size//1024}KB) [z{zoom}]")
        return True
    except Exception as e:
        print(f"  FAIL {name}: {e}"); return False

def main():
    print("Capturing Google Maps satellite for Tier 2 batch 2 (#43-47)...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 1280}, locale="en-US",
            geolocation={"latitude": 38.5414, "longitude": -121.7490},
            permissions=["geolocation"])
        page = ctx.new_page()
        ok = fail = 0
        for name, (lat, lon, zoom) in LANDMARKS.items():
            dst = BASE / name / "google_satellite.png"
            dst.parent.mkdir(exist_ok=True)
            if capture(page, name, lat, lon, zoom, dst):
                ok += 1
            else:
                fail += 1
            time.sleep(2)
        browser.close()
    print(f"\nDone: {ok} OK, {fail} failed")

if __name__ == "__main__":
    main()
