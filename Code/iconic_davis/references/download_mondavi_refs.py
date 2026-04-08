"""
Download reference images for Robert & Margrit Mondavi Center for the
Performing Arts (ICONIC-001, Landmark #10).

The Mondavi Center is a performing arts venue on the UC Davis campus, opened
October 3, 2002. Designed by Boora Architects (Portland, OR) as a "box within
a box" to insulate from freeway/train noise. Features a large glass-panelled
lobby surrounded by sandstone, Jackson Hall (1,801 seats), and Vanderhoef
Studio Theatre (250 seats). Named for Robert Mondavi who donated $10M.

Excellent Flickr coverage (589+ photos). 4 Wikimedia Commons images.

Usage:
    python Code/iconic_davis/references/download_mondavi_refs.py

Downloads images into:
    Code/iconic_davis/references/mondavi_center/
"""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

DEST = Path(__file__).parent / "mondavi_center"
USER_AGENT = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

# ── Wikimedia Commons images ──
WIKIMEDIA = {
    "01_exterior.jpg":
        "UC Davis Mondavi Center.jpg",
    "02_interior.jpg":
        "Mondavi Center UC Davis.jpg",
    "03_facade.jpg":
        "Mondavicenter.jpeg",
}

# ── Flickr images (direct static URLs, _b = 1024px large) ──
FLICKR = {
    "04_daytime_wide.jpg": (
        "https://live.staticflickr.com/5651/21321053269_9bb0cbdf9d_b.jpg",
        "https://www.flickr.com/photos/slizarraga/21321053269/",
        "Mondavi Center at UC Davis, wide daytime (lizarrd9)"
    ),
    "05_architecture.jpg": (
        "https://live.staticflickr.com/4239/35022364333_5057bda7ae_b.jpg",
        "https://www.flickr.com/photos/dsh1492/35022364333/",
        "Mondavi Center architectural detail (David Heaphy)"
    ),
    "06_robert_margrit.jpg": (
        "https://live.staticflickr.com/4821/46320378871_be162d6cdc_b.jpg",
        "https://www.flickr.com/photos/102709054@N05/46320378871/",
        "Robert and Margrit Mondavi Center (Alexander Kozik)"
    ),
    "07_evening_view.jpg": (
        "https://live.staticflickr.com/65535/50161009108_3c97acc13f_b.jpg",
        "https://www.flickr.com/photos/102709054@N05/50161009108/",
        "Mondavi Center evening view (Alexander Kozik)"
    ),
    "08_with_manetti.jpg": (
        "https://live.staticflickr.com/65535/50161804607_0701db88e6_b.jpg",
        "https://www.flickr.com/photos/102709054@N05/50161804607/",
        "Manetti Shrem + Mondavi Center together (Alexander Kozik)"
    ),
    "09_front_entrance.jpg": (
        "https://live.staticflickr.com/581/32472291166_8afccfd270_b.jpg",
        "https://www.flickr.com/photos/lcsalcedo/32472291166/",
        "Mondavi Center front entrance (Leon Salcedo)"
    ),
    "10_sunset.jpg": (
        "https://live.staticflickr.com/7181/6895366599_7e01968a38_b.jpg",
        "https://www.flickr.com/photos/sheenjek/6895366599/",
        "Mondavi Center sunset (sheenjek)"
    ),
    "11_glass_lobby.jpg": (
        "https://live.staticflickr.com/411/32138146962_386e11e2ef_b.jpg",
        "https://www.flickr.com/photos/jblevins/32138146962/",
        "Robert and Margrit Mondavi Center glass lobby (Jason Blevins)"
    ),
    "12_approach.jpg": (
        "https://live.staticflickr.com/2578/4122477574_069b86dc2e_b.jpg",
        "https://www.flickr.com/photos/prayitnophotography/4122477574/",
        "UC Davis Mondavi Center approach (Prayitno)"
    ),
    "13_night.jpg": (
        "https://live.staticflickr.com/2504/4122456614_2284d2775b_b.jpg",
        "https://www.flickr.com/photos/prayitnophotography/4122456614/",
        "UC Davis Mondavi Center at night (Prayitno)"
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
        f.write("# Robert & Margrit Mondavi Center — Reference Image Sources\n")
        f.write("# Multi-source: Wikimedia Commons + Flickr (educational reference use)\n")
        f.write("# Boora Architects, opened 2002. Glass lobby + sandstone walls.\n\n")
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
    print(f"Downloading {total} reference images for Mondavi Center...\n")
    download_all()
