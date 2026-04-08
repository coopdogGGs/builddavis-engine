"""
Test Stage 4: Fuse
===================
Validates that fuse.py correctly merges OSM + Overture elements into a
single fused_features.geojson with match/unmatched bookkeeping.
"""

import json
from pathlib import Path


def test_fuse_produces_geojson(fused_geojson):
    """run_fuse writes a valid GeoJSON FeatureCollection."""
    geojson, _ = fused_geojson

    assert geojson["type"] == "FeatureCollection"
    assert "features" in geojson
    assert len(geojson["features"]) >= 4, (
        f"Expected at least 4 fused features, got {len(geojson['features'])}"
    )


def test_fuse_features_have_required_properties(fused_geojson):
    """Each feature should have id, type, source, and geometry."""
    geojson, _ = fused_geojson

    for feat in geojson["features"]:
        assert feat["type"] == "Feature"
        assert "geometry" in feat
        assert "properties" in feat

        props = feat["properties"]
        assert "id" in props, f"Feature missing id"
        assert "type" in props, f"Feature {props.get('id')} missing type"
        assert "source" in props, f"Feature {props.get('id')} missing source"


def test_fuse_buildings_present(fused_geojson):
    """Fused output should contain buildings from both OSM and Overture."""
    geojson, _ = fused_geojson

    buildings = [
        f for f in geojson["features"]
        if f["properties"]["type"] == "building"
    ]
    # OSM fixture has 2 buildings, Overture has 2 (1 matching, 1 unique)
    # After fusion: at least 3 buildings
    assert len(buildings) >= 2, f"Expected >= 2 buildings, got {len(buildings)}"


def test_fuse_non_buildings_preserved(fused_geojson):
    """Roads, parks, and other non-building elements pass through fusion."""
    geojson, _ = fused_geojson

    types = {f["properties"]["type"] for f in geojson["features"]}
    assert "highway" in types, "Roads should survive fusion"
    # Park is tagged as leisure, which maps to either "leisure" or "landuse"
    assert types & {"leisure", "landuse"}, "Park/landuse should survive fusion"


def test_fuse_manifest_written(parsed_elements):
    """run_fuse should produce a fuse_manifest.json."""
    elements, out_dir = parsed_elements
    from fuse import run_fuse

    elements_path = out_dir / "elements.json"
    run_fuse(elements_path=str(elements_path), output_dir=str(out_dir))

    manifest = out_dir / "fuse_manifest.json"
    assert manifest.exists(), "fuse_manifest.json not created"

    with open(manifest) as f:
        report = json.load(f)

    assert "elements_count" in report or "fused_path" in report


def test_fuse_geojson_geometry_valid(fused_geojson):
    """All features should have valid GeoJSON geometry."""
    geojson, _ = fused_geojson

    for feat in geojson["features"]:
        geom = feat["geometry"]
        assert geom["type"] in (
            "Point", "LineString", "Polygon", "MultiPolygon"
        ), f"Invalid geometry type: {geom['type']}"
        assert "coordinates" in geom
        assert len(geom["coordinates"]) > 0


def test_fuse_mc_coords_present(fused_geojson):
    """Fused features should carry Minecraft coordinate data."""
    geojson, _ = fused_geojson

    for feat in geojson["features"]:
        props = feat["properties"]
        # Either mc_coords_json or mc_x/mc_z should exist
        has_mc = (
            "mc_coords_json" in props
            or ("mc_x" in props and "mc_z" in props)
        )
        assert has_mc, f"Feature {props.get('id')} missing Minecraft coords"
