"""
Download reference images for UC Davis SSH "Death Star" Building
(ICONIC-001, Landmark #11).

Social Sciences & Humanities Building, designed by Antoine Predock (1989).
Angular metallic/concrete facade — students call it the "Death Star."
Iron blocks, dark grey concrete, slit windows. At 38.5352, -121.7537.

Good Flickr coverage (60+ photos). No Wikimedia Commons images found.

Usage:
    python Code/iconic_davis/references/download_ssh_deathstar_refs.py

Downloads images into:
    Code/iconic_davis/references/ssh_deathstar/
"""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

DEST = Path(__file__).parent / "ssh_deathstar"
USER_AGENT = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

# ── Flickr images (direct static URLs, _b = 1024px large) ──
FLICKR = {
    "01_frontal_view.jpg": (
        "https://live.staticflickr.com/4116/4938257772_37c02dbc64_b.jpg",
        "https://www.flickr.com/photos/eekim/4938257772/",
        "SSH exterior facade frontal view (Eugene Kim)"
    ),
    "02_angular_side.jpg": (
        "https://live.staticflickr.com/4123/4938255450_9d60b9d45c_b.jpg",
        "https://www.flickr.com/photos/eekim/4938255450/",
        "SSH angular side view (Eugene Kim)"
    ),
    "03_metallic_facade.jpg": (
        "https://live.staticflickr.com/65535/48545567762_e7cc54cba2_b.jpg",
        "https://www.flickr.com/photos/mateox/48545567762/",
        "Metallic angular facade detail (Matthew X. Kiernan)"
    ),
    "04_facade_variation.jpg": (
        "https://live.staticflickr.com/65535/48545566812_fbe9103f7c_b.jpg",
        "https://www.flickr.com/photos/mateox/48545566812/",
        "Facade variation angle (Matthew X. Kiernan)"
    ),
    "05_facade_variation2.jpg": (
        "https://live.staticflickr.com/65535/48545566157_59b71258d0_b.jpg",
        "https://www.flickr.com/photos/mateox/48545566157/",
        "Facade variation second angle (Matthew X. Kiernan)"
    ),
    "06_architectural_detail.jpg": (
        "https://live.staticflickr.com/3775/11831862943_e799411164_b.jpg",
        "https://www.flickr.com/photos/collageman/11831862943/",
        "Architectural angular forms (Steve Heimerle)"
    ),
    "07_material_texture.jpg": (
        "https://live.staticflickr.com/8508/8569877209_059c572ec6_b.jpg",
        "https://www.flickr.com/photos/thomasmichaelart/8569877209/",
        "Material texture closeup (Thomas Gillaspy)"
    ),
    "08_tower_detail.jpg": (
        "https://live.staticflickr.com/5700/21365200772_4417f16aec_b.jpg",
        "https://www.flickr.com/photos/enerva/21365200772/",
        "Tower detail (Sonny Abesamis)"
    ),
    "09_tower_upward.jpg": (
        "https://live.staticflickr.com/5723/21376009295_b2726b1772_b.jpg",
        "https://www.flickr.com/photos/enerva/21376009295/",
        "Tower upward angle (Sonny Abesamis)"
    ),
    "10_context_view.jpg": (
        "https://live.staticflickr.com/65535/50988047501_bbb3044669_b.jpg",
        "https://www.flickr.com/photos/whsieh78/50988047501/",
        "Context location view (Wayne Hsieh)"
    ),
    "11_afternoon_light.jpg": (
        "https://live.staticflickr.com/65535/25133181340_9709b74430_b.jpg",
        "https://www.flickr.com/photos/t-y-k/25133181340/",
        "Afternoon light study on facade (TiffK)"
    ),
}


def download_flickr(results):
    """Download from Flickr static CDN."""
    print("── Flickr ──")
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

    download_flickr(results)

    # Write urls.txt for attribution
    urls_path = DEST / "urls.txt"
    with open(urls_path, "w", encoding="utf-8") as f:
        f.write("# SSH 'Death Star' Building — Reference Image Sources\n")
        f.write("# Flickr only (no Wikimedia Commons coverage)\n")
        f.write("# Antoine Predock, 1989. Angular metallic + concrete.\n\n")
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
    total = len(FLICKR)
    print(f"Downloading {total} reference images for SSH Death Star...\n")
    download_all()
