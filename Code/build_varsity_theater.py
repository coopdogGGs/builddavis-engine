"""
Varsity Theatre — Streamline Moderne iconic build for BuildDavis.

Art Deco / Streamline Moderne movie theater at 616 2nd Street, Davis.
Key features: cursive VARSITY neon sign, illuminated changeable-letter
marquee, wide projecting canopy with recessed lights, large upper-story
window panels, stepped tower pylon on right (east) side with horizontal
red/blue neon accent stripes.

OSM: way 45208396, building=commercial, amenity=cinema, height=7.0m,
building:levels=2, building:colour=#D1B1A1 (warm salmon).
Real MC coords: python Code/mc_locate.py --osm-id 45208396
"""

import sys, os
import glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structurize.nbt_writer import StructureBuilder
from structurize.preview import generate_preview

# ── Block palette ─────────────────────────────────────────────────────────────
WALL     = "minecraft:white_concrete"           # clean white stucco exterior
TRIM     = "minecraft:smooth_quartz"            # horizontal trim / kickplate
FLOOR    = "minecraft:polished_andesite"        # lobby / interior floor
SIDEWALK = "minecraft:smooth_stone"             # front sidewalk
ROOF     = "minecraft:gray_concrete"            # flat commercial roof
PARAPET  = "minecraft:light_gray_concrete"      # roof-edge parapet cap
CANOPY   = "minecraft:cyan_terracotta"          # canopy surface (teal/green)
SOFFIT   = "minecraft:black_concrete"           # canopy underside (dark)
GLASS    = "minecraft:light_blue_stained_glass"  # ground-floor storefront
GLASS_U  = "minecraft:white_stained_glass"      # upper-story windows
DOOR     = "minecraft:dark_oak_planks"          # entrance doors
MARQUEE  = "minecraft:white_concrete"           # marquee letter-board
MARQ_TXT = "minecraft:black_concrete"           # marquee text detail
POSTER   = "minecraft:brown_concrete"           # poster display backing
SIGN_BG  = "minecraft:gray_concrete"            # sign background strip
SIGN_TXT = "minecraft:white_concrete"           # VARSITY sign lettering
NEON_R   = "minecraft:red_concrete"             # neon accent — red
NEON_B   = "minecraft:blue_concrete"            # neon accent — blue
LIGHT    = "minecraft:sea_lantern"              # recessed canopy lights
LADDER   = "minecraft:ladder[facing=north]"     # service ladder on tower back
AIR      = "minecraft:air"

# ── Dimensions ────────────────────────────────────────────────────────────────
W = 17         # width  (x-axis, along 2nd Street facade)
D = 30         # depth  (z-axis, front z=0 north/2nd St, back z=29 south)
TOTAL_H = 14   # max height (y=0 floor to y=13 tower peak)

# Y layout:
#   0     floor slab
#   1     kickplate / base trim
#   2-3   storefront glass & doors
#   4     upper ground-floor wall / marquee mount
#   5     2nd-floor slab / canopy surface
#   6-7   upper-story windows
#   8     sign band (VARSITY sign area)
#   9     parapet / roof edge
#   10-11 stepped parapet w/ neon (x=6-12)
#   10-13 tower pylon (x=13-16)

sb = StructureBuilder(W + 2, TOTAL_H, D + 2)   # 19 × 14 × 32
OX, OZ = 1, 2   # +1 side padding, +2 front for canopy projection

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def put(x, y, z, block):
    sb.set_block((W - 1 - x) + OX, y, z + OZ, block)  # x-mirrored: tower on right

def fill(x1, y1, z1, x2, y2, z2, block):
    for x in range(min(x1, x2), max(x1, x2) + 1):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            for z in range(min(z1, z2), max(z1, z2) + 1):
                put(x, y, z, block)

# ═══════════════════════════════════════════════════════════════════════════════
# Step 1 — Foundation & floor
# ═══════════════════════════════════════════════════════════════════════════════

fill(0, 0, 0, W - 1, 0, D - 1, FLOOR)        # interior floor
fill(0, 0, -1, W - 1, 0, -2, SIDEWALK)       # front sidewalk

# ═══════════════════════════════════════════════════════════════════════════════
# Step 2 — Exterior walls (y=1 to y=9, all four sides)
# ═══════════════════════════════════════════════════════════════════════════════

fill(0, 1, 0, W - 1, 9, 0, WALL)              # front (north)
fill(0, 1, D - 1, W - 1, 9, D - 1, WALL)      # back  (south)
fill(0, 1, 0, 0, 9, D - 1, WALL)              # left  (west)
fill(W - 1, 1, 0, W - 1, 9, D - 1, WALL)      # right (east)

# ═══════════════════════════════════════════════════════════════════════════════
# Step 3 — Interior 2nd-floor slab & flat roof
# ═══════════════════════════════════════════════════════════════════════════════

fill(1, 5, 1, W - 2, 5, D - 2, FLOOR)         # 2nd-floor slab
fill(1, 9, 1, W - 2, 9, D - 2, ROOF)          # roof surface

# ═══════════════════════════════════════════════════════════════════════════════
# Step 4 — Front facade: ground floor (y=1-4, z=0)
# ═══════════════════════════════════════════════════════════════════════════════

# Horizontal trim kickplate
for x in range(1, 13):
    put(x, 1, 0, TRIM)

# Left storefront glass (x=1-3)
for x in [1, 2, 3]:
    put(x, 2, 0, GLASS)
    put(x, 3, 0, GLASS)

# Left-center storefront (x=5-6)
for x in [5, 6]:
    put(x, 2, 0, GLASS)
    put(x, 3, 0, GLASS)

# Main entrance — triple glass doors (x=7-9)
for x in [7, 8, 9]:
    put(x, 1, 0, DOOR)
    put(x, 2, 0, DOOR)
    put(x, 3, 0, GLASS)       # glass transom above doors

# Right storefront glass (x=11-12)
for x in [11, 12]:
    put(x, 2, 0, GLASS)
    put(x, 3, 0, GLASS)

# Poster display cases (dark panels at eye level in storefront)
for x in [1, 12]:
    put(x, 2, 0, POSTER)

# Tower base section (x=13-16) stays solid wall from step 2

# ═══════════════════════════════════════════════════════════════════════════════
# Step 5 — Marquee letter-board (projecting at z=-1)
# ═══════════════════════════════════════════════════════════════════════════════

for x in range(4, 13):
    put(x, 3, -1, MARQUEE)
    put(x, 4, -1, MARQUEE)

# Marquee text detail — alternating dark blocks
for x in [5, 7, 9, 11]:
    put(x, 4, -1, MARQ_TXT)       # upper row text
for x in [4, 6, 8, 10, 12]:
    put(x, 3, -1, MARQ_TXT)       # lower row text

# ═══════════════════════════════════════════════════════════════════════════════
# Step 6 — Projecting canopy (y=5, z=-1 and z=-2)
# ═══════════════════════════════════════════════════════════════════════════════

# Canopy spans x=0-12 (stops before tower section)
# Front edge: neon-red accent line (signature Varsity detail)
for x in range(0, 13):
    put(x, 5, -2, NEON_R)

# Inner canopy: dark soffit with recessed sea-lantern lights
for x in range(0, 13):
    if x % 3 == 1:
        put(x, 5, -1, LIGHT)
    else:
        put(x, 5, -1, SOFFIT)

# ═══════════════════════════════════════════════════════════════════════════════
# Step 7 — Upper facade windows (y=6-7, z=0)
# ═══════════════════════════════════════════════════════════════════════════════

# 4 window panels, each 2 blocks wide
for xs in [(1, 2), (4, 5), (7, 8), (10, 11)]:
    for x in xs:
        put(x, 6, 0, GLASS_U)
        put(x, 7, 0, GLASS_U)

# ═══════════════════════════════════════════════════════════════════════════════
# Step 8 — VARSITY sign band (y=8, z=0)
# ═══════════════════════════════════════════════════════════════════════════════

# Dark background strip across upper facade
for x in range(1, 13):
    put(x, 8, 0, SIGN_BG)

# VARSITY lettering — community addition (cursive neon, too complex for block grid)
# Sign band left as plain dark background

# ═══════════════════════════════════════════════════════════════════════════════
# Step 9 — Parapet (y=9)
# ═══════════════════════════════════════════════════════════════════════════════

# Light-gray parapet cap on left section of facade (low roofline)
for x in range(0, 6):
    put(x, 9, 0, PARAPET)

# Parapet cap on back wall
for x in range(0, W):
    put(x, 9, D - 1, PARAPET)

# ═══════════════════════════════════════════════════════════════════════════════
# Step 10 — Stepped parapet with neon (x=6-12, y=10-11)
# ═══════════════════════════════════════════════════════════════════════════════

# 2-block stepped-up section with depth
fill(6, 10, 0, 12, 11, 1, WALL)

# Horizontal neon stripes on front face
for x in range(6, 13):
    put(x, 10, 0, NEON_R)
    put(x, 11, 0, NEON_B)

# ═══════════════════════════════════════════════════════════════════════════════
# Step 11 — Tower pylon (x=13-16, y=10-13)
# ═══════════════════════════════════════════════════════════════════════════════

# Tower volume rising above roofline
fill(13, 10, 0, 16, 13, 2, WALL)

# Neon stripes continuous with stepped section
for x in range(13, 17):
    put(x, 10, 0, NEON_R)         # red stripe (aligns with step)
    put(x, 12, 0, NEON_B)         # blue stripe

# Trim bands between neon on tower face
for x in range(13, 17):
    put(x, 11, 0, TRIM)
    put(x, 13, 0, TRIM)           # tower cap

# Service ladder on back face of tower (not street-visible, like the real building)
for y in range(10, 14):
    put(14, y, 2, LADDER)

# ═══════════════════════════════════════════════════════════════════════════════
# Step 12 — Side wall details
# ═══════════════════════════════════════════════════════════════════════════════

# Upper-floor windows on both sides (every 6 blocks of depth)
for z in [5, 11, 17, 23]:
    for x_wall in [0, W - 1]:
        put(x_wall, 6, z, GLASS_U)
        put(x_wall, 7, z, GLASS_U)

# Horizontal trim band at floor division (y=5) on side walls
for z in range(1, D - 1):
    put(0, 5, z, TRIM)
    put(W - 1, 5, z, TRIM)

# ═══════════════════════════════════════════════════════════════════════════════
# Step 13 — Back wall service entrance
# ═══════════════════════════════════════════════════════════════════════════════

for x in [8, 9]:
    put(x, 1, D - 1, DOOR)
    put(x, 2, D - 1, DOOR)

# ═══════════════════════════════════════════════════════════════════════════════
# DONE — save & preview
# ═══════════════════════════════════════════════════════════════════════════════

out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "iconic_davis", "varsity_theater")
os.makedirs(out_dir, exist_ok=True)

nbt_path = os.path.join(out_dir, "varsity_theater.nbt")
sb.save(nbt_path)

count = sum(
    1 for x in range(sb.width)
    for y in range(sb.height)
    for z in range(sb.depth)
    if sb._grid[x][y][z] is not None
)

print(f"Varsity Theatre — Streamline Moderne")
print(f"  Dimensions: {W}x{D} footprint, {TOTAL_H} tall")
print(f"  Blocks placed: {count}")
print(f"  Structure: {nbt_path}")

preview_path = os.path.join(out_dir, "varsity_theater_preview.html")

# Collect reference images from the references folder
ref_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "iconic_davis", "references", "varsity_theater")
ref_images = sorted(glob.glob(os.path.join(ref_dir, "*.jpg")) +
                    glob.glob(os.path.join(ref_dir, "*.png")))

generate_preview(sb, preview_path, title="Varsity Theatre — Streamline Moderne",
                 reference_images=ref_images)
print(f"  Preview: {preview_path}")
if ref_images:
    print(f"  Reference images: {len(ref_images)} embedded")
