#!/usr/bin/env python3
"""
BuildDavis Pipeline Orchestrator
==================================
Chains all pipeline stages with stop-on-failure and QA gates.

Stages:
  1. fetch     — Download OSM, Overture, LiDAR, city GIS data
  2. parse     — Convert raw data to structured elements
  3. fuse      — Merge multi-source data with priority rules
  4. adapt     — Enrich and convert to Arnis-compatible JSON
  5. render    — Run arnis.exe to produce Minecraft world
  6. qa        — Run world quality tests (blocks deployment on failure)
  7. stage     — Copy rendered world to server/ staging directory
  8. deploy    — Upload to Apex Hosting via FTP

Usage:
    python Code/pipeline.py --zone north_davis --bbox 38.560,-121.755,38.572,-121.738
    python Code/pipeline.py --zone north_davis --bbox 38.560,-121.755,38.572,-121.738 --from render
    python Code/pipeline.py --zone north_davis --bbox 38.560,-121.755,38.572,-121.738 --only qa
    python Code/pipeline.py --zone north_davis --from qa --skip-deploy
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
CODE_DIR = WORKSPACE / "Code"
DATA_DIR = WORKSPACE / "data"
SERVER_DIR = WORKSPACE / "server" / "BuildDavis"
PYTHON = WORKSPACE / ".venv" / "Scripts" / "python.exe"
ARNIS = WORKSPACE / "target" / "release" / "arnis.exe"

STAGES = ["fetch", "parse", "fuse", "adapt", "render", "qa", "stage", "deploy"]


def _banner(stage_num: int, name: str, desc: str):
    """Print a stage header."""
    bar = "=" * 70
    print(f"\n{bar}")
    print(f"  Stage {stage_num}: {name.upper()} -- {desc}")
    print(bar)


def _run(cmd: list, label: str, cwd: Path = None) -> int:
    """Run a subprocess, stream output, return exit code."""
    print(f"\n>> {' '.join(str(c) for c in cmd)}\n")
    t0 = time.time()
    result = subprocess.run(cmd, cwd=cwd or WORKSPACE)
    elapsed = time.time() - t0
    status = "PASS" if result.returncode == 0 else "FAIL"
    print(f"\n[{status}] {label} completed in {elapsed:.1f}s (exit {result.returncode})")
    return result.returncode


def stage_fetch(zone: str, bbox: str, data_dir: Path, **_) -> int:
    """Stage 1: Fetch geospatial data."""
    _banner(1, "fetch", "Download OSM, Overture, LiDAR, City GIS")
    return _run([
        str(PYTHON), str(CODE_DIR / "fetch.py"),
        "--bbox", bbox,
        "--output", str(data_dir),
    ], "Fetch")


def stage_parse(zone: str, data_dir: Path, origin: str = "38.5435,-121.7377", **_) -> int:
    """Stage 2: Parse raw data to structured elements."""
    _banner(2, "parse", "Convert raw data to structured elements")
    return _run([
        str(PYTHON), str(CODE_DIR / "parse.py"),
        "--fetch-dir", str(data_dir),
        "--output", str(data_dir),
        "--origin", origin,
    ], "Parse")


def stage_fuse(zone: str, data_dir: Path, **_) -> int:
    """Stage 3: Fuse multi-source data."""
    _banner(3, "fuse", "Merge data sources by priority")
    cmd = [
        str(PYTHON), str(CODE_DIR / "fuse.py"),
        "--elements", str(data_dir / "elements.json"),
        "--output", str(data_dir),
    ]
    gis = data_dir / "davis_bike_network.geojson"
    if gis.exists():
        cmd += ["--davis-gis", str(gis)]
    return _run(cmd, "Fuse")


def stage_adapt(zone: str, data_dir: Path, **_) -> int:
    """Stage 4: Enrich and convert to Arnis JSON format."""
    _banner(4, "adapt", "Enrich + convert to Overpass JSON for Arnis")
    cmd = [
        str(PYTHON), str(CODE_DIR / "adapter.py"),
        "--fused", str(data_dir / "fused_features.geojson"),
        "--output", str(data_dir),
    ]
    zones = data_dir / "spec003_zones.geojson"
    if zones.exists():
        cmd += ["--spec003-zones", str(zones)]
    cache = data_dir / "reference" / "cache.db"
    if cache.exists():
        cmd += ["--mapillary-cache", str(cache)]
    dsm = data_dir / "davis_dsm_1m.tif"
    if dsm.exists():
        cmd += ["--dsm", str(dsm)]
    dtm = data_dir / "davis_dem_1m.tif"
    if dtm.exists():
        cmd += ["--dtm", str(dtm)]
    return _run(cmd, "Adapt / Enrich")


def stage_render(zone: str, bbox: str, data_dir: Path,
                 ground_level: int = 49, **_) -> int:
    """Stage 5: Run arnis.exe to produce Minecraft world."""
    _banner(5, "render", "Build Minecraft world with Arnis engine")

    enriched = data_dir / "enriched_overpass.json"
    if not enriched.exists():
        print(f"ERROR: {enriched} not found. Run adapt stage first.")
        return 1

    world_output = data_dir / "world"
    world_output.mkdir(parents=True, exist_ok=True)

    if not ARNIS.exists():
        print(f"ERROR: Arnis binary not found at {ARNIS}")
        print("  Build with: cargo build --release --bin arnis --no-default-features")
        return 1

    return _run([
        str(ARNIS),
        "--file", str(enriched),
        "--path", str(world_output),
        "--bbox", bbox,
        "--ground-level", str(ground_level),
        "--fillground",
        "--interior",
        "--roof",
    ], "Arnis Render")


def stage_qa(zone: str, bbox: str, data_dir: Path,
             ground_level: int = 49, **_) -> int:
    """Stage 6: Run world quality tests."""
    _banner(6, "qa", "World quality verification")

    # Import from our test suite
    sys.path.insert(0, str(CODE_DIR))
    from test_world import run_qa, _resolve_bbox

    zone_dir = data_dir
    save_dir = data_dir / "world" / "Arnis World 1"
    if not save_dir.exists():
        # Try without the sub-folder
        save_dir = data_dir / "world"

    bbox_tuple = None
    if bbox:
        parts = [float(x) for x in bbox.split(",")]
        if len(parts) == 4:
            bbox_tuple = tuple(parts)

    if not bbox_tuple:
        bbox_tuple = _resolve_bbox(zone_dir, save_dir)

    passed, results, summary = run_qa(
        zone=zone,
        save_dir=save_dir,
        bbox=bbox_tuple,
        verbose=True,
        ground_level=ground_level,
    )

    print(f"\n{summary}")
    return 0 if passed else 1


def stage_stage(zone: str, data_dir: Path, **_) -> int:
    """Stage 7: Copy rendered world to server/ staging directory."""
    _banner(7, "stage", "Copy world to server/BuildDavis/ for deployment")

    # Find the rendered world
    arnis_world = data_dir / "world" / "Arnis World 1"
    if not arnis_world.exists():
        arnis_world = data_dir / "world"

    region_src = arnis_world / "region"
    level_src = arnis_world / "level.dat"

    if not region_src.exists():
        print(f"ERROR: No region/ directory at {arnis_world}")
        return 1
    if not level_src.exists():
        print(f"ERROR: No level.dat at {arnis_world}")
        return 1

    # Destination
    region_dst = SERVER_DIR / "region"
    region_dst.mkdir(parents=True, exist_ok=True)

    # Copy regions
    mca_files = list(region_src.glob("*.mca"))
    print(f"Copying {len(mca_files)} region files to {region_dst}")
    for mca in mca_files:
        shutil.copy2(mca, region_dst / mca.name)

    # Copy level.dat
    shutil.copy2(level_src, SERVER_DIR / "level.dat")
    print(f"Copied level.dat to {SERVER_DIR}")

    # Copy datapacks if present
    dp_src = arnis_world / "datapacks"
    if dp_src.exists():
        dp_dst = SERVER_DIR / "datapacks"
        if dp_dst.exists():
            shutil.rmtree(dp_dst)
        shutil.copytree(dp_src, dp_dst)
        print(f"Copied datapacks/ to {dp_dst}")

    total_mb = sum(f.stat().st_size for f in region_dst.glob("*.mca")) / (1024 * 1024)
    print(f"\nStaged {len(mca_files)} regions ({total_mb:.1f} MB) + level.dat")
    return 0


def stage_deploy(zone: str, **_) -> int:
    """Stage 8: Upload to Apex Hosting via FTP."""
    _banner(8, "deploy", "Upload world to Apex Hosting")
    return _run([
        str(PYTHON), str(CODE_DIR / "deploy_apex.py"),
        "--skip-qa",  # QA already ran in stage 6
    ], "Deploy to Apex")


# ── Orchestrator ──────────────────────────────────────────────────────────────

def run_pipeline(zone: str, bbox: str, from_stage: str = None,
                 to_stage: str = None, only_stage: str = None,
                 skip_deploy: bool = False, force: bool = False,
                 ground_level: int = 49, origin: str = "38.5435,-121.7377"):
    """Run the pipeline from start to finish (or a subset)."""

    data_dir = DATA_DIR / zone
    data_dir.mkdir(parents=True, exist_ok=True)

    # Resolve stage range
    if only_stage:
        active = [only_stage]
    else:
        start_idx = STAGES.index(from_stage) if from_stage else 0
        end_idx = STAGES.index(to_stage) if to_stage else len(STAGES) - 1
        active = STAGES[start_idx:end_idx + 1]

    if skip_deploy and "deploy" in active:
        active.remove("deploy")

    stage_fns = {
        "fetch": stage_fetch,
        "parse": stage_parse,
        "fuse": stage_fuse,
        "adapt": stage_adapt,
        "render": stage_render,
        "qa": stage_qa,
        "stage": stage_stage,
        "deploy": stage_deploy,
    }

    kwargs = dict(
        zone=zone,
        bbox=bbox,
        data_dir=data_dir,
        ground_level=ground_level,
        origin=origin,
    )

    print("=" * 70)
    print("  BuildDavis Pipeline Orchestrator")
    print("=" * 70)
    print(f"Zone:        {zone}")
    print(f"Bbox:        {bbox}")
    print(f"Data dir:    {data_dir}")
    print(f"Stages:      {' -> '.join(active)}")
    print(f"Ground:      Y={ground_level}")
    t_start = time.time()

    for stage_name in active:
        fn = stage_fns[stage_name]
        rc = fn(**kwargs)
        if rc != 0:
            if stage_name == "qa" and force:
                print(f"\nWARNING: QA failed but --force was specified. Continuing.")
                continue
            print(f"\nPIPELINE ABORTED: Stage '{stage_name}' failed (exit {rc})")
            print(f"  Fix the issue and resume with: --from {stage_name}")
            sys.exit(rc)

    total = time.time() - t_start
    print(f"\n{'=' * 70}")
    print(f"  PIPELINE COMPLETE  ({total:.1f}s total)")
    print(f"  Stages run: {', '.join(active)}")
    print(f"{'=' * 70}")


def main():
    parser = argparse.ArgumentParser(
        description="BuildDavis Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Full pipeline:
    python Code/pipeline.py --zone north_davis --bbox 38.560,-121.755,38.572,-121.738

  Resume from render stage:
    python Code/pipeline.py --zone north_davis --bbox 38.560,-121.755,38.572,-121.738 --from render

  Only run QA:
    python Code/pipeline.py --zone north_davis --bbox 38.560,-121.755,38.572,-121.738 --only qa

  Everything except deploy:
    python Code/pipeline.py --zone north_davis --bbox 38.560,-121.755,38.572,-121.738 --skip-deploy
        """
    )
    parser.add_argument("--zone", required=True, help="Zone name (e.g. north_davis)")
    parser.add_argument("--bbox", required=True,
                        help="Bounding box: S,W,N,E (e.g. 38.560,-121.755,38.572,-121.738)")
    parser.add_argument("--from", dest="from_stage", choices=STAGES,
                        help="Start from this stage (skip earlier stages)")
    parser.add_argument("--to", dest="to_stage", choices=STAGES,
                        help="Stop after this stage")
    parser.add_argument("--only", dest="only_stage", choices=STAGES,
                        help="Run only this single stage")
    parser.add_argument("--skip-deploy", action="store_true",
                        help="Run everything except the deploy stage")
    parser.add_argument("--force", action="store_true",
                        help="Continue past QA failures")
    parser.add_argument("--ground-level", type=int, default=49,
                        help="Minecraft ground Y level (default: 49)")
    parser.add_argument("--origin", default="38.5435,-121.7377",
                        help="Coordinate origin lat,lon (default: Davis Amtrak)")
    args = parser.parse_args()

    run_pipeline(
        zone=args.zone,
        bbox=args.bbox,
        from_stage=args.from_stage,
        to_stage=args.to_stage,
        only_stage=args.only_stage,
        skip_deploy=args.skip_deploy,
        force=args.force,
        ground_level=args.ground_level,
        origin=args.origin,
    )


if __name__ == "__main__":
    main()
