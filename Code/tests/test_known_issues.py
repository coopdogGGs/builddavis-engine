"""
Test Known Issues — Regression Guards
=======================================
Each test locks a specific bug fix so it cannot silently regress.
Tests are named after the original issue ID from PHASE4_ISSUES.md.
"""

import json
from pathlib import Path


# ── BT-002: bicycle_parking ────────────────────────────────────────────────
def test_bt002_bicycle_parking_filtered_by_adapter(fused_geojson):
    """
    BT-002: bicycle_parking nodes rendered as yellow scaffolding.
    Fix: adapter.py filters them before writing Overpass JSON.
    Guard: fixture includes a bicycle_parking element — verify it is dropped.
    """
    from adapter import convert

    geojson, out_dir = fused_geojson
    fused_path = out_dir / "fused_features.geojson"

    overpass_path, _, _ = convert(fused_path=fused_path, output_dir=out_dir)
    with open(overpass_path, encoding="utf-8") as f:
        overpass = json.load(f)

    amenities = [
        e.get("tags", {}).get("amenity")
        for e in overpass["elements"]
    ]
    assert "bicycle_parking" not in amenities, (
        "BT-002 regression: bicycle_parking present in adapter output"
    )


# ── BT-002 (parse-level): bicycle_parking is parsed correctly ─────────────
def test_bt002_bicycle_parking_parsed(parsed_elements):
    """
    The fixture contains a bicycle_parking node.
    parse.py should still capture it (filtering happens in adapter).
    """
    elements, _ = parsed_elements

    bike_parking = [
        e for e in elements
        if e.get("subtype") == "bicycle_parking"
        or (e.get("tags") or {}).get("amenity") == "bicycle_parking"
    ]
    assert len(bike_parking) >= 1, (
        "parse should retain bicycle_parking — filtering is adapter's job"
    )


# ── HV-001/HV-004: height validation ─────────────────────────────────────
def test_hv001_building_heights_positive(parsed_elements):
    """
    HV-001: All building heights should be positive or None.
    No building should have height_m <= 0.
    """
    elements, _ = parsed_elements

    buildings = [e for e in elements if e.get("type") == "building"]
    for bld in buildings:
        h = bld.get("height_m")
        if h is not None:
            assert float(h) > 0, (
                f"HV-001 regression: building {bld.get('id')} has "
                f"non-positive height {h}"
            )


# ── GS-001: ground material ──────────────────────────────────────────────
def test_gs001_park_terrain_block():
    """
    GS-001: Park/grass areas should map to minecraft:grass_block.
    Guard: transform palette must resolve park → grass_block.
    """
    from transform import PALETTE_TERRAIN

    for park_key in ("park", "grass", "meadow", "village_green"):
        assert PALETTE_TERRAIN.get(park_key) == "minecraft:grass_block", (
            f"GS-001 regression: {park_key} should be grass_block, "
            f"got {PALETTE_TERRAIN.get(park_key)}"
        )


# ── Elevation sanity ─────────────────────────────────────────────────────
def test_davis_ground_elevation_constant():
    """Davis ground Y should be 47 (15m + 32 sea level)."""
    from transform import SEA_LEVEL_Y, DAVIS_GROUND_Y

    assert DAVIS_GROUND_Y == SEA_LEVEL_Y + 15
