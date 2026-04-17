BBOX_LAT_MIN, BBOX_LAT_MAX = 38.530, 38.555
BBOX_LON_MIN, BBOX_LON_MAX = -121.760, -121.725
WORLD_X, WORLD_Z = 3043, 2779

towers = [
    (378657301, 38.5350885, -121.750919, 'UC Davis tower 1 (operator=university of california davis)'),
    (378657446, 38.5379203, -121.7592702, 'UC Davis tower 2 (operator=UC Davis)'),
]
for osm_id, lat, lon, name in towers:
    x = (lon - BBOX_LON_MIN) / (BBOX_LON_MAX - BBOX_LON_MIN) * WORLD_X
    z = (1 - (lat - BBOX_LAT_MIN) / (BBOX_LAT_MAX - BBOX_LAT_MIN)) * WORLD_Z
    # center the 33x33 structure: subtract half footprint (16)
    origin_x = int(x) - 16
    origin_z = int(z) - 16
    print(f'{name}')
    print(f'  OSM: {osm_id}, lat={lat}, lon={lon}')
    print(f'  MC centroid: X={int(x)}, Z={int(z)}')
    print(f'  Structure origin (top-left): X={origin_x}, Z={origin_z}')
    print()
