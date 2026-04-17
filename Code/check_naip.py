"""Quick script to check NAIP asset URLs."""
import requests
import json

url = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
body = {
    "collections": ["naip"],
    "bbox": [-121.742, 38.544, -121.728, 38.556],
    "limit": 1,
    "sortby": [{"field": "datetime", "direction": "desc"}]
}
r = requests.post(url, json=body, timeout=30)
data = r.json()
f = data["features"][0]
print("Date:", f["properties"]["datetime"])
print("GSD:", f["properties"]["gsd"])
assets = f.get("assets", {})
for k, v in assets.items():
    href = v.get("href", "?")
    typ = v.get("type", "?")
    print(f"  {k}: type={typ}")
    print(f"    {href[:180]}")
