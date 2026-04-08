"""
Download reference images for Egghead Sculptures (ICONIC-001, Landmark #9).

The Eggheads are a collection of sculptures by Robert Arneson, installed on
the UC Davis campus. Arneson (1930-1992) was a UC Davis art professor and
pioneer of the Funk Art movement. The bronze sculptures depict oversized
human heads in various poses and were installed posthumously.

Individual sculptures include:
  - Yin and Yang (two face sculptures)
  - Eye on Mrak / Fatal Laff (near Mrak Hall)
  - Bookhead (head made of stacked books)
  - See No Evil / Hear No Evil (two busts)
  - Stargazer (head looking skyward)
  - Egghead (iconic egg-shaped head)

Excellent Flickr coverage (195+ photos). Wikimedia has 62 results.

Usage:
    python Code/iconic_davis/references/download_eggheads_refs.py

Downloads images into:
    Code/iconic_davis/references/egghead_sculptures/
"""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

DEST = Path(__file__).parent / "egghead_sculptures"
USER_AGENT = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

# ── Wikimedia Commons images ──
WIKIMEDIA = {
    # (none — image 01 moved to Flickr after bad Wikimedia match)
}

# ── Flickr images (direct static URLs, _b = 1024px large) ──
# Curated selection covering different individual sculptures
FLICKR = {
    # --- Egghead overview ---
    "01_egghead_overview.jpg": (
        "https://live.staticflickr.com/65535/51409012316_0a567149e4_b.jpg",
        "https://www.flickr.com/photos/dsh1492/51409012316/",
        "Egg head sculpture at UC Davis (David Heaphy)"
    ),
    # --- Yin and Yang ---
    "02_yin_yang.jpg": (
        "https://live.staticflickr.com/65535/51631864720_9179b75072_b.jpg",
        "https://www.flickr.com/photos/ian_e_abbott/51631864720/",
        "Yin & Yang by Robert Arneson, UC Davis (Ian Abbott)"
    ),
    "03_yin_yang_alt.jpg": (
        "https://live.staticflickr.com/2342/2448519776_9f3c53b074_b.jpg",
        "https://www.flickr.com/photos/doomlordvekk/2448519776/",
        "Yin & Yang close-up (doomlordvekk)"
    ),
    # --- Eye on Mrak / Fatal Laff ---
    "04_eye_on_mrak.jpg": (
        "https://live.staticflickr.com/4486/24012681718_9662f11ac8_b.jpg",
        "https://www.flickr.com/photos/sygridparan/24012681718/",
        "Eye on Mrak (Fatal Laff) egghead (Sygrid Sophia Paran)"
    ),
    # --- Bookhead ---
    "05_bookhead.jpg": (
        "https://live.staticflickr.com/8670/29943104013_125f1df1f4_b.jpg",
        "https://www.flickr.com/photos/48141388@N07/29943104013/",
        "A Good Book / Bookhead egghead (Elaine Mikkelstrup)"
    ),
    "06_bookhead_sketch.jpg": (
        "https://live.staticflickr.com/5813/20539393341_e540ca6720_b.jpg",
        "https://www.flickr.com/photos/petescully/20539393341/",
        "Egghead bookhead pen sketch (petescully)"
    ),
    # --- See No Evil / Hear No Evil ---
    "07_see_hear_no_evil.jpg": (
        "https://live.staticflickr.com/4074/4938274606_1a9fd64176_b.jpg",
        "https://www.flickr.com/photos/eekim/4938274606/",
        "See No Evil, Hear No Evil (Eugene Kim)"
    ),
    "08_see_hear_no_evil_sketch.jpg": (
        "https://live.staticflickr.com/65535/53678618442_2089edd15f_b.jpg",
        "https://www.flickr.com/photos/petescully/53678618442/",
        "See No Evil Hear No Evil sketch 2024 (petescully)"
    ),
    # --- Stargazer ---
    "09_stargazer.jpg": (
        "https://live.staticflickr.com/4469/37263739591_ba20642f75_b.jpg",
        "https://www.flickr.com/photos/petescully/37263739591/",
        "Egghead stargazer sketch (petescully)"
    ),
    # --- Iconic Egghead ---
    "10_egghead_iconic.jpg": (
        "https://live.staticflickr.com/15/68932312_e05a6bf4b3_b.jpg",
        "https://www.flickr.com/photos/tealsharkie/68932312/",
        "Egghead — iconic egg-shaped at UC Davis (Christopher)"
    ),
    # --- Multiple / Group shots ---
    "11_eggheads_group.jpg": (
        "https://live.staticflickr.com/44/147887282_d05fbb8f85_b.jpg",
        "https://www.flickr.com/photos/ucdgrad/147887282/",
        "Eggheads group view on campus (Joe Young)"
    ),
    "12_eggheads_arneson.jpg": (
        "https://live.staticflickr.com/65535/53835673961_3f889d1a09_b.jpg",
        "https://www.flickr.com/photos/188479097@N07/53835673961/",
        "UC Davis Eggheads by Arneson overview (Alan Kyker)"
    ),
    # --- Turn that frown / upside down ---
    "13_frown_upside_down.jpg": (
        "https://live.staticflickr.com/5722/30501587476_d83e977950_b.jpg",
        "https://www.flickr.com/photos/48141388@N07/30501587476/",
        "Turn that frown upside down (Elaine Mikkelstrup)"
    ),
    # --- UC Davis Egg Head detail ---
    "14_egg_head_detail.jpg": (
        "https://live.staticflickr.com/5757/30484981115_5c89fa9209_b.jpg",
        "https://www.flickr.com/photos/48141388@N07/30484981115/",
        "UC Davis Egg Head close-up detail (Elaine Mikkelstrup)"
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
        f.write("# Egghead Sculptures (Robert Arneson) — Reference Image Sources\n")
        f.write("# Multi-source: Wikimedia + Flickr (educational reference use)\n")
        f.write("# Sculptures: Yin&Yang, Eye on Mrak, Bookhead, See/Hear No Evil,\n")
        f.write("#   Stargazer, Egghead (iconic), and others across UC Davis campus.\n\n")
        for local_name, source, page, ok in results:
            status = "OK" if ok else "FAILED"
            f.write(f"{local_name}\n  Source: {source}\n  Page: {page}\n  Status: {status}\n\n")

    ok_count = sum(1 for *_, ok in results if ok)
    fail_count = len(results) - ok_count
    total = len(results)
    print(f"\nDone: {ok_count}/{total} downloaded to {DEST}")
    if fail_count:
        print(f"  {fail_count} failed — re-run to retry")
    print(f"\nTIP — Add your own Google Earth screenshot as 15_aerial_satellite.png")


if __name__ == "__main__":
    total = len(WIKIMEDIA) + len(FLICKR)
    print(f"Downloading {total} reference images for Egghead Sculptures...\n")
    download_all()
