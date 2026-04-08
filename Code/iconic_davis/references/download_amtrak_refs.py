"""
Download reference images for Davis Amtrak Station (ICONIC-001, Landmark #1).

Usage:
    python Code/iconic_davis/references/download_amtrak_refs.py

Downloads 8 images from Wikimedia Commons into:
    Code/iconic_davis/references/davis_amtrak_station/
"""

import os
import time
import urllib.request
import urllib.parse
from pathlib import Path

DEST = Path(__file__).parent / "davis_amtrak_station"

# {local_filename: Wikimedia Commons filename}
IMAGES = {
    "01_front_facade_2022.jpg":
        "Davis Amtrak station - June 2022 - Sarah Stierch.jpg",
    "02_front_classic_2017.jpg":
        "Davis station, November 2017.JPG",
    "03_west_side_2017.jpg":
        "Davis station facing west, November 2017.JPG",
    "04_north_side_2017.jpg":
        "North side of Davis station, November 2017.JPG",
    "05_sp_signage_2017.jpg":
        "Southern Pacific signage at Davis station, November 2017.JPG",
    "06_platform_context_2017.jpg":
        "Unused platform at Davis station, November 2017.JPG",
    "07_depot_detail.jpg":
        "Davis Train Depot 21 - panoramio.jpg",
    "08_depot_wide.jpg":
        "Davis Train Depot 22 - panoramio.jpg",
}

USER_AGENT = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"


def download_all():
    DEST.mkdir(parents=True, exist_ok=True)
    results = []

    for local_name, wiki_name in IMAGES.items():
        dest_path = DEST / local_name
        if dest_path.exists() and dest_path.stat().st_size > 10_000:
            size_kb = dest_path.stat().st_size / 1024
            print(f"  [{local_name}] ... SKIP (already {size_kb:.0f} KB)")
            encoded = urllib.parse.quote(wiki_name.replace(" ", "_"))
            url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{encoded}"
            results.append((local_name, wiki_name, url, True))
            continue
        encoded = urllib.parse.quote(wiki_name.replace(" ", "_"))
        url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{encoded}"

        print(f"  [{local_name}] ...", end=" ", flush=True)
        try:
            # Use Wikimedia API to get the direct image URL (avoids 429 on Special:FilePath)
            api_url = (
                "https://en.wikipedia.org/w/api.php?action=query&titles=File:"
                + urllib.parse.quote(wiki_name.replace(" ", "_"))
                + "&prop=imageinfo&iiprop=url&iiurlwidth=2048&format=json"
            )
            api_req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(api_req, timeout=15) as api_resp:
                import json
                api_data = json.loads(api_resp.read())
            pages = api_data.get("query", {}).get("pages", {})
            img_url = None
            for page in pages.values():
                for ii in page.get("imageinfo", []):
                    # prefer thumburl (2048px wide) to dodge rate limits on originals
                    img_url = ii.get("thumburl") or ii.get("url")
            if not img_url:
                raise RuntimeError("Could not resolve image URL via API")

            req = urllib.request.Request(img_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            dest_path.write_bytes(data)
            size_kb = len(data) / 1024
            print(f"OK  ({size_kb:.0f} KB)")
            results.append((local_name, wiki_name, url, True))
        except Exception as e:
            print(f"FAILED  ({e})")
            results.append((local_name, wiki_name, url, False))

        time.sleep(2)  # polite delay — Wikimedia rate-limits aggressively

    # Write urls.txt for attribution
    urls_path = DEST / "urls.txt"
    with open(urls_path, "w", encoding="utf-8") as f:
        f.write("# Davis Amtrak Station — Reference Image Sources\n")
        f.write("# Downloaded from Wikimedia Commons (CC-licensed, educational use)\n\n")
        for local_name, wiki_name, url, ok in results:
            status = "OK" if ok else "FAILED"
            page = f"https://commons.wikimedia.org/wiki/File:{urllib.parse.quote(wiki_name.replace(' ', '_'))}"
            f.write(f"{local_name}\n  Source: {page}\n  Status: {status}\n\n")

    ok_count = sum(1 for *_, ok in results if ok)
    fail_count = len(results) - ok_count
    print(f"\nDone: {ok_count}/{len(results)} downloaded to {DEST}")
    if fail_count:
        print(f"  {fail_count} failed — check urls.txt")
    print(f"\nTIP: Add your own Google Earth screenshot as 09_aerial.jpg")


if __name__ == "__main__":
    print(f"Downloading {len(IMAGES)} reference images for Davis Amtrak Station...\n")
    download_all()
