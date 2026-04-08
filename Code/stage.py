"""stage.py — Iconic asset staging and live-placement workflow.

Usage:
  python Code/stage.py <name>                         # rebuild + (re)stage
  python Code/stage.py <name> --unstage               # remove from staging, restore grass
  python Code/stage.py <name> --live --osm-id <ID>   # final real placement (by OSM way ID)
  python Code/stage.py <name> --live --lat <LAT> --lon <LON>  # final real placement (explicit coords)
  python Code/stage.py --setup-pad                    # one-time: create 60x60 staging pad

Examples:
  python Code/stage.py --setup-pad
  python Code/stage.py varsity_theater
  python Code/stage.py varsity_theater --unstage
  python Code/stage.py varsity_theater --live --osm-id 45208396
"""

import argparse
import io
import json
import re
import struct
import sys
import zlib
from collections import Counter
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
WORKSPACE = Path(__file__).parent.parent            # repo root
CODE_DIR  = Path(__file__).parent                   # Code/
ICONIC_DIR = CODE_DIR / "iconic_davis"
STATE_FILE = ICONIC_DIR / ".staging_state.json"
FUNC_DIR = (
    WORKSPACE / "server" / "BuildDavis"
    / "datapacks" / "builddavis" / "data" / "builddavis" / "function"
)

# ── Staging pad constants ──────────────────────────────────────────────────────
# 60×60 flat pad at X=[-280,-221], Z=[-280,-221], Y=49
PAD_X1   = -280
PAD_Z1   = -280
PAD_SIZE = 60           # pad occupies [-280, -221] on each axis
PAD_Y    = 49
PAD_X2   = PAD_X1 + PAD_SIZE - 1   # -221
PAD_Z2   = PAD_Z1 + PAD_SIZE - 1   # -221
PAD_CENTER_X = PAD_X1 + PAD_SIZE // 2   # -250
PAD_CENTER_Z = PAD_Z1 + PAD_SIZE // 2   # -250

# ── Ground materials ──────────────────────────────────────────────────────────
ARNIS_GROUND   = "minecraft:stone"         # --city-boundaries flag, deterministic
STAGING_GROUND = "minecraft:grass_block"

# ── RCON ──────────────────────────────────────────────────────────────────────
RCON_HOST = "127.0.0.1"
RCON_PORT = 25575
RCON_PW   = "REDACTED_RCON_PASS"

# ── Import deps from sibling Code/ scripts ────────────────────────────────────
sys.path.insert(0, str(CODE_DIR))

from deploy_iconic import (
    generate_place_function,
    generate_undo_function,
    geo_to_mc,
    locate_osm_feature,
    load_structure_builder,
    _ascii_safe,
)
from rcon_cmd import rcon


# ── Collision detection ────────────────────────────────────────────────────────

# Blocks that are safe to overwrite without a warning.
# Includes Arnis terrain fills, all vegetation, and natural ground materials.
_SAFE_BLOCKS: frozenset[str] = frozenset({
    # ── Air ──────────────────────────────────────────────────────────────────
    "minecraft:air", "minecraft:cave_air", "minecraft:void_air",

    # ── Natural ground / terrain fills (Arnis --city-boundaries output) ──────
    "minecraft:stone", "minecraft:deepslate", "minecraft:cobblestone",
    "minecraft:grass_block", "minecraft:dirt", "minecraft:coarse_dirt",
    "minecraft:rooted_dirt", "minecraft:podzol", "minecraft:mycelium",
    "minecraft:sand", "minecraft:red_sand", "minecraft:gravel",
    "minecraft:sandstone", "minecraft:red_sandstone",
    "minecraft:snow_block", "minecraft:snow", "minecraft:ice",
    "minecraft:packed_ice", "minecraft:blue_ice",
    "minecraft:clay", "minecraft:mud", "minecraft:muddy_mangrove_roots",
    "minecraft:water", "minecraft:lava", "minecraft:bedrock",

    # ── Short grass / ground cover ────────────────────────────────────────────
    "minecraft:grass", "minecraft:tall_grass",
    "minecraft:fern", "minecraft:large_fern",
    "minecraft:dead_bush",
    "minecraft:seagrass", "minecraft:tall_seagrass",
    "minecraft:kelp", "minecraft:kelp_plant",
    "minecraft:lily_pad",

    # ── Flowers ───────────────────────────────────────────────────────────────
    "minecraft:dandelion", "minecraft:poppy", "minecraft:blue_orchid",
    "minecraft:allium", "minecraft:azure_bluet",
    "minecraft:red_tulip", "minecraft:orange_tulip",
    "minecraft:white_tulip", "minecraft:pink_tulip",
    "minecraft:oxeye_daisy", "minecraft:cornflower",
    "minecraft:lily_of_the_valley",
    "minecraft:sunflower", "minecraft:lilac", "minecraft:rose_bush",
    "minecraft:peony", "minecraft:wither_rose",
    "minecraft:torchflower", "minecraft:pitcher_plant",
    "minecraft:wildflowers",         # 1.21+
    "minecraft:leaf_litter",         # 1.21+
    "minecraft:short_dry_grass",     # 1.21+
    "minecraft:tall_dry_grass",      # 1.21+

    # ── Tree logs & wood ──────────────────────────────────────────────────────
    "minecraft:oak_log", "minecraft:oak_wood",
    "minecraft:birch_log", "minecraft:birch_wood",
    "minecraft:spruce_log", "minecraft:spruce_wood",
    "minecraft:jungle_log", "minecraft:jungle_wood",
    "minecraft:acacia_log", "minecraft:acacia_wood",
    "minecraft:dark_oak_log", "minecraft:dark_oak_wood",
    "minecraft:mangrove_log", "minecraft:mangrove_wood",
    "minecraft:cherry_log", "minecraft:cherry_wood",
    "minecraft:stripped_oak_log", "minecraft:stripped_oak_wood",
    "minecraft:stripped_birch_log", "minecraft:stripped_birch_wood",
    "minecraft:stripped_spruce_log", "minecraft:stripped_spruce_wood",
    "minecraft:stripped_jungle_log", "minecraft:stripped_jungle_wood",
    "minecraft:stripped_acacia_log", "minecraft:stripped_acacia_wood",
    "minecraft:stripped_dark_oak_log", "minecraft:stripped_dark_oak_wood",
    "minecraft:stripped_mangrove_log", "minecraft:stripped_mangrove_wood",
    "minecraft:stripped_cherry_log", "minecraft:stripped_cherry_wood",

    # ── Leaves ───────────────────────────────────────────────────────────────
    "minecraft:oak_leaves", "minecraft:birch_leaves",
    "minecraft:spruce_leaves", "minecraft:jungle_leaves",
    "minecraft:acacia_leaves", "minecraft:dark_oak_leaves",
    "minecraft:mangrove_leaves", "minecraft:cherry_leaves",
    "minecraft:azalea_leaves", "minecraft:flowering_azalea_leaves",

    # ── Saplings / propagules ────────────────────────────────────────────────
    "minecraft:oak_sapling", "minecraft:spruce_sapling",
    "minecraft:birch_sapling", "minecraft:jungle_sapling",
    "minecraft:acacia_sapling", "minecraft:dark_oak_sapling",
    "minecraft:cherry_sapling", "minecraft:mangrove_propagule",
    "minecraft:azalea", "minecraft:flowering_azalea",

    # ── Climbing / hanging vegetation ────────────────────────────────────────
    "minecraft:vine", "minecraft:cave_vines", "minecraft:cave_vines_plant",
    "minecraft:twisting_vines", "minecraft:twisting_vines_plant",
    "minecraft:weeping_vines", "minecraft:weeping_vines_plant",
    "minecraft:hanging_roots",

    # ── Other plants ─────────────────────────────────────────────────────────
    "minecraft:sugar_cane", "minecraft:cactus",
    "minecraft:bamboo", "minecraft:bamboo_sapling",
    "minecraft:cocoa", "minecraft:sweet_berry_bush",
    "minecraft:wheat", "minecraft:potatoes", "minecraft:carrots",
    "minecraft:beetroots", "minecraft:melon_stem", "minecraft:pumpkin_stem",
    "minecraft:nether_wart",
})


def _scan_conflicts(
    place_content: str,
    region_dir: Path,
) -> dict:
    """Scan an mcfunction for blocks that would overwrite non-safe terrain.

    Reads server region MCA files using nbtlib (supports Minecraft 1.18+ chunk
    format).  Returns a dict:

        {
          'conflicts': [(x, y, z, existing_block, new_block), ...],
          'scanned':   int,        # total setblock commands parsed
          'error':     str | None, # non-fatal issues (scan incomplete, etc.)
        }
    """
    # ── 1. Parse setblock commands from mcfunction ────────────────────────────
    _SB_RE = re.compile(
        r'^setblock\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(\S+)',
        re.MULTILINE,
    )
    setblocks = [
        (int(m.group(1)), int(m.group(2)), int(m.group(3)),
         m.group(4).split("[")[0])   # strip block-state suffix
        for m in _SB_RE.finditer(place_content)
    ]
    if not setblocks:
        return {"conflicts": [], "scanned": 0, "error": "No setblock commands parsed"}

    # ── 2. nbtlib-based block reader (supports 1.18+ chunk format) ───────────
    try:
        import nbtlib  # type: ignore
    except ImportError:
        return {
            "conflicts": [],
            "scanned": 0,
            "error": (
                "nbtlib not installed; collision scan skipped.  "
                "Install with:  .venv\\Scripts\\pip install nbtlib"
            ),
        }

    _chunk_cache: dict = {}   # (rx, rz, crx, crz) -> parsed sections list
    _region_exists: dict = {}  # (rx, rz) -> bool
    scan_errors = 0

    def _load_chunk_sections(rx, rz, crx, crz):
        """Load and cache parsed sections for a chunk. Returns list or None."""
        ckey = (rx, rz, crx, crz)
        if ckey in _chunk_cache:
            return _chunk_cache[ckey]

        rfile = region_dir / f"r.{rx}.{rz}.mca"
        rkey = (rx, rz)
        if rkey not in _region_exists:
            _region_exists[rkey] = rfile.exists()
        if not _region_exists[rkey]:
            _chunk_cache[ckey] = None
            return None

        try:
            with open(str(rfile), "rb") as f:
                f.seek(4 * (crx + crz * 32))
                loc = struct.unpack(">I", f.read(4))[0]
                offset = (loc >> 8) * 4096
                if offset == 0:
                    _chunk_cache[ckey] = None
                    return None
                f.seek(offset)
                length = struct.unpack(">I", f.read(4))[0]
                compression = struct.unpack("B", f.read(1))[0]
                raw = f.read(length - 1)

            data = zlib.decompress(raw) if compression == 2 else raw
            nbt_data = nbtlib.File.parse(io.BytesIO(data))
            sections = nbt_data.get(
                "sections",
                nbt_data.get("Level", {}).get("Sections", []),
            )
            _chunk_cache[ckey] = sections
            return sections
        except Exception:
            _chunk_cache[ckey] = None
            return None

    def _block_at(x: int, y: int, z: int) -> str:
        """Return 'minecraft:block_name' or '?' if unreadable."""
        rx, rz = x >> 9, z >> 9
        crx, crz = (x >> 4) & 31, (z >> 4) & 31

        sections = _load_chunk_sections(rx, rz, crx, crz)
        if sections is None:
            return "minecraft:air"

        try:
            target_sy = y >> 4
            for section in sections:
                sy = int(section.get("Y", section.get("y", 0)))
                if sy != target_sy:
                    continue
                bs = section.get("block_states", {})
                palette = bs.get("palette", [])
                if not palette:
                    return "minecraft:air"
                data_arr = bs.get("data")
                if data_arr is None or len(data_arr) == 0:
                    name = palette[0].get("Name", "minecraft:air")
                    return name if isinstance(name, str) else str(name)

                bits = max(4, (len(palette) - 1).bit_length())
                mask = (1 << bits) - 1
                lby, lz2, lx2 = y & 15, z & 15, x & 15
                block_idx = (lby * 16 + lz2) * 16 + lx2
                word_idx  = block_idx * bits // 64
                bit_off   = block_idx * bits % 64

                longs = [int(v) for v in data_arr]
                word  = longs[word_idx] if word_idx < len(longs) else 0
                if word < 0:
                    word += (1 << 64)   # treat as unsigned

                pidx = (word >> bit_off) & mask
                if pidx < len(palette):
                    name = palette[pidx].get("Name", "minecraft:air")
                    return name if isinstance(name, str) else str(name)
                return "minecraft:air"
            return "minecraft:air"

        except Exception:
            return "?"

    # ── 3. Check each placement coordinate ───────────────────────────────────
    conflicts = []
    for x, y, z, new_block in setblocks:
        existing = _block_at(x, y, z)
        if existing == "?":
            scan_errors += 1
            continue
        if existing not in _SAFE_BLOCKS:
            conflicts.append((x, y, z, existing, new_block))

    error_msg = (
        f"{scan_errors} block position(s) could not be read "
        f"(possible chunk-format issue — results may be incomplete)"
        if scan_errors > 0
        else None
    )
    return {"conflicts": conflicts, "scanned": len(setblocks), "error": error_msg}


def _print_conflict_report(name: str, ox: int, oz: int, conflicts: list) -> None:
    """Print a human-readable collision warning."""
    by_type = Counter(c[3] for c in conflicts)
    print()
    print("  ╔══════════════════════════════════════════════════════════════╗")
    print(f"  ║  [!] COLLISION WARNING -- '{name}'                          ")
    print(f"  ║     {len(conflicts)} non-safe block(s) would be overwritten        ")
    print("  ╚══════════════════════════════════════════════════════════════╝")
    print(f"\n  Live origin: ({ox}, {PAD_Y}, {oz})\n")
    print("  Existing block types that would be overwritten:")
    for block_type, count in by_type.most_common():
        print(f"    {block_type:<45}  ×{count}")
    show = conflicts[:12]
    remaining = len(conflicts) - len(show)
    print("\n  Sample positions:")
    for x, y, z, existing, new_blk in show:
        print(f"    ({x:>6}, {y:>3}, {z:>6})  {existing}  →  {new_blk}")
    if remaining > 0:
        print(f"    … and {remaining} more")
    print()


# ── State helpers ──────────────────────────────────────────────────────────────

def _load_state() -> dict:
    """Load staging state from disk (returns {} if missing)."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def _save_state(state: dict) -> None:
    """Persist staging state to disk."""
    ICONIC_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ── Build helpers ──────────────────────────────────────────────────────────────

def _find_build_script(name: str) -> Path:
    """Locate Code/build_<name>.py, with glob fallback for longer names.

    E.g. name='varsity_theater' → Code/build_varsity_theater.py (exact)
         name='varsity'         → Code/build_varsity_theater.py (glob fallback)
    """
    exact = CODE_DIR / f"build_{name}.py"
    if exact.exists():
        return exact
    matches = sorted(CODE_DIR.glob(f"build_{name}*.py"))
    if matches:
        return matches[0]
    raise FileNotFoundError(
        f"No build script for '{name}'.\n"
        f"Expected Code/build_{name}.py  (or Code/build_{name}*.py)"
    )


def _build_and_load(name: str):
    """Execute build script and return the StructureBuilder instance.

    Rebuilds the .nbt and preview HTML as a side effect (same as running
    the script directly).  Prints build output live.
    """
    script = _find_build_script(name)
    print(f"[stage] Building '{name}' via {script.name} …")
    sb = load_structure_builder(str(script))
    print(f"[stage] Build complete — {sb.width}×{sb.height}×{sb.depth} structure")
    return sb


# ── Staging helpers ────────────────────────────────────────────────────────────

def _staging_origin(sb) -> tuple[int, int]:
    """Compute SW corner (X, Z) of a structure centered in the staging pad."""
    ox = PAD_CENTER_X - sb.width  // 2
    oz = PAD_CENTER_Z - sb.depth  // 2
    return ox, oz


def _write_func(fname: str, content: str) -> Path:
    """Write an mcfunction to the server datapack function directory."""
    FUNC_DIR.mkdir(parents=True, exist_ok=True)
    path = FUNC_DIR / fname
    path.write_bytes(_ascii_safe(content).encode("ascii"))
    print(f"[stage] Wrote {path.name}  ({path.stat().st_size} bytes)")
    return path


def _rcon(*cmds: str) -> dict[str, str]:
    """Send commands to the local RCON server; returns {cmd: response} dict."""
    try:
        return rcon(RCON_HOST, RCON_PORT, RCON_PW, list(cmds))
    except ConnectionRefusedError:
        print(
            "[stage] WARNING: RCON connection refused — is the local server running?\n"
            "[stage]          mcfunctions were written; run /reload manually."
        )
        return {}
    except Exception as exc:
        print(f"[stage] WARNING: RCON error: {exc}")
        return {}


def _validate_blocks(sb) -> list[str]:
    """Test every unique block ID in a StructureBuilder against the live server.

    Uses RCON to place each block type at a safe underground test coordinate
    inside the staging pad area, then checks the server's response for errors.
    Returns a list of invalid block IDs (empty = all blocks are valid).
    """
    unique = {
        sb._grid[x][y][z]
        for x in range(sb.width)
        for y in range(sb.height)
        for z in range(sb.depth)
        if sb._grid[x][y][z] is not None and sb._grid[x][y][z] != "minecraft:air"
    }
    if not unique:
        return []

    print(f"[stage] Validating {len(unique)} unique block type(s) against server …")

    # Use a safe underground coordinate inside the staging pad (below surface)
    TX, TY, TZ = PAD_X1 + 5, PAD_Y - 10, PAD_Z1 + 5

    # Ensure the test chunk is loaded, then run one setblock per block type
    cmds: list[str] = [
        f"forceload add {PAD_X1} {PAD_Z1}",
        *(f"setblock {TX} {TY} {TZ} {block}" for block in sorted(unique)),
        f"setblock {TX} {TY} {TZ} minecraft:air",   # cleanup
    ]
    responses = _rcon(*cmds)

    if not responses:
        print("[stage] NOTICE: RCON unreachable — block validation skipped.")
        return []

    invalid: list[str] = []
    error_keywords = ("Unknown block type", "Expected", "Whilst parsing", "Invalid")
    for block in sorted(unique):
        cmd = f"setblock {TX} {TY} {TZ} {block}"
        body = responses.get(cmd, "")
        if any(kw in body for kw in error_keywords):
            invalid.append(block)

    return invalid


# ── Sub-commands ───────────────────────────────────────────────────────────────

def cmd_setup_pad() -> None:
    """Create the permanent 60×60 flat staging pad (run once)."""
    print(
        f"[stage] Setting up staging pad: "
        f"X={PAD_X1}..{PAD_X2}, Y={PAD_Y}, Z={PAD_Z1}..{PAD_Z2}"
    )
    _rcon(
        f"forceload add {PAD_X1} {PAD_Z1} {PAD_X2} {PAD_Z2}",
        # Stone substrate one layer below, then grass on top
        f"fill {PAD_X1} {PAD_Y - 1} {PAD_Z1} {PAD_X2} {PAD_Y - 1} {PAD_Z2} minecraft:stone",
        f"fill {PAD_X1} {PAD_Y} {PAD_Z1} {PAD_X2} {PAD_Y} {PAD_Z2} {STAGING_GROUND}",
        # Clear air above so no leftover structures remain
        f"fill {PAD_X1} {PAD_Y + 1} {PAD_Z1} {PAD_X2} {PAD_Y + 30} {PAD_Z2} minecraft:air",
        f"forceload remove {PAD_X1} {PAD_Z1} {PAD_X2} {PAD_Z2}",
    )
    print("[stage] Staging pad ready.")


def cmd_stage(name: str) -> None:
    """Build + (re-)deploy asset to the staging pad."""
    # 1. Build / rebuild
    sb = _build_and_load(name)

    # 2. Staging origin
    ox, oz = _staging_origin(sb)
    print(f"[stage] Staging origin: ({ox}, {PAD_Y}, {oz})")

    # 3. Generate place function — purely additive, no fill pre-clear
    place_content, count = generate_place_function(sb, ox, PAD_Y, oz, f"stage_{name}")

    # 4. Generate undo function — surgical setblock→air, then restore pad grass
    undo_base = generate_undo_function(sb, ox, PAD_Y, oz, f"stage_{name}")
    footprint_x2 = ox + sb.width  - 1
    footprint_z2 = oz + sb.depth  - 1
    undo_content = (
        undo_base
        + "\n# Restore staging ground\n"
        + f"fill {ox} {PAD_Y} {oz} {footprint_x2} {PAD_Y} {footprint_z2} {STAGING_GROUND}"
    )

    # 5. Write both functions to server datapack
    _write_func(f"place_stage_{name}.mcfunction", place_content)
    _write_func(f"undo_stage_{name}.mcfunction",  undo_content)

    # 6. RCON: if previously staged → undo old, reload, place new, tp to pad
    state = _load_state()
    cmds: list[str] = []
    if state.get(name, {}).get("staged"):
        print(f"[stage] Undoing previous '{name}' in staging …")
        cmds.append(f"function builddavis:undo_stage_{name}")
    cmds += [
        "reload",                                          # registers new functions
        f"function builddavis:place_stage_{name}",
        f"tp @a[limit=1] {PAD_CENTER_X} {PAD_Y + 2} {PAD_CENTER_Z}",
    ]
    _rcon(*cmds)

    # 7. Persist state
    entry = state.get(name, {})
    entry.update({
        "staged": True,
        "staging_origin": [ox, PAD_Y, oz],
        "real_origin": entry.get("real_origin"),
    })
    state[name] = entry
    _save_state(state)

    print(f"[stage] '{name}' staged — {count} blocks  origin ({ox}, {PAD_Y}, {oz})")
    # Hint: find the preview HTML
    previews = sorted(ICONIC_DIR.glob(f"**/*{name}*preview*.html"))
    if previews:
        print(f"[stage] Preview: {previews[0]}")


def cmd_unstage(name: str) -> None:
    """Remove asset from staging pad and restore the grass surface."""
    state = _load_state()
    if not state.get(name, {}).get("staged"):
        print(f"[stage] '{name}' is not currently staged — nothing to undo.")
        return

    # RCON: undo then reload
    _rcon(
        f"function builddavis:undo_stage_{name}",
        "reload",
    )

    # Remove the staging mcfunctions from the datapack
    for fname in [
        f"place_stage_{name}.mcfunction",
        f"undo_stage_{name}.mcfunction",
    ]:
        p = FUNC_DIR / fname
        if p.exists():
            p.unlink()
            print(f"[stage] Removed {fname}")

    state[name]["staged"] = False
    _save_state(state)
    print(f"[stage] '{name}' unstaged — staging ground restored.")


def _score_position(
    sb,
    dx: int,
    dz: int,
    ideal_ox: int,
    ideal_oz: int,
    region_dir: Path,
    y: int = PAD_Y,
) -> tuple[int, str | None]:
    """Score one grid candidate: return (conflict_count, error_or_None)."""
    ox = ideal_ox + dx
    oz = ideal_oz + dz
    place_content, _ = generate_place_function(sb, ox, y, oz, "_scan")
    scan = _scan_conflicts(place_content, region_dir)
    return len(scan["conflicts"]), scan.get("error")


def cmd_live(name: str, osm_id: int | None, lat: float | None = None,
             lon: float | None = None, force: bool = False,
             offset: tuple[int, int] | None = None) -> None:
    """Place asset at its real geographic location on the Arnis map."""
    # 1. Build / rebuild
    sb = _build_and_load(name)

    # 2. Validate every block ID against the live server before touching disk.
    #    This catches typos / version-incompatible blocks (e.g. minecraft:chain)
    #    before the mcfunction is written and triggers a server parse error.
    bad_blocks = _validate_blocks(sb)
    if bad_blocks:
        print(
            f"\n[stage] [FAIL] BLOCK VALIDATION FAILED -- cannot place '{name}'\n"
            f"[stage]    The following block IDs are unknown on this server:\n"
        )
        for b in sorted(bad_blocks):
            print(f"[stage]      • {b}")
        print(
            f"\n[stage]    Fix Code/build_{name}.py then re-run.  "
            f"No files were written.\n"
        )
        return

    # 3. Resolve lat/lon → MC coords
    if lat is not None and lon is not None:
        print(f"[stage] Using explicit coordinates: lat={lat:.6f} lon={lon:.6f}")
    else:
        lat, lon = locate_osm_feature(osm_id)
    cx, cz   = geo_to_mc(lat, lon)
    # Place SW corner so structure is centered on the OSM centroid
    ox = cx - sb.width  // 2
    oz = cz - sb.depth  // 2
    if offset:
        ox += offset[0]
        oz += offset[1]
    print(f"[stage] OSM {osm_id}: lat={lat:.6f} lon={lon:.6f}")
    print(f"[stage] MC centroid: ({cx}, {cz})  →  live origin: ({ox}, {PAD_Y}, {oz})")
    if offset:
        print(f"[stage] Offset applied: dx={offset[0]:+} dz={offset[1]:+}")

    # 4. Generate live placement functions
    #    place: purely additive — no bounding-box pre-clear, preserves Arnis terrain
    place_content, count = generate_place_function(sb, ox, PAD_Y, oz, name)

    #    undo: surgical setblock→air only — the Arnis blocks that were beneath the
    #    structure are still there (additive placement never removed them)
    undo_content = generate_undo_function(sb, ox, PAD_Y, oz, name)

    # 5. Collision detection — warn before overwriting non-safe terrain
    region_dir = WORKSPACE / "server" / "BuildDavis" / "region"
    if region_dir.is_dir():
        print(f"[stage] Scanning {count} block positions for terrain conflicts …")
        scan = _scan_conflicts(place_content, region_dir)

        if scan.get("error"):
            if scan.get("scanned", 0) == 0:
                # Scan was entirely skipped (nbtlib missing, region dir absent, etc.)
                # Do NOT print the misleading "[OK] safe to place" below.
                print(
                    f"\n[stage] [!] WARNING: Collision scan unavailable -- "
                    f"{scan['error']}\n"
                    f"[stage]    Proceeding WITHOUT terrain collision data.\n"
                    f"[stage]    Verify placement visually in-game after deploy.\n"
                )
                scan_ok = False
            else:
                print(f"[stage] NOTICE: {scan['error']}")
                scan_ok = True
        else:
            scan_ok = True

        conflicts = scan.get("conflicts", [])
        if conflicts:
            _print_conflict_report(name, ox, oz, conflicts)
            if force:
                print("[stage] --force flag set — proceeding despite conflicts.\n")
            else:
                try:
                    ans = input(
                        "[stage] Proceed and overwrite these blocks? [y/N] "
                    ).strip().lower()
                except EOFError:
                    ans = "n"
                if ans not in ("y", "yes"):
                    print(
                        "[stage] Placement aborted.\n"
                        "[stage] Fix the location or use --force to proceed anyway."
                    )
                    return
        elif scan_ok:
            scanned = scan.get("scanned", 0)
            print(f"[stage] [OK] No terrain conflicts in {scanned} positions -- safe to place.")
    else:
        print(
            "[stage] WARNING: server region/ not found at expected path — "
            "skipping collision scan."
        )

    # 6. Write to server datapack
    _write_func(f"place_{name}.mcfunction", place_content)
    _write_func(f"undo_{name}.mcfunction",  undo_content)

    # 7. RCON sequence
    state = _load_state()
    cmds: list[str] = []
    if state.get(name, {}).get("staged"):
        print(f"[stage] Removing staging version of '{name}' first …")
        cmds.append(f"function builddavis:undo_stage_{name}")
    place_cmd = f"function builddavis:place_{name}"
    cmds += [
        "reload",                                      # registers new place_{name}
        f"tp @a[limit=1] {cx} {PAD_Y + 2} {cz}",
        place_cmd,
    ]
    rcon_resp = _rcon(*cmds)

    # 8. Persist state — only when RCON confirmed placement (Issue 3 fix)
    if not rcon_resp:
        # RCON was unreachable — mcfunctions were written to disk but placement
        # was not confirmed.  Leave state unchanged so the stale entry isn't
        # overwritten with a position we can't verify.
        print(
            f"\n[stage] WARNING: RCON unreachable — state NOT updated.\n"
            f"[stage]   If the server is running, reload and place manually:\n"
            f"[stage]     /reload\n"
            f"[stage]     /function builddavis:place_{name}\n"
        )
    else:
        place_resp = rcon_resp.get(place_cmd, "")
        error_kws  = ("Unknown block type", "Failed to load", "Whilst parsing",
                      "Error", "not found")
        if any(kw in place_resp for kw in error_kws):
            print(
                f"\n[stage] [FAIL] RCON reported an error running '{place_cmd}':\n"
                f"[stage]    {place_resp}\n"
                f"[stage]    State NOT updated — fix the issue and re-run.\n"
            )
        else:
            entry = state.get(name, {})
            entry.update({
                "staged": False,
                "staging_origin": entry.get("staging_origin"),
                "real_origin": [ox, PAD_Y, oz],
            })
            state[name] = entry
            _save_state(state)
            print(f"[stage] [OK] State saved: real_origin = ({ox}, {PAD_Y}, {oz})")

    print(f"[stage] '{name}' placed live — {count} blocks  origin ({ox}, {PAD_Y}, {oz})")
    print(f"[stage] OSM way: https://www.openstreetmap.org/way/{osm_id}")


def cmd_find_safe(name: str, osm_id: int | None,
                  lat: float | None = None, lon: float | None = None) -> None:
    """Rank candidate positions near the OSM centroid by terrain-conflict count."""
    sb = _build_and_load(name)

    # Resolve coordinates (mirrors cmd_live logic)
    if lat is not None and lon is not None:
        print(f"[stage] Using explicit coordinates: lat={lat:.6f} lon={lon:.6f}")
    else:
        lat, lon = locate_osm_feature(osm_id)
    cx, cz = geo_to_mc(lat, lon)
    ideal_ox = cx - sb.width  // 2
    ideal_oz = cz - sb.depth  // 2
    print(
        f"[stage] OSM centroid MC: ({cx}, {cz})"
        f"  →  ideal origin: ({ideal_ox}, {PAD_Y}, {ideal_oz})"
    )

    region_dir = WORKSPACE / "server" / "BuildDavis" / "region"
    if not region_dir.is_dir():
        print(
            "[stage] ERROR: server region/ not found — conflict scan requires "
            f"region files at:\n[stage]   {region_dir}"
        )
        return

    # Scan ±16-block grid in steps of 4 → 81 candidate offsets
    STEP, RADIUS = 4, 16
    n_candidates = len(range(-RADIUS, RADIUS + 1, STEP)) ** 2
    print(f"\n[stage] Scanning {n_candidates} candidate positions (±{RADIUS} blocks, step {STEP}) …")

    results: list[tuple[int, int, int, str | None]] = []
    for dx in range(-RADIUS, RADIUS + 1, STEP):
        for dz in range(-RADIUS, RADIUS + 1, STEP):
            count, err = _score_position(sb, dx, dz, ideal_ox, ideal_oz, region_dir)
            results.append((count, dx, dz, err))
    results.sort()  # primary: conflict_count; ties: dx then dz (ascending)

    # Print ranked table (top 15)
    w = 60
    print(f"\n{'─' * w}")
    print(f"  find-safe: {name}  ({sb.width}×{sb.depth})")
    print(f"  Ideal origin  X={ideal_ox}  Z={ideal_oz}")
    print(f"{'─' * w}")
    print(f"  {'Rank':>4}  {'Offset (dx,dz)':>15}  {'Conflicts':>9}  Note")
    print(f"  {'─' * 4}  {'─' * 15}  {'─' * 9}  {'─' * 30}")
    for rank, (count, dx, dz, err) in enumerate(results[:15], 1):
        if dx == 0 and dz == 0:
            note = "← ideal (OSM centroid)"
        elif err:
            note = f"warn: {err[:40]}"
        else:
            note = ""
        print(f"  {rank:>4}  ({dx:>+3},{dz:>+3})          {count:>9}  {note}")
    print(f"{'─' * w}")

    best = results[0]
    osm_arg = f"--osm-id {osm_id}" if osm_id else f"--lat {lat} --lon {lon}"
    offset_args = "" if (best[1] == 0 and best[2] == 0) else f" --offset {best[1]} {best[2]}"
    force_arg = " --force" if best[0] > 0 else ""
    print(
        f"\n  Best: {best[0]} conflict(s)\n"
        f"  python Code/stage.py {name} --live {osm_arg}{offset_args}{force_arg}\n"
    )


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Iconic asset staging and live-placement workflow.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "name", nargs="?",
        help="Asset name — matches Code/build_<name>.py  (e.g. varsity_theater)",
    )
    parser.add_argument("--setup-pad", action="store_true",
                        help="One-time: create the 60×60 flat staging pad")
    parser.add_argument("--unstage",   action="store_true",
                        help="Remove asset from staging, restore grass")
    parser.add_argument("--live",      action="store_true",
                        help="Place asset at real geographic location")
    parser.add_argument("--osm-id",    type=int, metavar="ID",
                        help="OSM way ID (with --live; alternative to --lat/--lon)")
    parser.add_argument("--lat",       type=float, metavar="LAT",
                        help="Real-world latitude override (with --live)")
    parser.add_argument("--lon",       type=float, metavar="LON",
                        help="Real-world longitude override (with --live)")
    parser.add_argument(
        "--force", action="store_true",
        help="Skip collision-detection confirmation and place anyway",
    )
    parser.add_argument(
        "--find-safe", action="store_true",
        help="Rank candidate positions near the OSM origin by terrain-conflict count",
    )
    parser.add_argument(
        "--offset", nargs=2, type=int, metavar=("DX", "DZ"),
        help="Shift the live placement origin by DX blocks (X) and DZ blocks (Z)",
    )
    args = parser.parse_args()

    if args.setup_pad:
        cmd_setup_pad()
        return

    if not args.name:
        parser.error("asset name is required (or use --setup-pad)")

    if args.find_safe:
        has_osm = bool(args.osm_id)
        has_latlon = (args.lat is not None and args.lon is not None)
        if not has_osm and not has_latlon:
            parser.error("--find-safe requires either --osm-id <ID> or both --lat <LAT> --lon <LON>")
        cmd_find_safe(args.name, args.osm_id, lat=args.lat, lon=args.lon)
    elif args.live:
        has_osm = bool(args.osm_id)
        has_latlon = (args.lat is not None and args.lon is not None)
        if not has_osm and not has_latlon:
            parser.error("--live requires either --osm-id <ID> or both --lat <LAT> --lon <LON>")
        cmd_live(args.name, args.osm_id, lat=args.lat, lon=args.lon, force=args.force,
                 offset=tuple(args.offset) if args.offset else None)
    elif args.unstage:
        cmd_unstage(args.name)
    else:
        cmd_stage(args.name)


if __name__ == "__main__":
    main()
