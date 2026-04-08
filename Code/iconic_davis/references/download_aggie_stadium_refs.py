"""
Download reference images for UC Davis Aggie Stadium
(ICONIC-001, Landmark #15).

Football stadium, capacity 10,000+. Full stadium with track, bleachers,
field markings. Renamed UC Davis Health Stadium in recent years.
At 38.5298, -121.7487.

Good Flickr coverage. 3 Wikimedia Commons images (including 2024 drone).

Usage:
    python Code/iconic_davis/references/download_aggie_stadium_refs.py

Downloads images into:
    Code/iconic_davis/references/aggie_stadium/
"""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

DEST = Path(__file__).parent / "aggie_stadium"
USER_AGENT = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

# ── Wikimedia Commons images ──
WIKIMEDIA = {
    "01_exterior.jpg":
        "Aggie Stadium (UC Davis).jpg",
    "02_aerial_2024.jpg":
        "UC Davis Health Stadium view from above 2024.jpg",
    "03_drone_2024.jpg":
        "UC Davis Health Stadium drone view 2024.jpg",
}

# ── Flickr images (direct static URLs, _b = 1024px large) ──
FLICKR = {
    "04_full_stadium.jpg": (
        "https://live.staticflickr.com/65535/29353093590_ebce1d3b20_b.jpg",
        "https://www.flickr.com/photos/60035031@N06/29353093590/",
        "Full stadium view (Al Case)"
    ),
    "05_modern_view.jpg": (
        "https://live.staticflickr.com/943/41962910572_627e117ec0_b.jpg",
        "https://www.flickr.com/photos/102709054@N05/41962910572/",
        "Modern stadium photograph (Alexander Kozik)"
    ),
    "06_exterior_view.jpg": (
        "https://live.staticflickr.com/7179/6991598785_fb20e1f901_b.jpg",
        "https://www.flickr.com/photos/lcsalcedo/6991598785/",
        "Stadium exterior (Leon Salcedo)"
    ),
    "07_historic_angle.jpg": (
        "https://live.staticflickr.com/2086/1784032518_7f48c3814a_b.jpg",
        "https://www.flickr.com/photos/almonddejoy/1784032518/",
        "Historic angle view (wing-yan)"
    ),
    "08_field_view.jpg": (
        "https://live.staticflickr.com/3280/2973981706_6860ed563e_b.jpg",
        "https://www.flickr.com/photos/boxerrumble/2973981706/",
        "Field and seating view (BoxerRumble)"
    ),
    "09_east_entrance.jpg": (
        "https://live.staticflickr.com/2430/4076728710_3d09c5244c_b.jpg",
        "https://www.flickr.com/photos/calaggie/4076728710/",
        "East entrance detail (calaggie)"
    ),
    "10_seating.jpg": (
        "https://live.staticflickr.com/2352/1783186679_5de1097ea6_b.jpg",
        "https://www.flickr.com/photos/almonddejoy/1783186679/",
        "Seating/bleacher view (wing-yan)"
    ),
    "11_architectural.jpg": (
        "https://live.staticflickr.com/678/20635307793_ed3da92e00_b.jpg",
        "https://www.flickr.com/photos/auvet/20635307793/",
        "Architectural shot (Jimmy Emerson, DVM)"
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
        f.write("# Aggie Stadium (UC Davis Health Stadium) — Reference Image Sources\n")
        f.write("# Multi-source: Wikimedia Commons + Flickr (educational reference use)\n")
        f.write("# Football stadium, 10K+ capacity, track, bleachers.\n\n")
        for local_name, source, page, ok in results:
            status = "OK" if ok else "FAILED"
            f.write(f"{local_name}\n  Source: {source}\n  Page: {page}\n  Status: {status}\n\n")

    ok_count = sum(1 for *_, ok in results if ok)
    fail_count = len(results) - ok_count
    total = len(results)
    print(f"\nDone: {ok_count}/{total} downloaded to {DEST}")
    if fail_count:
        print(f"  {fail_count} failed — re-run to retry")
    print(f"\nTIP — Add your own Google Earth screenshot as 12_aerial_satellite.png")


if __name__ == "__main__":
    total = len(WIKIMEDIA) + len(FLICKR)
    print(f"Downloading {total} reference images for Aggie Stadium...\n")
    download_all()
