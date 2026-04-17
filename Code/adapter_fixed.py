"""
adapter.py — BuildDavis Enrichment Adapter (Stage 6)
=====================================================
Converts fused_features.geojson (output of fuse.py) into Overpass API JSON
format that Arnis expects. Applies all enrichment layers in sequence:

  4a — Height injection (Overture ML + OSM floors → building:levels, height)
  4b — Landuse refinement (park/open-space classification)
  4c — Colour injection (building:colour from Mapillary dominant colour)
  4d — Type refinement (Overture category → OSM building type)
  4e — Feature tag passthrough (roof:shape, abandoned, etc.)
   5 — SPEC-003 palette override (Davis zone-based material lock)

Output: enriched_overpass.json  — ready for arnis --file enriched_overpass.json
        enrichment_log.json     — per-building attribution record

Usage:
    python adapter.py \
        --fused  data/fused_features.geojson \
        --output data/ \
        [--spec003-zones data/spec003_zones.geojson] \
        [--mapillary-cache data/reference/cache.db]

ADR-007: Overpass JSON is the canonical inter-stage format.
ADR-009: Enrichment is additive — Arnis renders, we feed it better data.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("adapter")

# ── Constants ──────────────────────────────────────────────────────────────────

VERSION = "1.0.0"

# Synthetic node ID base — above OSM's current max to avoid collisions
SYNTHETIC_NODE_BASE = 10_000_000_000

# SPEC-003 zone material overrides (Davis-specific)
# Maps zone name → building:colour hex closest to the target Minecraft block
SPEC003_ZONE_COLOURS: dict[str, str] = {
    "downtown_commercial": "#8B4513",   # → minecraft:brick
    "residential":         "#F4D03F",   # → minecraft:smooth_sandstone
    "uc_davis_campus":     "#A0A0A0",   # → minecraft:smooth_stone
    "industrial":          "#5C5C5C",   # → minecraft:gray_concrete
}

# Overture category → OSM building tag mapping
OVERTURE_TO_OSM_BUILDING: dict[str, str] = {
    "commercial":          "commercial",
    "retail":              "retail",
    "food_and_beverage":   "commercial",
    "education":           "school",
    "primary_school":      "school",
    "university":          "university",
    "hospital":            "hospital",
    "medical":             "hospital",
    "office":              "office",
    "industrial":          "industrial",
    "warehouse":           "warehouse",
    "residential":         "residential",
    "apartment":           "apartments",
    "hotel":               "hotel",
    "religious":           "religious",
    "government":          "public",
    "civic":               "public",
    "entertainment":       "commercial",
    "arts_and_entertainment": "commercial",
    "sports_and_recreation": "public",
    "transportation":      "transportation",
    "parking":             "parking",
    "garage":              "garage",
}

# OSM leisure/landuse → tree density classification
# "open"   → reclassify to landuse=grass (no Arnis tree fill)
# "wooded" → keep as natural=wood (dense Arnis tree fill)
# "mixed"  → keep as leisure=park (moderate Arnis tree fill)
# "pitch"  → reclassify to leisure=pitch (no trees, flat surface)
PARK_TREE_DENSITY_THRESHOLD_PER_100SQM = 0.5  # trees per 100 m² → wooded
PARK_OPEN_THRESHOLD_PER_100SQM         = 0.05  # trees per 100 m² → open

# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class EnrichmentRecord:
    """Per-element attribution record written to enrichment_log.json."""
    osm_id:        int
    name:          str
    osm_type:      str        # node / way / relation
    element_type:  str        # building / highway / leisure / etc.
    arnis_baseline: dict[str, Any] = field(default_factory=dict)
    enrichments_applied: list[dict[str, Any]] = field(default_factory=list)
    enrichments_missing: list[dict[str, Any]] = field(default_factory=list)
    quality_tier:  int = 0
    contributor_credits: list[str] = field(default_factory=list)
    schematic_id:  str | None = None

    def add_enrichment(self, field_name: str, source: str,
                       before: Any, after: Any,
                       confidence: float = 1.0,
                       note: str = "") -> None:
        if before == after:
            return
        entry: dict[str, Any] = {
            "field":      field_name,
            "source":     source,
            "before":     before,
            "after":      after,
            "confidence": round(confidence, 3),
        }
        if note:
            entry["note"] = note
        self.enrichments_applied.append(entry)

    def add_missing(self, field_name: str, reason: str,
                    improvement_possible: str = "") -> None:
        entry: dict[str, Any] = {"field": field_name, "reason": reason}
        if improvement_possible:
            entry["improvement_possible"] = improvement_possible
        self.enrichments_missing.append(entry)

    def compute_tier(self) -> int:
        fields_enriched = {e["field"] for e in self.enrichments_applied}
        if self.schematic_id:
            return 5
        if {"height", "wall_material", "building_type"}.issubset(fields_enriched):
            return 4
        if "wall_material" in fields_enriched and "height" in fields_enriched:
            return 4
        if "wall_material" in fields_enriched or "height" in fields_enriched:
            return 3
        if "building_type" in fields_enriched:
            return 2
        if len(fields_enriched) > 0:
            return 1
        return 0

    def to_dict(self) -> dict[str, Any]:
        self.quality_tier = self.compute_tier()
        return {
            "osm_id":               self.osm_id,
            "name":                 self.name,
            "osm_type":             self.osm_type,
            "element_type":         self.element_type,
            "arnis_baseline":       self.arnis_baseline,
            "enrichments_applied":  self.enrichments_applied,
            "enrichments_missing":  self.enrichments_missing,
            "quality_tier":         self.quality_tier,
            "contributor_credits":  self.contributor_credits,
            "schematic_id":         self.schematic_id,
        }


@dataclass
class AdapterStats:
    total_elements:     int = 0
    buildings:          int = 0
    highways:           int = 0
    landuse:            int = 0
    other:              int = 0
    height_enriched:    int = 0
    colour_enriched:    int = 0
    type_enriched:      int = 0
    landuse_reclassed:  int = 0
    spec003_overridden: int = 0
    tier_counts:        dict[int, int] = field(default_factory=lambda: {i: 0 for i in range(6)})

    def summary(self) -> dict[str, Any]:
        return {
            "version":            VERSION,
            "total_elements":     self.total_elements,
            "buildings":          self.buildings,
            "highways":           self.highways,
            "landuse":            self.landuse,
            "other":              self.other,
            "enrichment": {
                "height_enriched":    self.height_enriched,
                "colour_enriched":    self.colour_enriched,
                "type_enriched":      self.type_enriched,
                "landuse_reclassed":  self.landuse_reclassed,
                "spec003_overridden": self.spec003_overridden,
            },
            "quality_tiers":      self.tier_counts,
            "pct_tier3_plus": round(
                100 * sum(v for k, v in self.tier_counts.items() if k >= 3)
                / max(self.buildings, 1), 1
            ),
        }


# ── Mapillary colour cache ─────────────────────────────────────────────────────

class ColourCache:
    """
    SQLite-backed cache for Mapillary dominant-colour results.
    Schema: (osm_id INTEGER PRIMARY KEY, hex TEXT, confidence REAL, source TEXT)
    Falls back gracefully if no DB available.
    """

    def __init__(self, db_path: Path | None) -> None:
        self._conn: sqlite3.Connection | None = None
        if db_path and db_path.exists():
            try:
                self._conn = sqlite3.connect(str(db_path))
                self._conn.execute(
                    "CREATE TABLE IF NOT EXISTS colours "
                    "(osm_id INTEGER PRIMARY KEY, hex TEXT, "
                    " confidence REAL, source TEXT)"
                )
                self._conn.commit()
                log.info("Colour cache loaded: %s", db_path)
            except Exception as exc:
                log.warning("Colour cache unavailable: %s", exc)
                self._conn = None

    def get(self, osm_id: int) -> tuple[str, float] | None:
        if not self._conn:
            return None
        try:
            row = self._conn.execute(
                "SELECT hex, confidence FROM colours WHERE osm_id = ?",
                (osm_id,)
            ).fetchone()
            return (row[0], row[1]) if row else None
        except Exception:
            return None

    def put(self, osm_id: int, hex_colour: str,
            confidence: float, source: str = "mapillary") -> None:
        if not self._conn:
            return
        try:
            self._conn.execute(
                "INSERT OR REPLACE INTO colours VALUES (?,?,?,?)",
                (osm_id, hex_colour, confidence, source)
            )
            self._conn.commit()
        except Exception:
            pass


# ── Enrichment functions ───────────────────────────────────────────────────────

def enrich_4a_height(feat: dict, tags: dict,
                     record: EnrichmentRecord) -> None:
    """
    Stage 4a — Height injection.
    Priority: OSM explicit tags > Overture ML height > type defaults.
    Injects building:levels and/or height= into tags.
    """
    if feat.get("type") != "building":
        return

    # Arnis default height (6 blocks ≈ 1-floor building)
    arnis_default_levels = 1
    record.arnis_baseline["height_blocks"] = 6

    # Already has explicit OSM levels — highest confidence, pass through
    if "building:levels" in tags:
        levels = _parse_int(tags["building:levels"])
        if levels and levels > 0:
            record.add_enrichment("height", "osm_explicit",
                                  arnis_default_levels, levels,
                                  confidence=1.0,
                                  note="OSM building:levels tag present")
            return  # No further height enrichment needed

    # Already has explicit OSM height in metres
    if "height" in tags:
        try:
            h = float(str(tags["height"]).rstrip("m").strip())
            if h > 0:
                record.add_enrichment("height", "osm_explicit_metres",
                                      arnis_default_levels,
                                      f"{h:.1f}m", confidence=1.0)
                return
        except ValueError:
            pass

    # Overture ML height estimate
    overture_height_m: float | None = feat.get("height_m")
    overture_levels: int | None     = feat.get("floors")
    overture_confidence: float      = feat.get("height_confidence", 0.7)

    if overture_levels and overture_levels > 0:
        tags["building:levels"] = str(overture_levels)
        record.add_enrichment("height", "overture_ml",
                              arnis_default_levels, overture_levels,
                              confidence=overture_confidence)
        return

    if overture_height_m and overture_height_m > 0:
        tags["height"] = f"{overture_height_m:.1f}"
        record.add_enrichment("height", "overture_ml_metres",
                              arnis_default_levels, f"{overture_height_m:.1f}m",
                              confidence=overture_confidence)
        return

    # Type-based defaults (match Arnis's own defaults for these types)
    building_type = tags.get("building", "yes")
    type_defaults = {
        "apartments": 4, "residential": 2, "house": 2,
        "hospital":   6, "school":      3, "office":       4,
        "commercial": 2, "retail":      1, "industrial":   2,
        "warehouse":  1, "hotel":       5, "garage":       1,
        "shed":       1,
    }
    if building_type in type_defaults:
        default_levels = type_defaults[building_type]
        if default_levels != arnis_default_levels:
            tags["building:levels"] = str(default_levels)
            record.add_enrichment("height", "type_default",
                                  arnis_default_levels, default_levels,
                                  confidence=0.5,
                                  note=f"Default for building={building_type}")
        return

    # No height data available
    record.add_missing("height", "no_data_available",
                       "contributor_can_add_building:levels")


def enrich_4b_landuse(feat: dict, tags: dict,
                      record: EnrichmentRecord,
                      tree_nodes_in_poly: int,
                      poly_area_m2: float) -> None:
    """
    Stage 4b — Landuse refinement.
    Reclassifies leisure=park to more specific tags based on tree density.
    Prevents Arnis from over-foresting open lawn spaces.
    """
    if feat.get("type") not in ("leisure", "landuse", "natural"):
        return

    leisure = tags.get("leisure", "")
    landuse = tags.get("landuse", "")

    # Only reclassify parks — other leisure types handled correctly by Arnis
    if leisure != "park" and landuse not in ("grass", "recreation_ground"):
        return

    # Calculate tree density
    density_per_100sqm = (
        (tree_nodes_in_poly / poly_area_m2 * 100)
        if poly_area_m2 > 0 else 0.0
    )

    original = {"leisure": leisure, "landuse": landuse}

    if density_per_100sqm >= PARK_TREE_DENSITY_THRESHOLD_PER_100SQM:
        # Dense trees → reclassify as woodland
        tags["natural"] = "wood"
        tags.pop("leisure", None)
        record.add_enrichment(
            "landuse_type", "tree_density_analysis",
            "leisure=park", "natural=wood",
            confidence=0.8,
            note=f"Tree density {density_per_100sqm:.2f}/100m² → wooded"
        )

    elif density_per_100sqm <= PARK_OPEN_THRESHOLD_PER_100SQM:
        # Very sparse or no trees → open lawn, remove park tree generation
        tags["landuse"] = "grass"
        tags.pop("leisure", None)
        record.add_enrichment(
            "landuse_type", "tree_density_analysis",
            "leisure=park", "landuse=grass",
            confidence=0.75,
            note=f"Tree density {density_per_100sqm:.2f}/100m² → open lawn"
        )

    else:
        # Mixed — keep as leisure=park (Arnis moderate density is correct)
        record.add_enrichment(
            "landuse_type", "tree_density_analysis",
            "leisure=park", "leisure=park (mixed, unchanged)",
            confidence=0.6,
            note=f"Tree density {density_per_100sqm:.2f}/100m² → mixed"
        )


def enrich_4c_colour(feat: dict, tags: dict,
                     record: EnrichmentRecord,
                     colour_cache: ColourCache) -> None:
    """
    Stage 4c — Building colour injection.
    Looks up dominant facade colour from Mapillary cache.
    Injects building:colour tag for Arnis colour-to-block mapping.
    """
    if feat.get("type") != "building":
        return

    # Already has a colour tag — mapper or SPEC-003 has already set it
    if "building:colour" in tags:
        return

    osm_id = feat.get("osm_id", 0)
    cached = colour_cache.get(osm_id)

    if cached:
        hex_colour, confidence = cached
        record.arnis_baseline["wall_block"] = "random_category_palette"
        tags["building:colour"] = hex_colour
        record.add_enrichment("wall_material", "mapillary_color",
                              "random_category_palette", hex_colour,
                              confidence=confidence)
    else:
        record.add_missing("wall_material", "no_mapillary_data",
                           "contributor_can_add_building:colour or "
                           "mapillary_images_needed_for_this_building")


def enrich_4d_type(feat: dict, tags: dict,
                   record: EnrichmentRecord) -> None:
    """
    Stage 4d — Building type refinement.
    Converts Overture category strings to specific OSM building= values.
    This activates Arnis category-specific presets (windows, materials, roofs).
    """
    if feat.get("type") != "building":
        return

    current_type = tags.get("building", "yes")

    # Already specific — don't override mapper's more precise tag
    if current_type not in ("yes", "", None):
        return

    # fuse.py stores Overture category in 'subtype' field.
    # Also check 'overture_category' for forward-compatibility.
    overture_category: str = (
        feat.get("overture_category")
        or feat.get("subtype")
        or ""
    )
    if not overture_category:
        return

    osm_type = OVERTURE_TO_OSM_BUILDING.get(overture_category.lower())
    if osm_type and osm_type != current_type:
        tags["building"] = osm_type
        record.add_enrichment("building_type", "overture_category",
                              current_type, osm_type,
                              confidence=0.85,
                              note=f"Overture category: {overture_category}")


def enrich_4e_passthrough(feat: dict, tags: dict,
                          record: EnrichmentRecord) -> None:
    """
    Stage 4e — Feature tag passthrough and gap-fill.
    Ensures Arnis-activating tags that are present in our enriched data
    are correctly propagated. Also infers missing tags where we can.
    """
    # Roof shape — pass through from our parse.py output
    roof_shape = feat.get("roof_shape", "")
    if roof_shape and "roof:shape" not in tags:
        tags["roof:shape"] = roof_shape
        record.add_enrichment("roof_shape", "osm_passthrough",
                              None, roof_shape, confidence=1.0)

    # Abandoned buildings — pass through
    if (feat.get("tags") or {}).get("abandoned") == "yes":
        tags["abandoned"] = "yes"

    # Name — always pass through (used by Arnis for some amenity types)
    name = feat.get("name", "")
    if name and "name" not in tags:
        tags["name"] = name

    # Building material tag → map to building:colour if colour not set
    material = feat.get("material", "")
    material_to_colour = {
        "brick":        "#8B4513",
        "concrete":     "#A0A0A0",
        "wood":         "#8B6914",
        "glass":        "#ADD8E6",
        "stone":        "#808080",
        "metal":        "#C0C0C0",
        "sandstone":    "#D2A679",
    }
    if material and "building:colour" not in tags:
        hex_col = material_to_colour.get(material.lower())
        if hex_col:
            tags["building:colour"] = hex_col
            record.add_enrichment("wall_material", "building_material_tag",
                                  "unknown", hex_col, confidence=0.7,
                                  note=f"Inferred from building:material={material}")


def enrich_5_spec003(feat: dict, tags: dict,
                     record: EnrichmentRecord,
                     zone: str | None) -> None:
    """
    Stage 5 — SPEC-003 Davis zone palette override.
    Locks building:colour to Davis-specific values for key zones.
    This overrides any earlier colour enrichment — SPEC-003 is authoritative
    for zones where we have made deliberate design decisions.
    """
    if feat.get("type") != "building":
        return
    if not zone:
        return

    override_colour = SPEC003_ZONE_COLOURS.get(zone)
    if not override_colour:
        return

    previous = tags.get("building:colour", "none")
    tags["building:colour"] = override_colour
    record.add_enrichment("wall_material", f"spec003_{zone}",
                          previous, override_colour,
                          confidence=1.0,
                          note=f"SPEC-003 zone override: {zone}")


# ── Node synthesis ─────────────────────────────────────────────────────────────

def coords_to_nodes(
    coords: list[list[float]],
    node_id_counter: list[int],  # mutable counter via list
    nodes_out:  list[dict],
    node_ids_out: list[int],
) -> None:
    """
    Convert a list of [lon, lat] coordinate pairs into synthetic Overpass
    node objects. Populates nodes_out and node_ids_out in place.
    Uses a shared counter to ensure globally unique IDs across all ways.
    """
    for lon, lat in coords:
        nid = node_id_counter[0]
        node_id_counter[0] += 1
        nodes_out.append({
            "type": "node",
            "id":   nid,
            "lat":  lat,
            "lon":  lon,
            "tags": {},
        })
        node_ids_out.append(nid)


# ── Zone lookup ────────────────────────────────────────────────────────────────

def load_spec003_zones(zones_path: Path | None) -> list[dict] | None:
    """Load SPEC-003 zone polygons from GeoJSON if available."""
    if not zones_path or not zones_path.exists():
        return None
    with open(zones_path) as f:
        data = json.load(f)
    return data.get("features", [])


def point_in_polygon(px: float, pz: float,
                     polygon: list[tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon test (2D)."""
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > pz) != (yj > pz)) and \
           (px < (xj - xi) * (pz - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def get_zone_for_feature(feat: dict,
                         zones: list[dict] | None) -> str | None:
    """
    Return the SPEC-003 zone name for a feature's centroid, if any.
    Uses lat/lon coordinates — zone polygons are in WGS84.
    Falls back to mc_centroid-derived lat/lon if direct lat/lon not present.
    """
    if not zones:
        return None

    # Prefer direct lat/lon centroid (present on nodes and some ways)
    lat = feat.get("lat")
    lon = feat.get("lon")

    # For ways/polygons, derive from coords centroid
    if lat is None or lon is None:
        coords = feat.get("coords", [])
        if coords:
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            lon = sum(lons) / len(lons)
            lat = sum(lats) / len(lats)

    if lat is None or lon is None:
        return None

    for zone_feat in zones:
        props = zone_feat.get("properties", {})
        zone_name = props.get("zone")
        if not zone_name:
            continue
        geom = zone_feat.get("geometry", {})
        if geom.get("type") == "Polygon":
            # Zone polygon coords are [lon, lat] pairs
            ring = [(c[0], c[1]) for c in geom["coordinates"][0]]
            if point_in_polygon(lon, lat, ring):
                return zone_name
    return None


# ── Tree node counting (for 4b) ────────────────────────────────────────────────

def build_tree_index(features: list[dict]) -> list[tuple[float, float]]:
    """
    Extract all natural=tree node locations from the feature list.
    Returns a list of (mc_x, mc_z) tuples for spatial counting.
    Handles both flat dicts and GeoJSON Feature wrapper objects.
    """
    trees: list[tuple[float, float]] = []
    for feat in features:
        props = feat.get("properties", feat) if feat.get("type") == "Feature" else feat
        if props.get("type") == "natural" and props.get("subtype") == "tree":
            mc_x = props.get("mc_x")
            mc_z = props.get("mc_z")
            if mc_x is not None and mc_z is not None:
                trees.append((float(mc_x), float(mc_z)))
    return trees


def count_trees_in_bbox(trees: list[tuple[float, float]],
                        bbox: dict) -> int:
    """Count tree nodes within a bounding box dict {min_x, max_x, min_z, max_z}."""
    if not bbox or not trees:
        return 0
    min_x = bbox.get("min_x", -1e9)
    max_x = bbox.get("max_x",  1e9)
    min_z = bbox.get("min_z", -1e9)
    max_z = bbox.get("max_z",  1e9)
    return sum(
        1 for tx, tz in trees
        if min_x <= tx <= max_x and min_z <= tz <= max_z
    )


def estimate_area_m2(coords: list[list[float]]) -> float:
    """
    Estimate polygon area in square metres using the shoelace formula.
    Input: [[lon, lat], ...] WGS84 coordinates.
    Approximation valid for small areas (Davis-scale polygons).
    """
    if len(coords) < 3:
        return 0.0
    # Approximate degrees to metres at Davis latitude (~38.5°N)
    lat_m = 111_000.0
    lon_m = 111_000.0 * math.cos(math.radians(38.5))
    n = len(coords)
    area = 0.0
    for i in range(n):
        x1 = coords[i][0] * lon_m
        y1 = coords[i][1] * lat_m
        x2 = coords[(i + 1) % n][0] * lon_m
        y2 = coords[(i + 1) % n][1] * lat_m
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


# ── Main conversion ────────────────────────────────────────────────────────────

def convert(
    fused_path: Path,
    output_dir: Path,
    zones_path: Path | None = None,
    colour_db_path: Path | None = None,
) -> tuple[Path, Path, Path]:
    """
    Main conversion function. Returns (overpass_path, log_path, summary_path).
    """
    t0 = time.time()
    log.info("Loading fused features from %s", fused_path)

    with open(fused_path, encoding="utf-8") as f:
        data = json.load(f)

    # Support both GeoJSON FeatureCollection and raw list
    features: list[dict] = (
        data.get("features", data)
        if isinstance(data, dict)
        else data
    )

    log.info("Loaded %d features", len(features))

    # Initialise helpers
    colour_cache = ColourCache(colour_db_path)
    zones        = load_spec003_zones(zones_path)
    tree_index   = build_tree_index(features)
    stats        = AdapterStats()
    log.info("Tree index: %d natural=tree nodes", len(tree_index))

    # Shared mutable node ID counter
    node_id_counter = [SYNTHETIC_NODE_BASE]

    # Output containers
    overpass_nodes:    list[dict] = []
    overpass_ways:     list[dict] = []
    overpass_rels:     list[dict] = []
    enrichment_log:    list[dict] = []

    for feat in features:
        stats.total_elements += 1

        # Unwrap GeoJSON FeatureCollection format.
        # fuse.py outputs: {"type":"Feature","geometry":{...},"properties":{...}}
        # All element data lives in properties. Geometry coords may be in
        # either properties.coords (our internal format) or geometry.coordinates
        # (GeoJSON standard). We normalise to a flat props dict.
        if feat.get("type") == "Feature":
            props  = dict(feat.get("properties") or {})
            # Pull coords from GeoJSON geometry if not already in properties
            geojson_geom = feat.get("geometry") or {}
            geom_kind    = geojson_geom.get("type", "")
            raw_coords   = geojson_geom.get("coordinates", [])
            if not props.get("coords") and raw_coords:
                if geom_kind == "Point":
                    props["lon"] = props.get("lon", raw_coords[0])
                    props["lat"] = props.get("lat", raw_coords[1])
                elif geom_kind in ("Polygon", "MultiPolygon"):
                    props["coords"] = raw_coords[0] if geom_kind == "Polygon" else raw_coords[0][0]
                elif geom_kind == "LineString":
                    props["coords"] = raw_coords
        else:
            # Already a flat dict (legacy format)
            props = feat

        osm_id     = int(props.get("osm_id", node_id_counter[0]))
        osm_type   = props.get("osm_type", "way")   # node / way / relation
        elem_type  = props.get("type", "")           # building / highway / etc.
        name       = props.get("name", "")
        geom_type  = props.get("geometry", "polygon")
        coords     = props.get("coords", [])
        # fuse.py stores OSM tags in the "tags" dict for buildings,
        # but highway and other non-building features may have tags=None.
        # Reconstruct the tags dict Arnis expects from available fields.
        raw_tags = dict(props.get("tags") or {})

        if not raw_tags:
            # Try osm_{key} style fields first
            OSM_TAG_KEYS = (
                "building", "highway", "landuse", "waterway", "natural",
                "amenity", "leisure", "name", "height", "building:levels",
                "building:material", "roof:shape", "surface",
            )
            for tk in OSM_TAG_KEYS:
                val = props.get(f"osm_{tk}")
                if val is not None:
                    raw_tags[tk] = str(val)

        # Always ensure the primary element tag is present.
        # fuse.py stores element type in "type" and value in "subtype".
        # e.g. type="highway", subtype="primary" → tags["highway"]="primary"
        subtype = props.get("subtype", "")
        if elem_type and elem_type not in raw_tags:
            if subtype:
                raw_tags[elem_type] = subtype
            else:
                raw_tags[elem_type] = "yes"

        # Carry forward name if present
        if name and "name" not in raw_tags:
            raw_tags["name"] = name

        tags = raw_tags  # mutable copy for enrichment

        # ── Enrichment record setup ──────────────────────────────────────────
        record = EnrichmentRecord(
            osm_id=osm_id,
            name=name,
            osm_type=osm_type,
            element_type=elem_type,
        )

        # ── Apply enrichment layers ──────────────────────────────────────────
        if elem_type == "building":
            stats.buildings += 1

            enrich_4a_height(props, tags, record)
            enrich_4c_colour(props, tags, record, colour_cache)
            enrich_4d_type(props, tags, record)
            enrich_4e_passthrough(props, tags, record)

            zone = get_zone_for_feature(props, zones)
            enrich_5_spec003(props, tags, record, zone)

            # Update stats
            applied_fields = {e["field"] for e in record.enrichments_applied}
            if "height" in applied_fields:
                stats.height_enriched += 1
            if "wall_material" in applied_fields:
                stats.colour_enriched += 1
            if "building_type" in applied_fields:
                stats.type_enriched += 1
            if zone:
                stats.spec003_overridden += 1

        elif elem_type in ("leisure", "landuse", "natural"):
            stats.landuse += 1
            if geom_type in ("polygon",):
                area_m2 = estimate_area_m2(coords)
                tree_count = count_trees_in_bbox(tree_index,
                                                 props.get("mc_bbox", {}))
                enrich_4b_landuse(props, tags, record,
                                  tree_count, area_m2)
                applied_fields = {e["field"] for e in record.enrichments_applied}
                if "landuse_type" in applied_fields:
                    stats.landuse_reclassed += 1

        elif elem_type == "highway":
            stats.highways += 1
            enrich_4e_passthrough(props, tags, record)

        else:
            stats.other += 1
            enrich_4e_passthrough(props, tags, record)

        # ── Compute quality tier and log ─────────────────────────────────────
        tier = record.compute_tier()
        stats.tier_counts[tier] = stats.tier_counts.get(tier, 0) + 1
        if elem_type == "building":
            enrichment_log.append(record.to_dict())

        # ── Convert geometry to Overpass nodes/ways/relations ────────────────
        if osm_type == "node" or geom_type == "point":
            lat = props.get("lat", 0.0)
            lon = props.get("lon", 0.0)
            overpass_nodes.append({
                "type": "node",
                "id":   osm_id,
                "lat":  lat,
                "lon":  lon,
                "tags": tags,
            })

        elif osm_type in ("way", "relation") or geom_type in ("polygon", "linestring"):
            if not coords:
                continue

            way_node_ids: list[int] = []
            coords_to_nodes(coords, node_id_counter,
                            overpass_nodes, way_node_ids)

            way_obj: dict[str, Any] = {
                "type": "way",
                "id":   osm_id,
                "nodes": way_node_ids,
                "tags": tags,
            }
            overpass_ways.append(way_obj)

    # ── Assemble final Overpass JSON ─────────────────────────────────────────
    all_elements = overpass_nodes + overpass_ways + overpass_rels
    overpass_out = {
        "version":    0.6,
        "generator":  f"BuildDavis adapter v{VERSION}",
        "elements":   all_elements,
    }

    # ── Write outputs ────────────────────────────────────────────────────────
    output_dir.mkdir(parents=True, exist_ok=True)

    overpass_path = output_dir / "enriched_overpass.json"
    log_path      = output_dir / "enrichment_log.json"
    summary_path  = output_dir / "enrichment_summary.json"

    with open(overpass_path, "w", encoding="utf-8") as f:
        json.dump(overpass_out, f)

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(enrichment_log, f, indent=2)

    summary = stats.summary()
    summary["elapsed_seconds"] = round(time.time() - t0, 1)
    summary["generated_at"]    = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # ── Report ────────────────────────────────────────────────────────────────
    log.info("─" * 60)
    log.info("Adapter complete in %.1fs", summary["elapsed_seconds"])
    log.info("  Elements:        %d", stats.total_elements)
    log.info("  Buildings:       %d", stats.buildings)
    log.info("  Height enriched: %d (%.0f%%)",
             stats.height_enriched,
             100 * stats.height_enriched / max(stats.buildings, 1))
    log.info("  Colour enriched: %d (%.0f%%)",
             stats.colour_enriched,
             100 * stats.colour_enriched / max(stats.buildings, 1))
    log.info("  Type enriched:   %d (%.0f%%)",
             stats.type_enriched,
             100 * stats.type_enriched / max(stats.buildings, 1))
    log.info("  Landuse reclass: %d", stats.landuse_reclassed)
    log.info("  SPEC-003 zones:  %d", stats.spec003_overridden)
    log.info("  Tier 3+ buildings: %.1f%%", summary["pct_tier3_plus"])
    log.info("─" * 60)
    log.info("Outputs:")
    log.info("  %s", overpass_path)
    log.info("  %s", log_path)
    log.info("  %s", summary_path)

    return overpass_path, log_path, summary_path


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_int(val: Any) -> int | None:
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return None


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="BuildDavis Stage 6 — Enrichment Adapter"
    )
    parser.add_argument(
        "--fused", required=True,
        help="Path to fused_features.geojson (output of fuse.py)"
    )
    parser.add_argument(
        "--output", required=True,
        help="Output directory for enriched_overpass.json and logs"
    )
    parser.add_argument(
        "--spec003-zones", default=None,
        help="Optional GeoJSON file defining SPEC-003 zone polygons"
    )
    parser.add_argument(
        "--mapillary-cache", default=None,
        help="Optional path to Mapillary colour cache SQLite DB"
    )
    args = parser.parse_args()

    overpass_path, log_path, summary_path = convert(
        fused_path     = Path(args.fused),
        output_dir     = Path(args.output),
        zones_path     = Path(args.spec003_zones) if args.spec003_zones else None,
        colour_db_path = Path(args.mapillary_cache) if args.mapillary_cache else None,
    )

    print(f"\nReady for Arnis:")
    print(f"  arnis --file {overpass_path} --path <world_output> --bbox <bbox>")
    print(f"\nEnrichment summary: {summary_path}")


if __name__ == "__main__":
    main()
