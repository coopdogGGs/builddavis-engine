import urllib.request
import json

CANDIDATE_URLS = [
    "https://gis.ucdavis.edu/server/rest/services/Grounds_Tree_Database/MapServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=geojson&resultRecordCount=2",
    "https://gis.ucdavis.edu/server/rest/services/Grounds_Tree_Database/FeatureServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=geojson&resultRecordCount=2",
    "https://services1.arcgis.com/r9Mg8HKGmFKdTerH/arcgis/rest/services/UC_Davis_Trees/FeatureServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=geojson&resultRecordCount=2",
    "https://services1.arcgis.com/r9Mg8HKGmFKdTerH/arcgis/rest/services/Grounds_Tree_Database/FeatureServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=geojson&resultRecordCount=2",
]

print("Testing UC Davis tree API endpoints...")

working_url = None

for url in CANDIDATE_URLS:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BuildDavis/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        feats = data.get("features", [])
        if feats:
            fields = list(feats[0].get("properties", {}).keys())
            print("WORKS:", url[:90])
            print("Fields:", fields)
            for k, v in list(feats[0].get("properties", {}).items())[:12]:
                print("  ", k, "=", v)
            working_url = url.replace("&resultRecordCount=2", "")
            break
        else:
            print("EMPTY:", url[:90])
    except Exception as e:
        print("FAIL:", url[:70], "->", str(e)[:80])

print()
if working_url:
    print("SUCCESS - Working URL:")
    print(working_url)
    path = r'REDACTED_PATH\builddavis-world\src\builddavis\fetch_ucdavis_trees.py'
    try:
        with open(path, 'r', encoding='utf-8') as f:
            src = f.read()
        idx_start = src.find('UCDAVIS_TREE_API = (')
        idx_end = src.find('\n)', idx_start) + 2
        if idx_start > 0:
            old_block = src[idx_start:idx_end]
            new_block = 'UCDAVIS_TREE_API = (\n    "' + working_url + '"\n)'
            src = src.replace(old_block, new_block)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(src)
            print("fetch_ucdavis_trees.py patched with correct URL")
        else:
            print("URL block not found - set UCDAVIS_TREE_API manually")
    except Exception as e:
        print("Patch failed:", e)
else:
    print("ALL URLS FAILED - check https://data-ucda.opendata.arcgis.com/ manually")
