"""
Download reference images for UC Davis Arboretum Waterway
(ICONIC-001, Landmark #16).

Cement-lined original Putah Creek bed — smooth stone banks, weeping willows,
footbridges at each crossing. A Davis signature landscape feature.
At 38.5340, -121.7503.

Good Flickr coverage (UC Davis Arboretum official account + individuals).
Wikimedia has botanical images but few waterway landscape shots.

Usage:
    python Code/iconic_davis/references/download_arboretum_waterway_refs.py

Downloads images into:
    Code/iconic_davis/references/arboretum_waterway/
"""

import time
import urllib.request
from pathlib import Path

DEST = Path(__file__).parent / "arboretum_waterway"
USER_AGENT = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

# ── Flickr images (direct static URLs, _b = 1024px large) ──
FLICKR = {
    "01_waterway_detail.jpg": (
        "https://live.staticflickr.com/2449/3794029259_1101cfe3b6_b.jpg",
        "https://www.flickr.com/photos/calaggie/3794029259/",
        "Arboretum waterway detail (calaggie)"
    ),
    "02_stone_banks.jpg": (
        "https://live.staticflickr.com/5492/12121860336_37ed91e3ea_b.jpg",
        "https://www.flickr.com/photos/goodlifegarden/12121860336/",
        "Waterway with stone banks (UC Davis Arboretum)"
    ),
    "03_footbridge.jpg": (
        "https://live.staticflickr.com/4303/35485251813_b4f235f95b_b.jpg",
        "https://www.flickr.com/photos/goodlifegarden/35485251813/",
        "Footbridge crossing (UC Davis Arboretum)"
    ),
    "04_waterway_perspective.jpg": (
        "https://live.staticflickr.com/4299/35485252123_fdffc42310_b.jpg",
        "https://www.flickr.com/photos/goodlifegarden/35485252123/",
        "Waterway perspective view (UC Davis Arboretum)"
    ),
    "05_landscape.jpg": (
        "https://live.staticflickr.com/4318/36290463205_1f9f855469_b.jpg",
        "https://www.flickr.com/photos/goodlifegarden/36290463205/",
        "Landscape view (UC Davis Arboretum)"
    ),
    "06_willows.jpg": (
        "https://live.staticflickr.com/457/18204885569_1a2420fae9_b.jpg",
        "https://www.flickr.com/photos/ian_e_abbott/18204885569/",
        "Water with weeping willows (Ian Abbott)"
    ),
    "07_scenic.jpg": (
        "https://live.staticflickr.com/4280/35662170422_18b84f7d7a_b.jpg",
        "https://www.flickr.com/photos/dsh1492/35662170422/",
        "Scenic waterway view (David Heaphy)"
    ),
    "08_footbridge_detail.jpg": (
        "https://live.staticflickr.com/4264/35831497495_b0479e12f2_b.jpg",
        "https://www.flickr.com/photos/dsh1492/35831497495/",
        "Footbridge across Putah Creek detail (David Heaphy)"
    ),
    "09_water_wildlife.jpg": (
        "https://live.staticflickr.com/65535/47972758956_14d8718949_b.jpg",
        "https://www.flickr.com/photos/36618387@N06/47972758956/",
        "Putah Creek at Arboretum, water/wildlife (sdttds)"
    ),
    "10_pathway.jpg": (
        "https://live.staticflickr.com/1369/1111183552_b60f3fea51_b.jpg",
        "https://www.flickr.com/photos/disneyite/1111183552/",
        "Arboretum pathway view (Donna S)"
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
        f.write("# Arboretum Waterway — Reference Image Sources\n")
        f.write("# Flickr (educational reference use)\n")
        f.write("# Cement-lined Putah Creek bed, stone banks, willows, footbridges.\n\n")
        for local_name, source, page, ok in results:
            status = "OK" if ok else "FAILED"
            f.write(f"{local_name}\n  Source: {source}\n  Page: {page}\n  Status: {status}\n\n")

    ok_count = sum(1 for *_, ok in results if ok)
    fail_count = len(results) - ok_count
    total = len(results)
    print(f"\nDone: {ok_count}/{total} downloaded to {DEST}")
    if fail_count:
        print(f"  {fail_count} failed — re-run to retry")
    print(f"\nTIP — Add your own Google Earth screenshot as 11_aerial_satellite.png")


if __name__ == "__main__":
    total = len(FLICKR)
    print(f"Downloading {total} reference images for Arboretum Waterway...\n")
    download_all()
