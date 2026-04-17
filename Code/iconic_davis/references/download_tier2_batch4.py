#!/usr/bin/env python3
"""Download reference images for Tier 2D landmarks #52-56.

Mrak Hall, Davis Senior High, Sudwerk Brewery,
Nugget Markets, Vet Med Teaching Hospital.
"""

import pathlib, urllib.request, time, ssl

BASE = pathlib.Path(__file__).parent
ctx = ssl.create_default_context()

LANDMARKS = {
    "mrak_hall": [
        # LocalWiki — south side exterior
        ("https://localwiki.org/davis/Mrak_Hall/_files/mrak-south.jpg",
         "01_mrak_hall_localwiki_south.jpg"),
        # LocalWiki — west side at sunset through trees
        ("https://localwiki.org/davis/Mrak_Hall/_files/mrak-west-sunset.jpg",
         "02_mrak_hall_localwiki_sunset.jpg"),
        # LocalWiki — eggheads in front
        ("https://localwiki.org/davis/Mrak_Hall/_files/mrak-eggheads.jpg",
         "03_mrak_hall_localwiki_eggheads.jpg"),
        # Flickr — UC Davis admin building
        ("https://live.staticflickr.com/65535/49044181523_bedf7c71de_b.jpg",
         "04_mrak_hall_flickr_aerial.jpg"),
    ],
    "davis_senior_high": [
        # LocalWiki — library front view
        ("https://localwiki.org/davis/Davis_Senior_High_School/_files/dhslibrary.jpg",
         "01_davis_senior_high_localwiki_library.jpg"),
        # LocalWiki — campus exterior
        ("https://localwiki.org/davis/Davis_Senior_High_School/_files/Davis_SHS.JPG",
         "02_davis_senior_high_localwiki_campus.jpg"),
        # LocalWiki — library side view (Graham Kolbeins 2003)
        ("https://localwiki.org/davis/Davis_Senior_High_School/_files/dhs-library1.jpg",
         "03_davis_senior_high_localwiki_library_side.jpg"),
        # LocalWiki — old gym
        ("https://localwiki.org/davis/Davis_Senior_High_School/_files/gym.jpg",
         "04_davis_senior_high_localwiki_gym.jpg"),
        # LocalWiki — Blue Devil mascot
        ("https://localwiki.org/davis/Davis_Senior_High_School/_files/bluedevil.jpg",
         "05_davis_senior_high_localwiki_bluedevil.jpg"),
    ],
    "sudwerk_brewery": [
        # LocalWiki — main building exterior
        ("https://localwiki.org/davis/Sudwerk/_files/sudwerk.jpg",
         "01_sudwerk_localwiki_exterior.jpg"),
        # LocalWiki — fountain/patio
        ("https://localwiki.org/davis/Sudwerk/_files/fountain.jpg",
         "02_sudwerk_localwiki_fountain.jpg"),
        # LocalWiki — truck on I-80
        ("https://localwiki.org/davis/Sudwerk/_files/Truck.jpg",
         "03_sudwerk_localwiki_truck.jpg"),
        # LocalWiki — dollar drinks sign
        ("https://localwiki.org/davis/Sudwerk/_files/dollar_drinks.jpg",
         "04_sudwerk_localwiki_sign.jpg"),
        # LocalWiki — Oktoberfest
        ("https://localwiki.org/davis/Sudwerk/_files/photo.JPG",
         "05_sudwerk_localwiki_oktoberfest.jpg"),
        # LocalWiki — two liter steins on patio
        ("https://localwiki.org/davis/Sudwerk/_files/twolitersavage.jpg",
         "06_sudwerk_localwiki_patio.jpg"),
    ],
    "nugget_markets": [
        # LocalWiki — Covell store exterior
        ("https://localwiki.org/davis/Nugget_Markets/_files/Nugget.jpg",
         "01_nugget_localwiki_covell_exterior.jpg"),
        # LocalWiki — sandwich counter
        ("https://localwiki.org/davis/Nugget_Markets/_files/nugget_sandwiches.jpg",
         "02_nugget_localwiki_sandwiches.jpg"),
        # LocalWiki — cheese wheel at Mace location
        ("https://localwiki.org/davis/Nugget_Markets/_files/cheese_wheel.jpg",
         "03_nugget_localwiki_cheese_wheel.jpg"),
        # LocalWiki — root beer party kegs
        ("https://localwiki.org/davis/Nugget_Markets/_files/rbpk.jpg",
         "04_nugget_localwiki_rootbeer.jpg"),
    ],
    "vet_med_teaching_hospital": [
        # Flickr — UC Davis Vet Med exterior
        ("https://live.staticflickr.com/65535/48545410661_3444df4390_b.jpg",
         "01_vet_med_flickr_exterior.jpg"),
        # Wikimedia — Vet Med Teaching Hospital, UC Davis
        ("https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/VMTH_at_UC_Davis.jpg/1280px-VMTH_at_UC_Davis.jpg",
         "02_vet_med_wikimedia_vmth.jpg"),
        # Flickr — UC Davis School of Vet Med campus
        ("https://live.staticflickr.com/7399/12917925903_e1f9ac41af_b.jpg",
         "03_vet_med_flickr_campus.jpg"),
    ],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def download_all():
    for name, urls in LANDMARKS.items():
        dest = BASE / name
        dest.mkdir(exist_ok=True)
        # write urls.txt
        with open(dest / "urls.txt", "w") as f:
            for url, fname in urls:
                f.write(f"{url}\n  -> {fname}\n")
        # download images
        for url, fname in urls:
            out = dest / fname
            if out.exists():
                print(f"  SKIP {fname}")
                continue
            print(f"  GET  {fname}")
            req = urllib.request.Request(url, headers=HEADERS)
            try:
                with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
                    out.write_bytes(r.read())
            except Exception as e:
                print(f"  FAIL {fname}: {e}")
            time.sleep(0.5)
        print(f"[OK] {name}: {len(urls)} refs")

if __name__ == "__main__":
    download_all()
