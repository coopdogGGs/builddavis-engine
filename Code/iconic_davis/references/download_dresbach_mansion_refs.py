"""
Download reference images for Dresbach-Hunt-Boyer Mansion (ICONIC-001, Landmark #19).

The Dresbach-Hunt-Boyer Mansion is a historic Victorian-era home at 604 2nd
Street in Old North Davis. Built c.1868 by William Dresbach, it is listed on
the National Register of Historic Places (NRHP #76000540). The mansion features
Italianate architectural details with later Victorian modifications.

Limited online coverage — 2 Wikimedia + 2 Flickr photos. GAP: needs user photos
(side profiles, detail closeups, garden/yard).

GPS: 38.5433, -121.7394

Usage:
    python Code/iconic_davis/references/download_dresbach_mansion_refs.py

Downloads images into:
    Code/iconic_davis/references/dresbach_mansion/
"""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

DEST = Path(__file__).parent / "dresbach_mansion"
USER_AGENT = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

# ── Wikimedia Commons images ──
WIKIMEDIA = {
    "01_exterior.jpg":
        "Dresbach-Hunt-Boyer Mansion- Davis, CA.jpg",
    "02_landmark_sign.jpg":
        "Davis Landmark Sign for Dresbach-Hunt-Boyer Mansion.jpg",
}

# ── Flickr images (direct static URLs, _b = 1024px large) ──
FLICKR = {
    "03_604_2nd_st.jpg": (
        "https://live.staticflickr.com/65535/48544936461_bbb3bb0d55_b.jpg",
        "https://www.flickr.com/photos/mateox/48544936461/",
        "604 2nd St Old Town Davis (Matthew X. Kiernan)"
    ),
    "04_mansion_view.jpg": (
        "https://live.staticflickr.com/2852/33516997582_1d8805bcb3_b.jpg",
        "https://www.flickr.com/photos/petescully/33516997582/",
        "Dresbach-Hunt-Boyer Mansion sketch/photo (petescully)"
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
        f.write("# Dresbach-Hunt-Boyer Mansion — Reference Image Sources\n")
        f.write("# Multi-source: Wikimedia Commons + Flickr (educational reference use)\n")
        f.write("# NRHP #76000540, 604 2nd St, Davis. c.1868 Italianate Victorian.\n")
        f.write("# GAP: Only 4 images. Needs user photos (side views, details, yard).\n\n")
        for local_name, source, page, ok in results:
            status = "OK" if ok else "FAILED"
            f.write(f"{local_name}\n  Source: {source}\n  Page: {page}\n  Status: {status}\n\n")

    ok_count = sum(1 for *_, ok in results if ok)
    fail_count = len(results) - ok_count
    total = len(results)
    print(f"\nDone: {ok_count}/{total} downloaded to {DEST}")
    if fail_count:
        print(f"  {fail_count} failed — re-run to retry")
    print(f"\nGAP: Only {ok_count} images — needs user Google Earth/Street View screenshots")


if __name__ == "__main__":
    total = len(WIKIMEDIA) + len(FLICKR)
    print(f"Downloading {total} reference images for Dresbach-Hunt-Boyer Mansion...\n")
    download_all()
