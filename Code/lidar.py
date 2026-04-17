"""
BuildDavis Pipeline — Stage 2: LiDAR Terrain Processor
=======================================================
Takes the LiDAR tile manifest from Stage 1 (fetch.py) and produces a
seamless 1-metre Digital Elevation Model (DEM) covering the full Davis
bounding box.

Processing chain:
  1. Discover & download .laz point cloud tiles from USGS TNM
  2. Classify ground points using PDAL SMRF filter (tuned for flat Davis terrain)
  3. Generate per-tile 1m DEMs
  4. Merge all tiles into a single seamless GeoTIFF
  5. Fill voids (water bodies, data gaps) using nearest-neighbour interpolation
  6. Clip to exact bounding box
  7. Validate output and write quality report

Output: davis_dem_1m.tif  (GeoTIFF, EPSG:4326, 1m resolution)

Confirmed data sources (verified March 2026 via USGS LiDAR Explorer):
  - CA SolanoCounty 1 A23     (northern Davis + UC Davis campus)
  - CA NoCAL Wildfires B5a 2018 (central + southern Davis)

Usage:
    python lidar.py --manifest data/lidar_tiles.json --output data/
    python lidar.py --manifest data/lidar_tiles.json --output data/ --skip-download
    python lidar.py --manifest data/lidar_tiles.json --output data/ --bbox "38.530,-121.760,38.590,-121.710"

Author: BuildDavis Project
License: Apache 2.0
"""

import os
import sys
import json
import time
import math
import shutil
import hashlib
import logging
import argparse
import tempfile
import subprocess
from pathlib import Path
from typing import Optional

import requests
import numpy as np

# Optional imports — graceful degradation if not available
try:
    import pdal
    HAS_PDAL = True
except ImportError:
    HAS_PDAL = False
    logging.warning("PDAL not available — install python-pdal for LiDAR processing")

try:
    import rasterio
    from rasterio.merge import merge as rio_merge
    from rasterio.mask import mask as rio_mask
    from rasterio.fill import fillnodata
    from rasterio.transform import from_bounds
    from rasterio.warp import reproject, Resampling
    import rasterio.crs
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False
    logging.warning("rasterio not available — install rasterio for DEM processing")

try:
    from shapely.geometry import box, mapping
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False


# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("lidar")

# ── Constants ─────────────────────────────────────────────────────────────────

# USGS TNM API for downloading .laz tiles
TNM_DOWNLOAD_API = (
    "https://tnmaccess.nationalmap.gov/api/v1/products"
    "?datasets=Lidar+Point+Cloud+%28LPC%29"
    "&bbox={west},{south},{east},{north}"
    "&max=50&outputFormat=JSON"
)

# Davis-specific elevation constants (from SPEC-001)
DAVIS_ELEVATION_MIN_M = 14.0   # metres above sea level — lowest point
DAVIS_ELEVATION_MAX_M = 22.0   # metres — UC Davis campus
ELEVATION_EXPECTED_RANGE_M = 15.0  # anything > this is suspicious for Davis

# Minecraft elevation mapping (from ADR-001)
SEA_LEVEL_MINECRAFT_Y   = 32
DAVIS_GROUND_MINECRAFT_Y = 47  # ~15m elevation → Y47

# PDAL SMRF parameters tuned for flat Davis terrain (SPEC-001)
# SMRF = Simple Morphological Filter — standard ground classification
SMRF_SLOPE    = 0.15   # Low slope threshold appropriate for flat terrain
SMRF_WINDOW   = 18     # Large window for open agricultural areas
SMRF_SCALAR   = 1.2    # Scalar for object height above ground
SMRF_THRESHOLD = 0.5   # Height threshold for ground classification

# Target output resolution
TARGET_RESOLUTION_M = 1.0  # 1 metre = 1 Minecraft block

# Cache directory for downloaded tiles (avoid re-downloading multi-GB files)
DEFAULT_CACHE_DIR = Path.home() / ".builddavis" / "lidar_cache"


# ─────────────────────────────────────────────────────────────────────────────
# Bounding box helper (reused from fetch.py pattern)
# ─────────────────────────────────────────────────────────────────────────────

class BoundingBox:
    def __init__(self, south, west, north, east):
        self.south, self.west, self.north, self.east = south, west, north, east

    @classmethod
    def from_string(cls, bbox_str):
        parts = [float(x.strip()) for x in bbox_str.split(",")]
        # Detect south,west,north,east vs west,south,east,north
        if -90 <= parts[0] <= 90 and -90 <= parts[2] <= 90:
            return cls(parts[0], parts[1], parts[2], parts[3])
        return cls(parts[1], parts[0], parts[3], parts[2])

    @classmethod
    def from_manifest(cls, manifest):
        b = manifest["bbox"]
        return cls(b["south"], b["west"], b["north"], b["east"])

    def buffer(self, degrees=0.01):
        """Add a buffer around the bbox to ensure full coverage at edges."""
        return BoundingBox(
            self.south - degrees, self.west - degrees,
            self.north + degrees, self.east + degrees
        )

    def area_km2(self):
        lat_c = math.radians((self.north + self.south) / 2)
        ns_m  = (self.north - self.south) * 111_320
        ew_m  = (self.east  - self.west ) * 111_320 * math.cos(lat_c)
        return (ns_m * ew_m) / 1_000_000

    def __repr__(self):
        return f"BBox(S={self.south}, W={self.west}, N={self.north}, E={self.east})"


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2A — Tile discovery & download
# ─────────────────────────────────────────────────────────────────────────────

def discover_tiles(bbox: BoundingBox, manifest_path: Path) -> list:
    """
    Load tile info from the fetch.py manifest.
    If the manifest has pre-confirmed Davis tiles (from visual inspection),
    use those directly. Otherwise query TNM API.
    """
    with open(manifest_path) as f:
        manifest = json.load(f)

    lidar_source = manifest.get("sources", {}).get("lidar", {})
    tiles = []

    # Load from manifest
    if lidar_source:
        tile_meta_path = lidar_source.get("path", "")
        if tile_meta_path and Path(tile_meta_path).exists():
            with open(tile_meta_path) as f:
                tile_data = json.load(f)
            tiles = tile_data.get("tiles", [])

    if tiles:
        log.info("  Loaded %d tiles from manifest", len(tiles))
        return tiles

    # Fallback — query TNM directly
    log.info("  Querying USGS TNM API for LiDAR tiles...")
    buffered = bbox.buffer(0.01)
    url = TNM_DOWNLOAD_API.format(
        west=buffered.west, south=buffered.south,
        east=buffered.east, north=buffered.north
    )
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        tiles = [{
            "title":       item.get("title", ""),
            "downloadURL": item.get("downloadURL", ""),
            "sizeInBytes": item.get("sizeInBytes", 0),
            "source":      "TNM API"
        } for item in items if item.get("downloadURL", "").endswith(".laz")]
        log.info("  TNM API returned %d .laz tiles", len(tiles))
    except Exception as exc:
        log.warning("  TNM API failed: %s", exc)

    # Final fallback — pre-confirmed Davis tiles with known download paths
    if not tiles:
        log.info("  Using pre-confirmed Davis tile metadata")
        tiles = [
            {
                "title":   "CA SolanoCounty 1 A23",
                "source":  "pre-confirmed",
                "note":    "Covers northern Davis + UC Davis campus. QL2 1m.",
                "downloadURL": None,  # Requires manual TNM download
            },
            {
                "title":   "CA NoCAL Wildfires B5a 2018",
                "source":  "pre-confirmed",
                "note":    "Covers central + southern Davis. QL2 1m.",
                "downloadURL": None,
            }
        ]

    return tiles


def download_tile(tile: dict, cache_dir: Path) -> Optional[Path]:
    """
    Download a single .laz tile to the cache directory.
    Returns path to downloaded file, or None if unavailable.
    Skips download if already cached (checks file size).
    """
    url = tile.get("downloadURL")
    if not url:
        log.warning("  No download URL for tile: %s", tile.get("title", "unknown"))
        log.warning("  Download manually from: https://apps.nationalmap.gov/lidar-explorer/")
        return None

    cache_dir.mkdir(parents=True, exist_ok=True)

    # Use URL hash as cache key
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
    filename = f"{url_hash}_{Path(url).name}"
    local_path = cache_dir / filename

    # Check if already cached
    expected_size = tile.get("sizeInBytes", 0)
    if local_path.exists():
        actual_size = local_path.stat().st_size
        if expected_size == 0 or abs(actual_size - expected_size) < 1024:
            log.info("  Cache hit: %s (%s MB)", local_path.name,
                     f"{actual_size/1024/1024:.0f}")
            return local_path
        else:
            log.warning("  Cached file size mismatch — re-downloading")
            local_path.unlink()

    # Download with progress
    log.info("  Downloading: %s", tile.get("title", url))
    log.info("  URL: %s", url)
    size_mb = expected_size / 1024 / 1024
    if size_mb > 0:
        log.info("  Size: %.0f MB", size_mb)

    try:
        resp = requests.get(url, stream=True, timeout=300)
        resp.raise_for_status()
        downloaded = 0
        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                if size_mb > 0:
                    pct = downloaded / expected_size * 100
                    if downloaded % (50 * 1024 * 1024) < 1024 * 1024:
                        log.info("    %.0f%% (%.0f / %.0f MB)", pct,
                                 downloaded/1024/1024, size_mb)
        log.info("  Downloaded: %.0f MB", downloaded/1024/1024)
        return local_path
    except Exception as exc:
        log.error("  Download failed: %s", exc)
        if local_path.exists():
            local_path.unlink()
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2B — PDAL point cloud processing
# ─────────────────────────────────────────────────────────────────────────────

def build_pdal_pipeline(laz_path: Path, dem_output: Path, bbox: BoundingBox) -> dict:
    """
    Build the PDAL JSON pipeline for processing a single .laz file.

    Pipeline stages:
      1. Read .laz file
      2. Crop to bounding box (with buffer)
      3. Assign EPSG:4326 CRS if missing
      4. SMRF ground classification (tuned for flat Davis terrain)
      5. Filter to ground points only (classification == 2)
      6. Write 1m DEM GeoTIFF

    SMRF parameters from SPEC-001:
      slope=0.15    — low slope appropriate for flat terrain
      window=18     — large window for open agricultural areas
      scalar=1.2    — modest object height threshold
      threshold=0.5 — tight height threshold for flat ground
    """
    buffered = bbox.buffer(0.005)

    pipeline = {
        "pipeline": [
            # Stage 1: Read
            {
                "type": "readers.las",
                "filename": str(laz_path)
            },
            # Stage 2: Crop to bbox (with small buffer)
            {
                "type": "filters.crop",
                "bounds": (
                    f"([{buffered.west},{buffered.east}],"
                    f"[{buffered.south},{buffered.north}])"
                )
            },
            # Stage 3: Assign CRS if not present
            {
                "type": "filters.reprojection",
                "in_srs": "EPSG:4326",
                "out_srs": "EPSG:4326"
            },
            # Stage 4: SMRF ground classification
            # Parameters specifically tuned for Davis's flat terrain (SPEC-001)
            {
                "type": "filters.smrf",
                "slope":     SMRF_SLOPE,
                "window":    SMRF_WINDOW,
                "scalar":    SMRF_SCALAR,
                "threshold": SMRF_THRESHOLD
            },
            # Stage 5: Keep only ground points (class 2)
            {
                "type": "filters.range",
                "limits": "Classification[2:2]"
            },
            # Stage 6: Write 1m DEM
            {
                "type": "writers.gdal",
                "filename": str(dem_output),
                "resolution": TARGET_RESOLUTION_M,
                "output_type": "mean",
                "gdalopts": "COMPRESS=LZW,TILED=YES,BLOCKXSIZE=256,BLOCKYSIZE=256",
                "nodata": -9999.0
            }
        ]
    }
    return pipeline


def build_pdal_pipeline_dsm(laz_path: Path, dsm_output: Path, bbox: BoundingBox) -> dict:
    """
    Build the PDAL JSON pipeline for a Digital Surface Model (DSM).

    Unlike the DTM pipeline (ground-only), the DSM uses FIRST RETURN
    points to capture rooftops, treetops, power lines — the top of
    everything. Building height = DSM - DTM at any coordinate.

    Pipeline:
      1. Read .laz file
      2. Crop to bounding box
      3. Assign CRS
      4. Keep only first returns (return_number == 1)
      5. Write 1m DSM GeoTIFF using MAX value (highest point in cell)
    """
    buffered = bbox.buffer(0.005)

    pipeline = {
        "pipeline": [
            {
                "type": "readers.las",
                "filename": str(laz_path)
            },
            {
                "type": "filters.crop",
                "bounds": (
                    f"([{buffered.west},{buffered.east}],"
                    f"[{buffered.south},{buffered.north}])"
                )
            },
            {
                "type": "filters.reprojection",
                "in_srs": "EPSG:4326",
                "out_srs": "EPSG:4326"
            },
            # Keep first returns only — these hit rooftops, treetops
            {
                "type": "filters.range",
                "limits": "ReturnNumber[1:1]"
            },
            # Use MAX output — we want the highest point in each 1m cell
            {
                "type": "writers.gdal",
                "filename": str(dsm_output),
                "resolution": TARGET_RESOLUTION_M,
                "output_type": "max",
                "gdalopts": "COMPRESS=LZW,TILED=YES,BLOCKXSIZE=256,BLOCKYSIZE=256",
                "nodata": -9999.0
            }
        ]
    }
    return pipeline


def process_tile_pdal(laz_path: Path, dem_output: Path, bbox: BoundingBox,
                      dsm_output: Path = None) -> bool:
    """Run the PDAL DTM pipeline on a single .laz tile.
    Optionally also generates DSM (first-return surface model)."""
    if not HAS_PDAL:
        raise RuntimeError("PDAL is required for LiDAR processing. Install: conda install -c conda-forge python-pdal")

    log.info("  Processing tile: %s", laz_path.name)

    # DTM (ground only)
    pipeline_json = build_pdal_pipeline(laz_path, dem_output, bbox)
    try:
        pipeline = pdal.Pipeline(json.dumps(pipeline_json))
        pipeline.execute()
        point_count = pipeline.arrays[0].shape[0] if pipeline.arrays else 0
        log.info("  Processed %d ground points → %s", point_count, dem_output.name)
    except Exception as exc:
        log.error("  PDAL DTM processing failed for %s: %s", laz_path.name, exc)
        return False

    # DSM (first return — rooftops + treetops)
    if dsm_output:
        dsm_json = build_pdal_pipeline_dsm(laz_path, dsm_output, bbox)
        try:
            dsm_pipe = pdal.Pipeline(json.dumps(dsm_json))
            dsm_pipe.execute()
            dsm_count = dsm_pipe.arrays[0].shape[0] if dsm_pipe.arrays else 0
            log.info("  Processed %d first-return points → %s", dsm_count, dsm_output.name)
        except Exception as exc:
            log.error("  PDAL DSM processing failed for %s: %s", laz_path.name, exc)
            # DSM failure is non-fatal — DTM still succeeded
            log.warning("  Continuing without DSM for this tile")

    return True


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2C — DEM merging and post-processing
# ─────────────────────────────────────────────────────────────────────────────

def merge_dems(dem_paths: list, output_path: Path, bbox: BoundingBox) -> bool:
    """
    Merge multiple per-tile DEMs into a single seamless GeoTIFF.

    For Davis we have two tile sets with a potential seam:
      - CA SolanoCounty 1 A23 (north)
      - CA NoCAL Wildfires B5a 2018 (south)

    Uses rasterio merge with 'first' method (higher-resolution tile wins
    where they overlap). The overlap region provides natural blending.
    """
    if not HAS_RASTERIO:
        raise RuntimeError("rasterio is required. Install: conda install -c conda-forge rasterio")

    log.info("  Merging %d DEM tiles...", len(dem_paths))

    # Open all source DEMs
    sources = []
    for path in dem_paths:
        if path.exists():
            sources.append(rasterio.open(path))
        else:
            log.warning("  DEM tile not found: %s", path)

    if not sources:
        log.error("  No valid DEM tiles to merge")
        return False

    try:
        # Merge — 'first' method prioritises the first dataset where tiles overlap
        # This means the higher-resolution SolanoCounty tile wins in overlap areas
        merged, transform = rio_merge(sources, method="first", nodata=-9999.0)

        # Write merged DEM
        profile = sources[0].profile.copy()
        profile.update({
            "driver":    "GTiff",
            "height":    merged.shape[1],
            "width":     merged.shape[2],
            "transform": transform,
            "crs":       rasterio.crs.CRS.from_epsg(4326),
            "nodata":    -9999.0,
            "compress":  "lzw",
            "tiled":     True,
            "blockxsize": 256,
            "blockysize": 256,
        })

        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(merged)

        log.info("  Merged DEM: %s × %s pixels", merged.shape[2], merged.shape[1])
        return True

    finally:
        for src in sources:
            src.close()


def fill_voids(dem_path: Path, output_path: Path) -> bool:
    """
    Fill NoData voids in the DEM using nearest-neighbour interpolation.

    Voids occur over:
      - Water bodies (Putah Creek, Arboretum Waterway, irrigation channels)
        — LiDAR doesn't penetrate water surfaces reliably
      - Tile boundary gaps
      - Urban canyons where points were filtered out

    For water bodies, the filled elevation represents the water surface level,
    which is correct for Minecraft (we place water blocks at that elevation).
    """
    if not HAS_RASTERIO:
        return False

    log.info("  Filling DEM voids (water bodies + data gaps)...")

    with rasterio.open(dem_path) as src:
        data = src.read(1)
        profile = src.profile.copy()
        nodata = src.nodata or -9999.0

        # Create mask: 1 = valid data, 0 = void
        valid_mask = (data != nodata).astype(np.uint8)
        void_count = np.sum(valid_mask == 0)
        total = data.size
        log.info("  Voids: %d pixels (%.1f%%)", void_count, void_count/total*100)

        if void_count == 0:
            log.info("  No voids found — skipping fill")
            shutil.copy2(dem_path, output_path)
            return True

        # Fill voids using nearest-neighbour
        filled = fillnodata(data, mask=valid_mask, max_search_distance=100)

        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(filled, 1)

    remaining_voids = np.sum(filled == nodata)
    log.info("  After fill: %d voids remaining", remaining_voids)
    return True


def clip_to_bbox(dem_path: Path, output_path: Path, bbox: BoundingBox) -> bool:
    """Clip the merged DEM to the exact Davis bounding box."""
    if not HAS_RASTERIO or not HAS_SHAPELY:
        log.warning("  Skipping bbox clip — rasterio or shapely not available")
        shutil.copy2(dem_path, output_path)
        return True

    log.info("  Clipping to Davis bounding box...")

    clip_geom = box(bbox.west, bbox.south, bbox.east, bbox.north)

    with rasterio.open(dem_path) as src:
        clipped, transform = rio_mask(src, [mapping(clip_geom)], crop=True, nodata=-9999.0)
        profile = src.profile.copy()
        profile.update({
            "height":    clipped.shape[1],
            "width":     clipped.shape[2],
            "transform": transform,
        })
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(clipped)

    log.info("  Clipped: %d × %d pixels", clipped.shape[2], clipped.shape[1])
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2D — Validation & quality report
# ─────────────────────────────────────────────────────────────────────────────

def validate_dem(dem_path: Path, bbox: BoundingBox) -> dict:
    """
    Validate the output DEM against Davis-specific expectations.
    Returns a quality report dict.

    Davis elevation facts (from SPEC-001):
      - Minimum: ~14m (lowest streets near Putah Creek)
      - Maximum: ~22m (UC Davis campus, eastern foothills fringe)
      - Expected range: < 15m total (very flat)
      - Typical ground: ~15m → Minecraft Y47
    """
    report = {
        "valid": False,
        "path": str(dem_path),
        "checks": {},
        "warnings": [],
        "minecraft_y": {}
    }

    if not dem_path.exists():
        report["warnings"].append("DEM file does not exist")
        return report

    if not HAS_RASTERIO:
        report["warnings"].append("rasterio not available — skipping validation")
        report["valid"] = True
        return report

    with rasterio.open(dem_path) as src:
        data = src.read(1)
        nodata = src.nodata or -9999.0
        valid = data[data != nodata]

        if valid.size == 0:
            report["warnings"].append("DEM contains no valid data")
            return report

        elev_min  = float(np.min(valid))
        elev_max  = float(np.max(valid))
        elev_mean = float(np.mean(valid))
        elev_range = elev_max - elev_min
        void_pct  = float(np.sum(data == nodata)) / data.size * 100
        pixel_w   = abs(src.transform.a)
        pixel_h   = abs(src.transform.e)

        report["stats"] = {
            "elevation_min_m":   round(elev_min, 2),
            "elevation_max_m":   round(elev_max, 2),
            "elevation_mean_m":  round(elev_mean, 2),
            "elevation_range_m": round(elev_range, 2),
            "void_percent":      round(void_pct, 2),
            "pixel_size_m":      round(pixel_w, 4),
            "pixels_total":      int(data.size),
            "pixels_valid":      int(valid.size),
            "width_px":          src.width,
            "height_px":         src.height,
            "crs":               str(src.crs),
        }

        # Davis-specific validation checks
        checks = {}

        # Check elevation range is plausible for Davis
        checks["elevation_in_davis_range"] = (
            DAVIS_ELEVATION_MIN_M - 5 <= elev_min <= DAVIS_ELEVATION_MAX_M + 5 and
            DAVIS_ELEVATION_MIN_M - 5 <= elev_max <= DAVIS_ELEVATION_MAX_M + 10
        )

        # Check terrain is appropriately flat (Davis-specific)
        checks["terrain_is_flat"] = elev_range < 30.0
        if elev_range > ELEVATION_EXPECTED_RANGE_M:
            report["warnings"].append(
                f"Elevation range {elev_range:.1f}m exceeds expected {ELEVATION_EXPECTED_RANGE_M}m "
                f"— check for outlier points or incorrect tile area"
            )

        # Check resolution is approximately 1m
        checks["resolution_is_1m"] = abs(pixel_w - TARGET_RESOLUTION_M) < 0.5

        # Check void percentage is acceptable
        checks["voids_acceptable"] = void_pct < 10.0
        if void_pct >= 10.0:
            report["warnings"].append(
                f"High void percentage ({void_pct:.1f}%) — check LiDAR coverage or run fill_voids again"
            )

        # Check CRS is geographic
        checks["crs_is_geographic"] = src.crs.is_geographic if src.crs else False

        report["checks"] = checks
        report["valid"] = all(checks.values())

        # Minecraft Y mapping for key Davis elevations
        def to_minecraft_y(elevation_m):
            return round(SEA_LEVEL_MINECRAFT_Y + elevation_m)

        report["minecraft_y"] = {
            "dem_minimum":     to_minecraft_y(elev_min),
            "dem_mean":        to_minecraft_y(elev_mean),
            "dem_maximum":     to_minecraft_y(elev_max),
            "typical_davis_ground_y47": to_minecraft_y(15.0),
            "uc_davis_campus_y50":      to_minecraft_y(18.0),
            "putah_creek_water_y46":    to_minecraft_y(14.0),
        }

        # Summary
        passed = sum(1 for v in checks.values() if v)
        total  = len(checks)
        log.info("  Validation: %d/%d checks passed", passed, total)
        log.info("  Elevation: %.1f–%.1fm (range %.1fm)", elev_min, elev_max, elev_range)
        log.info("  Voids: %.1f%%", void_pct)
        log.info("  Minecraft Y range: %d–%d",
                 report["minecraft_y"]["dem_minimum"],
                 report["minecraft_y"]["dem_maximum"])

        if report["warnings"]:
            for w in report["warnings"]:
                log.warning("  WARN: %s", w)

    return report


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic DEM fallback (for testing without real LiDAR data)
# ─────────────────────────────────────────────────────────────────────────────

def generate_synthetic_dem(output_path: Path, bbox: BoundingBox) -> bool:
    """
    Generate a synthetic flat DEM for Davis for pipeline testing.

    Davis is extremely flat — this creates a realistic placeholder:
      - Base elevation: 15m (typical Davis ground)
      - UC Davis campus area: +2m gradient (northwest)
      - Putah Creek corridor: -1m depression (southern edge)
      - Agricultural fringe: exactly flat at 15m

    This allows the full pipeline to run end-to-end before real LiDAR
    tiles are downloaded (which can be several GB).
    """
    if not HAS_RASTERIO:
        log.error("rasterio required for DEM generation")
        return False

    log.info("  Generating synthetic Davis DEM (flat terrain approximation)...")

    # Calculate pixel dimensions
    lat_c = math.radians((bbox.north + bbox.south) / 2)
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(lat_c)

    width_m  = (bbox.east  - bbox.west ) * m_per_deg_lon
    height_m = (bbox.north - bbox.south) * m_per_deg_lat

    width_px  = int(width_m  / TARGET_RESOLUTION_M)
    height_px = int(height_m / TARGET_RESOLUTION_M)

    log.info("  Synthetic DEM size: %d × %d pixels (%.1f × %.1f km)",
             width_px, height_px, width_m/1000, height_m/1000)

    # Build elevation grid
    dem = np.full((height_px, width_px), 15.0, dtype=np.float32)

    # Normalised coordinate grids (0.0 = south/west, 1.0 = north/east)
    # Both grids are full 2D arrays so all numpy operations broadcast correctly
    y_norm = np.tile(np.linspace(0, 1, height_px).reshape(-1, 1), (1, width_px))
    x_norm = np.tile(np.linspace(0, 1, width_px).reshape(1, -1), (height_px, 1))

    # UC Davis campus area (northwest quadrant) — slight elevation gain
    campus_mask = (x_norm < 0.45) & (y_norm > 0.55)
    dem = np.where(campus_mask, dem + np.clip(2.0 * (1 - x_norm) * y_norm, 0, 2), dem)

    # Putah Creek corridor (southern edge) — gentle depression
    creek_mask = y_norm < 0.12
    dem = np.where(creek_mask, dem - 1.0 * (0.12 - y_norm) / 0.12, dem)

    # Agricultural fringe (eastern and western edges) — perfectly flat
    ag_mask = (x_norm < 0.08) | (x_norm > 0.92)
    dem = np.where(ag_mask, 15.0, dem)

    # Add very subtle noise to avoid perfectly flat terrain (0.1m max)
    np.random.seed(42)
    noise = np.random.normal(0, 0.05, dem.shape).astype(np.float32)
    dem = (dem + noise).astype(np.float32)

    # Write GeoTIFF
    transform = from_bounds(
        bbox.west, bbox.south, bbox.east, bbox.north,
        width_px, height_px
    )

    with rasterio.open(
        output_path, "w",
        driver="GTiff",
        height=height_px,
        width=width_px,
        count=1,
        dtype=np.float32,
        crs=rasterio.crs.CRS.from_epsg(4326),
        transform=transform,
        nodata=-9999.0,
        compress="lzw",
        tiled=True,
        blockxsize=256,
        blockysize=256,
    ) as dst:
        dst.write(dem, 1)

    log.info("  Synthetic DEM written: %s", output_path.name)
    log.info("  Elevation range: %.1f–%.1fm (realistic for flat Davis)",
             float(dem.min()), float(dem.max()))

    # Also generate synthetic DSM (ground + building heights)
    dsm_path = output_path.parent / "davis_dsm_1m.tif"
    dsm = dem.copy()
    # Simulate building footprints as random elevated patches
    np.random.seed(99)
    for _ in range(200):
        bx = np.random.randint(10, width_px - 30)
        by = np.random.randint(10, height_px - 30)
        bw = np.random.randint(5, 25)
        bh = np.random.randint(5, 20)
        building_height = np.random.choice([4.0, 5.0, 6.0, 7.0, 9.0, 10.5])
        dsm[by:by+bh, bx:bx+bw] += building_height

    with rasterio.open(
        dsm_path, "w",
        driver="GTiff", height=height_px, width=width_px,
        count=1, dtype=np.float32,
        crs=rasterio.crs.CRS.from_epsg(4326),
        transform=transform, nodata=-9999.0,
        compress="lzw", tiled=True, blockxsize=256, blockysize=256,
    ) as dst:
        dst.write(dsm, 1)
    log.info("  Synthetic DSM written: %s", dsm_path.name)

    return True


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2E — Per-building height extraction & roof shape classification
# ─────────────────────────────────────────────────────────────────────────────

def _classify_roof_shape(roof_surface: np.ndarray) -> tuple:
    """
    Classify roof shape from a 2D elevation grid (DSM − DTM) of a single building.

    Uses the elevation profile within the building footprint:
      - Flat:      σ < 0.3m (uniform elevation)
      - Gabled:    Strong primary gradient axis, ridge along one direction
      - Hipped:    Ridge shorter than 60% of long axis
      - Pyramidal: Single peak at center, radial symmetry
      - Skillion:  Consistent slope in one direction (R² > 0.8)

    Returns:
        (shape, orientation, confidence)
        shape:       "flat" | "gabled" | "hipped" | "pyramidal" | "skillion"
        orientation: "along" | "across" | None
        confidence:  0.0–1.0
    """
    if roof_surface.size < 4:
        return "flat", None, 0.3

    # Remove any nodata / zero values
    valid = roof_surface[roof_surface > 0.5]
    if valid.size < 4:
        return "flat", None, 0.3

    height_std = float(np.std(valid))
    height_range = float(np.max(valid) - np.min(valid))

    # Flat roof: very uniform height
    if height_std < 0.3 or height_range < 0.5:
        return "flat", None, min(0.95, 0.7 + (0.3 - height_std))

    rows, cols = roof_surface.shape

    # Compute gradients
    if rows >= 3 and cols >= 3:
        gy, gx = np.gradient(roof_surface)
        # Replace nan/inf with 0
        gx = np.nan_to_num(gx, 0.0)
        gy = np.nan_to_num(gy, 0.0)
    else:
        return "gabled" if height_range > 1.0 else "flat", None, 0.4

    # Check for skillion (consistent slope in one direction)
    # Fit a plane and check R²
    if rows >= 3 and cols >= 3:
        y_coords, x_coords = np.mgrid[0:rows, 0:cols]
        valid_mask = roof_surface > 0.5
        if np.sum(valid_mask) >= 6:
            xv = x_coords[valid_mask].flatten()
            yv = y_coords[valid_mask].flatten()
            zv = roof_surface[valid_mask].flatten()

            # Simple plane fit: z = a*x + b*y + c
            A = np.column_stack([xv, yv, np.ones_like(xv)])
            try:
                result = np.linalg.lstsq(A, zv, rcond=None)
                coeffs = result[0]
                residuals = zv - A @ coeffs
                ss_res = np.sum(residuals ** 2)
                ss_tot = np.sum((zv - np.mean(zv)) ** 2)
                r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

                slope_angle = math.degrees(math.atan(
                    math.sqrt(coeffs[0]**2 + coeffs[1]**2)
                ))

                if r_squared > 0.8 and slope_angle > 5.0:
                    return "skillion", None, round(min(0.95, r_squared), 2)
            except (np.linalg.LinAlgError, ValueError):
                pass

    # Detect ridge line (gabled vs hipped)
    # Find the row/column with the highest mean elevation
    row_means = np.array([
        np.mean(roof_surface[r, roof_surface[r, :] > 0.5])
        if np.any(roof_surface[r, :] > 0.5) else 0
        for r in range(rows)
    ])
    col_means = np.array([
        np.mean(roof_surface[roof_surface[:, c] > 0.5, c])
        if np.any(roof_surface[:, c] > 0.5) else 0
        for c in range(cols)
    ])

    # Ridge detection: find the axis with a clear peak
    row_peak_strength = float(np.max(row_means) - np.mean(row_means)) if rows > 2 else 0
    col_peak_strength = float(np.max(col_means) - np.mean(col_means)) if cols > 2 else 0

    # ── Check for pyramidal FIRST (before ridge detection) ──
    # Pyramidal: single peak near center with radial symmetry
    max_pos = np.unravel_index(np.argmax(roof_surface), roof_surface.shape)
    center_r, center_c = rows // 2, cols // 2
    dist_from_center = math.sqrt(
        ((max_pos[0] - center_r) / max(rows, 1)) ** 2 +
        ((max_pos[1] - center_c) / max(cols, 1)) ** 2
    )
    if dist_from_center < 0.3 and height_range > 1.0:
        aspect_ratio = max(rows, cols) / max(min(rows, cols), 1)
        # Pyramidal: peak is a POINT, not a line.  Count pixels near the
        # maximum value — if only a small cluster, it's pyramidal.
        # If a whole row/column is near max, it's a ridge (hipped/gabled).
        peak_val = float(np.max(roof_surface))
        near_peak = np.sum(roof_surface > (peak_val - 0.3 * height_range))
        near_peak_frac = near_peak / max(roof_surface.size, 1)
        # True pyramidal: < 15% of pixels near peak.  Hipped: a ridge line
        # means 20-40% of pixels are near peak.
        if aspect_ratio < 1.5 and near_peak_frac < 0.15:
            return "pyramidal", None, round(min(0.90, 0.5 + height_range / 5.0), 2)

    # ── Detect ridge line (gabled vs hipped) ──
    # Determine ridge axis
    if row_peak_strength > col_peak_strength and row_peak_strength > 0.3:
        # Ridge runs along columns (east-west)
        ridge_axis = "row"
        peak_idx = int(np.argmax(row_means))
        peak_strength = row_peak_strength
    elif col_peak_strength > 0.3:
        # Ridge runs along rows (north-south)
        ridge_axis = "col"
        peak_idx = int(np.argmax(col_means))
        peak_strength = col_peak_strength
    else:
        # No clear ridge and not pyramidal → default gabled
        return "gabled", None, 0.4

    # Determine if gabled or hipped based on ridge length
    # Gabled: ridge extends most of the building length
    # Hipped: ridge is shorter, slopes on all four sides
    if ridge_axis == "row":
        # Ridge runs east-west → check how many columns have peak at that row
        ridge_cols = sum(1 for c in range(cols)
                         if roof_surface[peak_idx, c] > 0.5 and
                         abs(roof_surface[peak_idx, c] - np.max(row_means)) < 0.5)
        ridge_fraction = ridge_cols / max(cols, 1)
        orientation = "across" if rows > cols else "along"
    else:
        # Ridge runs north-south
        ridge_rows = sum(1 for r in range(rows)
                         if roof_surface[r, peak_idx] > 0.5 and
                         abs(roof_surface[r, peak_idx] - np.max(col_means)) < 0.5)
        ridge_fraction = ridge_rows / max(rows, 1)
        orientation = "along" if rows > cols else "across"

    confidence = round(min(0.95, 0.4 + peak_strength / 3.0 + ridge_fraction / 3.0), 2)

    # Determine if gabled or hipped based on ridge length
    # Gabled: ridge extends most of the building length
    # Hipped: ridge is shorter, slopes on all four sides
    if ridge_axis == "row":
        # Ridge runs east-west → check how many columns have peak at that row
        ridge_cols = sum(1 for c in range(cols)
                         if roof_surface[peak_idx, c] > 0.5 and
                         abs(roof_surface[peak_idx, c] - np.max(row_means)) < 0.5)
        ridge_fraction = ridge_cols / max(cols, 1)
        orientation = "across" if rows > cols else "along"
    else:
        # Ridge runs north-south
        ridge_rows = sum(1 for r in range(rows)
                         if roof_surface[r, peak_idx] > 0.5 and
                         abs(roof_surface[r, peak_idx] - np.max(col_means)) < 0.5)
        ridge_fraction = ridge_rows / max(rows, 1)
        orientation = "along" if rows > cols else "across"

    confidence = round(min(0.95, 0.4 + peak_strength / 3.0 + ridge_fraction / 3.0), 2)

    # Gabled vs hipped:  ridge extends > 60% of length → gabled
    # For near-square footprints, use a lower threshold since the ridge
    # is proportionally shorter even on a gabled roof
    aspect_ratio = max(rows, cols) / max(min(rows, cols), 1)
    gabled_threshold = 0.6 if aspect_ratio > 1.3 else 0.75

    if ridge_fraction > gabled_threshold:
        return "gabled", orientation, confidence
    else:
        return "hipped", orientation, confidence


def extract_building_heights(
    fused_geojson_path: str,
    dem_path: str,
    dsm_path: str,
    output_path: str,
) -> dict:
    """
    Extract per-building heights (DSM − DTM) and classify roof shapes
    using the LiDAR raster data already on disk.

    For each building polygon in fused_features.geojson:
      1. Mask DSM raster to building footprint → rooftop elevation
      2. Mask DTM raster to building footprint → ground elevation
      3. height_m = DSM_mean − DTM_mean
      4. Classify roof shape from DSM elevation profile

    Args:
        fused_geojson_path:  Path to fused_features.geojson from Stage 4
        dem_path:            Path to davis_dem_1m.tif (ground DEM)
        dsm_path:            Path to davis_dsm_1m.tif (surface DSM)
        output_path:         Path to write lidar_building_heights.json

    Returns:
        Result dict with stats
    """
    if not HAS_RASTERIO or not HAS_SHAPELY:
        raise RuntimeError(
            "rasterio + shapely required for building height extraction. "
            "Install: conda install -c conda-forge rasterio shapely"
        )

    from shapely.geometry import shape as shapely_shape

    log.info("=" * 60)
    log.info("  BuildDavis — Stage 2E: Building Height Extraction")
    log.info("=" * 60)

    # Load building polygons
    log.info("[1/3] Loading building footprints from fused_features.geojson...")
    with open(fused_geojson_path) as f:
        geojson = json.load(f)

    buildings = []
    for feat in geojson.get("features", []):
        props = feat.get("properties", {})
        geom  = feat.get("geometry", {})
        if props.get("type") != "building":
            continue
        if geom.get("type") != "Polygon":
            continue
        buildings.append((props, geom))

    log.info("  %d building polygons found", len(buildings))

    # Open rasters
    log.info("[2/3] Extracting heights and classifying roofs...")
    dem_src = rasterio.open(dem_path)
    dsm_src = rasterio.open(dsm_path)

    results = {}
    skipped = 0
    roof_counts = {"flat": 0, "gabled": 0, "hipped": 0, "pyramidal": 0, "skillion": 0}

    for props, geom in buildings:
        try:
            shp = shapely_shape(geom)
            if not shp.is_valid or shp.is_empty:
                skipped += 1
                continue

            # Mask DSM (rooftop surface)
            dsm_masked, dsm_transform = rio_mask(
                dsm_src, [mapping(shp)], crop=True, nodata=-9999.0, all_touched=True
            )
            dsm_pixels = dsm_masked[0]
            dsm_valid = dsm_pixels[dsm_pixels != -9999.0]

            # Mask DTM (ground surface)
            dtm_masked, dtm_transform = rio_mask(
                dem_src, [mapping(shp)], crop=True, nodata=-9999.0, all_touched=True
            )
            dtm_pixels = dtm_masked[0]
            dtm_valid = dtm_pixels[dtm_pixels != -9999.0]

            pixel_count = min(len(dsm_valid), len(dtm_valid))

            if pixel_count < 4:
                skipped += 1
                continue

            dsm_mean = float(np.mean(dsm_valid))
            dsm_max  = float(np.max(dsm_valid))
            dtm_mean = float(np.mean(dtm_valid))

            height_m     = round(dsm_mean - dtm_mean, 2)
            height_max_m = round(dsm_max  - dtm_mean, 2)

            # Sanity checks
            if height_m < 1.0 or height_m > 80.0:
                skipped += 1
                continue

            # Roof shape classification from DSM elevation profile
            roof_surface = dsm_pixels.copy()
            # Subtract ground to get pure roof shape
            if dtm_pixels.shape == dsm_pixels.shape:
                roof_surface = dsm_pixels - dtm_pixels
                roof_surface[dsm_pixels == -9999.0] = 0
                roof_surface[dtm_pixels == -9999.0] = 0
            else:
                roof_surface[dsm_pixels == -9999.0] = 0
                roof_surface = roof_surface - dtm_mean

            roof_shape, roof_orientation, roof_confidence = _classify_roof_shape(roof_surface)
            roof_counts[roof_shape] = roof_counts.get(roof_shape, 0) + 1

            # Build result entry
            bid = str(props.get("osm_id") or props.get("id", ""))
            centroid = shp.centroid

            entry = {
                "height_m":         height_m,
                "height_max_m":     height_max_m,
                "pixel_count":      pixel_count,
                "confidence":       "lidar_dsm_dtm",
                "roof_shape":       roof_shape,
                "roof_orientation": roof_orientation,
                "roof_confidence":  roof_confidence,
                "centroid_lon":     round(centroid.x, 6),
                "centroid_lat":     round(centroid.y, 6),
            }
            results[bid] = entry

        except Exception as exc:
            skipped += 1
            continue

    dem_src.close()
    dsm_src.close()

    # Write output
    log.info("[3/3] Writing lidar_building_heights.json...")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    log.info("  Results:  %d buildings with LiDAR heights", len(results))
    log.info("  Skipped:  %d (too small, invalid, or out of range)", skipped)
    log.info("  Roof shapes: %s", roof_counts)
    log.info("  Output:   %s", output_path)

    return {
        "buildings_processed": len(results),
        "skipped":             skipped,
        "roof_shapes":         roof_counts,
        "output_path":         output_path,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_lidar(
    manifest_path: str,
    output_dir: str,
    bbox_override: Optional[str] = None,
    skip_download: bool = False,
    use_synthetic: bool = False,
    cache_dir: Optional[str] = None,
) -> dict:
    """
    Run the full LiDAR processing pipeline.

    Args:
        manifest_path:  Path to fetch_manifest.json from Stage 1
        output_dir:     Directory to write output files
        bbox_override:  Optional bbox string to override manifest bbox
        skip_download:  Skip .laz download (use cached tiles only)
        use_synthetic:  Generate synthetic flat DEM (for testing)
        cache_dir:      Cache directory for downloaded .laz tiles

    Returns:
        Result dict with output paths and quality report
    """
    start = time.time()
    out   = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    cache = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR

    log.info("=" * 60)
    log.info("  BuildDavis — Stage 2: LiDAR")
    log.info("=" * 60)

    # Load manifest and bbox
    # Manifest is optional in synthetic mode or when --bbox is provided
    DAVIS_DEFAULT_BBOX = "38.527,-121.812,38.591,-121.670"
    manifest_p = Path(manifest_path)
    manifest   = {}

    if bbox_override:
        bbox = BoundingBox.from_string(bbox_override)
    elif manifest_p.exists():
        with open(manifest_p) as f:
            manifest = json.load(f)
        bbox = BoundingBox.from_manifest(manifest)
    elif use_synthetic:
        log.info("  No manifest found — using full Davis bounding box")
        bbox = BoundingBox.from_string(DAVIS_DEFAULT_BBOX)
    else:
        raise FileNotFoundError(
            "Manifest not found. Run Stage 1 first (python fetch.py --output data) "
            "or add --synthetic to test without a manifest."
        )

    log.info("  bbox: %s", bbox)
    log.info("  area: %.1f km²", bbox.area_km2())

    final_dem = out / "davis_dem_1m.tif"

    # ── Synthetic mode (for testing) ──────────────────────────────────────────
    if use_synthetic:
        log.info("  SYNTHETIC MODE — generating flat terrain approximation")
        success = generate_synthetic_dem(final_dem, bbox)
        if not success:
            raise RuntimeError("Synthetic DEM generation failed")
        report = validate_dem(final_dem, bbox)
        result = {
            "stage":  "lidar",
            "mode":   "synthetic",
            "path":   str(final_dem),
            "report": report,
            "elapsed_seconds": round(time.time() - start, 1)
        }
        manifest_out = out / "lidar_manifest.json"
        manifest_out.write_text(json.dumps(result, indent=2))
        log.info("  Done (synthetic) in %.1fs", time.time() - start)
        return result

    # ── Real LiDAR processing ─────────────────────────────────────────────────
    if not HAS_PDAL:
        log.warning("PDAL not available — falling back to synthetic DEM")
        log.warning("Install with: conda install -c conda-forge python-pdal")
        return run_lidar(manifest_path, output_dir, bbox_override,
                         skip_download=True, use_synthetic=True, cache_dir=cache_dir)

    # 2A: Discover tiles
    log.info("[1/5] Discovering LiDAR tiles...")
    tiles = discover_tiles(bbox, manifest_p)
    log.info("  %d tiles identified", len(tiles))

    # 2A: Download tiles
    laz_paths = []
    if not skip_download:
        log.info("[2/5] Downloading .laz tiles...")
        for tile in tiles:
            laz_path = download_tile(tile, cache)
            if laz_path:
                laz_paths.append(laz_path)
    else:
        log.info("[2/5] Skipping download (--skip-download)")
        # Look for existing .laz files in cache
        if cache.exists():
            laz_paths = list(cache.glob("*.laz"))
            log.info("  Found %d cached .laz files", len(laz_paths))

    if not laz_paths:
        log.warning("No .laz files available — falling back to synthetic DEM")
        log.warning("To get real data: visit https://apps.nationalmap.gov/lidar-explorer/")
        log.warning("Search for 'CA SolanoCounty 1 A23' and 'CA NoCAL Wildfires B5a 2018'")
        return run_lidar(manifest_path, output_dir, bbox_override,
                         use_synthetic=True, cache_dir=cache_dir)

    # 2B: Process each tile with PDAL
    log.info("[3/5] Processing %d tiles with PDAL...", len(laz_paths))
    per_tile_dems = []
    per_tile_dsms = []
    tile_dir = out / "tiles"
    tile_dir.mkdir(exist_ok=True)

    for i, laz_path in enumerate(laz_paths, 1):
        dem_out = tile_dir / f"tile_{i:03d}_dem.tif"
        dsm_out = tile_dir / f"tile_{i:03d}_dsm.tif"
        log.info("  Tile %d/%d: %s", i, len(laz_paths), laz_path.name)
        success = process_tile_pdal(laz_path, dem_out, bbox, dsm_output=dsm_out)
        if success and dem_out.exists():
            per_tile_dems.append(dem_out)
            if dsm_out.exists():
                per_tile_dsms.append(dsm_out)
        else:
            log.warning("  Tile %d failed — will be excluded from merge", i)

    if not per_tile_dems:
        raise RuntimeError("All PDAL tile processing failed")

    # 2C: Merge tiles
    log.info("[4/5] Merging and post-processing DEM...")
    merged_raw  = out / "davis_dem_merged_raw.tif"
    filled_dem  = out / "davis_dem_filled.tif"

    if not merge_dems(per_tile_dems, merged_raw, bbox):
        raise RuntimeError("DEM merge failed")

    fill_voids(merged_raw, filled_dem)
    clip_to_bbox(filled_dem, final_dem, bbox)

    # Merge DSM tiles (if any)
    final_dsm = out / "davis_dsm_1m.tif"
    if per_tile_dsms:
        log.info("  Merging %d DSM tiles...", len(per_tile_dsms))
        dsm_merged = out / "davis_dsm_merged_raw.tif"
        dsm_filled = out / "davis_dsm_filled.tif"
        if merge_dems(per_tile_dsms, dsm_merged, bbox):
            fill_voids(dsm_merged, dsm_filled)
            clip_to_bbox(dsm_filled, final_dsm, bbox)
            log.info("  DSM ready: %s", final_dsm.name)
        else:
            log.warning("  DSM merge failed — building heights unavailable")
    else:
        log.warning("  No DSM tiles — building heights unavailable")

    # 2D: Validate
    log.info("[5/5] Validating output...")
    report = validate_dem(final_dem, bbox)

    elapsed = time.time() - start
    result = {
        "stage":   "lidar",
        "mode":    "real",
        "path":    str(final_dem),
        "tiles_processed": len(per_tile_dems),
        "report":  report,
        "elapsed_seconds": round(elapsed, 1)
    }

    manifest_out = out / "lidar_manifest.json"
    manifest_out.write_text(json.dumps(result, indent=2))

    log.info("=" * 60)
    log.info("  Stage 2 complete in %.1fs", elapsed)
    log.info("  Output: %s", final_dem)
    log.info("  Valid: %s", report.get("valid", False))
    log.info("=" * 60)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="BuildDavis Pipeline — Stage 2: LiDAR Terrain Processor"
    )
    parser.add_argument(
        "--manifest", required=False, default="data/fetch_manifest.json",
        help="Path to fetch_manifest.json from Stage 1 (not needed with --extract-heights)"
    )
    parser.add_argument(
        "--output", default="./data",
        help="Output directory (default: ./data)"
    )
    parser.add_argument(
        "--bbox",
        help='Override bounding box: "south,west,north,east"'
    )
    parser.add_argument(
        "--skip-download", action="store_true",
        help="Skip .laz download — use cached tiles only"
    )
    parser.add_argument(
        "--synthetic", action="store_true",
        help="Generate synthetic flat DEM for testing (no download needed)"
    )
    parser.add_argument(
        "--cache-dir",
        help=f"LiDAR tile cache directory (default: {DEFAULT_CACHE_DIR})"
    )
    parser.add_argument(
        "--extract-heights", action="store_true",
        help="Extract per-building heights + roof shapes from existing DEM/DSM "
             "(requires fused_features.geojson from Stage 4)"
    )
    parser.add_argument(
        "--fused-geojson",
        help="Path to fused_features.geojson (required with --extract-heights)"
    )
    args = parser.parse_args()

    if args.extract_heights:
        # Stage 2E: Per-building height extraction
        out = Path(args.output)
        fused = args.fused_geojson or str(out / "fused_features.geojson")
        dem   = str(out / "davis_dem_1m.tif")
        dsm   = str(out / "davis_dsm_1m.tif")
        output = str(out / "lidar_building_heights.json")

        if not Path(fused).exists():
            log.error("fused_features.geojson not found at %s — run fuse.py first", fused)
            sys.exit(1)
        if not Path(dem).exists() or not Path(dsm).exists():
            log.error("DEM/DSM not found — run lidar.py first (or with --synthetic)")
            sys.exit(1)

        result = extract_building_heights(fused, dem, dsm, output)
        log.info("Done: %d buildings processed", result["buildings_processed"])
    else:
        run_lidar(
            manifest_path  = args.manifest,
            output_dir     = args.output,
            bbox_override  = args.bbox,
            skip_download  = args.skip_download,
            use_synthetic  = args.synthetic,
            cache_dir      = args.cache_dir,
        )


if __name__ == "__main__":
    main()
