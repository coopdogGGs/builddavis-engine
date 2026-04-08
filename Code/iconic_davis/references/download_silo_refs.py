"""
Download reference images for The Silo at UC Davis
(ICONIC-001, Landmark #14).

Original 1909 dairy barn — wood planks, gambrel roof. Oldest building on
campus, now a dining facility. At 38.5372, -121.7463.

Moderate Flickr coverage (petescully prolific). No Wikimedia Commons.

Usage:
    python Code/iconic_davis/references/download_silo_refs.py

Downloads images into:
    Code/iconic_davis/references/the_silo/
"""

import time
import urllib.request
from pathlib import Path

DEST = Path(__file__).parent / "the_silo"
USER_AGENT = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

# ── Flickr images (direct static URLs, _b = 1024px large) ──
FLICKR = {
    "01_south_silo.jpg": (
        "https://live.staticflickr.com/5682/30126223454_07b8e0c4ce_b.jpg",
        "https://www.flickr.com/photos/petescully/30126223454/",
        "South Silo UC Davis, clear daylit (petescully)"
    ),
    "02_wood_planks.jpg": (
        "https://live.staticflickr.com/8305/7877796620_0c05408159_b.jpg",
        "https://www.flickr.com/photos/petescully/7877796620/",
        "Silo with wood planks visible (petescully)"
    ),
    "03_full_structure.jpg": (
        "https://live.staticflickr.com/5206/5371228359_0b8e17712d_b.jpg",
        "https://www.flickr.com/photos/petescully/5371228359/",
        "Full structure angle view (petescully)"
    ),
    "04_close_detail.jpg": (
        "https://live.staticflickr.com/8031/7990661019_f6c3606fdf_b.jpg",
        "https://www.flickr.com/photos/petescully/7990661019/",
        "Close architectural detail (petescully)"
    ),
    "05_gambrel_roof.jpg": (
        "https://live.staticflickr.com/5189/5665793646_6ddb37f8e0_b.jpg",
        "https://www.flickr.com/photos/petescully/5665793646/",
        "Gambrel roof visible (petescully)"
    ),
    "06_modern_angle.jpg": (
        "https://live.staticflickr.com/4604/40035615032_d31f102b75_b.jpg",
        "https://www.flickr.com/photos/whsieh78/40035615032/",
        "Modern angle view (Wayne Hsieh)"
    ),
    "07_campus_context.jpg": (
        "https://live.staticflickr.com/3751/11468591184_c9ff55bb39_b.jpg",
        "https://www.flickr.com/photos/kuanghan/11468591184/",
        "Campus context view (ASTROKUANG)"
    ),
    "08_profile.jpg": (
        "https://live.staticflickr.com/3389/3331266482_6905a20ee2_b.jpg",
        "https://www.flickr.com/photos/cdreilly/3331266482/",
        "Architectural profile (CDReilly)"
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
        f.write("# The Silo (UC Davis) — Reference Image Sources\n")
        f.write("# Flickr only (no Wikimedia Commons coverage)\n")
        f.write("# Original 1909 dairy barn, wood planks, gambrel roof.\n\n")
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
    print(f"Downloading {total} reference images for The Silo...\n")
    download_all()
