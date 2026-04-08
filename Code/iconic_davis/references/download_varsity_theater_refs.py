"""
Download reference images for Varsity Theater (ICONIC-001, Landmark #5).

All Flickr — no Wikimedia Commons results for Davis Varsity specifically.

Usage:
    python Code/iconic_davis/references/download_varsity_theater_refs.py

Downloads images into:
    Code/iconic_davis/references/varsity_theater/
"""

import time
import urllib.request
from pathlib import Path

DEST = Path(__file__).parent / "varsity_theater"
USER_AGENT = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

# ── Flickr images (direct static URLs, _b = 1024px large) ──
# {local_filename: (direct_url, flickr_page, description)}
FLICKR = {
    "01_facade_daytime.jpg": (
        "https://live.staticflickr.com/65535/51712277944_4ecde4c9b1_b.jpg",
        "https://www.flickr.com/photos/meckleychina/51712277944/",
        "Daytime facade straight-on, 2021 (John Meckley)"
    ),
    "02_marquee_detail.jpg": (
        "https://live.staticflickr.com/2485/4001178998_9c8908aa58_b.jpg",
        "https://www.flickr.com/photos/thomashawk/4001178998/",
        "Daytime marquee + facade detail, Canon 5D (Thomas Hawk)"
    ),
    "03_night_headlights.jpg": (
        "https://live.staticflickr.com/5350/30959979201_a064eb15f7_b.jpg",
        "https://www.flickr.com/photos/t-y-k/30959979201/",
        "Night shot with headlight trails, Nikon D750 (TiffK)"
    ),
    "04_daytime_detail.jpg": (
        "https://live.staticflickr.com/7205/6978510477_5e27fc9898_b.jpg",
        "https://www.flickr.com/photos/megansauce/6978510477/",
        "Daytime facade detail - true colors (Megan McKay)"
    ),
    "05_daytime_angle.jpg": (
        "https://live.staticflickr.com/6139/5948772290_d386ee6d29_b.jpg",
        "https://www.flickr.com/photos/csaulit/5948772290/",
        "Daytime side angle (Chris Saulit)"
    ),
    "06_facade_alt.jpg": (
        "https://live.staticflickr.com/4512/36728110404_8dc15d53f0_b.jpg",
        "https://www.flickr.com/photos/143972765@N04/36728110404/",
        "Facade alternate angle (Leia Hewitt)"
    ),
    "07_street_context.jpg": (
        "https://live.staticflickr.com/8708/26741368306_522e925a24_b.jpg",
        "https://www.flickr.com/photos/punktoad/26741368306/",
        "Street context view (PunkToad)"
    ),
    "08_dusk.jpg": (
        "https://live.staticflickr.com/7199/6832401958_8aa19e49c5_b.jpg",
        "https://www.flickr.com/photos/megansauce/6832401958/",
        "Varsity Theater at dusk (Megan McKay)"
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
        f.write("# Varsity Theater — Reference Image Sources\n")
        f.write("# All Flickr (educational reference use)\n\n")
        for local_name, source, page, ok in results:
            status = "OK" if ok else "FAILED"
            f.write(f"{local_name}\n  Source: {source}\n  Page: {page}\n  Status: {status}\n\n")

    ok_count = sum(1 for *_, ok in results if ok)
    fail_count = len(results) - ok_count
    total = len(results)
    print(f"\nDone: {ok_count}/{total} downloaded to {DEST}")
    if fail_count:
        print(f"  ⚠  {fail_count} failed — re-run to retry")


if __name__ == "__main__":
    download_all()
