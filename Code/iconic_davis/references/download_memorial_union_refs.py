"""
Download reference images for UC Davis Memorial Union
(ICONIC-001, Landmark #12).

Heart of campus — features a distinctive dome, sandstone base, and the
UC Davis official seal. Built 1955, expanded multiple times. Bus terminal
at entrance. At 38.5403, -121.7494.

Good Flickr coverage. 1 Wikimedia Commons image.

Usage:
    python Code/iconic_davis/references/download_memorial_union_refs.py

Downloads images into:
    Code/iconic_davis/references/memorial_union/
"""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

DEST = Path(__file__).parent / "memorial_union"
USER_AGENT = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

# ── Wikimedia Commons images ──
WIKIMEDIA = {
    "01_exterior.jpg":
        "UC Davis Memorial Union.jpg",
}

# ── Flickr images (direct static URLs, _b = 1024px large) ──
FLICKR = {
    "02_recent_overview.jpg": (
        "https://live.staticflickr.com/65535/54290268088_c7e0e11c98_b.jpg",
        "https://www.flickr.com/photos/aforum/54290268088/",
        "Memorial Union at UC Davis, recent overall (Carnaval.com Studios)"
    ),
    "03_panorama.jpg": (
        "https://live.staticflickr.com/65535/50549806141_88bdd144fe_b.jpg",
        "https://www.flickr.com/photos/petescully/50549806141/",
        "MU panorama with dome visible (petescully)"
    ),
    "04_summer_exterior.jpg": (
        "https://live.staticflickr.com/7595/28809782151_642e015266_b.jpg",
        "https://www.flickr.com/photos/petescully/28809782151/",
        "Summer daylight exterior (petescully)"
    ),
    "05_dome_view.jpg": (
        "https://live.staticflickr.com/4609/25196482917_819dbe91c8_b.jpg",
        "https://www.flickr.com/photos/whsieh78/25196482917/",
        "Clear exterior shot with dome (Wayne Hsieh)"
    ),
    "06_transit_center.jpg": (
        "https://live.staticflickr.com/1713/26032606622_f109d31c0d_b.jpg",
        "https://www.flickr.com/photos/mrviking426/26032606622/",
        "Modern entrance/transit center (Charles Wang)"
    ),
    "07_architectural.jpg": (
        "https://live.staticflickr.com/2638/3739859256_61c1dc3282_b.jpg",
        "https://www.flickr.com/photos/39794136@N06/3739859256/",
        "Architectural perspective (SusanneRockwell)"
    ),
    "08_daytime.jpg": (
        "https://live.staticflickr.com/65535/27090314493_406f42fc46_b.jpg",
        "https://www.flickr.com/photos/t-y-k/27090314493/",
        "Daytime exterior (TiffK)"
    ),
    "09_mu_jon_nelson.jpg": (
        "https://live.staticflickr.com/4404/36605223803_3651bde8b8_b.jpg",
        "https://www.flickr.com/photos/jonmnelson/36605223803/",
        "UC Davis Memorial Union exterior (Jon Nelson)"
    ),
    "10_mu_steve_owen.jpg": (
        "https://live.staticflickr.com/65535/49211050143_f70b9d755d_b.jpg",
        "https://www.flickr.com/photos/steve_owen/49211050143/",
        "Memorial Union Building exterior (Steve Owen)"
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
        f.write("# UC Davis Memorial Union — Reference Image Sources\n")
        f.write("# Multi-source: Wikimedia Commons + Flickr (educational reference use)\n")
        f.write("# Heart of campus, dome, sandstone base, UC Davis seal. Built 1955.\n\n")
        for local_name, source, page, ok in results:
            status = "OK" if ok else "FAILED"
            f.write(f"{local_name}\n  Source: {source}\n  Page: {page}\n  Status: {status}\n\n")

    ok_count = sum(1 for *_, ok in results if ok)
    fail_count = len(results) - ok_count
    total = len(results)
    print(f"\nDone: {ok_count}/{total} downloaded to {DEST}")
    if fail_count:
        print(f"  {fail_count} failed — re-run to retry")
    print(f"\nTIP — Add your own Google Earth screenshot as 11_aerial_satellite.png")


if __name__ == "__main__":
    total = len(WIKIMEDIA) + len(FLICKR)
    print(f"Downloading {total} reference images for Memorial Union...\n")
    download_all()
