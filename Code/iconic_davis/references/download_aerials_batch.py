#!/usr/bin/env python3
"""Download aerial reference images for Davis landmarks from Wikimedia Commons.

Most Davis landmarks have NO aerial/drone photos on Flickr.
This script grabs the few that exist on Wikimedia.
For all others, user should add Google Earth screenshots.
"""

import urllib.request, json, pathlib

UA = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"
BASE = pathlib.Path(__file__).parent


def download_wikimedia(folder: str, filename: str, title: str) -> None:
    dst_dir = BASE / folder
    dst_dir.mkdir(exist_ok=True)
    dst = dst_dir / filename
    if dst.exists():
        print(f"  SKIP {folder}/{filename} (exists)")
        return
    api = (
        "https://en.wikipedia.org/w/api.php?action=query"
        f"&titles=File:{urllib.request.quote(title)}"
        "&prop=imageinfo&iiprop=url&iiurlwidth=2048&format=json"
    )
    req = urllib.request.Request(api, headers={"User-Agent": UA})
    info = json.loads(urllib.request.urlopen(req).read())
    page = next(iter(info["query"]["pages"].values()))
    url = page["imageinfo"][0].get("thumburl", page["imageinfo"][0]["url"])
    req2 = urllib.request.Request(url, headers={"User-Agent": UA})
    data = urllib.request.urlopen(req2).read()
    dst.write_bytes(data)
    print(f"  OK  {folder}/{filename} ({len(data)//1024}KB) [Wikimedia]")


def download_flickr(folder: str, filename: str, url: str) -> None:
    dst_dir = BASE / folder
    dst_dir.mkdir(exist_ok=True)
    dst = dst_dir / filename
    if dst.exists():
        print(f"  SKIP {folder}/{filename} (exists)")
        return
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    data = urllib.request.urlopen(req).read()
    dst.write_bytes(data)
    print(f"  OK  {folder}/{filename} ({len(data)//1024}KB) [Flickr]")


# --- Wikimedia aerial images of UC Davis ---
WIKIMEDIA_AERIALS = [
    # Aerial view of UC Davis — entire campus from above (2005)
    ("mondavi_center",    "aerial_overhead.jpg", "Aerial_view_of_UC_Davis_(cropped).jpg"),
    ("memorial_union",    "aerial_overhead.jpg", "Aerial_view_of_UC_Davis_(cropped).jpg"),
    ("shields_library",   "aerial_overhead.jpg", "Aerial_view_of_UC_Davis_(cropped).jpg"),
    ("ssh_deathstar",     "aerial_overhead.jpg", "Aerial_view_of_UC_Davis_(cropped).jpg"),
    ("the_silo",          "aerial_overhead.jpg", "Aerial_view_of_UC_Davis_(cropped).jpg"),
    ("bike_barn",         "aerial_overhead.jpg", "Aerial_view_of_UC_Davis_(cropped).jpg"),
    ("lake_spafford",     "aerial_overhead.jpg", "Aerial_view_of_UC_Davis_(cropped).jpg"),
    ("egghead_sculptures","aerial_overhead.jpg", "Aerial_view_of_UC_Davis_(cropped).jpg"),

    # UC Davis Health Stadium drone view 2024 (CC BY 4.0, Quintin Soloviev)
    ("aggie_stadium",     "aerial_drone_2024.jpg", "UC_Davis_Health_Stadium_drone_view_2024.jpg"),
]

# --- Flickr aerial-ish images ---
FLICKR_AERIALS = [
    # Ian Abbott — 1983 campus aerial (archival but shows layout)
    ("arboretum_waterway", "aerial_campus_1983.jpg",
     "https://live.staticflickr.com/5477/10946462944_7e090760da_b.jpg"),
]


if __name__ == "__main__":
    print("Downloading aerial images for Davis landmarks...")
    print()

    # Wikimedia aerials
    for folder, fname, title in WIKIMEDIA_AERIALS:
        try:
            download_wikimedia(folder, fname, title)
        except Exception as e:
            print(f"  FAIL {folder}/{fname}: {e}")

    # Flickr aerials
    for folder, fname, url in FLICKR_AERIALS:
        try:
            download_flickr(folder, fname, url)
        except Exception as e:
            print(f"  FAIL {folder}/{fname}: {e}")

    print()
    print("=" * 60)
    print("LANDMARKS STILL NEEDING USER AERIAL (Google Earth screenshots):")
    print("=" * 60)
    needs_aerial = [
        "arboretum_waterway (campus aerial added but needs closeup)",
        "central_park",
        "covell_bicycle_overpass",
        "davis_food_coop",
        "davis_municipal_golf",
        "dresbach_mansion",
        "e_street_plaza",
        "el_macero_golf",
        "Farmers Market",
        "flying_carousel",
        "i80_richards_interchange",
        "mace_ranch",
        "manor_pool",
        "old_east_davis",
        "putah_creek",
        "richards_underpass",
        "slide_hill_park",
        "sycamore_park_skatepark",
        "unitrans_bus (bus depot/yard)",
        "village_homes",
        "whole_earth_festival (UC Davis Quad)",
        "wildhorse_golf",
        "yolo_causeway",
    ]
    for name in needs_aerial:
        print(f"  [ ] {name}")
    print()
    print("Done.")
