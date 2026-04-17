#!/usr/bin/env python3
"""Download reference images for Whole Earth Festival (UC Davis, CA).

Annual sustainability/arts festival held on the UC Davis Quad. Features
stages, vendor booths, art installations, and communal gathering spaces.
"""

import urllib.request, os, pathlib

FOLDER = pathlib.Path(__file__).parent / "whole_earth_festival"
FOLDER.mkdir(exist_ok=True)

UA = "BuildDavis/1.0 (educational Minecraft project; contact: coopdogGGs)"

FLICKR = {
    # hkirschner2016 — UC Davis Whole Earth Festival 2016 (wide quad overview)
    "01_wef_quad_overview.jpg": "https://live.staticflickr.com/7355/26609065580_08a3742479_b.jpg",
    # mama2em — Face Painting at WEF (crowd scene, booth context)
    "02_face_painting_booth.jpg": "https://live.staticflickr.com/226/497066704_8c96b40356_b.jpg",
    # Chris Dunphy — WEF Stage View (stage + quad context)
    "03_stage_view.jpg": "https://live.staticflickr.com/48/172345184_dfde8d08f0_b.jpg",
    # Chris Dunphy — WEF Dancing (crowd activity, wide)
    "04_dancing_spinning.jpg": "https://live.staticflickr.com/59/172346339_8339ee19cd_b.jpg",
    # jennifer hardwick — Whole Earth Festival (wide, booth layout)
    "05_vendor_booths.jpg": "https://live.staticflickr.com/4029/4622301344_2c7e277792_b.jpg",
    # sdttds — WEFers (festival crowd, UC Davis Quad)
    "06_wef_crowd.jpg": "https://live.staticflickr.com/65535/52073181804_eea3a92317_b.jpg",
    # sdttds — WEFers (another crowd angle)
    "07_wef_gathering.jpg": "https://live.staticflickr.com/65535/52101066144_078d775427_b.jpg",
}


def download(filename: str, url: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    data = urllib.request.urlopen(req).read()
    dst = FOLDER / filename
    dst.write_bytes(data)
    print(f"  OK  {filename} ({len(data)//1024}KB) [Flickr]")


def write_urls_txt() -> None:
    lines = [
        "# Whole Earth Festival — Reference Image Sources",
        "# Flickr (educational reference use)",
        "# Annual sustainability/arts festival on the UC Davis Quad.",
        "",
    ]
    flickr_pages = {
        "01_wef_quad_overview.jpg":  "https://www.flickr.com/photos/57738665@N04/26609065580/",
        "02_face_painting_booth.jpg":"https://www.flickr.com/photos/mama2em/497066704/",
        "03_stage_view.jpg":         "https://www.flickr.com/photos/radven/172345184/",
        "04_dancing_spinning.jpg":   "https://www.flickr.com/photos/radven/172346339/",
        "05_vendor_booths.jpg":      "https://www.flickr.com/photos/jenniferhardwick/4622301344/",
        "06_wef_crowd.jpg":          "https://www.flickr.com/photos/36618387@N06/52073181804/",
        "07_wef_gathering.jpg":      "https://www.flickr.com/photos/36618387@N06/52101066144/",
    }
    for fname, page in flickr_pages.items():
        lines += [f"{fname}", f"  Source: Flickr", f"  Page: {page}", ""]
    (FOLDER / "urls.txt").write_text("\n".join(lines), encoding="utf-8")
    print("  urls.txt written")


if __name__ == "__main__":
    print("Downloading Whole Earth Festival reference images...")
    for fname, url in FLICKR.items():
        try:
            download(fname, url)
        except Exception as e:
            print(f"  FAIL {fname}: {e}")
    write_urls_txt()
    print("Done.")
