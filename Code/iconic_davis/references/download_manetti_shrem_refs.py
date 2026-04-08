"""
Download reference images for Manetti Shrem Museum (ICONIC-001, Landmark #4).

Multi-source: Wikimedia Commons + Flickr.

Usage:
    python Code/iconic_davis/references/download_manetti_shrem_refs.py

Downloads images into:
    Code/iconic_davis/references/manetti_shrem_museum/
"""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

DEST = Path(__file__).parent / "manetti_shrem_museum"
USER_AGENT = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

# ── Wikimedia Commons images ──
# {local_filename: wikimedia_filename}
WIKIMEDIA = {
    "01_exterior_main.jpg":
        "Manetti Shrem Museum of Art.jpg",
    "02_entrance.jpg":
        "Manetti Shrem Museum of Art entrance.jpg",
    "03_canopy_swirl.jpg":
        "Manetti Shrem Museum of Art swirling canopies.jpg",
}

# ── Flickr images (direct static URLs, _b = 1024px large) ──
# {local_filename: (direct_url, flickr_page, description)}
FLICKR = {
    "04_exterior_architecture.jpg": (
        "https://live.staticflickr.com/4563/25075717938_e82301410e_b.jpg",
        "https://www.flickr.com/photos/herrera/25075717938/",
        "Exterior wide shot - SO-IL + Bohlin Cywinski Jackson (fernando herrera)"
    ),
    "05_looking_up_canopy.jpg": (
        "https://live.staticflickr.com/1721/42857650261_353d8fe223_b.jpg",
        "https://www.flickr.com/photos/timothysallenphotos/42857650261/",
        "Looking Up - dramatic canopy exterior (Timothy S. Allen)"
    ),
    "06_under_canopy.jpg": (
        "https://live.staticflickr.com/7923/33244766918_5cda86def8_b.jpg",
        "https://www.flickr.com/photos/janeland/33244766918/",
        "Under the trees at Manetti Shrem (Jane Marie Cleveland)"
    ),
    "07_canopy_detail.jpg": (
        "https://live.staticflickr.com/4686/38060838055_37dcda02f1_b.jpg",
        "https://www.flickr.com/photos/herrera/38060838055/",
        "Exterior canopy detail angle (fernando herrera)"
    ),
    "08_with_mondavi.jpg": (
        "https://live.staticflickr.com/65535/50161804607_0701db88e6_b.jpg",
        "https://www.flickr.com/photos/102709054@N05/50161804607/",
        "Museum + Mondavi Center context (Alexander Kozik)"
    ),
    "09_modern_2025.jpg": (
        "https://live.staticflickr.com/65535/54435311331_188bf37b95_b.jpg",
        "https://www.flickr.com/photos/srikanthsangeeta/54435311331/",
        "Recent 2025 photo (Srikanth Srinivasan)"
    ),
    "10_exterior_color.jpg": (
        "https://live.staticflickr.com/8280/29745754474_953390842d_b.jpg",
        "https://www.flickr.com/photos/rocor/29745754474/",
        "Exterior color daytime - 254 Old Davis Rd (Rob Corder)"
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
        f.write("# Manetti Shrem Museum — Reference Image Sources\n")
        f.write("# Multi-source: Wikimedia Commons + Flickr (educational reference use)\n\n")
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
