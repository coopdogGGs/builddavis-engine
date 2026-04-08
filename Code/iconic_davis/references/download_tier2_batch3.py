#!/usr/bin/env python3
"""Download reference images for Tier 2 landmarks #48-52.

University House, Davis Cemetery, Stevenson Bridge,
Boy Scout Cabin, Scott House/Ciocolat.
"""

import pathlib, urllib.request, time, ssl

BASE = pathlib.Path(__file__).parent
ctx = ssl.create_default_context()

LANDMARKS = {
    "university_house": [
        # Flickr — petescully 2017
        ("https://live.staticflickr.com/2409/32986354776_703be9d877_b.jpg",
         "01_university_house_petescully_2017.jpg"),
        # Flickr — petescully 2013 sketch
        ("https://live.staticflickr.com/8370/8573115689_e47aa06852_b.jpg",
         "02_university_house_petescully_sketch.jpg"),
        # Flickr — petescully Oct 2024
        ("https://live.staticflickr.com/65535/54104546800_c6c5522360_b.jpg",
         "03_university_house_petescully_2024.jpg"),
        # Flickr — Matthew X. Kiernan
        ("https://live.staticflickr.com/65535/48545410661_3444df4390_b.jpg",
         "04_university_house_kiernan.jpg"),
    ],
    "davis_cemetery": [
        # LocalWiki — bright gate entrance
        ("https://localwiki.org/davis/Davis_Cemetery/_files/bright%20gate.jpg",
         "01_davis_cemetery_localwiki_gate.jpg"),
        # LocalWiki — cemetery grounds 2004
        ("https://localwiki.org/davis/Davis_Cemetery/_files/cemetery_view.jpg",
         "02_davis_cemetery_localwiki_grounds.jpg"),
        # LocalWiki — grounds coping shot
        ("https://localwiki.org/davis/Davis_Cemetery/_files/Brandon%20Long%20coping%20shot.jpg",
         "03_davis_cemetery_localwiki_grounds2.jpg"),
        # LocalWiki — blossoming trees
        ("https://localwiki.org/davis/Davis_Cemetery/_files/Blossoming%20Trees.jpg",
         "04_davis_cemetery_localwiki_blossoms.jpg"),
        # LocalWiki — solar panels
        ("https://localwiki.org/davis/Davis_Cemetery/_files/Solar.jpg",
         "05_davis_cemetery_localwiki_solar.jpg"),
        # LocalWiki — veterans day
        ("https://localwiki.org/davis/Davis_Cemetery/_files/Vet%20DAy%202011.jpg",
         "06_davis_cemetery_localwiki_vetsday.jpg"),
    ],
    "stevenson_bridge": [
        # LocalWiki — looking north, main shot
        ("https://localwiki.org/davis/Stevenson_Bridge/_files/Stevenson_Bridge_1.jpg",
         "01_stevenson_bridge_localwiki_north.jpg"),
        # LocalWiki — with bicyclist
        ("https://localwiki.org/davis/Stevenson_Bridge/_files/Stevenson_Bridge_2.jpg",
         "02_stevenson_bridge_localwiki_bicyclist.jpg"),
        # LocalWiki — view north
        ("https://localwiki.org/davis/Stevenson_Bridge/_files/brdige.jpg",
         "03_stevenson_bridge_localwiki_view_north.jpg"),
        # LocalWiki — column over Putah Creek
        ("https://localwiki.org/davis/Stevenson_Bridge/_files/column.jpg",
         "04_stevenson_bridge_localwiki_column.jpg"),
        # Flickr — Janet Kopper, hero shot (16 likes)
        ("https://live.staticflickr.com/7399/12917925903_e1f9ac41af_b.jpg",
         "05_stevenson_bridge_jkopper.jpg"),
        # Flickr — Duncan Smith, bridge photo
        ("https://live.staticflickr.com/7033/6800273007_b08970e3cb_b.jpg",
         "06_stevenson_bridge_duncansmith.jpg"),
        # Flickr — sdttds
        ("https://live.staticflickr.com/7080/7246743354_9cee82ce1c_b.jpg",
         "07_stevenson_bridge_sdttds.jpg"),
        # Flickr — Charlotte Romeo
        ("https://live.staticflickr.com/8376/29884168235_8af57e44c7_b.jpg",
         "08_stevenson_bridge_cromeo.jpg"),
    ],
    "boy_scout_cabin": [
        # LocalWiki — street view
        ("https://localwiki.org/davis/Boy_Scout_Cabin/_files/Boy_Scout_Cabin_Street.JPG",
         "01_boy_scout_cabin_localwiki_street.jpg"),
        # LocalWiki — lawn view
        ("https://localwiki.org/davis/Boy_Scout_Cabin/_files/Boy_Scout_Cabin_Lawn.JPG",
         "02_boy_scout_cabin_localwiki_lawn.jpg"),
        # LocalWiki — alternate
        ("https://localwiki.org/davis/Boy_Scout_Cabin/_files/bsc.jpg",
         "03_boy_scout_cabin_localwiki_alt.jpg"),
        # Flickr — Matthew X. Kiernan
        ("https://live.staticflickr.com/65535/48545085967_3075734483_b.jpg",
         "04_boy_scout_cabin_kiernan.jpg"),
        # Flickr — Rob Corder
        ("https://live.staticflickr.com/65535/54223790773_238e122d7f_b.jpg",
         "05_boy_scout_cabin_rocorder.jpg"),
        # Flickr — Wayne Hsieh
        ("https://live.staticflickr.com/65535/50988046551_ae9da7903a_b.jpg",
         "06_boy_scout_cabin_whsieh.jpg"),
        # Flickr — petescully (Log Cabin Gallery)
        ("https://live.staticflickr.com/8364/8341177256_ab4304967a_b.jpg",
         "07_boy_scout_cabin_petescully_gallery.jpg"),
    ],
    "scott_house_ciocolat": [
        # LocalWiki — Ciocolat on a June afternoon 2006 (daytime)
        ("https://localwiki.org/davis/Ciocolat/_files/Ciocolat06.jpg",
         "01_scott_house_localwiki_june2006.jpg"),
        # LocalWiki — view from street, Dec 2004 (daytime)
        ("https://localwiki.org/davis/Ciocolat/_files/ciocolateday.jpg",
         "02_scott_house_localwiki_streetview.jpg"),
    ],
}


def download(url, dst):
    """Download a single file with retries."""
    headers = {"User-Agent": "Mozilla/5.0 (educational research)"}
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                data = resp.read()
            dst.write_bytes(data)
            return len(data)
        except Exception as e:
            if attempt == 2:
                print(f"    FAIL: {e}")
                return 0
            time.sleep(2)
    return 0


def main():
    total_ok = total_fail = 0

    for landmark, images in LANDMARKS.items():
        folder = BASE / landmark
        folder.mkdir(exist_ok=True)
        print(f"\n{'='*60}")
        print(f"  {landmark} ({len(images)} images)")
        print(f"{'='*60}")

        for url, filename in images:
            dst = folder / filename
            if dst.exists():
                print(f"  SKIP {filename} (exists)")
                total_ok += 1
                continue
            size = download(url, dst)
            if size:
                print(f"  OK   {filename} ({size//1024}KB)")
                total_ok += 1
            else:
                total_fail += 1

        # Write urls.txt
        urls_file = folder / "urls.txt"
        with open(urls_file, "w") as f:
            f.write(f"# {landmark} reference images\n")
            for url, filename in images:
                f.write(f"{url}\n  -> {filename}\n")

    print(f"\n{'='*60}")
    print(f"  TOTAL: {total_ok} OK, {total_fail} failed")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
