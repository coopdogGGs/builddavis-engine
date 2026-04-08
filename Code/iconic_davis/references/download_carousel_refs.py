"""
Download reference images for Flying Carousel of the Delta Breeze
(ICONIC-001, Landmark #8).

The Flying Carousel of the Delta Breeze is a hand-carved wooden carousel
located in Central Park, Davis. It was built in 1995 and features animals
native to the Sacramento Valley. Named after the Delta Breeze — the cool
Pacific air that flows through the Delta to relieve Sacramento Valley heat.

Very limited Flickr/Wikimedia coverage. User should add own photos and
Google Earth screenshots.

Usage:
    python Code/iconic_davis/references/download_carousel_refs.py

Downloads images into:
    Code/iconic_davis/references/flying_carousel/
"""

import time
import urllib.request
from pathlib import Path

DEST = Path(__file__).parent / "flying_carousel"
USER_AGENT = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

# ── Flickr images (direct static URLs, _b = 1024px large) ──
FLICKR = {
    "01_carousel.jpg": (
        "https://live.staticflickr.com/3306/3602739562_3a7f3cab25_b.jpg",
        "https://www.flickr.com/photos/cptferg/3602739562/",
        "Carousel in Davis Central Park (Captain.Ferg)"
    ),
    # 02 & 03 removed — were Let's Draw Davis posters, not carousel photos.
    # Very limited online coverage for this carousel.
    # User should add own photos and Google Earth/Street View aerials.
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
        f.write("# Flying Carousel of the Delta Breeze — Reference Image Sources\n")
        f.write("# Flickr only (educational reference use)\n")
        f.write("# NOTE: Very limited online coverage for this specific carousel.\n")
        f.write("#   Located in Central Park, Davis (B St & 4th St).\n")
        f.write("#   Built 1995, hand-carved wooden animals native to Sacramento Valley.\n")
        f.write("#   Circular structure with conical roof.\n")
        f.write("#   User should add own photos and Google Earth/Street View captures.\n\n")
        for local_name, source, page, ok in results:
            status = "OK" if ok else "FAILED"
            f.write(f"{local_name}\n  Source: {source}\n  Page: {page}\n  Status: {status}\n\n")

    ok_count = sum(1 for *_, ok in results if ok)
    fail_count = len(results) - ok_count
    total = len(results)
    print(f"\nDone: {ok_count}/{total} downloaded to {DEST}")
    if fail_count:
        print(f"  {fail_count} failed — re-run to retry")
    print(f"\nGAP — This carousel has very limited online photo coverage.")
    print(f"  Add your own captures:")
    print(f"  - 04_carousel_front.jpg    — front/entrance view")
    print(f"  - 05_carousel_animals.jpg  — carved animal detail")
    print(f"  - 06_carousel_roof.jpg     — conical roof structure")
    print(f"  - 07_aerial_satellite.png  — Google Earth overhead view")


if __name__ == "__main__":
    total = len(FLICKR)
    print(f"Downloading {total} reference images for Flying Carousel...\n")
    download_all()
