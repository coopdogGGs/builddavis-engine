"""
Download reference images for E Street Plaza / Clepsydra (ICONIC-001, Landmark #20).

E Street Plaza is a small public plaza in downtown Davis at 2nd & E Street,
featuring the Clepsydra (water clock) sculpture. The plaza is a gathering
spot for the Saturday Farmers Market and features public art, brick pavers,
and seasonal decorations.

Limited online coverage — 4 Flickr photos (most results are Pete Scully
sketches). No Wikimedia images found. GAP: needs user photos of the water
clock sculpture itself.

GPS: approximately 38.5445, -121.7405

Usage:
    python Code/iconic_davis/references/download_e_street_plaza_refs.py

Downloads images into:
    Code/iconic_davis/references/e_street_plaza/
"""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

DEST = Path(__file__).parent / "e_street_plaza"
USER_AGENT = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

WIKIMEDIA = {}

# ── Flickr images (direct static URLs, _b = 1024px large) ──
FLICKR = {
    "01_plaza_overview.jpg": (
        "https://live.staticflickr.com/5061/5881906001_835a8f8681_b.jpg",
        "https://www.flickr.com/photos/brightflyer/5881906001/",
        "E Street Plaza overview (Janice L-H)"
    ),
    "02_plaza_view.jpg": (
        "https://live.staticflickr.com/65535/53378913943_c3a62e6e77_b.jpg",
        "https://www.flickr.com/photos/whsieh78/53378913943/",
        "E Street Plaza view (Wayne Hsieh)"
    ),
    "03_plaza_event.jpg": (
        "https://live.staticflickr.com/3206/3470539847_b8715a15eb_b.jpg",
        "https://www.flickr.com/photos/7537306@N08/3470539847/",
        "E Street Plaza event — Lone Twins (barefoot snowangel)"
    ),
    "04_plaza_scene.jpg": (
        "https://live.staticflickr.com/1399/5144751794_5faffcf284_b.jpg",
        "https://www.flickr.com/photos/basykes/5144751794/",
        "E Street Plaza scene (Bev Sykes)"
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
        f.write("# E Street Plaza / Clepsydra — Reference Image Sources\n")
        f.write("# Flickr only (educational reference use)\n")
        f.write("# Downtown Davis plaza at 2nd & E Street. Water clock sculpture.\n")
        f.write("# GAP: Only 4 images. Needs user photos of Clepsydra sculpture.\n\n")
        for local_name, source, page, ok in results:
            status = "OK" if ok else "FAILED"
            f.write(f"{local_name}\n  Source: {source}\n  Page: {page}\n  Status: {status}\n\n")

    ok_count = sum(1 for *_, ok in results if ok)
    fail_count = len(results) - ok_count
    total = len(results)
    print(f"\nDone: {ok_count}/{total} downloaded to {DEST}")
    if fail_count:
        print(f"  {fail_count} failed — re-run to retry")
    print(f"\nGAP: Only {ok_count} images — needs user photos of Clepsydra water clock")


if __name__ == "__main__":
    total = len(FLICKR)
    print(f"Downloading {total} reference images for E Street Plaza...\n")
    download_all()
