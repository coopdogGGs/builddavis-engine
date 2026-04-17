"""
Download reference images for The Bike Barn (ICONIC-001, Landmark #18).

The Bike Barn is UC Davis's on-campus bicycle repair shop, located near the
Silo. It provides bike sales, repairs, and rentals. The building is a simple
utilitarian structure surrounded by hundreds of parked bicycles — iconic to
Davis's identity as the most bike-friendly city in America.

Flickr coverage: 27 photos (many are Pete Scully's urban sketches — filtered
to photos only).

GPS: approximately 38.5410, -121.7530

Usage:
    python Code/iconic_davis/references/download_bike_barn_refs.py

Downloads images into:
    Code/iconic_davis/references/bike_barn/
"""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

DEST = Path(__file__).parent / "bike_barn"
USER_AGENT = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

# No Wikimedia Commons images found
WIKIMEDIA = {}

# ── Flickr images (direct static URLs, _b = 1024px large) ──
FLICKR = {
    "01_exterior.jpg": (
        "https://live.staticflickr.com/65535/48545763416_234a2673f3_b.jpg",
        "https://www.flickr.com/photos/mateox/48545763416/",
        "Bike Barn exterior UC Davis (Matthew X. Kiernan)"
    ),
    "02_bikes_front.jpg": (
        "https://live.staticflickr.com/65535/49216012191_ec96a5c35a_b.jpg",
        "https://www.flickr.com/photos/steve_owen/49216012191/",
        "Bike Barn with bikes parked out front (Steve OWEN)"
    ),
    "03_bikes_side.jpg": (
        "https://live.staticflickr.com/65535/49216012256_50974cf036_b.jpg",
        "https://www.flickr.com/photos/steve_owen/49216012256/",
        "Bike Barn side view with bike racks (Steve OWEN)"
    ),
    "04_building_front.jpg": (
        "https://live.staticflickr.com/3283/3064619202_68c0041373_b.jpg",
        "https://www.flickr.com/photos/techieshark/3064619202/",
        "UC Davis Bike Barn building front (Peter W)"
    ),
    "05_building_angle.jpg": (
        "https://live.staticflickr.com/3219/3064613634_65cfb1951d_b.jpg",
        "https://www.flickr.com/photos/techieshark/3064613634/",
        "UC Davis Bike Barn angle view (Peter W)"
    ),
    "06_context.jpg": (
        "https://live.staticflickr.com/3096/2591628046_74eff7785f_b.jpg",
        "https://www.flickr.com/photos/dakotaunderwater/2591628046/",
        "Bike Barn context view (dakotaunderwater)"
    ),
    "07_bike_parking.jpg": (
        "https://live.staticflickr.com/3596/3666925165_d06f7396d5_b.jpg",
        "https://www.flickr.com/photos/danbmay/3666925165/",
        "Massive bike parking at Bike Barn (Dan B May)"
    ),
    "08_bike_rows.jpg": (
        "https://live.staticflickr.com/3599/3666922237_43591a4a3d_b.jpg",
        "https://www.flickr.com/photos/danbmay/3666922237/",
        "Rows of bikes near Bike Barn (Dan B May)"
    ),
}


def download_wikimedia(results):
    """Download from Wikimedia Commons via API thumbnail endpoint."""
    if not WIKIMEDIA:
        return
    print("── Wikimedia Commons ──")
    for local_name, wiki_name in WIKIMEDIA.items():
        dest_path = DEST / local_name
        if dest_path.exists() and dest_path.stat().st_size > 10_000:
            size_kb = dest_path.stat().st_size / 1024
            print(f"  [{local_name}] SKIP (already {size_kb:.0f} KB)")
            page = f"https://commons.wikimedia.org/wiki/File:{urllib.parse.quote(wiki_name.replace(' ', '_'))}"
            results.append((local_name, "Wikimedia", page, True))
            continue

        print(f"  [{local_name}] ...", end=" ", flush=True)
        try:
            api_url = (
                "https://en.wikipedia.org/w/api.php?action=query&titles=File:"
                + urllib.parse.quote(wiki_name.replace(" ", "_"))
                + "&prop=imageinfo&iiprop=url&iiurlwidth=2048&format=json"
            )
            api_req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(api_req, timeout=15) as api_resp:
                api_data = json.loads(api_resp.read())
            pages = api_data.get("query", {}).get("pages", {})
            img_url = None
            for page in pages.values():
                for ii in page.get("imageinfo", []):
                    img_url = ii.get("thumburl") or ii.get("url")
            if not img_url:
                raise RuntimeError("Could not resolve image URL via API")

            req = urllib.request.Request(img_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            dest_path.write_bytes(data)
            size_kb = len(data) / 1024
            print(f"OK  ({size_kb:.0f} KB)")
            page = f"https://commons.wikimedia.org/wiki/File:{urllib.parse.quote(wiki_name.replace(' ', '_'))}"
            results.append((local_name, "Wikimedia", page, True))
        except Exception as e:
            print(f"FAILED  ({e})")
            results.append((local_name, "Wikimedia", "", False))

        time.sleep(2)


def download_flickr(results):
    """Download from Flickr static CDN."""
    print("\n── Flickr ──")
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

    download_wikimedia(results)
    download_flickr(results)

    # Write urls.txt for attribution
    urls_path = DEST / "urls.txt"
    with open(urls_path, "w", encoding="utf-8") as f:
        f.write("# The Bike Barn — Reference Image Sources\n")
        f.write("# Flickr only (educational reference use)\n")
        f.write("# UC Davis on-campus bike shop near The Silo.\n\n")
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
    total = len(WIKIMEDIA) + len(FLICKR)
    print(f"Downloading {total} reference images for The Bike Barn...\n")
    download_all()
