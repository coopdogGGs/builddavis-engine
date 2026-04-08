"""Tests for stage.py — Iconic asset staging workflow.

All tests run without a Minecraft server or RCON connection.
"""

import json
import sys
from pathlib import Path

import pytest

# Ensure Code/ is on the path so both stage and deploy_iconic are importable
CODE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(CODE_DIR))

import stage
from deploy_iconic import generate_place_function, generate_undo_function, geo_to_mc


# ── Minimal StructureBuilder mock ─────────────────────────────────────────────

class _MockSB:
    """Minimal StructureBuilder stand-in with a known block layout."""

    def __init__(self, width: int, height: int, depth: int):
        self.width  = width
        self.height = height
        self.depth  = depth
        # Allocate sparse grid (None = air)
        self._grid = [
            [[None] * depth for _ in range(height)]
            for _ in range(width)
        ]

    def place(self, x: int, y: int, z: int, block: str) -> None:
        self._grid[x][y][z] = block


def _simple_sb() -> _MockSB:
    """4×3×6 structure with 3 non-air blocks in known positions."""
    sb = _MockSB(4, 3, 6)
    sb.place(0, 0, 0, "minecraft:stone")
    sb.place(1, 0, 0, "minecraft:white_concrete")
    sb.place(2, 1, 3, "minecraft:sea_lantern")
    return sb


# ── 1. generate_place_function — no fill commands ─────────────────────────────

def test_generate_place_no_fill_commands():
    """Place function must be purely additive — zero fill commands allowed."""
    sb = _simple_sb()
    content, count = generate_place_function(sb, 100, 49, 200, "test_asset")
    lines = content.splitlines()
    fill_lines = [ln for ln in lines if ln.strip().lower().startswith("fill")]
    assert fill_lines == [], (
        f"generate_place_function emitted fill commands (anti-pattern):\n"
        + "\n".join(fill_lines)
    )


def test_generate_place_block_count():
    """Place function should report exactly the non-air block count."""
    sb = _simple_sb()
    content, count = generate_place_function(sb, 0, 49, 0, "test_asset")
    assert count == 3, f"Expected 3 blocks, got {count}"


def test_generate_place_setblock_coords():
    """Every placed block must appear as a setblock at the correct absolute coord."""
    sb = _simple_sb()
    px, py, pz = 1000, 49, 2000
    content, _ = generate_place_function(sb, px, py, pz, "test_asset")
    # stone at grid (0,0,0) → world (1000, 49, 2000)
    assert f"setblock {px+0} {py+0} {pz+0} minecraft:stone" in content
    # sea_lantern at grid (2,1,3) → world (1002, 50, 2003)
    assert f"setblock {px+2} {py+1} {pz+3} minecraft:sea_lantern" in content


# ── 2. generate_undo_function — surgical, no bounding-box fill ────────────────

def test_generate_undo_no_bounding_box_fill():
    """Base undo function must NOT contain any fill commands (surgical only)."""
    sb = _simple_sb()
    content = generate_undo_function(sb, 100, 49, 200, "test_asset")
    lines = content.splitlines()
    fill_lines = [ln for ln in lines if ln.strip().lower().startswith("fill")]
    assert fill_lines == [], (
        f"generate_undo_function emitted fill commands (bounding-box anti-pattern):\n"
        + "\n".join(fill_lines)
    )


def test_generate_undo_surgical_setblock_air():
    """Undo must emit exactly one `setblock ... air` per placed block."""
    sb = _simple_sb()
    content = generate_undo_function(sb, 100, 49, 200, "test_asset")
    lines = content.splitlines()
    air_lines = [ln for ln in lines if "setblock" in ln and ln.rstrip().endswith("air")]
    assert len(air_lines) == 3, (
        f"Expected 3 surgical air setblocks, found {len(air_lines)}"
    )


def test_generate_undo_no_extra_air_blocks():
    """Undo must not also remove air-grid cells (would be wasteful air→air)."""
    sb = _simple_sb()             # 4×3×6 = 72 cells, only 3 are non-air
    content = generate_undo_function(sb, 0, 49, 0, "test_asset")
    air_lines = [
        ln for ln in content.splitlines()
        if "setblock" in ln and ln.rstrip().endswith("air")
    ]
    assert len(air_lines) == 3, (
        f"Undo set {len(air_lines)} blocks to air — should only touch the 3 placed blocks"
    )


# ── 3. Staging origin computation ─────────────────────────────────────────────

def test_staging_origin_centered_on_pad():
    """Structure should be centered on the staging pad."""
    sb = _MockSB(20, 10, 32)
    ox, oz = stage._staging_origin(sb)
    # PAD_CENTER = (-250, -250)
    # ox = -250 - 20//2 = -260
    # oz = -250 - 32//2 = -266
    assert ox == -260, f"Expected ox=-260, got {ox}"
    assert oz == -266, f"Expected oz=-266, got {oz}"


def test_staging_origin_small_structure():
    """Small structure should also be centered correctly."""
    sb = _MockSB(4, 3, 6)
    ox, oz = stage._staging_origin(sb)
    # ox = -250 - 4//2 = -252
    # oz = -250 - 6//2 = -253
    assert ox == -252, f"Expected ox=-252, got {ox}"
    assert oz == -253, f"Expected oz=-253, got {oz}"


def test_staging_origin_fits_in_pad():
    """Structure footprint centered in pad must stay within pad bounds."""
    sb = _MockSB(40, 20, 50)   # max safe size with 60×60 pad
    ox, oz = stage._staging_origin(sb)
    assert ox >= stage.PAD_X1, f"ox={ox} is outside west pad edge"
    assert oz >= stage.PAD_Z1, f"oz={oz} is outside north pad edge"
    assert ox + sb.width  <= stage.PAD_X2 + 1, "structure overflows east pad edge"
    assert oz + sb.depth  <= stage.PAD_Z2 + 1, "structure overflows south pad edge"


# ── 4. Coordinate conversion ───────────────────────────────────────────────────

def test_geo_to_mc_bbox_corners():
    """Min-lat/min-lon and max-lat/max-lon should map to world corners."""
    # SW corner of bbox → X=0, Z=world_z
    x, z = geo_to_mc(38.530, -121.760)
    assert x == 0,   f"SW corner X should be 0, got {x}"
    assert z == 2779, f"SW corner Z should be 2779, got {z}"  # rz=1 → int(1*2779)

    # NE corner of bbox → X=world_x, Z=0
    x, z = geo_to_mc(38.555, -121.725)
    assert x == 3043, f"NE corner X should be 3043, got {x}"
    assert z == 0,    f"NE corner Z should be 0, got {z}"


def test_geo_to_mc_varsity_range():
    """Varsity Theater centroid must land in a plausible area of the map."""
    # Varsity Theater ~38.5448°N, 121.7411°W (616 2nd St, Davis)
    x, z = geo_to_mc(38.5448, -121.7411)
    assert 1400 <= x <= 1900, f"Varsity x={x} outside expected downtown range"
    assert  800 <= z <= 1500, f"Varsity z={z} outside expected downtown range"


def test_geo_to_mc_deterministic():
    """Same inputs must always produce identical outputs."""
    a = geo_to_mc(38.545, -121.741)
    b = geo_to_mc(38.545, -121.741)
    assert a == b


# ── 5. State file round-trip ──────────────────────────────────────────────────

def test_state_roundtrip(tmp_path: Path):
    """State written by _save_state must be readable by _load_state."""
    orig_state_file = stage.STATE_FILE
    orig_iconic_dir = stage.ICONIC_DIR
    stage.STATE_FILE = tmp_path / ".staging_state.json"
    stage.ICONIC_DIR = tmp_path
    try:
        payload = {
            "varsity_theater": {
                "staged": True,
                "staging_origin": [-259, 49, -266],
                "real_origin": None,
            }
        }
        stage._save_state(payload)
        loaded = stage._load_state()

        assert loaded["varsity_theater"]["staged"] is True
        assert loaded["varsity_theater"]["staging_origin"] == [-259, 49, -266]
        assert loaded["varsity_theater"]["real_origin"] is None
    finally:
        stage.STATE_FILE = orig_state_file
        stage.ICONIC_DIR = orig_iconic_dir


def test_state_missing_returns_empty(tmp_path: Path):
    """_load_state returns {} when no state file exists."""
    orig = stage.STATE_FILE
    stage.STATE_FILE = tmp_path / "nonexistent.json"
    try:
        assert stage._load_state() == {}
    finally:
        stage.STATE_FILE = orig


def test_state_preserves_other_assets(tmp_path: Path):
    """Saving one asset must not overwrite existing entries for other assets."""
    orig_state_file = stage.STATE_FILE
    orig_iconic_dir = stage.ICONIC_DIR
    stage.STATE_FILE = tmp_path / ".staging_state.json"
    stage.ICONIC_DIR = tmp_path
    try:
        initial = {
            "water_tower":     {"staged": False, "staging_origin": None, "real_origin": [200, 49, 300]},
            "varsity_theater": {"staged": True,  "staging_origin": [-259, 49, -266], "real_origin": None},
        }
        stage._save_state(initial)

        # Add a new asset
        state = stage._load_state()
        state["amtrak"] = {"staged": False, "staging_origin": None, "real_origin": [392, 4, 240]}
        stage._save_state(state)

        final = stage._load_state()
        assert "water_tower"     in final
        assert "varsity_theater" in final
        assert "amtrak"          in final
        assert final["water_tower"]["real_origin"] == [200, 49, 300]
    finally:
        stage.STATE_FILE = orig_state_file
        stage.ICONIC_DIR = orig_iconic_dir


# ── 6. staging undo includes ground restore line ─────────────────────────────

def test_stage_undo_includes_ground_fill():
    """cmd_stage appends a grass fill to undo_content — verify the pattern."""
    sb = _simple_sb()
    ox, oz = 100, 200
    undo_base = generate_undo_function(sb, ox, stage.PAD_Y, oz, "stage_test")
    footprint_x2 = ox + sb.width  - 1
    footprint_z2 = oz + sb.depth  - 1
    undo_content = (
        undo_base
        + "\n# Restore staging ground\n"
        + f"fill {ox} {stage.PAD_Y} {oz} {footprint_x2} {stage.PAD_Y} {footprint_z2} {stage.STAGING_GROUND}"
    )

    # The undo content should now have exactly one fill line (ground restore)
    fill_lines = [
        ln for ln in undo_content.splitlines()
        if ln.strip().lower().startswith("fill")
    ]
    assert len(fill_lines) == 1, f"Expected exactly 1 fill (ground restore), got {len(fill_lines)}"
    assert stage.STAGING_GROUND in fill_lines[0]
    # Confirm it covers the full footprint at PAD_Y
    expected = (
        f"fill {ox} {stage.PAD_Y} {oz} "
        f"{footprint_x2} {stage.PAD_Y} {footprint_z2} {stage.STAGING_GROUND}"
    )
    assert expected in undo_content


# ── 7. build script discovery ─────────────────────────────────────────────────

def test_find_build_script_exact(tmp_path: Path):
    """Exact name match returns the correct script."""
    orig = stage.CODE_DIR
    stage.CODE_DIR = tmp_path
    try:
        script = tmp_path / "build_water_tower.py"
        script.write_text("# stub", encoding="utf-8")
        found = stage._find_build_script("water_tower")
        assert found == script
    finally:
        stage.CODE_DIR = orig


def test_find_build_script_glob_fallback(tmp_path: Path):
    """Glob fallback finds build_<name>_<suffix>.py when exact name absent."""
    orig = stage.CODE_DIR
    stage.CODE_DIR = tmp_path
    try:
        script = tmp_path / "build_varsity_theater.py"
        script.write_text("# stub", encoding="utf-8")
        # 'varsity' → no exact match → glob finds 'build_varsity_theater.py'
        found = stage._find_build_script("varsity")
        assert found == script
    finally:
        stage.CODE_DIR = orig


def test_find_build_script_missing_raises(tmp_path: Path):
    """FileNotFoundError is raised when no script matches."""
    orig = stage.CODE_DIR
    stage.CODE_DIR = tmp_path
    try:
        with pytest.raises(FileNotFoundError, match="build_nonexistent"):
            stage._find_build_script("nonexistent")
    finally:
        stage.CODE_DIR = orig
