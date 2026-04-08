# WARNING: Uses parse.py coordinate system (Amtrak station = MC origin 0,0).
# Outputs RELATIVE OFFSETS only — NOT absolute MC coords.
# DO NOT use these values for placement or /tp commands.
# For real placement coordinates use: python Code/mc_locate.py --name "..."

"""Find UC Davis water tower in OSM."""
import json, urllib.request, urllib.parse

query = """
[out:json][timeout:25];
(
  node["man_made"="water_tower"](38.53,-121.76,38.55,-121.74);
  way["man_made"="water_tower"](38.53,-121.76,38.55,-121.74);
);
out body;
>;
out skel qt;
"""

url = 'https://overpass-api.de/api/interpreter'
post_data = ('data=' + urllib.parse.quote(query.strip())).encode('utf-8')
req = urllib.request.Request(url, data=post_data, headers={'User-Agent': 'BuildDavis/1.0'})
resp = urllib.request.urlopen(req, timeout=60)
data = json.loads(resp.read())
for e in data['elements']:
    if e['type'] == 'node' and 'tags' in e:
        print(f"Node {e['id']}: {e.get('lat')}, {e.get('lon')} tags={e.get('tags',{})}")
    elif e['type'] == 'way' and 'tags' in e:
        print(f"Way {e['id']}: tags={e.get('tags',{})}")
        print(f"  nodes: {e.get('nodes',[])}")
    elif e['type'] == 'node':
        print(f"  node {e['id']}: {e.get('lat')}, {e.get('lon')}")
