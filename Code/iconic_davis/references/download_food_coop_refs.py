"""
Download reference images for Davis Food Co-op (ICONIC-001, Landmark #21).

The Davis Food Co-op is a community-owned grocery store at 620 G Street in
downtown Davis. Founded in 1972, it is a beloved local institution with a
distinctive green/yellow facade and mural art. The current building (opened
2009) features modern architecture with large windows and a prominent
corner entrance.

Excellent Flickr coverage (200+ photos). No Wikimedia Commons images.

GPS: approximately 38.5445, -121.7418

Usage:
    python Code/iconic_davis/references/download_food_coop_refs.py

Downloads images into:
    Code/iconic_davis/references/davis_food_coop/
"""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

DEST = Path(__file__).parent / "davis_food_coop"
USER_AGENT = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

WIKIMEDIA = {}

# ── Flickr images (direct static URLs, _b = 1024px large) ──
FLICKR = {
    "01_exterior.jpg": (
        "https://live.staticflickr.com/8491/29395580640_477d7973a6_b.jpg",
        "https://www.flickr.com/photos/144876426@N03/29395580640/",
        "Davis Food Co-op exterior (Cultivate Food)"
    ),
    "02_storefront.jpg": (
        "https://live.staticflickr.com/4508/37025136473_dc08f65aff_b.jpg",
        "https://www.flickr.com/photos/144876426@N03/37025136473/",
        "Davis Food Co-op storefront (Cultivate Food)"
    ),
    "03_coop_building.jpg": (
        "https://live.staticflickr.com/65535/53689826879_616313c449_b.jpg",
        "https://www.flickr.com/photos/bulmanbartz/53689826879/",
        "Davis Co-op building view (rbulman)"
    ),
    "04_street_view.jpg": (
        "https://live.staticflickr.com/65535/53130410608_6e5176a01c_b.jpg",
        "https://www.flickr.com/photos/southerncalifornian/53130410608/",
        "Davis Food Co-op street view (So Cal Metro)"
    ),
    "05_facade.jpg": (
        "https://live.staticflickr.com/3061/2561017161_741641d23e_b.jpg",
        "https://www.flickr.com/photos/y-l/2561017161/",
        "Davis Food Co-op facade (Y. Lai)"
    ),
    "06_wide_view.jpg": (
        "https://live.staticflickr.com/3050/2942024102_35e21ae40c_b.jpg",
        "https://www.flickr.com/photos/gumprecht/2942024102/",
        "Davis Food Co-op wide view (Blake Gumprecht)"
    ),
    "07_signage.jpg": (
        "https://live.staticflickr.com/121/285197901_5b85b848a6_b.jpg",
        "https://www.flickr.com/photos/tspauld/285197901/",
        "Davis Food Co-Op signage 2006 (Tom Spaulding)"
    ),
    "08_visit.jpg": (
        "https://live.staticflickr.com/7272/8164258846_c170db41ae_b.jpg",
        "https://www.flickr.com/photos/greatbasinfoodcooperative/8164258846/",
        "Trip to Davis Food Co-op (Great Basin Food Co-op)"
    ),
}


def download_flickr(results):
    """Download from Flickr static CDN."""
    print("── Flickr ──")
    for local_name, (url, page, desc) in FLICKR.items():
        dest_path = DEST / local_name
        if dest_path.exists() and dest_path.stat().st_size > 10_000:
            size_kb = dest_path.stat().st_size / 1024
            print(f"  [{local_name}] SKIP (already {size_kb:.0f} KB)")
            results.append((local_name, "Flickr", page, True))
            continue

        print(f"  [{local_name}] {desc[:50]}...", end=" ", flush=True)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            dest_path.write_bytes(data)
            size_kb = len(data) / 1024
            print(f"OK  ({size_kb:.0f} KB)")
            results.append((local_name, "Flickr", page, True))
        except Exception as e:
            print(f"FAILED  ({e})")
            results.append((local_name, "Flickr", page, False))

        time.sleep(1)


def download_all():
    DEST.mkdir(parents=True, exist_ok=True)
    results = []

    download_flickr(results)

    # Write urls.txt for attribution
    urls_path = DEST / "urls.txt"
    with open(urls_path, "w", encoding="utf-8") as f:
        f.write("# Davis Food Co-op — Reference Image Sources\n")
        f.write("# Flickr only (educational reference use)\n")
        f.write("# Community-owned grocery, 620 G Street, Davis. Founded 1972.\n\n")
        for local_name, source, page, ok in results:
            status = "OK" if ok else "FAILED"
            f.write(f"{local_name}\n  Source: {source}\n  Page: {page}\n  Status: {status}\n\n")

    ok_count = sum(1 for *_, ok in results if ok)
    fail_count = len(results) - ok_count
    total = len(results)
    print(f"\nDone: {ok_count}/{total} downloaded to {DEST}")
    if fail_count:
        print(f"  {fail_count} failed — re-run to retry")
    print(f"\nTIP — Add your own Google Earth screenshot as 09_aerial_satellite.png")


if __name__ == "__main__":
    total = len(FLICKR)
    print(f"Downloading {total} reference images for Davis Food Co-op...\n")
    download_all()
