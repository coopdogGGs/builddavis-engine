"""
Download reference images for UC Davis Shields Library
(ICONIC-001, Landmark #13).

Peter J. Shields Library (1971) — brutalist concrete exterior, smooth stone,
flat roof, wide entrance steps. The Bookhead Egghead sculpture sits outside.
At 38.5381, -121.7497.

Excellent Flickr coverage (Alexander Kozik has 20+ shots). 2 Wikimedia images.

Usage:
    python Code/iconic_davis/references/download_shields_library_refs.py

Downloads images into:
    Code/iconic_davis/references/shields_library/
"""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

DEST = Path(__file__).parent / "shields_library"
USER_AGENT = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

# ── Wikimedia Commons images ──
WIKIMEDIA = {
    "01_exterior.jpg":
        "Peter J Shields Library.jpg",
    "02_campus_view.jpg":
        "UC Davis Shields Library.jpg",
}

# ── Flickr images (direct static URLs, _b = 1024px large) ──
FLICKR = {
    "03_facade_detail_hdr.jpg": (
        "https://live.staticflickr.com/5454/17733091252_b87dc5f40b_b.jpg",
        "https://www.flickr.com/photos/102709054@N05/17733091252/",
        "Brutalist facade detail HDR (Alexander Kozik)"
    ),
    "04_concrete_structure.jpg": (
        "https://live.staticflickr.com/8787/17679855486_8f70d25d28_b.jpg",
        "https://www.flickr.com/photos/102709054@N05/17679855486/",
        "Multi-angle concrete structure (Alexander Kozik)"
    ),
    "05_building_corner.jpg": (
        "https://live.staticflickr.com/5330/17516013910_1f394d28a5_b.jpg",
        "https://www.flickr.com/photos/102709054@N05/17516013910/",
        "Building corner/exterior facade (Alexander Kozik)"
    ),
    "06_full_exterior.jpg": (
        "https://live.staticflickr.com/4904/44484894110_554f57cf30_b.jpg",
        "https://www.flickr.com/photos/102709054@N05/44484894110/",
        "Full exterior building face (Alexander Kozik)"
    ),
    "07_morning_light.jpg": (
        "https://live.staticflickr.com/8893/28336874355_d88b60314a_b.jpg",
        "https://www.flickr.com/photos/102709054@N05/28336874355/",
        "Brutalist facade atmospheric morning light (Alexander Kozik)"
    ),
    "08_side_facade.jpg": (
        "https://live.staticflickr.com/4846/44484888990_f13bafd5ee_b.jpg",
        "https://www.flickr.com/photos/102709054@N05/44484888990/",
        "Side facade angle (Alexander Kozik)"
    ),
    "09_brutalist_detail.jpg": (
        "https://live.staticflickr.com/5452/17703466955_bc93bc7a08_b.jpg",
        "https://www.flickr.com/photos/102709054@N05/17703466955/",
        "Concrete brutalist detail (Alexander Kozik)"
    ),
    "10_exterior_2024.jpg": (
        "https://live.staticflickr.com/65535/53550294548_71a11398d8_b.jpg",
        "https://www.flickr.com/photos/petescully/53550294548/",
        "Recent 2024 exterior shot (petescully)"
    ),
    "11_walker_hall_context.jpg": (
        "https://live.staticflickr.com/1504/25466736220_7a6788d00c_b.jpg",
        "https://www.flickr.com/photos/petescully/25466736220/",
        "Walker Hall & Shields context (petescully)"
    ),
    "12_architectural.jpg": (
        "https://live.staticflickr.com/4105/5083448531_83bde74fd8_b.jpg",
        "https://www.flickr.com/photos/ghirson/5083448531/",
        "Architectural detail emphasis (Greg Hirson)"
    ),
    "13_exterior_detail.jpg": (
        "https://live.staticflickr.com/4518/37998727845_4f4b4b05b3_b.jpg",
        "https://www.flickr.com/photos/102709054@N05/37998727845/",
        "Exterior detail shot (Alexander Kozik)"
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
        f.write("# Shields Library — Reference Image Sources\n")
        f.write("# Multi-source: Wikimedia Commons + Flickr (educational reference use)\n")
        f.write("# Peter J. Shields Library, 1971. Brutalist concrete, flat roof.\n\n")
        for local_name, source, page, ok in results:
            status = "OK" if ok else "FAILED"
            f.write(f"{local_name}\n  Source: {source}\n  Page: {page}\n  Status: {status}\n\n")

    ok_count = sum(1 for *_, ok in results if ok)
    fail_count = len(results) - ok_count
    total = len(results)
    print(f"\nDone: {ok_count}/{total} downloaded to {DEST}")
    if fail_count:
        print(f"  {fail_count} failed — re-run to retry")
    print(f"\nTIP — Add your own Google Earth screenshot as 14_aerial_satellite.png")


if __name__ == "__main__":
    total = len(WIKIMEDIA) + len(FLICKR)
    print(f"Downloading {total} reference images for Shields Library...\n")
    download_all()
