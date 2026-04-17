"""BuildDavis — Pipeline Run Manifest

Captures a complete snapshot of pipeline configuration before each run,
so any POC/zone generation can be reproduced exactly.

Usage:
  # Stamp a manifest before running the pipeline
  python run_manifest.py --bbox 38.560,-121.755,38.572,-121.738 --name poc11_north_davis

  # Compare two manifests to see what changed
  python run_manifest.py --diff manifests/poc10_amtrak.json manifests/poc11_north_davis.json

Manifests go to: <workspace>/manifests/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
MANIFEST_DIR = WORKSPACE / "manifests"
CODE_DIR = WORKSPACE / "Code"
DATA_DIR = WORKSPACE / "data"

# Files whose content matters for reproducibility
VERSIONED_FILES = [
    CODE_DIR / "adapter.py",
    CODE_DIR / "fuse.py",
    CODE_DIR / "parse.py",
    CODE_DIR / "transform.py",
    CODE_DIR / "fetch.py",
    CODE_DIR / "lidar.py",
    CODE_DIR / "spec003_zones.geojson",
    CODE_DIR / "spec003_zones_1.geojson",
    CODE_DIR / "pyproject.toml",
]


def _file_hash(path: Path) -> str | None:
    """SHA-256 of a file, or None if missing."""
    if not path.exists():
        return None
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()[:16]  # 16-char prefix is plenty


def _git_info() -> dict:
    """Current git branch and short SHA, if available."""
    info: dict[str, str | None] = {"branch": None, "sha": None, "dirty": None}
    try:
        info["branch"] = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=WORKSPACE, text=True, stderr=subprocess.DEVNULL,
        ).strip()
        info["sha"] = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=WORKSPACE, text=True, stderr=subprocess.DEVNULL,
        ).strip()
        status = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=WORKSPACE, text=True, stderr=subprocess.DEVNULL,
        ).strip()
        info["dirty"] = bool(status)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return info


def create_manifest(name: str, bbox: str | None = None,
                    arnis_flags: str | None = None,
                    notes: str | None = None) -> Path:
    """Create a timestamped run manifest."""
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {
        "name": name,
        "created": datetime.now(timezone.utc).isoformat(),
        "bbox": bbox,
        "arnis_flags": arnis_flags or "--ground-level 49 --fillground --interior --roof",
        "notes": notes,
        "environment": {
            "python": platform.python_version(),
            "os": f"{platform.system()} {platform.release()}",
            "machine": platform.machine(),
        },
        "git": _git_info(),
        "file_hashes": {
            str(f.relative_to(WORKSPACE)): _file_hash(f)
            for f in VERSIONED_FILES
        },
        "data_artifacts": {
            f.name: f.stat().st_size if f.exists() else None
            for f in sorted(DATA_DIR.glob("*"))
            if f.is_file() and not f.name.endswith(".tif")
        },
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = name.replace(" ", "_").lower()
    out_path = MANIFEST_DIR / f"{safe_name}_{ts}.json"
    out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"✓ Manifest: {out_path.name}")
    print(f"  bbox: {bbox or '(not set)'}")
    print(f"  git:  {manifest['git'].get('sha', '?')} ({manifest['git'].get('branch', '?')})"
          f"{' [dirty]' if manifest['git'].get('dirty') else ''}")
    print(f"  files hashed: {sum(1 for v in manifest['file_hashes'].values() if v)}"
          f"/{len(manifest['file_hashes'])}")
    return out_path


def diff_manifests(path_a: Path, path_b: Path) -> None:
    """Compare two manifests and show what changed."""
    a = json.loads(path_a.read_text(encoding="utf-8"))
    b = json.loads(path_b.read_text(encoding="utf-8"))

    print(f"Comparing: {path_a.name}  ↔  {path_b.name}")
    print("=" * 60)

    # Metadata
    for key in ("bbox", "arnis_flags"):
        va, vb = a.get(key), b.get(key)
        if va != vb:
            print(f"  {key}: {va!r} → {vb!r}")

    # Git
    sha_a = a.get("git", {}).get("sha", "?")
    sha_b = b.get("git", {}).get("sha", "?")
    if sha_a != sha_b:
        print(f"  git sha: {sha_a} → {sha_b}")

    # File hashes
    hashes_a = a.get("file_hashes", {})
    hashes_b = b.get("file_hashes", {})
    all_files = sorted(set(hashes_a) | set(hashes_b))
    changed = []
    for f in all_files:
        ha, hb = hashes_a.get(f), hashes_b.get(f)
        if ha != hb:
            changed.append(f)
            status = "ADDED" if ha is None else "REMOVED" if hb is None else "CHANGED"
            print(f"  {status}: {f}")
    if not changed:
        print("  (no pipeline code changes)")

    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="BuildDavis run manifest tool")
    parser.add_argument("--name", type=str, help="Run/POC name (e.g. 'poc11_north_davis')")
    parser.add_argument("--bbox", type=str, help="Bounding box (lat1,lon1,lat2,lon2)")
    parser.add_argument("--arnis-flags", type=str, help="Arnis CLI flags used")
    parser.add_argument("--notes", type=str, help="Free-text notes")
    parser.add_argument("--diff", nargs=2, metavar="FILE", help="Diff two manifest files")
    parser.add_argument("--list", action="store_true", help="List existing manifests")
    args = parser.parse_args()

    if args.diff:
        diff_manifests(Path(args.diff[0]), Path(args.diff[1]))
        return

    if args.list:
        if not MANIFEST_DIR.exists():
            print("No manifests directory yet.")
            return
        for f in sorted(MANIFEST_DIR.glob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            print(f"  {f.name:<50} bbox={data.get('bbox', '?')}")
        return

    if not args.name:
        parser.error("--name is required when creating a manifest")

    create_manifest(args.name, args.bbox, args.arnis_flags, args.notes)


if __name__ == "__main__":
    main()
