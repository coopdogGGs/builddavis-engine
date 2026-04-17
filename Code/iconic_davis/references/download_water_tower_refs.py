"""
Download reference images for UC Davis Water Tower (ICONIC-001, Landmark #2).

Multi-source: Wikimedia Commons + Flickr + UC Davis official.

Usage:
    python Code/iconic_davis/references/download_water_tower_refs.py

Downloads images into:
    Code/iconic_davis/references/uc_davis_water_tower/
"""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

DEST = Path(__file__).parent / "uc_davis_water_tower"
USER_AGENT = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

# ── Wikimedia Commons images ──
# {local_filename: wikimedia_filename}
WIKIMEDIA = {
    "01_front_cropped.jpg":
        "Water Tower, UC Davis(cropped).jpg",
    "02_full_view.jpg":
        "Water Tower, UC Davis.jpg",
    "03_alternate_angle.jpg":
        "Water Tower in UC-Davis.jpg",
    "04_campus_context.jpg":
        "UC Davis - University of California, Davis (25707342720).jpg",
    "05_classic_view.jpg":
        "UCD Water tower.jpg",
}

# ── Flickr images (direct static URLs, _b = 1024px large) ──
# {local_filename: (direct_url, flickr_page, description)}
FLICKR = {
    "06_closeup_tonal.jpg": (
        "https://live.staticflickr.com/5534/10929978866_8fded53e78_b.jpg",
        "https://www.flickr.com/photos/funeralbell/10929978866/",
        "Close-up tonal shot (CC BY-ND 2.0, Steven Tyler PJs)"
    ),
    "07_night_neowise.jpg": (
        "https://live.staticflickr.com/65535/50193328126_5113684c62_b.jpg",
        "https://www.flickr.com/photos/94314925@N03/50193328126/",
        "Night shot with comet NEOWISE (Hadley Johnson)"
    ),
    "08_train_context.jpg": (
        "https://live.staticflickr.com/8239/8621543620_1a6b0f584d_b.jpg",
        "https://www.flickr.com/photos/amtrakdavis22/8621543620/",
        "UP locomotive + water tower context (Jake Miille)"
    ),
    "09_official_ucdavis.jpg": (
        "https://live.staticflickr.com/8010/7315889846_60fdea7e14_b.jpg",
        "https://www.flickr.com/photos/ucdavis_life/7315889846/",
        "Official UC Davis Admissions photo"
    ),
    "10_modern_2023.jpg": (
        "https://live.staticflickr.com/65535/52802824190_996a89b12c_b.jpg",
        "https://www.flickr.com/photos/mraja/52802824190/",
        "Recent 2023 photo (indien69)"
    ),
}


def download_wikimedia(results):
    """Download from Wikimedia Commons via API thumbnail endpoint."""
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
        f.write("# UC Davis Water Tower — Reference Image Sources\n")
        f.write("# Multi-source: Wikimedia Commons + Flickr (educational reference use)\n\n")
        for local_name, source, page, ok in results:
            status = "OK" if ok else "FAILED"
            f.write(f"{local_name}\n  Source: {source}\n  Page: {page}\n  Status: {status}\n\n")

    ok_count = sum(1 for *_, ok in results if ok)
    fail_count = len(results) - ok_count
    total = len(results)
    print(f"\nDone: {ok_count}/{total} downloaded to {DEST}")
    if fail_count:
        print(f"  {fail_count} failed — re-run script to retry")
    print(f"\nGAP — add your own Google Earth screenshot as 11_aerial.jpg")


if __name__ == "__main__":
    total = len(WIKIMEDIA) + len(FLICKR)
    print(f"Downloading {total} reference images for UC Davis Water Tower...\n")
    download_all()
