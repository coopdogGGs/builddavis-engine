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

from height_validator import MultiSourceValidator, init_validator

try:
    from shapely.geometry import Point, LineString, Polygon
    from shapely.ops import unary_union
    from shapely import prepared
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False

log = logging.getLogger("adapter")

# ── Constants ──────────────────────────────────────────────────────────────────

VERSION = "1.0.0"

# Synthetic node ID base — above OSM's current max to avoid collisions
SYNTHETIC_NODE_BASE = 10_000_000_000

# SPEC-003 zone material palettes (Davis-specific)
# Each zone gets a list of plausible building:colour hex values.
# When no real colour data exists, one is picked per building (deterministic by osm_id).
# IMPORTANT: hex values are chosen to map to DISTINCT Minecraft blocks
# via the Arnis engine's DEFINED_COLORS closest-match table.
# See block_definitions.rs for the colour→block mapping.
SPEC003_ZONE_PALETTES: dict[str, list[str]] = {
    "downtown_commercial": [
        "#E96B39",   # brick red → BRICK / NETHER_BRICK
        "#9F5224",   # brown-orange → BROWN_TERRACOTTA / POLISHED_GRANITE
        "#808080",   # grey → POLISHED_ANDESITE / SMOOTH_STONE
        "#AEAF8E",   # sage green → END_STONE_BRICKS / SANDSTONE
        "#D1B1A1",   # warm beige → WHITE_TERRACOTTA / SANDSTONE
        "#BFB62A",   # gold → SMOOTH_SANDSTONE / SANDSTONE
    ],
    "residential": [
        "#D1B1A1",   # warm stucco → WHITE_TERRACOTTA / SANDSTONE
        "#E0D8AF",   # cream → SMOOTH_SANDSTONE / LIGHT_GRAY_CONCRETE
        "#7A5C42",   # warm brown → MUD_BRICKS / BROWN_TERRACOTTA / SANDSTONE
        "#E96B39",   # brick red → BRICK / NETHER_BRICK
        "#BCB6B3",   # cool grey → SMOOTH_SANDSTONE / QUARTZ_BRICKS / POLISHED_ANDESITE
        "#AEAF8E",   # sage → END_STONE_BRICKS / SANDSTONE
        "#9F5224",   # deep brown → BROWN_TERRACOTTA / BRICK / POLISHED_GRANITE
        "#FFFFFF",   # white → WHITE_CONCRETE / QUARTZ
    ],
    "uc_davis_campus": [
        "#808080",   # medium grey → POLISHED_ANDESITE / SMOOTH_STONE
        "#E96B39",   # brick (older bldgs) → BRICK / NETHER_BRICK
        "#AEAEB2",   # light grey → POLISHED_ANDESITE / LIGHT_GRAY_CONCRETE
        "#392929",   # dark brown → BROWN_TERRACOTTA / MUD_BRICKS
        "#D1B1A1",   # tan (newer) → WHITE_TERRACOTTA / SANDSTONE
    ],
    "industrial": [
        "#392929",   # dark grey-brown → BROWN_TERRACOTTA / BROWN_CONCRETE
        "#808080",   # medium grey → POLISHED_ANDESITE / SMOOTH_STONE
        "#AEAEB2",   # light grey → POLISHED_ANDESITE / LIGHT_GRAY_CONCRETE
        "#121212",   # near-black → DEEPSLATE_BRICKS / BLACKSTONE
        "#BCB6B3",   # cool light grey → SMOOTH_SANDSTONE / QUARTZ_BRICKS
    ],
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
                     record: EnrichmentRecord,
                     validator: MultiSourceValidator | None = None) -> dict | None:
    """
    Stage 4a — Height injection via multi-source triangulation.
    Uses OSM explicit, LiDAR DSM-DTM, and Overture ML.
    Returns HeightResult if building was validated, else None.
    """
    if feat.get("type") != "building":
        return None

    arnis_default_levels = 1
    record.arnis_baseline["height_blocks"] = 6

    if validator is None:
        validator = MultiSourceValidator()

    subtype = tags.get("building", "yes")
    coords  = feat.get("coords", [])
    area_m2 = None
    lat, lon = feat.get("lat"), feat.get("lon")

    if coords and len(coords) >= 3:
        area_m2 = _estimate_area(coords)
        if lat is None or lon is None:
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            lon = sum(lons) / len(lons)
            lat = sum(lats) / len(lats)

    source_info = {}
    overture_h = feat.get("height_m")
    if overture_h and float(overture_h) > 0:
        source_info["overture_height_m"] = float(overture_h)
    overture_floors = feat.get("floors")
    if overture_floors:
        source_info["overture_floors"] = int(overture_floors)

    result = validator.validate(tags, subtype, area_m2, lat, lon, source_info)

    confidence = result.confidence
    source_label = result.source_used
    final_levels = result.final_levels

    record.add_enrichment("height", source_label,
                          arnis_default_levels, final_levels,
                          confidence=confidence,
                          note=result.note)
    return result


def _estimate_area(coords):
    """Quick shoelace area from WGS84 coords."""
    if len(coords) < 3:
        return 0.0
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
    Stage 5 — SPEC-003 Davis zone palette fallback.
    Sets building:colour to Davis zone defaults ONLY when no real colour
    data exists (e.g. no Mapillary data, no building:material tag).
    Real per-building colour always takes priority over zone palette.
    Picks from a varied palette per zone, seeded by osm_id for determinism.

    When no zone polygon matches, infers zone from building type tags.
    """
    if feat.get("type") != "building":
        return

    # If the building already has a colour from a real source (Mapillary,
    # OSM mapper, material tag), keep it — accuracy over uniformity.
    if "building:colour" in tags:
        return

    # Infer zone from building type when no geographic zone matched
    if not zone:
        zone = _infer_zone_from_tags(tags)

    palette = SPEC003_ZONE_PALETTES.get(zone)  # type: ignore[arg-type]
    if not palette:
        return

    # Pick colour deterministically from palette
    # Use osm_id when available; fall back to coordinate hash for synthetic buildings
    osm_id = feat.get("osm_id", 0) or 0
    if osm_id != 0:
        seed = osm_id
    else:
        # Hash from coordinates for buildings without osm_id (Overture/MS)
        coords = feat.get("coords", [])
        lat = feat.get("lat", 0.0) or (coords[0][1] if coords else 0.0)
        lon = feat.get("lon", 0.0) or (coords[0][0] if coords else 0.0)
        seed = int(abs(lat * 1e7) + abs(lon * 1e7) * 31)
    idx = hash(seed * 2654435761) % len(palette)
    colour = palette[idx]

    tags["building:colour"] = colour
    record.add_enrichment("wall_material", f"spec003_{zone}",
                          "none", colour,
                          confidence=0.5,
                          note=f"SPEC-003 zone fallback (varied palette, no real colour data)")


# OSM building= values → SPEC-003 zone inference
_BUILDING_TYPE_TO_ZONE: dict[str, str] = {
    "commercial":   "downtown_commercial",
    "retail":       "downtown_commercial",
    "office":       "downtown_commercial",
    "hotel":        "downtown_commercial",
    "university":   "uc_davis_campus",
    "college":      "uc_davis_campus",
    "industrial":   "industrial",
    "warehouse":    "industrial",
    "manufacture":  "industrial",
}


def _infer_zone_from_tags(tags: dict) -> str:
    """Infer a SPEC-003 zone from building tags. Defaults to residential."""
    btype = tags.get("building", "yes")
    return _BUILDING_TYPE_TO_ZONE.get(btype, "residential")


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


# ── Synthetic street tree generation ───────────────────────────────────────────

# Davis City ordinance requires street trees on residential streets.
# Typical spacing: ~12m apart, offset ~3m from road centre line.
TREE_SPACING_M = 12.0
TREE_OFFSET_M  = 3.0

# Species distribution for Davis street trees (realistic mix)
DAVIS_STREET_TREE_SPECIES = [
    {"species": "Quercus lobata",       "genus": "Quercus",  "leaf_type": "broadleaved"},  # Valley Oak
    {"species": "Zelkova serrata",      "leaf_type": "broadleaved"},                        # Zelkova
    {"species": "Pistacia chinensis",   "leaf_type": "broadleaved"},                        # Chinese Pistache
    {"species": "Pyrus calleryana",     "leaf_type": "broadleaved"},                        # Callery Pear
    {"species": "Liquidambar styraciflua", "leaf_type": "broadleaved"},                     # Sweetgum
    {"species": "Platanus acerifolia",  "leaf_type": "broadleaved"},                        # London Plane
    {"species": "Cedrus deodara",       "leaf_type": "needleleaved"},                       # Deodar Cedar
    {"species": "Sequoia sempervirens", "leaf_type": "needleleaved"},                       # Coast Redwood
]

# Road types that get street trees
TREE_ROAD_TYPES = {"residential", "living_street", "tertiary"}

# Road half-widths for tree exclusion buffering (metres, approximate)
ROAD_BUFFER_M = {
    "motorway": 12, "trunk": 10, "primary": 8, "secondary": 7,
    "tertiary": 6, "residential": 5, "service": 4, "unclassified": 5,
    "living_street": 4, "cycleway": 2, "footway": 1.5, "path": 1.5,
    "pedestrian": 3, "track": 2,
}
DEFAULT_ROAD_BUFFER_M = 4

# Approximate degrees-per-metre at Davis latitude (~38.5°N)
DEG_PER_METRE_LAT = 1.0 / 111_320
DEG_PER_METRE_LON = 1.0 / (111_320 * math.cos(math.radians(38.54)))


def deconflict_trees(
    trees: list[dict],
    overpass_ways: list[dict],
    overpass_nodes: list[dict],
) -> list[dict]:
    """
    Remove trees that overlap with roads, bike paths, buildings,
    swimming pools, or open park/grass/pitch areas.
    Uses shapely buffered geometries.
    Returns filtered tree list.
    """
    if not HAS_SHAPELY or not trees:
        return trees

    # Build node lookup for way geometry reconstruction
    node_lut: dict[int, tuple[float, float]] = {}
    for n in overpass_nodes:
        if n.get("type") == "node" and "lat" in n and "lon" in n:
            node_lut[n["id"]] = (n["lon"], n["lat"])

    exclusion_geoms = []

    # Leisure/landuse types where synthetic trees should be excluded
    OPEN_AREA_LEISURE = {"pitch", "track", "playground", "sports_centre",
                         "swimming_pool", "dog_park"}

    for w in overpass_ways:
        tags = w.get("tags", {})
        nids = w.get("nodes", [])
        coords = [node_lut[nid] for nid in nids if nid in node_lut]
        if len(coords) < 2:
            continue

        highway = tags.get("highway")
        is_building = "building" in tags
        is_pool = tags.get("leisure") == "swimming_pool"
        leisure = tags.get("leisure", "")

        if highway:
            # Buffer road centerline — use narrower surfaced-width only
            # (not the full ROAD_BUFFER_M which includes planting strip)
            TREE_ROAD_SURFACE_M = {
                "motorway": 10, "trunk": 8, "primary": 6, "secondary": 5,
                "tertiary": 4, "residential": 2, "service": 2, "unclassified": 2,
                "living_street": 2, "cycleway": 1.5, "footway": 1, "path": 1,
                "pedestrian": 2, "track": 1.5,
            }
            buf_m = TREE_ROAD_SURFACE_M.get(highway, 2)
            buf_deg = buf_m * DEG_PER_METRE_LON
            try:
                line = LineString(coords)
                exclusion_geoms.append(line.buffer(buf_deg))
            except Exception:
                pass
        elif is_building or is_pool:
            # Building/pool polygon — trees shouldn't be inside
            if len(coords) >= 3:
                try:
                    poly = Polygon(coords)
                    if poly.is_valid:
                        exclusion_geoms.append(poly)
                except Exception:
                    pass
        elif leisure in OPEN_AREA_LEISURE:
            # Sports fields only — no synthetic trees on pitches/tracks
            if len(coords) >= 3:
                try:
                    poly = Polygon(coords)
                    if poly.is_valid:
                        exclusion_geoms.append(poly)
                except Exception:
                    pass

    if not exclusion_geoms:
        return trees

    # Merge all exclusion zones into one geometry for fast lookup
    log.info("  Building exclusion mask from %d geometries...", len(exclusion_geoms))
    exclusion = unary_union(exclusion_geoms)
    prep_exclusion = prepared.prep(exclusion)

    kept = []
    removed = 0
    for tree in trees:
        pt = Point(tree["lon"], tree["lat"])
        if prep_exclusion.contains(pt):
            removed += 1
        else:
            kept.append(tree)

    log.info("  Tree de-confliction: %d kept, %d removed (roads/parks/buildings/pools)",
             len(kept), removed)
    return kept


def generate_street_trees(
    features: list[dict],
    node_id_counter: list[int],
) -> list[dict]:
    """
    Generate synthetic street tree nodes along residential roads.
    Places trees at TREE_SPACING_M intervals, offset from the road centre.
    Returns a list of Overpass-format tree nodes.
    """
    tree_nodes: list[dict] = []
    lat_m = 111_000.0
    lon_m = 111_000.0 * math.cos(math.radians(38.5))

    for feat in features:
        props = feat.get("properties", feat) if feat.get("type") == "Feature" else feat

        if props.get("type") != "highway":
            continue

        subtype = props.get("subtype", "")
        tags = props.get("tags") or {}
        highway_val = tags.get("highway", subtype)
        if highway_val not in TREE_ROAD_TYPES:
            continue

        # Get coordinates from GeoJSON geometry or flat coords field
        geom = feat.get("geometry") if feat.get("type") == "Feature" else None
        if geom and geom.get("type") == "LineString":
            coords = geom["coordinates"]
        else:
            coords = props.get("coords", [])
        if len(coords) < 2:
            continue

        # Walk along the road, placing trees at intervals
        accumulated = 0.0
        for i in range(len(coords) - 1):
            lon1, lat1 = coords[i]
            lon2, lat2 = coords[i + 1]
            dx = (lon2 - lon1) * lon_m
            dy = (lat2 - lat1) * lat_m
            seg_len = math.sqrt(dx * dx + dy * dy)
            if seg_len < 0.1:
                continue

            # Unit direction and perpendicular
            ux, uy = dx / seg_len, dy / seg_len
            px, py = -uy, ux  # perpendicular (left side)

            t = 0.0
            if accumulated > 0:
                t = TREE_SPACING_M - accumulated
                accumulated = 0.0

            while t < seg_len:
                frac = t / seg_len
                base_lon = lon1 + frac * (lon2 - lon1)
                base_lat = lat1 + frac * (lat2 - lat1)

                # Place tree on both sides of the road
                for side in (1, -1):
                    offset_lon = base_lon + side * px * TREE_OFFSET_M / lon_m
                    offset_lat = base_lat + side * py * TREE_OFFSET_M / lat_m

                    # Pick species deterministically
                    sp_idx = node_id_counter[0] % len(DAVIS_STREET_TREE_SPECIES)
                    sp_tags = dict(DAVIS_STREET_TREE_SPECIES[sp_idx])
                    sp_tags["natural"] = "tree"
                    sp_tags["source"] = "synthetic_street_tree"

                    nid = node_id_counter[0]
                    node_id_counter[0] += 1
                    tree_nodes.append({
                        "type": "node",
                        "id": nid,
                        "lat": offset_lat,
                        "lon": offset_lon,
                        "tags": sp_tags,
                    })

                t += TREE_SPACING_M

            remaining = seg_len - (t - TREE_SPACING_M)
            accumulated = remaining if remaining > 0 else 0.0

    return tree_nodes


def generate_baseball_infields(
    overpass_ways: list[dict],
    overpass_nodes: list[dict],
    node_id_counter: list[int],
) -> tuple[list[dict], list[dict]]:
    """
    Generate dirt infield polygons for baseball diamond pitches.

    Finds ways tagged leisure=pitch + sport=baseball, computes an infield
    arc (90° wedge from the southernmost vertex as home plate), and emits
    a new leisure=pitch + surface=dirt polygon.  Also sets surface=grass
    on the original outfield polygon.

    Returns (new_nodes, new_ways) for the infield dirt areas.
    """
    INFIELD_RADIUS_M = 27.4  # regulation: 90 feet = 27.43m
    ARC_SEGMENTS = 12        # smooth quarter-circle

    lat_m = 111_320.0
    lon_m = 111_320.0 * math.cos(math.radians(38.56))

    # Build node lookup
    node_lut: dict[int, tuple[float, float]] = {}
    for n in overpass_nodes:
        if n.get("type") == "node":
            node_lut[n["id"]] = (n.get("lon", 0.0), n.get("lat", 0.0))

    new_nodes: list[dict] = []
    new_ways: list[dict] = []

    for way in overpass_ways:
        tags = way.get("tags", {})
        if tags.get("leisure") != "pitch" or tags.get("sport") != "baseball":
            continue

        # Get polygon coordinates
        nids = way.get("nodes", [])
        coords = [node_lut[nid] for nid in nids if nid in node_lut]
        if len(coords) < 3:
            continue

        # Set the outfield surface to grass
        tags["surface"] = "grass"

        # Find home plate — typically the southernmost vertex (lowest lat)
        home_idx = min(range(len(coords)), key=lambda i: coords[i][1])
        home_lon, home_lat = coords[home_idx]

        # Compute centroid to determine field orientation
        cx = sum(c[0] for c in coords) / len(coords)
        cy = sum(c[1] for c in coords) / len(coords)

        # Direction from home plate toward centre of field
        dx_m = (cx - home_lon) * lon_m
        dy_m = (cy - home_lat) * lat_m
        dist = math.sqrt(dx_m * dx_m + dy_m * dy_m)
        if dist < 1.0:
            continue

        # Angle from home plate to field centre (radians)
        centre_angle = math.atan2(dy_m, dx_m)

        # Generate 90° arc centred on the field direction
        arc_points = [(home_lon, home_lat)]  # start at home plate
        for i in range(ARC_SEGMENTS + 1):
            angle = centre_angle - math.pi / 4 + (math.pi / 2) * (i / ARC_SEGMENTS)
            pt_lon = home_lon + INFIELD_RADIUS_M * math.cos(angle) / lon_m
            pt_lat = home_lat + INFIELD_RADIUS_M * math.sin(angle) / lat_m
            arc_points.append((pt_lon, pt_lat))
        arc_points.append((home_lon, home_lat))  # close polygon

        # Emit infield nodes and way
        infield_node_ids: list[int] = []
        for lon, lat in arc_points:
            nid = node_id_counter[0]
            node_id_counter[0] += 1
            new_nodes.append({
                "type": "node",
                "id": nid,
                "lat": lat,
                "lon": lon,
                "tags": {},
            })
            infield_node_ids.append(nid)

        way_id = node_id_counter[0]
        node_id_counter[0] += 1
        new_ways.append({
            "type": "way",
            "id": way_id,
            "nodes": infield_node_ids,
            "tags": {
                "leisure": "pitch",
                "sport": "baseball",
                "surface": "dirt",
                "source": "synthetic_baseball_infield",
            },
        })

    return new_nodes, new_ways


def merge_bridge_segments(
    overpass_ways: list[dict],
    overpass_nodes: list[dict],
    node_id_counter: list[int],
) -> tuple[list[dict], list[dict]]:
    """
    Fill gaps between parallel bridge segments (e.g. divided highways where
    eastbound and westbound are separate OSM ways).

    Arnis renders each bridge=yes way as a line with block_range width.
    A polygon approach draws edges but not interior — leaving the gap.
    Instead, emit a centerline way running down the middle of the gap,
    plus approach-ramp ways at each end to ensure slope connectivity.

    Returns (new_nodes, new_ways).
    """
    # Build node lookup
    node_lut: dict[int, tuple[float, float]] = {}
    for n in overpass_nodes:
        if n.get("type") == "node":
            node_lut[n["id"]] = (n.get("lon", 0.0), n.get("lat", 0.0))

    lat_m = 111_320.0
    lon_m = 111_320.0 * math.cos(math.radians(38.56))

    # Collect bridge highway ways with their endpoint coords and node ids
    bridge_ways = []
    for w in overpass_ways:
        tags = w.get("tags", {})
        if tags.get("bridge") != "yes":
            continue
        if tags.get("highway") not in ("primary", "secondary", "tertiary",
                                        "trunk", "motorway"):
            continue
        nids = w.get("nodes", [])
        coords = [node_lut[nid] for nid in nids if nid in node_lut]
        if len(coords) < 2:
            continue
        bridge_ways.append({"way": w, "coords": coords, "nids": nids})

    if len(bridge_ways) < 2:
        return [], []

    new_nodes: list[dict] = []
    new_ways: list[dict] = []
    used = set()

    # Find pairs of bridge ways that are roughly parallel and close together
    for i in range(len(bridge_ways)):
        if i in used:
            continue
        a = bridge_ways[i]
        ac = a["coords"]
        a_mid_lon = (ac[0][0] + ac[-1][0]) / 2
        a_mid_lat = (ac[0][1] + ac[-1][1]) / 2
        a_dx = (ac[-1][0] - ac[0][0]) * lon_m
        a_dy = (ac[-1][1] - ac[0][1]) * lat_m
        a_len = math.sqrt(a_dx * a_dx + a_dy * a_dy)
        if a_len < 1:
            continue

        best_j = None
        best_dist = 25.0

        for j in range(len(bridge_ways)):
            if j == i or j in used:
                continue
            b = bridge_ways[j]
            bc = b["coords"]
            b_mid_lon = (bc[0][0] + bc[-1][0]) / 2
            b_mid_lat = (bc[0][1] + bc[-1][1]) / 2
            dist_m = math.sqrt(
                ((b_mid_lon - a_mid_lon) * lon_m) ** 2 +
                ((b_mid_lat - a_mid_lat) * lat_m) ** 2
            )
            b_dx = (bc[-1][0] - bc[0][0]) * lon_m
            b_dy = (bc[-1][1] - bc[0][1]) * lat_m
            b_len = math.sqrt(b_dx * b_dx + b_dy * b_dy)
            if b_len < 1:
                continue
            dot = abs((a_dx * b_dx + a_dy * b_dy) / (a_len * b_len))
            if dot < 0.8:
                continue
            if dist_m < best_dist:
                best_dist = dist_m
                best_j = j

        if best_j is None:
            continue

        used.add(i)
        used.add(best_j)
        b = bridge_ways[best_j]
        bc = b["coords"]

        # Determine which ends correspond (A[0]↔B[0] or A[0]↔B[-1])
        d00 = math.sqrt(((ac[0][0] - bc[0][0]) * lon_m) ** 2 +
                        ((ac[0][1] - bc[0][1]) * lat_m) ** 2)
        d01 = math.sqrt(((ac[0][0] - bc[-1][0]) * lon_m) ** 2 +
                        ((ac[0][1] - bc[-1][1]) * lat_m) ** 2)

        if d00 < d01:
            # A[0] near B[0], A[-1] near B[-1]
            start_a, end_a = ac[0], ac[-1]
            start_b, end_b = bc[0], bc[-1]
        else:
            # A[0] near B[-1], A[-1] near B[0]
            start_a, end_a = ac[0], ac[-1]
            start_b, end_b = bc[-1], bc[0]

        # ── Centerline way — runs down the middle of the gap ──
        # Interpolate along both ways and average to get centerline
        n_points = max(len(ac), len(bc), 4)
        center_coords = []
        for t in range(n_points):
            frac = t / max(n_points - 1, 1)
            # Lerp along A
            a_idx = frac * (len(ac) - 1)
            a_lo = int(a_idx)
            a_hi = min(a_lo + 1, len(ac) - 1)
            a_f = a_idx - a_lo
            ax = ac[a_lo][0] * (1 - a_f) + ac[a_hi][0] * a_f
            ay = ac[a_lo][1] * (1 - a_f) + ac[a_hi][1] * a_f
            # Lerp along B (use matched direction)
            if d00 < d01:
                b_idx = frac * (len(bc) - 1)
            else:
                b_idx = (1 - frac) * (len(bc) - 1)
            b_lo = int(b_idx)
            b_hi = min(b_lo + 1, len(bc) - 1)
            b_f = b_idx - b_lo
            bx = bc[b_lo][0] * (1 - b_f) + bc[b_hi][0] * b_f
            by = bc[b_lo][1] * (1 - b_f) + bc[b_hi][1] * b_f
            # Midpoint
            center_coords.append(((ax + bx) / 2, (ay + by) / 2))

        # Emit centerline nodes and way
        centerline_nids: list[int] = []
        for lon, lat in center_coords:
            nid = node_id_counter[0]
            node_id_counter[0] += 1
            new_nodes.append({
                "type": "node", "id": nid,
                "lat": lat, "lon": lon, "tags": {},
            })
            centerline_nids.append(nid)

        a_tags = a["way"]["tags"]
        way_id = node_id_counter[0]
        node_id_counter[0] += 1
        new_ways.append({
            "type": "way",
            "id": way_id,
            "nodes": centerline_nids,
            "tags": {
                "highway": a_tags.get("highway", "primary"),
                "bridge": "yes",
                "layer": a_tags.get("layer", "1"),
                "surface": "asphalt",
                "source": "synthetic_bridge_fill",
            },
        })

        # ── Approach ramps — short ground-level ways extending from
        #    each bridge endpoint outward along the road direction,
        #    tagged layer=0.  These ensure the Arnis connectivity map
        #    sees a layer=0 way at the bridge endpoint node so ramp
        #    slopes are generated on all three bridge ways. ──
        RAMP_LENGTH_M = 20.0  # length of ground-level approach stub

        for way_data in [a, b]:
            wc = way_data["coords"]
            wnids = way_data["nids"]
            for end_idx, dir_sign in [(0, -1), (-1, 1)]:
                # Direction vector from this end into the bridge
                other_idx = 1 if end_idx == 0 else -2
                if abs(other_idx) >= len(wc):
                    continue
                dx_m = (wc[other_idx][0] - wc[end_idx][0]) * lon_m
                dy_m = (wc[other_idx][1] - wc[end_idx][1]) * lat_m
                seg_len = math.sqrt(dx_m * dx_m + dy_m * dy_m)
                if seg_len < 0.1:
                    continue
                # Extend OUTWARD from bridge end (opposite direction)
                ext_lon = wc[end_idx][0] - (dx_m / seg_len) * RAMP_LENGTH_M / lon_m
                ext_lat = wc[end_idx][1] - (dy_m / seg_len) * RAMP_LENGTH_M / lat_m

                # Ramp start = bridge endpoint node (reuse its id for connectivity)
                bridge_end_nid = wnids[end_idx] if end_idx >= 0 else wnids[len(wnids) + end_idx]

                ext_nid = node_id_counter[0]
                node_id_counter[0] += 1
                new_nodes.append({
                    "type": "node", "id": ext_nid,
                    "lat": ext_lat, "lon": ext_lon, "tags": {},
                })

                ramp_way_id = node_id_counter[0]
                node_id_counter[0] += 1
                if end_idx == 0:
                    ramp_nids = [ext_nid, bridge_end_nid]
                else:
                    ramp_nids = [bridge_end_nid, ext_nid]

                new_ways.append({
                    "type": "way",
                    "id": ramp_way_id,
                    "nodes": ramp_nids,
                    "tags": {
                        "highway": a_tags.get("highway", "primary"),
                        "layer": "0",
                        "surface": "asphalt",
                        "source": "synthetic_bridge_ramp",
                    },
                })

    return new_nodes, new_ways


def generate_driveways(
    features: list[dict],
    node_id_counter: list[int],
) -> tuple[list[dict], list[dict]]:
    """
    Generate synthetic driveways connecting each residential building
    to the nearest road.  Returns (nodes, ways).
    """
    if not HAS_SHAPELY:
        return [], []

    lat_m = 111_320.0
    lon_m = 111_320.0 * math.cos(math.radians(38.54))

    # Collect road centerlines
    road_types = {"residential", "living_street", "tertiary", "secondary",
                  "primary", "service", "unclassified"}
    road_lines: list[LineString] = []
    for feat in features:
        props = feat.get("properties", feat) if feat.get("type") == "Feature" else feat
        if props.get("type") != "highway":
            continue
        tags = props.get("tags") or {}
        hw = tags.get("highway", props.get("subtype", ""))
        if hw not in road_types:
            continue
        geom = feat.get("geometry") if feat.get("type") == "Feature" else None
        if geom and geom.get("type") == "LineString":
            coords = geom["coordinates"]
        else:
            coords = props.get("coords", [])
        if len(coords) >= 2:
            road_lines.append(LineString(coords))

    if not road_lines:
        return [], []

    road_union = unary_union(road_lines)

    # Collect residential building centroids
    building_types = {"yes", "house", "residential", "detached", "semidetached_house",
                      "terrace", "apartments", ""}
    nodes_out: list[dict] = []
    ways_out: list[dict] = []

    for feat in features:
        props = feat.get("properties", feat) if feat.get("type") == "Feature" else feat
        if props.get("type") != "building":
            continue
        tags = props.get("tags") or {}
        btype = tags.get("building", props.get("subtype", "yes"))
        if btype not in building_types:
            continue

        geom = feat.get("geometry") if feat.get("type") == "Feature" else None
        if geom and geom.get("type") == "Polygon":
            coords = geom["coordinates"][0] if geom["coordinates"] else []
        else:
            coords = props.get("coords", [])
        if len(coords) < 3:
            continue

        # Building centroid
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        clon = sum(lons) / len(lons)
        clat = sum(lats) / len(lats)

        bldg_pt = Point(clon, clat)
        nearest_pt = road_union.interpolate(road_union.project(bldg_pt))

        # Distance check — skip if too far (>50m) or too close (<3m)
        dist_deg = bldg_pt.distance(nearest_pt)
        dist_m = dist_deg * lon_m
        if dist_m > 50 or dist_m < 3:
            continue

        # Create driveway as 2-node way
        n1_id = node_id_counter[0]; node_id_counter[0] += 1
        n2_id = node_id_counter[0]; node_id_counter[0] += 1
        w_id = node_id_counter[0]; node_id_counter[0] += 1

        nodes_out.append({"type": "node", "id": n1_id,
                          "lat": clat, "lon": clon, "tags": {}})
        nodes_out.append({"type": "node", "id": n2_id,
                          "lat": nearest_pt.y, "lon": nearest_pt.x, "tags": {}})
        ways_out.append({
            "type": "way", "id": w_id,
            "nodes": [n1_id, n2_id],
            "tags": {"highway": "footway",
                     "surface": "concrete", "source": "synthetic_driveway"},
        })

    return nodes_out, ways_out


def generate_yards(
    features: list[dict],
    node_id_counter: list[int],
    driveway_nodes: list[dict] | None = None,
    driveway_ways: list[dict] | None = None,
    buffer_m: float = 8.0,
) -> tuple[list[dict], list[dict]]:
    """
    Generate yard polygons (leisure=garden) around each residential building.
    Creates a buffered polygon around the building footprint, then subtracts
    the building itself, roads, and driveways to leave green yards.
    Returns (nodes, ways).
    """
    if not HAS_SHAPELY:
        return [], []

    lat_m = DEG_PER_METRE_LAT
    lon_m = DEG_PER_METRE_LON

    building_types = {"yes", "house", "residential", "detached",
                      "semidetached_house", "terrace", "apartments", ""}

    # Collect road geometries to avoid placing yards over roads
    road_lines: list = []
    for feat in features:
        props = feat.get("properties", feat) if feat.get("type") == "Feature" else feat
        if props.get("type") != "highway":
            continue
        geom = feat.get("geometry") if feat.get("type") == "Feature" else None
        if geom and geom.get("type") == "LineString":
            coords = geom["coordinates"]
        else:
            coords = props.get("coords", [])
        if len(coords) >= 2:
            road_lines.append(LineString(coords))

    # Build driveway lines from synthetic driveway nodes/ways
    if driveway_nodes and driveway_ways:
        dw_node_lut = {n["id"]: (n["lon"], n["lat"]) for n in driveway_nodes}
        for dw in driveway_ways:
            dw_coords = [dw_node_lut[nid] for nid in dw.get("nodes", []) if nid in dw_node_lut]
            if len(dw_coords) >= 2:
                road_lines.append(LineString(dw_coords))

    road_buffer = None
    if road_lines:
        try:
            road_union = unary_union(road_lines)
            # Buffer roads/driveways by ~3m in degrees
            road_buffer = road_union.buffer(3.0 * lon_m)
        except Exception as e:
            log.warning("Road buffer failed (OOM on large areas) — yards will overlap roads: %s", e)
            road_buffer = None

    nodes_out: list[dict] = []
    ways_out: list[dict] = []

    for feat in features:
        props = feat.get("properties", feat) if feat.get("type") == "Feature" else feat
        if props.get("type") != "building":
            continue
        tags = props.get("tags") or {}
        btype = tags.get("building", props.get("subtype", "yes"))
        if btype not in building_types:
            continue

        geom = feat.get("geometry") if feat.get("type") == "Feature" else None
        if geom and geom.get("type") == "Polygon":
            coords = geom["coordinates"][0] if geom["coordinates"] else []
        else:
            coords = props.get("coords", [])
        if len(coords) < 3:
            continue

        try:
            bldg_poly = Polygon(coords)
            if not bldg_poly.is_valid:
                continue
        except Exception:
            continue

        # Buffer outward by buffer_m in degrees
        yard = bldg_poly.buffer(buffer_m * lon_m)

        # Subtract the building footprint itself
        yard = yard.difference(bldg_poly)

        # Subtract roads
        if road_buffer is not None:
            yard = yard.difference(road_buffer)

        if yard.is_empty:
            continue

        # Convert to polygon coords (take exterior only, skip holes)
        polys = [yard] if yard.geom_type == "Polygon" else list(yard.geoms) if yard.geom_type == "MultiPolygon" else []

        for poly in polys:
            if poly.is_empty or poly.area < 1e-12:
                continue
            ext_coords = list(poly.exterior.coords)
            if len(ext_coords) < 4:
                continue
            # Simplify to reduce node count
            simplified = poly.simplify(1.0 * lon_m)
            if simplified.is_empty:
                continue
            if simplified.geom_type == "Polygon":
                ext_coords = list(simplified.exterior.coords)
            else:
                continue
            if len(ext_coords) < 4:
                continue

            nids = []
            for lon_c, lat_c in ext_coords:
                nid = node_id_counter[0]; node_id_counter[0] += 1
                nodes_out.append({"type": "node", "id": nid,
                                  "lat": lat_c, "lon": lon_c, "tags": {}})
                nids.append(nid)

            wid = node_id_counter[0]; node_id_counter[0] += 1
            ways_out.append({
                "type": "way", "id": wid,
                "nodes": nids,
                "tags": {"leisure": "garden", "source": "synthetic_yard"},
            })

    return nodes_out, ways_out


def deconflict_grass_with_landuse(
    grass_nodes: list[dict],
    grass_ways: list[dict],
    overpass_ways: list[dict],
    overpass_nodes: list[dict],
) -> tuple[list[dict], list[dict]]:
    """
    Remove NAIP grass polygons that overlap with farmland or other
    non-grass landuse polygons to prevent overriding their rendering.
    """
    if not HAS_SHAPELY or not grass_ways:
        return grass_nodes, grass_ways

    # Build node lookup
    node_lut: dict[int, tuple[float, float]] = {}
    for n in overpass_nodes:
        if n.get("type") == "node" and "lat" in n and "lon" in n:
            node_lut[n["id"]] = (n["lon"], n["lat"])

    # Collect landuse polygons that should NOT be covered by grass
    exclude_landuse = {"farmland", "orchard", "vineyard", "industrial",
                       "commercial", "retail", "construction"}
    landuse_polys = []
    for w in overpass_ways:
        tags = w.get("tags", {})
        lu = tags.get("landuse", "")
        if lu not in exclude_landuse:
            continue
        nids = w.get("nodes", [])
        coords = [node_lut[nid] for nid in nids if nid in node_lut]
        if len(coords) >= 3:
            try:
                poly = Polygon(coords)
                if poly.is_valid:
                    landuse_polys.append(poly)
            except Exception:
                pass

    if not landuse_polys:
        return grass_nodes, grass_ways

    exclusion = unary_union(landuse_polys)
    prep_exclusion = prepared.prep(exclusion)

    # Build grass node lookup
    grass_node_lut: dict[int, dict] = {}
    for n in grass_nodes:
        grass_node_lut[n["id"]] = n

    kept_ways = []
    removed_node_ids: set[int] = set()
    removed_count = 0
    for gw in grass_ways:
        nids = gw.get("nodes", [])
        coords = [(grass_node_lut[nid]["lon"], grass_node_lut[nid]["lat"])
                   for nid in nids if nid in grass_node_lut]
        if len(coords) < 3:
            kept_ways.append(gw)
            continue
        centroid = Point(sum(c[0] for c in coords) / len(coords),
                         sum(c[1] for c in coords) / len(coords))
        if prep_exclusion.contains(centroid):
            removed_count += 1
            removed_node_ids.update(nids)
        else:
            kept_ways.append(gw)

    kept_nodes = [n for n in grass_nodes if n["id"] not in removed_node_ids]
    log.info("  Grass de-confliction: %d kept, %d removed (overlap with farmland/commercial)",
             len(kept_ways), removed_count)
    return kept_nodes, kept_ways
# ── Main conversion ────────────────────────────────────────────────────────────

def convert(
    fused_path: Path,
    output_dir: Path,
    zones_path: Path | None = None,
    colour_db_path: Path | None = None,
    dsm_path: Path | None = None,
    dtm_path: Path | None = None,
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

    # Filter out bicycle_parking nodes (renders as yellow scaffolding — BT-002)
    pre_count = len(features)
    features = [
        f for f in features
        if not ((f.get("properties") or f).get("subtype") == "bicycle_parking"
                or (f.get("properties") or f).get("tags", {}).get("amenity") == "bicycle_parking")
    ]
    filtered = pre_count - len(features)
    if filtered:
        log.info("Filtered %d bicycle_parking elements (BT-002)", filtered)

    # Initialise multi-source height validator
    validator = init_validator(
        dsm_path=str(dsm_path) if dsm_path else None,
        dtm_path=str(dtm_path) if dtm_path else None,
    )

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
    height_reviews:    list[dict] = []     # flagged buildings for review

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
                "building:material", "roof:shape", "surface", "service",
                "access", "sport", "bridge", "layer", "railway",
                "barrier", "fence_type", "lit", "lanes",
                "oneway", "maxspeed", "ref",
                "power", "man_made", "emergency", "advertising",
                "golf", "historic", "tourism",
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

            height_result = enrich_4a_height(props, tags, record, validator)
            enrich_4c_colour(props, tags, record, colour_cache)
            enrich_4d_type(props, tags, record)
            enrich_4e_passthrough(props, tags, record)

            zone = get_zone_for_feature(props, zones)
            enrich_5_spec003(props, tags, record, zone)

            # Collect flagged buildings for height_review.json
            if height_result and height_result.flag in ("yellow", "red"):
                height_reviews.append({
                    "osm_id": osm_id,
                    "name": name or "(unnamed)",
                    "flag": height_result.flag,
                    "final_height_m": height_result.final_height_m,
                    "final_levels": height_result.final_levels,
                    "confidence": round(height_result.confidence, 2),
                    "source_used": height_result.source_used,
                    "note": height_result.note,
                    "readings": [
                        {"source": r.source, "height_m": r.height_m, "trust": r.trust}
                        for r in height_result.readings
                    ],
                    "lat": props.get("lat"),
                    "lon": props.get("lon"),
                })

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

    # ── Exclude iconic buildings replaced by custom assets ─────────────────
    # These OSM way IDs will be rebuilt using hand-crafted StructureBuilder
    # assets, so Arnis must NOT render its own version (prevents collisions).
    ICONIC_EXCLUSIONS: set[int] = {
        62095055,   # Davis Station (Amtrak) — replaced by build_amtrak_v3.py
        # Add more way IDs here as iconic assets are created
    }
    pre_iconic = len(overpass_ways)
    overpass_ways = [w for w in overpass_ways if w.get("id") not in ICONIC_EXCLUSIONS]
    iconic_dropped = pre_iconic - len(overpass_ways)
    if iconic_dropped:
        log.info("Excluded %d iconic building(s) from Arnis rendering: %s",
                 iconic_dropped, ICONIC_EXCLUSIONS)

    # ── Filter oversized untyped buildings (Overture false positives) ──────
    MAX_UNTYPED_SPAN_M = 100  # any building=yes wider than 100m is suspicious
    _node_lut: dict[int, tuple[float, float]] = {}
    for n in overpass_nodes:
        if n.get("type") == "node" and "lat" in n and "lon" in n:
            _node_lut[n["id"]] = (n["lat"], n["lon"])
    pre_way_count = len(overpass_ways)
    filtered_ways = []
    for w in overpass_ways:
        tags = w.get("tags", {})
        if tags.get("building") == "yes":
            nids = w.get("nodes", [])
            node_coords = [_node_lut[n] for n in nids if n in _node_lut]
            if node_coords:
                lats = [c[0] for c in node_coords]
                lngs = [c[1] for c in node_coords]
                w_m = (max(lngs) - min(lngs)) * 87000
                h_m = (max(lats) - min(lats)) * 111319
                if max(w_m, h_m) > MAX_UNTYPED_SPAN_M:
                    continue  # drop this false positive
        filtered_ways.append(w)
    dropped = pre_way_count - len(filtered_ways)
    if dropped:
        overpass_ways = filtered_ways
        log.info("Filtered %d oversized untyped buildings (span > %dm)",
                 dropped, MAX_UNTYPED_SPAN_M)

    # ── Assemble final Overpass JSON ─────────────────────────────────────────
    # Add trees — prefer NAIP-detected trees, fall back to synthetic street trees
    naip_trees_path = output_dir / "naip_trees_overpass.json"
    if naip_trees_path.exists():
        with open(naip_trees_path) as f:
            naip_trees = json.load(f)
        if naip_trees:
            naip_trees = deconflict_trees(naip_trees, overpass_ways, overpass_nodes)
            overpass_nodes.extend(naip_trees)
            log.info("NAIP trees: %d satellite-detected trees loaded", len(naip_trees))
    else:
        street_trees = generate_street_trees(features, node_id_counter)
        if street_trees:
            street_trees = deconflict_trees(street_trees, overpass_ways, overpass_nodes)
            overpass_nodes.extend(street_trees)
            log.info("Street trees: %d synthetic trees after de-confliction",
                     len(street_trees))

    # Add synthetic driveways for every residential building
    dw_nodes, dw_ways = generate_driveways(features, node_id_counter)
    if dw_ways:
        overpass_nodes.extend(dw_nodes)
        overpass_ways.extend(dw_ways)
        log.info("Synthetic driveways: %d generated", len(dw_ways))

    # Add synthetic yard/garden polygons around residential buildings
    try:
        yd_nodes, yd_ways = generate_yards(features, node_id_counter,
                                           driveway_nodes=dw_nodes, driveway_ways=dw_ways)
        if yd_ways:
            overpass_nodes.extend(yd_nodes)
            overpass_ways.extend(yd_ways)
            log.info("Synthetic yards: %d garden polygons generated", len(yd_ways))
    except Exception as e:
        log.warning("Yard generation failed (non-fatal): %s", e)

    # Baseball infield generation disabled — diamond orientation needs work (CV-003)
    # bi_nodes, bi_ways = generate_baseball_infields(
    #     overpass_ways, overpass_nodes, node_id_counter)
    # if bi_ways:
    #     overpass_nodes.extend(bi_nodes)
    #     overpass_ways.extend(bi_ways)
    #     log.info("Baseball infields: %d dirt diamond polygons generated", len(bi_ways))

    # Merge parallel bridge segments (fill median gaps on divided overpasses)
    bf_nodes, bf_ways = merge_bridge_segments(
        overpass_ways, overpass_nodes, node_id_counter)
    if bf_ways:
        overpass_nodes.extend(bf_nodes)
        overpass_ways.extend(bf_ways)
        log.info("Bridge fills: %d synthetic bridge deck polygons generated", len(bf_ways))

    # Add NAIP-detected grass areas (de-conflicted with farmland / commercial)
    naip_grass_path = output_dir / "naip_grass_overpass.json"
    if naip_grass_path.exists():
        with open(naip_grass_path) as f:
            grass_data = json.load(f)
        grass_nodes = grass_data.get("nodes", [])
        grass_ways = grass_data.get("ways", [])
        if grass_nodes:
            grass_nodes, grass_ways = deconflict_grass_with_landuse(
                grass_nodes, grass_ways, overpass_ways, overpass_nodes)
            overpass_nodes.extend(grass_nodes)
            overpass_ways.extend(grass_ways)
            log.info("NAIP grass: %d polygons (%d nodes) loaded (after de-confliction)",
                     len(grass_ways), len(grass_nodes))

    # NAIP pool detection disabled — NDWI at 0.6m produces too many false
    # positives (shadows, blue roofs, tarps) and no spatial de-confliction
    # with trees causes trees-in-pools artefacts.  See POC7 v1 review.
    # naip_pools_path = output_dir / "naip_pools_overpass.json"

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
    review_path   = output_dir / "height_review.json"

    with open(overpass_path, "w", encoding="utf-8") as f:
        json.dump(overpass_out, f)

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(enrichment_log, f, indent=2)

    # Height review report — buildings flagged for manual verification
    red_count    = sum(1 for r in height_reviews if r["flag"] == "red")
    yellow_count = sum(1 for r in height_reviews if r["flag"] == "yellow")
    review_out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_flagged": len(height_reviews),
        "red": red_count,
        "yellow": yellow_count,
        "buildings": sorted(height_reviews, key=lambda r: (0 if r["flag"] == "red" else 1, -r.get("final_height_m", 0))),
    }
    with open(review_path, "w", encoding="utf-8") as f:
        json.dump(review_out, f, indent=2)
    log.info("Height review: %d flagged (%d RED, %d YELLOW) → %s",
             len(height_reviews), red_count, yellow_count, review_path)

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
    parser.add_argument(
        "--dsm", default=None,
        help="Path to DSM GeoTIFF (first-return surface) for LiDAR height triangulation"
    )
    parser.add_argument(
        "--dtm", default=None,
        help="Path to DTM GeoTIFF (bare-earth) for LiDAR height triangulation"
    )
    args = parser.parse_args()

    overpass_path, log_path, summary_path = convert(
        fused_path     = Path(args.fused),
        output_dir     = Path(args.output),
        zones_path     = Path(args.spec003_zones) if args.spec003_zones else None,
        colour_db_path = Path(args.mapillary_cache) if args.mapillary_cache else None,
        dsm_path       = Path(args.dsm) if args.dsm else None,
        dtm_path       = Path(args.dtm) if args.dtm else None,
    )

    print(f"\nReady for Arnis:")
    print(f"  arnis --file {overpass_path} --path <world_output> --bbox <bbox>")
    print(f"\nEnrichment summary: {summary_path}")


if __name__ == "__main__":
    main()
