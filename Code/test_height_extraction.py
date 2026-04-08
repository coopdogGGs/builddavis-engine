"""Quick integration test: verify extract_building_heights works with a known building."""
import json
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from pathlib import Path
from lidar import extract_building_heights

tmpdir = Path("../data/test_heights")
tmpdir.mkdir(exist_ok=True)

# Create a tiny test DEM/DSM with known building height
west, south, east, north = -121.74, 38.540, -121.738, 38.542
w, h = 200, 200
transform = from_bounds(west, south, east, north, w, h)

# DTM = flat at 15m
dtm = np.full((h, w), 15.0, dtype=np.float32)
# DSM = 15m ground + 6m building in center block
dsm = dtm.copy()
dsm[80:120, 80:120] = 21.0  # 6m tall building

profile = dict(driver="GTiff", height=h, width=w, count=1, dtype="float32",
               crs="EPSG:4326", transform=transform, nodata=-9999.0)

dem_path = str(tmpdir / "test_dem.tif")
dsm_path = str(tmpdir / "test_dsm.tif")
with rasterio.open(dem_path, "w", **profile) as dst:
    dst.write(dtm, 1)
with rasterio.open(dsm_path, "w", **profile) as dst:
    dst.write(dsm, 1)

# Create a building footprint that precisely covers the elevated area
# Elevated block is pixels 80:120 out of 200 → 40% to 60% of the raster extent
bldg_west  = west  + (east - west) * 0.40    # col 80
bldg_east  = west  + (east - west) * 0.60    # col 120
bldg_north = north - (north - south) * 0.40  # row 80
bldg_south = north - (north - south) * 0.60  # row 120
bldg_coords = [
    [bldg_west, bldg_south], [bldg_east, bldg_south],
    [bldg_east, bldg_north], [bldg_west, bldg_north],
    [bldg_west, bldg_south]
]
geojson = {
    "type": "FeatureCollection",
    "features": [{
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [bldg_coords]},
        "properties": {"type": "building", "osm_id": 12345, "id": "12345"}
    }]
}
geojson_path = str(tmpdir / "test_fused.geojson")
with open(geojson_path, "w") as f:
    json.dump(geojson, f)

# Run extraction
result = extract_building_heights(
    geojson_path, dem_path, dsm_path,
    str(tmpdir / "test_heights.json")
)

print("Processed:", result["buildings_processed"])
print("Roof shapes:", result["roof_shapes"])

# Check output
with open(tmpdir / "test_heights.json") as f:
    heights = json.load(f)

for k, v in heights.items():
    print("Building %s: height=%.1fm, roof=%s, orientation=%s, conf=%.2f" % (
        k, v["height_m"], v["roof_shape"], v["roof_orientation"], v["roof_confidence"]
    ))
    assert 5.0 < v["height_m"] < 7.0, "Height should be ~6m"
    assert v["roof_shape"] == "flat", "Synthetic box roof should be flat"
    print("PASS: Height and roof shape correct!")

# Cleanup
import shutil
shutil.rmtree(tmpdir)
print("Integration test PASSED")
