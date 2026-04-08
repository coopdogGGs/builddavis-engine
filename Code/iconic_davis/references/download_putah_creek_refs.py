#!/usr/bin/env python3
"""Download reference images for Putah Creek corridor (Davis, CA).

Putah Creek runs along the southern edge of UC Davis and downtown Davis.
The greenway includes walking/biking trails, riparian corridor, bridges,
and is part of the UC Davis Arboretum GATEway Garden.
"""

import urllib.request, json, os, pathlib

FOLDER = pathlib.Path(__file__).parent / "putah_creek"
FOLDER.mkdir(exist_ok=True)

UA = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

# --- Wikimedia Commons images ---
WIKIMEDIA = {
    # Wide creek corridor + bridge structure
    "01_creek_wide.jpg": "Putah_Creek_-_University_of_California,_Davis_-_DSC03437.JPG",
    "02_creek_bridge.jpg": "Putah_Creek_bridge_-_University_of_California,_Davis_-_DSC03405.JPG",
}

# --- Flickr images (direct static CDN, _b = 1024px) ---
# Curated for: daytime, color, wide shots showing creek banks/bridges/trails
FLICKR = {
    # Ian Abbott — wide arboretum view from footbridge (CC BY-NC-SA 2.0, Nikon D3100)
    "03_arboretum_from_bridge.jpg": "https://live.staticflickr.com/457/18204885569_1a2420fae9_b.jpg",
    # David Heaphy — footbridge across Putah Creek (wide, structural ref)
    "04_footbridge.jpg": "https://live.staticflickr.com/4264/35831497495_b0479e12f2_b.jpg",
    # Captain.Ferg — wide creek from footbridge, banks & canopy visible
    "05_creek_wide_banks.jpg": "https://live.staticflickr.com/2148/2546250489_6de3ceb3d9_b.jpg",
    # Donna S — Putah Creek reflections, bank shape/vegetation
    "06_creek_reflections.jpg": "https://live.staticflickr.com/1369/1111183552_b60f3fea51_b.jpg",
    # sdttds — recently restored Putah Creek section (wide, modern)
    "07_restored_creek.jpg": "https://live.staticflickr.com/65535/54790028466_a8c743efec_b.jpg",
    # miwa. — creek near lodge, water level and banks (CC BY-NC-SA 2.0)
    "08_creek_near_lodge.jpg": "https://live.staticflickr.com/1289/641197648_f3dc83ce99_b.jpg",
}


def download_wikimedia(filename: str, title: str) -> None:
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
    dst = FOLDER / filename
    dst.write_bytes(data)
    print(f"  OK  {filename} ({len(data)//1024}KB) [Wikimedia]")


def download_flickr(filename: str, url: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    data = urllib.request.urlopen(req).read()
    dst = FOLDER / filename
    dst.write_bytes(data)
    print(f"  OK  {filename} ({len(data)//1024}KB) [Flickr]")


def write_urls_txt() -> None:
    lines = [
        "# Putah Creek Corridor — Reference Image Sources",
        "# Wikimedia Commons + Flickr (educational reference use)",
        "# Creek corridor along south edge of UC Davis / downtown Davis.",
        "",
    ]
    for fname, title in WIKIMEDIA.items():
        lines += [
            f"{fname}",
            f"  Source: Wikimedia Commons",
            f"  Page: https://commons.wikimedia.org/wiki/File:{title}",
            f"  License: CC",
            "",
        ]
    flickr_pages = {
        "03_arboretum_from_bridge.jpg": "https://www.flickr.com/photos/ian_e_abbott/18204885569/",
        "04_footbridge.jpg":            "https://www.flickr.com/photos/dsh1492/35831497495/",
        "05_creek_wide_banks.jpg":      "https://www.flickr.com/photos/cptferg/2546250489/",
        "06_creek_reflections.jpg":     "https://www.flickr.com/photos/disneyite/1111183552/",
        "07_restored_creek.jpg":        "https://www.flickr.com/photos/36618387@N06/54790028466/",
        "08_creek_near_lodge.jpg":      "https://www.flickr.com/photos/meerar/641197648/",
    }
    for fname, page in flickr_pages.items():
        lines += [f"{fname}", f"  Source: Flickr", f"  Page: {page}", ""]
    (FOLDER / "urls.txt").write_text("\n".join(lines), encoding="utf-8")
    print("  urls.txt written")


if __name__ == "__main__":
    print("Downloading Putah Creek reference images...")
    for fname, title in WIKIMEDIA.items():
        try:
            download_wikimedia(fname, title)
        except Exception as e:
            print(f"  FAIL {fname}: {e}")
    for fname, url in FLICKR.items():
        try:
            download_flickr(fname, url)
        except Exception as e:
            print(f"  FAIL {fname}: {e}")
    write_urls_txt()
    print("Done.")
