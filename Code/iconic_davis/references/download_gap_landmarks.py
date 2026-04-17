#!/usr/bin/env python3
"""Download reference images for 5 GAP landmarks.

Wildhorse Golf, Village Homes, Sycamore Park Skatepark, Manor Pool, Mace Ranch.
Educational/research reference use only.
"""

import pathlib, urllib.request, ssl, time, sys

BASE = pathlib.Path(__file__).parent

# Disable SSL verification for educational downloads
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

LANDMARKS = {
    "wildhorse_golf": [
        ("01_clubhouse.jpg",        "https://www.wildhorsegolfclub.com/images/galleries/course/clubhouse.jpg"),
        ("02_clubhouse_alt.jpg",    "https://www.wildhorsegolfclub.com/images/galleries/course/wildhorse-clubhouse.jpg"),
        ("03_front_sign.jpg",       "https://www.wildhorsegolfclub.com/images/galleries/course/front-sign.jpg"),
        ("04_carts.jpg",            "https://www.wildhorsegolfclub.com/images/galleries/course/carts.jpg"),
        ("05_fairway_1.jpg",        "https://www.wildhorsegolfclub.com/images/galleries/course/gallery-new-1.jpg"),
        ("06_fairway_2.jpg",        "https://www.wildhorsegolfclub.com/images/galleries/course/gallery-new-2.jpg"),
        ("07_fairway_3.jpg",        "https://www.wildhorsegolfclub.com/images/galleries/course/gallery-new-3.jpg"),
        ("08_hole_pg01.jpg",        "https://www.wildhorsegolfclub.com/images/galleries/course/pg01.jpg"),
        ("09_hole_pg06.jpg",        "https://www.wildhorsegolfclub.com/images/galleries/course/pg06.jpg"),
        ("10_hole_pg10.jpg",        "https://www.wildhorsegolfclub.com/images/galleries/course/pg10.jpg"),
        ("11_clubhouse_thumb.png",  "https://www.wildhorsegolfclub.com/images/buttons/clubhouse-image-button-new.png"),
    ],

    "village_homes": [
        ("01_overview.jpg",         "https://localwiki.org/davis/Village_Homes/_files/village.jpg"),
        ("02_vineyards.jpg",        "https://localwiki.org/davis/Village_Homes/_files/vinyard.jpg"),
        ("03_garden_belt.jpg",      "https://localwiki.org/davis/Village_Homes/_files/gbelt.jpg"),
        ("04_community_center.jpg", "https://localwiki.org/davis/Village_Homes/_files/cc.jpg"),
        ("05_park.jpg",             "https://localwiki.org/davis/Village_Homes/_files/park.jpg"),
        ("06_plaque.jpg",           "https://localwiki.org/davis/Village_Homes/_files/Village_Homes_Plaque.JPG"),
        ("07_garden_1.jpg",         "https://localwiki.org/davis/Village_Homes/_files/flow2.jpg"),
        ("08_garden_2.jpg",         "https://localwiki.org/davis/Village_Homes/_files/flow.jpg"),
        ("09_street_diagram.jpg",   "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6d/Village_Homes_Street_Network_Diagram.jpg/800px-Village_Homes_Street_Network_Diagram.jpg"),
        ("10_drainage_swale.jpg",   "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Grass_lined_channel_NRCS.jpg/800px-Grass_lined_channel_NRCS.jpg"),
        ("11_site_plan.gif",        "https://www.context.org/wp-content/uploads/icimages/vhplan.gif"),
        ("12_cross_section.gif",    "https://www.context.org/wp-content/uploads/icimages/vhsect.gif"),
    ],

    "sycamore_park_skatepark": [
        # Davis Public Skate Park (in Community Park on F St)
        ("01_funbox.jpg",           "https://localwiki.org/davis/Public_Skate_Park/_files/skate.jpg"),
        ("02_wide_view.jpg",        "https://localwiki.org/davis/Public_Skate_Park/_files/skate2.jpg"),
        ("03_crater_rail.jpg",      "https://localwiki.org/davis/Public_Skate_Park/_files/Skate_Park_1.JPG"),
        ("04_culvert_pool.jpg",     "https://localwiki.org/davis/Public_Skate_Park/_files/Skate_Park_2.JPG"),
        # Sycamore Park itself
        ("05_playground.jpg",       "https://localwiki.org/davis/Sycamore_Park/_files/playground.JPG"),
        ("06_play_small.jpg",       "https://localwiki.org/davis/Sycamore_Park/_files/wikiwesh1205.jpg"),
        ("07_play_big.jpg",         "https://localwiki.org/davis/Sycamore_Park/_files/wikiwesh1206.jpg"),
        ("08_park_view.jpg",        "https://localwiki.org/davis/Sycamore_Park/_files/wikiwesh1207.jpg"),
    ],

    "manor_pool": [
        ("01_splash_pad.jpg",       "https://localwiki.org/davis/Manor_Pool/_files/sprinklers.jpg"),
        ("02_water_slide.jpg",      "https://localwiki.org/davis/Manor_Pool/_files/slide.jpg"),
        ("03_diving_pool.jpg",      "https://localwiki.org/davis/Manor_Pool/_files/manor%20diving%20pool.jpg"),
        ("04_concrete_slide.jpg",   "https://localwiki.org/davis/Manor_Park_or_Slide_Hill_Park/_files/slide_hill.jpg"),
        ("05_panoramic.jpg",        "https://localwiki.org/davis/Manor_Park_or_Slide_Hill_Park/_files/Slide_Hill_Pano_1.JPG"),
        ("06_park_view_1.jpg",      "https://localwiki.org/davis/Manor_Park_or_Slide_Hill_Park/_files/slidehill001.jpg"),
        ("07_park_view_2.jpg",      "https://localwiki.org/davis/Manor_Park_or_Slide_Hill_Park/_files/slidehill002.jpg"),
        ("08_park_view_3.jpg",      "https://localwiki.org/davis/Manor_Park_or_Slide_Hill_Park/_files/slidehill003.jpg"),
        ("09_park_view_4.jpg",      "https://localwiki.org/davis/Manor_Park_or_Slide_Hill_Park/_files/slidehill004.jpg"),
        ("10_park_view_5.jpg",      "https://localwiki.org/davis/Manor_Park_or_Slide_Hill_Park/_files/slidehill005.jpg"),
        ("11_park_view_6.jpg",      "https://localwiki.org/davis/Manor_Park_or_Slide_Hill_Park/_files/slidehill006.jpg"),
        ("12_park_view_7.jpg",      "https://localwiki.org/davis/Manor_Park_or_Slide_Hill_Park/_files/slidehill007.jpg"),
    ],

    "mace_ranch": [
        ("01_entrance_sign.jpg",    "https://localwiki.org/davis/Mace_Ranch/_files/Mace_Ranch_Sign_Disrepair.JPG"),
        ("02_bike_path.jpg",        "https://localwiki.org/davis/Mace_Ranch/_files/dscp1133.jpg"),
        ("03_park_play_area.jpg",   "https://localwiki.org/davis/Mace_Ranch_Park/_files/Mace_Ranch_Park_Play_Area.JPG"),
        ("04_habitat_sign.jpg",     "https://localwiki.org/davis/Mace_Ranch_Park/_files/Mace_Ranch_Habitat_Area_Sign.JPG"),
        ("05_solar_spiral.jpg",     "https://localwiki.org/davis/Mace_Ranch_Park/_files/Mace_Ranch_Spiral.JPG"),
        ("06_gazebo.jpg",           "https://localwiki.org/davis/Mace_Ranch_Park_Gazebo/_files/Mace_Ranch_Park_Gazebo.JPG"),
        ("07_barovetto_park.jpg",   "https://localwiki.org/davis/John_Barovetto_Park/_files/john1.jpg"),
        ("08_barovetto_bball.jpg",  "https://localwiki.org/davis/John_Barovetto_Park/_files/john2.jpg"),
        ("09_barovetto_fog.jpg",    "https://localwiki.org/davis/John_Barovetto_Park/_files/fogseasonbyWesHardaker.jpg"),
        ("10_explorit_bldg.jpg",    "https://localwiki.org/davis/Explorit_Science_Center/_files/Explorit_Mace_Park_Branch.JPG"),
        ("11_explorit_sign.jpg",    "https://localwiki.org/davis/Explorit_Science_Center/_files/sign.jpg"),
    ],
}


def download(url: str, dst: pathlib.Path) -> bool:
    """Download a single file. Returns True on success."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            data = resp.read()
        if len(data) < 500:
            return False
        dst.write_bytes(data)
        return True
    except Exception as e:
        print(f"    ERROR: {e}")
        return False


def main():
    total = sum(len(v) for v in LANDMARKS.values())
    print(f"Downloading reference images for {len(LANDMARKS)} landmarks ({total} images)...\n")

    done = 0
    failed = 0

    for folder, images in sorted(LANDMARKS.items()):
        dst_dir = BASE / folder
        dst_dir.mkdir(exist_ok=True)
        print(f"  [{folder}] ({len(images)} images)")

        for filename, url in images:
            dst = dst_dir / filename
            if dst.exists():
                print(f"    SKIP {filename}")
                done += 1
                continue

            ok = download(url, dst)
            if ok:
                kb = dst.stat().st_size // 1024
                print(f"    OK   {filename} ({kb}KB)")
                done += 1
            else:
                print(f"    FAIL {filename}")
                failed += 1

            time.sleep(0.3)  # polite delay

        print()

    print(f"Done: {done} downloaded, {failed} failed (of {total} total)")


if __name__ == "__main__":
    main()
