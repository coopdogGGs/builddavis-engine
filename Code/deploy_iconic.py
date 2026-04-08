"""
deploy_iconic.py — One-command deploy of iconic structures to a Minecraft world.

Generates:
  - place_<name>.mcfunction   (forceload + clear + setblock all blocks)
  - undo_<name>.mcfunction    (restore original terrain by filling air + grass)
  - Installs both to the world's datapack

Usage:
  python deploy_iconic.py --build build_amtrak_v3.py --world POC10_Amtrak --x 392 --y 4 --z 240 --name amtrak
  python deploy_iconic.py --build build_amtrak_v3.py --world POC10_Amtrak --x 392 --y 4 --z 240 --name amtrak --remove

In Minecraft:
  /reload
  /function builddavis:place_amtrak
  /function builddavis:undo_amtrak      (if you need to revert)
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

SAVES_DIR = Path(os.environ.get(
    "MINECRAFT_SAVES",
    os.path.expandvars(r"%APPDATA%\.minecraft\saves")
))

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"

# Staging area — flat empty area northwest of rendered world
STAGE_X, STAGE_Y, STAGE_Z = -100, 49, -100

# Arnis world parameters — must match render metadata.json
BBOX_MIN_LAT, BBOX_MAX_LAT = 38.530, 38.590
BBOX_MIN_LON, BBOX_MAX_LON = -121.760, -121.710
WORLD_X, WORLD_Z = 4347, 6671


def geo_to_mc(lat: float, lon: float) -> tuple[int, int]:
    """Convert real-world lat/lon to Minecraft X/Z coordinates."""
    rx = (lon - BBOX_MIN_LON) / (BBOX_MAX_LON - BBOX_MIN_LON)
    rz = 1.0 - (lat - BBOX_MIN_LAT) / (BBOX_MAX_LAT - BBOX_MIN_LAT)
    return int(rx * WORLD_X), int(rz * WORLD_Z)


def locate_osm_feature(osm_id: int) -> tuple[float, float]:
    """Find centroid of an OSM way in enriched_overpass.json."""
    eo_path = DATA_DIR / "enriched_overpass.json"
    if not eo_path.exists():
        raise FileNotFoundError(f"enriched_overpass.json not found at {eo_path}")

    data = json.loads(eo_path.read_text(encoding="utf-8"))

    # Build node lookup
    node_map = {}
    target = None
    for el in data["elements"]:
        if el.get("type") == "node" and "lat" in el:
            node_map[el["id"]] = (el["lat"], el["lon"])
        if el.get("id") == osm_id and el.get("type") == "way":
            target = el

    if target is None:
        raise ValueError(f"OSM way {osm_id} not found in enriched_overpass.json")

    lats, lons = [], []
    for nid in target.get("nodes", []):
        if nid in node_map:
            lat, lon = node_map[nid]
            lats.append(lat)
            lons.append(lon)

    if not lats:
        raise ValueError(f"OSM way {osm_id} has no resolvable node coordinates")

    return sum(lats) / len(lats), sum(lons) / len(lons)


def _ascii_safe(text: str) -> str:
    """Replace non-ASCII characters with ASCII equivalents for mcfunction files."""
    return text.replace("\u2014", "-").replace("\u2013", "-").replace("\u2018", "'").replace("\u2019", "'")


def load_structure_builder(build_script: str):
    """Execute a build script and return the StructureBuilder instance."""
    sys.path.insert(0, str(SCRIPT_DIR))

    # Capture the sb variable from the build script
    namespace = {"__file__": str(Path(build_script).resolve()), "__name__": "__main__"}
    with open(build_script, encoding="utf-8") as f:
        code = f.read()
    exec(compile(code, build_script, "exec"), namespace)

    # The build scripts create an 'sb' variable
    sb = namespace.get("sb")
    if sb is None:
        raise RuntimeError(f"Build script {build_script} did not create an 'sb' StructureBuilder")
    return sb


def generate_place_function(sb, px, py, pz, name):
    """Generate the place mcfunction with forceload + setblock commands.
    
    Does NOT clear the surrounding area — only places structure blocks
    on top of existing terrain to preserve roads, buildings, etc.
    """
    commands = []

    x2 = px + sb.width
    z2 = pz + sb.depth

    # Force-load chunks
    commands.append(f"# Place {name} - {sb.width}x{sb.depth} footprint, {sb.height} tall")
    commands.append(f"forceload add {px} {pz} {x2} {z2}")

    # Place blocks (no area clearing — preserves surrounding terrain)
    count = 0
    for x in range(sb.width):
        for y in range(sb.height):
            for z in range(sb.depth):
                bid = sb._grid[x][y][z]
                if bid is not None and bid != "minecraft:air":
                    commands.append(f"setblock {px + x} {py + y} {pz + z} {bid}")
                    count += 1

    # Unload chunks after
    commands.append(f"forceload remove {px} {pz} {x2} {z2}")
    commands.append(f'tellraw @s {{"text":"Placed {name}: {count} blocks","color":"green"}}')

    return "\n".join(commands), count


def generate_undo_function(sb, px, py, pz, name):
    """Generate the undo mcfunction — surgically remove only placed blocks.
    
    Sets each placed block back to air. Does NOT fill the whole volume,
    so surrounding roads, buildings, and terrain are preserved.
    """
    commands = []

    x2 = px + sb.width
    z2 = pz + sb.depth

    commands.append(f"# Undo {name} (surgical — only removes placed blocks)")
    commands.append(f"forceload add {px} {pz} {x2} {z2}")

    # Only air-out blocks that were actually placed
    count = 0
    for x in range(sb.width):
        for y in range(sb.height):
            for z in range(sb.depth):
                bid = sb._grid[x][y][z]
                if bid is not None and bid != "minecraft:air":
                    commands.append(f"setblock {px + x} {py + y} {pz + z} air")
                    count += 1

    commands.append(f"forceload remove {px} {pz} {x2} {z2}")
    commands.append(f'tellraw @s {{"text":"Removed {name}: {count} blocks","color":"yellow"}}')

    return "\n".join(commands)


def install_datapack(world_name, name, place_content, undo_content):
    """Install the mcfunctions into the world's datapack."""
    world_dir = SAVES_DIR / world_name

    if not world_dir.exists():
        print(f"ERROR: World not found: {world_dir}")
        sys.exit(1)

    pack_dir = world_dir / "datapacks" / "builddavis"
    func_dir = pack_dir / "data" / "builddavis" / "function"
    func_dir.mkdir(parents=True, exist_ok=True)

    # Write pack.mcmeta — pack_format required by MC, even with min/max_format
    mcmeta = pack_dir / "pack.mcmeta"
    mcmeta.write_bytes('{"pack":{"pack_format":61,"description":"BuildDavis Iconic Structures"}}'.encode('ascii'))

    # Write functions (ASCII only, no BOM — Minecraft rejects both)
    place_path = func_dir / f"place_{name}.mcfunction"
    undo_path = func_dir / f"undo_{name}.mcfunction"

    place_path.write_bytes(_ascii_safe(place_content).encode('ascii'))
    undo_path.write_bytes(_ascii_safe(undo_content).encode('ascii'))

    return place_path, undo_path


def save_to_iconic(build_script, name, px, py, pz, place_content, undo_content):
    """Save a copy of the build + functions to iconic_davis/ for future reference."""
    iconic_dir = SCRIPT_DIR / "iconic_davis" / name
    iconic_dir.mkdir(parents=True, exist_ok=True)

    # Copy build script
    shutil.copy2(build_script, iconic_dir / Path(build_script).name)

    # Save functions
    (iconic_dir / f"place_{name}.mcfunction").write_text(place_content)
    (iconic_dir / f"undo_{name}.mcfunction").write_text(undo_content)

    # Save placement config
    config = {
        "name": name,
        "build_script": Path(build_script).name,
        "placement": {"x": px, "y": py, "z": pz},
    }
    import json
    (iconic_dir / "config.json").write_text(json.dumps(config, indent=2))

    return iconic_dir


def main():
    parser = argparse.ArgumentParser(
        description="Deploy iconic structures to a Minecraft world"
    )
    parser.add_argument("--build", required=True, help="Path to the build script (e.g. build_amtrak_v3.py)")
    parser.add_argument("--world", required=True, help="Minecraft world name (e.g. POC10_Amtrak)")
    parser.add_argument("--x", type=int, default=None, help="Placement X coordinate")
    parser.add_argument("--y", type=int, default=49, help="Placement Y coordinate (ground level, default 49)")
    parser.add_argument("--z", type=int, default=None, help="Placement Z coordinate")
    parser.add_argument("--name", required=True, help="Structure name (e.g. amtrak)")
    parser.add_argument("--remove", action="store_true", help="Print the undo command instead")
    parser.add_argument("--stage", action="store_true",
                        help="Place at staging area (-100, 49, -100) for visual verification")
    parser.add_argument("--locate", type=int, default=None, metavar="OSM_ID",
                        help="Auto-derive coords from OSM way ID in enriched_overpass.json")

    args = parser.parse_args()

    # Resolve coordinates
    if args.stage:
        args.x, args.y, args.z = STAGE_X, STAGE_Y, STAGE_Z
        print(f"STAGING MODE: placing at ({args.x}, {args.y}, {args.z})")
    elif args.locate:
        print(f"Locating OSM way {args.locate} in enriched_overpass.json...")
        clat, clon = locate_osm_feature(args.locate)
        mc_x, mc_z = geo_to_mc(clat, clon)
        # Load structure first to get dimensions for centering
        sb_temp = load_structure_builder(args.build)
        args.x = mc_x - sb_temp.width // 2
        args.z = mc_z - sb_temp.depth // 2
        print(f"  Centroid: {clat:.7f}, {clon:.7f} -> MC ({mc_x}, {mc_z})")
        print(f"  Centered: ({args.x}, {args.y}, {args.z}) [{sb_temp.width}x{sb_temp.depth}]")
    elif args.x is None or args.z is None:
        parser.error("--x and --z are required unless using --stage or --locate")

    if args.remove:
        print(f"In Minecraft, run:  /function builddavis:undo_{args.name}")
        return

    print(f"Loading structure from {args.build}...")
    sb = load_structure_builder(args.build)

    print(f"Generating functions...")
    place_content, count = generate_place_function(sb, args.x, args.y, args.z, args.name)
    undo_content = generate_undo_function(sb, args.x, args.y, args.z, args.name)

    print(f"Installing to world '{args.world}'...")
    place_path, undo_path = install_datapack(args.world, args.name, place_content, undo_content)

    print(f"Saving to iconic_davis/{args.name}/...")
    iconic_dir = save_to_iconic(args.build, args.name, args.x, args.y, args.z,
                                 place_content, undo_content)

    mode = "STAGED" if args.stage else "DEPLOYED"
    print(f"\n{'='*60}")
    print(f"  {mode}: {args.name}")
    print(f"  Blocks: {count}")
    print(f"  Coords: ({args.x}, {args.y}, {args.z})")
    print(f"  World:  {args.world}")
    print(f"{'='*60}")
    print(f"\n  In Minecraft:")
    print(f"    /reload")
    print(f"    /function builddavis:place_{args.name}")
    print(f"    /function builddavis:undo_{args.name}   (to revert)")
    if args.stage:
        print(f"    /tp @s {args.x} {args.y + 20} {args.z}   (fly to staging area)")
    else:
        print(f"    /tp @s {args.x} {args.y + 20} {args.z}")
    print(f"\n  Files:")
    print(f"    {place_path}")
    print(f"    {undo_path}")
    print(f"    {iconic_dir}")


if __name__ == "__main__":
    main()
