#!/usr/bin/env python3
"""
deploy_apex.py — Upload BuildDavis world to Apex Hosting via FTP.

Uploads:
  - server/BuildDavis/region/*.mca  -> <world>/region/
  - server/BuildDavis/level.dat     -> <world>/level.dat
  - server/BuildDavis/datapacks/    -> <world>/datapacks/  (recursive)

Credentials are read from .env in the workspace root (never committed).

IMPORTANT: Stop the server in the Apex panel BEFORE deploying!
  The Paper server will auto-save over uploaded files if it's running,
  causing chunk position mismatches and world corruption.

Usage:
  python Code/deploy_apex.py            # full deploy (runs QA gate first)
  python Code/deploy_apex.py --dry-run  # preview what would be uploaded
  python Code/deploy_apex.py --region   # region files only (fast re-deploy)
  python Code/deploy_apex.py --list     # list remote world folder contents
  python Code/deploy_apex.py --verify   # compare local vs remote checksums
  python Code/deploy_apex.py --skip-qa  # skip QA gate
  python Code/deploy_apex.py --force    # deploy even if QA fails
"""

import ftplib
import hashlib
import io
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

# ── Resolve workspace root (one level up from Code/) ──────────────────────────
WORKSPACE = Path(__file__).parent.parent
WORLD_DIR  = WORKSPACE / "server" / "BuildDavis"
REGION_DIR = WORLD_DIR / "region"
DATAPACK_DIR = WORLD_DIR / "datapacks"
LEVEL_DAT  = WORLD_DIR / "level.dat"


# ── Load .env manually (no extra deps) ────────────────────────────────────────
def load_env(path: Path) -> dict:
    env = {}
    if not path.exists():
        print(f"ERROR: .env not found at {path}")
        sys.exit(1)
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


# ── FTP helpers ───────────────────────────────────────────────────────────────
def connect(host: str, port: int, user: str, password: str) -> ftplib.FTP:
    """Connect via FTPS (TLS) with plain FTP fallback."""
    print(f"Connecting to {host}:{port} ...")
    try:
        ftp = ftplib.FTP_TLS()
        ftp.connect(host, port, timeout=30)
        ftp.login(user, password)
        ftp.prot_p()
        print("  Connected (FTPS/TLS)")
    except Exception as tls_err:
        print(f"  FTPS failed ({tls_err}), falling back to plain FTP ...")
        ftp = ftplib.FTP()
        ftp.connect(host, port, timeout=30)
        ftp.login(user, password)
        print("  Connected (plain FTP)")
    ftp.set_pasv(True)
    return ftp


def check_server_running(host: str, mc_port: int = 25606) -> bool:
    """Check if the Minecraft server is accepting connections."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((host, mc_port))
        sock.close()
        return result == 0
    except Exception:
        return False


def ensure_remote_dir(ftp: ftplib.FTP, remote_dir: str) -> None:
    """Create remote directory if it doesn't exist (ignores error if exists)."""
    try:
        ftp.mkd(remote_dir)
    except ftplib.error_perm:
        pass  # already exists


def upload_file(ftp: ftplib.FTP, local: Path, remote: str, dry_run: bool) -> int:
    """Upload one file. Returns bytes transferred (0 on dry run)."""
    size = local.stat().st_size
    label = f"{local.name}  ({size / 1024:.0f} KB)"
    if dry_run:
        print(f"  [dry] {label}  ->  {remote}")
        return 0
    print(f"  ↑ {label}", end="", flush=True)
    t0 = time.time()
    with open(local, "rb") as f:
        ftp.storbinary(f"STOR {remote}", f)
    elapsed = time.time() - t0
    print(f"  ({elapsed:.1f}s)")
    return size


def upload_dir_recursive(ftp: ftplib.FTP, local_dir: Path,
                          remote_dir: str, dry_run: bool) -> tuple[int, int]:
    """Recursively upload a local directory. Returns (files, bytes)."""
    ensure_remote_dir(ftp, remote_dir)
    total_files = 0
    total_bytes = 0
    for item in sorted(local_dir.iterdir()):
        if item.is_file():
            remote_path = f"{remote_dir}/{item.name}"
            total_bytes += upload_file(ftp, item, remote_path, dry_run)
            total_files += 1
        elif item.is_dir():
            sub_remote = f"{remote_dir}/{item.name}"
            f, b = upload_dir_recursive(ftp, item, sub_remote, dry_run)
            total_files += f
            total_bytes += b
    return total_files, total_bytes


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    dry_run     = "--dry-run" in sys.argv
    region_only = "--region"  in sys.argv
    list_only   = "--list"    in sys.argv
    verify_only = "--verify"  in sys.argv

    env = load_env(WORKSPACE / ".env")
    host   = env.get("APEX_HOST", "")
    port   = int(env.get("APEX_PORT", "21"))
    user   = env.get("APEX_USER", "")
    passwd = env.get("APEX_PASS", "")
    remote_world = env.get("APEX_WORLD_FOLDER", "paper_1_21_4_3817181")

    if not all([host, user, passwd]):
        print("ERROR: APEX_HOST / APEX_USER / APEX_PASS missing from .env")
        sys.exit(1)

    # Validate local source
    if not REGION_DIR.exists():
        print(f"ERROR: Region dir not found: {REGION_DIR}")
        sys.exit(1)
    region_files = sorted(REGION_DIR.glob("*.mca"))
    if not region_files:
        print("ERROR: No .mca files found in region dir")
        sys.exit(1)

    ftp = connect(host, port, user, passwd)

    # ── --list mode ───────────────────────────────────────────────────────────
    if list_only:
        print(f"\nRemote listing of /{remote_world}/:")
        try:
            ftp.cwd(remote_world)
            ftp.dir()
            print(f"\n/{remote_world}/region/:")
            ftp.cwd("region")
            entries = ftp.nlst()
            print(f"  {len(entries)} files")
            for e in sorted(entries)[:10]:
                print(f"  {e}")
            if len(entries) > 10:
                print(f"  ... and {len(entries) - 10} more")
        except ftplib.error_perm as e:
            print(f"  FTP error: {e}")
        ftp.quit()
        return

    # ── --verify mode ─────────────────────────────────────────────────────────
    if verify_only:
        print(f"\nVerifying local vs remote checksums in /{remote_world}/region/ ...")
        ftp.voidcmd("TYPE I")
        mismatches = 0
        checked = 0
        for mca in region_files:
            local_md5 = hashlib.md5(mca.read_bytes()).hexdigest()
            try:
                buf = io.BytesIO()
                ftp.retrbinary(f"RETR {remote_world}/region/{mca.name}", buf.write)
                remote_md5 = hashlib.md5(buf.getvalue()).hexdigest()
                checked += 1
                if local_md5 != remote_md5:
                    mismatches += 1
                    print(f"  MISMATCH  {mca.name}  local={local_md5[:8]}  remote={remote_md5[:8]}")
            except ftplib.error_perm:
                print(f"  MISSING   {mca.name}")
                mismatches += 1
        print(f"\nChecked {checked}/{len(region_files)} files, {mismatches} mismatches")
        if mismatches == 0:
            print("All files match — deployment is clean!")
        else:
            print("Files differ — redeploy with server STOPPED")
        ftp.quit()
        return

    # ── Pre-deploy safety check ───────────────────────────────────────────────
    mc_host = host.replace(".node.apexhosting.gdn", "")
    # Try to resolve game server IP from FTP host
    if check_server_running(host.split(".")[0] + ".node.apexhosting.gdn", 25606):
        print("\n⚠  WARNING: Minecraft server appears to be RUNNING!")
        print("   The server will auto-save over uploaded files, causing corruption.")
        print("   Stop the server in the Apex panel first, then re-run this script.")
        resp = input("   Continue anyway? (yes/no): ").strip().lower()
        if resp != "yes":
            print("   Aborted. Stop the server and retry.")
            ftp.quit()
            return

    # ── QA Gate — run world quality tests before deploying ─────────────────
    skip_qa = "--skip-qa" in sys.argv
    force    = "--force" in sys.argv

    if not skip_qa and not dry_run:
        print("\n--- Running World Quality Tests (QA Gate) ---")
        # Determine zone and bbox from .env or defaults
        zone = env.get("DEPLOY_ZONE", "north_davis")
        bbox_str = env.get("DEPLOY_BBOX", "38.560,-121.755,38.572,-121.738")

        # World dir is server/BuildDavis which has region/ and level.dat
        qa_save_dir = WORLD_DIR

        try:
            # Import the test suite from same directory
            sys.path.insert(0, str(Path(__file__).parent))
            from test_world import run_qa, _resolve_bbox

            bbox = tuple(float(x) for x in bbox_str.split(","))
            passed, results, summary = run_qa(zone, qa_save_dir, bbox, verbose=False)

            if not passed:
                print(f"\n!!! QA GATE FAILED: {summary}")
                if force:
                    print("    --force flag set — deploying anyway\n")
                else:
                    print("    Deployment blocked. Fix issues first.")
                    print("    Use --force to deploy anyway, or --skip-qa to bypass.")
                    ftp.quit()
                    return
            else:
                print(f"\n+++ QA GATE PASSED: {summary}\n")
        except Exception as qa_err:
            print(f"\n!!! QA gate error: {qa_err}")
            if force:
                print("    --force flag set — deploying anyway\n")
            else:
                print("    Use --force to deploy anyway, or --skip-qa to bypass.")
                ftp.quit()
                return

    # ── Deploy ────────────────────────────────────────────────────────────────
    if dry_run:
        print("\n=== DRY RUN — no files will be uploaded ===\n")

    remote_region   = f"{remote_world}/region"
    remote_datapacks = f"{remote_world}/datapacks"

    total_files = 0
    total_bytes = 0
    t_start = time.time()

    # 1) Region files
    print(f"\n[1/3] Region files ({len(region_files)} .mca files) -> {remote_region}/")
    ensure_remote_dir(ftp, remote_world)
    ensure_remote_dir(ftp, remote_region)
    for i, mca in enumerate(region_files, 1):
        remote_path = f"{remote_region}/{mca.name}"
        print(f"  [{i:3d}/{len(region_files)}]", end=" ")
        total_bytes += upload_file(ftp, mca, remote_path, dry_run)
        total_files += 1

    if not region_only:
        # 2) level.dat
        print(f"\n[2/3] level.dat -> {remote_world}/level.dat")
        if LEVEL_DAT.exists():
            total_bytes += upload_file(ftp, LEVEL_DAT,
                                       f"{remote_world}/level.dat", dry_run)
            total_files += 1
        else:
            print("  WARNING: level.dat not found — skipping")

        # 3) datapacks
        print(f"\n[3/3] datapacks/ -> {remote_datapacks}/")
        if DATAPACK_DIR.exists():
            f, b = upload_dir_recursive(ftp, DATAPACK_DIR,
                                        remote_datapacks, dry_run)
            total_files += f
            total_bytes += b
        else:
            print("  WARNING: datapacks/ not found — skipping")

    elapsed = time.time() - t_start
    mb = total_bytes / (1024 * 1024)
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Done: {total_files} files, "
          f"{mb:.1f} MB in {elapsed:.1f}s")
    print("\nNext steps:")
    print("  1. Start the server in Apex panel")
    print("  2. Run in console: op Coopdog53")
    print("  3. Connect and: /tp @s 2304 100 3584")
    print(f"  4. Verify: python Code/deploy_apex.py --verify")

    ftp.quit()


if __name__ == "__main__":
    main()
