"""
Generate an .mcfunction file that places the Amtrak station block-by-block.
This bypasses all .nbt/datapack path issues — just run /function builddavis:place_amtrak
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structurize.nbt_writer import StructureBuilder

# Re-run the build to get the StructureBuilder instance
exec(open("build_amtrak_v3.py", encoding="utf-8").read())

# sb is now the populated StructureBuilder from build_amtrak_v3.py

# Placement origin — absolute coordinates
# Station bbox test: lat 38.5317, lon -121.7406
# Arnis bbox 38.528,-121.745,38.536,-121.736
# Arnis scale_factor_x=782, scale_factor_z=889 → MC X=382, Z=477
# Ground level = 49 (Arnis --ground-level 49)
PX, PY, PZ = 382, 49, 477

commands = []

# Clear in smaller chunks to avoid "not loaded" errors
# Split the fill into 4 smaller fills
hw = (sb.width + 2) // 2
commands.append(f"forceload add {PX} {PZ} {PX + sb.width} {PZ + sb.depth}")
commands.append(f"fill {PX} {PY} {PZ} {PX + hw} {PY + sb.height} {PZ + sb.depth} air")
commands.append(f"fill {PX + hw + 1} {PY} {PZ} {PX + sb.width} {PY + sb.height} {PZ + sb.depth} air")

# Then: place each non-air block
count = 0
for x in range(sb.width):
    for y in range(sb.height):
        for z in range(sb.depth):
            bid = sb._grid[x][y][z]
            if bid is not None and bid != "minecraft:air":
                wx = PX + x
                wy = PY + y
                wz = PZ + z
                commands.append(f"setblock {wx} {wy} {wz} {bid}")
                count += 1

print(f"Generated {count} setblock commands")

# Write .mcfunction
mcfunc_path = "place_amtrak.mcfunction"
with open(mcfunc_path, "w") as f:
    f.write("\n".join(commands))
print(f"Written to {mcfunc_path}")
print(f"File size: {os.path.getsize(mcfunc_path) / 1024:.0f} KB")
