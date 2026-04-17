"""
Download reference images for Davis Toad Tunnel + Toad Hotel (ICONIC-001, Landmark #3).

Multi-source: Wikimedia Commons + Flickr.

Usage:
    python Code/iconic_davis/references/download_toad_tunnel_refs.py

Downloads images into:
    Code/iconic_davis/references/toad_tunnel/
"""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

DEST = Path(__file__).parent / "toad_tunnel"
USER_AGENT = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

# ── Wikimedia Commons images ──
# {local_filename: wikimedia_filename}
WIKIMEDIA = {
    "01_tunnel_entrance.jpg":
        "Davis Toad Tunnel entrance.jpg",
    "02_solar_house.jpg":
        "Davis Toad Tunnel solar powered house.jpg",
    "03_pole_line_rd_context.jpg":
        "Pole Line Rd looking at the post office toad tunnel in Davis California.jpg",
    "04_tunnel_entrance_alt.jpg":
        "Toad tunnel entrance.jpg",
    "05_tunnel_under_road.jpg":
        "Toad tunnel entrance under Pole Line Road.jpg",
}

# ── Flickr images (direct static URLs, _b = 1024px large) ──
# {local_filename: (direct_url, flickr_page, description)}
FLICKR = {
    "06_toad_hollow_wide.jpg": (
        "https://live.staticflickr.com/8165/7648017150_91768f1ec2_b.jpg",
        "https://www.flickr.com/photos/whsieh78/7648017150/",
        "Toad Hollow wide shot with miniature buildings (Wayne Hsieh)"
    ),
    "07_toad_town_green.jpg": (
        "https://live.staticflickr.com/2245/2094267187_326627a6aa_b.jpg",
        "https://www.flickr.com/photos/basykes/2094267187/",
        "Toad Town Goes Green - solar panels on miniature buildings (Bev Sykes)"
    ),
    "08_tunnel_closeup.jpg": (
        "https://live.staticflickr.com/3487/3754710295_11a61599be_b.jpg",
        "https://www.flickr.com/photos/spor/3754710295/",
        "Toad Tunnel pipe entrance close-up (Gareth Spor)"
    ),
    "09_toad_ville.jpg": (
        "https://live.staticflickr.com/8012/7464494604_e3fcd6e3ff_b.jpg",
        "https://www.flickr.com/photos/julien-vergneau/7464494604/",
        "Crapaud ville - toad town angle (Julien_V)"
    ),
    "10_wetland_pond.jpg": (
        "https://live.staticflickr.com/3546/3362451750_6cea73ff1c_b.jpg",
        "https://www.flickr.com/photos/sheenjek/3362451750/",
        "Toad Hollow wetland/pond - tunnel destination (sheenjek)"
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
        f.write("# Davis Toad Tunnel + Toad Hotel — Reference Image Sources\n")
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
