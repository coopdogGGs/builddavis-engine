"""
Test Stage 3: Parse
====================
Validates that parse.py correctly converts raw OSM + Overture data into
structured elements.json with Minecraft coordinates.
"""

import json
import math
from pathlib import Path


def test_parse_produces_elements_json(fetch_dir, tmp_data_dir):
    """run_parse writes elements.json with the expected element count."""
    from parse import run_parse

    result = run_parse(
        fetch_dir=str(fetch_dir),
        output_dir=str(tmp_data_dir),
    )

    elements_path = tmp_data_dir / "elements.json"
    assert elements_path.exists(), "elements.json not created"

    with open(elements_path) as f:
        elements = json.load(f)

    assert isinstance(elements, list)
    # OSM fixture has: 2 buildings (ways), 1 road (way), 1 park (way),
    # 1 bicycle_parking (node) = 5 tagged elements
    # Overture fixture has: 2 buildings
    # Total parsed >= 5 (some may merge or be filtered)
    assert len(elements) >= 4, f"Expected at least 4 elements, got {len(elements)}"


def test_parse_element_types(parsed_elements):
    """Each element has required fields and a valid type."""
    elements, _ = parsed_elements

    required_fields = {"id", "source", "type", "priority"}
    for elem in elements:
        missing = required_fields - set(elem.keys())
        assert not missing, f"Element {elem.get('id')} missing fields: {missing}"
        # osm_id only required for OSM-sourced elements
        if elem.get("source") == "osm":
            assert "osm_id" in elem, f"OSM element {elem['id']} missing osm_id"
        assert elem["type"] in (
            "building", "highway", "landuse", "waterway",
            "natural", "amenity", "leisure", "railway",
        ), f"Unknown type: {elem['type']}"
        assert elem["source"] in ("osm", "overture"), f"Unknown source: {elem['source']}"


def test_parse_minecraft_coords_near_origin(parsed_elements):
    """All mc_coords should be close to (0,0) since fixture data is near the origin."""
    elements, _ = parsed_elements

    for elem in elements:
        if "mc_coords" in elem and elem["mc_coords"]:
            for mx, mz in elem["mc_coords"]:
                assert abs(mx) < 2000, f"mc_x={mx} too far from origin"
                assert abs(mz) < 2000, f"mc_z={mz} too far from origin"
        elif "mc_x" in elem:
            assert abs(elem["mc_x"]) < 2000
            assert abs(elem["mc_z"]) < 2000


def test_parse_building_has_height_fields(parsed_elements):
    """Buildings should have height_m and floors fields (may be None)."""
    elements, _ = parsed_elements

    buildings = [e for e in elements if e["type"] == "building"]
    assert len(buildings) >= 2, "Expected at least 2 buildings"

    for b in buildings:
        assert "height_m" in b, f"Building {b['id']} missing height_m"
        assert "floors" in b, f"Building {b['id']} missing floors"


def test_parse_priority_ordering(parsed_elements):
    """Elements should be sorted by priority (ascending)."""
    elements, _ = parsed_elements

    priorities = [e["priority"] for e in elements]
    assert priorities == sorted(priorities), "Elements not sorted by priority"


def test_parse_road_is_linestring(parsed_elements):
    """Highway elements should have geometry='linestring' (not polygon)."""
    elements, _ = parsed_elements

    roads = [e for e in elements if e["type"] == "highway"]
    assert len(roads) >= 1, "Expected at least 1 road"

    for r in roads:
        assert r["geometry"] == "linestring", (
            f"Road {r['id']} geometry={r['geometry']}, expected linestring"
        )


def test_parse_manifest_written(fetch_dir, tmp_data_dir):
    """run_parse should produce a parse_manifest.json quality report."""
    from parse import run_parse

    run_parse(fetch_dir=str(fetch_dir), output_dir=str(tmp_data_dir))

    manifest = tmp_data_dir / "parse_manifest.json"
    assert manifest.exists(), "parse_manifest.json not created"

    with open(manifest) as f:
        report = json.load(f)

    assert "elements_count" in report
    assert report["elements_count"] >= 4
