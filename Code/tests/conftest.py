"""
BuildDavis Pipeline Test Suite — Shared Fixtures
=================================================
Provides small synthetic Davis data for testing each pipeline stage
without network calls or large files.
"""

import json
import math
import shutil
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ── Coordinate helpers (mirroring parse.py) ──────────────────────────────────

DEFAULT_ORIGIN_LAT = 38.5435
DEFAULT_ORIGIN_LON = -121.7377
LAT_DEG_TO_M = 111_320.0
LON_DEG_TO_M = 111_320.0 * math.cos(math.radians(38.54))


# ── Directory fixtures ───────────────────────────────────────────────────────

@pytest.fixture
def tmp_data_dir(tmp_path):
    """Fresh temp directory for pipeline output."""
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture
def fetch_dir(tmp_path):
    """Simulated Stage 1 fetch directory with micro fixture data."""
    d = tmp_path / "fetch"
    d.mkdir()
    shutil.copy(FIXTURES_DIR / "osm_raw_micro.json", d / "osm_raw.json")
    shutil.copy(
        FIXTURES_DIR / "overture_buildings_micro.geojson",
        d / "overture_buildings.geojson",
    )
    return d


# ── Loaded data fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def osm_raw():
    """Raw OSM Overpass response (micro)."""
    with open(FIXTURES_DIR / "osm_raw_micro.json") as f:
        return json.load(f)


@pytest.fixture
def overture_buildings():
    """Overture building footprints (micro)."""
    with open(FIXTURES_DIR / "overture_buildings_micro.geojson") as f:
        return json.load(f)


@pytest.fixture
def parsed_elements(fetch_dir, tmp_data_dir):
    """Run parse stage on micro data → returns (elements_list, output_dir)."""
    from parse import run_parse

    result = run_parse(
        fetch_dir=str(fetch_dir),
        output_dir=str(tmp_data_dir),
        origin_lat=DEFAULT_ORIGIN_LAT,
        origin_lon=DEFAULT_ORIGIN_LON,
    )
    with open(tmp_data_dir / "elements.json") as f:
        elements = json.load(f)
    return elements, tmp_data_dir


@pytest.fixture
def fused_geojson(parsed_elements):
    """Run fuse stage on parsed micro data → returns (geojson_dict, output_dir)."""
    elements, out_dir = parsed_elements
    from fuse import run_fuse

    elements_path = out_dir / "elements.json"
    run_fuse(
        elements_path=str(elements_path),
        output_dir=str(out_dir),
    )
    with open(out_dir / "fused_features.geojson") as f:
        geojson = json.load(f)
    return geojson, out_dir
