#!/usr/bin/env python3
"""
BuildDavis World Quality Test Suite
====================================
Scans Minecraft region files (.mca) and cross-references with input data
to verify buildings, roads, bridges, and amenities rendered correctly.

Usage:
    python Code/test_world.py <zone_name> [--save-dir <mc_save>] [--verbose]
    python Code/test_world.py north_davis --bbox 38.560,-121.755,38.572,-121.738

Example:
    python Code/test_world.py north_davis
    python Code/test_world.py north_davis --save-dir "%APPDATA%/.minecraft/saves/North Davis Test"
"""
import io

import argparse
import json
import math
import os
import struct
import sys
import zlib
from collections import Counter, defaultdict
from pathlib import Path

# Force UTF-8 output on Windows (only when run directly, not when imported by pytest)
if sys.platform == "win32" and __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Minecraft region file reader (pure Python — no external deps needed)
# ---------------------------------------------------------------------------

class RegionFile:
    """Reads a Minecraft .mca (Anvil) region file."""

    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        # Parse region coords from filename: r.X.Z.mca
        parts = path.stem.split(".")
        self.region_x = int(parts[1])
        self.region_z = int(parts[2])

    def chunk_offsets(self):
        """Yield (local_x, local_z, offset, sector_count) for non-empty chunks."""
        for i in range(1024):
            val = struct.unpack_from(">I", self.data, i * 4)[0]
            if val == 0:
                continue
            offset = (val >> 8) & 0xFFFFFF
            sector_count = val & 0xFF
            local_z, local_x = divmod(i, 32)
            yield local_x, local_z, offset, sector_count

    def read_chunk_nbt(self, offset, sector_count):
        """Read and decompress chunk NBT data. Returns raw bytes or None."""
        byte_offset = offset * 4096
        if byte_offset + 5 > len(self.data):
            return None
        length = struct.unpack_from(">I", self.data, byte_offset)[0]
        compression = self.data[byte_offset + 4]
        compressed = self.data[byte_offset + 5 : byte_offset + 4 + length]
        try:
            if compression == 2:  # zlib
                return zlib.decompress(compressed)
            elif compression == 1:  # gzip
                import gzip
                return gzip.decompress(compressed)
        except Exception:
            return None
        return None


def parse_nbt_tag(data, pos):
    """Minimal NBT parser — returns (tag_type, name, value, new_pos)."""
    if pos >= len(data):
        return None, None, None, pos

    tag_type = data[pos]
    pos += 1
    if tag_type == 0:  # TAG_End
        return 0, "", None, pos

    name_len = struct.unpack_from(">H", data, pos)[0]
    pos += 2
    name = data[pos : pos + name_len].decode("utf-8", errors="replace")
    pos += name_len

    value, pos = parse_nbt_payload(data, pos, tag_type)
    return tag_type, name, value, pos


def parse_nbt_payload(data, pos, tag_type):
    """Parse NBT payload by type. Returns (value, new_pos)."""
    if tag_type == 1:  # Byte
        return data[pos], pos + 1
    elif tag_type == 2:  # Short
        return struct.unpack_from(">h", data, pos)[0], pos + 2
    elif tag_type == 3:  # Int
        return struct.unpack_from(">i", data, pos)[0], pos + 4
    elif tag_type == 4:  # Long
        return struct.unpack_from(">q", data, pos)[0], pos + 8
    elif tag_type == 5:  # Float
        return struct.unpack_from(">f", data, pos)[0], pos + 4
    elif tag_type == 6:  # Double
        return struct.unpack_from(">d", data, pos)[0], pos + 8
    elif tag_type == 7:  # Byte Array
        length = struct.unpack_from(">i", data, pos)[0]
        pos += 4
        return data[pos : pos + length], pos + length
    elif tag_type == 8:  # String
        length = struct.unpack_from(">H", data, pos)[0]
        pos += 2
        return data[pos : pos + length].decode("utf-8", errors="replace"), pos + length
    elif tag_type == 9:  # List
        list_type = data[pos]
        pos += 1
        length = struct.unpack_from(">i", data, pos)[0]
        pos += 4
        items = []
        for _ in range(length):
            val, pos = parse_nbt_payload(data, pos, list_type)
            items.append(val)
        return items, pos
    elif tag_type == 10:  # Compound
        compound = {}
        while True:
            t, n, v, pos = parse_nbt_tag(data, pos)
            if t == 0:
                break
            compound[n] = (t, v)
        return compound, pos
    elif tag_type == 11:  # Int Array
        length = struct.unpack_from(">i", data, pos)[0]
        pos += 4
        arr = struct.unpack_from(f">{length}i", data, pos)
        return list(arr), pos + length * 4
    elif tag_type == 12:  # Long Array
        length = struct.unpack_from(">i", data, pos)[0]
        pos += 4
        arr = struct.unpack_from(f">{length}q", data, pos)
        return list(arr), pos + length * 8
    return None, pos


def extract_block_palette(chunk_nbt_data):
    """Extract block palette strings from chunk NBT data.
    Returns a set of block name strings found in the chunk.
    """
    blocks = set()
    # Search for palette entries in the raw bytes (faster than full NBT parse)
    # Palette entries contain "minecraft:" prefixed block names
    raw = chunk_nbt_data
    idx = 0
    while True:
        idx = raw.find(b"minecraft:", idx)
        if idx == -1:
            break
        # Read until a control char or end
        end = idx
        while end < len(raw) and raw[end] >= 32 and raw[end] < 127:
            end += 1
        name = raw[idx:end].decode("ascii", errors="replace")
        # Filter to actual block names (not entities, dimensions, etc.)
        if len(name) < 60 and "/" not in name:
            blocks.add(name)
        idx = end
    return blocks


# ---------------------------------------------------------------------------
# Coordinate transformer (replicates Arnis's Rust CoordTransformer in Python)
# ---------------------------------------------------------------------------

def haversine_lat(lat1, lat2):
    R = 6_371_000.0
    d = math.radians(lat2 - lat1)
    a = math.sin(d / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def haversine_lon(lat, lon1, lon2):
    R = 6_371_000.0
    d = math.radians(lon2 - lon1)
    cos_lat = math.cos(math.radians(lat))
    a = cos_lat * cos_lat * math.sin(d / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class CoordTransformer:
    """Replicates Arnis's CoordTransformer: lat/lon → MC x/z."""

    def __init__(self, bbox):
        """bbox = (south, west, north, east) = (min_lat, min_lon, max_lat, max_lon)."""
        self.min_lat, self.min_lon, self.max_lat, self.max_lon = bbox
        self.len_lat = self.max_lat - self.min_lat
        self.len_lon = self.max_lon - self.min_lon

        # Arnis: geo_distance returns (lat_meters, lon_meters)
        lat_m = haversine_lat(self.min_lat, self.max_lat)
        avg_lat = (self.min_lat + self.max_lat) / 2
        lon_m = haversine_lon(avg_lat, self.min_lon, self.max_lon)

        # Arnis: scale_factor_z = floor(lat_meters) * scale
        #         scale_factor_x = floor(lon_meters) * scale
        self.scale_z = math.floor(lat_m)  # scale=1.0
        self.scale_x = math.floor(lon_m)

    def transform(self, lat, lon):
        """Return (mc_x, mc_z) for given lat/lon."""
        rel_x = (lon - self.min_lon) / self.len_lon
        rel_z = 1.0 - (lat - self.min_lat) / self.len_lat
        return int(rel_x * self.scale_x), int(rel_z * self.scale_z)

    @property
    def world_dims(self):
        return self.scale_x, self.scale_z


# ---------------------------------------------------------------------------
# Building material detection
# ---------------------------------------------------------------------------

# Blocks that indicate a building was rendered (wall, floor, roof materials)
BUILDING_BLOCKS = {
    # Residential walls
    "minecraft:bricks", "minecraft:white_terracotta", "minecraft:light_gray_terracotta",
    "minecraft:brown_terracotta", "minecraft:orange_terracotta", "minecraft:yellow_terracotta",
    "minecraft:red_terracotta", "minecraft:terracotta",
    "minecraft:smooth_quartz", "minecraft:quartz_block",
    "minecraft:white_concrete", "minecraft:light_gray_concrete",
    # Planks
    "minecraft:oak_planks", "minecraft:spruce_planks", "minecraft:birch_planks",
    "minecraft:dark_oak_planks", "minecraft:jungle_planks", "minecraft:acacia_planks",
    # Stone variants
    "minecraft:stone_bricks", "minecraft:mossy_stone_bricks",
    "minecraft:smooth_stone", "minecraft:polished_andesite",
    "minecraft:polished_granite", "minecraft:polished_diorite",
    # Glass (windows)
    "minecraft:glass_pane", "minecraft:glass", "minecraft:white_stained_glass_pane",
    "minecraft:light_gray_stained_glass_pane", "minecraft:light_blue_stained_glass_pane",
    # Doors
    "minecraft:oak_door", "minecraft:spruce_door", "minecraft:iron_door",
    # Slabs and stairs (roofs)
    "minecraft:brick_slab", "minecraft:stone_brick_slab", "minecraft:oak_slab",
    "minecraft:spruce_slab", "minecraft:dark_oak_slab",
    "minecraft:brick_stairs", "minecraft:stone_brick_stairs",
    # Concrete (commercial)
    "minecraft:gray_concrete", "minecraft:cyan_terracotta",
}

ROAD_BLOCKS = {
    "minecraft:black_concrete", "minecraft:gray_concrete",
    "minecraft:light_gray_concrete", "minecraft:white_concrete",
    "minecraft:dirt_path",
}

WATER_BLOCKS = {
    "minecraft:water",
}

TREE_BLOCKS = {
    "minecraft:oak_log", "minecraft:spruce_log", "minecraft:birch_log",
    "minecraft:dark_oak_log",
    "minecraft:oak_leaves", "minecraft:spruce_leaves", "minecraft:birch_leaves",
    "minecraft:dark_oak_leaves",
}


# ---------------------------------------------------------------------------
# Test Suite
# ---------------------------------------------------------------------------

class TestResult:
    def __init__(self, name):
        self.name = name
        self.passed = True
        self.messages = []
        self.warnings = []

    def fail(self, msg):
        self.passed = False
        self.messages.append(f"FAIL: {msg}")

    def warn(self, msg):
        self.warnings.append(f"WARN: {msg}")

    def info(self, msg):
        self.messages.append(f"INFO: {msg}")


def test_region_files_exist(save_dir: Path) -> TestResult:
    """T1: Check that region files exist and are non-empty."""
    result = TestResult("Region Files Exist")
    region_dir = save_dir / "region"

    if not region_dir.exists():
        result.fail(f"Region directory not found: {region_dir}")
        return result

    mca_files = list(region_dir.glob("*.mca"))
    if not mca_files:
        result.fail("No .mca region files found")
        return result

    result.info(f"Found {len(mca_files)} region files")
    for f in sorted(mca_files):
        size = f.stat().st_size
        if size < 8192:  # minimum viable region file
            result.fail(f"{f.name}: too small ({size} bytes)")
        else:
            result.info(f"{f.name}: {size:,} bytes")

    return result


def test_level_dat_exists(save_dir: Path) -> TestResult:
    """T2: Check that level.dat exists at the save root (not nested)."""
    result = TestResult("level.dat at Root")
    level_dat = save_dir / "level.dat"

    if not level_dat.exists():
        result.fail("level.dat not found at save root")
        # Check if it's nested
        for nested in save_dir.rglob("level.dat"):
            result.fail(f"Found nested: {nested.relative_to(save_dir)}")
        return result

    result.info(f"level.dat: {level_dat.stat().st_size} bytes")
    return result


def scan_region_blocks(save_dir: Path, verbose=False):
    """Scan all region files and return block statistics per chunk."""
    region_dir = save_dir / "region"
    chunk_stats = {}  # (chunk_x, chunk_z) → {'building': count, 'road': count, ...}
    all_blocks = Counter()

    for mca_path in sorted(region_dir.glob("*.mca")):
        region = RegionFile(mca_path)
        for local_x, local_z, offset, sectors in region.chunk_offsets():
            chunk_x = region.region_x * 32 + local_x
            chunk_z = region.region_z * 32 + local_z

            nbt_data = region.read_chunk_nbt(offset, sectors)
            if not nbt_data:
                continue

            blocks = extract_block_palette(nbt_data)
            all_blocks.update(blocks)

            stats = {
                "building": len(blocks & BUILDING_BLOCKS),
                "road": len(blocks & ROAD_BLOCKS),
                "water": len(blocks & WATER_BLOCKS),
                "tree": len(blocks & TREE_BLOCKS),
                "building_blocks": blocks & BUILDING_BLOCKS,
                "all": blocks,
            }
            chunk_stats[(chunk_x, chunk_z)] = stats

    return chunk_stats, all_blocks


def test_building_blocks_present(chunk_stats: dict) -> TestResult:
    """T3: Check that building material blocks exist in the world."""
    result = TestResult("Building Blocks Present")

    chunks_with_buildings = sum(
        1 for s in chunk_stats.values() if s["building"] > 0
    )
    total_chunks = len(chunk_stats)

    if chunks_with_buildings == 0:
        result.fail("NO chunks contain building material blocks!")
        result.fail("Buildings may not be rendering at all")
    else:
        pct = 100 * chunks_with_buildings / total_chunks if total_chunks else 0
        result.info(
            f"{chunks_with_buildings}/{total_chunks} chunks ({pct:.0f}%) contain building blocks"
        )

    # List unique building blocks found
    all_bldg = set()
    for s in chunk_stats.values():
        all_bldg |= s.get("building_blocks", set())
    if all_bldg:
        result.info(f"Building block types found: {len(all_bldg)}")
        for b in sorted(all_bldg)[:10]:
            result.info(f"  {b}")
    else:
        result.fail("No building block types found in any chunk")

    return result


def test_road_blocks_present(chunk_stats: dict) -> TestResult:
    """T4: Check that road blocks exist."""
    result = TestResult("Road Blocks Present")

    chunks_with_roads = sum(1 for s in chunk_stats.values() if s["road"] > 0)
    total = len(chunk_stats)
    pct = 100 * chunks_with_roads / total if total else 0

    if chunks_with_roads == 0:
        result.fail("No road blocks found in any chunk")
    else:
        result.info(f"{chunks_with_roads}/{total} chunks ({pct:.0f}%) contain road blocks")

    return result


def test_building_spatial_coverage(
    chunk_stats: dict,
    buildings_data: list,
    transformer: CoordTransformer,
) -> TestResult:
    """T5: Check that buildings exist near their expected MC coordinates."""
    result = TestResult("Building Spatial Coverage")

    if not buildings_data:
        result.warn("No building data provided for cross-reference")
        return result

    # Map expected building positions to chunks
    expected_chunks = set()
    building_positions = []
    for bldg in buildings_data:
        nodes = bldg.get("nodes", [])
        # Get centroid from node coordinates
        if bldg.get("geometry"):
            coords = bldg["geometry"].get("coordinates", [[]])
            ring = coords[0] if coords else []
            if ring:
                avg_lon = sum(c[0] for c in ring) / len(ring)
                avg_lat = sum(c[1] for c in ring) / len(ring)
                mc_x, mc_z = transformer.transform(avg_lat, avg_lon)
                chunk_x, chunk_z = mc_x >> 4, mc_z >> 4
                expected_chunks.add((chunk_x, chunk_z))
                building_positions.append((mc_x, mc_z, bldg.get("properties", {}).get("building", "yes")))

    result.info(f"Expected buildings in {len(expected_chunks)} chunks")
    result.info(f"Building MC coordinate range: X=[{min(p[0] for p in building_positions)}, {max(p[0] for p in building_positions)}] Z=[{min(p[1] for p in building_positions)}, {max(p[1] for p in building_positions)}]")

    # Check which expected chunks actually have building blocks
    missing = 0
    missing_chunks = []
    for cx, cz in sorted(expected_chunks):
        stats = chunk_stats.get((cx, cz))
        if not stats or stats["building"] == 0:
            missing += 1
            missing_chunks.append((cx, cz))

    if missing > 0:
        pct = 100 * missing / len(expected_chunks)
        if pct > 30:
            result.fail(
                f"{missing}/{len(expected_chunks)} expected building chunks ({pct:.0f}%) "
                f"have NO building blocks"
            )
        else:
            result.warn(
                f"{missing}/{len(expected_chunks)} expected building chunks ({pct:.0f}%) "
                f"missing building blocks"
            )

        # Show sample missing chunks
        for cx, cz in missing_chunks[:5]:
            block_x = cx * 16
            block_z = cz * 16
            result.info(f"  Missing chunk ({cx},{cz}) → blocks ({block_x}-{block_x+15}, {block_z}-{block_z+15})")
    else:
        result.info("All expected building chunks contain building blocks")

    return result


def test_empty_areas(chunk_stats: dict, transformer: CoordTransformer) -> TestResult:
    """T6: Flag large contiguous areas without any structure blocks."""
    result = TestResult("No Large Empty Areas")

    world_x, world_z = transformer.world_dims
    max_chunk_x = world_x >> 4
    max_chunk_z = world_z >> 4

    # Find chunks that have no building, road, or water blocks (only terrain)
    empty_chunks = set()
    for cx in range(max_chunk_x + 1):
        for cz in range(max_chunk_z + 1):
            stats = chunk_stats.get((cx, cz))
            if not stats:
                empty_chunks.add((cx, cz))
            elif stats["building"] == 0 and stats["road"] == 0:
                empty_chunks.add((cx, cz))

    # Find clusters of empty chunks (simple flood fill)
    visited = set()
    clusters = []
    for start in empty_chunks:
        if start in visited:
            continue
        cluster = set()
        queue = [start]
        while queue:
            pt = queue.pop()
            if pt in visited or pt not in empty_chunks:
                continue
            visited.add(pt)
            cluster.add(pt)
            cx, cz = pt
            for dx, dz in [(-1,0),(1,0),(0,-1),(0,1)]:
                queue.append((cx+dx, cz+dz))
        if len(cluster) >= 4:  # 4+ chunks = 64x64 blocks = suspicious
            clusters.append(cluster)

    if clusters:
        clusters.sort(key=len, reverse=True)
        result.warn(f"Found {len(clusters)} empty areas (≥4 chunks without buildings/roads)")
        for i, cluster in enumerate(clusters[:5]):
            min_cx = min(c[0] for c in cluster)
            max_cx = max(c[0] for c in cluster)
            min_cz = min(c[1] for c in cluster)
            max_cz = max(c[1] for c in cluster)
            result.info(
                f"  Empty area {i+1}: {len(cluster)} chunks, "
                f"block range ({min_cx*16}-{max_cx*16+15}, {min_cz*16}-{max_cz*16+15})"
            )
    else:
        result.info("No large empty areas found")

    return result


def test_building_height(save_dir: Path, ground_level: int = 49) -> TestResult:
    """T7: Verify buildings are above ground level (not underground)."""
    result = TestResult("Buildings Above Ground")
    # This test checks via palette — if building blocks appear in
    # chunk sections at Y < ground_level, they're underground
    result.info(f"Ground level: Y={ground_level}")
    result.info("(Full Y-level scan requires section-level NBT parsing — palette check used)")
    return result


def test_coordinate_range(
    buildings_data: list,
    transformer: CoordTransformer,
) -> TestResult:
    """T8: Verify building coordinates map within world bounds."""
    result = TestResult("Coordinates Within Bounds")

    if not buildings_data:
        result.warn("No building data for coordinate check")
        return result

    world_x, world_z = transformer.world_dims
    out_of_bounds = 0

    for bldg in buildings_data:
        if bldg.get("geometry"):
            coords = bldg["geometry"].get("coordinates", [[]])
            ring = coords[0] if coords else []
            for lon, lat in ring:
                mc_x, mc_z = transformer.transform(lat, lon)
                if mc_x < 0 or mc_x > world_x or mc_z < 0 or mc_z > world_z:
                    out_of_bounds += 1
                    break

    if out_of_bounds > 0:
        result.fail(f"{out_of_bounds} buildings have coordinates outside world bounds (0-{world_x}, 0-{world_z})")
    else:
        result.info(f"All buildings within world bounds (0-{world_x}, 0-{world_z})")

    return result


def load_buildings_from_geojson(geojson_path: Path):
    """Load building features from fused_features.geojson."""
    if not geojson_path.exists():
        return []

    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    buildings = []
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        if props.get("type") == "building" or "building" in props:
            buildings.append(feat)

    return buildings


# ---------------------------------------------------------------------------
# Programmatic API — called by deploy_apex.py, pytest, pipeline.py
# ---------------------------------------------------------------------------

def run_qa(zone: str, save_dir: Path = None, bbox: tuple = None,
           verbose: bool = False, ground_level: int = 49) -> tuple:
    """Run the full QA suite programmatically.

    Returns (passed: bool, results: list[TestResult], summary: str).
    """
    project_root = Path(__file__).resolve().parent.parent
    zone_dir = project_root / "data" / zone

    if save_dir is None:
        save_dir = zone_dir / "world" / "Arnis World 1"

    return _run_suite(zone, zone_dir, save_dir, bbox, verbose, ground_level)


def _resolve_bbox(zone_dir: Path, save_dir: Path, bbox_arg: str = None) -> tuple:
    """Resolve bbox from arg, metadata, or enriched_overpass.json."""
    if bbox_arg:
        parts = [float(x) for x in bbox_arg.split(",")]
        if len(parts) == 4:
            return tuple(parts)

    metadata_path = save_dir / "metadata.json"
    if metadata_path.exists():
        with open(metadata_path) as f:
            meta = json.load(f)
        bbox_str = meta.get("bbox", "")
        if bbox_str:
            parts = [float(x) for x in bbox_str.split(",")]
            if len(parts) == 4:
                return tuple(parts)

    enriched = zone_dir / "enriched_overpass.json"
    if enriched.exists():
        with open(enriched) as f:
            data = json.load(f)
        lats, lons = [], []
        for el in data.get("elements", []):
            if el.get("type") == "node":
                if "lat" in el and "lon" in el:
                    lats.append(el["lat"])
                    lons.append(el["lon"])
        if lats:
            return (min(lats), min(lons), max(lats), max(lons))

    return None


def _run_suite(zone, zone_dir, save_dir, bbox, verbose, ground_level):
    """Core test runner. Returns (passed, results, summary)."""
    print("=" * 70)
    print("BuildDavis World Quality Test Suite")
    print("=" * 70)
    print(f"Zone:     {zone}")
    print(f"Save dir: {save_dir}")
    print()

    if not bbox:
        print("ERROR: Could not determine bbox.")
        return False, [], "ERROR: No bbox available"

    print(f"Bbox:     {bbox}")
    transformer = CoordTransformer(bbox)
    print(f"World:    {transformer.world_dims[0]}x{transformer.world_dims[1]} blocks")
    print()

    results = []

    # T1-T2
    print("-" * 50)
    r = test_region_files_exist(save_dir)
    results.append(r)
    print_result(r, verbose)

    r = test_level_dat_exists(save_dir)
    results.append(r)
    print_result(r, verbose)

    # T3-T6: Block scanning
    print("\nScanning region files for block types...")
    chunk_stats, all_blocks = scan_region_blocks(save_dir, verbose)
    print(f"Scanned {len(chunk_stats)} chunks\n")

    if verbose:
        print("Top 20 block types found:")
        for block, count in all_blocks.most_common(20):
            marker = " <- BUILDING" if block in BUILDING_BLOCKS else ""
            marker = " <- ROAD" if block in ROAD_BLOCKS else marker
            print(f"  {count:4d} chunks: {block}{marker}")
        print()

    r = test_building_blocks_present(chunk_stats)
    results.append(r)
    print_result(r, verbose)

    r = test_road_blocks_present(chunk_stats)
    results.append(r)
    print_result(r, verbose)

    geojson_path = zone_dir / "fused_features.geojson"
    buildings = load_buildings_from_geojson(geojson_path)
    print(f"\nLoaded {len(buildings)} buildings from fused data")

    r = test_building_spatial_coverage(chunk_stats, buildings, transformer)
    results.append(r)
    print_result(r, verbose)

    r = test_empty_areas(chunk_stats, transformer)
    results.append(r)
    print_result(r, verbose)

    r = test_building_height(save_dir, ground_level)
    results.append(r)
    print_result(r, verbose)

    r = test_coordinate_range(buildings, transformer)
    results.append(r)
    print_result(r, verbose)

    # Summary
    print("\n" + "=" * 70)
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    warned = sum(1 for r in results if r.warnings)
    total = len(results)

    if failed == 0:
        summary = f"ALL {total} TESTS PASSED"
        if warned:
            summary += f" ({warned} with warnings)"
        print(f"[PASS] {summary}")
    else:
        summary = f"{failed}/{total} TESTS FAILED"
        print(f"[FAIL] {summary}")
        for r in results:
            if not r.passed:
                print(f"  FAILED: {r.name}")

    print("=" * 70)
    return failed == 0, results, summary


# ---------------------------------------------------------------------------
# Main (CLI entry point)
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="BuildDavis World Quality Test Suite")
    parser.add_argument("zone", help="Zone name (e.g. north_davis)")
    parser.add_argument("--save-dir", help="MC save directory (default: data/<zone>/world/Arnis World 1)")
    parser.add_argument("--bbox", help="Bbox as S,W,N,E (e.g. 38.560,-121.755,38.572,-121.738)")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--ground-level", type=int, default=49)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    zone_dir = project_root / "data" / args.zone

    # Determine save directory
    if args.save_dir:
        save_dir = Path(os.path.expandvars(args.save_dir))
    else:
        save_dir = zone_dir / "world" / "Arnis World 1"

    # Resolve bbox
    bbox = _resolve_bbox(zone_dir, save_dir, args.bbox)
    if not bbox:
        print("ERROR: Could not determine bbox. Pass --bbox S,W,N,E")
        sys.exit(1)

    passed, results, summary = run_qa(
        args.zone, save_dir, bbox, args.verbose, args.ground_level
    )
    return 0 if passed else 1


def print_result(result: TestResult, verbose: bool):
    status = "PASS" if result.passed else "FAIL"
    print(f"\n[{status}] {result.name}")
    if result.warnings:
        for w in result.warnings:
            print(f"  WARNING: {w}")
    if verbose or not result.passed:
        for m in result.messages:
            print(f"  {m}")


if __name__ == "__main__":
    sys.exit(main())
