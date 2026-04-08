"""
detect_trees_naip.py — Detect tree locations from NAIP aerial imagery
=====================================================================
Downloads 4-band NAIP imagery (0.6m) from Microsoft Planetary Computer,
computes NDVI to identify vegetation canopy, and outputs tree point
locations as GeoJSON for the BuildDavis pipeline.

Usage:
    python detect_trees_naip.py --bbox "38.544,-121.742,38.556,-121.728" \
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
from scipy import ndimage

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("detect_trees")

# Microsoft Planetary Computer STAC endpoint
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"

# NDVI thresholds
NDVI_TREE_THRESHOLD = 0.35       # pixels above this are likely tree canopy
MIN_CANOPY_PIXELS = 4            # minimum cluster size (~1.4m² at 0.6m GSD)
MAX_CANOPY_PIXELS = 2500         # max cluster size to avoid parks/fields (~900m²)

# Davis street tree species distribution (for Arnis rendering)
TREE_SPECIES = [
    {"species": "Quercus lobata",       "genus": "Quercus",  "leaf_type": "broadleaved"},
    {"species": "Zelkova serrata",      "leaf_type": "broadleaved"},
    {"species": "Pistacia chinensis",   "leaf_type": "broadleaved"},
    {"species": "Liquidambar styraciflua", "leaf_type": "broadleaved"},
    {"species": "Platanus acerifolia",  "leaf_type": "broadleaved"},
    {"species": "Cedrus deodara",       "leaf_type": "needleleaved"},
    {"species": "Sequoia sempervirens", "leaf_type": "needleleaved"},
    {"species": "Pyrus calleryana",     "leaf_type": "broadleaved"},
]


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


def compute_ndvi(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """Compute NDVI from red and NIR bands. Returns array in [-1, 1]."""
    red = red.astype(np.float32)
    nir = nir.astype(np.float32)
    denom = nir + red
    ndvi = np.where(denom > 0, (nir - red) / denom, 0.0)
    return ndvi


def detect_canopy_centers(ndvi: np.ndarray, transform, src_crs=None) -> list[dict]:
    """
    Find tree canopy centers from NDVI raster.
    Returns list of {lon, lat, canopy_area_m2} dicts in WGS84.
    """
    from rasterio.warp import transform as warp_transform

    # Binary mask of high-NDVI pixels
    tree_mask = ndvi > NDVI_TREE_THRESHOLD

    # Label connected components
    labeled, num_features = ndimage.label(tree_mask)
    log.info("  NDVI clusters found: %d", num_features)

    # Find centroid of each cluster
    trees = []
    pixel_area = abs(transform.a * transform.e)  # m² per pixel (approximate)

    for label_id in range(1, num_features + 1):
        cluster_pixels = np.argwhere(labeled == label_id)
        n_pixels = len(cluster_pixels)

        # Filter by size
        if n_pixels < MIN_CANOPY_PIXELS:
            continue  # too small — noise or shrub
        if n_pixels > MAX_CANOPY_PIXELS:
            continue  # too large — park/field, not individual tree

        # Centroid in pixel coordinates (row, col)
        row_center = cluster_pixels[:, 0].mean()
        col_center = cluster_pixels[:, 1].mean()

        # Convert to geographic coordinates (in image CRS)
        x, y = rasterio.transform.xy(transform, row_center, col_center)

        trees.append({
            "x": x, "y": y,
            "canopy_area_m2": round(n_pixels * pixel_area, 1),
            "canopy_pixels": n_pixels,
        })

    # Reproject all centroids to WGS84 in one batch
    if trees and src_crs and str(src_crs) != "EPSG:4326":
        xs = [t["x"] for t in trees]
        ys = [t["y"] for t in trees]
        lons, lats = warp_transform(src_crs, "EPSG:4326", xs, ys)
        for i, t in enumerate(trees):
            t["lon"] = lons[i]
            t["lat"] = lats[i]
    else:
        for t in trees:
            t["lon"] = t.get("x", 0)
            t["lat"] = t.get("y", 0)

    return trees


def assign_species(trees: list[dict]) -> list[dict]:
    """Assign species tags to detected trees deterministically."""
    for i, tree in enumerate(trees):
        sp = TREE_SPECIES[i % len(TREE_SPECIES)]
        tree["tags"] = {
            "natural": "tree",
            "source": "naip_ndvi_detection",
            **sp,
        }
    return trees


def to_geojson(trees: list[dict], output_path: Path) -> Path:
    """Write tree detections as GeoJSON for the pipeline."""
    features = []
    for t in trees:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [t["lon"], t["lat"]]
            },
            "properties": {
                "natural": "tree",
                "canopy_area_m2": t["canopy_area_m2"],
                **t["tags"],
            }
        })
    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }
    with open(output_path, "w") as f:
        json.dump(geojson, f)
    return output_path


def to_overpass_nodes(trees: list[dict], start_id: int = 9_500_000) -> list[dict]:
    """Convert tree detections directly to Overpass node format."""
    nodes = []
    for i, t in enumerate(trees):
        nodes.append({
            "type": "node",
            "id": start_id + i,
            "lat": t["lat"],
            "lon": t["lon"],
            "tags": t["tags"],
        })
    return nodes


def main():
    parser = argparse.ArgumentParser(description="Detect trees from NAIP imagery")
    parser.add_argument("--bbox", required=True,
                        help="Bounding box: south,west,north,east")
    parser.add_argument("--output", required=True,
                        help="Output directory")
    parser.add_argument("--ndvi-threshold", type=float, default=NDVI_TREE_THRESHOLD,
                        help=f"NDVI threshold for tree detection (default: {NDVI_TREE_THRESHOLD})")
    args = parser.parse_args()

    # Parse bbox
    parts = [float(x) for x in args.bbox.split(",")]
    south, west, north, east = parts
    bbox_wsen = [west, south, east, north]  # STAC format

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    log.info("Detecting trees from NAIP imagery")
    log.info("  bbox: S=%.4f W=%.4f N=%.4f E=%.4f", south, west, north, east)

    # 1. Find NAIP image
    image_url = find_naip_image(bbox_wsen)

    # 2. Read just the bbox window from the Cloud-Optimized GeoTIFF
    log.info("Reading NAIP window (4 bands, 0.6m)...")
    with rasterio.open(image_url) as src:
        log.info("  Image CRS: %s, size: %dx%d", src.crs, src.width, src.height)

        # Reproject bbox from WGS84 to image CRS if needed
        if str(src.crs) != "EPSG:4326":
            from rasterio.warp import transform as warp_transform
            xs = [west, east, west, east]
            ys = [south, south, north, north]
            xs_t, ys_t = warp_transform("EPSG:4326", src.crs, xs, ys)
            win_west, win_east = min(xs_t), max(xs_t)
            win_south, win_north = min(ys_t), max(ys_t)
            log.info("  Reprojected bbox to %s: %.1f,%.1f,%.1f,%.1f",
                     src.crs, win_west, win_south, win_east, win_north)
        else:
            win_west, win_south, win_east, win_north = west, south, east, north

        # Create window for our bbox
        window = from_bounds(win_west, win_south, win_east, win_north, src.transform)
        log.info("  Window: %s", window)

        # Read bands: NAIP is typically R=1, G=2, B=3, NIR=4
        red = src.read(1, window=window)
        nir = src.read(4, window=window)
        transform = src.window_transform(window)
        image_crs = src.crs

    log.info("  Window size: %d x %d pixels (%.0f x %.0fm)",
             red.shape[1], red.shape[0],
             red.shape[1] * 0.6, red.shape[0] * 0.6)

    # 3. Compute NDVI
    log.info("Computing NDVI...")
    ndvi = compute_ndvi(red, nir)
    tree_pixels = np.sum(ndvi > args.ndvi_threshold)
    total_pixels = ndvi.size
    log.info("  Green canopy: %.1f%% of area (%d/%d pixels)",
             100 * tree_pixels / total_pixels, tree_pixels, total_pixels)

    # 4. Detect canopy centers
    log.info("Detecting individual tree canopies...")
    trees = detect_canopy_centers(ndvi, transform, src_crs=image_crs)
    trees = assign_species(trees)
    log.info("  Trees detected: %d", len(trees))

    if trees:
        areas = [t["canopy_area_m2"] for t in trees]
        log.info("  Canopy area: min=%.1fm², median=%.1fm², max=%.1fm²",
                 min(areas), sorted(areas)[len(areas)//2], max(areas))

    # 5. Write output
    geojson_path = to_geojson(trees, output_dir / "naip_trees.geojson")
    log.info("Output: %s", geojson_path)

    # Also write Overpass-format nodes for direct injection
    nodes = to_overpass_nodes(trees)
    nodes_path = output_dir / "naip_trees_overpass.json"
    with open(nodes_path, "w") as f:
        json.dump(nodes, f)
    log.info("Overpass nodes: %s (%d trees)", nodes_path, len(nodes))

    return trees


if __name__ == "__main__":
    main()
