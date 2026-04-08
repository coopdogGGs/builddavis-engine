"""
BuildDavis Pipeline — Stage 5: Transform
=========================================
Takes the fused GeoJSON from Stage 4 and the 1m DEM from Stage 2,
applies SPEC-003 block palette rules to every element, and outputs
blocks.json — the complete block placement list for the Rust engine.

Input:
    data/fused_features.geojson   — fused elements from Stage 4
    data/davis_dem_1m.tif         — 1m DEM from Stage 2 (optional, uses
                                    flat fallback if not present)

Output:
    data/blocks.json              — block placement list for Stage 6 (Rust)
    data/transform_manifest.json  — statistics and quality report

Block placement format (one entry per block):
    {"x": int, "y": int, "z": int, "block": str, "layer": str}

    x, z: Minecraft block coordinates (origin = Amtrak Station)
    y:    Minecraft Y coordinate from DEM elevation mapping
    block: Minecraft block ID (e.g. "minecraft:smooth_sandstone")
    layer: which pipeline layer placed this block (terrain/road/building/object)

SPEC-003 palette summary:
    Downtown commercial  → minecraft:brick (SPEC-003 bug fix — was sandstone)
    Residential          → minecraft:smooth_sandstone
    UC Davis campus      → minecraft:smooth_stone
    Roads (primary)      → minecraft:gray_concrete
    Bike paths Class I   → minecraft:light_gray_concrete
    Parks / grass        → minecraft:grass_block
    Water                → minecraft:water
    Farmland             → minecraft:farmland

Elevation mapping (ADR-001):
    Y = SEA_LEVEL_Y + elevation_metres
    SEA_LEVEL_Y = 32
    Typical Davis ground (~15m) → Y47
    UC Davis campus (~18m)      → Y50

Usage:
    python transform.py --fused data/fused_features.geojson --output data/
    python transform.py --fused data/fused_features.geojson --dem data/davis_dem_1m.tif --output data/

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

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("transform")

# ── Elevation constants (ADR-001) ─────────────────────────────────────────────
SEA_LEVEL_Y          = 32
DAVIS_GROUND_Y       = 47   # ~15m elevation
DAVIS_CAMPUS_Y       = 50   # ~18m elevation
WATER_Y              = 46   # Putah Creek, Arboretum
DEFAULT_GROUND_Y     = DAVIS_GROUND_Y

# ── Layer names ───────────────────────────────────────────────────────────────
LAYER_TERRAIN  = "terrain"
LAYER_ROAD     = "road"
LAYER_BUILDING = "building"
LAYER_OBJECT   = "object"
LAYER_WATER    = "water"
LAYER_RAILWAY  = "road"      # Railway shares road priority for dedup

# ── SPEC-003 Block Palette ─────────────────────────────────────────────────────
# Full palette — every OSM tag combination maps to a Minecraft block

# Terrain / landuse
PALETTE_TERRAIN = {
    "residential":        "minecraft:grass_block",
    "commercial":         "minecraft:stone",
    "retail":             "minecraft:stone",
    "industrial":         "minecraft:cobblestone",
    "farmland":           "minecraft:farmland",
    "farm":               "minecraft:farmland",
    "orchard":            "minecraft:farmland",
    "vineyard":           "minecraft:farmland",
    "grass":              "minecraft:grass_block",
    "meadow":             "minecraft:grass_block",
    "park":               "minecraft:grass_block",
    "recreation_ground":  "minecraft:grass_block",
    "village_green":      "minecraft:grass_block",
    "cemetery":           "minecraft:grass_block",
    "forest":             "minecraft:grass_block",
    "wood":               "minecraft:grass_block",
    "scrub":              "minecraft:dirt",
    "bare_rock":          "minecraft:stone",
    "sand":               "minecraft:sand",
    "wetland":            "minecraft:clay",
    "water":              "minecraft:water",
    "basin":              "minecraft:water",
    "reservoir":          "minecraft:water",
    "university":         "minecraft:grass_block",
    "school":             "minecraft:grass_block",
    "default":            "minecraft:grass_block",
}

# Road surface blocks (SPEC-003)
PALETTE_ROAD = {
    "motorway":           "minecraft:gray_concrete",
    "trunk":              "minecraft:gray_concrete",
    "primary":            "minecraft:gray_concrete",
    "secondary":          "minecraft:gray_concrete",
    "tertiary":           "minecraft:light_gray_concrete",
    "residential":        "minecraft:light_gray_concrete",
    "unclassified":       "minecraft:light_gray_concrete",
    "service":            "minecraft:light_gray_concrete",
    "living_street":      "minecraft:light_gray_concrete",
    "pedestrian":         "minecraft:white_concrete",
    "footway":            "minecraft:white_concrete",
    "path":               "minecraft:gravel",
    "track":              "minecraft:dirt",
    # Bike paths — Class I gets distinctive light grey + white edges
    "cycleway":           "minecraft:light_gray_concrete",
    "class_i":            "minecraft:light_gray_concrete",
    "class_ii":           "minecraft:gray_concrete",
    "class_iii":          "minecraft:light_gray_concrete",
    "default":            "minecraft:light_gray_concrete",
}

# Road stripe / edge blocks (placed at path edges for Class I bike paths)
BIKE_PATH_EDGE_BLOCK = "minecraft:white_concrete"

# Railway block palette
PALETTE_RAILWAY = {
    "rail":               "minecraft:iron_block",       # standard gauge
    "light_rail":         "minecraft:iron_block",
    "subway":             "minecraft:iron_block",
    "tram":               "minecraft:iron_block",
    "platform":           "minecraft:smooth_stone_slab",
    "station":            "minecraft:smooth_stone",
    "default":            "minecraft:iron_block",
}
RAILWAY_SLEEPER_BLOCK  = "minecraft:dark_oak_planks"    # cross-ties
RAILWAY_BALLAST_BLOCK  = "minecraft:gravel"             # gravel bed

# Building wall blocks by zoning / use type (SPEC-003 + downtown commercial fix)
PALETTE_BUILDING_WALL = {
    # Downtown commercial — FIXED from sandstone to brick (POC bug)
    "commercial":         "minecraft:brick",
    "retail":             "minecraft:brick",
    "office":             "minecraft:brick",
    "civic":              "minecraft:brick",
    "government":         "minecraft:brick",
    # Residential
    "house":              "minecraft:smooth_sandstone",
    "residential":        "minecraft:smooth_sandstone",
    "apartments":         "minecraft:smooth_sandstone",
    "detached":           "minecraft:smooth_sandstone",
    "semidetached_house": "minecraft:smooth_sandstone",
    "terrace":            "minecraft:smooth_sandstone",
    # UC Davis campus — modernist concrete
    "university":         "minecraft:smooth_stone",
    "college":            "minecraft:smooth_stone",
    "school":             "minecraft:smooth_stone",
    # Industrial / utility
    "industrial":         "minecraft:stone_bricks",
    "warehouse":          "minecraft:stone_bricks",
    "garage":             "minecraft:cobblestone",
    "parking":            "minecraft:cobblestone",
    # Religious / historic
    "church":             "minecraft:stone_bricks",
    "historic":           "minecraft:stone_bricks",
    # Default fallback — tan stucco (most common in Davis)
    "default":            "minecraft:smooth_sandstone",
}

# Building roof blocks by type (SPEC-003)
PALETTE_ROOF = {
    "flat":               "minecraft:smooth_stone_slab",
    "gabled":             "minecraft:oak_stairs",
    "hipped":             "minecraft:oak_stairs",
    "pyramidal":          "minecraft:oak_stairs",
    "skillion":           "minecraft:oak_slab",
    "default":            "minecraft:smooth_stone_slab",
}

# Floor / ground floor block (inside building footprint)
BUILDING_FLOOR_BLOCK  = "minecraft:stone"
BUILDING_FILL_BLOCK   = "minecraft:air"    # interior air

# Waterway blocks
PALETTE_WATER = {
    "river":    "minecraft:water",
    "stream":   "minecraft:water",
    "canal":    "minecraft:water",
    "drain":    "minecraft:water",
    "ditch":    "minecraft:water",
    "default":  "minecraft:water",
}
WATERWAY_BANK_BLOCK  = "minecraft:smooth_stone"   # Arboretum cement banks
WATERWAY_EARTH_BLOCK = "minecraft:dirt"            # Natural creek banks

# Natural feature blocks
PALETTE_NATURAL = {
    "tree":         "minecraft:oak_log",     # trunk — canopy added separately
    "wood":         "minecraft:oak_leaves",
    "scrub":        "minecraft:fern",
    "grassland":    "minecraft:grass_block",
    "heath":        "minecraft:grass_block",
    "water":        "minecraft:water",
    "wetland":      "minecraft:clay",
    "default":      "minecraft:grass_block",
}

# Amenity / street furniture blocks (SPEC-003 Section 5)
PALETTE_AMENITY = {
    "bench":            "minecraft:oak_slab",
    "waste_basket":     "minecraft:barrel",
    "bicycle_parking":  "minecraft:iron_bars",
    "drinking_water":   "minecraft:cauldron",
    "post_box":         "minecraft:red_wool",
    "telephone":        "minecraft:glass",
    "recycling":        "minecraft:lime_wool",
    "fire_hydrant":     "minecraft:red_concrete",
    "bus_stop":         "minecraft:oak_fence",
    "parking":          "minecraft:light_gray_concrete",
    "default":          "minecraft:oak_slab",
}

# Landmark-specific palette overrides (ICONIC-001)
LANDMARK_PALETTE = {
    # name_key: {wall, roof, height_blocks (overrides Overture if present)}
    "davis amtrak":       {"wall": "minecraft:smooth_sandstone", "roof": "minecraft:terracotta",        "height_blocks": 5},
    "davisville":         {"wall": "minecraft:smooth_sandstone", "roof": "minecraft:terracotta",        "height_blocks": 5},
    "varsity theatre":    {"wall": "minecraft:brick",            "roof": "minecraft:brick_slab",        "height_blocks": 6},
    "varsity theater":    {"wall": "minecraft:brick",            "roof": "minecraft:brick_slab",        "height_blocks": 6},
    "memorial union":     {"wall": "minecraft:smooth_sandstone", "roof": "minecraft:terracotta",        "height_blocks": 6},
    "shields library":    {"wall": "minecraft:smooth_stone",     "roof": "minecraft:smooth_stone_slab", "height_blocks": 7},
    "death star":         {"wall": "minecraft:iron_block",       "roof": "minecraft:iron_block",        "height_blocks": 8},
    "ssh building":       {"wall": "minecraft:iron_block",       "roof": "minecraft:iron_block",        "height_blocks": 8},
    "mondavi":            {"wall": "minecraft:quartz_block",     "roof": "minecraft:quartz_slab",       "height_blocks": 5},
    "the silo":           {"wall": "minecraft:oak_planks",       "roof": "minecraft:oak_stairs",        "height_blocks": 4},
}

# Default building height if no OSM or Overture data (blocks)
DEFAULT_HEIGHT_BLOCKS = {
    "commercial":   5,
    "retail":       4,
    "office":       6,
    "residential":  4,
    "house":        4,
    "apartments":   8,
    "university":   5,
    "industrial":   4,
    "default":      4,
}


# ─────────────────────────────────────────────────────────────────────────────
# DEM elevation lookup
# ─────────────────────────────────────────────────────────────────────────────

class ElevationLookup:
    """
    Looks up Minecraft Y coordinate from the DEM for a given (mc_x, mc_z).
    Falls back to flat Davis ground (Y47) if DEM is not available.
    """

    def __init__(self, dem_path: Optional[Path] = None):
        self.dem_data   = None
        self.dem_origin = None  # (mc_x_min, mc_z_min)
        self.dem_size   = None  # (width, height) in pixels
        self._load(dem_path)

    def _load(self, dem_path: Optional[Path]):
        if not dem_path or not dem_path.exists():
            log.info("  DEM not available — using flat terrain Y%d", DEFAULT_GROUND_Y)
            return
        try:
            import rasterio
            import numpy as np
            with rasterio.open(dem_path) as src:
                self.dem_data   = src.read(1).astype(float)
                self.dem_nodata = src.nodata or -9999.0
                self.dem_data[self.dem_data == self.dem_nodata] = 15.0
                self.transform  = src.transform
                self.width      = src.width
                self.height     = src.height
            log.info("  DEM loaded: %d × %d pixels", self.width, self.height)
        except Exception as exc:
            log.warning("  DEM load failed: %s — using flat terrain", exc)
            self.dem_data = None

    def get_y(self, mc_x: int, mc_z: int) -> int:
        """
        Get Minecraft Y for a Minecraft (X, Z) coordinate.
        Uses bilinear-ish lookup from DEM if available.
        """
        if self.dem_data is None:
            return DEFAULT_GROUND_Y

        try:
            import rasterio
            # Convert Minecraft coords back to geographic
            # mc_x = (lon - origin_lon) * lon_to_m
            # mc_z = -(lat - origin_lat) * lat_to_m
            # This inverse is approximate — transform handles it properly
            row, col = rasterio.transform.rowcol(
                self.transform, mc_x, mc_z
            )
            row = max(0, min(row, self.height - 1))
            col = max(0, min(col, self.width  - 1))
            elev_m = float(self.dem_data[row, col])
            return SEA_LEVEL_Y + int(round(elev_m))
        except Exception:
            return DEFAULT_GROUND_Y


# ─────────────────────────────────────────────────────────────────────────────
# Block palette resolution
# ─────────────────────────────────────────────────────────────────────────────

def resolve_building_palette(props: dict) -> tuple:
    """
    Resolve wall and roof block for a building from its properties.
    Returns (wall_block, roof_block, height_blocks).

    Priority:
      1. Landmark override (ICONIC-001)
      2. OSM building:material tag
      3. Building subtype / use
      4. Default (smooth_sandstone — most common Davis residential)
    """
    name    = (props.get("name") or props.get("osm_name") or "").lower()
    subtype = (props.get("subtype") or props.get("osm_building") or "").lower()
    mat     = (props.get("material") or props.get("osm_building:material") or "").lower()

    # Normalize generic OSM subtypes to sensible defaults
    SUBTYPE_NORMALIZE = {
        "yes": "residential",       # generic OSM "building=yes"
        "houses": "house",
        "transportation": "civic",
        "train_station": "civic",
        "museum": "civic",
        "shed": "garage",
        "roof": "garage",
    }
    subtype = SUBTYPE_NORMALIZE.get(subtype, subtype)

    # 1. Landmark override
    for landmark_key, palette in LANDMARK_PALETTE.items():
        if landmark_key in name:
            wall  = palette["wall"]
            roof  = palette.get("roof", PALETTE_ROOF["default"])
            # Use Overture height if available, otherwise use landmark hardcoded height
            if props.get("height_blocks"):
                h_blocks = int(props["height_blocks"])
            elif props.get("height_m"):
                h_blocks = max(3, int(round(float(props["height_m"]))))
            else:
                h_blocks = palette.get("height_blocks", DEFAULT_HEIGHT_BLOCKS.get(subtype, 4))
            return wall, roof, h_blocks

    # 2. Material tag → wall block
    material_map = {
        "brick":     "minecraft:brick",
        "stone":     "minecraft:stone_bricks",
        "concrete":  "minecraft:smooth_stone",
        "wood":      "minecraft:oak_planks",
        "glass":     "minecraft:glass",
        "metal":     "minecraft:iron_block",
        "sandstone": "minecraft:smooth_sandstone",
        "plaster":   "minecraft:smooth_sandstone",
        "stucco":    "minecraft:smooth_sandstone",
    }
    wall = None
    for mat_key, block in material_map.items():
        if mat_key in mat:
            wall = block
            break

    # 3. Subtype → wall block
    if not wall:
        wall = PALETTE_BUILDING_WALL.get(subtype,
               PALETTE_BUILDING_WALL.get("default"))

    # 4. Roof shape
    roof_shape = (props.get("roof_shape") or props.get("osm_roof:shape") or "flat").lower()
    roof = PALETTE_ROOF.get(roof_shape, PALETTE_ROOF["default"])

    # 5. Height — explicit priority chain to avoid operator precedence bugs
    if props.get("height_blocks"):
        h_blocks = int(props["height_blocks"])
    elif props.get("height_m"):
        h_blocks = max(3, int(round(float(props["height_m"]))))
    else:
        h_blocks = DEFAULT_HEIGHT_BLOCKS.get(subtype, DEFAULT_HEIGHT_BLOCKS["default"])

    return wall, roof, h_blocks


def resolve_road_block(props: dict) -> str:
    """Resolve the surface block for a road/path element."""
    bike_class = props.get("bike_class")
    highway    = (props.get("osm_highway") or props.get("subtype") or "").lower()
    surface    = (props.get("surface") or "").lower()

    # Surface material override
    surface_map = {
        "asphalt":   "minecraft:gray_concrete",
        "concrete":  "minecraft:light_gray_concrete",
        "paving_stones": "minecraft:stone_bricks",
        "gravel":    "minecraft:gravel",
        "dirt":      "minecraft:dirt",
        "grass":     "minecraft:grass_block",
        "wood":      "minecraft:oak_planks",
    }
    for surf_key, block in surface_map.items():
        if surf_key in surface:
            return block

    # Bike class override
    if bike_class:
        return PALETTE_ROAD.get(bike_class, PALETTE_ROAD["class_i"])

    return PALETTE_ROAD.get(highway, PALETTE_ROAD["default"])


# ─────────────────────────────────────────────────────────────────────────────
# Block generation functions
# ─────────────────────────────────────────────────────────────────────────────

def rasterise_polygon(mc_coords: list) -> list:
    """
    Convert a polygon (list of (x,z) pairs) to a list of (x,z) interior points
    using scanline rasterisation.

    This is the core algorithm that fills building footprints and landuse areas
    with blocks. Pure Python — no numpy required.
    """
    if len(mc_coords) < 3:
        return []

    # Find bounding box
    xs = [c[0] for c in mc_coords]
    zs = [c[1] for c in mc_coords]
    min_x, max_x = min(xs), max(xs)
    min_z, max_z = min(zs), max(zs)

    # Guard against huge polygons (safety limit for POC)
    if (max_x - min_x) > 2000 or (max_z - min_z) > 2000:
        log.warning("    Polygon too large (%d×%d) — skipping rasterisation",
                    max_x-min_x, max_z-min_z)
        return []

    points = []
    n = len(mc_coords)

    for z in range(min_z, max_z + 1):
        intersections = []
        for i in range(n):
            j = (i + 1) % n
            xi, zi = mc_coords[i]
            xj, zj = mc_coords[j]
            if (zi <= z < zj) or (zj <= z < zi):
                # Compute x intersection
                t = (z - zi) / (zj - zi)
                x_int = xi + t * (xj - xi)
                intersections.append(x_int)
        intersections.sort()
        for k in range(0, len(intersections) - 1, 2):
            x_start = int(math.ceil(intersections[k]))
            x_end   = int(math.floor(intersections[k+1]))
            for x in range(x_start, x_end + 1):
                points.append((x, z))

    return points


def rasterise_linestring(mc_coords: list, width: int = 1) -> list:
    """
    Convert a linestring to a list of (x,z) points using Bresenham's algorithm.
    Width > 1 adds perpendicular offset blocks for roads.
    """
    if len(mc_coords) < 2:
        return []

    points = set()
    for i in range(len(mc_coords) - 1):
        x0, z0 = mc_coords[i]
        x1, z1 = mc_coords[i + 1]

        # Bresenham's line
        dx = abs(x1 - x0)
        dz = abs(z1 - z0)
        sx = 1 if x0 < x1 else -1
        sz = 1 if z0 < z1 else -1
        err = dx - dz
        cx, cz = x0, z0

        while True:
            # Square brush — fill block_range x block_range square at each centerline point
            # This matches Arnis behavior and eliminates jagged diagonal road edges
            half = width // 2
            for bx in range(-half, half + 1):
                for bz in range(-half, half + 1):
                    points.add((cx + bx, cz + bz))
            if cx == x1 and cz == z1:
                break
            e2 = 2 * err
            if e2 > -dz:
                err -= dz
                cx  += sx
            if e2 < dx:
                err += dx
                cz  += sz

    return list(points)


def generate_building_blocks(elem: dict, elev: ElevationLookup) -> list:
    """
    Generate all blocks for a single building element.
    Produces: floor, walls (perimeter), and roof.
    Interior is left as air (BUILDING_FILL_BLOCK).
    """
    mc_coords = elem.get("mc_coords", [])
    if len(mc_coords) < 3:
        return []

    # Convert to list of (x,z) tuples
    coords = [(c[0], c[1]) for c in mc_coords]

    # Get ground Y at building centroid
    centroid = elem.get("mc_centroid", (0, 0))
    if isinstance(centroid, (list, tuple)) and len(centroid) >= 2:
        ground_y = elev.get_y(centroid[0], centroid[1])
    else:
        ground_y = DEFAULT_GROUND_Y

    # Resolve palette
    props = {
        **elem,
        **{f"osm_{k}": v for k, v in elem.get("tags", {}).items()}
    }
    wall_block, roof_block, height = resolve_building_palette(props)
    height = max(3, min(height, 50))  # clamp 3–50 blocks

    blocks = []

    # Get all interior + perimeter points
    footprint = rasterise_polygon(coords)
    if not footprint:
        return []

    # Get perimeter points (edge of polygon)
    perimeter = set()
    n = len(coords)
    for i in range(n):
        seg = rasterise_linestring([coords[i], coords[(i+1) % n]], width=1)
        for pt in seg:
            perimeter.add(pt)

    for x, z in footprint:
        # No separate floor block — terrain layer provides the ground surface.
        # Building priority (4) ensures walls overwrite any terrain at ground_y.
        is_wall = (x, z) in perimeter

        if is_wall:
            # Wall — full height
            for dy in range(1, height + 1):
                blocks.append({"x": x, "y": ground_y + dy, "z": z,
                               "block": wall_block, "layer": LAYER_BUILDING})
        else:
            # Interior — air columns (clear any terrain that poked through)
            for dy in range(1, height):
                blocks.append({"x": x, "y": ground_y + dy, "z": z,
                               "block": BUILDING_FILL_BLOCK, "layer": LAYER_BUILDING})

    # Roof layer (top of building)
    for x, z in footprint:
        blocks.append({"x": x, "y": ground_y + height + 1, "z": z,
                       "block": roof_block, "layer": LAYER_BUILDING})

    return blocks


def generate_road_blocks(elem: dict, elev: ElevationLookup) -> list:
    """Generate surface blocks for a road or path."""
    mc_coords = elem.get("mc_coords", [])
    if len(mc_coords) < 2:
        return []

    coords      = [(c[0], c[1]) for c in mc_coords]
    road_block  = resolve_road_block(elem)
    is_bike     = elem.get("is_bike_path", False)
    bike_class  = elem.get("bike_class")
    subtype     = (elem.get("subtype") or elem.get("osm_highway") or "").lower()

    # Width by road type (ADR-001: 1m = 1 block)
    # Primary roads ~7m = 3 blocks each direction, but we use 1-side width
    ROAD_WIDTHS = {
        "motorway":    3, "trunk":      3, "primary":     3,
        "secondary":   2, "tertiary":   2, "residential": 2,
        "unclassified":2, "service":    1, "living_street":1,
        "pedestrian":  2, "footway":    1, "path":        1,
        "cycleway":    2, "class_i":    2, "class_ii":    1, "class_iii":   1,
    }
    width = ROAD_WIDTHS.get(subtype, 2)
    width = max(1, elem.get("width_blocks", width))

    points = rasterise_linestring(coords, width=width)
    if not points:
        return []

    blocks = []
    for x, z in points:
        y = elev.get_y(x, z)
        blocks.append({"x": x, "y": y, "z": z,
                       "block": road_block, "layer": LAYER_ROAD})

    # Class I bike paths get white edge stripes
    if is_bike and bike_class == "class_i" and width >= 3:
        edge_points = rasterise_linestring(coords, width=1)
        for x, z in edge_points:
            y = elev.get_y(x, z)
            # Left edge
            blocks.append({"x": x - (width//2), "y": y, "z": z,
                           "block": BIKE_PATH_EDGE_BLOCK, "layer": LAYER_ROAD})
            # Right edge
            blocks.append({"x": x + (width//2), "y": y, "z": z,
                           "block": BIKE_PATH_EDGE_BLOCK, "layer": LAYER_ROAD})

    return blocks


def generate_railway_blocks(elem: dict, elev: ElevationLookup) -> list:
    """Generate blocks for railway tracks, platforms, and stations."""
    mc_coords = elem.get("mc_coords", [])
    subtype   = (elem.get("subtype") or elem.get("osm_railway") or "rail").lower()
    geom_type = elem.get("geometry", "linestring")

    # Platforms and stations are polygons
    if subtype in ("platform", "station") and geom_type == "polygon" and len(mc_coords) >= 3:
        coords = [(c[0], c[1]) for c in mc_coords]
        surface_block = PALETTE_RAILWAY.get(subtype, PALETTE_RAILWAY["default"])
        points = rasterise_polygon(coords)
        blocks = []
        for x, z in points:
            y = elev.get_y(x, z)
            blocks.append({"x": x, "y": y, "z": z,
                           "block": surface_block, "layer": LAYER_RAILWAY})
        return blocks

    # Track types — linestring with gravel bed + sleepers + rails
    if len(mc_coords) < 2:
        return []

    coords     = [(c[0], c[1]) for c in mc_coords]
    rail_block = PALETTE_RAILWAY.get(subtype, PALETTE_RAILWAY["default"])

    # Gravel ballast bed (3 blocks wide)
    ballast_points = rasterise_linestring(coords, width=3)
    # Rail lines (1 block wide centre)
    rail_points    = rasterise_linestring(coords, width=1)

    blocks = []

    # Layer 1: Gravel bed
    for x, z in ballast_points:
        y = elev.get_y(x, z)
        blocks.append({"x": x, "y": y, "z": z,
                       "block": RAILWAY_BALLAST_BLOCK, "layer": LAYER_RAILWAY})

    # Layer 2: Rails on top of gravel (same Y)
    for x, z in rail_points:
        y = elev.get_y(x, z)
        blocks.append({"x": x, "y": y, "z": z,
                       "block": rail_block, "layer": LAYER_RAILWAY})

    return blocks


def generate_terrain_blocks(elem: dict, elev: ElevationLookup) -> list:
    """Generate ground surface blocks for landuse and natural areas."""
    mc_coords = elem.get("mc_coords", [])
    geom_type = elem.get("geometry", "polygon")

    if geom_type != "polygon" or len(mc_coords) < 3:
        return []

    coords = [(c[0], c[1]) for c in mc_coords]
    subtype = (elem.get("subtype") or elem.get("osm_landuse") or
               elem.get("osm_natural") or elem.get("osm_leisure") or "").lower()
    surface_block = PALETTE_TERRAIN.get(subtype, PALETTE_TERRAIN["default"])

    points = rasterise_polygon(coords)
    if not points:
        return []

    blocks = []
    for x, z in points:
        y = elev.get_y(x, z)
        blocks.append({"x": x, "y": y, "z": z,
                       "block": surface_block, "layer": LAYER_TERRAIN})

    return blocks


def generate_water_blocks(elem: dict, elev: ElevationLookup) -> list:
    """Generate water blocks for waterways."""
    mc_coords = elem.get("mc_coords", [])
    geom_type = elem.get("geometry", "linestring")
    subtype   = elem.get("subtype", elem.get("osm_waterway", "stream"))

    # Is this a canal (Arboretum) — gets cement banks
    is_canal = "canal" in subtype or "arboretum" in elem.get("name", "").lower()
    bank_block = WATERWAY_BANK_BLOCK if is_canal else WATERWAY_EARTH_BLOCK
    water_block = PALETTE_WATER.get(subtype, PALETTE_WATER["default"])

    if geom_type == "polygon":
        coords = [(c[0], c[1]) for c in mc_coords]
        points = rasterise_polygon(coords)
    else:
        coords = [(c[0], c[1]) for c in mc_coords]
        points = rasterise_linestring(coords, width=3)

    if not points:
        return []

    blocks = []
    for x, z in points:
        y = WATER_Y
        blocks.append({"x": x, "y": y,     "z": z,
                       "block": water_block,  "layer": LAYER_WATER})
        blocks.append({"x": x, "y": y - 1, "z": z,
                       "block": bank_block,   "layer": LAYER_WATER})

    return blocks


def generate_amenity_blocks(elem: dict, elev: ElevationLookup) -> list:
    """Generate a single block for a point amenity."""
    mc_x = elem.get("mc_x", 0)
    mc_z = elem.get("mc_z", 0)
    subtype = (elem.get("subtype") or elem.get("osm_amenity") or "").lower()
    block = PALETTE_AMENITY.get(subtype, PALETTE_AMENITY["default"])
    y = elev.get_y(mc_x, mc_z) + 1  # place on top of ground
    return [{"x": mc_x, "y": y, "z": mc_z,
             "block": block, "layer": LAYER_OBJECT}]


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_transform(
    fused_path:  str,
    output_dir:  str,
    dem_path:    Optional[str] = None,
) -> dict:
    """
    Run the full transform stage.

    Args:
        fused_path:  Path to fused_features.geojson from Stage 4
        output_dir:  Directory to write blocks.json
        dem_path:    Optional path to davis_dem_1m.tif from Stage 2

    Returns:
        Transform result dict with output paths and statistics
    """
    start = time.time()
    out   = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("  BuildDavis — Stage 5: Transform")
    log.info("=" * 60)

    # ── Load DEM ──────────────────────────────────────────────────────────────
    log.info("[1/4] Loading elevation model...")
    dem_p = Path(dem_path) if dem_path else out / "davis_dem_1m.tif"
    elev  = ElevationLookup(dem_p if dem_p.exists() else None)

    # ── Load fused features ───────────────────────────────────────────────────
    log.info("[2/4] Loading fused features...")
    with open(fused_path) as f:
        geojson = json.load(f)
    features = geojson.get("features", [])
    log.info("  %d features loaded", len(features))

    # ── Generate blocks ───────────────────────────────────────────────────────
    log.info("[3/4] Generating blocks...")
    all_blocks   = []
    stats        = {
        "terrain":  0, "road": 0,
        "building": 0, "water": 0,
        "object":   0, "skipped": 0,
        "base":     0,
    }

    # ── Base terrain pass: fill entire bbox with grass at Y=47 ───────────────
    # This covers all areas with no OSM data, preventing exposed stone fill walls.
    # Higher priority layers (roads, buildings) will overwrite this base layer.
    # We need to know the bbox first — compute from features.
    all_mc_coords = []
    for feat in features:
        props = feat.get("properties", {}) or {}
        mc_x = props.get("mc_x")
        mc_z = props.get("mc_z")
        if mc_x is not None and mc_z is not None:
            all_mc_coords.append((int(mc_x), int(mc_z)))
        mc_coords_json = props.get("mc_coords_json", "")
        if mc_coords_json:
            try:
                raw = json.loads(mc_coords_json)
                for c in raw:
                    if len(c) >= 2:
                        all_mc_coords.append((int(c[0]), int(c[1])))
            except Exception:
                pass

    if all_mc_coords:
        base_min_x = min(c[0] for c in all_mc_coords) - 8
        base_max_x = max(c[0] for c in all_mc_coords) + 8
        base_min_z = min(c[1] for c in all_mc_coords) - 8
        base_max_z = max(c[1] for c in all_mc_coords) + 8
        base_y = DEFAULT_GROUND_Y  # Y=47

        log.info("  Base terrain fill: %dx%d blocks at Y=%d",
                 base_max_x - base_min_x, base_max_z - base_min_z, base_y)

        base_count = 0
        for x in range(base_min_x, base_max_x + 1):
            for z in range(base_min_z, base_max_z + 1):
                all_blocks.append({"x": x, "y": base_y, "z": z,
                                   "block": "minecraft:grass_block",
                                   "layer": LAYER_TERRAIN,
                                   "priority": -1})  # lowest priority
                base_count += 1
        stats["base"] = base_count
        log.info("  Base terrain: %d blocks", base_count)

    for i, feat in enumerate(features):
        props    = feat.get("properties", {}) or {}
        elem_type = props.get("type", "")
        geom_type = props.get("geometry", "")
        mc_coords = []  # reconstruct from GeoJSON geometry

        # Recover mc_coords from the compact JSON string stored by fuse.py
        mc_coords = []
        mc_coords_json = props.get("mc_coords_json", "")
        if mc_coords_json:
            try:
                raw = json.loads(mc_coords_json)
                # raw is list of [x, z] pairs
                mc_coords = [(int(c[0]), int(c[1])) for c in raw if len(c) >= 2]
            except Exception:
                pass

        # Fallback: reconstruct from mc_bbox if mc_coords_json missing
        if not mc_coords:
            geom = feat.get("geometry", {})
            if geom.get("type") == "Polygon":
                min_x = props.get("min_x", props.get("mc_x", 0))
                max_x = props.get("max_x", props.get("mc_x", 0))
                min_z = props.get("min_z", props.get("mc_z", 0))
                max_z = props.get("max_z", props.get("mc_z", 0))
                mc_coords = [
                    (min_x, min_z), (max_x, min_z),
                    (max_x, max_z), (min_x, max_z),
                    (min_x, min_z)
                ]
            else:
                mc_x = props.get("mc_x", 0)
                mc_z = props.get("mc_z", 0)
                mc_coords = [(mc_x, mc_z)]

        # Attach mc_coords back to props for block generators
        elem = {**props, "mc_coords": mc_coords,
                "mc_centroid": (props.get("mc_x", 0), props.get("mc_z", 0))}

        new_blocks = []

        if elem_type == "building":
            new_blocks = generate_building_blocks(elem, elev)
            stats["building"] += len(new_blocks)

        elif elem_type == "highway":
            new_blocks = generate_road_blocks(elem, elev)
            stats["road"] += len(new_blocks)

        elif elem_type in ("landuse", "leisure", "natural"):
            new_blocks = generate_terrain_blocks(elem, elev)
            stats["terrain"] += len(new_blocks)

        elif elem_type == "waterway":
            new_blocks = generate_water_blocks(elem, elev)
            stats["water"] += len(new_blocks)

        elif elem_type == "amenity":
            new_blocks = generate_amenity_blocks(elem, elev)
            stats["object"] += len(new_blocks)

        elif elem_type == "railway":
            new_blocks = generate_railway_blocks(elem, elev)
            stats["railway"] = stats.get("railway", 0) + len(new_blocks)

        else:
            stats["skipped"] += 1

        # Tag each block with its layer priority for dedup
        # terrain=0, water=1, road=2, object=3, building=4
        LAYER_PRIORITY = {"terrain": 0, "water": 1, "road": 2, "object": 3, "building": 4}
        for b in new_blocks:
            b["priority"] = LAYER_PRIORITY.get(b.get("layer", "terrain"), 0)
        all_blocks.extend(new_blocks)

    total_blocks = len(all_blocks)
    log.info("  Total blocks generated: %d", total_blocks)
    for layer, count in stats.items():
        if count > 0:
            log.info("    %-12s %d", layer + ":", count)

    # ── Deduplicate — highest priority layer wins per position ──────────────
    log.info("[4/4] Deduplicating %d blocks...", total_blocks)
    block_map = {}
    for b in all_blocks:
        key = (b["x"], b["y"], b["z"])
        existing = block_map.get(key)
        if existing is None or b.get("priority", 0) >= existing.get("priority", 0):
            block_map[key] = b

    deduped = list(block_map.values())
    log.info("  After dedup: %d unique block positions", len(deduped))

    # ── Ground fill: minimal 5-block foundation below every surface block ────
    # Design (ADR-001):
    #   Y=surface-1: dirt (visual transition)
    #   Y=0:         bedrock (indestructible floor)
    #   Y=1 to Y=4:  stone (builder can excavate without falling through)
    #   Y=5 to Y=46: air (untouched — keeps blocks.json lean)
    #
    # At full Davis scale this is moved into place.exe using fill_column_absolute()
    # so it never bloats blocks.json. For the POC this inline version is fine.
    FILL_DEPTH   = 15  # blocks below surface: bedrock at Y=0, stone Y=1-Y=14

    log.info("  Adding ground fill (depth=%d, full bbox)...", FILL_DEPTH)

    # Compute bbox from all placed blocks
    all_x = [b["x"] for b in deduped]
    all_z = [b["z"] for b in deduped]
    bbox_min_x, bbox_max_x = min(all_x), max(all_x)
    bbox_min_z, bbox_max_z = min(all_z), max(all_z)

    # Fill EVERY (x,z) in the bbox — not just under placed blocks.
    # This closes holes at road intersections and diagonal gaps.
    fill_blocks = []
    for x in range(bbox_min_x, bbox_max_x + 1):
        for z in range(bbox_min_z, bbox_max_z + 1):
            # Bedrock at Y=0
            fill_blocks.append({"x": x, "y": 0, "z": z,
                                "block": "minecraft:bedrock", "layer": "ground",
                                "priority": -2})
            # Stone Y=1 to Y=14
            for y in range(1, FILL_DEPTH):
                fill_blocks.append({"x": x, "y": y, "z": z,
                                   "block": "minecraft:stone", "layer": "ground",
                                   "priority": -1})

    deduped = deduped + fill_blocks
    log.info("  Ground fill: %d blocks added (%dx%d bbox)",
             len(fill_blocks),
             bbox_max_x - bbox_min_x + 1,
             bbox_max_z - bbox_min_z + 1)

    # ── Write blocks.json ─────────────────────────────────────────────────────
    blocks_path = out / "blocks.json"
    with open(blocks_path, "w") as f:
        json.dump(deduped, f, separators=(",", ":"))  # compact — can be large

    elapsed = time.time() - start

    result = {
        "stage":           "transform",
        "blocks_path":     str(blocks_path),
        "total_blocks":    len(deduped),
        "stats":           stats,
        "dem_used":        dem_p.exists() if dem_p else False,
        "elapsed_seconds": round(elapsed, 1)
    }

    manifest_path = out / "transform_manifest.json"
    manifest_path.write_text(json.dumps(result, indent=2))

    log.info("")
    log.info("=" * 60)
    log.info("  Stage 5 complete in %.1fs", elapsed)
    log.info("  Output:  %s", blocks_path)
    log.info("  Blocks:  %d unique positions", len(deduped))
    log.info("=" * 60)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="BuildDavis Pipeline — Stage 5: Transform"
    )
    parser.add_argument(
        "--fused", required=True,
        help="Path to fused_features.geojson from Stage 4"
    )
    parser.add_argument(
        "--output", default="./data",
        help="Output directory (default: ./data)"
    )
    parser.add_argument(
        "--dem",
        help="Path to davis_dem_1m.tif from Stage 2 (optional)"
    )
    args = parser.parse_args()
    run_transform(args.fused, args.output, args.dem)


if __name__ == "__main__":
    main()
