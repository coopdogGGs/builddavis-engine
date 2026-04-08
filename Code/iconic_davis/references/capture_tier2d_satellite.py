#!/usr/bin/env python3
"""Capture Google Maps satellite screenshots for Tier 2D landmarks #52-56.

Mrak Hall, Davis Senior High, Sudwerk Brewery,
Nugget Markets, Vet Med Teaching Hospital.
Saves to per-landmark folders as google_satellite.png.
"""

import pathlib, time
from playwright.sync_api import sync_playwright

BASE = pathlib.Path(__file__).parent

LANDMARKS = {
    "mrak_hall":                (38.5382, -121.7494, 19),  # UC Davis admin, built 1966
    "davis_senior_high":        (38.5497, -121.7451, 18),  # 315 W 14th St at Oak
    "sudwerk_brewery":          (38.5561, -121.7251, 19),  # 2001 2nd St, under Pole Line
    "nugget_markets":           (38.5631, -121.7283, 18),  # 1414 E Covell Blvd, flagship
    "vet_med_teaching_hospital":(38.5328, -121.7633, 18),  # UC Davis Vet Med complex
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
div[class*="watermark"], span[class*="google"],
.app-viewcard-strip, .section-hero-header-title,
div[class*="bottom"], div[id*="footer"],
.scene-footer-container, #watermark,
a[href*="google.com/intl"], .scene-default-footer,
div[class*="consent"], div[id*="consent"],
div[class*="cookie"], div[id*="cookie"]
{ display: none !important; visibility: hidden !important; }
"""


def capture():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 1280},
            locale="en-US",
        )
        page = ctx.new_page()

        for name, (lat, lon, zoom) in LANDMARKS.items():
            dest = BASE / name / "google_satellite.png"
            url = (
                f"https://www.google.com/maps/@{lat},{lon},{zoom}z"
                "/data=!3m1!1e3"
            )
            print(f"[{name}] navigating …")
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)

            # dismiss consent dialog if present
            try:
                accept_btn = page.locator(
                    "button:has-text('Accept all'), "
                    "form[action*='consent'] button"
                ).first
                accept_btn.click(timeout=4000)
                time.sleep(1)
            except Exception:
                pass

            # inject CSS to hide chrome
            page.add_style_tag(content=HIDE_UI_CSS)
            # wait for satellite tiles
            time.sleep(8)
            page.add_style_tag(content=HIDE_UI_CSS)
            time.sleep(1)

            page.screenshot(path=str(dest))
            print(f"  -> {dest}")

        browser.close()
    print("Done — captured", len(LANDMARKS), "satellites")


if __name__ == "__main__":
    capture()
