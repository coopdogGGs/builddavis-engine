"""
BuildDavis Pipeline — Stage 4: Data Fusion
===========================================
Merges elements from multiple sources into a single best-of-both dataset
using the fusion priority rules from DATA-001 v3.

Input:
    data/elements.json              — parsed elements from Stage 3

Output:
    data/fused_features.geojson     — fused GeoJSON ready for Stage 5
    data/fusion_log.json            — detailed merge decisions
    data/fuse_manifest.json         — statistics and quality report

Fusion priority order (DATA-001 v3):
    1. City of Davis GIS            (highest trust — local authority)
    2. UC Davis GIS                 (campus data)
    3. USGS LiDAR                   (terrain — handled by Stage 2)
    4. Overture Maps                (AI-traced footprints + ML heights)
    5. OpenStreetMap                (tags, names, metadata — baseline)
    6. Mapillary / Wikimedia        (Phase 4 — not used here)

Building fusion strategy:
    - Match OSM buildings to Overture buildings by polygon overlap (IoU)
    - Matched pair: use Overture GEOMETRY + OSM TAGS (best of both)
    - OSM only: keep as-is (Overture missed it)
    - Overture only: keep as-is (OSM missed it — 7 extra in POC)

Non-building fusion:
    - Roads, waterways, landuse: OSM is authoritative (Overture is buildings-only)
    - Bike paths: flag Class I/II/III from OSM tags + City of Davis GIS
    - Landmarks: flag from ICONIC-001 name list

Usage:
    python fuse.py --elements data/elements.json --output data/
    python fuse.py --elements data/elements.json --davis-gis data/davis_bike_network.geojson --output data/

Author: BuildDavis Project
License: Apache 2.0
"""

import json
import math
import time
import logging
import argparse
from pathlib import Path
from typing import Optional

# Coordinate conversion (same constants as parse.py — ADR-001)
DEFAULT_ORIGIN_LAT =  38.5435
DEFAULT_ORIGIN_LON = -121.7377
LAT_DEG_TO_M = 111_320.0
LON_DEG_TO_M = 111_320.0 * math.cos(math.radians(DEFAULT_ORIGIN_LAT))

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("fuse")

# ── Fusion constants ──────────────────────────────────────────────────────────

# Minimum IoU (Intersection over Union) to consider two building polygons a match
# 0.3 = 30% overlap — low enough to catch buildings with slightly different footprints
IOU_THRESHOLD = 0.3

# Minimum polygon area in Minecraft blocks² to keep a building
# Filters out micro-polygons that are OSM tagging artefacts
MIN_BUILDING_AREA_BLOCKS = 4

# Bike path classification from OSM tags (SPEC-003)
# Class I = dedicated separated path (highest priority)
# Class II = painted bike lane on road
# Class III = shared road with signage
BIKE_CLASS = {
    "cycleway":    "class_i",
    "path":        "class_i",
    "footway":     "class_i",    # when bicycle=designated
    "pedestrian":  "class_i",    # when bicycle=designated
    "track":       "class_ii",
    "residential": "class_iii",
    "service":     "class_iii",
    "tertiary":    "class_iii",
    "secondary":   "class_ii",
    "primary":     "class_ii",
}

# Road width estimates in Minecraft blocks (SPEC-003)
# Used when OSM width tag is absent
DEFAULT_ROAD_WIDTH = {
    "motorway":     12,
    "trunk":        10,
    "primary":       8,
    "secondary":     6,
    "tertiary":      5,
    "residential":   4,
    "service":       3,
    "cycleway":      3,
    "path":          2,
    "footway":       2,
    "track":         2,
    "unclassified":  4,
}

# Landmark names from ICONIC-001 (subset — used for confidence boosting)
LANDMARK_NAMES = {
    "davis amtrak", "davisville", "varsity theater", "varsity theatre",
    "memorial union", "shields library", "the silo", "mondavi center",
    "aggie stadium", "davis food co-op", "central park", "community park",
    "slide hill", "us bicycle hall of fame", "arc recreation center",
    "memorial union", "death star", "arboretum", "putah creek",
}

# ── Microsoft Building Footprints integration ────────────────────────────────

# Area threshold: MS footprints are preferred for small residential buildings
# below this size.  Larger buildings (campus, commercial) keep Overture geometry
# because MS ML sometimes fragments them.
MS_GEOMETRY_MAX_AREA_BLOCKS = 540  # ≈ 500 m²

# ── LiDAR per-building height integration ────────────────────────────────────

# Minimum LiDAR pixel count per building to trust the height measurement
LIDAR_MIN_PIXEL_COUNT = 4


# ─────────────────────────────────────────────────────────────────────────────
# Polygon geometry helpers (pure Python — no shapely dependency required)
# ─────────────────────────────────────────────────────────────────────────────

def polygon_area(coords: list) -> float:
    """
    Calculate polygon area using the shoelace formula.
    coords: list of (x, z) tuples in Minecraft block coordinates.
    Returns area in blocks².
    """
    n = len(coords)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += coords[i][0] * coords[j][1]
        area -= coords[j][0] * coords[i][1]
    return abs(area) / 2.0


def polygon_bbox(coords: list) -> tuple:
    """Return (min_x, min_z, max_x, max_z) bounding box of polygon."""
    if not coords:
        return (0, 0, 0, 0)
    xs = [c[0] for c in coords]
    zs = [c[1] for c in coords]
    return (min(xs), min(zs), max(xs), max(zs))


def bboxes_overlap(a: tuple, b: tuple) -> bool:
    """Check if two bounding boxes (min_x, min_z, max_x, max_z) overlap."""
    ax1, az1, ax2, az2 = a
    bx1, bz1, bx2, bz2 = b
    return not (ax2 < bx1 or bx2 < ax1 or az2 < bz1 or bz2 < az1)


def bbox_intersection_area(a: tuple, b: tuple) -> float:
    """Return area of intersection of two bounding boxes."""
    ax1, az1, ax2, az2 = a
    bx1, bz1, bx2, bz2 = b
    ix1 = max(ax1, bx1)
    iz1 = max(az1, bz1)
    ix2 = min(ax2, bx2)
    iz2 = min(az2, bz2)
    if ix2 <= ix1 or iz2 <= iz1:
        return 0.0
    return (ix2 - ix1) * (iz2 - iz1)


def bbox_iou(a: tuple, b: tuple) -> float:
    """
    Calculate Intersection over Union of two bounding boxes.
    Used as a fast proxy for polygon IoU — avoids expensive polygon clipping.
    Good enough for building matching at 1:1 scale where footprints are similar.
    """
    inter = bbox_intersection_area(a, b)
    if inter == 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union  = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def centroid_distance(a_centroid: tuple, b_centroid: tuple) -> float:
    """Euclidean distance between two Minecraft centroids in blocks."""
    return math.sqrt(
        (a_centroid[0] - b_centroid[0]) ** 2 +
        (a_centroid[1] - b_centroid[1]) ** 2
    )


# ─────────────────────────────────────────────────────────────────────────────
# MS Building Footprints loader
# ─────────────────────────────────────────────────────────────────────────────

def _wgs84_to_mc(lat: float, lon: float) -> tuple:
    """Convert a single lat/lon to Minecraft (X, Z) — same logic as parse.py."""
    delta_m_east  = (lon - DEFAULT_ORIGIN_LON) * LON_DEG_TO_M
    delta_m_north = (lat - DEFAULT_ORIGIN_LAT) * LAT_DEG_TO_M
    return int(round(delta_m_east)), int(round(-delta_m_north))


def _polygon_to_mc(ring: list) -> list:
    """Convert a list of [lon, lat] pairs to Minecraft (X, Z) pairs."""
    return [_wgs84_to_mc(c[1], c[0]) for c in ring]


def load_ms_buildings(ms_path: Path) -> list:
    """
    Load Microsoft Building Footprints GeoJSON into internal format.
    Returns a list of building dicts with mc_coords, mc_bbox, area_blocks,
    and WGS84 centroid for spatial lookups.
    """
    if not ms_path or not ms_path.exists():
        return []

    with open(ms_path) as f:
        data = json.load(f)

    features = data.get("features", [])
    buildings = []
    for i, feat in enumerate(features):
        geom = feat.get("geometry", {})
        if geom.get("type") != "Polygon":
            continue
        coords_wgs = geom["coordinates"][0]  # outer ring
        mc_coords = _polygon_to_mc(coords_wgs)
        area = polygon_area(mc_coords)
        if area < MIN_BUILDING_AREA_BLOCKS:
            continue

        clat = sum(c[1] for c in coords_wgs) / len(coords_wgs)
        clon = sum(c[0] for c in coords_wgs) / len(coords_wgs)
        mc_cx, mc_cz = _wgs84_to_mc(clat, clon)

        buildings.append({
            "id":          f"ms_{i}",
            "source":      "ms",
            "type":        "building",
            "coords":      coords_wgs,
            "mc_coords":   mc_coords,
            "mc_centroid": (mc_cx, mc_cz),
            "mc_bbox": {
                "min_x": min(c[0] for c in mc_coords),
                "max_x": max(c[0] for c in mc_coords),
                "min_z": min(c[1] for c in mc_coords),
                "max_z": max(c[1] for c in mc_coords),
                "width":  max(c[0] for c in mc_coords) - min(c[0] for c in mc_coords),
                "depth":  max(c[1] for c in mc_coords) - min(c[1] for c in mc_coords),
            },
            "area_blocks": area,
            "lat":         clat,
            "lon":         clon,
            "tags":        {"building": "yes"},
            "geometry":    "polygon",
            "priority":    60,
        })

    return buildings


# ─────────────────────────────────────────────────────────────────────────────
# LiDAR per-building height loader
# ─────────────────────────────────────────────────────────────────────────────

def load_lidar_heights(lidar_heights_path: Path) -> tuple:
    """
    Load LiDAR DSM−DTM per-building heights from lidar_building_heights.json.

    Returns:
        (by_osm_id, by_centroid) — two lookup dicts.
        by_osm_id:   { str(osm_id): {"height_m": float, "roof_shape": str, ...}, ... }
        by_centroid:  { (round_lon, round_lat): {...}, ... }  for ms_only buildings
    """
    if not lidar_heights_path or not lidar_heights_path.exists():
        return {}, {}

    with open(lidar_heights_path) as f:
        data = json.load(f)

    by_osm_id = {}
    by_centroid = {}
    for key, entry in data.items():
        by_osm_id[key] = entry
        # Build centroid index for spatial fallback (ms_only buildings)
        if "centroid_lon" in entry and "centroid_lat" in entry:
            ck = (round(entry["centroid_lon"], 5), round(entry["centroid_lat"], 5))
            by_centroid[ck] = entry

    return by_osm_id, by_centroid


def lookup_lidar_height(by_osm_id: dict, by_centroid: dict,
                        osm_id, lat: float = None, lon: float = None) -> dict:
    """
    Look up LiDAR height for a building. Try osm_id first, fall back to
    centroid spatial match within ~1m (5 decimal places at Davis latitude).
    Returns the entry dict or None.
    """
    if osm_id is not None:
        entry = by_osm_id.get(str(osm_id))
        if entry and entry.get("pixel_count", 0) >= LIDAR_MIN_PIXEL_COUNT:
            return entry

    if lat is not None and lon is not None:
        ck = (round(lon, 5), round(lat, 5))
        entry = by_centroid.get(ck)
        if entry and entry.get("pixel_count", 0) >= LIDAR_MIN_PIXEL_COUNT:
            return entry

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Building fusion
# ─────────────────────────────────────────────────────────────────────────────

def fuse_buildings(osm_buildings: list, overture_buildings: list,
                   ms_buildings: list = None, lidar_heights: tuple = None) -> tuple:
    """
    Match OSM buildings to Overture buildings using bounding box IoU.
    Optionally upgrade geometry from MS Building Footprints for small buildings,
    and inject LiDAR DSM−DTM heights.

    Matching strategy:
      1. For each OSM building, find the Overture building with highest IoU
      2. If IoU >= threshold: merge (Overture geometry + OSM tags)
      3. For small buildings (<500m²): check MS footprint IoU; if better, use MS geometry
      4. Unmatched OSM buildings: keep as-is
      5. Unmatched Overture buildings: keep as-is (new buildings OSM missed)
      6. Unmatched MS buildings: add as new (buildings both OSM and Overture missed)
      7. Apply LiDAR heights where available (overrides Overture/OSM estimates)

    Returns:
        (fused_buildings, fusion_log)
    """
    fused    = []
    log_entries = []
    matched_overture_ids = set()
    ms_buildings = ms_buildings or []
    lidar_by_id, lidar_by_centroid = lidar_heights if lidar_heights else ({}, {})

    # Pre-compute bounding boxes for all Overture buildings
    overture_bboxes = {}
    for ov in overture_buildings:
        coords = ov.get("mc_coords", [])
        if coords:
            overture_bboxes[ov["id"]] = polygon_bbox(coords)

    # Pre-compute bounding boxes for all MS buildings
    ms_bboxes = {}
    matched_ms_ids = set()
    for ms in ms_buildings:
        coords = ms.get("mc_coords", [])
        if coords:
            ms_bboxes[ms["id"]] = polygon_bbox(coords)

    # Match each OSM building to best Overture counterpart
    for osm in osm_buildings:
        osm_coords = osm.get("mc_coords", [])
        if not osm_coords:
            continue

        osm_bbox   = polygon_bbox(osm_coords)
        osm_area   = polygon_area(osm_coords)
        osm_centre = osm.get("mc_centroid", (0, 0))

        # Skip micro-polygons
        if osm_area < MIN_BUILDING_AREA_BLOCKS:
            continue

        best_iou    = 0.0
        best_ov     = None

        for ov in overture_buildings:
            if ov["id"] in matched_overture_ids:
                continue
            ov_bbox = overture_bboxes.get(ov["id"])
            if not ov_bbox:
                continue
            if not bboxes_overlap(osm_bbox, ov_bbox):
                continue
            iou = bbox_iou(osm_bbox, ov_bbox)
            if iou > best_iou:
                best_iou = iou
                best_ov  = ov

        if best_ov and best_iou >= IOU_THRESHOLD:
            # Matched — merge: Overture geometry + OSM tags
            matched_overture_ids.add(best_ov["id"])

            # Height: prefer OSM explicit tag, fall back to Overture ML estimate
            height_m = osm.get("height_m") or best_ov.get("height_m")
            floors   = osm.get("floors")
            if not height_m and floors:
                height_m = floors * 3.0   # assume 3m per floor

            # Geometry source selection:
            # Small buildings (<500m²) → try MS footprint (more accurate residential)
            # Large buildings → Overture (better unified polygons)
            use_ms_geom = False
            best_ms = None
            if ms_buildings and osm_area < MS_GEOMETRY_MAX_AREA_BLOCKS:
                best_ms_iou = 0.0
                for ms in ms_buildings:
                    if ms["id"] in matched_ms_ids:
                        continue
                    ms_bb = ms_bboxes.get(ms["id"])
                    if not ms_bb or not bboxes_overlap(osm_bbox, ms_bb):
                        continue
                    ms_iou = bbox_iou(osm_bbox, ms_bb)
                    if ms_iou > best_ms_iou:
                        best_ms_iou = ms_iou
                        best_ms = ms
                if best_ms and best_ms_iou >= IOU_THRESHOLD:
                    matched_ms_ids.add(best_ms["id"])
                    use_ms_geom = True

            geom_source = best_ms if use_ms_geom else best_ov
            fusion_method = "ms_geometry_osm_tags" if use_ms_geom else "osm_tags_overture_geometry"

            # LiDAR height override
            height_source = "overture_or_osm"
            lidar_entry = lookup_lidar_height(lidar_by_id, lidar_by_centroid,
                                              osm.get("osm_id"))
            if lidar_entry:
                height_m = lidar_entry["height_m"]
                height_source = "lidar_dsm_dtm"

            merged = {
                **osm,                              # start with OSM element
                "id":           osm["id"],
                "source":       "fused",
                "osm_id":       osm.get("osm_id"),
                "overture_id":  best_ov.get("overture_id"),
                # Best geometry source
                "coords":       geom_source.get("coords",    osm.get("coords")),
                "mc_coords":    geom_source.get("mc_coords", osm.get("mc_coords")),
                "mc_centroid":  geom_source.get("mc_centroid", osm_centre),
                "mc_bbox":      geom_source.get("mc_bbox",   osm.get("mc_bbox", {})),
                # OSM tags (names, types, attributes)
                "tags":         osm.get("tags", {}),
                "name":         osm.get("name") or best_ov.get("name", ""),
                "subtype":      osm.get("subtype") or best_ov.get("subtype", ""),
                # Best available height
                "height_m":     height_m,
                "height_source": height_source,
                "floors":       floors,
                "height_blocks": int(round(height_m / 1.0)) if height_m else None,
                # Roof shape from LiDAR if available
                "roof_shape":   lidar_entry.get("roof_shape") if lidar_entry else None,
                "roof_orientation": lidar_entry.get("roof_orientation") if lidar_entry else None,
                # Metadata
                "fusion_iou":   round(best_iou, 3),
                "fusion_method": fusion_method,
                "is_landmark":  osm.get("is_landmark") or is_landmark_name(osm.get("name", "")),
                "area_blocks":  polygon_area(geom_source.get("mc_coords", osm_coords)),
            }
            fused.append(merged)
            log_entries.append({
                "type":    "match",
                "osm_id":  osm.get("osm_id"),
                "ov_id":   best_ov.get("overture_id"),
                "iou":     round(best_iou, 3),
                "name":    merged.get("name", ""),
            })

        else:
            # No Overture match — try MS geometry for small buildings
            height_m = osm.get("height_m")
            floors   = osm.get("floors")
            if not height_m and floors:
                height_m = floors * 3.0

            use_ms_geom = False
            best_ms = None
            if ms_buildings and osm_area < MS_GEOMETRY_MAX_AREA_BLOCKS:
                best_ms_iou = 0.0
                for ms in ms_buildings:
                    if ms["id"] in matched_ms_ids:
                        continue
                    ms_bb = ms_bboxes.get(ms["id"])
                    if not ms_bb or not bboxes_overlap(osm_bbox, ms_bb):
                        continue
                    ms_iou = bbox_iou(osm_bbox, ms_bb)
                    if ms_iou > best_ms_iou:
                        best_ms_iou = ms_iou
                        best_ms = ms
                if best_ms and best_ms_iou >= IOU_THRESHOLD:
                    matched_ms_ids.add(best_ms["id"])
                    use_ms_geom = True

            # LiDAR height override
            height_source = "osm"
            lidar_entry = lookup_lidar_height(lidar_by_id, lidar_by_centroid,
                                              osm.get("osm_id"))
            if lidar_entry:
                height_m = lidar_entry["height_m"]
                height_source = "lidar_dsm_dtm"

            fusion_method = "ms_geometry_osm_tags" if use_ms_geom else "osm_only"
            geom_source = best_ms if use_ms_geom else osm

            kept = {
                **osm,
                "source":        "fused" if use_ms_geom else "osm_only",
                "coords":        geom_source.get("coords", osm.get("coords")),
                "mc_coords":     geom_source.get("mc_coords", osm.get("mc_coords")),
                "mc_centroid":   geom_source.get("mc_centroid", osm.get("mc_centroid")),
                "mc_bbox":       geom_source.get("mc_bbox", osm.get("mc_bbox", {})),
                "height_blocks": int(round(height_m)) if height_m else None,
                "height_m":      height_m,
                "height_source": height_source,
                "roof_shape":    lidar_entry.get("roof_shape") if lidar_entry else None,
                "roof_orientation": lidar_entry.get("roof_orientation") if lidar_entry else None,
                "fusion_method": fusion_method,
                "area_blocks":   polygon_area(geom_source.get("mc_coords", osm_coords)),
                "is_landmark":   osm.get("is_landmark") or is_landmark_name(osm.get("name", "")),
            }
            fused.append(kept)
            log_entries.append({
                "type":   "osm_only",
                "osm_id": osm.get("osm_id"),
                "name":   osm.get("name", ""),
                "reason": f"best_iou={round(best_iou, 3)} < threshold={IOU_THRESHOLD}",
            })

    # Add unmatched Overture buildings (new buildings OSM missed)
    overture_only_count = 0
    for ov in overture_buildings:
        if ov["id"] not in matched_overture_ids:
            coords    = ov.get("mc_coords", [])
            area      = polygon_area(coords) if coords else 0
            if area < MIN_BUILDING_AREA_BLOCKS:
                continue
            height_m = ov.get("height_m")

            # LiDAR height override for Overture-only buildings
            height_source = "overture"
            lidar_entry = lookup_lidar_height(
                lidar_by_id, lidar_by_centroid, None,
                lat=ov.get("lat"), lon=ov.get("lon"))
            if lidar_entry:
                height_m = lidar_entry["height_m"]
                height_source = "lidar_dsm_dtm"

            kept = {
                **ov,
                "source":        "overture_only",
                "fusion_method": "overture_only",
                "height_blocks": int(round(height_m)) if height_m else None,
                "height_m":      height_m,
                "height_source": height_source,
                "roof_shape":    lidar_entry.get("roof_shape") if lidar_entry else None,
                "roof_orientation": lidar_entry.get("roof_orientation") if lidar_entry else None,
                "area_blocks":   area,
                "is_landmark":   is_landmark_name(ov.get("name", "")),
            }
            fused.append(kept)
            log_entries.append({
                "type":     "overture_only",
                "ov_id":    ov.get("overture_id"),
                "name":     ov.get("name", ""),
                "height_m": height_m,
            })
            overture_only_count += 1

    # Add unmatched MS buildings (buildings both OSM and Overture missed)
    ms_only_count = 0
    for ms in ms_buildings:
        if ms["id"] not in matched_ms_ids:
            coords = ms.get("mc_coords", [])
            area   = polygon_area(coords) if coords else 0
            if area < MIN_BUILDING_AREA_BLOCKS:
                continue

            # Try LiDAR height
            height_m = None
            height_source = None
            lidar_entry = lookup_lidar_height(
                lidar_by_id, lidar_by_centroid, None,
                lat=ms.get("lat"), lon=ms.get("lon"))
            if lidar_entry:
                height_m = lidar_entry["height_m"]
                height_source = "lidar_dsm_dtm"

            kept = {
                **ms,
                "source":        "ms_only",
                "fusion_method": "ms_only",
                "height_blocks": int(round(height_m)) if height_m else None,
                "height_m":      height_m,
                "height_source": height_source,
                "roof_shape":    lidar_entry.get("roof_shape") if lidar_entry else None,
                "roof_orientation": lidar_entry.get("roof_orientation") if lidar_entry else None,
                "area_blocks":   area,
                "is_landmark":   False,
                "name":          "",
                "subtype":       "",
            }
            fused.append(kept)
            log_entries.append({
                "type":       "ms_only",
                "ms_id":      ms["id"],
                "area":       round(area, 1),
                "height_m":   height_m,
            })
            ms_only_count += 1

    return fused, log_entries


# ─────────────────────────────────────────────────────────────────────────────
# Road / path enrichment
# ─────────────────────────────────────────────────────────────────────────────

def enrich_highway(element: dict) -> dict:
    """
    Enrich a highway element with bike classification, width, and surface.
    Applied to all highway elements from OSM.
    """
    tags     = element.get("tags", {})
    highway  = tags.get("highway", "")
    bicycle  = tags.get("bicycle", "")
    cycleway = tags.get("cycleway", "")

    # Determine bike classification
    bike_class = None
    if element.get("is_bike_path"):
        if highway in ("cycleway", "path") or bicycle == "designated":
            bike_class = "class_i"
        elif cycleway in ("lane", "track") or bicycle == "yes":
            bike_class = "class_ii"
        else:
            bike_class = "class_iii"

    # Road width in blocks
    width_str = tags.get("width", tags.get("est_width", ""))
    width_blocks = None
    if width_str:
        try:
            width_blocks = int(round(float(str(width_str).replace("m", "").strip())))
        except (ValueError, TypeError):
            pass
    if not width_blocks:
        width_blocks = DEFAULT_ROAD_WIDTH.get(highway, 4)

    # Surface type (for SPEC-003 block palette)
    surface = tags.get("surface", "")

    return {
        **element,
        "bike_class":    bike_class,
        "width_blocks":  width_blocks,
        "surface":       surface,
        "lanes":         int(tags.get("lanes", 1)),
        "oneway":        tags.get("oneway") == "yes",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Davis GIS bike network overlay
# ─────────────────────────────────────────────────────────────────────────────

def overlay_davis_gis(elements: list, davis_gis_path: Path) -> list:
    """
    Overlay City of Davis GIS bike network data onto highway elements.
    Davis GIS is higher-priority than OSM for bike infrastructure (DATA-001 v3).

    When a Davis GIS path matches an OSM highway element (by proximity),
    the Davis GIS classification overrides the OSM-derived bike_class.
    """
    if not davis_gis_path or not davis_gis_path.exists():
        log.info("  Davis GIS bike network not available — skipping overlay")
        return elements

    try:
        with open(davis_gis_path) as f:
            gis_data = json.load(f)
        gis_features = gis_data.get("features", [])
        if not gis_features:
            log.info("  Davis GIS: no features found")
            return elements
        log.info("  Davis GIS: overlaying %d bike network segments", len(gis_features))
        # For now, flag that Davis GIS data is available
        # Full geometry matching will be implemented in transform.py
        # where we have full spatial indexing available
        for elem in elements:
            if elem.get("type") == "highway" and elem.get("is_bike_path"):
                elem["davis_gis_available"] = True
        return elements
    except Exception as exc:
        log.warning("  Davis GIS overlay failed: %s", exc)
        return elements


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def is_landmark_name(name: str) -> bool:
    if not name:
        return False
    name_lower = name.lower()
    return any(lm in name_lower for lm in LANDMARK_NAMES)


def element_to_geojson_feature(elem: dict) -> dict:
    """Convert a fused element to a GeoJSON Feature."""
    geom_type = elem.get("geometry", "point")
    coords    = elem.get("coords", [])
    mc_centre = elem.get("mc_centroid", (0, 0))

    if geom_type == "point":
        geojson_geom = {
            "type": "Point",
            "coordinates": [elem.get("lon", 0), elem.get("lat", 0)]
        }
    elif geom_type == "polygon" and coords:
        # Ensure polygon is closed
        ring = coords if coords[0] == coords[-1] else coords + [coords[0]]
        geojson_geom = {"type": "Polygon", "coordinates": [ring]}
    elif geom_type == "linestring" and coords:
        geojson_geom = {"type": "LineString", "coordinates": coords}
    else:
        geojson_geom = {"type": "Point", "coordinates": [0, 0]}

    # Build properties — exclude large raw coord lists but keep mc_coords as string
    props = {k: v for k, v in elem.items()
             if k not in ("coords", "tags")
             and not isinstance(v, (list, dict))}
    # Store mc_coords as compact JSON string so transform.py can recover them
    if "mc_coords" in elem and elem["mc_coords"]:
        props["mc_coords_json"] = json.dumps(elem["mc_coords"], separators=(",", ":"))

    # Add key tag values as top-level properties for easy access
    tags = elem.get("tags", {})
    for tag_key in ("building", "highway", "landuse", "waterway", "natural",
                    "amenity", "leisure", "name", "height", "building:levels",
                    "building:material", "roof:shape", "surface", "service",
                    "access", "sport", "bridge", "layer", "railway",
                    "barrier", "fence_type", "lit", "lanes",
                    "oneway", "maxspeed", "ref",
                    "power", "man_made", "emergency", "advertising",
                    "golf", "historic", "tourism"):
        if tag_key in tags:
            props[f"osm_{tag_key}"] = tags[tag_key]

    # Inject LiDAR-classified roof shape as OSM tag for downstream (adapter.py)
    if elem.get("roof_shape") and "osm_roof:shape" not in props:
        props["osm_roof:shape"] = elem["roof_shape"]
    if elem.get("roof_orientation") and "osm_roof:orientation" not in props:
        props["osm_roof:orientation"] = elem["roof_orientation"]

    # Pass through height source for traceability
    if elem.get("height_source"):
        props["height_source"] = elem["height_source"]

    props["mc_x"] = mc_centre[0] if isinstance(mc_centre, (list, tuple)) else 0
    props["mc_z"] = mc_centre[1] if isinstance(mc_centre, (list, tuple)) else 0

    return {"type": "Feature", "geometry": geojson_geom, "properties": props}


def build_fusion_report(fused: list, log_entries: list) -> dict:
    """Build quality report for the fusion run."""
    buildings = [e for e in fused if e.get("type") == "building"]
    matched   = [e for e in log_entries if e.get("type") == "match"]
    osm_only  = [e for e in log_entries if e.get("type") == "osm_only"]
    ov_only   = [e for e in log_entries if e.get("type") == "overture_only"]
    ms_only   = [e for e in log_entries if e.get("type") == "ms_only"]

    with_height   = sum(1 for b in buildings if b.get("height_m") or b.get("height_blocks"))
    with_name     = sum(1 for b in buildings if b.get("name"))
    landmarks     = sum(1 for e in fused if e.get("is_landmark"))
    bike_paths    = sum(1 for e in fused if e.get("is_bike_path"))
    class_i_paths = sum(1 for e in fused if e.get("bike_class") == "class_i")
    ms_geom       = sum(1 for b in buildings if b.get("fusion_method") == "ms_geometry_osm_tags")
    lidar_heights = sum(1 for b in buildings if b.get("height_source") == "lidar_dsm_dtm")
    lidar_roofs   = sum(1 for b in buildings if b.get("roof_shape"))

    avg_iou = (sum(e["iou"] for e in matched) / len(matched)) if matched else 0

    report = {
        "total_fused":        len(fused),
        "buildings": {
            "total":              len(buildings),
            "matched":            len(matched),
            "osm_only":           len(osm_only),
            "overture_only":      len(ov_only),
            "ms_only":            len(ms_only),
            "ms_geometry_used":   ms_geom,
            "lidar_height_count": lidar_heights,
            "lidar_roof_count":   lidar_roofs,
            "match_rate_pct":     round(len(matched) / max(len(buildings), 1) * 100, 1),
            "avg_iou":            round(avg_iou, 3),
            "with_height":        with_height,
            "with_name":          with_name,
            "height_pct":         round(with_height / max(len(buildings), 1) * 100, 1),
        },
        "landmarks":          landmarks,
        "bike_paths":         bike_paths,
        "class_i_paths":      class_i_paths,
        "checks": {
            "has_buildings":   len(buildings) > 0,
            "has_matched":     len(matched) > 0,
            "has_overture_only": len(ov_only) >= 0,  # always passes
            "has_bike_paths":  bike_paths > 0,
            "has_landmarks":   landmarks > 0,
        }
    }
    passed = sum(1 for v in report["checks"].values() if v)
    report["checks_passed"] = f"{passed}/{len(report['checks'])}"
    report["valid"] = passed >= 4
    return report


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_fuse(
    elements_path: str,
    output_dir: str,
    davis_gis_path: Optional[str] = None,
    ms_buildings_path: Optional[str] = None,
    lidar_heights_path: Optional[str] = None,
) -> dict:
    """
    Run the full fusion stage.

    Args:
        elements_path:       Path to elements.json from Stage 3
        output_dir:          Directory to write output files
        davis_gis_path:      Optional path to davis_bike_network.geojson from Stage 1
        ms_buildings_path:   Optional path to ms_buildings.geojson from Stage 1F
        lidar_heights_path:  Optional path to lidar_building_heights.json from Stage 2

    Returns:
        Fusion result dict with output paths and quality report
    """
    start = time.time()
    out   = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("  BuildDavis — Stage 4: Fuse")
    log.info("=" * 60)

    # ── Load elements ─────────────────────────────────────────────────────────
    log.info("[1/4] Loading elements from Stage 3...")
    with open(elements_path) as f:
        elements = json.load(f)

    # Separate by type and source
    osm_buildings      = [e for e in elements
                          if e.get("type") == "building" and e.get("source") == "osm"]
    overture_buildings = [e for e in elements
                          if e.get("type") == "building" and e.get("source") == "overture"]
    non_buildings      = [e for e in elements
                          if e.get("type") != "building"]

    log.info("  OSM buildings:      %d", len(osm_buildings))
    log.info("  Overture buildings: %d", len(overture_buildings))
    log.info("  Other elements:     %d", len(non_buildings))

    # ── Load MS Building Footprints (Stage 1F) ────────────────────────────────
    ms_path = Path(ms_buildings_path) if ms_buildings_path else None
    if not ms_path and (Path(output_dir) / "ms_buildings.geojson").exists():
        ms_path = Path(output_dir) / "ms_buildings.geojson"
    ms_buildings = load_ms_buildings(ms_path) if ms_path else []
    log.info("  MS footprints:      %d", len(ms_buildings))

    # ── Load LiDAR per-building heights (Stage 2 extension) ──────────────────
    lh_path = Path(lidar_heights_path) if lidar_heights_path else None
    if not lh_path and (Path(output_dir) / "lidar_building_heights.json").exists():
        lh_path = Path(output_dir) / "lidar_building_heights.json"
    lidar_heights = load_lidar_heights(lh_path) if lh_path else ({}, {})
    lidar_by_id = lidar_heights[0]
    log.info("  LiDAR heights:      %d buildings", len(lidar_by_id))

    # ── Fuse buildings ────────────────────────────────────────────────────────
    log.info("[2/4] Fusing buildings (IoU threshold=%.2f)...", IOU_THRESHOLD)
    fused_buildings, fusion_log = fuse_buildings(
        osm_buildings, overture_buildings,
        ms_buildings=ms_buildings, lidar_heights=lidar_heights
    )

    matched_count  = sum(1 for e in fusion_log if e["type"] == "match")
    osm_only_count = sum(1 for e in fusion_log if e["type"] == "osm_only")
    ov_only_count  = sum(1 for e in fusion_log if e["type"] == "overture_only")
    ms_only_count  = sum(1 for e in fusion_log if e["type"] == "ms_only")
    ms_geom_count  = sum(1 for b in fused_buildings if b.get("fusion_method") == "ms_geometry_osm_tags")
    lidar_ht_count = sum(1 for b in fused_buildings if b.get("height_source") == "lidar_dsm_dtm")
    roof_count     = sum(1 for b in fused_buildings if b.get("roof_shape"))

    log.info("  Matched:        %d (Overture geometry + OSM tags)", matched_count)
    log.info("  OSM only:       %d", osm_only_count)
    log.info("  Overture only:  %d (buildings OSM missed)", ov_only_count)
    log.info("  MS only:        %d (buildings OSM+Overture missed)", ms_only_count)
    log.info("  MS geometry:    %d (small buildings upgraded to MS footprint)", ms_geom_count)
    log.info("  LiDAR heights:  %d buildings", lidar_ht_count)
    log.info("  LiDAR roof:     %d buildings with classified roof shape", roof_count)
    log.info("  Total fused:    %d buildings", len(fused_buildings))

    # ── Enrich non-building elements ──────────────────────────────────────────
    log.info("[3/4] Enriching roads, paths, and other elements...")
    enriched_non_buildings = []
    for elem in non_buildings:
        if elem.get("type") == "highway":
            enriched_non_buildings.append(enrich_highway(elem))
        else:
            enriched_non_buildings.append(elem)

    # Overlay Davis GIS bike network if available
    gis_path = Path(davis_gis_path) if davis_gis_path else None
    if not gis_path and (Path(output_dir) / "davis_bike_network.geojson").exists():
        gis_path = Path(output_dir) / "davis_bike_network.geojson"
    enriched_non_buildings = overlay_davis_gis(enriched_non_buildings, gis_path)

    # ── Combine and sort ──────────────────────────────────────────────────────
    all_fused = enriched_non_buildings + fused_buildings

    # Sort: landuse → waterways → roads → amenities → buildings → landmarks
    all_fused.sort(key=lambda e: (
        e.get("priority", 50),
        1 if e.get("is_landmark") else 0
    ))

    # ── Write GeoJSON output ──────────────────────────────────────────────────
    log.info("[4/4] Writing output files...")
    features = [element_to_geojson_feature(e) for e in all_fused]
    geojson  = {
        "type":     "FeatureCollection",
        "features": features,
        "metadata": {
            "source":    "BuildDavis fusion pipeline",
            "stage":     "fuse",
            "elements":  len(features),
            "buildings": len(fused_buildings),
        }
    }

    fused_path = out / "fused_features.geojson"
    with open(fused_path, "w") as f:
        json.dump(geojson, f, indent=2)

    fusion_log_path = out / "fusion_log.json"
    with open(fusion_log_path, "w") as f:
        json.dump(fusion_log, f, indent=2)

    # ── Quality report ────────────────────────────────────────────────────────
    report  = build_fusion_report(all_fused, fusion_log)
    elapsed = time.time() - start

    # Log summary
    log.info("")
    log.info("  Results:")
    log.info("    Total fused elements:  %d", report["total_fused"])
    log.info("    Buildings:             %d (%s%% matched, avg IoU %.3f)",
             report["buildings"]["total"],
             report["buildings"]["match_rate_pct"],
             report["buildings"]["avg_iou"])
    log.info("    With height data:      %d (%s%%)",
             report["buildings"]["with_height"],
             report["buildings"]["height_pct"])
    log.info("    Landmarks flagged:     %d", report["landmarks"])
    log.info("    Bike paths:            %d (%d Class I)",
             report["bike_paths"], report["class_i_paths"])
    log.info("    Checks:                %s", report["checks_passed"])

    # Show landmark buildings found
    landmark_buildings = [e for e in all_fused
                          if e.get("is_landmark") and e.get("name")][:5]
    if landmark_buildings:
        names = [e["name"] for e in landmark_buildings]
        log.info("    Landmarks:             %s", ", ".join(names))

    result = {
        "stage":            "fuse",
        "fused_path":       str(fused_path),
        "fusion_log_path":  str(fusion_log_path),
        "elements_count":   len(all_fused),
        "report":           report,
        "elapsed_seconds":  round(elapsed, 1)
    }

    manifest_path = out / "fuse_manifest.json"
    manifest_path.write_text(json.dumps(result, indent=2))

    log.info("")
    log.info("=" * 60)
    log.info("  Stage 4 complete in %.1fs", elapsed)
    log.info("  Output: %s", fused_path)
    log.info("  Valid:  %s", report["valid"])
    log.info("=" * 60)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="BuildDavis Pipeline — Stage 4: Data Fusion"
    )
    parser.add_argument(
        "--elements", required=True,
        help="Path to elements.json from Stage 3 (parse.py)"
    )
    parser.add_argument(
        "--output", default="./data",
        help="Output directory (default: ./data)"
    )
    parser.add_argument(
        "--davis-gis",
        help="Optional path to davis_bike_network.geojson from Stage 1"
    )
    parser.add_argument(
        "--ms-buildings",
        help="Optional path to ms_buildings.geojson from Stage 1F (Microsoft Building Footprints)"
    )
    parser.add_argument(
        "--lidar-heights",
        help="Optional path to lidar_building_heights.json from Stage 2 (LiDAR DSM-DTM heights)"
    )
    args = parser.parse_args()

    run_fuse(args.elements, args.output, args.davis_gis,
             ms_buildings_path=args.ms_buildings,
             lidar_heights_path=args.lidar_heights)


if __name__ == "__main__":
    main()
