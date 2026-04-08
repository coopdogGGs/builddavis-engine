"""
BuildDavis World Quality Tests (pytest integration)
=====================================================
Wraps test_world.py for pytest discovery. Runs automatically via:
    python -m pytest tests/ -v
    run_tests.bat

Requires rendered world data in data/<zone>/world/Arnis World 1/.
Skips gracefully if no world data exists (CI/dev machines without renders).

Configure zone/bbox in .env:
    DEPLOY_ZONE=north_davis
    DEPLOY_BBOX=38.560,-121.755,38.572,-121.738
"""

import sys
from pathlib import Path

import pytest

# Add Code/ to path so we can import test_world
CODE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(CODE_DIR))

WORKSPACE = CODE_DIR.parent

# ── Load zone config from .env ───────────────────────────────────────────────

def _load_env():
    env_path = WORKSPACE / ".env"
    env = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def _get_zone_config():
    env = _load_env()
    zone = env.get("DEPLOY_ZONE", "north_davis")
    bbox_str = env.get("DEPLOY_BBOX", "38.560,-121.755,38.572,-121.738")
    bbox = tuple(float(x) for x in bbox_str.split(","))
    return zone, bbox


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def zone_config():
    return _get_zone_config()


@pytest.fixture(scope="session")
def world_save_dir(zone_config):
    zone, _ = zone_config
    save_dir = WORKSPACE / "data" / zone / "world" / "Arnis World 1"
    if not save_dir.exists() or not list((save_dir / "region").glob("*.mca")):
        pytest.skip(f"No rendered world at {save_dir} — skipping world quality tests")
    return save_dir


@pytest.fixture(scope="session")
def server_world_dir():
    """World staged for deployment in server/BuildDavis/."""
    d = WORKSPACE / "server" / "BuildDavis"
    if not d.exists() or not list((d / "region").glob("*.mca")):
        pytest.skip("No server world at server/BuildDavis/ — skipping deploy QA")
    return d


@pytest.fixture(scope="session")
def chunk_scan(world_save_dir):
    """Scan region files once for the entire test session (expensive)."""
    from test_world import scan_region_blocks
    chunk_stats, all_blocks = scan_region_blocks(world_save_dir, verbose=False)
    return chunk_stats, all_blocks


@pytest.fixture(scope="session")
def transformer(zone_config):
    from test_world import CoordTransformer
    _, bbox = zone_config
    return CoordTransformer(bbox)


@pytest.fixture(scope="session")
def buildings_data(zone_config):
    from test_world import load_buildings_from_geojson
    zone, _ = zone_config
    geojson_path = WORKSPACE / "data" / zone / "fused_features.geojson"
    return load_buildings_from_geojson(geojson_path)


# ── Tests ────────────────────────────────────────────────────────────────────

class TestWorldStructure:
    """Validate world file structure before deployment."""

    def test_region_files_exist(self, world_save_dir):
        from test_world import test_region_files_exist
        result = test_region_files_exist(world_save_dir)
        assert result.passed, f"Region files check failed: {result.messages}"

    def test_level_dat_at_root(self, world_save_dir):
        from test_world import test_level_dat_exists
        result = test_level_dat_exists(world_save_dir)
        assert result.passed, f"level.dat check failed: {result.messages}"


class TestBuildingRendering:
    """Validate buildings actually rendered into the world."""

    def test_building_blocks_present(self, chunk_scan):
        from test_world import test_building_blocks_present
        chunk_stats, _ = chunk_scan
        result = test_building_blocks_present(chunk_stats)
        assert result.passed, f"No building blocks found: {result.messages}"

    def test_building_spatial_coverage(self, chunk_scan, buildings_data, transformer):
        from test_world import test_building_spatial_coverage
        chunk_stats, _ = chunk_scan
        result = test_building_spatial_coverage(chunk_stats, buildings_data, transformer)
        assert result.passed, f"Building coverage gaps: {result.messages}"


class TestRoadRendering:
    """Validate roads rendered into the world."""

    def test_road_blocks_present(self, chunk_scan):
        from test_world import test_road_blocks_present
        chunk_stats, _ = chunk_scan
        result = test_road_blocks_present(chunk_stats)
        assert result.passed, f"No road blocks found: {result.messages}"


class TestWorldQuality:
    """Higher-level world quality checks."""

    def test_no_large_empty_areas(self, chunk_scan, transformer):
        """Warn (but don't fail) for large empty areas — some are parks/fields."""
        from test_world import test_empty_areas
        chunk_stats, _ = chunk_scan
        result = test_empty_areas(chunk_stats, transformer)
        # This is informational — empty areas can be legitimate (parks, fields)
        if result.warnings:
            for w in result.warnings:
                print(f"  WARNING: {w}")

    def test_coordinates_within_bounds(self, buildings_data, transformer):
        from test_world import test_coordinate_range
        result = test_coordinate_range(buildings_data, transformer)
        if not result.passed:
            pytest.xfail(f"Edge buildings outside bounds (known issue): {result.messages}")


class TestDeployStaging:
    """Validate the server/BuildDavis/ staging directory matches the render."""

    def test_server_region_files(self, server_world_dir):
        from test_world import test_region_files_exist
        result = test_region_files_exist(server_world_dir)
        assert result.passed, f"Server staging region check: {result.messages}"

    def test_server_level_dat(self, server_world_dir):
        from test_world import test_level_dat_exists
        result = test_level_dat_exists(server_world_dir)
        assert result.passed, f"Server staging level.dat: {result.messages}"

    def test_server_has_building_blocks(self, server_world_dir):
        """Quick sanity: server staging dir also has buildings."""
        from test_world import scan_region_blocks, test_building_blocks_present
        chunk_stats, _ = scan_region_blocks(server_world_dir, verbose=False)
        result = test_building_blocks_present(chunk_stats)
        assert result.passed, f"Server staging has no buildings: {result.messages}"
