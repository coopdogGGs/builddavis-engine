"""
Davis Amtrak Station — Direct architectural build using StructureBuilder.

Mission Revival style: arched colonnade wrapping front and sides,
stepped parapets, clay tile sloped roof, DAVIS/SP signage.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structurize.nbt_writer import StructureBuilder
from structurize.preview import generate_preview

# ── Block palette ──
WALL  = "minecraft:smooth_sandstone"      # warm sandy adobe walls
WALL2 = "minecraft:sandstone"             # slightly different tone for detail
TRIM  = "minecraft:cut_sandstone"         # cut sandstone for trim/molding
FLOOR = "minecraft:smooth_sandstone"      # interior floor
PLAZA = "minecraft:smooth_stone"          # front plaza ground
ROOF  = "minecraft:brown_terracotta"      # dark brown clay tile roof
EAVE  = "minecraft:spruce_planks"         # dark wooden eave/beam trim
BEAM  = "minecraft:dark_oak_planks"       # exposed beam brackets (vigas)
DOOR  = "minecraft:dark_oak_planks"       # dark entrance doors
GLASS = "minecraft:brown_stained_glass"   # tinted windows
SIGN_BG = "minecraft:black_concrete"      # sign background
SIGN_TXT = "minecraft:white_concrete"     # sign letters
LANTERN = "minecraft:lantern"
MEDAL = "minecraft:polished_andesite"     # clock/medallion
AIR   = "minecraft:air"
PILLAR = "minecraft:smooth_sandstone"     # column/pillar same as wall
IRON  = "minecraft:iron_bars"             # decorative railing

# ── Dimensions ──
W = 31   # x-axis (east-west, along tracks)
D = 17   # z-axis (north-south, street to tracks)
H = 8    # wall height (y=0 floor to y=7 top of wall)
TOTAL_H = 14  # max height including parapets

sb = StructureBuilder(W + 2, TOTAL_H, D + 2)  # +2 for roof overhang
OX, OZ = 1, 1  # offset for overhang padding

# ═══════════════════════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════════════════════

def put(x, y, z, block):
    """Place a block with offset."""
    sb.set_block(x + OX, y, z + OZ, block)

def fill(x1, y1, z1, x2, y2, z2, block):
    """Fill a region with offset."""
    for x in range(min(x1,x2), max(x1,x2)+1):
        for y in range(min(y1,y2), max(y1,y2)+1):
            for z in range(min(z1,z2), max(z1,z2)+1):
                put(x, y, z, block)

def arch_opening(fixed_axis, fixed_val, var_start, var_end, y_base, y_top, depth_axis, depth_start, depth_end):
    """
    Cut an arch-shaped opening with a rounded top.
    fixed_axis: 'x' or 'z' — which axis the wall is on
    fixed_val: the position on that axis
    var_start/var_end: range on the variable axis (the width of the arch)
    y_base/y_top: vertical range
    depth_axis/depth_start/depth_end: depth through the wall
    """
    opening_w = var_end - var_start + 1

    for d in range(depth_start, depth_end + 1):
        # Full opening from y_base to y_top-1
        for v in range(var_start, var_end + 1):
            for y in range(y_base, y_top):
                if fixed_axis == 'z':
                    put(v, y, d, AIR)
                else:
                    put(d, y, v, AIR)

        # Arch curve at y_top: narrow by 1 on each side (if wide enough)
        if opening_w >= 3:
            for v in range(var_start + 1, var_end):
                if fixed_axis == 'z':
                    put(v, y_top, d, AIR)
                else:
                    put(d, y_top, v, AIR)

        # Extra arch curve: if arch is >= 5 wide, add another layer
        if opening_w >= 5:
            for v in range(var_start + 2, var_end - 1):
                if fixed_axis == 'z':
                    put(v, y_top + 1, d, AIR)
                else:
                    put(d, y_top + 1, v, AIR)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. FLOOR (y=0)
# ═══════════════════════════════════════════════════════════════════════════════
fill(0, 0, 0, W-1, 0, D-1, FLOOR)

# ═══════════════════════════════════════════════════════════════════════════════
# 2. OUTER WALLS — full perimeter walls (we'll cut arches after)
# ═══════════════════════════════════════════════════════════════════════════════
# Front wall (z=0)
fill(0, 1, 0, W-1, H-1, 0, WALL)
# Back wall (z=D-1)
fill(0, 1, D-1, W-1, H-1, D-1, WALL)
# Left wall (x=0)
fill(0, 1, 0, 0, H-1, D-1, WALL)
# Right wall (x=W-1)
fill(W-1, 1, 0, W-1, H-1, D-1, WALL)

# ═══════════════════════════════════════════════════════════════════════════════
# 3. INNER BUILDING WALLS (the enclosed core behind the arcade)
# ═══════════════════════════════════════════════════════════════════════════════
# The arcade is 3 blocks deep on front (z=0,1,2) and sides (x=0,1,2 / x=28,29,30)
# Inner walls define the enclosed building

ARCADE_DEPTH = 3

# Inner front wall (z = ARCADE_DEPTH)
fill(ARCADE_DEPTH, 1, ARCADE_DEPTH, W-1-ARCADE_DEPTH, H-1, ARCADE_DEPTH, WALL)
# Inner left wall (x = ARCADE_DEPTH)
fill(ARCADE_DEPTH, 1, ARCADE_DEPTH, ARCADE_DEPTH, H-1, D-1, WALL)
# Inner right wall (x = W-1-ARCADE_DEPTH)
fill(W-1-ARCADE_DEPTH, 1, ARCADE_DEPTH, W-1-ARCADE_DEPTH, H-1, D-1, WALL)

# ═══════════════════════════════════════════════════════════════════════════════
# 4. ARCADE CEILING (y=H-1 over the colonnade area)
# ═══════════════════════════════════════════════════════════════════════════════
# Front arcade ceiling
fill(0, H-1, 0, W-1, H-1, ARCADE_DEPTH-1, WALL)
# Left arcade ceiling
fill(0, H-1, 0, ARCADE_DEPTH-1, H-1, D-1, WALL)
# Right arcade ceiling
fill(W-1-ARCADE_DEPTH+1, H-1, 0, W-1, H-1, D-1, WALL)

# Also fill arcade interior with air explicitly (clear any overlap)
# Front arcade interior
fill(1, 1, 1, W-2, H-2, ARCADE_DEPTH-1, AIR)
# Left arcade interior
fill(1, 1, 1, ARCADE_DEPTH-1, H-2, D-2, AIR)
# Right arcade interior
fill(W-ARCADE_DEPTH, 1, 1, W-2, H-2, D-2, AIR)

# Main building interior
fill(ARCADE_DEPTH+1, 1, ARCADE_DEPTH+1, W-1-ARCADE_DEPTH-1, H-2, D-2, AIR)

# ═══════════════════════════════════════════════════════════════════════════════
# 5. CUT ARCHES — Front face (z=0), 5 arches
# ═══════════════════════════════════════════════════════════════════════════════
# Front arch layout (x positions):
# x=0:      left end pillar
# x=1-4:    arch 1 (4 wide)
# x=5-6:    pillar
# x=7-10:   arch 2 (4 wide)
# x=11-12:  pillar
# x=13-17:  center arch (5 wide, taller)
# x=18-19:  pillar
# x=20-23:  arch 4 (4 wide)
# x=24-25:  pillar
# x=26-29:  arch 5 (4 wide)
# x=30:     right end pillar

FRONT_ARCHES = [
    (1,  4,  5),   # arch 1: x=1..4, 4 wide, normal height
    (7,  10, 5),   # arch 2: x=7..10
    (13, 17, 6),   # center: x=13..17, 5 wide, taller
    (20, 23, 5),   # arch 4: x=20..23
    (26, 29, 5),   # arch 5: x=26..29
]

for ax1, ax2, atop in FRONT_ARCHES:
    # Cut through outer wall (z=0) and into arcade space (z=0 only for wall)
    arch_opening('z', 0, ax1, ax2, 1, atop, 'z', 0, 0)

# Also cut matching openings in the inner wall (z=ARCADE_DEPTH) for doorways
# Center entrance gets a door opening in the inner wall
arch_opening('z', ARCADE_DEPTH, 13, 17, 1, 6, 'z', ARCADE_DEPTH, ARCADE_DEPTH)
# Side arches get smaller openings into the building
for ax1, ax2 in [(1,4), (7,10), (20,23), (26,29)]:
    arch_opening('z', ARCADE_DEPTH, ax1+1, ax2-1, 1, 4, 'z', ARCADE_DEPTH, ARCADE_DEPTH)

# ═══════════════════════════════════════════════════════════════════════════════
# 6. CUT ARCHES — Left side (x=0), 4 arches
# ═══════════════════════════════════════════════════════════════════════════════
LEFT_ARCHES = [
    (1,  3,  5),   # z=1..3
    (5,  7,  5),   # z=5..7
    (9,  11, 5),   # z=9..11
    (13, 15, 5),   # z=13..15
]

for az1, az2, atop in LEFT_ARCHES:
    arch_opening('x', 0, az1, az2, 1, atop, 'x', 0, 0)

# Inner left wall openings
for az1, az2 in [(1,3), (5,7), (9,11), (13,15)]:
    arch_opening('x', ARCADE_DEPTH, az1, az2, 1, 4, 'x', ARCADE_DEPTH, ARCADE_DEPTH)

# ═══════════════════════════════════════════════════════════════════════════════
# 7. CUT ARCHES — Right side (x=W-1), 4 arches
# ═══════════════════════════════════════════════════════════════════════════════
for az1, az2, atop in LEFT_ARCHES:
    arch_opening('x', W-1, az1, az2, 1, atop, 'x', W-1, W-1)

for az1, az2 in [(1,3), (5,7), (9,11), (13,15)]:
    arch_opening('x', W-1-ARCADE_DEPTH, az1, az2, 1, 4, 'x', W-1-ARCADE_DEPTH, W-1-ARCADE_DEPTH)

# ═══════════════════════════════════════════════════════════════════════════════
# 8. BACK WALL — solid with a few windows and a door
# ═══════════════════════════════════════════════════════════════════════════════
# Back door
fill(14, 1, D-1, 16, 4, D-1, DOOR)
# Back windows
for wx in [5, 10, 20, 25]:
    fill(wx, 3, D-1, wx+2, 5, D-1, GLASS)

# ═══════════════════════════════════════════════════════════════════════════════
# 9. SLOPED ROOF — hipped, dark brown clay tile
# ═══════════════════════════════════════════════════════════════════════════════
# The roof sits on top of the walls (y=H) and slopes inward.
# Using a hipped roof: all 4 sides slope inward.

roof_y = H
inset = 0
# Overhang: extend 1 block beyond walls
start_x, end_x = -1, W
start_z, end_z = -1, D

while start_x + inset <= end_x - inset and start_z + inset <= end_z - inset:
    y = roof_y + inset
    x1 = start_x + inset
    x2 = end_x - inset
    z1 = start_z + inset
    z2 = end_z - inset

    for x in range(x1, x2 + 1):
        put(x, y, z1, ROOF)
        put(x, y, z2, ROOF)
    for z in range(z1 + 1, z2):
        put(x1, y, z, ROOF)
        put(x2, y, z, ROOF)

    inset += 1

# Fill the very top ridge if there's a gap
ridge_y = roof_y + inset - 1
if start_x + inset - 1 <= end_x - inset + 1:
    for x in range(start_x + inset - 1, end_x - inset + 2):
        for z in range(start_z + inset - 1, end_z - inset + 2):
            put(x, ridge_y, z, ROOF)

# ═══════════════════════════════════════════════════════════════════════════════
# 10. DARK WOOD EAVE TRIM — beam brackets along top of walls
# ═══════════════════════════════════════════════════════════════════════════════
# Continuous eave beam at y=H-1 (top of wall), outer face
# Front eave
for x in range(W):
    put(x, H-1, 0, EAVE)
# Back eave
for x in range(W):
    put(x, H-1, D-1, EAVE)
# Left eave
for z in range(D):
    put(0, H-1, z, EAVE)
# Right eave
for z in range(D):
    put(W-1, H-1, z, EAVE)

# Exposed beam brackets (vigas) sticking out at y=H-2 along front
for x in range(0, W, 3):
    put(x, H-2, 0, BEAM)
# And along sides
for z in range(0, D, 3):
    put(0, H-2, z, BEAM)
    put(W-1, H-2, z, BEAM)

# ═══════════════════════════════════════════════════════════════════════════════
# 11. PARAPETS — Mission Revival stepped facades
# ═══════════════════════════════════════════════════════════════════════════════

# Central parapet (front face, above the entrance)
# Rising stepped arch shape
parapet_profile = [
    (11, 19, H),      # base: wide
    (12, 18, H + 1),  # step in
    (13, 17, H + 2),  # step in
    (14, 16, H + 3),  # near peak
    (15, 15, H + 4),  # peak block
]
for x1p, x2p, yp in parapet_profile:
    for x in range(x1p, x2p + 1):
        for dz in range(2):  # 2 blocks thick
            put(x, yp, dz, WALL)

# Left wing parapet (smaller "SP" section)
left_parapet = [
    (2, 8,  H),
    (3, 7,  H + 1),
    (4, 6,  H + 2),
]
for x1p, x2p, yp in left_parapet:
    for x in range(x1p, x2p + 1):
        for dz in range(2):
            put(x, yp, dz, WALL)

# Right wing parapet (mirror of left)
right_parapet = [
    (22, 28, H),
    (23, 27, H + 1),
    (24, 26, H + 2),
]
for x1p, x2p, yp in right_parapet:
    for x in range(x1p, x2p + 1):
        for dz in range(2):
            put(x, yp, dz, WALL)

# ═══════════════════════════════════════════════════════════════════════════════
# 12. SIGNAGE
# ═══════════════════════════════════════════════════════════════════════════════

# "DAVIS" sign — centered above entrance on main parapet
# Sign background (dark rectangle)
fill(13, H+1, 0, 17, H+1, 0, SIGN_BG)
# Letters (simplified: white blocks for "D A V I S" — 5 letters across 5 blocks)
for sx in range(13, 18):
    put(sx, H+1, 0, SIGN_TXT)
# Re-do the background 1 row below and put text on it
fill(13, H, 0, 17, H, 0, SIGN_BG)
fill(14, H, 0, 16, H, 0, SIGN_TXT)  # "DAVIS" approximation

# "SP" sign on left wing parapet
fill(4, H, 0, 6, H, 0, SIGN_BG)
fill(4, H, 0, 5, H, 0, SIGN_TXT)  # "SP" (2 letter blocks)

# ═══════════════════════════════════════════════════════════════════════════════
# 13. DECORATIVE DETAILS
# ═══════════════════════════════════════════════════════════════════════════════

# Clock/medallion above entrance
put(15, 6, 0, MEDAL)

# Lanterns flanking the entrance
put(12, 5, 0, LANTERN)
put(18, 5, 0, LANTERN)

# Lanterns along the arcade
for x in [5, 11, 19, 25]:
    put(x, 5, 0, LANTERN)

# Decorative trim/molding line at mid-wall (y=4 or y=5)
for x in range(W):
    put(x, 4, 0, TRIM)  # front horizontal trim band

# Corner pilaster trim (slightly raised columns at wing edges)
for y in range(1, H):
    put(0, y, 0, TRIM)
    put(W-1, y, 0, TRIM)

# ═══════════════════════════════════════════════════════════════════════════════
# 14. ENTRANCE DOORS
# ═══════════════════════════════════════════════════════════════════════════════
# Place dark doors in the center arch on the inner wall
fill(14, 1, ARCADE_DEPTH, 16, 5, ARCADE_DEPTH, DOOR)
# Glass transom above door
fill(14, 5, ARCADE_DEPTH, 16, 6, ARCADE_DEPTH, GLASS)

# ═══════════════════════════════════════════════════════════════════════════════
# 15. FRONT PLAZA (ground in front of building)
# ═══════════════════════════════════════════════════════════════════════════════
# Extend the floor 1 block out front (in the overhang area)
for x in range(W):
    put(x, 0, -1, PLAZA)

# ═══════════════════════════════════════════════════════════════════════════════
# Done — save and preview
# ═══════════════════════════════════════════════════════════════════════════════

nbt_path = "davis_amtrak_v2.nbt"
sb.save(nbt_path)

# Count placed blocks
count = sum(
    1 for x in range(sb.width) for y in range(sb.height) for z in range(sb.depth)
    if sb._grid[x][y][z] is not None
)
print(f"Davis Amtrak Station v2")
print(f"  Dimensions: {W}×{D} footprint, {TOTAL_H} tall")
print(f"  Blocks placed: {count}")
print(f"  Structure: {nbt_path}")

preview_path = "davis_amtrak_v2_preview.html"
generate_preview(sb, preview_path, title="Davis Amtrak Station — Mission Revival")
print(f"  Preview: {preview_path}")
