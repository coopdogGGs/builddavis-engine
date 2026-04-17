#!/usr/bin/env python3
"""Capture Google Maps satellite screenshots for Tier 2 batch 1 (landmarks #38-42).

Saves to per-landmark folders as google_satellite.png.
"""

import pathlib, time, sys
from playwright.sync_api import sync_playwright

BASE = pathlib.Path(__file__).parent

TIER2_LANDMARKS = {
    "historic_city_hall":       (38.5448, -121.7399, 19),  # 226 F Street
    "anderson_bank_building":   (38.5439, -121.7393, 19),  # 203 G Street / 719 2nd St
    "davis_community_church":   (38.5465, -121.7441, 19),  # 412 C Street
    "hattie_weber_museum":      (38.5461, -121.7448, 20),  # 445 C Street, NE corner Central Park
    "crocker_nuclear_lab":      (38.5352, -121.7536, 19),  # UC Davis, between Math Sci & Bainer
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
    print("Capturing Google Maps satellite for Tier 2 landmarks #38-42...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 1280}, locale="en-US",
            geolocation={"latitude": 38.5449, "longitude": -121.7405},
            permissions=["geolocation"])
        page = ctx.new_page()
        ok = fail = 0
        for name, (lat, lon, zoom) in TIER2_LANDMARKS.items():
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
