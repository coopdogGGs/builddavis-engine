"""
Download reference images for Covell Bicycle Overpass (ICONIC-001, Landmark #6).

The Covell Bicycle/Pedestrian Overpass connects Community Park to the
North Davis greenbelt across Covell Boulevard — an iconic symbol of Davis's
"Bicycle Capital" identity.

Wikimedia (1 image) + Flickr (3 images). Limited online coverage for this
specific overpass. User should add Google Earth screenshots.

Usage:
    python Code/iconic_davis/references/download_covell_overpass_refs.py

Downloads images into:
    Code/iconic_davis/references/covell_bicycle_overpass/
"""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

DEST = Path(__file__).parent / "covell_bicycle_overpass"
USER_AGENT = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

# ── Wikimedia Commons images ──
WIKIMEDIA = {
    "01_overview.jpg":
        "Covell bike overpass.jpg",
}

# ── Flickr images (direct static URLs, _b = 1024px large) ──
FLICKR = {
    "02_approach_view.jpg": (
        "https://live.staticflickr.com/7207/6823594862_0458035438_b.jpg",
        "https://www.flickr.com/photos/photokohn/6823594862/",
        "Approach view of bike overpass (Roger Kohn)"
    ),
    "03_bike_ped_overpass.jpg": (
        "https://live.staticflickr.com/2269/2193994813_1285a94589_b.jpg",
        "https://www.flickr.com/photos/soyunterrorista/2193994813/",
        "Bike/ped highway overpass, Davis (kate mccarthy)"
    ),
    "04_park_context.jpg": (
        "https://live.staticflickr.com/7072/7238364220_a49fe9bfc9_b.jpg",
        "https://www.flickr.com/photos/73170567@N07/7238364220/",
        "Davis park near bike overpass (DavisvilleCA)"
    ),
    "05_freeway_path.jpg": (
        "https://live.staticflickr.com/176/386196800_eddb6456d0_b.jpg",
        "https://www.flickr.com/photos/jshj/386196800/",
        "Freeway running/bike path overpass (jshj)"
    ),
}


def download_wikimedia(results):
    """Download from Wikimedia Commons via API thumbnail endpoint."""
    print("── Wikimedia Commons ──")
    for local_name, wiki_name in WIKIMEDIA.items():
        dest_path = DEST / local_name
        if dest_path.exists() and dest_path.stat().st_size > 5_000:
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
        f.write("# Covell Bicycle Overpass — Reference Image Sources\n")
        f.write("# Wikimedia + Flickr (educational reference use)\n")
        f.write("# NOTE: Limited online coverage. Add Google Earth aerial screenshot.\n\n")
        for local_name, source, page, ok in results:
            status = "OK" if ok else "FAILED"
            f.write(f"{local_name}\n  Source: {source}\n  Page: {page}\n  Status: {status}\n\n")

    ok_count = sum(1 for *_, ok in results if ok)
    fail_count = len(results) - ok_count
    total = len(results)
    print(f"\nDone: {ok_count}/{total} downloaded to {DEST}")
    if fail_count:
        print(f"  {fail_count} failed — re-run to retry")
    print(f"\nGAP — add your own Google Earth screenshot as 06_aerial_satellite.png")


if __name__ == "__main__":
    total = len(WIKIMEDIA) + len(FLICKR)
    print(f"Downloading {total} reference images for Covell Bicycle Overpass...\n")
    download_all()
