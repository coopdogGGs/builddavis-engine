"""
detect_grass_naip.py — Detect grass/lawn areas from NAIP aerial imagery
========================================================================
Uses the same NDVI pipeline as detect_trees_naip.py but targets lower
NDVI values (0.15-0.35) that indicate grass/lawn rather than tree canopy.
Outputs simplified polygons as GeoJSON and Overpass ways for Arnis.

Usage:
    python detect_grass_naip.py --bbox "38.544,-121.742,38.556,-121.728" \
                                --output REDACTED_PATH\\BuildDavis\\poc6\\data

Author: BuildDavis Project
License: Apache 2.0
"""

import argparse
import json
import logging
import math
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds
from rasterio.features import shapes
from rasterio.warp import transform as warp_transform
from scipy import ndimage
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("detect_grass")

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"

# NDVI thresholds for grass detection
NDVI_GRASS_MIN = 0.15     # below this is bare soil/pavement
NDVI_GRASS_MAX = 0.35     # above this is tree canopy
MIN_GRASS_AREA_M2 = 25    # ignore tiny patches (< 5m x 5m)
SIMPLIFY_TOLERANCE = 0.00003  # ~3m simplification in degrees


def find_naip_image(bbox_wsen: list[float]) -> str:
    """Query Planetary Computer for the most recent NAIP image covering bbox."""
    import requests
    body = {
        "collections": ["naip"],
        "bbox": bbox_wsen,
        "limit": 1,
        "sortby": [{"field": "datetime", "direction": "desc"}]
    }
    r = requests.post(STAC_URL, json=body, timeout=30)
    r.raise_for_status()
    data = r.json()
    features = data.get("features", [])
    if not features:
        raise RuntimeError(f"No NAIP imagery found for bbox {bbox_wsen}")
    href = features[0]["assets"]["image"]["href"]
    year = features[0]["properties"].get("naip:year", "?")
    log.info("NAIP image: %s (year=%s)", href.split("/")[-1], year)
    return href


def detect_grass_polygons(bbox_wsen, image_url):
    """
    Detect grass areas from NAIP NDVI and return as WGS84 Shapely polygons.
    """
    west, south, east, north = bbox_wsen

    with rasterio.open(image_url) as src:
        image_crs = src.crs

        # Reproject bbox to image CRS
        if str(image_crs) != "EPSG:4326":
            xs = [west, east, west, east]
            ys = [south, south, north, north]
            xs_t, ys_t = warp_transform("EPSG:4326", image_crs, xs, ys)
            win_west, win_east = min(xs_t), max(xs_t)
            win_south, win_north = min(ys_t), max(ys_t)
        else:
            win_west, win_south, win_east, win_north = west, south, east, north

        window = from_bounds(win_west, win_south, win_east, win_north, src.transform)

        red = src.read(1, window=window).astype(np.float32)
        nir = src.read(4, window=window).astype(np.float32)
        transform = src.window_transform(window)

    log.info("  Window: %d x %d pixels", red.shape[1], red.shape[0])

    # Compute NDVI
    denom = nir + red
    ndvi = np.where(denom > 0, (nir - red) / denom, 0.0)

    # Grass mask: NDVI between grass thresholds
    grass_mask = ((ndvi >= NDVI_GRASS_MIN) & (ndvi < NDVI_GRASS_MAX)).astype(np.uint8)

    # Morphological close to fill small gaps within lawns
    kernel = np.ones((5, 5), dtype=np.uint8)
    grass_mask = ndimage.binary_closing(grass_mask, structure=kernel).astype(np.uint8)

    grass_pixels = np.sum(grass_mask)
    total_pixels = grass_mask.size
    log.info("  Grass pixels: %d / %d (%.1f%%)",
             grass_pixels, total_pixels, 100.0 * grass_pixels / total_pixels)

    # Vectorize grass mask to polygons (in image CRS)
    grass_shapes = list(shapes(grass_mask, mask=grass_mask == 1, transform=transform))
    log.info("  Raw grass polygons: %d", len(grass_shapes))

    # Convert to Shapely, reproject to WGS84, filter by area
    polys = []
    pixel_area = abs(transform.a * transform.e)

    for geom_dict, value in grass_shapes:
        poly = shape(geom_dict)
        area_m2 = poly.area  # in CRS units (metres for UTM)
        if area_m2 < MIN_GRASS_AREA_M2:
            continue
        polys.append(poly)

    log.info("  Grass polygons after area filter: %d", len(polys))

    if not polys:
        return []

    # Merge overlapping polygons
    merged = unary_union(polys)
    if merged.geom_type == "Polygon":
        merged_list = [merged]
    elif merged.geom_type == "MultiPolygon":
        merged_list = list(merged.geoms)
    else:
        merged_list = []

    log.info("  After merge: %d polygons", len(merged_list))

    # Reproject to WGS84 and simplify
    result = []
    for poly in merged_list:
        # Simplify in CRS units (metres)
        simplified = poly.simplify(3.0, preserve_topology=True)
        if simplified.is_empty:
            continue

        # Reproject exterior ring to WGS84
        coords = list(simplified.exterior.coords)
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]

        if str(image_crs) != "EPSG:4326":
            lons, lats = warp_transform(image_crs, "EPSG:4326", xs, ys)
        else:
            lons, lats = xs, ys

        wgs84_coords = list(zip(lons, lats))
        area_m2 = poly.area  # still in CRS units

        result.append({
            "coords": wgs84_coords,
            "area_m2": round(area_m2, 1),
        })

    return result


def to_overpass_ways(grass_polys, start_id=9_800_000):
    """Convert grass polygons to Overpass way + node format."""
    nodes = []
    ways = []
    node_id = start_id
    way_id = start_id

    for poly in grass_polys:
        way_node_ids = []
        for lon, lat in poly["coords"]:
            nodes.append({
                "type": "node",
                "id": node_id,
                "lat": lat,
                "lon": lon,
                "tags": {},
            })
            way_node_ids.append(node_id)
            node_id += 1

        ways.append({
            "type": "way",
            "id": way_id,
            "nodes": way_node_ids,
            "tags": {
                "landuse": "grass",
                "source": "naip_ndvi_detection",
                "surface": "grass",
            },
        })
        way_id += 1

    return nodes, ways


def main():
    parser = argparse.ArgumentParser(description="Detect grass from NAIP imagery")
    parser.add_argument("--bbox", required=True, help="south,west,north,east")
    parser.add_argument("--output", required=True, help="Output directory")
    args = parser.parse_args()

    parts = [float(x) for x in args.bbox.split(",")]
    south, west, north, east = parts
    bbox_wsen = [west, south, east, north]

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    log.info("Detecting grass from NAIP imagery")
    log.info("  bbox: S=%.4f W=%.4f N=%.4f E=%.4f", south, west, north, east)

    image_url = find_naip_image(bbox_wsen)

    log.info("Analyzing NDVI for grass areas...")
    grass_polys = detect_grass_polygons(bbox_wsen, image_url)
    log.info("Grass areas detected: %d", len(grass_polys))

    if grass_polys:
        areas = [p["area_m2"] for p in grass_polys]
        log.info("  Area range: %.0fm² - %.0fm², total: %.0fm²",
                 min(areas), max(areas), sum(areas))

    # Write GeoJSON
    features = []
    for p in grass_polys:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[lon, lat] for lon, lat in p["coords"]]]
            },
            "properties": {
                "landuse": "grass",
                "area_m2": p["area_m2"],
                "source": "naip_ndvi",
            }
        })
    geojson = {"type": "FeatureCollection", "features": features}
    geojson_path = output_dir / "naip_grass.geojson"
    with open(geojson_path, "w") as f:
        json.dump(geojson, f)
    log.info("GeoJSON: %s", geojson_path)

    # Write Overpass format for adapter injection
    nodes, ways = to_overpass_ways(grass_polys)
    overpass_path = output_dir / "naip_grass_overpass.json"
    with open(overpass_path, "w") as f:
        json.dump({"nodes": nodes, "ways": ways}, f)
    log.info("Overpass: %s (%d polygons, %d nodes)", overpass_path, len(ways), len(nodes))


if __name__ == "__main__":
    main()
