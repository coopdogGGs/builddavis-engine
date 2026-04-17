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


# ── 8. OSM collision detection ────────────────────────────────────────────────

def _make_enriched_overpass(tmp_path: Path, buildings: list[dict]) -> Path:
    """Create a minimal enriched_overpass.json with given building ways."""
    nodes = []
    ways = []
    nid = 1000

    for b in buildings:
        # Create 4 corner nodes from min/max lat/lon
        node_ids = []
        corners = [
            (b["min_lat"], b["min_lon"]),
            (b["min_lat"], b["max_lon"]),
            (b["max_lat"], b["max_lon"]),
            (b["max_lat"], b["min_lon"]),
        ]
        for lat, lon in corners:
            nodes.append({"type": "node", "id": nid, "lat": lat, "lon": lon})
            node_ids.append(nid)
            nid += 1
        node_ids.append(node_ids[0])  # close the polygon
        ways.append({
            "type": "way",
            "id": b["osm_id"],
            "nodes": node_ids,
            "tags": b.get("tags", {"building": "yes"}),
        })

    data = {"elements": nodes + ways}
    path = tmp_path / "enriched_overpass.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_scan_osm_collisions_no_overlap():
    """No collisions when asset is far from any building."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        eo = _make_enriched_overpass(td, [{
            "osm_id": 9999,
            "min_lat": 38.540, "max_lat": 38.541,
            "min_lon": -121.740, "max_lon": -121.739,
            "tags": {"building": "yes"},
        }])
        # Place asset far away (MC origin 0,0 → bottom-left corner of the map)
        result = stage._scan_osm_collisions(0, 7000, 10, 10, eo_path=eo)
        assert result == [], f"Expected no collisions, got {len(result)}"


def test_scan_osm_collisions_full_overlap():
    """Detect engulfed collision when asset bbox fully covers a building."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # Small building in the middle of the map
        eo = _make_enriched_overpass(td, [{
            "osm_id": 5555,
            "min_lat": 38.5450, "max_lat": 38.5452,
            "min_lon": -121.7410, "max_lon": -121.7407,
            "tags": {"building": "commercial", "name": "Test Shop"},
        }])
        # Convert building centroid to MC → place a large asset covering it
        from deploy_iconic import geo_to_mc as di_geo_to_mc
        cx, cz = di_geo_to_mc(38.5451, -121.74085)
        ox = cx - 50   # 100-block wide asset centered on building
        oz = cz - 50
        result = stage._scan_osm_collisions(ox, oz, 100, 100, eo_path=eo)
        assert len(result) == 1, f"Expected 1 collision, got {len(result)}"
        assert result[0]["osm_id"] == 5555
        assert result[0]["classification"] == "engulfed"
        assert result[0]["overlap_pct"] > 80


def test_scan_osm_collisions_excluded_building():
    """Buildings in ICONIC_EXCLUSIONS should not appear in collision results."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        eo = _make_enriched_overpass(td, [{
            "osm_id": 62095055,
            "min_lat": 38.543, "max_lat": 38.544,
            "min_lon": -121.738, "max_lon": -121.737,
            "tags": {"building": "train_station"},
        }])
        from deploy_iconic import geo_to_mc as di_geo_to_mc
        cx, cz = di_geo_to_mc(38.5435, -121.7375)
        result = stage._scan_osm_collisions(
            cx - 50, cz - 50, 100, 100,
            eo_path=eo,
            exclusions={62095055},
        )
        assert result == [], "Excluded building should not appear in collisions"


def test_scan_osm_collisions_neighbor_expected():
    """Neighbor overlaps with expect_neighbors=True are marked as expected."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # Two buildings: one fully overlapping, one barely touching (neighbor)
        eo = _make_enriched_overpass(td, [
            {
                "osm_id": 1001,
                "min_lat": 38.5450, "max_lat": 38.5452,
                "min_lon": -121.7410, "max_lon": -121.7408,
                "tags": {"building": "commercial", "name": "Target Bldg"},
            },
            {
                "osm_id": 1002,
                "min_lat": 38.5452, "max_lat": 38.5455,
                "min_lon": -121.7410, "max_lon": -121.7408,
                "tags": {"building": "retail", "name": "Adjacent Shop"},
            },
        ])
        from deploy_iconic import geo_to_mc as di_geo_to_mc
        # Place asset exactly on building 1001
        cx, cz = di_geo_to_mc(38.5451, -121.7409)
        # Small asset covering only building 1001 footprint, barely touching 1002
        ox = cx - 5
        oz = cz - 5
        result = stage._scan_osm_collisions(
            ox, oz, 10, 10,
            eo_path=eo,
            expect_neighbors=True,
        )
        # Should find at least the target building
        assert len(result) >= 1
        # If neighbor detected, it should be marked expected
        neighbors = [c for c in result if c["classification"] == "neighbor"]
        for n in neighbors:
            assert n["expected"] is True, f"Neighbor {n['osm_id']} should be expected"


def test_classify_overlap_thresholds():
    """Verify overlap classification thresholds."""
    assert stage._classify_overlap(0.90) == "engulfed"
    assert stage._classify_overlap(0.80) == "engulfed"
    assert stage._classify_overlap(0.50) == "partial"
    assert stage._classify_overlap(0.20) == "partial"
    assert stage._classify_overlap(0.19) == "neighbor"
    assert stage._classify_overlap(0.05) == "neighbor"
    assert stage._classify_overlap(0.00) == "neighbor"


def test_bbox_overlap_fraction_no_overlap():
    """Non-overlapping bboxes → 0.0."""
    frac = stage._bbox_overlap_fraction(
        0.0, 1.0, 0.0, 1.0,   # asset
        2.0, 3.0, 2.0, 3.0,   # building (far away)
    )
    assert frac == 0.0


def test_bbox_overlap_fraction_full():
    """Asset fully contains building → 1.0."""
    frac = stage._bbox_overlap_fraction(
        0.0, 10.0, 0.0, 10.0,   # asset (large)
        2.0, 3.0,  2.0, 3.0,    # building (small, inside)
    )
    assert frac == 1.0


def test_bbox_overlap_fraction_half():
    """Asset covers exactly half of building → ~0.5."""
    frac = stage._bbox_overlap_fraction(
        0.0, 5.0, 0.0, 10.0,   # asset
        0.0, 10.0, 0.0, 10.0,  # building
    )
    assert abs(frac - 0.5) < 0.01


def test_load_iconic_exclusions_parses_set():
    """_load_iconic_exclusions should return at least the Amtrak station ID."""
    exclusions = stage._load_iconic_exclusions()
    assert 62095055 in exclusions, "Amtrak station (62095055) should be in exclusions"


def test_scan_osm_collisions_empty_eo():
    """Missing enriched_overpass.json → empty collision list (not an error)."""
    result = stage._scan_osm_collisions(
        0, 0, 10, 10,
        eo_path=Path("/nonexistent/enriched_overpass.json"),
    )
    assert result == []
