"""
structurize — Image-informed Minecraft structure builder.

CLI entry point for the BuildDavis post-Arnis overlay system.

Usage:
  python -m structurize analyze <image>              Analyze image → JSON
  python -m structurize build <json>                 Build JSON → .nbt + preview
  python -m structurize full <image>                 Full pipeline: image → .nbt + preview
  python -m structurize preview <json>               Preview a JSON analysis
  python -m structurize backup <world_dir> <x> <y> <z> <sx> <sy> <sz>
  python -m structurize restore <backup_file>
  python -m structurize test                         Run built-in test structure
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


def cmd_analyze(args):
    """Analyze an image and output structural JSON."""
    from .analyze import analyze_image, save_analysis

    print(f"Analyzing image: {args.image}")
    analysis = analyze_image(
        image_path=args.image,
        api_key=args.api_key,
        model=args.model,
        constraint_width=args.max_width,
        constraint_depth=args.max_depth,
        constraint_height=args.max_height,
    )

    out = args.output or Path(args.image).stem + "_analysis.json"
    save_analysis(analysis, out)
    print(f"\nStructure: {analysis.get('description', 'unknown')}")
    dims = analysis.get("dimensions", {})
    print(f"Dimensions: {dims.get('width')}×{dims.get('height')}×{dims.get('depth')} blocks")
    return analysis


def cmd_build(args):
    """Build a .nbt structure from analysis JSON."""
    from .analyze import load_analysis
    from .build import build_structure
    from .preview import generate_preview

    analysis = load_analysis(args.json_file)
    print(f"Building: {analysis.get('description', 'structure')}")

    sb = build_structure(analysis)

    # Save .nbt
    nbt_path = args.output or Path(args.json_file).stem + ".nbt"
    sb.save(nbt_path)
    print(f"Structure saved: {nbt_path}")

    # Generate preview
    preview_path = Path(nbt_path).stem + "_preview.html"
    generate_preview(sb, preview_path,
                     title=analysis.get("description", "Structure"))

    _print_placement_commands(nbt_path, args.place_x, args.place_y, args.place_z)
    return nbt_path


def cmd_full(args):
    """Full pipeline: image → analysis → .nbt + preview."""
    from .analyze import analyze_image, save_analysis
    from .build import build_structure
    from .preview import generate_preview

    stem = Path(args.image).stem

    # Step 1: Analyze
    print(f"Step 1/3: Analyzing {args.image}...")
    analysis = analyze_image(
        image_path=args.image,
        api_key=args.api_key,
        model=args.model,
        constraint_width=args.max_width,
        constraint_depth=args.max_depth,
        constraint_height=args.max_height,
    )
    json_path = args.output_dir + "/" + stem + "_analysis.json" if args.output_dir else stem + "_analysis.json"
    save_analysis(analysis, json_path)

    desc = analysis.get("description", "structure")
    dims = analysis.get("dimensions", {})
    print(f"  → {desc}")
    print(f"  → {dims.get('width')}×{dims.get('height')}×{dims.get('depth')} blocks")

    # Step 2: Build
    print(f"\nStep 2/3: Building structure...")
    sb = build_structure(analysis)
    nbt_path = args.output_dir + "/" + stem + ".nbt" if args.output_dir else stem + ".nbt"
    sb.save(nbt_path)
    print(f"  → {nbt_path}")

    # Step 3: Preview
    print(f"\nStep 3/3: Generating preview...")
    preview_path = args.output_dir + "/" + stem + "_preview.html" if args.output_dir else stem + "_preview.html"
    generate_preview(sb, preview_path, title=desc)

    print(f"\n{'='*50}")
    print(f"DONE — {desc}")
    print(f"  Analysis: {json_path}")
    print(f"  Structure: {nbt_path}")
    print(f"  Preview: {preview_path}")
    print(f"{'='*50}")

    _print_placement_commands(nbt_path, args.place_x, args.place_y, args.place_z)
    return nbt_path


def cmd_preview(args):
    """Generate preview from analysis JSON."""
    from .analyze import load_analysis
    from .build import build_structure
    from .preview import generate_preview

    analysis = load_analysis(args.json_file)
    sb = build_structure(analysis)
    out = args.output or Path(args.json_file).stem + "_preview.html"
    generate_preview(sb, out, title=analysis.get("description", "Preview"))


def cmd_backup(args):
    """Backup a region of the Minecraft world before overwriting."""
    import datetime
    world_dir = Path(args.world_dir)
    if not world_dir.exists():
        print(f"ERROR: World directory not found: {world_dir}")
        sys.exit(1)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_info = {
        "timestamp": timestamp,
        "world_dir": str(world_dir),
        "region": {
            "x": args.x, "y": args.y, "z": args.z,
            "sx": args.sx, "sy": args.sy, "sz": args.sz,
        },
        "region_files": [],
    }

    # Identify affected region files
    region_dir = world_dir / "region"
    if not region_dir.exists():
        print(f"ERROR: No region/ directory in {world_dir}")
        sys.exit(1)

    # Calculate which region files (.mca) are affected
    rx_min = args.x >> 9  # divide by 512
    rx_max = (args.x + args.sx) >> 9
    rz_min = args.z >> 9
    rz_max = (args.z + args.sz) >> 9

    backup_dir = Path(f"structurize_backup_{timestamp}")
    backup_dir.mkdir(exist_ok=True)

    for rx in range(rx_min, rx_max + 1):
        for rz in range(rz_min, rz_max + 1):
            mca_name = f"r.{rx}.{rz}.mca"
            mca_path = region_dir / mca_name
            if mca_path.exists():
                dest = backup_dir / mca_name
                shutil.copy2(mca_path, dest)
                backup_info["region_files"].append(mca_name)
                print(f"  Backed up {mca_name}")

    # Save backup manifest
    manifest_path = backup_dir / "backup_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(backup_info, f, indent=2)

    print(f"\nBackup saved to {backup_dir}/")
    print(f"  Region files: {len(backup_info['region_files'])}")
    print(f"  To restore: python -m structurize restore {backup_dir}")


def cmd_restore(args):
    """Restore a previously backed-up region."""
    backup_dir = Path(args.backup_dir)
    manifest_path = backup_dir / "backup_manifest.json"

    if not manifest_path.exists():
        print(f"ERROR: No backup_manifest.json in {backup_dir}")
        sys.exit(1)

    with open(manifest_path) as f:
        manifest = json.load(f)

    world_dir = Path(manifest["world_dir"])
    region_dir = world_dir / "region"

    if not region_dir.exists():
        print(f"ERROR: World region dir not found: {region_dir}")
        sys.exit(1)

    for mca_name in manifest["region_files"]:
        src = backup_dir / mca_name
        dest = region_dir / mca_name
        if src.exists():
            shutil.copy2(src, dest)
            print(f"  Restored {mca_name}")
        else:
            print(f"  WARNING: {mca_name} not in backup")

    print(f"\nRestore complete. World: {world_dir}")
    print(f"Region: {manifest['region']}")


def cmd_test(args):
    """Generate a test structure to verify the pipeline works."""
    from .build import build_structure
    from .preview import generate_preview

    # A simple 2-story brick building with door and windows
    test_analysis = {
        "description": "Test — 2-story brick building",
        "dimensions": {"width": 10, "height": 8, "depth": 8},
        "walls": {"material": "brick", "color": "#8B4513"},
        "roof": {"type": "gabled", "material": "shingles", "color": "#555555", "overhang": 0},
        "floors": {"count": 2, "height": 4, "material": "wood_floor"},
        "front_face": {
            "features": [
                {"type": "door", "material": "door_wood", "x": 4, "y": 1, "width": 2, "height": 3},
                {"type": "window", "material": "window", "x": 1, "y": 1, "width": 2, "height": 2},
                {"type": "window", "material": "window", "x": 7, "y": 1, "width": 2, "height": 2},
                {"type": "window", "material": "window", "x": 1, "y": 5, "width": 2, "height": 2},
                {"type": "window", "material": "window", "x": 4, "y": 5, "width": 2, "height": 2},
                {"type": "window", "material": "window", "x": 7, "y": 5, "width": 2, "height": 2},
            ]
        },
        "back_face": {
            "features": [
                {"type": "window", "material": "window", "x": 2, "y": 1, "width": 2, "height": 2},
                {"type": "window", "material": "window", "x": 6, "y": 1, "width": 2, "height": 2},
                {"type": "window", "material": "window", "x": 2, "y": 5, "width": 2, "height": 2},
                {"type": "window", "material": "window", "x": 6, "y": 5, "width": 2, "height": 2},
            ]
        },
        "left_face": {
            "features": [
                {"type": "window", "material": "window", "x": 3, "y": 1, "width": 2, "height": 2},
                {"type": "window", "material": "window", "x": 3, "y": 5, "width": 2, "height": 2},
            ]
        },
        "right_face": {
            "features": [
                {"type": "window", "material": "window", "x": 3, "y": 1, "width": 2, "height": 2},
                {"type": "window", "material": "window", "x": 3, "y": 5, "width": 2, "height": 2},
            ]
        },
        "interior": "floors",
        "accent_blocks": [
            {"material": "stone", "color": "#808080", "positions": "corners"},
            {"material": "trim", "color": "#EEEEEE", "positions": "top_edge"},
        ],
        "ground_features": [],
        "custom_blocks": [],
    }

    from .analyze import save_analysis
    save_analysis(test_analysis, "test_structure_analysis.json")

    print("Building test structure...")
    sb = build_structure(test_analysis)

    nbt_path = "test_structure.nbt"
    sb.save(nbt_path)
    print(f"Structure: {nbt_path}")

    preview_path = "test_structure_preview.html"
    generate_preview(sb, preview_path, title="Test — 2-story brick building")

    print(f"\nOpen {preview_path} in your browser to preview.")
    print("If it looks good, the pipeline is working!")


def _print_placement_commands(nbt_path: str, x: int | None, y: int | None,
                              z: int | None):
    """Print Minecraft commands to place the structure."""
    if x is not None and y is not None and z is not None:
        name = Path(nbt_path).stem
        print(f"\nTo place in Minecraft (Java Edition):")
        print(f"  1. Copy {nbt_path} to .minecraft/saves/<world>/generated/builddavis/structures/")
        print(f"  2. Run: /place template builddavis:{name} {x} {y} {z}")
        print(f"\nOr use a structure block at ({x}, {y}, {z})")


def main():
    parser = argparse.ArgumentParser(
        prog="structurize",
        description="Image-informed Minecraft structure builder for BuildDavis",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── analyze ──
    p_analyze = sub.add_parser("analyze", help="Analyze image → JSON")
    p_analyze.add_argument("image", help="Path to image file")
    p_analyze.add_argument("-o", "--output", help="Output JSON path")
    p_analyze.add_argument("--api-key", help="Anthropic API key")
    p_analyze.add_argument("--model", default="claude-sonnet-4-20250514")
    p_analyze.add_argument("--max-width", type=int, help="Max width constraint (blocks)")
    p_analyze.add_argument("--max-depth", type=int, help="Max depth constraint (blocks)")
    p_analyze.add_argument("--max-height", type=int, help="Max height constraint (blocks)")

    # ── build ──
    p_build = sub.add_parser("build", help="Build JSON → .nbt + preview")
    p_build.add_argument("json_file", help="Analysis JSON file")
    p_build.add_argument("-o", "--output", help="Output .nbt path")
    p_build.add_argument("--place-x", type=int)
    p_build.add_argument("--place-y", type=int)
    p_build.add_argument("--place-z", type=int)

    # ── full ──
    p_full = sub.add_parser("full", help="Full pipeline: image → .nbt + preview")
    p_full.add_argument("image", help="Path to image file")
    p_full.add_argument("--api-key", help="Anthropic API key")
    p_full.add_argument("--model", default="claude-sonnet-4-20250514")
    p_full.add_argument("--max-width", type=int)
    p_full.add_argument("--max-depth", type=int)
    p_full.add_argument("--max-height", type=int)
    p_full.add_argument("--output-dir", default=".")
    p_full.add_argument("--place-x", type=int)
    p_full.add_argument("--place-y", type=int)
    p_full.add_argument("--place-z", type=int)

    # ── preview ──
    p_preview = sub.add_parser("preview", help="Preview from JSON")
    p_preview.add_argument("json_file", help="Analysis JSON file")
    p_preview.add_argument("-o", "--output", help="Output HTML path")

    # ── backup ──
    p_backup = sub.add_parser("backup", help="Backup world region")
    p_backup.add_argument("world_dir", help="Minecraft world directory")
    p_backup.add_argument("x", type=int)
    p_backup.add_argument("y", type=int)
    p_backup.add_argument("z", type=int)
    p_backup.add_argument("sx", type=int, help="Size X")
    p_backup.add_argument("sy", type=int, help="Size Y")
    p_backup.add_argument("sz", type=int, help="Size Z")

    # ── restore ──
    p_restore = sub.add_parser("restore", help="Restore from backup")
    p_restore.add_argument("backup_dir", help="Backup directory")

    # ── test ──
    sub.add_parser("test", help="Run built-in test structure")

    args = parser.parse_args()

    commands = {
        "analyze": cmd_analyze,
        "build": cmd_build,
        "full": cmd_full,
        "preview": cmd_preview,
        "backup": cmd_backup,
        "restore": cmd_restore,
        "test": cmd_test,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
