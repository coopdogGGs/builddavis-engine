#!/usr/bin/env python3
"""Download reference images for Yolo Causeway (Davis/Sacramento, CA).

The Yolo Causeway is a 3.1-mile elevated highway crossing the Yolo Bypass
floodplain between Davis and Sacramento. Both I-80 and the railroad use it.
"""

import urllib.request, os, pathlib

FOLDER = pathlib.Path(__file__).parent / "yolo_causeway"
FOLDER.mkdir(exist_ok=True)

UA = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

# Avoid: Alexander Kozik (B&W film), marleneleeart (pen sketches)
FLICKR = {
    # Patrick Dirden — "The Capitol at West Causeway" — train on elevated causeway
    "01_capitol_west_causeway.jpg": "https://live.staticflickr.com/65535/49489840688_95d14de6e1_b.jpg",
    # John Benner — "Amtrak #5 on the Yolo Causeway" — train crossing
    "02_amtrak_causeway.jpg": "https://live.staticflickr.com/4208/34904858272_8f36224ba8_b.jpg",
    # sdttds — "Flooded Yolo Bypass at Dusk" — flooded bypass landscape
    "03_flooded_bypass.jpg": "https://live.staticflickr.com/572/31466580543_3a1862e1f4_b.jpg",
    # Jake Miille — "Sunrise Starlight" — Amtrak on causeway at sunrise
    "04_sunrise_starlight.jpg": "https://live.staticflickr.com/65535/52998114324_f81687287a_b.jpg",
    # Greg Brown — "Ten Spirited Miles" — causeway landscape
    "05_ten_spirited_miles.jpg": "https://live.staticflickr.com/65535/53901093797_3dcb399728_b.jpg",
}


def download(filename: str, url: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    data = urllib.request.urlopen(req).read()
    dst = FOLDER / filename
    dst.write_bytes(data)
    print(f"  OK  {filename} ({len(data)//1024}KB) [Flickr]")


def write_urls_txt() -> None:
    lines = [
        "# Yolo Causeway — Reference Image Sources",
        "# Flickr (educational reference use)",
        "# 3.1-mile elevated highway crossing Yolo Bypass between Davis and Sacramento.",
        "",
    ]
    flickr_pages = {
        "01_capitol_west_causeway.jpg": "https://www.flickr.com/photos/sp8254/49489840688/",
        "02_amtrak_causeway.jpg":       "https://www.flickr.com/photos/23375206@N05/34904858272/",
        "03_flooded_bypass.jpg":        "https://www.flickr.com/photos/36618387@N06/31466580543/",
        "04_sunrise_starlight.jpg":     "https://www.flickr.com/photos/amtrakdavis22/52998114324/",
        "05_ten_spirited_miles.jpg":    "https://www.flickr.com/photos/goatboat/53901093797/",
    }
    for fname, page in flickr_pages.items():
        lines += [f"{fname}", f"  Source: Flickr", f"  Page: {page}", ""]
    (FOLDER / "urls.txt").write_text("\n".join(lines), encoding="utf-8")
    print("  urls.txt written")


if __name__ == "__main__":
    print("Downloading Yolo Causeway reference images...")
    for fname, url in FLICKR.items():
        try:
            download(fname, url)
        except Exception as e:
            print(f"  FAIL {fname}: {e}")
    write_urls_txt()
    print("Done.")
