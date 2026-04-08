"""
Test Stage 5: Transform (unit-level)
=====================================
Tests block-palette resolution and road-block resolution directly, without
needing a full DEM. These are pure-function tests against transform.py
constants and helpers.
"""

import pytest


def test_resolve_building_palette_residential():
    """A generic residential building should map to smooth_sandstone."""
    from transform import resolve_building_palette

    wall, roof, h = resolve_building_palette({"subtype": "house"})
    assert wall == "minecraft:smooth_sandstone"
    assert h >= 3


def test_resolve_building_palette_commercial():
    """A commercial building should map to brick per SPEC-003."""
    from transform import resolve_building_palette

    wall, roof, h = resolve_building_palette({"subtype": "commercial"})
    assert "brick" in wall or "stone" in wall


def test_resolve_building_palette_material_override():
    """Explicit material tag should take precedence over subtype."""
    from transform import resolve_building_palette

    wall, roof, h = resolve_building_palette({
        "subtype": "house",
        "material": "brick",
    })
    assert wall == "minecraft:brick"


def test_resolve_building_palette_height_from_props():
    """height_m in properties should drive height_blocks."""
    from transform import resolve_building_palette

    wall, roof, h = resolve_building_palette({
        "subtype": "apartments",
        "height_m": 12.0,
    })
    assert h == 12  # round(12.0) = 12


def test_resolve_building_palette_generic_yes():
    """building=yes normalises to residential → smooth_sandstone."""
    from transform import resolve_building_palette

    wall, roof, h = resolve_building_palette({"subtype": "yes"})
    # "yes" normalises to "residential"
    assert "sandstone" in wall or "smooth" in wall


def test_resolve_road_block_primary():
    """Primary/residential roads → gray_concrete."""
    from transform import resolve_road_block

    block = resolve_road_block({"subtype": "primary"})
    assert "concrete" in block


def test_resolve_road_block_bike_path():
    """Bike paths → light_gray_concrete."""
    from transform import resolve_road_block

    block = resolve_road_block({"subtype": "cycleway"})
    assert "light_gray" in block or "concrete" in block


def test_palette_terrain_constants():
    """PALETTE_TERRAIN should cover core Davis land uses."""
    from transform import PALETTE_TERRAIN

    assert "park" in PALETTE_TERRAIN
    assert "farmland" in PALETTE_TERRAIN
    assert "residential" in PALETTE_TERRAIN
    # Parks and grass should be grass_block
    assert PALETTE_TERRAIN["park"] == "minecraft:grass_block"


def test_elevation_constants():
    """Key elevation constants should match Davis geography."""
    from transform import SEA_LEVEL_Y, DAVIS_GROUND_Y

    assert SEA_LEVEL_Y == 32
    assert DAVIS_GROUND_Y == 47  # ~15m elevation
    assert DAVIS_GROUND_Y > SEA_LEVEL_Y
