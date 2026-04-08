#!/usr/bin/env python3
"""Download reference images for Unitrans double-decker bus (Davis, CA).

Unitrans is the student-run transit system at UC Davis, famous for its
fleet of vintage London double-decker buses (AEC Regent III RT) and
modern Alexander Dennis Enviro500 double-deckers alongside standard fleet.
"""

import urllib.request, os, pathlib

FOLDER = pathlib.Path(__file__).parent / "unitrans_bus"
FOLDER.mkdir(exist_ok=True)

UA = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

# --- Flickr images (direct static CDN, _b = 1024px) ---
FLICKR = {
    # Kevin Nelson — Enviro double-decker full side profile, daytime
    "01_doubledecker_daytime.jpg": "https://live.staticflickr.com/5226/5668409946_92de596099_b.jpg",
    # So Cal Metro — Alexander Dennis Enviro500 double-decker, March 2025
    "02_enviro500_doubledecker.jpg": "https://live.staticflickr.com/65535/54398683190_789da63fb9_b.jpg",
    # So Cal Metro — Orion V on Lake Blvd, Davis street context
    "03_orion_lake_blvd.jpg": "https://live.staticflickr.com/65535/51934793966_3f0c31b0d7_b.jpg",
    # So Cal Metro — New Flyer Xcelsior XN40, modern fleet
    "04_xcelsior_xn40.jpg": "https://live.staticflickr.com/697/21120366032_d2ea9b6bff_b.jpg",
    # So Cal Metro — Orion V front angle in Davis
    "05_orion_v_front.jpg": "https://live.staticflickr.com/592/21104295436_85c8a784e6_b.jpg",
    # So Cal Metro — New Flyer XN40 downtown Davis, March 2025
    "06_xn40_downtown.jpg": "https://live.staticflickr.com/65535/54398011569_9cc0897c36_b.jpg",
    # bravoinsd — Orion bus at Davis stop
    "07_orion_at_stop.jpg": "https://live.staticflickr.com/205/464724428_33964c264c_b.jpg",
    # Michael Choe — wide campus shot with New Flyers (Nikon D80)
    "08_campus_wide.jpg": "https://live.staticflickr.com/7076/7301044180_4caabf6765_b.jpg",
}


def download(filename: str, url: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    data = urllib.request.urlopen(req).read()
    dst = FOLDER / filename
    dst.write_bytes(data)
    print(f"  OK  {filename} ({len(data)//1024}KB) [Flickr]")


def write_urls_txt() -> None:
    lines = [
        "# Unitrans Double-Decker Bus — Reference Image Sources",
        "# Flickr (educational reference use)",
        "# UC Davis student-run transit with vintage London double-deckers.",
        "",
    ]
    flickr_pages = {
        "01_doubledecker_daytime.jpg":        "https://www.flickr.com/photos/knelson27/5668409946/",
        "02_enviro500_doubledecker.jpg":      "https://www.flickr.com/photos/southerncalifornian/54398683190/",
        "03_orion_lake_blvd.jpg":             "https://www.flickr.com/photos/southerncalifornian/51934793966/",
        "04_xcelsior_xn40.jpg":               "https://www.flickr.com/photos/southerncalifornian/21120366032/",
        "05_orion_v_front.jpg":               "https://www.flickr.com/photos/southerncalifornian/21104295436/",
        "06_xn40_downtown.jpg":               "https://www.flickr.com/photos/southerncalifornian/54398011569/",
        "07_orion_at_stop.jpg":               "https://www.flickr.com/photos/sandiegobravo/464724428/",
        "08_campus_wide.jpg":                 "https://www.flickr.com/photos/79634636@N05/7301044180/",
    }
    for fname, page in flickr_pages.items():
        lines += [f"{fname}", f"  Source: Flickr", f"  Page: {page}", ""]
    (FOLDER / "urls.txt").write_text("\n".join(lines), encoding="utf-8")
    print("  urls.txt written")


if __name__ == "__main__":
    print("Downloading Unitrans reference images...")
    for fname, url in FLICKR.items():
        try:
            download(fname, url)
        except Exception as e:
            print(f"  FAIL {fname}: {e}")
    write_urls_txt()
    print("Done.")
