"""
Regenerate place_amtrak.mcfunction with corrected coordinates.

Attempt 3: Using verified OSM data from enriched_overpass.json.
  - Davis Station building (way 62095055) centroid: lat=38.543387, lon=-121.737811
  - MC centroid: X=1929, Z=1290
  - Structure 33x19 centered → placement origin: X=1913, Y=49, Z=1281

Previous WRONG placements to clear:
  1. X=1939, Z=1278 (attempt 1 — spawn coords)
  2. X=1677, Z=1156 (attempt 2 — estimated lat/lon)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

# Execute the build script to get the StructureBuilder
ns = {"__file__": os.path.abspath("Code/build_amtrak_v3.py"), "__name__": "__main__"}
with open("Code/build_amtrak_v3.py", encoding="utf-8") as f:
    code = f.read()
exec(compile(code, "Code/build_amtrak_v3.py", "exec"), ns)
sb = ns["sb"]
print(f"Structure: {sb.width}x{sb.depth}x{sb.height}")

# OLD (wrong) coordinates — two failed placements to clear
OLD_1_X, OLD_1_Y, OLD_1_Z = 1939, 49, 1278   # attempt 1: spawn coords
OLD_2_X, OLD_2_Y, OLD_2_Z = 1677, 49, 1156   # attempt 2: estimated lat/lon

# CORRECTED coordinates — from enriched_overpass.json way 62095055 (Davis Station)
# Building centroid: lat=38.543387, lon=-121.737811 → MC X=1929, Z=1290
# Structure 33x19, center at X+16, Z+9 → placement origin:
PX, PY, PZ = 1913, 49, 1281

DATAPACK = os.path.join(
    "server", "BuildDavis", "datapacks", "builddavis",
    "data", "builddavis", "function"
)

# ── Generate undo for BOTH old placements ──
undo_cmds = []

# Clear attempt 1 (1939, 1278)
undo_cmds.append("# Clear attempt 1 (spawn coords)")
undo_cmds.append(f"forceload add {OLD_1_X} {OLD_1_Z} {OLD_1_X + sb.width} {OLD_1_Z + sb.depth}")
mid1 = OLD_1_X + sb.width // 2
undo_cmds.append(f"fill {OLD_1_X} {OLD_1_Y} {OLD_1_Z} {mid1} {OLD_1_Y + sb.height} {OLD_1_Z + sb.depth} air")
undo_cmds.append(f"fill {mid1+1} {OLD_1_Y} {OLD_1_Z} {OLD_1_X + sb.width} {OLD_1_Y + sb.height} {OLD_1_Z + sb.depth} air")
undo_cmds.append(f"forceload remove {OLD_1_X} {OLD_1_Z} {OLD_1_X + sb.width} {OLD_1_Z + sb.depth}")

# Clear attempt 2 (1677, 1156)
undo_cmds.append("# Clear attempt 2 (estimated lat/lon)")
undo_cmds.append(f"forceload add {OLD_2_X} {OLD_2_Z} {OLD_2_X + sb.width} {OLD_2_Z + sb.depth}")
mid2 = OLD_2_X + sb.width // 2
undo_cmds.append(f"fill {OLD_2_X} {OLD_2_Y} {OLD_2_Z} {mid2} {OLD_2_Y + sb.height} {OLD_2_Z + sb.depth} air")
undo_cmds.append(f"fill {mid2+1} {OLD_2_Y} {OLD_2_Z} {OLD_2_X + sb.width} {OLD_2_Y + sb.height} {OLD_2_Z + sb.depth} air")
undo_cmds.append(f"forceload remove {OLD_2_X} {OLD_2_Z} {OLD_2_X + sb.width} {OLD_2_Z + sb.depth}")

undo_cmds.append('tellraw @s {"text":"Cleared both old Amtrak placements","color":"yellow"}')

undo_path = os.path.join(DATAPACK, "undo_amtrak_old.mcfunction")
with open(undo_path, "w") as f:
    f.write("\n".join(undo_cmds))
print(f"Wrote undo (old position) -> {undo_path}")

# ── Generate corrected placement ──
cmds = []
x2 = PX + sb.width
z2 = PZ + sb.depth
cmds.append(f"# Amtrak Station (corrected) - {sb.width}x{sb.depth}x{sb.height}")
cmds.append(f"forceload add {PX} {PZ} {x2} {z2}")

# Clear only the exact footprint ABOVE ground (Y=50+) to remove any Arnis
# building without damaging the ground plane. setblock will overwrite Y=49.
mid = PX + sb.width // 2
cmds.append(f"fill {PX} {PY+1} {PZ} {mid} {PY + sb.height} {z2} air")
cmds.append(f"fill {mid+1} {PY+1} {PZ} {x2} {PY + sb.height} {z2} air")

count = 0
for x in range(sb.width):
    for y in range(sb.height):
        for z in range(sb.depth):
            bid = sb._grid[x][y][z]
            if bid is not None and bid != "minecraft:air":
                cmds.append(f"setblock {PX+x} {PY+y} {PZ+z} {bid}")
                count += 1

cmds.append(f"forceload remove {PX} {PZ} {x2} {z2}")
cmds.append(f'tellraw @s {{"text":"Placed Amtrak Station: {count} blocks","color":"green"}}')

place_path = os.path.join(DATAPACK, "place_amtrak.mcfunction")
with open(place_path, "w") as f:
    f.write("\n".join(cmds))
print(f"Wrote place ({count} blocks) -> {place_path}")
print(f"Origin: X={PX}, Y={PY}, Z={PZ}")

# ── Summary ──
print(f"\n=== IN-GAME STEPS ===")
print(f"1. /reload")
print(f"2. /function builddavis:undo_amtrak_old   (clear old placement)")
print(f"3. /function builddavis:place_amtrak       (place at correct location)")
print(f"4. /tp @s {PX+16} {PY+20} {PZ+10}         (fly to new position)")
