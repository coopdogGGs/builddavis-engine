"""
Davis Amtrak Station v3 — Direct architectural build using StructureBuilder.

Mission Revival style: arched colonnade wrapping front and sides,
curved parapets, clay tile gabled-hip roof, DAVIS/SP/Amtrak signage.

Reference images studied:
  - Front straight-on: 5 arches, DAVIS sign on central parapet, dark doors
  - Front-left angle: arcade wraps around sides, clay tile hipped roof visible
  - Back/platform side: 4 arches, SP curved parapet, 2 louvered upper windows,
    small square corbels, Amtrak sign, dark beam brackets
  - Aerial: gabled-hip roof with ridge running east-west, 3 curved parapets
    rising above roofline (center DAVIS, left SP, right mirror)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structurize.nbt_writer import StructureBuilder
from structurize.preview import generate_preview

# ── Block palette ──
WALL   = "minecraft:white_terracotta"      # warm peach/salmon stucco (210,178,161)
WALL_D = "minecraft:orange_terracotta"     # slightly darker stucco for shadow/depth
TRIM   = "minecraft:pink_terracotta"       # trim/molding (162,78,79) warm accent
FLOOR  = "minecraft:white_terracotta"      # interior floor matches walls
PLAZA  = "minecraft:smooth_stone"          # front plaza ground
ROOF   = "minecraft:brown_terracotta"      # dark brown clay tile roof
EAVE   = "minecraft:spruce_planks"         # dark wooden eave/beam trim
BEAM   = "minecraft:dark_oak_planks"       # exposed beam brackets (vigas)
DOOR   = "minecraft:dark_oak_planks"       # dark entrance doors
GLASS  = "minecraft:brown_stained_glass"   # tinted windows
SHUTTER= "minecraft:spruce_planks"         # louvered window shutters (dark wood)
SIGN_BG = "minecraft:black_concrete"       # sign background
SIGN_TXT = "minecraft:white_concrete"      # sign letters
SP_BG  = "minecraft:gray_concrete"         # SP medallion bg (gray-green)
SP_TXT = "minecraft:light_gray_concrete"   # SP letters
LANTERN = "minecraft:lantern"
MEDAL  = "minecraft:polished_andesite"     # clock/medallion
AIR    = "minecraft:air"
CORBEL = "minecraft:spruce_planks"         # small square corbel blocks

# ── Dimensions ──
# The building is roughly 90ft × 50ft real-life.
# At 1:1 scale (1 block ≈ 1 meter ≈ 3.3ft): ~27×15 meters
W = 31   # x-axis (east-west, along tracks)
D = 17   # z-axis (north-south, front=z=0, back/tracks=z=D-1)
H = 9    # wall height (y=0 floor to y=8 top of wall)
TOTAL_H = 16  # max height including parapets + roof peak

sb = StructureBuilder(W + 2, TOTAL_H, D + 2)  # +2 for roof overhang
OX, OZ = 1, 1  # offset for overhang padding

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def put(x, y, z, block):
    sb.set_block(x + OX, y, z + OZ, block)

def fill(x1, y1, z1, x2, y2, z2, block):
    for x in range(min(x1,x2), max(x1,x2)+1):
        for y in range(min(y1,y2), max(y1,y2)+1):
            for z in range(min(z1,z2), max(z1,z2)+1):
                put(x, y, z, block)

def arch_cut(fixed_axis, fixed_val, var_start, var_end, y_base, y_top):
    """Cut an arch-shaped opening with a rounded top."""
    w = var_end - var_start + 1
    # Rectangular part
    for v in range(var_start, var_end + 1):
        for y in range(y_base, y_top):
            if fixed_axis == 'z':
                put(v, y, fixed_val, AIR)
            else:
                put(fixed_val, y, v, AIR)
    # Arch curve at top: narrow by 1 each side
    if w >= 3:
        for v in range(var_start + 1, var_end):
            if fixed_axis == 'z':
                put(v, y_top, fixed_val, AIR)
            else:
                put(fixed_val, y_top, v, AIR)
    if w >= 5:
        for v in range(var_start + 2, var_end - 1):
            if fixed_axis == 'z':
                put(v, y_top + 1, fixed_val, AIR)
            else:
                put(fixed_val, y_top + 1, v, AIR)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. FLOOR
# ═══════════════════════════════════════════════════════════════════════════════
fill(0, 0, 0, W-1, 0, D-1, FLOOR)

# ═══════════════════════════════════════════════════════════════════════════════
# 2. OUTER WALLS — full perimeter
# ═══════════════════════════════════════════════════════════════════════════════
fill(0, 1, 0, W-1, H-1, 0, WALL)       # front (z=0)
fill(0, 1, D-1, W-1, H-1, D-1, WALL)   # back (z=D-1)
fill(0, 1, 0, 0, H-1, D-1, WALL)       # left (x=0)
fill(W-1, 1, 0, W-1, H-1, D-1, WALL)   # right (x=W-1)

# ═══════════════════════════════════════════════════════════════════════════════
# 3. INNER WALLS — enclosed core behind the 3-deep arcade
# ═══════════════════════════════════════════════════════════════════════════════
AD = 3  # arcade depth

# Inner front wall
fill(AD, 1, AD, W-1-AD, H-1, AD, WALL)
# Inner left wall
fill(AD, 1, AD, AD, H-1, D-1, WALL)
# Inner right wall
fill(W-1-AD, 1, AD, W-1-AD, H-1, D-1, WALL)

# ═══════════════════════════════════════════════════════════════════════════════
# 4. ARCADE CEILINGS + CLEAR INTERIORS
# ═══════════════════════════════════════════════════════════════════════════════
# Arcade ceiling
fill(0, H-1, 0, W-1, H-1, AD-1, WALL)
fill(0, H-1, 0, AD-1, H-1, D-1, WALL)
fill(W-AD, H-1, 0, W-1, H-1, D-1, WALL)

# Clear arcade interiors
fill(1, 1, 1, W-2, H-2, AD-1, AIR)   # front arcade
fill(1, 1, 1, AD-1, H-2, D-2, AIR)   # left arcade
fill(W-AD, 1, 1, W-2, H-2, D-2, AIR) # right arcade

# Clear main interior
fill(AD+1, 1, AD+1, W-1-AD-1, H-2, D-2, AIR)

# ═══════════════════════════════════════════════════════════════════════════════
# 5. DEFINE ARCH POSITIONS (cut later, after all decorative elements)
# ═══════════════════════════════════════════════════════════════════════════════

# Front arches: x=0 pillar | 1-4 | pillar 5 | 6-9 | pillar 10-11
# | center 12-18 | pillar 19-20 | 21-24 | pillar 25 | 26-29 | pillar 30
FRONT_ARCHES = [
    (1,  4,  5),   # arch 1
    (6,  9,  5),   # arch 2
    (12, 18, 6),   # center (7 wide, taller)
    (21, 24, 5),   # arch 4
    (26, 29, 5),   # arch 5
]

# Back arches (platform side)
BACK_ARCHES = [
    (3,  7,  5),   # arch 1
    (10, 14, 6),   # arch 2 (center-left, taller)
    (16, 20, 6),   # arch 3 (center-right)
    (23, 27, 5),   # arch 4
]

# Side arches (left and right)
SIDE_ARCHES = [
    (1,  3,  5),
    (5,  7,  5),
    (9,  11, 5),
    (13, 15, 5),
]

# ═══════════════════════════════════════════════════════════════════════════════
# 9. BACK SIDE — upper louvered windows (SP wing back view)
# ═══════════════════════════════════════════════════════════════════════════════
# Two louvered windows on upper wall of the SP/left wing
for wx in [4, 8]:
    fill(wx, 6, D-1, wx+2, 7, D-1, SHUTTER)
# Two on the right wing too
for wx in [20, 24]:
    fill(wx, 6, D-1, wx+2, 7, D-1, SHUTTER)

# ═══════════════════════════════════════════════════════════════════════════════
# 10. GABLED-HIP ROOF (from aerial view)
# ═══════════════════════════════════════════════════════════════════════════════
# Ridge runs east-west (along X). Hipped at the ends.
# Overhang 1 block on all sides.

roof_base = H  # y=9

# First layer: full rectangle with 1-block overhang
for x in range(-1, W+1):
    for z in range(-1, D+1):
        put(x, roof_base, z, ROOF)

# Gable layers: slopes in from north and south (z-axis) toward ridge
# Ridge is at z = D//2 = 8
ridge_z = D // 2
max_rise = ridge_z + 1  # how many layers until ridge

for layer in range(1, max_rise + 1):
    y = roof_base + layer
    z1 = -1 + layer
    z2 = D - layer

    if z1 > z2:
        z1 = z2 = ridge_z

    # Hip: also shrink x by layer, but more slowly (hipped at ends only)
    x_shrink = max(0, layer - 3)  # hips start closing after 3 layers
    x1 = -1 + x_shrink
    x2 = W + 1 - 1 - x_shrink

    if x1 > x2:
        break

    for x in range(x1, x2 + 1):
        put(x, y, z1, ROOF)
        if z2 != z1:
            put(x, y, z2, ROOF)

    # Fill the ridge line (all x at z=ridge_z for this y level)
    if z1 == z2:
        for x in range(x1, x2 + 1):
            put(x, y, z1, ROOF)

# ═══════════════════════════════════════════════════════════════════════════════
# 11. DARK WOOD EAVE TRIM + BEAM BRACKETS
# ═══════════════════════════════════════════════════════════════════════════════
# Continuous eave trim at top of wall
for x in range(W):
    put(x, H-1, 0, EAVE)
    put(x, H-1, D-1, EAVE)
for z in range(D):
    put(0, H-1, z, EAVE)
    put(W-1, H-1, z, EAVE)

# Exposed beam brackets (vigas) — sticking out below eave, every 2-3 blocks
for x in range(1, W-1, 2):
    put(x, H-2, 0, BEAM)      # front
    put(x, H-2, D-1, BEAM)    # back
for z in range(1, D-1, 2):
    put(0, H-2, z, BEAM)      # left side
    put(W-1, H-2, z, BEAM)    # right side

# ═══════════════════════════════════════════════════════════════════════════════
# 12. SMALL SQUARE CORBELS — decorative blocks dotting upper wall
# (visible in back and side photos)
# ═══════════════════════════════════════════════════════════════════════════════
# Front wall corbels at y=6
for x in range(2, W-1, 4):
    put(x, 6, 0, CORBEL)
# Back wall corbels at y=6
for x in range(2, W-1, 4):
    put(x, 6, D-1, CORBEL)
# Side wall corbels
for z in range(2, D-1, 4):
    put(0, 6, z, CORBEL)
    put(W-1, 6, z, CORBEL)

# ═══════════════════════════════════════════════════════════════════════════════
# 13. PARAPETS — smooth curved Mission Revival facades
# ═══════════════════════════════════════════════════════════════════════════════

# Central parapet (front, above entrance) — wider curved arch
# Curved profile: semicircle-ish shape, widest at base
# The profile rises from x=10 to x=20, peaking around y=H+5

def curved_parapet(cx, half_w, peak_h, z_start, z_end):
    """Draw a curved parapet centered at cx, with half_w blocks on each side."""
    for dy in range(peak_h + 1):
        # Circle-ish: width = half_w * sqrt(1 - (dy/peak)^2)
        import math
        ratio = dy / peak_h if peak_h > 0 else 0
        cur_half = round(half_w * math.sqrt(max(0, 1 - ratio * ratio)))
        if cur_half < 1 and dy < peak_h:
            cur_half = 1
        y = H + dy
        for x in range(cx - cur_half, cx + cur_half + 1):
            if 0 <= x < W:
                for z in range(z_start, z_end + 1):
                    put(x, y, z, WALL)

# Central DAVIS parapet
curved_parapet(15, 6, 5, 0, 1)

# Left SP parapet (smaller)
curved_parapet(5, 4, 4, 0, 1)

# Right parapet (mirror of left)
curved_parapet(25, 4, 4, 0, 1)

# Trim lines on parapets (horizontal accent bands near top)
# Central parapet trim
for x in range(10, 21):
    put(x, H, 0, TRIM)      # base trim
    put(x, H+1, 0, TRIM)    # second trim line
# Left parapet trim
for x in range(2, 9):
    put(x, H, 0, TRIM)
    put(x, H+1, 0, TRIM)
# Right parapet trim
for x in range(22, 29):
    put(x, H, 0, TRIM)
    put(x, H+1, 0, TRIM)

# ═══════════════════════════════════════════════════════════════════════════════
# 14. SIGNAGE
# ═══════════════════════════════════════════════════════════════════════════════

# "DAVIS" sign — on central parapet, front face
# Background rectangle
fill(13, H+3, 0, 17, H+3, 0, SIGN_BG)
# White letter blocks
for x in range(13, 18):
    put(x, H+3, 0, SIGN_TXT)

# "SP" oval/rectangle sign — on left parapet
fill(4, H+2, 0, 6, H+2, 0, SP_BG)
put(4, H+2, 0, SP_TXT)
put(5, H+2, 0, SP_TXT)
put(6, H+2, 0, SP_BG)  # border

# "Amtrak" sign — on back wall, left side
fill(2, 5, D-1, 5, 5, D-1, SIGN_BG)
fill(2, 5, D-1, 4, 5, D-1, SIGN_TXT)

# ═══════════════════════════════════════════════════════════════════════════════
# 15. ENTRANCE DETAILS
# ═══════════════════════════════════════════════════════════════════════════════

# Clock/medallion above entrance on outer wall
put(15, 6, 0, MEDAL)

# Lanterns flanking entrance
put(11, 5, 0, LANTERN)
put(19, 5, 0, LANTERN)

# Lanterns along the arcade colonnade
for x in [5, 25]:
    put(x, 5, 0, LANTERN)

# ═══════════════════════════════════════════════════════════════════════════════
# 16. FRONT PILLAR EMPHASIS (between arches — slightly thicker pillars)
# ═══════════════════════════════════════════════════════════════════════════════
# Reinforce the pillars between arches to read as columns
pillar_centers_front = [0, 5, 10, 11, 19, 20, 25, 30]
for px in pillar_centers_front:
    for y in range(1, H-1):
        put(px, y, 0, WALL)
        put(px, y, 1, WALL)
        put(px, y, 2, WALL)

# ═══════════════════════════════════════════════════════════════════════════════
# 17. HORIZONTAL TRIM BAND (decorative molding at ~mid-wall height)
# ═══════════════════════════════════════════════════════════════════════════════
# Visible in photos as a continuous horizontal line around the building
# Front
for x in range(W):
    put(x, 5, 0, TRIM)
# Back
for x in range(W):
    put(x, 5, D-1, TRIM)
# Sides
for z in range(D):
    put(0, 5, z, TRIM)
    put(W-1, 5, z, TRIM)

# ═══════════════════════════════════════════════════════════════════════════════
# 18. FRONT PLAZA
# ═══════════════════════════════════════════════════════════════════════════════
for x in range(W):
    put(x, 0, -1, PLAZA)

# ═══════════════════════════════════════════════════════════════════════════════
# 19. CUT ALL ARCHES (LAST — so nothing overwrites them)
# ═══════════════════════════════════════════════════════════════════════════════

# --- Front arches (z=0) + arcade depth (z=1, z=2) ---
for ax1, ax2, atop in FRONT_ARCHES:
    # Cut through outer wall
    arch_cut('z', 0, ax1, ax2, 1, atop)
    # Cut through arcade depth
    for z in range(1, AD):
        for x in range(ax1, ax2+1):
            for y in range(1, atop):
                put(x, y, z, AIR)
        w = ax2 - ax1 + 1
        if w >= 3:
            for x in range(ax1+1, ax2):
                put(x, atop, z, AIR)
        if w >= 5:
            for x in range(ax1+2, ax2-1):
                put(x, atop+1, z, AIR)
    # Inner wall openings
    arch_cut('z', AD, ax1+1, ax2-1, 1, min(atop, 5))

# --- Back arches (z=D-1) ---
for ax1, ax2, atop in BACK_ARCHES:
    arch_cut('z', D-1, ax1, ax2, 1, atop)

# --- Left side arches (x=0) + arcade depth ---
for az1, az2, atop in SIDE_ARCHES:
    arch_cut('x', 0, az1, az2, 1, atop)
    for x in range(1, AD):
        for z in range(az1, az2+1):
            for y in range(1, atop):
                put(x, y, z, AIR)
        w = az2 - az1 + 1
        if w >= 3:
            for z in range(az1+1, az2):
                put(x, atop, z, AIR)
    arch_cut('x', AD, az1, az2, 1, min(atop, 4))

# --- Right side arches (x=W-1) + arcade depth ---
for az1, az2, atop in SIDE_ARCHES:
    arch_cut('x', W-1, az1, az2, 1, atop)
    for x in range(W-AD, W-1):
        for z in range(az1, az2+1):
            for y in range(1, atop):
                put(x, y, z, AIR)
        w = az2 - az1 + 1
        if w >= 3:
            for z in range(az1+1, az2):
                put(x, atop, z, AIR)
    arch_cut('x', W-1-AD, az1, az2, 1, min(atop, 4))

# ═══════════════════════════════════════════════════════════════════════════════
# 20. RE-PLACE DOORS + DETAILS (after arch cuts so they don't get erased)
# ═══════════════════════════════════════════════════════════════════════════════
# Dark entrance doors in center arch (inner wall, z=AD)
fill(14, 1, AD, 16, 5, AD, DOOR)
# Glass transom above door
fill(14, 6, AD, 16, 6, AD, GLASS)
# Back door
fill(14, 1, D-1, 16, 4, D-1, DOOR)

# ═══════════════════════════════════════════════════════════════════════════════
# DONE — save and preview
# ═══════════════════════════════════════════════════════════════════════════════

nbt_path = "davis_amtrak_v3.nbt"
sb.save(nbt_path)

count = sum(
    1 for x in range(sb.width) for y in range(sb.height) for z in range(sb.depth)
    if sb._grid[x][y][z] is not None
)
print(f"Davis Amtrak Station v3")
print(f"  Dimensions: {W}×{D} footprint, {TOTAL_H} tall")
print(f"  Blocks placed: {count}")
print(f"  Structure: {nbt_path}")

preview_path = "davis_amtrak_v3_preview.html"
generate_preview(sb, preview_path, title="Davis Amtrak Station — Mission Revival v3")
print(f"  Preview: {preview_path}")
