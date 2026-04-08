# fix_adapter_osm_id.py - Fix None osm_id handling in adapter.py
path = r'REDACTED_PATH\builddavis-world\src\builddavis\adapter.py'
with open(path, 'r', encoding='utf-8') as f:
    src = f.read()

old = '        osm_id     = int(props.get("osm_id", node_id_counter[0]))'
new = '        _raw_osm_id = props.get("osm_id")\n        osm_id     = int(_raw_osm_id) if _raw_osm_id is not None else node_id_counter[0]'

if old in src:
    src = src.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(src)
    print("PATCHED OK")
else:
    print("NOT FOUND")
    idx = src.find('osm_id     = int(')
    print(repr(src[max(0,idx-50):idx+100]))
