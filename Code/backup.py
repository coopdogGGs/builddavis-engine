"""BuildDavis — Phase 0A: Backup & Recovery

Creates timestamped .zip snapshots of:
  1. Minecraft world saves (pre-pipeline, so you can rollback a bad gen)
  2. Pipeline data artifacts (enriched_overpass.json, fused_features, etc.)
  3. Pipeline config (spec003_zones, pyproject.toml)

Usage:
  python backup.py                          # back up everything
  python backup.py --world "POC11 North"    # back up one world (substring match)
  python backup.py --data-only              # pipeline artifacts only
  python backup.py --config-only            # config files only
  python backup.py --list                   # list existing backups
  python backup.py --restore <zipfile>      # restore a world backup

Backups go to: <workspace>/backups/
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

WORKSPACE = Path(__file__).resolve().parent.parent  # BuildDavis root
BACKUP_DIR = WORKSPACE / "backups"

MC_SAVES = Path(os.environ.get(
    "MINECRAFT_SAVES",
    Path(os.environ.get("APPDATA", "")) / ".minecraft" / "saves",
))

DATA_DIR = WORKSPACE / "data"
CODE_DIR = WORKSPACE / "Code"

# Pipeline artifacts worth snapshotting (regenerable but slow)
DATA_ARTIFACTS = [
    "enriched_overpass.json",
    "enrichment_log.json",
    "enrichment_summary.json",
    "elements.json",
    "fused_features.geojson",
    "fusion_log.json",
    "osm_raw.json",
    "parse_manifest.json",
    "fuse_manifest.json",
    "lidar_manifest.json",
    "height_review.json",
    "lidar_building_heights.json",
    # Intentionally skip .tif DEMs (~230 MB each, regenerable from USGS cache)
]

# Config files that define *how* the pipeline runs
CONFIG_FILES = [
    CODE_DIR / "pyproject.toml",
    CODE_DIR / "spec003_zones.geojson",
    CODE_DIR / "spec003_zones_1.geojson",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts() -> str:
    """Compact timestamp for filenames: 20260401_153012"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _zip_directory(src: Path, zip_path: Path) -> int:
    """Zip an entire directory tree. Returns file count."""
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(src.rglob("*")):
            if file.is_file():
                zf.write(file, file.relative_to(src.parent))
                count += 1
    return count


def _zip_files(files: list[Path], zip_path: Path, base: Path) -> int:
    """Zip a flat list of files. Returns file count."""
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            if f.exists():
                zf.write(f, f.relative_to(base))
                count += 1
    return count


def _sizeof_fmt(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num) < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def _find_worlds(pattern: str | None = None) -> list[Path]:
    """Find BuildDavis world saves. Optional substring filter."""
    if not MC_SAVES.exists():
        return []
    worlds = sorted(MC_SAVES.iterdir())
    worlds = [w for w in worlds if w.is_dir()]
    if pattern:
        pat = pattern.lower()
        worlds = [w for w in worlds if pat in w.name.lower()]
    return worlds


# ---------------------------------------------------------------------------
# Backup operations
# ---------------------------------------------------------------------------

def backup_world(world_path: Path) -> Path | None:
    """Zip a single Minecraft world save. Returns zip path."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", world_path.name)
    zip_name = f"world_{safe_name}_{_ts()}.zip"
    zip_path = BACKUP_DIR / zip_name

    count = _zip_directory(world_path, zip_path)
    size = _sizeof_fmt(zip_path.stat().st_size)
    print(f"  ✓ World '{world_path.name}' → {zip_name} ({count} files, {size})")
    return zip_path


def backup_worlds(pattern: str | None = None) -> list[Path]:
    """Backup all (or filtered) BuildDavis world saves."""
    worlds = _find_worlds(pattern)
    if not worlds:
        print(f"  ⚠ No worlds found{' matching ' + repr(pattern) if pattern else ''}")
        return []
    zips = []
    for w in worlds:
        z = backup_world(w)
        if z:
            zips.append(z)
    return zips


def backup_data() -> Path | None:
    """Backup pipeline data artifacts (not DEMs — too large and regenerable)."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    files = [DATA_DIR / name for name in DATA_ARTIFACTS]
    existing = [f for f in files if f.exists()]
    if not existing:
        print("  ⚠ No data artifacts found in data/")
        return None
    zip_path = BACKUP_DIR / f"data_{_ts()}.zip"
    count = _zip_files(existing, zip_path, WORKSPACE)
    size = _sizeof_fmt(zip_path.stat().st_size)
    print(f"  ✓ Data artifacts → {zip_path.name} ({count} files, {size})")
    return zip_path


def backup_config() -> Path | None:
    """Backup pipeline config files."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    existing = [f for f in CONFIG_FILES if f.exists()]
    if not existing:
        print("  ⚠ No config files found")
        return None
    zip_path = BACKUP_DIR / f"config_{_ts()}.zip"
    count = _zip_files(existing, zip_path, WORKSPACE)
    size = _sizeof_fmt(zip_path.stat().st_size)
    print(f"  ✓ Config → {zip_path.name} ({count} files, {size})")
    return zip_path


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------

def restore_world(zip_path: Path) -> None:
    """Restore a world backup .zip into Minecraft saves.

    Raises:
        FileNotFoundError: if zip_path doesn't exist.
        ValueError: if zip isn't a world backup or has unexpected structure.
    """
    if not zip_path.exists():
        raise FileNotFoundError(f"Backup not found: {zip_path}")
    if not zip_path.name.startswith("world_"):
        raise ValueError(
            f"Not a world backup (expected 'world_*.zip'): {zip_path.name}"
        )

    with zipfile.ZipFile(zip_path, "r") as zf:
        # The top-level folder inside the zip is the world name
        top_dirs = {Path(n).parts[0] for n in zf.namelist() if "/" in n or "\\" in n}
        if len(top_dirs) != 1:
            raise ValueError(f"Unexpected zip structure: {top_dirs}")
        world_name = top_dirs.pop()
        dest = MC_SAVES / world_name

        if dest.exists():
            # Safety: back up the current version first
            print(f"  ⟳ Existing world '{world_name}' found — backing up before overwrite")
            backup_world(dest)
            shutil.rmtree(dest)

        zf.extractall(MC_SAVES, filter="data")  # filter prevents zip-slip
        print(f"  ✓ Restored '{world_name}' to {dest}")


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

def list_backups() -> None:
    """Print existing backups."""
    if not BACKUP_DIR.exists():
        print("No backups directory yet.")
        return
    zips = sorted(BACKUP_DIR.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not zips:
        print("No backups found.")
        return
    print(f"{'Name':<55} {'Size':>10}  {'Created'}")
    print("-" * 85)
    for z in zips:
        size = _sizeof_fmt(z.stat().st_size)
        mtime = datetime.fromtimestamp(z.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"{z.name:<55} {size:>10}  {mtime}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="BuildDavis backup & recovery tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--world", type=str, default=None,
                        help="Substring filter for world name (default: all BuildDavis worlds)")
    parser.add_argument("--data-only", action="store_true",
                        help="Only back up pipeline data artifacts")
    parser.add_argument("--config-only", action="store_true",
                        help="Only back up config files")
    parser.add_argument("--list", action="store_true",
                        help="List existing backups")
    parser.add_argument("--restore", type=str, default=None,
                        help="Restore a world backup .zip")
    args = parser.parse_args()

    if args.list:
        list_backups()
        return

    if args.restore:
        try:
            restore_world(Path(args.restore))
        except (FileNotFoundError, ValueError) as exc:
            print(f"  ✗ {exc}")
            sys.exit(1)
        return

    ts = _ts()
    print(f"BuildDavis Backup — {ts}")
    print("=" * 40)

    if args.data_only:
        backup_data()
        return

    if args.config_only:
        backup_config()
        return

    # Full backup: worlds + data + config
    print("\n[1/3] Minecraft worlds")
    backup_worlds(args.world)

    print("\n[2/3] Pipeline data")
    backup_data()

    print("\n[3/3] Config files")
    backup_config()

    print(f"\nAll backups in: {BACKUP_DIR}")


if __name__ == "__main__":
    main()
