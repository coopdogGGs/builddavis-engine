"""BuildDavis — Server Management Console

All-in-one CLI for managing the Paper Minecraft server from VS Code terminal.

Usage:
  python Code/server_mgr.py start              # Start the server (background)
  python Code/server_mgr.py stop               # Graceful stop via RCON
  python Code/server_mgr.py restart             # Stop + start
  python Code/server_mgr.py status              # Check if server is running
  python Code/server_mgr.py cmd "say Hello"     # Run any server command
  python Code/server_mgr.py players             # List online players
  python Code/server_mgr.py logs                # Tail server log (live)
  python Code/server_mgr.py logs --last 50      # Print last N lines
  python Code/server_mgr.py backup              # Snapshot world + announce
  python Code/server_mgr.py deploy <world_dir>  # Deploy world to server
  python Code/server_mgr.py world               # Show active world name
  python Code/server_mgr.py world <name>        # Switch active world
  python Code/server_mgr.py whitelist add <p>    # Add player to whitelist
  python Code/server_mgr.py whitelist remove <p> # Remove player
  python Code/server_mgr.py whitelist list       # Show whitelist
  python Code/server_mgr.py op <player>          # Grant operator
  python Code/server_mgr.py deop <player>        # Revoke operator
  python Code/server_mgr.py plugins              # List installed plugins
  python Code/server_mgr.py tp <player> <x> <y> <z>  # Teleport player
  python Code/server_mgr.py protect <name> <x1> <z1> <x2> <z2>  # WorldGuard region
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WORKSPACE = Path(__file__).resolve().parent.parent
SERVER_DIR = WORKSPACE / "server"
SERVER_JAR = "paper-1.21.11-69.jar"
JAVA_HOME = r"C:\Program Files\Eclipse Adoptium\jdk-21.0.10.7-hotspot"
JAVA_EXE = Path(JAVA_HOME) / "bin" / "java.exe"

RCON_HOST = "127.0.0.1"
RCON_PORT = 25575
RCON_PASS = "REDACTED_RCON_PASS"
SERVER_PORT = 25565

PROPERTIES_FILE = SERVER_DIR / "server.properties"
LOG_FILE = SERVER_DIR / "logs" / "latest.log"
BACKUP_DIR = WORKSPACE / "backups"


# ---------------------------------------------------------------------------
# RCON Client
# ---------------------------------------------------------------------------

class RconError(Exception):
    pass


def _rcon_send(sock: socket.socket, cmd: str, req_id: int = 1) -> str:
    """Send one RCON command and return response body."""
    payload = struct.pack("<ii", req_id, 2) + cmd.encode("utf-8") + b"\x00\x00"
    sock.send(struct.pack("<i", len(payload)) + payload)
    time.sleep(0.3)
    resp = sock.recv(4096)
    if len(resp) < 14:
        return ""
    return resp[12:-2].decode("utf-8", errors="replace")


def rcon_connect() -> socket.socket:
    """Open an authenticated RCON connection."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    try:
        s.connect((RCON_HOST, RCON_PORT))
    except (ConnectionRefusedError, OSError):
        raise RconError("Server not reachable — is it running?")
    # Login packet (type 3)
    payload = struct.pack("<ii", 0, 3) + RCON_PASS.encode() + b"\x00\x00"
    s.send(struct.pack("<i", len(payload)) + payload)
    resp = s.recv(4096)
    resp_id = struct.unpack("<i", resp[4:8])[0]
    if resp_id == -1:
        s.close()
        raise RconError("RCON authentication failed — check password")
    return s


def rcon_cmd(cmd: str) -> str:
    """Run a single RCON command. Returns response text."""
    s = rcon_connect()
    try:
        return _rcon_send(s, cmd)
    finally:
        s.close()


def rcon_cmds(cmds: list[str]) -> list[tuple[str, str]]:
    """Run multiple RCON commands. Returns list of (cmd, response)."""
    s = rcon_connect()
    results = []
    try:
        for i, cmd in enumerate(cmds):
            resp = _rcon_send(s, cmd, req_id=i + 1)
            results.append((cmd, resp))
    finally:
        s.close()
    return results


# ---------------------------------------------------------------------------
# Server properties helpers
# ---------------------------------------------------------------------------

def _read_properties() -> dict[str, str]:
    props = {}
    for line in PROPERTIES_FILE.read_text().splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        props[k] = v
    return props


def _write_property(key: str, value: str) -> None:
    lines = PROPERTIES_FILE.read_text().splitlines()
    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}")
    PROPERTIES_FILE.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Process helpers
# ---------------------------------------------------------------------------

def _is_server_running() -> bool:
    """Check if a Java process is listening on the server port."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((RCON_HOST, SERVER_PORT))
        s.close()
        return True
    except (ConnectionRefusedError, OSError):
        return False


def _is_rcon_up() -> bool:
    try:
        s = rcon_connect()
        s.close()
        return True
    except RconError:
        return False


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_start(args: argparse.Namespace) -> None:
    """Start the Paper server as a background process."""
    if _is_server_running():
        print("⚠  Server already running on port 25565")
        return

    java_args = [
        str(JAVA_EXE),
        "-Xms2G", "-Xmx4G",
        "-jar", SERVER_JAR,
        "--nogui",
    ]
    print(f"Starting server in {SERVER_DIR}...")
    proc = subprocess.Popen(
        java_args,
        cwd=SERVER_DIR,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"  PID: {proc.pid}")

    # Wait for RCON to come up (max 60s)
    print("  Waiting for server to be ready", end="", flush=True)
    for _ in range(60):
        time.sleep(1)
        print(".", end="", flush=True)
        if _is_rcon_up():
            print(f"\n✅ Server started (PID {proc.pid})")
            return
    print("\n⚠  Server process launched but RCON not responding after 60s")
    print("   Check logs: python Code/server_mgr.py logs --last 30")


def cmd_stop(args: argparse.Namespace) -> None:
    """Graceful shutdown via RCON."""
    try:
        print("Sending stop command...")
        rcon_cmd("save-all")
        time.sleep(1)
        rcon_cmd("stop")
        print("✅ Server stopping")
    except RconError as e:
        print(f"⚠  {e}")


def cmd_restart(args: argparse.Namespace) -> None:
    """Stop then start."""
    if _is_server_running():
        cmd_stop(args)
        print("Waiting for shutdown...", end="", flush=True)
        for _ in range(30):
            time.sleep(1)
            print(".", end="", flush=True)
            if not _is_server_running():
                break
        print()
        time.sleep(2)
    cmd_start(args)


def cmd_status(args: argparse.Namespace) -> None:
    """Check server status."""
    running = _is_server_running()
    print(f"Server port 25565: {'🟢 OPEN' if running else '🔴 CLOSED'}")

    if running:
        try:
            resp = rcon_cmd("list")
            print(f"Players: {resp}")
            props = _read_properties()
            print(f"World: {props.get('level-name', '?')}")
            print(f"Gamemode: {props.get('gamemode', '?')}")
            print(f"Difficulty: {props.get('difficulty', '?')}")
            print(f"MOTD: {props.get('motd', '?')}")
        except RconError as e:
            print(f"  RCON: {e}")
    else:
        props = _read_properties()
        print(f"World (configured): {props.get('level-name', '?')}")


def cmd_cmd(args: argparse.Namespace) -> None:
    """Run arbitrary server commands."""
    for c in args.commands:
        try:
            resp = rcon_cmd(c)
            print(f"[{c}] => {resp}")
        except RconError as e:
            print(f"[{c}] ERROR: {e}")


def cmd_players(args: argparse.Namespace) -> None:
    """List online players."""
    try:
        resp = rcon_cmd("list")
        print(resp)
    except RconError as e:
        print(f"⚠  {e}")


def cmd_logs(args: argparse.Namespace) -> None:
    """Tail or print server log."""
    if not LOG_FILE.exists():
        print(f"No log file at {LOG_FILE}")
        return

    if args.last:
        # Print last N lines
        lines = LOG_FILE.read_text(errors="replace").splitlines()
        for line in lines[-args.last:]:
            print(line)
    else:
        # Live tail using PowerShell Get-Content -Wait
        print(f"📜 Tailing {LOG_FILE}  (Ctrl+C to stop)")
        print("-" * 60)
        try:
            proc = subprocess.Popen(
                ["powershell", "-Command",
                 f"Get-Content -Path '{LOG_FILE}' -Tail 20 -Wait"],
                cwd=SERVER_DIR,
            )
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            print("\nStopped tailing.")


def cmd_backup(args: argparse.Namespace) -> None:
    """Create world snapshot with optional in-game announcement."""
    props = _read_properties()
    world_name = props.get("level-name", "world")
    world_dir = SERVER_DIR / world_name

    if not world_dir.exists():
        print(f"⚠  World directory not found: {world_dir}")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{world_name}_{ts}"
    backup_path = BACKUP_DIR / backup_name

    # Save if server is running
    running = _is_rcon_up()
    if running:
        rcon_cmds([
            f'say §e[Backup] Starting world backup...',
            'save-all',
            'save-off',
        ])
        time.sleep(3)

    # Copy world
    BACKUP_DIR.mkdir(exist_ok=True)
    print(f"Copying {world_dir} → {backup_path}")
    shutil.copytree(world_dir, backup_path)
    print(f"✅ Backup saved: {backup_path}")

    # Re-enable saving
    if running:
        rcon_cmds([
            'save-on',
            f'say §a[Backup] Complete! Saved as {backup_name}',
        ])


def cmd_deploy(args: argparse.Namespace) -> None:
    """Deploy a generated world to the server."""
    src = Path(args.world_dir).resolve()
    if not src.exists():
        print(f"⚠  Source not found: {src}")
        return

    target_name = args.name or src.name
    target = SERVER_DIR / target_name

    running = _is_server_running()
    props = _read_properties()
    active_world = props.get("level-name", "")

    if running and active_world == target_name:
        print(f"⚠  World '{target_name}' is currently active!")
        print("   Stop the server first, or deploy to a different name.")
        return

    if target.exists():
        print(f"Removing existing {target}...")
        shutil.rmtree(target)

    print(f"Deploying {src} → {target}")
    shutil.copytree(src, target)
    print(f"✅ Deployed as '{target_name}'")

    if args.activate:
        _write_property("level-name", target_name)
        print(f"   Set as active world in server.properties")
        if running:
            print("   ⚠  Restart server to load the new world")


def cmd_world(args: argparse.Namespace) -> None:
    """Show or switch the active world."""
    props = _read_properties()
    current = props.get("level-name", "?")

    if args.name:
        new_world = args.name
        world_dir = SERVER_DIR / new_world
        if not world_dir.exists():
            # List available worlds
            worlds = [d.name for d in SERVER_DIR.iterdir()
                      if d.is_dir() and (d / "level.dat").exists()]
            print(f"⚠  World '{new_world}' not found in server directory")
            print(f"   Available: {', '.join(worlds)}")
            return

        _write_property("level-name", new_world)
        print(f"World switched: {current} → {new_world}")
        if _is_server_running():
            print("⚠  Restart server to load the new world")
    else:
        print(f"Active world: {current}")
        # List all worlds
        worlds = [d.name for d in SERVER_DIR.iterdir()
                  if d.is_dir() and (d / "level.dat").exists()]
        if worlds:
            print(f"Available: {', '.join(worlds)}")


def cmd_whitelist(args: argparse.Namespace) -> None:
    """Manage whitelist."""
    action = args.action

    if action == "list":
        try:
            resp = rcon_cmd("whitelist list")
            print(resp)
        except RconError:
            # Read from file if server is down
            wl_file = SERVER_DIR / "whitelist.json"
            if wl_file.exists():
                wl = json.loads(wl_file.read_text())
                names = [p.get("name", "?") for p in wl]
                print(f"Whitelist ({len(names)}): {', '.join(names) or '(empty)'}")
    elif action in ("add", "remove"):
        if not args.player:
            print("⚠  Specify a player name")
            return
        try:
            resp = rcon_cmd(f"whitelist {action} {args.player}")
            print(resp)
        except RconError as e:
            print(f"⚠  {e}")
    else:
        print(f"Unknown whitelist action: {action}")


def cmd_op(args: argparse.Namespace) -> None:
    """Grant/revoke operator."""
    cmd_name = "op" if not args.deop else "deop"
    try:
        resp = rcon_cmd(f"{cmd_name} {args.player}")
        print(resp)
    except RconError as e:
        print(f"⚠  {e}")


def cmd_plugins(args: argparse.Namespace) -> None:
    """List installed plugins."""
    plugin_dir = SERVER_DIR / "plugins"
    jars = sorted(plugin_dir.glob("*.jar"))

    print(f"Plugins ({len(jars)}):")
    for jar in jars:
        size_mb = jar.stat().st_size / (1024 * 1024)
        print(f"  {jar.name}  ({size_mb:.1f} MB)")

    if _is_rcon_up():
        print()
        resp = rcon_cmd("plugins")
        print(f"Server reports: {resp}")


def cmd_tp(args: argparse.Namespace) -> None:
    """Teleport a player."""
    try:
        resp = rcon_cmd(f"tp {args.player} {args.x} {args.y} {args.z}")
        print(resp)
    except RconError as e:
        print(f"⚠  {e}")


def cmd_protect(args: argparse.Namespace) -> None:
    """Create a WorldGuard protection region."""
    name = args.name
    cmds = [
        f"//pos1 {args.x1},0,{args.z1}",
        f"//pos2 {args.x2},319,{args.z2}",
        f"rg define {name}",
        f"rg flag {name} build deny",
        f"rg flag {name} block-break deny",
        f"rg flag {name} block-place deny",
        f'say §a[Protection] Region "{name}" created',
    ]
    try:
        results = rcon_cmds(cmds)
        for c, r in results:
            print(f"  [{c}] => {r}")
        print(f"✅ Region '{name}' protected (build/break/place denied)")
    except RconError as e:
        print(f"⚠  {e}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="server_mgr",
        description="BuildDavis Server Management Console",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # start
    sub.add_parser("start", help="Start the Paper server")

    # stop
    sub.add_parser("stop", help="Graceful shutdown via RCON")

    # restart
    sub.add_parser("restart", help="Stop then start")

    # status
    sub.add_parser("status", help="Check server status")

    # cmd
    p = sub.add_parser("cmd", help="Run server command(s)")
    p.add_argument("commands", nargs="+", help="Commands to run")

    # players
    sub.add_parser("players", help="List online players")

    # logs
    p = sub.add_parser("logs", help="Tail or show server log")
    p.add_argument("--last", type=int, help="Show last N lines instead of tailing")

    # backup
    sub.add_parser("backup", help="Snapshot the active world")

    # deploy
    p = sub.add_parser("deploy", help="Deploy a world to the server")
    p.add_argument("world_dir", help="Path to world directory")
    p.add_argument("--name", help="Name in server (default: source dir name)")
    p.add_argument("--activate", action="store_true", help="Set as active world")

    # world
    p = sub.add_parser("world", help="Show/switch active world")
    p.add_argument("name", nargs="?", help="World to switch to")

    # whitelist
    p = sub.add_parser("whitelist", help="Manage whitelist")
    p.add_argument("action", choices=["add", "remove", "list"])
    p.add_argument("player", nargs="?")

    # op
    p = sub.add_parser("op", help="Grant operator")
    p.add_argument("player")

    # deop
    p = sub.add_parser("deop", help="Revoke operator")
    p.add_argument("player")

    # plugins
    sub.add_parser("plugins", help="List installed plugins")

    # tp
    p = sub.add_parser("tp", help="Teleport a player")
    p.add_argument("player")
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)
    p.add_argument("z", type=int)

    # protect
    p = sub.add_parser("protect", help="Create WorldGuard protection region")
    p.add_argument("name", help="Region name")
    p.add_argument("x1", type=int)
    p.add_argument("z1", type=int)
    p.add_argument("x2", type=int)
    p.add_argument("z2", type=int)

    args = parser.parse_args()

    dispatch = {
        "start": cmd_start,
        "stop": cmd_stop,
        "restart": cmd_restart,
        "status": cmd_status,
        "cmd": cmd_cmd,
        "players": cmd_players,
        "logs": cmd_logs,
        "backup": cmd_backup,
        "deploy": cmd_deploy,
        "world": cmd_world,
        "whitelist": cmd_whitelist,
        "op": lambda a: cmd_op(argparse.Namespace(player=a.player, deop=False)),
        "deop": lambda a: cmd_op(argparse.Namespace(player=a.player, deop=True)),
        "plugins": cmd_plugins,
        "tp": cmd_tp,
        "protect": cmd_protect,
    }

    dispatch[args.command](args)


if __name__ == "__main__":
    main()
