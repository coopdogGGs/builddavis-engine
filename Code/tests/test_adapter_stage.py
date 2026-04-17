"""
Test Stage 4.5: Adapter
========================
Validates that adapter.py converts fused GeoJSON into Overpass JSON format
that Arnis can consume, applies enrichment layers, and filters BT-002.
"""

import json
from pathlib import Path


def _run_adapter(fused_geojson_tuple):
    """Helper: run adapter.convert on the fused GeoJSON fixture."""
    geojson, out_dir = fused_geojson_tuple
    from adapter import convert

    fused_path = out_dir / "fused_features.geojson"
    overpass_path, log_path, summary_path = convert(
        fused_path=fused_path,
        output_dir=out_dir,
    )
    with open(overpass_path, encoding="utf-8") as f:
        overpass = json.load(f)
    return overpass, log_path, summary_path


def test_adapter_produces_valid_overpass_json(fused_geojson):
    """Output should have Overpass JSON structure with version, generator, elements."""
    overpass, _, _ = _run_adapter(fused_geojson)

    assert "version" in overpass
    assert "generator" in overpass
    assert "elements" in overpass
    assert isinstance(overpass["elements"], list)
    assert len(overpass["elements"]) > 0


def test_adapter_elements_are_nodes_or_ways(fused_geojson):
    """Every element should be a node or a way (or relation)."""
    overpass, _, _ = _run_adapter(fused_geojson)

    valid_types = {"node", "way", "relation"}
    for elem in overpass["elements"]:
        assert elem["type"] in valid_types, (
            f"Element {elem.get('id')} has unexpected type: {elem['type']}"
        )


def test_adapter_ways_have_nodes(fused_geojson):
    """Way elements should have a nodes list with at least 2 entries."""
    overpass, _, _ = _run_adapter(fused_geojson)

    ways = [e for e in overpass["elements"] if e["type"] == "way"]
    assert len(ways) > 0, "Expected at least 1 way element"
    for way in ways:
        assert "nodes" in way, f"Way {way['id']} missing nodes list"
        assert len(way["nodes"]) >= 2, (
            f"Way {way['id']} has fewer than 2 nodes: {len(way['nodes'])}"
        )


def test_adapter_nodes_have_coords(fused_geojson):
    """Node elements should have lat and lon."""
    overpass, _, _ = _run_adapter(fused_geojson)

    nodes = [e for e in overpass["elements"] if e["type"] == "node"]
    assert len(nodes) > 0, "Expected at least 1 node element"
    for node in nodes:
        assert "lat" in node, f"Node {node['id']} missing lat"
        assert "lon" in node, f"Node {node['id']} missing lon"


def test_adapter_synthetic_node_ids(fused_geojson):
    """Synthetic node IDs should be >= 10_000_000_000."""
    overpass, _, _ = _run_adapter(fused_geojson)

    nodes = [e for e in overpass["elements"] if e["type"] == "node"]
    for node in nodes:
        assert node["id"] >= 10_000_000_000, (
            f"Node ID {node['id']} below synthetic threshold"
        )


def test_adapter_bicycle_parking_filtered(fused_geojson):
    """BT-002: bicycle_parking should not appear in adapter output."""
    overpass, _, _ = _run_adapter(fused_geojson)

    for elem in overpass["elements"]:
        tags = elem.get("tags", {})
        assert tags.get("amenity") != "bicycle_parking", (
            f"bicycle_parking element leaked through BT-002 filter (id={elem['id']})"
        )


def test_adapter_enrichment_log_written(fused_geojson):
    """Adapter should write an enrichment log file."""
    _, log_path, _ = _run_adapter(fused_geojson)
    assert Path(log_path).exists(), "enrichment_log.json not written"


def test_adapter_ways_have_tags(fused_geojson):
    """Way elements should carry tags (building, highway, landuse, etc.)."""
    overpass, _, _ = _run_adapter(fused_geojson)

    ways = [e for e in overpass["elements"] if e["type"] == "way"]
    for way in ways:
        assert "tags" in way, f"Way {way['id']} missing tags dict"
        assert len(way["tags"]) > 0, f"Way {way['id']} has empty tags"
