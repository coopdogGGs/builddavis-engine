"""
BuildDavis Pipeline — Stage 3: OSM & Overture Parser
=====================================================
Converts raw OSM JSON and Overture GeoJSON from Stage 1 into a clean,
structured element list with Minecraft block coordinates calculated.

Input files (from Stage 1 fetch.py):
    data/osm_raw.json              — raw Overpass API response
    data/overture_buildings.geojson — AI-traced building footprints + heights

Output:
    data/elements.json             — structured, prioritised element list
    data/parse_manifest.json       — parse statistics and quality report

Coordinate system:
    Origin: Davis Amtrak Station (38.5435, -121.7377) = Minecraft (0, 0)
    Scale:  1:1  (1 real-world metre = 1 Minecraft block)
    X axis: East  (+X = East,  -X = West)
    Z axis: South (+Z = South, -Z = North)  [Minecraft convention]
    Y axis: Elevation from Stage 2 DEM (Y47 = typical Davis ground)

Element priority (higher = rendered on top / later):
    10  landuse (base layer — parks, farmland, residential zones)
    20  waterway
    30  natural (trees, grass, scrub)
    40  highway (roads and paths)
    50  amenity (street furniture, benches, bike racks)
    60  building (always on top of ground features)
    70  landmark (hand-craft priority overrides)

Usage:
    python parse.py --fetch-dir data/ --output data/
    python parse.py --fetch-dir data/ --output data/ --origin "38.5435,-121.7377"

Author: BuildDavis Project
License: Apache 2.0
"""

import os
import json
import math
import time
import logging
import argparse
from pathlib import Path
from typing import Optional

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("parse")

# ── Davis coordinate origin (Amtrak Station — spawn point) ───────────────────
# ADR-001: Spawn point = Davis Amtrak Station, 1:1 scale, Minecraft (0,0,0)
DEFAULT_ORIGIN_LAT =  38.5435
DEFAULT_ORIGIN_LON = -121.7377

# Metres per degree at Davis latitude (~38.54°)
LAT_DEG_TO_M = 111_320.0
LON_DEG_TO_M = 111_320.0 * math.cos(math.radians(DEFAULT_ORIGIN_LAT))

# Default spawn Y (ground level at station, from ADR-001)
SPAWN_Y = 48

# ── Element priority table (from SPEC-003) ────────────────────────────────────
PRIORITY = {
    "landuse":     10,
    "waterway":    20,
    "natural":     30,
    "golf":        30,   # ground-level landcover, renders before roads
    "highway":     40,
    "railway":     45,
    "power":       46,
    "amenity":     50,
    "leisure":     50,
    "barrier":     52,
    "man_made":    53,
    "emergency":   54,
    "advertising": 54,
    "tourism":     55,
    "historic":    55,
    "building":    60,
    "landmark":    70,
}

# ── OSM tag → element type mapping ───────────────────────────────────────────
# Maps the primary OSM key to our internal element type
OSM_KEY_TO_TYPE = {
    "building":   "building",
    "highway":    "highway",
    "waterway":   "waterway",
    "landuse":    "landuse",
    "natural":    "natural",
    "amenity":    "amenity",
    "leisure":    "leisure",
    "tourism":    "tourism",
    "historic":   "historic",
    "railway":    "railway",
    "barrier":    "barrier",
    "power":      "power",
    "man_made":   "man_made",
    "emergency":  "emergency",
    "advertising":"advertising",
    "golf":       "golf",
}

# ── Highway subtypes that are bike paths (SPEC-003) ──────────────────────────
BIKE_PATH_TYPES = {
    "cycleway", "path", "footway", "pedestrian", "track"
}

# ── Landmark names from ICONIC-001 (used to flag priority) ───────────────────
ICONIC_LANDMARKS = {
    "davis amtrak", "davisville", "varsity theater", "varsity theatre",
    "davis food co-op", "memorial union", "shields library", "the silo",
    "mondavi center", "aggie stadium", "slide hill", "central park",
    "community park", "us bicycle hall of fame", "explorit",
    "hattie weber", "arc recreation", "bike barn",
}


# ─────────────────────────────────────────────────────────────────────────────
# Coordinate conversion
# ─────────────────────────────────────────────────────────────────────────────

class CoordinateConverter:
    """
    Converts geographic coordinates (lat/lon) to Minecraft block coordinates.

    Origin: Davis Amtrak Station (spawn point)
    Scale:  1:1 — 1 metre = 1 Minecraft block
    X:      East (+) / West (-)
    Z:      South (+) / North (-)   [Minecraft convention — Z increases south]
    Y:      Elevation, handled separately by Stage 2 DEM
    """

    def __init__(self, origin_lat: float, origin_lon: float):
        self.origin_lat = origin_lat
        self.origin_lon = origin_lon
        self.lat_to_m = LAT_DEG_TO_M
        self.lon_to_m = LON_DEG_TO_M

    def to_minecraft(self, lat: float, lon: float) -> tuple[int, int]:
        """
        Convert lat/lon to Minecraft (X, Z) block coordinates.
        Returns integers — Minecraft blocks are whole numbers.
        """
        # Delta from origin in degrees
        delta_lat = lat - self.origin_lat
        delta_lon = lon - self.origin_lon

        # Convert to metres
        delta_m_north = delta_lat * self.lat_to_m   # positive = north
        delta_m_east  = delta_lon * self.lon_to_m   # positive = east

        # Minecraft convention: X = East, Z = South (inverted from North)
        mc_x = int(round(delta_m_east))
        mc_z = int(round(-delta_m_north))  # negate: north = -Z in Minecraft

        return mc_x, mc_z

    def polygon_to_minecraft(self, coords: list) -> list:
        """Convert a list of [lon, lat] coordinate pairs to Minecraft (X, Z) pairs."""
        return [self.to_minecraft(lat, lon) for lon, lat in coords]

    def bbox_minecraft(self, coords: list) -> dict:
        """Get the Minecraft bounding box of a polygon."""
        if not coords:
            return {}
        mc_coords = self.polygon_to_minecraft(coords)
        xs = [c[0] for c in mc_coords]
        zs = [c[1] for c in mc_coords]
        return {
            "min_x": min(xs), "max_x": max(xs),
            "min_z": min(zs), "max_z": max(zs),
            "width":  max(xs) - min(xs),
            "depth":  max(zs) - min(zs),
        }

    def centroid_minecraft(self, coords: list) -> tuple[int, int]:
        """Get the Minecraft centroid of a polygon."""
        if not coords:
            return 0, 0
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        return self.to_minecraft(sum(lats)/len(lats), sum(lons)/len(lons))


# ─────────────────────────────────────────────────────────────────────────────
# OSM parser
# ─────────────────────────────────────────────────────────────────────────────

def parse_osm(osm_data: dict, converter: CoordinateConverter) -> list:
    """
    Parse raw Overpass API JSON into structured elements.

    Handles:
      - nodes (points: trees, benches, amenities)
      - ways (polygons: buildings, landuse; lines: roads, waterways)
      - relations (complex multipolygons: large parks, building complexes)

    Returns a list of element dicts.
    """
    elements_out = []

    # Build a node lookup for way geometry
    node_lookup = {}
    for elem in osm_data.get("elements", []):
        if elem.get("type") == "node":
            node_lookup[elem["id"]] = (
                elem.get("lon", 0),
                elem.get("lat", 0)
            )

    for elem in osm_data.get("elements", []):
        etype = elem.get("type")
        tags  = elem.get("tags", {})
        eid   = elem.get("id")

        if not tags:
            continue

        # Determine element type from tags
        osm_type = None
        for key in OSM_KEY_TO_TYPE:
            if key in tags:
                osm_type = OSM_KEY_TO_TYPE[key]
                break

        if not osm_type:
            continue

        # ── Node elements (points) ────────────────────────────────────────────
        if etype == "node":
            lat = elem.get("lat", 0)
            lon = elem.get("lon", 0)
            mc_x, mc_z = converter.to_minecraft(lat, lon)

            out = {
                "id":       f"osm_node_{eid}",
                "source":   "osm",
                "osm_id":   eid,
                "osm_type": etype,
                "type":     osm_type,
                "subtype":  tags.get(osm_type, ""),
                "tags":     tags,
                "geometry": "point",
                "lat":      lat,
                "lon":      lon,
                "mc_x":     mc_x,
                "mc_z":     mc_z,
                "mc_y":     SPAWN_Y,
                "priority": PRIORITY.get(osm_type, 50),
                "name":     tags.get("name", ""),
                "is_landmark": is_landmark(tags),
            }
            elements_out.append(out)

        # ── Way elements (lines and polygons) ─────────────────────────────────
        elif etype == "way":
            # Resolve node references to coordinates
            node_refs = elem.get("nodes", [])

            # Try geometry field first (returned by Overpass with 'geom' output)
            if "geometry" in elem:
                coords = [[g["lon"], g["lat"]] for g in elem["geometry"]]
            else:
                coords = []
                for nid in node_refs:
                    if nid in node_lookup:
                        coords.append(list(node_lookup[nid]))

            if len(coords) < 2:
                continue

            is_closed = (len(coords) >= 3 and
                         coords[0][0] == coords[-1][0] and
                         coords[0][1] == coords[-1][1])
            geom_type = "polygon" if is_closed else "linestring"

            mc_coords  = converter.polygon_to_minecraft(coords)
            centroid   = converter.centroid_minecraft(coords)
            bbox       = converter.bbox_minecraft(coords) if is_closed else {}

            # Detect bike paths specifically for SPEC-003
            is_bike_path = (
                osm_type == "highway" and
                tags.get("highway") in BIKE_PATH_TYPES
            ) or tags.get("bicycle") in ("designated", "yes") \
              or tags.get("cycleway") is not None

            # Estimate building height from OSM tags
            height_m = None
            if osm_type == "building":
                height_m = extract_height(tags)

            out = {
                "id":          f"osm_way_{eid}",
                "source":      "osm",
                "osm_id":      eid,
                "osm_type":    etype,
                "type":        osm_type,
                "subtype":     tags.get(osm_type, ""),
                "tags":        tags,
                "geometry":    geom_type,
                "coords":      coords,
                "mc_coords":   mc_coords,
                "mc_centroid": centroid,
                "mc_bbox":     bbox,
                "mc_y":        SPAWN_Y,
                "priority":    PRIORITY.get(osm_type, 50),
                "name":        tags.get("name", ""),
                "height_m":    height_m,
                "floors":      extract_floors(tags),
                "material":    tags.get("building:material", ""),
                "is_bike_path": is_bike_path,
                "is_landmark": is_landmark(tags),
                "roof_shape":  tags.get("roof:shape", ""),
            }
            elements_out.append(out)

        # ── Relation elements (multipolygons) ─────────────────────────────────
        elif etype == "relation":
            # Relations are complex — extract outer ring as primary geometry
            members = elem.get("members", [])
            outer_coords = []

            for member in members:
                if member.get("role") == "outer" and "geometry" in member:
                    outer_coords = [[g["lon"], g["lat"]]
                                    for g in member["geometry"]]
                    break

            if len(outer_coords) < 3:
                continue

            mc_coords = converter.polygon_to_minecraft(outer_coords)
            centroid  = converter.centroid_minecraft(outer_coords)
            bbox      = converter.bbox_minecraft(outer_coords)

            out = {
                "id":          f"osm_rel_{eid}",
                "source":      "osm",
                "osm_id":      eid,
                "osm_type":    etype,
                "type":        osm_type,
                "subtype":     tags.get(osm_type, ""),
                "tags":        tags,
                "geometry":    "polygon",
                "coords":      outer_coords,
                "mc_coords":   mc_coords,
                "mc_centroid": centroid,
                "mc_bbox":     bbox,
                "mc_y":        SPAWN_Y,
                "priority":    PRIORITY.get(osm_type, 50),
                "name":        tags.get("name", ""),
                "height_m":    extract_height(tags),
                "floors":      extract_floors(tags),
                "material":    tags.get("building:material", ""),
                "is_bike_path": False,
                "is_landmark": is_landmark(tags),
                "roof_shape":  tags.get("roof:shape", ""),
            }
            elements_out.append(out)

    return elements_out


# ─────────────────────────────────────────────────────────────────────────────
# Overture parser
# ─────────────────────────────────────────────────────────────────────────────

def parse_overture(overture_data: dict, converter: CoordinateConverter) -> list:
    """
    Parse Overture Maps GeoJSON building footprints.

    Overture provides:
      - AI-traced building footprints (more accurate than OSM polygons)
      - ML height estimates from satellite imagery
      - Confidence scores

    Returns a list of building element dicts.
    """
    elements_out = []

    for feat in overture_data.get("features", []):
        props = feat.get("properties", {}) or {}
        geom  = feat.get("geometry", {}) or {}

        if geom.get("type") not in ("Polygon", "MultiPolygon"):
            continue

        # Get outer ring coordinates
        if geom["type"] == "Polygon":
            coords = geom.get("coordinates", [[]])[0]
        else:  # MultiPolygon — use largest ring
            rings = [ring[0] for ring in geom.get("coordinates", [])]
            coords = max(rings, key=len) if rings else []

        if len(coords) < 3:
            continue

        mc_coords = converter.polygon_to_minecraft(coords)
        centroid  = converter.centroid_minecraft(coords)
        bbox      = converter.bbox_minecraft(coords)

        # Extract height — Overture uses 'height' property in metres
        height_m = props.get("height") or props.get("building_height")
        if height_m:
            try:
                height_m = float(height_m)
            except (ValueError, TypeError):
                height_m = None

        # Extract Overture ID
        overture_id = (props.get("id") or
                       props.get("@id") or
                       f"ov_{hash(str(coords[:3]))}")

        out = {
            "id":           f"overture_{overture_id}",
            "source":       "overture",
            "overture_id":  overture_id,
            "type":         "building",
            "subtype":      props.get("class", props.get("subtype", "")),
            "tags":         {k: v for k, v in props.items()
                             if v is not None and k not in ("id", "@id")},
            "geometry":     "polygon",
            "coords":       coords,
            "mc_coords":    mc_coords,
            "mc_centroid":  centroid,
            "mc_bbox":      bbox,
            "mc_y":         SPAWN_Y,
            "priority":     PRIORITY["building"],
            "name":         props.get("names", {}).get("primary", "") if isinstance(props.get("names"), dict)
                            else props.get("name", ""),
            "height_m":     height_m,
            "floors":       None,
            "material":     "",
            "is_bike_path": False,
            "is_landmark":  False,
            "roof_shape":   "",
            "confidence":   props.get("confidence", None),
        }
        elements_out.append(out)

    return elements_out


# ─────────────────────────────────────────────────────────────────────────────
# Height and floor extraction helpers
# ─────────────────────────────────────────────────────────────────────────────

def extract_height(tags: dict) -> Optional[float]:
    """
    Extract building height in metres from OSM tags.
    Handles: height, building:height, roof:height, min_height
    Handles unit suffixes: "10 m", "30 ft", "3 floors"
    """
    for key in ("height", "building:height"):
        val = tags.get(key, "")
        if not val:
            continue
        val = str(val).strip().lower()
        try:
            # Plain number — assume metres
            return float(val)
        except ValueError:
            pass
        # Try with unit
        if "ft" in val or "'" in val:
            try:
                return float(val.replace("ft", "").replace("'", "").strip()) * 0.3048
            except ValueError:
                pass
        if "m" in val:
            try:
                return float(val.replace("m", "").strip())
            except ValueError:
                pass
    return None


def extract_floors(tags: dict) -> Optional[int]:
    """Extract number of floors from OSM tags."""
    for key in ("building:levels", "levels", "building:floors"):
        val = tags.get(key)
        if val:
            try:
                return int(float(str(val).strip()))
            except (ValueError, TypeError):
                pass
    return None


def is_landmark(tags: dict) -> bool:
    """Check if this element matches any ICONIC-001 landmark by name."""
    name = tags.get("name", "").lower()
    return any(landmark in name for landmark in ICONIC_LANDMARKS)


# ─────────────────────────────────────────────────────────────────────────────
# Priority sorting
# ─────────────────────────────────────────────────────────────────────────────

def sort_by_priority(elements: list) -> list:
    """
    Sort elements by render priority.
    Lower priority = base layer (rendered first).
    Higher priority = top layer (rendered last, wins conflicts).
    Within same priority, landmarks sort to the end (rendered last).
    """
    return sorted(elements, key=lambda e: (
        e.get("priority", 50),
        1 if e.get("is_landmark") else 0,
        e.get("name", "")
    ))


# ─────────────────────────────────────────────────────────────────────────────
# Statistics and quality report
# ─────────────────────────────────────────────────────────────────────────────

def build_report(elements: list, osm_count: int, overture_count: int) -> dict:
    """Build a quality report for the parsed elements."""
    type_counts = {}
    for e in elements:
        t = e.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    buildings = [e for e in elements if e.get("type") == "building"]
    with_height   = sum(1 for b in buildings if b.get("height_m"))
    with_floors   = sum(1 for b in buildings if b.get("floors"))
    with_material = sum(1 for b in buildings if b.get("material"))
    with_name     = sum(1 for b in buildings if b.get("name"))
    landmarks     = sum(1 for e in elements if e.get("is_landmark"))
    bike_paths    = sum(1 for e in elements if e.get("is_bike_path"))
    overture_src  = sum(1 for e in elements if e.get("source") == "overture")
    osm_src       = sum(1 for e in elements if e.get("source") == "osm")

    report = {
        "total_elements":    len(elements),
        "osm_input":         osm_count,
        "overture_input":    overture_count,
        "by_type":           type_counts,
        "by_source":         {"osm": osm_src, "overture": overture_src},
        "buildings": {
            "total":         len(buildings),
            "with_height":   with_height,
            "with_floors":   with_floors,
            "with_material": with_material,
            "with_name":     with_name,
            "height_pct":    round(with_height / len(buildings) * 100, 1) if buildings else 0,
        },
        "landmarks":         landmarks,
        "bike_paths":        bike_paths,
        "checks": {
            "has_buildings":   len(buildings) > 0,
            "has_roads":       type_counts.get("highway", 0) > 0,
            "has_waterways":   type_counts.get("waterway", 0) > 0,
            "has_landuse":     type_counts.get("landuse",  0) > 0,
            "has_bike_paths":  bike_paths > 0,
        }
    }

    passed = sum(1 for v in report["checks"].values() if v)
    report["checks_passed"] = f"{passed}/{len(report['checks'])}"
    report["valid"] = passed == len(report["checks"])

    return report


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_parse(
    fetch_dir: str,
    output_dir: str,
    origin_lat: float = DEFAULT_ORIGIN_LAT,
    origin_lon: float = DEFAULT_ORIGIN_LON,
) -> dict:
    """
    Run the full parse stage.

    Args:
        fetch_dir:  Directory containing Stage 1 output files
        output_dir: Directory to write elements.json and parse_manifest.json
        origin_lat: Spawn point latitude (default: Davis Amtrak Station)
        origin_lon: Spawn point longitude (default: Davis Amtrak Station)

    Returns:
        Parse result dict with output paths and quality report
    """
    start = time.time()
    fetch = Path(fetch_dir)
    out   = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("  BuildDavis — Stage 3: Parse")
    log.info("=" * 60)
    log.info("  Origin: (%.4f, %.4f) → Minecraft (0, 0)", origin_lat, origin_lon)
    log.info("  Scale:  1:1  (1m = 1 block)")

    converter = CoordinateConverter(origin_lat, origin_lon)
    all_elements = []

    # ── Load and parse OSM data ───────────────────────────────────────────────
    osm_path = fetch / "osm_raw.json"
    osm_count = 0
    if osm_path.exists():
        log.info("[1/3] Parsing OSM data...")
        with open(osm_path) as f:
            osm_data = json.load(f)
        osm_elements = parse_osm(osm_data, converter)
        osm_count = len(osm_elements)
        all_elements.extend(osm_elements)
        log.info("  OSM: %d elements parsed", osm_count)
    else:
        log.warning("  osm_raw.json not found — skipping OSM parse")

    # ── Load and parse Overture data ──────────────────────────────────────────
    overture_path = fetch / "overture_buildings.geojson"
    overture_count = 0
    if overture_path.exists():
        log.info("[2/3] Parsing Overture buildings...")
        with open(overture_path, encoding="utf-8") as f:
            overture_data = json.load(f)
        overture_elements = parse_overture(overture_data, converter)
        overture_count = len(overture_elements)
        all_elements.extend(overture_elements)
        log.info("  Overture: %d buildings parsed", overture_count)
    else:
        log.warning("  overture_buildings.geojson not found — skipping Overture parse")

    if not all_elements:
        raise RuntimeError(
            "No elements parsed — check that fetch.py has been run first."
        )

    # ── Sort by priority ──────────────────────────────────────────────────────
    log.info("[3/3] Sorting %d elements by render priority...", len(all_elements))
    all_elements = sort_by_priority(all_elements)

    # ── Write output ──────────────────────────────────────────────────────────
    elements_path = out / "elements.json"
    with open(elements_path, "w") as f:
        json.dump(all_elements, f, indent=2)

    # ── Build quality report ──────────────────────────────────────────────────
    report = build_report(all_elements, osm_count, overture_count)
    elapsed = time.time() - start

    # Log summary
    log.info("")
    log.info("  Results:")
    log.info("    Total elements:  %d", report["total_elements"])
    log.info("    Buildings:       %d (%s%% with height)",
             report["buildings"]["total"], report["buildings"]["height_pct"])
    log.info("    Roads/paths:     %d", report["by_type"].get("highway", 0))
    log.info("    Bike paths:      %d", report["bike_paths"])
    log.info("    Waterways:       %d", report["by_type"].get("waterway", 0))
    log.info("    Landmarks:       %d", report["landmarks"])
    log.info("    Checks:          %s", report["checks_passed"])

    # Sample — show first few named landmarks found
    landmark_names = [e["name"] for e in all_elements
                      if e.get("is_landmark") and e.get("name")][:8]
    if landmark_names:
        log.info("    Landmark names:  %s", ", ".join(landmark_names))

    # Show coordinate conversion example
    example = next((e for e in all_elements
                    if e.get("type") == "building" and e.get("name")), None)
    if example:
        log.info("")
        log.info("  Coordinate example:")
        log.info("    '%s'", example.get("name", ""))
        if "mc_centroid" in example:
            log.info("    Centroid → Minecraft X=%d, Z=%d",
                     example["mc_centroid"][0], example["mc_centroid"][1])

    result = {
        "stage":           "parse",
        "elements_path":   str(elements_path),
        "elements_count":  len(all_elements),
        "report":          report,
        "origin":          {"lat": origin_lat, "lon": origin_lon},
        "elapsed_seconds": round(elapsed, 1)
    }

    manifest_path = out / "parse_manifest.json"
    manifest_path.write_text(json.dumps(result, indent=2))

    log.info("")
    log.info("=" * 60)
    log.info("  Stage 3 complete in %.1fs", elapsed)
    log.info("  Output: %s", elements_path)
    log.info("  Valid:  %s", report["valid"])
    log.info("=" * 60)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="BuildDavis Pipeline — Stage 3: OSM & Overture Parser"
    )
    parser.add_argument(
        "--fetch-dir", required=True,
        help="Directory containing Stage 1 output files (osm_raw.json etc.)"
    )
    parser.add_argument(
        "--output", default="./data",
        help="Output directory (default: ./data)"
    )
    parser.add_argument(
        "--origin",
        default=f"{DEFAULT_ORIGIN_LAT},{DEFAULT_ORIGIN_LON}",
        help=f"Spawn point lat,lon (default: {DEFAULT_ORIGIN_LAT},{DEFAULT_ORIGIN_LON})"
    )
    args = parser.parse_args()

    lat, lon = [float(x.strip()) for x in args.origin.split(",")]
    run_parse(args.fetch_dir, args.output, lat, lon)


if __name__ == "__main__":
    main()
