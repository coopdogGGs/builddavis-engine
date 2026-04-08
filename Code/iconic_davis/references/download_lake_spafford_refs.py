"""
Download reference images for Lake Spafford (ICONIC-001, Landmark #17).

Lake Spafford is a small lake/pond on the UC Davis campus, located within the
UC Davis Arboretum. Named after Ivanhoe Spafford, the university's first
official head gardener. Popular with students and visitors for its ducks,
geese, turtles, and tree-lined banks. Mrak Hall (main admin building) sits
across the lake.

Good Flickr coverage (156+ photos). 1 Wikimedia Commons image.

GPS: approximately 38.5377, -121.7483

Usage:
    python Code/iconic_davis/references/download_lake_spafford_refs.py

Downloads images into:
    Code/iconic_davis/references/lake_spafford/
"""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

DEST = Path(__file__).parent / "lake_spafford"
USER_AGENT = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

# ── Wikimedia Commons images ──
WIKIMEDIA = {
    "01_mrak_hall_across.jpg":
        "Mrak Hall (UC Davis) Across Lake Spafford.jpg",
}

# ── Flickr images (direct static URLs, _b = 1024px large) ──
FLICKR = {
    "02_lake_overview.jpg": (
        "https://live.staticflickr.com/1084/1155687363_5167a8e51c_b.jpg",
        "https://www.flickr.com/photos/sam_schmidt/1155687363/",
        "Lake Spafford overview with trees and reflections (Sam Schmidt)"
    ),
    "03_lake_shoreline.jpg": (
        "https://live.staticflickr.com/2168/2479515086_b221772ec2_b.jpg",
        "https://www.flickr.com/photos/maxbrain0/2479515086/",
        "Lake Spafford shoreline view (Maxbrain0)"
    ),
    "04_from_bridge.jpg": (
        "https://live.staticflickr.com/3286/2479511506_dc28792989_b.jpg",
        "https://www.flickr.com/photos/maxbrain0/2479511506/",
        "Lake from the bridge looking across (Maxbrain0)"
    ),
    "05_calm_reflection.jpg": (
        "https://live.staticflickr.com/8343/29817160355_649cb85396_b.jpg",
        "https://www.flickr.com/photos/jmf1007/29817160355/",
        "Summer's Calm — lake with serene reflections (Janice Marie Foote, CC-BY)"
    ),
    "06_portrait_view.jpg": (
        "https://live.staticflickr.com/8014/7132863331_e3a9cebe48_b.jpg",
        "https://www.flickr.com/photos/julien-vergneau/7132863331/",
        "Lake Spafford portrait view with trees (Julien_V)"
    ),
    "07_arboretum_context.jpg": (
        "https://live.staticflickr.com/65535/52054435336_0b6d00058d_b.jpg",
        "https://www.flickr.com/photos/goodlifegarden/52054435336/",
        "Lake Spafford arboretum setting (UC Davis Arboretum & Public Garden)"
    ),
    "08_fall_colors.jpg": (
        "https://live.staticflickr.com/3709/11343057254_74e49eef67_b.jpg",
        "https://www.flickr.com/photos/goodlifegarden/11343057254/",
        "Lake Spafford autumn colors (UC Davis Arboretum & Public Garden)"
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
        f.write("# Lake Spafford — Reference Image Sources\n")
        f.write("# Multi-source: Wikimedia Commons + Flickr (educational reference use)\n")
        f.write("# UC Davis Arboretum duck pond, named for Ivanhoe Spafford.\n\n")
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
    print(f"Downloading {total} reference images for Lake Spafford...\n")
    download_all()
