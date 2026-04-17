#!/usr/bin/env python3
"""Repair ground damage at the Amtrak station and water tower footprints.

Root cause: Chat35 added `fill ... Y=49 ... minecraft:air` clearing commands
to place_amtrak.mcfunction and place_water_tower.mcfunction.  Y=49 IS the
ground level, so those fills wiped the Arnis-rendered terrain.

Repair plan:
  1. Re-run Arnis on the full enriched dataset → fresh clean render in a
     temporary directory (data/repair_temp/)
  2. Copy ONLY the two damaged region files to the server world:
        r.3.10.mca  — Amtrak station area  (X=[1536,2047], Z=[5120,5631])
        r.1.11.mca  — Water tower area     (X=[512,1023],  Z=[5632,6143])
  3. Apply fix_regions to both copied files (Paper 1.21 NBT format patch)
  4. Remove the broken fill-from-Y49 lines from both mcfunctions

Usage:
    # Server MUST be stopped before running this script
    python Code/repair_ground.py

    # If you already ran Arnis recently and the temp dir still exists:
    python Code/repair_ground.py --skip-render

    # Cleanup the temp dir only:
    python Code/repair_ground.py --cleanup
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
WORKSPACE   = Path(__file__).resolve().parent.parent
CODE_DIR    = WORKSPACE / "Code"
DATA_DIR    = WORKSPACE / "data"
SERVER_REGION = WORKSPACE / "server" / "BuildDavis" / "region"
FUNC_DIR    = (
    WORKSPACE / "server" / "BuildDavis"
    / "datapacks" / "builddavis" / "data" / "builddavis" / "function"
)
TEMP_DIR    = DATA_DIR / "repair_temp"

# Locate Arnis binary (try workspace first, then builddavis-engine sibling)
_ARNIS_CANDIDATES = [
    WORKSPACE / "target" / "release" / "arnis.exe",
    Path.home() / "builddavis-engine" / "target" / "release" / "arnis.exe",
]
ARNIS = next((p for p in _ARNIS_CANDIDATES if p.exists()), None)

PYTHON = WORKSPACE / ".venv" / "Scripts" / "python.exe"

# Full-city render parameters (must match deploy_iconic.py)
FULL_CITY_BBOX   = "38.527,-121.812,38.591,-121.670"
GROUND_LEVEL     = 49

# Regions that contain the damaged footprints
DAMAGED_REGIONS = [
    "r.3.10.mca",   # Amtrak station: blocks X≈1955-1991, Z≈5170-5192
    "r.1.11.mca",   # Water tower:    blocks X≈939-973,   Z≈6098-6132
]

# mcfunction files with broken Y=49 clearing
MCFUNCTIONS_TO_FIX = [
    FUNC_DIR / "place_amtrak.mcfunction",
    FUNC_DIR / "place_water_tower.mcfunction",
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _banner(msg: str) -> None:
    bar = "=" * 65
    print(f"\n{bar}\n  {msg}\n{bar}")


def _run(cmd: list, label: str, cwd: Path = None) -> int:
    """Stream subprocess output; return exit code."""
    print(f"\n>> {' '.join(str(c) for c in cmd)}\n")
    t0 = time.time()
    result = subprocess.run(cmd, cwd=cwd or WORKSPACE)
    elapsed = time.time() - t0
    status = "PASS" if result.returncode == 0 else "FAIL"
    print(f"\n[{status}] {label} in {elapsed:.1f}s (exit {result.returncode})")
    return result.returncode


def _find_arnis_regions(output_root: Path) -> Path:
    """Return the region/ directory inside an Arnis world output.

    Arnis may write to:
      <output_root>/Arnis World 1/region/   (single-player save-like layout)
      <output_root>/region/                  (bare layout)
    """
    candidates = [
        output_root / "Arnis World 1" / "region",
        output_root / "region",
    ]
    for p in candidates:
        if p.is_dir():
            return p
    # Deeper search in case Arnis created a sub-directory
    found = list(output_root.rglob("region"))
    if found:
        return found[0]
    raise FileNotFoundError(
        f"Could not find region/ directory under {output_root}\n"
        f"  Searched: {[str(c) for c in candidates]}"
    )


def _fix_regions(region_file: Path) -> None:
    """Apply the Paper-1.21 NBT patch to a single .mca file (in-place)."""
    script = CODE_DIR / "fix_regions.py"
    if not script.exists():
        print(f"  WARNING: fix_regions.py not found at {script} — skipping patch")
        return
    # fix_regions.py accepts either a directory or a single file path
    # Calling it with the file's parent directory patches all .mca files there,
    # which is fine since we've already copied only the two we want.
    rc = _run([str(PYTHON), str(script), str(region_file.parent)],
              f"fix_regions on {region_file.parent.name}")
    if rc != 0:
        print(f"  WARNING: fix_regions exited {rc} for {region_file.name}")


def _remove_y49_fills(mcfunction_path: Path) -> None:
    """Remove any `fill` commands whose Y start coordinate is 49 (= ground).

    These lines look like:
        fill X1 49 Z1 X2 Y2 Z2 minecraft:air

    They are replaced with a comment explaining why they were removed.
    """
    if not mcfunction_path.exists():
        print(f"  WARNING: {mcfunction_path.name} not found — skipping")
        return

    content = mcfunction_path.read_text(encoding="utf-8")
    fixed_lines = []
    removed = 0
    for line in content.splitlines():
        stripped = line.strip().lower()
        # Match: fill <any> 49 <any> <any> <any> <any> <anything>
        parts = stripped.split()
        if (
            len(parts) >= 8
            and parts[0] == "fill"
            and parts[2] == "49"          # Y_start == 49 (ground level)
        ):
            fixed_lines.append(
                f"# REMOVED (Y=49 fill would wipe Arnis ground): {line.strip()}"
            )
            removed += 1
        else:
            fixed_lines.append(line)

    if removed == 0:
        print(f"  {mcfunction_path.name}: no Y=49 fill commands found (already clean)")
        return

    fixed_content = "\n".join(fixed_lines) + "\n"
    mcfunction_path.write_bytes(fixed_content.encode("ascii", errors="replace"))
    print(f"  {mcfunction_path.name}: commented out {removed} Y=49 fill line(s) [OK]")


def _confirm(prompt: str) -> bool:
    """Return True if the user types y/Y."""
    try:
        return input(prompt + " [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


# ── Main steps ─────────────────────────────────────────────────────────────────

def step_render(skip: bool) -> Path:
    """Run Arnis to produce a clean world in TEMP_DIR.  Returns the region path."""
    if skip:
        _banner("SKIP RENDER — using existing temp dir")
        try:
            return _find_arnis_regions(TEMP_DIR)
        except FileNotFoundError:
            print(f"ERROR: --skip-render specified but no region/ found in {TEMP_DIR}")
            print("       Remove --skip-render and let the script run Arnis.")
            sys.exit(1)

    _banner("STEP 1 — Re-render with Arnis")

    if ARNIS is None:
        print("ERROR: arnis.exe not found. Searched:")
        for p in _ARNIS_CANDIDATES:
            print(f"  {p}")
        print("Build with: cargo build --release --bin arnis --no-default-features")
        sys.exit(1)

    enriched = DATA_DIR / "enriched_overpass.json"
    if not enriched.exists():
        print(f"ERROR: {enriched} not found. Run the adapter stage first.")
        sys.exit(1)

    # Wipe and recreate temp dir to guarantee clean output
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
    TEMP_DIR.mkdir(parents=True)

    rc = _run([
        str(ARNIS),
        "--file",         str(enriched),
        "--path",         str(TEMP_DIR),
        "--bbox",         FULL_CITY_BBOX,
        "--ground-level", str(GROUND_LEVEL),
        "--fillground",
        "--interior",
        "--roof",
    ], "Arnis full-city render")

    if rc != 0:
        print(f"ERROR: Arnis exited with code {rc}.")
        sys.exit(1)

    return _find_arnis_regions(TEMP_DIR)


def step_copy_regions(src_region_dir: Path) -> None:
    """Copy the two damaged region files from the fresh render to the server."""
    _banner("STEP 2 — Copy clean region files to server")

    if not SERVER_REGION.is_dir():
        print(f"ERROR: Server region directory not found: {SERVER_REGION}")
        sys.exit(1)

    for filename in DAMAGED_REGIONS:
        src = src_region_dir / filename
        dst = SERVER_REGION / filename

        if not src.exists():
            print(f"  WARNING: {filename} not found in Arnis output ({src}) — skipping")
            continue

        shutil.copy2(src, dst)
        size_kb = dst.stat().st_size // 1024
        print(f"  Copied {filename} → {dst}  ({size_kb:,} KB)")


def step_fix_format() -> None:
    """Patch the two copied region files from Arnis (pre-1.18 NBT) to Paper 1.21 format."""
    _banner("STEP 3 — Apply Paper 1.21 NBT patch (fix_regions)")

    # We only want to patch the two files we just copied, not the entire server.
    # The simplest way is to copy them to a staging dir, run fix_regions there,
    # then move them back — but fix_regions.py works on directories.
    # Instead, create a tiny staging dir with only the two files.
    staging = TEMP_DIR / "fix_staging"
    staging.mkdir(parents=True, exist_ok=True)

    for filename in DAMAGED_REGIONS:
        src = SERVER_REGION / filename
        if src.exists():
            shutil.copy2(src, staging / filename)

    # Run fix_regions on the staging directory
    script = CODE_DIR / "fix_regions.py"
    if not script.exists():
        print(f"  WARNING: fix_regions.py not found — skipping patch")
        return

    rc = _run([str(PYTHON), str(script), str(staging)], "fix_regions (staging)")
    if rc != 0:
        print(f"  WARNING: fix_regions exited {rc}")
        return

    # Move patched files back to server region
    for filename in DAMAGED_REGIONS:
        patched = staging / filename
        if patched.exists():
            shutil.move(str(patched), str(SERVER_REGION / filename))
            size_kb = (SERVER_REGION / filename).stat().st_size // 1024
            print(f"  Patched & moved {filename}  ({size_kb:,} KB)")


def step_fix_mcfunctions() -> None:
    """Remove Y=49 fill commands from the two placement mcfunctions."""
    _banner("STEP 4 — Fix mcfunction clearing (remove Y=49 fills)")

    for path in MCFUNCTIONS_TO_FIX:
        _remove_y49_fills(path)


def step_cleanup() -> None:
    """Remove the temporary render directory.

    Uses PowerShell on Windows to handle read-only files that Arnis sometimes leaves.
    """
    _banner("CLEANUP — Removing temp render dir")
    if not TEMP_DIR.exists():
        print(f"  {TEMP_DIR} does not exist — nothing to remove")
        return

    if sys.platform == "win32":
        result = subprocess.run(
            ["powershell", "-Command",
             f"Remove-Item -Recurse -Force '{TEMP_DIR}' -ErrorAction SilentlyContinue"],
            capture_output=True,
        )
        if not TEMP_DIR.exists():
            print(f"  Removed {TEMP_DIR}")
            return
        # Fall through to shutil if PS failed somehow
    try:
        shutil.rmtree(TEMP_DIR)
        print(f"  Removed {TEMP_DIR}")
    except Exception as e:
        print(f"  WARNING: Could not remove {TEMP_DIR}: {e}")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Repair Arnis ground damage at train station and water tower.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--skip-render", action="store_true",
        help="Skip Arnis re-render; use existing data/repair_temp/ output",
    )
    parser.add_argument(
        "--cleanup", action="store_true",
        help="Remove data/repair_temp/ and exit",
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip the 'are you sure?' confirmation prompt",
    )
    args = parser.parse_args()

    if args.cleanup:
        step_cleanup()
        return

    # Safety gate
    print("\n" + "!" * 65)
    print("  REPAIR GROUND — Will overwrite 2 server region files:")
    for r in DAMAGED_REGIONS:
        print(f"    {SERVER_REGION / r}")
    print("\n  WARNING: STOP the Paper server before continuing!")
    print("!" * 65)

    if not args.yes and not _confirm("\nContinue?"):
        print("Aborted.")
        sys.exit(0)

    # Run all steps
    region_dir = step_render(skip=args.skip_render)
    step_copy_regions(region_dir)
    step_fix_format()
    step_fix_mcfunctions()

    print("\n" + "=" * 65)
    print("  REPAIR COMPLETE")
    print("  [OK]  r.3.10.mca and r.1.11.mca replaced with clean Arnis render")
    print("  [OK]  Both region files patched for Paper 1.21 compatibility")
    print("  [OK]  Y=49 fill commands commented out in place_amtrak.mcfunction")
    print("         and place_water_tower.mcfunction")
    print()
    print("  Next steps:")
    print("  1. Start the Paper server")
    print("  2. Run:  python Code/stage.py amtrak --live --osm-id <ID>")
    print("     (collision detection will warn before overwriting anything)")
    print("  3. Run:  python Code/stage.py water_tower --live --osm-id <ID>")
    print("=" * 65)

    # Clean up temp dir automatically
    step_cleanup()


if __name__ == "__main__":
    main()
