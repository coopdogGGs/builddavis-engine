#!/usr/bin/env python3
"""Download reference images for Tier 2 landmarks #43-47.

North Hall, South Hall, Hart Hall, King Hall, The Pavilion at ARC.
"""

import pathlib, urllib.request, time, ssl

BASE = pathlib.Path(__file__).parent
ctx = ssl.create_default_context()

LANDMARKS = {
    "north_hall": [
        # LocalWiki — finished 1908, one of three original dormitories
        ("https://localwiki.org/davis/North_Hall/_files/NorthHall.jpg",
         "01_north_hall_localwiki_quad.jpg"),
        # Flickr — Michael Head, front facade
        ("https://live.staticflickr.com/8034/8057022609_ba8f373903_b.jpg",
         "02_north_hall_michael_head_front.jpg"),
        # Flickr — Michael Head, alternate angle
        ("https://live.staticflickr.com/8032/8057022304_c0d1a32746_b.jpg",
         "03_north_hall_michael_head_side.jpg"),
        # Flickr — Matthew X. Kiernan
        ("https://live.staticflickr.com/65535/48545407881_fbea457a32_b.jpg",
         "04_north_hall_kiernan.jpg"),
        # Flickr — petescully, front
        ("https://live.staticflickr.com/6191/6157534527_96aa2a9958_b.jpg",
         "05_north_hall_petescully_front.jpg"),
        # Flickr — petescully, rear
        ("https://live.staticflickr.com/5268/5615634408_3b9509e4d5_b.jpg",
         "06_north_hall_petescully_rear.jpg"),
    ],
    "south_hall": [
        # LocalWiki — built 1912, original dormitory
        ("https://localwiki.org/davis/South_Hall/_files/SouthHall.jpg",
         "01_south_hall_localwiki_sunny.jpg"),
        # LocalWiki — quad side
        ("https://localwiki.org/davis/South_Hall/_files/South_Hall_Quad_Side.JPG",
         "02_south_hall_localwiki_quad_side.jpg"),
        # Flickr — petescully sketch/drawing
        ("https://live.staticflickr.com/5256/5395194150_c0d4857bf7_b.jpg",
         "03_south_hall_petescully.jpg"),
        # Flickr — Michael Head
        ("https://live.staticflickr.com/8174/8057024021_2e887d8176_b.jpg",
         "04_south_hall_michael_head.jpg"),
        # Flickr — petescully recent 2024
        ("https://live.staticflickr.com/65535/54089910161_859316cbd7_b.jpg",
         "05_south_hall_petescully_2024.jpg"),
        # Flickr — Matthew X. Kiernan
        ("https://live.staticflickr.com/65535/48545409261_b9df072dd6_b.jpg",
         "06_south_hall_kiernan.jpg"),
    ],
    "hart_hall": [
        # LocalWiki — front view, typical
        ("https://localwiki.org/davis/Hart_Hall/_files/hart1.jpg",
         "01_hart_hall_localwiki_front.jpg"),
        # LocalWiki — 1952 archival photo
        ("https://localwiki.org/davis/Hart_Hall/_files/hart1952.jpg",
         "02_hart_hall_localwiki_1952.jpg"),
        # LocalWiki — courtyard
        ("https://localwiki.org/davis/Hart_Hall/_files/Hart_Courtyard.JPG",
         "03_hart_hall_localwiki_courtyard.jpg"),
        # LocalWiki — angle view
        ("https://localwiki.org/davis/Hart_Hall/_files/hart_angle.jpg",
         "04_hart_hall_localwiki_angle.jpg"),
        # Flickr — petescully 2023
        ("https://live.staticflickr.com/65535/52809528804_4b79062443_b.jpg",
         "05_hart_hall_petescully_2023.jpg"),
        # Flickr — petescully hero shot (12 likes)
        ("https://live.staticflickr.com/4316/35443566553_a419ea70e7_b.jpg",
         "06_hart_hall_petescully_hero.jpg"),
        # Flickr — sdttds 2024
        ("https://live.staticflickr.com/65535/54145871642_436d8f2940_b.jpg",
         "07_hart_hall_sdttds_2024.jpg"),
        # Flickr — petescully feb 2024
        ("https://live.staticflickr.com/65535/53550294463_4a488397da_b.jpg",
         "08_hart_hall_petescully_feb2024.jpg"),
    ],
    "king_hall": [
        # LocalWiki — main exterior
        ("https://localwiki.org/davis/King_Hall/_files/kinghall.jpg",
         "01_king_hall_localwiki_exterior.jpg"),
        # LocalWiki — school of law view
        ("https://localwiki.org/davis/King_Hall/_files/school.jpg",
         "02_king_hall_localwiki_school.jpg"),
        # LocalWiki — Dr. King terra cotta sculpture
        ("https://localwiki.org/davis/King_Hall/_files/drking.jpg",
         "03_king_hall_localwiki_sculpture.jpg"),
        # LocalWiki — 40th anniversary banner
        ("https://localwiki.org/davis/King_Hall/_files/King_40th_Banner.jpg",
         "04_king_hall_localwiki_banner.jpg"),
        # Flickr — Eric E Johnson, interior
        ("https://live.staticflickr.com/6119/6344349685_12f82e2380_b.jpg",
         "05_king_hall_ericejohnson_interior.jpg"),
        # Flickr — Eric E Johnson, exterior
        ("https://live.staticflickr.com/6096/6345098800_5658a9ec1f_b.jpg",
         "06_king_hall_ericejohnson_exterior.jpg"),
        # Flickr — Eric E Johnson, facade
        ("https://live.staticflickr.com/6225/6344350855_483e3e60d9_b.jpg",
         "07_king_hall_ericejohnson_facade.jpg"),
        # Flickr — funeralbell, School of Law exterior
        ("https://live.staticflickr.com/7442/11051207343_cb99e885d9_b.jpg",
         "08_king_hall_funeralbell_exterior.jpg"),
    ],
    "pavilion_arc": [
        # LocalWiki — Pavilion exterior from ARC entrance
        ("https://localwiki.org/davis/The_Pavilion_at_ARC/_files/pavillion1.jpg",
         "01_pavilion_arc_localwiki_exterior.jpg"),
        # LocalWiki — interior basketball
        ("https://localwiki.org/davis/The_Pavilion_at_ARC/_files/interiorbballpavillion.jpg",
         "02_pavilion_arc_localwiki_interior.jpg"),
        # LocalWiki — ARC building exterior
        ("https://localwiki.org/davis/Activities_and_Recreation_Center/_files/ARC.jpg",
         "03_arc_localwiki_exterior.jpg"),
        # LocalWiki — ARC alternate view
        ("https://localwiki.org/davis/Activities_and_Recreation_Center/_files/ARC1.jpg",
         "04_arc_localwiki_alternate.jpg"),
        # Flickr — 305 Seahill, ARC exterior
        ("https://live.staticflickr.com/5485/18690188778_982e749627_b.jpg",
         "05_arc_flickr_305seahill.jpg"),
        # Flickr — basketball game inside
        ("https://live.staticflickr.com/8580/16134000844_c65fb1d371_b.jpg",
         "06_pavilion_basketball_game.jpg"),
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
