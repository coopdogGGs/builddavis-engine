"""
Download reference images for Richards Underpass / Color Study Mural
(ICONIC-001, Landmark #7).

The Richards Boulevard Underpass passes beneath the Union Pacific railroad
tracks in downtown Davis. In 2021, artist Ben Volta completed "Color Study
for Cyclists," a vibrant geometric mural covering the underpass walls —
now one of Davis's most photographed landmarks.

Limited Flickr coverage for the mural specifically. Includes sketches
and train context shots. User should add own photos/Google Earth screenshots.

Usage:
    python Code/iconic_davis/references/download_richards_underpass_refs.py

Downloads images into:
    Code/iconic_davis/references/richards_underpass/
"""

import time
import urllib.request
from pathlib import Path

DEST = Path(__file__).parent / "richards_underpass"
USER_AGENT = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

# ── Flickr images (direct static URLs, _b = 1024px large) ──
FLICKR = {
    "01_underpass_sketch.jpg": (
        "https://live.staticflickr.com/2851/33673948275_2e3fe12657_b.jpg",
        "https://www.flickr.com/photos/petescully/33673948275/",
        "Richards underpass pen sketch, 1917 structure (petescully)"
    ),
    "02_train_crossing.jpg": (
        "https://live.staticflickr.com/65535/52624922717_da885421df_b.jpg",
        "https://www.flickr.com/photos/157015151@N05/52624922717/",
        "Westbound train crosses Richards Blvd underpass (Tom Taylor)"
    ),
    "03_under_i80_bike.jpg": (
        "https://live.staticflickr.com/2386/2199299556_9c6f473ed8_b.jpg",
        "https://www.flickr.com/photos/soyunterrorista/2199299556/",
        "Under I-80 on bike path near Richards (kate mccarthy)"
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
        f.write("# Richards Underpass / Color Study Mural — Reference Image Sources\n")
        f.write("# Flickr only (educational reference use)\n")
        f.write("# NOTE: 'Color Study for Cyclists' mural by Ben Volta (2021) has\n")
        f.write("#   very limited Flickr coverage. The mural is a vibrant geometric\n")
        f.write("#   pattern of colorful stripes painted on the underpass walls/ceiling.\n")
        f.write("#   User should add own photos or Google Earth/Street View captures.\n\n")
        for local_name, source, page, ok in results:
            status = "OK" if ok else "FAILED"
            f.write(f"{local_name}\n  Source: {source}\n  Page: {page}\n  Status: {status}\n\n")

    ok_count = sum(1 for *_, ok in results if ok)
    fail_count = len(results) - ok_count
    total = len(results)
    print(f"\nDone: {ok_count}/{total} downloaded to {DEST}")
    if fail_count:
        print(f"  {fail_count} failed — re-run to retry")
    print(f"\nGAP — Color Study mural has limited online images.")
    print(f"  Add your own Google Street View / photo captures:")
    print(f"  - 04_mural_wide.jpg   — full underpass with mural visible")
    print(f"  - 05_mural_detail.jpg — close-up of geometric color stripes")
    print(f"  - 06_aerial_satellite.png — Google Earth overhead view")


if __name__ == "__main__":
    total = len(FLICKR)
    print(f"Downloading {total} reference images for Richards Underpass...\n")
    download_all()
