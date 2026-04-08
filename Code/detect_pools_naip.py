"""
detect_pools_naip.py — Detect swimming pools from NAIP aerial imagery
=====================================================================
Downloads 4-band NAIP imagery (0.6m) from Microsoft Planetary Computer,
computes NDWI (Normalized Difference Water Index) to identify swimming
pools, and outputs pool polygons for the BuildDavis pipeline.

NDWI = (Green - NIR) / (Green + NIR)
Water surfaces (pools) absorb NIR strongly, so NDWI > 0.3 for pools.
Pools are filtered by area (15-80 m² residential, up to 500 m² public).

Usage:
    python detect_pools_naip.py --bbox "38.544,-121.742,38.556,-121.728" \\
                                --output REDACTED_PATH\\BuildDavis\\poc7\\data
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.warp import transform as warp_transform
from rasterio.windows import from_bounds
from scipy import ndimage
from shapely.geometry import shape
from shapely.ops import unary_union

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("detect_pools")

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"

# NDWI threshold — water surfaces
NDWI_POOL_THRESHOLD = 0.3

# Pool area filters (in m²)
MIN_POOL_AREA_M2 = 12       # ~3x4m small pool / spa
MAX_POOL_AREA_M2 = 600      # large public/community pool
RESIDENTIAL_MAX_M2 = 80     # typical backyard pool upper bound

# Morphological settings
CLOSE_KERNEL_SIZE = 3        # small kernel — pools are compact


def find_naip_image(bbox_wsen: list[float]) -> tuple[str, str]:
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
    return href, str(year)


def detect_pools(bbox_wsen, image_url):
    """Detect pool polygons from NAIP imagery using NDWI."""
    west, south, east, north = bbox_wsen

    with rasterio.open(image_url) as src:
        image_crs = src.crs
        log.info("  Image CRS: %s, size: %dx%d", src.crs, src.width, src.height)

        # Reproject bbox to image CRS if needed
        if str(src.crs) != "EPSG:4326":
            xs = [west, east, west, east]
            ys = [south, south, north, north]
            xs_t, ys_t = warp_transform("EPSG:4326", src.crs, xs, ys)
            win_west, win_east = min(xs_t), max(xs_t)
            win_south, win_north = min(ys_t), max(ys_t)
        else:
            win_west, win_south, win_east, win_north = west, south, east, north

        window = from_bounds(win_west, win_south, win_east, win_north, src.transform)

        # NAIP bands: R=1, G=2, B=3, NIR=4
        green = src.read(2, window=window).astype(np.float32)
        nir = src.read(4, window=window).astype(np.float32)
        transform = src.window_transform(window)

    log.info("  Window: %d x %d pixels", green.shape[1], green.shape[0])

    # Compute NDWI: (Green - NIR) / (Green + NIR)
    denom = green + nir
    ndwi = np.where(denom > 0, (green - nir) / denom, 0.0)

    # Pool mask: high NDWI
    pool_mask = (ndwi >= NDWI_POOL_THRESHOLD).astype(np.uint8)

    # Morphological close to fill small gaps within pool surfaces
    kernel = np.ones((CLOSE_KERNEL_SIZE, CLOSE_KERNEL_SIZE), dtype=np.uint8)
    pool_mask = ndimage.binary_closing(pool_mask, structure=kernel).astype(np.uint8)

    pool_pixels = np.sum(pool_mask)
    total_pixels = pool_mask.size
    log.info("  Water pixels: %d / %d (%.2f%%)",
             pool_pixels, total_pixels, 100.0 * pool_pixels / total_pixels)

    # Vectorize pool mask to polygons
    pool_shapes = list(shapes(pool_mask, mask=pool_mask == 1, transform=transform))
    log.info("  Raw water polygons: %d", len(pool_shapes))

    # Filter by area
    polys = []
    for geom_dict, value in pool_shapes:
        poly = shape(geom_dict)
        area_m2 = poly.area  # CRS units (metres for UTM)
        if area_m2 < MIN_POOL_AREA_M2:
            continue
        if area_m2 > MAX_POOL_AREA_M2:
            log.debug("  Skipping large water body: %.0f m²", area_m2)
            continue
        polys.append(poly)

    log.info("  Pool polygons after area filter: %d (%.0f-%d m²)",
             len(polys), MIN_POOL_AREA_M2, MAX_POOL_AREA_M2)

    if not polys:
        return []

    # Simplify and reproject to WGS84
    result = []
    for poly in polys:
        simplified = poly.simplify(0.5, preserve_topology=True)
        if simplified.is_empty:
            continue

        coords = list(simplified.exterior.coords)
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]

        if str(image_crs) != "EPSG:4326":
            lons, lats = warp_transform(image_crs, "EPSG:4326", xs, ys)
        else:
            lons, lats = xs, ys

        wgs84_coords = list(zip(lons, lats))
        area_m2 = poly.area

        pool_type = "residential" if area_m2 <= RESIDENTIAL_MAX_M2 else "public"

        result.append({
            "coords": wgs84_coords,
            "area_m2": round(area_m2, 1),
            "pool_type": pool_type,
        })

    # Sort by area descending for logging
    result.sort(key=lambda p: p["area_m2"], reverse=True)

    return result


def to_overpass_ways(pools, start_id=9_900_000):
    """Convert pool polygons to Overpass way + node format."""
    nodes = []
    ways = []
    node_id = start_id
    way_id = start_id

    for pool in pools:
        way_node_ids = []
        for lon, lat in pool["coords"]:
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
                "leisure": "swimming_pool",
                "source": "naip_ndwi_detection",
                "access": "private" if pool["pool_type"] == "residential" else "yes",
            },
        })
        way_id += 1

    return nodes, ways


def to_geojson(pools, output_path):
    """Write pool detections as GeoJSON."""
    features = []
    for p in pools:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [p["coords"]],
            },
            "properties": {
                "leisure": "swimming_pool",
                "area_m2": p["area_m2"],
                "pool_type": p["pool_type"],
            },
        })
    geojson = {"type": "FeatureCollection", "features": features}
    with open(output_path, "w") as f:
        json.dump(geojson, f)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Detect swimming pools from NAIP imagery")
    parser.add_argument("--bbox", required=True,
                        help="Bounding box: south,west,north,east")
    parser.add_argument("--output", required=True,
                        help="Output directory")
    parser.add_argument("--ndwi-threshold", type=float, default=NDWI_POOL_THRESHOLD,
                        help=f"NDWI threshold (default: {NDWI_POOL_THRESHOLD})")
    args = parser.parse_args()

    parts = [float(x) for x in args.bbox.split(",")]
    south, west, north, east = parts
    bbox_wsen = [west, south, east, north]

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    log.info("Detecting swimming pools from NAIP imagery")
    log.info("  bbox: S=%.4f W=%.4f N=%.4f E=%.4f", south, west, north, east)

    # 1. Find NAIP image
    image_url, year = find_naip_image(bbox_wsen)

    # 2. Detect pools
    log.info("Reading NAIP window (Green + NIR bands)...")
    pools = detect_pools(bbox_wsen, image_url)
    log.info("Pools detected: %d", len(pools))

    if pools:
        areas = [p["area_m2"] for p in pools]
        residential = sum(1 for p in pools if p["pool_type"] == "residential")
        public = sum(1 for p in pools if p["pool_type"] == "public")
        total_area = sum(areas)
        log.info("  Residential: %d, Public/community: %d", residential, public)
        log.info("  Area range: %.0f - %.0f m² (total: %.0f m²)",
                 min(areas), max(areas), total_area)

    # 3. Write outputs
    geojson_path = to_geojson(pools, output_dir / "naip_pools.geojson")
    log.info("GeoJSON: %s", geojson_path)

    nodes, ways = to_overpass_ways(pools)
    overpass_data = {"nodes": nodes, "ways": ways}
    overpass_path = output_dir / "naip_pools_overpass.json"
    with open(overpass_path, "w") as f:
        json.dump(overpass_data, f)
    log.info("Overpass: %s (%d pools, %d nodes)", overpass_path, len(ways), len(nodes))

    return pools


if __name__ == "__main__":
    main()
