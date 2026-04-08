import os

adapter_path = r'REDACTED_PATH\builddavis-world\src\builddavis\adapter.py'

with open(adapter_path, 'r', encoding='utf-8') as f:
    src = f.read()

OLD = (
    '    for feat in features:\n'
    '        stats.total_elements += 1\n'
    '        props      = feat if not feat.get("properties") else feat["properties"]\n'
    '        osm_id     = int(props.get("osm_id", node_id_counter[0]))'
)

NEW = (
    '    for feat in features:\n'
    '        stats.total_elements += 1\n'
    '        if feat.get("type") == "Feature":\n'
    '            props = dict(feat.get("properties") or {})\n'
    '            geojson_geom = feat.get("geometry") or {}\n'
    '            geom_kind = geojson_geom.get("type", "")\n'
    '            raw_coords = geojson_geom.get("coordinates", [])\n'
    '            if not props.get("coords") and raw_coords:\n'
    '                if geom_kind == "Polygon": props["coords"] = raw_coords[0]\n'
    '                elif geom_kind == "LineString": props["coords"] = raw_coords\n'
    '                elif geom_kind == "Point":\n'
    '                    props["lon"] = raw_coords[0]\n'
    '                    props["lat"] = raw_coords[1]\n'
    '        else:\n'
    '            props = feat\n'
    '        osm_id     = int(props.get("osm_id", node_id_counter[0]))'
)

if OLD not in src:
    print('ERROR: target text not found in adapter.py')
    print('First 50 chars of loop area:')
    idx = src.find('for feat in features')
    print(repr(src[idx:idx+200]))
else:
    patched = src.replace(OLD, NEW)
    with open(adapter_path, 'w', encoding='utf-8') as f:
        f.write(patched)
    print('PATCHED OK - lines now:', len(patched.split('\n')))
