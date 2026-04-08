#!/usr/bin/env python3
"""Download reference images for Tier 2 landmarks #38-42.

Historic City Hall, Anderson Bank Building, Davis Community Church,
Hattie Weber Museum, Crocker Nuclear Laboratory.
"""

import pathlib, urllib.request, time, ssl

BASE = pathlib.Path(__file__).parent
ctx = ssl.create_default_context()

LANDMARKS = {
    "historic_city_hall": [
        # LocalWiki — 226 F Street, Spanish Colonial Revival, built 1938
        ("https://localwiki.org/davis/Historic_City_Hall/_files/Historic_City_Hall.jpg",
         "01_historic_city_hall_front.jpg"),
        ("https://localwiki.org/davis/Historic_City_Hall/_files/IMG_3411.JPG",
         "02_historic_city_hall_detail.jpg"),
        ("https://localwiki.org/davis/Historic_City_Hall/_files/city%20hall%20illustrated.jpg",
         "03_historic_city_hall_illustrated.jpg"),
    ],
    "anderson_bank_building": [
        # LocalWiki — 203 G Street, built 1914 by JB Anderson
        ("https://localwiki.org/davis/Anderson_Bank_Building/_files/JB_Anderson_Building.JPG",
         "01_jb_anderson_entrance.jpg"),
        ("https://localwiki.org/davis/Anderson_Bank_Building/_files/sign.jpg",
         "02_anderson_tenant_sign.jpg"),
        ("https://localwiki.org/davis/Anderson_Bank_Building/_files/Lower_Windows_Sign.JPG",
         "03_anderson_lower_windows.jpg"),
    ],
    "davis_community_church": [
        # LocalWiki — 412 C Street, Mission style, 1926
        ("https://localwiki.org/davis/Davis_Community_Church/_files/belltower.jpg",
         "01_dcc_belltower.jpg"),
        ("https://localwiki.org/davis/Davis_Community_Church/_files/church.jpg",
         "02_dcc_exterior.jpg"),
        ("https://localwiki.org/davis/Davis_Community_Church/_files/cornerstone.jpg",
         "03_dcc_cornerstone_1926.jpg"),
        # Flickr — marleneleeart
        ("https://live.staticflickr.com/65535/53931411043_0abbc1bc52_b.jpg",
         "04_dcc_flickr_marleneleeart.jpg"),
    ],
    "hattie_weber_museum": [
        # LocalWiki — 445 C Street, built 1911, relocated to Central Park
        ("https://localwiki.org/davis/Hattie_Weber_Museum/_files/Hattie_Weber_sign.jpg",
         "01_hattie_weber_sign.jpg"),
        ("https://localwiki.org/davis/Hattie_Weber_Museum/_files/Hattie_Weber_front.jpg",
         "02_hattie_weber_front.jpg"),
        # Flickr photos
        ("https://live.staticflickr.com/65535/50185636076_9027896800_b.jpg",
         "03_hattie_weber_aug2020_petescully.jpg"),
        ("https://live.staticflickr.com/65535/50991715001_542f1d7eb3_b.jpg",
         "04_hattie_weber_whsieh.jpg"),
        ("https://live.staticflickr.com/65535/48544437091_d8b79ce63d_b.jpg",
         "05_hattie_weber_kiernan_01.jpg"),
        ("https://live.staticflickr.com/65535/48544587837_289e46e515_b.jpg",
         "06_hattie_weber_kiernan_02.jpg"),
        ("https://live.staticflickr.com/2517/4027745896_05d6250603_b.jpg",
         "07_hattie_weber_pappyv.jpg"),
        # Flickr sketches (petescully — good architectural detail)
        ("https://live.staticflickr.com/8381/28975395043_a2247f6a40_b.jpg",
         "08_hattie_weber_sketch_petescully.jpg"),
    ],
    "crocker_nuclear_lab": [
        # LocalWiki — UC Davis campus, built 1965, cyclotron facility
        ("https://localwiki.org/davis/Crocker_Nuclear_Laboratory/_files/crocker_nuclear_lab_05.jpg",
         "01_crocker_lab_front_2005.jpg"),
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

            print(f"  GET  {filename}...", end="", flush=True)
            size = download(url, dst)
            if size:
                print(f" OK ({size // 1024}KB)")
                total_ok += 1
            else:
                total_fail += 1
            time.sleep(1)

    print(f"\n\nDone: {total_ok} OK, {total_fail} failed")
    print("\nCoverage notes:")
    print("  historic_city_hall  — 3 images (LocalWiki only). GAP: needs user photos")
    print("  anderson_bank       — 3 images (LocalWiki only). GAP: needs user photos")
    print("  davis_community_ch  — 4 images (LocalWiki + Flickr)")
    print("  hattie_weber        — 8 images (LocalWiki + Flickr). Good coverage")
    print("  crocker_nuclear     — 1 image  (LocalWiki only). GAP: needs user photos")


if __name__ == "__main__":
    main()
