"""
Download reference images for Central Park (ICONIC-001, Landmark #22).

Central Park is Davis's main downtown park located at 3rd & B/C Streets.
Features mature trees, gardens, walking paths, a rose garden, community
garden plots, playground, and public art. Hosts the Saturday Farmers Market.

Good Flickr coverage (163+ photos). No relevant Wikimedia (results return
NYC Central Park).

GPS: approximately 38.5460, -121.7405

Usage:
    python Code/iconic_davis/references/download_central_park_refs.py

Downloads images into:
    Code/iconic_davis/references/central_park/
"""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

DEST = Path(__file__).parent / "central_park"
USER_AGENT = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

WIKIMEDIA = {}

# ── Flickr images (direct static URLs, _b = 1024px large) ──
FLICKR = {
    "01_park_wide.jpg": (
        "https://live.staticflickr.com/5469/30219882241_79ae7005c3_b.jpg",
        "https://www.flickr.com/photos/148190849@N03/30219882241/",
        "Central Park wide view with lawn and trees (John Hines)"
    ),
    "02_gandhi_statue.jpg": (
        "https://live.staticflickr.com/5349/30131692913_645157c692_b.jpg",
        "https://www.flickr.com/photos/148190849@N03/30131692913/",
        "Mahatma Gandhi statue at Central Park Davis (John Hines)"
    ),
    "03_farmers_market_wide.jpg": (
        "https://live.staticflickr.com/3136/2585618846_d2d946839f_b.jpg",
        "https://www.flickr.com/photos/danbmay/2585618846/",
        "Central Park during Saturday Farmers Market — wide (Dan B May)"
    ),
    "04_farmers_market_tents.jpg": (
        "https://live.staticflickr.com/3063/2585618520_f481c323fa_b.jpg",
        "https://www.flickr.com/photos/danbmay/2585618520/",
        "Farmers Market tents and crowd (Dan B May)"
    ),
    "05_farmers_market_stalls.jpg": (
        "https://live.staticflickr.com/3012/2584784279_2db563532d_b.jpg",
        "https://www.flickr.com/photos/danbmay/2584784279/",
        "Central Park Farmers Market stalls (Dan B May)"
    ),
    "06_park_trees_lawn.jpg": (
        "https://live.staticflickr.com/5306/5587303790_0f649b6ee0_b.jpg",
        "https://www.flickr.com/photos/ktackett/5587303790/",
        "Davis Central Park — trees and lawn (Kim Tackett)"
    ),
    "07_garden_entrance.jpg": (
        "https://live.staticflickr.com/3643/3319988365_4ec67a04b7_b.jpg",
        "https://www.flickr.com/photos/calaggie/3319988365/",
        "Entry to Central Park Gardens — arch and plantings (calaggie)"
    ),
    "08_community_church_panorama.jpg": (
        "https://live.staticflickr.com/8655/16613446991_87a3483900_b.jpg",
        "https://www.flickr.com/photos/petescully/16613446991/",
        "Community Church + Central Park panorama (petescully)"
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

    urls_path = DEST / "urls.txt"
    with open(urls_path, "w", encoding="utf-8") as f:
        f.write("# Central Park Davis — Reference Image Sources\n")
        f.write("# Flickr only (educational reference use)\n")
        f.write("# Downtown Davis park at 3rd & B/C Streets. Gardens, paths, palms.\n\n")
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
    print(f"Downloading {total} reference images for Central Park Davis...\n")
    download_all()
