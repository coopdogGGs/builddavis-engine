"""
The Flying Carousel of the Delta Breeze — Iconic build for BuildDavis.

Davis's beloved community carousel in Central Park, built 1995 by
William Dentzel (5th-generation carousel maker). Pedal-powered with
hand-carved wooden animals painted by local schoolchildren.

Architecture (from reference photos):
  - Octagonal pavilion, ~10m diameter (~33ft)
  - 8 dark green wooden support posts
  - Decorative radial fan brackets between posts (dark green)
  - White/cream trim on eaves with arched fascia + trefoil cutouts
  - Two-tier peaked roof: lower octagonal hip + upper cupola
  - Dark green wrought-iron fence enclosure between posts
  - Brick paver pad surround
  - Interior: colorful mosaic center column, wood chip floor,
    8 hand-carved animals on poles

Minecraft scale: 1:1 (10m ≈ 10 blocks diameter)
  Footprint: 12×12 blocks (octagonal outline inscribed)
  Height: 9 blocks (posts 4, lower roof 3, cupola 2)

Geo: 38.5459, -121.7447  (Central Park, B St & 4th St, Davis CA)
OSM Node: 10774589405
Stage: python Code/stage.py carousel
Live:  python Code/stage.py carousel --live --lat 38.5459 --lon -121.7447
"""

import sys, os, math, glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structurize.nbt_writer import StructureBuilder
from structurize.preview import generate_preview

# ── Block palette ─────────────────────────────────────────────────────────────
POST     = "minecraft:dark_oak_fence"        # dark green support posts
POST_BLK = "minecraft:green_concrete"        # post base blocks (thicker)
FENCE    = "minecraft:iron_bars"             # wrought-iron fence enclosure
ROOF_LOW = "minecraft:spruce_planks"         # lower hip roof (grey-brown shingle)
ROOF_UP  = "minecraft:spruce_planks"         # cupola roof
ROOF_CAP = "minecraft:dark_oak_slab"         # roof peak cap
TRIM     = "minecraft:smooth_quartz"         # white/cream eave trim
BRACKET  = "minecraft:dark_oak_planks"       # decorative fan brackets (dark green wood)
BRICK    = "minecraft:bricks"             # brick paver pad surround
FLOOR    = "minecraft:coarse_dirt"           # wood-chip floor inside
CENTER   = "minecraft:cyan_glazed_terracotta" # mosaic center column
POLE     = "minecraft:lightning_rod"         # animal ride poles (vertical rod)
ANIMAL_1 = "minecraft:white_concrete"        # cow (Daisy)
ANIMAL_2 = "minecraft:orange_concrete"       # dog (Bob)
ANIMAL_3 = "minecraft:brown_concrete"        # horse (Pegasus)
ANIMAL_4 = "minecraft:lime_concrete"         # frog (Fred)
SLAB_SPR = "minecraft:spruce_slab"           # spruce slab variant
AIR      = "minecraft:air"

# ── Dimensions ────────────────────────────────────────────────────────────────
# Doubled scale: ~24×24 footprint octagonal, ~20 blocks tall
W = 28   # x extent (with brick pad border)
D = 28   # z extent
H = 21   # y extent (pad + posts + roof + cupola)

CX, CZ = 14, 14  # center
OUTER_R = 12     # octagon outer radius (brick pad edge)
STRUCT_R = 10    # pavilion post radius (structure footprint)
INNER_R = 6      # carousel mechanism radius (animal ring)

# Vertical zones
PAD_Y      = 0   # brick pad
FLOOR_Y    = 1   # interior floor
POST_BOT_Y = 1   # posts start
POST_TOP_Y = 8   # posts end (8 blocks tall)
EAVE_Y     = 9   # trim / bracket level
ROOF_BOT_Y = 9   # lower roof starts
ROOF_MID_Y = 14  # lower roof ends / cupola base
CUPOLA_Y   = 15  # cupola walls
CUPOLA_TOP = 17  # cupola roof
PEAK_Y     = 19  # roof peak cap

sb = StructureBuilder(W, H, D)


# ── Helpers ───────────────────────────────────────────────────────────────────

def s(x, y, z, block):
    sb.set_block(x, y, z, block)


def f(x1, y1, z1, x2, y2, z2, block):
    sb.fill(x1, y1, z1, x2, y2, z2, block)


def octagon_points(cx, cz, r):
    """Return the 8 vertices of an octagon centered at (cx,cz) with radius r."""
    pts = []
    for i in range(8):
        angle = math.pi / 8 + i * math.pi / 4  # 22.5° offset for flat sides
        x = cx + r * math.cos(angle)
        z = cz + r * math.sin(angle)
        pts.append((round(x), round(z)))
    return pts


def octagon_fill(cx, cz, r, y, block):
    """Fill a solid octagonal area at height y."""
    for x in range(cx - r, cx + r + 1):
        for z in range(cz - r, cz + r + 1):
            dx, dz = abs(x - cx), abs(z - cz)
            # Octagon test: Chebyshev-ish with corner cut
            if dx + dz <= r * 1.41 and dx <= r and dz <= r:
                s(x, y, z, block)


def octagon_ring(cx, cz, r, y, block):
    """Draw just the perimeter of an octagon at height y."""
    for x in range(cx - r, cx + r + 1):
        for z in range(cz - r, cz + r + 1):
            dx, dz = abs(x - cx), abs(z - cz)
            dist = dx + dz
            # On the octagon edge (within 1 block of boundary)
            if dist <= r * 1.41 and dx <= r and dz <= r:
                inner_ok = (dx + dz <= (r - 1) * 1.41 and dx <= r - 1 and dz <= r - 1)
                if not inner_ok:
                    s(x, y, z, block)


# ── Build: Brick paver pad ───────────────────────────────────────────────────
octagon_fill(CX, CZ, OUTER_R, PAD_Y, BRICK)

# ── Build: Interior floor (wood chips / coarse dirt) ─────────────────────────
octagon_fill(CX, CZ, STRUCT_R, FLOOR_Y, FLOOR)

# ── Build: 8 support posts ──────────────────────────────────────────────────
post_positions = octagon_points(CX, CZ, STRUCT_R)
for px, pz in post_positions:
    # Thick green base block
    s(px, POST_BOT_Y, pz, POST_BLK)
    # Tall fence posts above
    for y in range(POST_BOT_Y + 1, POST_TOP_Y + 1):
        s(px, y, pz, POST)

# ── Build: Wrought-iron fence between posts ──────────────────────────────────
# Iron bars on the perimeter ring (3 blocks tall for 2x scale)
for y in [FLOOR_Y, FLOOR_Y + 1, FLOOR_Y + 2, FLOOR_Y + 3]:
    for x in range(CX - STRUCT_R, CX + STRUCT_R + 1):
        for z in range(CZ - STRUCT_R, CZ + STRUCT_R + 1):
            dx, dz = abs(x - CX), abs(z - CZ)
            if dx + dz <= STRUCT_R * 1.41 and dx <= STRUCT_R and dz <= STRUCT_R:
                inner_ok = (dx + dz <= (STRUCT_R - 1) * 1.41
                            and dx <= STRUCT_R - 1 and dz <= STRUCT_R - 1)
                if not inner_ok:
                    # Skip post positions
                    if (x, z) not in post_positions:
                        s(x, y, z, FENCE)

# ── Build: White trim / eave ring ────────────────────────────────────────────
octagon_ring(CX, CZ, STRUCT_R + 1, EAVE_Y, TRIM)
octagon_ring(CX, CZ, STRUCT_R, EAVE_Y, TRIM)

# ── Build: Decorative brackets at eave level ─────────────────────────────────
# Place bracket blocks adjacent to each post at the eave
for px, pz in post_positions:
    s(px, EAVE_Y, pz, BRACKET)
    s(px, POST_TOP_Y, pz, BRACKET)

# ── Build: Lower octagonal hip roof ─────────────────────────────────────────
# Concentric shrinking octagon layers rising from eave
for layer in range(6):
    y = ROOF_BOT_Y + layer
    r = STRUCT_R + 1 - layer
    if r < 1:
        break
    octagon_fill(CX, CZ, r, y, ROOF_LOW)

# ── Build: Cupola base ring ──────────────────────────────────────────────────
# Small octagonal cupola sitting on top of lower roof
cupola_r = 4
for cy in [CUPOLA_Y, CUPOLA_Y + 1]:
    octagon_ring(CX, CZ, cupola_r, cy, BRACKET)

# Cupola roof — 2 layers tapering
octagon_fill(CX, CZ, cupola_r, CUPOLA_TOP, ROOF_UP)
octagon_fill(CX, CZ, cupola_r - 1, CUPOLA_TOP + 1, ROOF_UP)
s(CX, PEAK_Y, CZ, ROOF_CAP)
s(CX, PEAK_Y - 1, CZ, ROOF_CAP)

# ── Build: Center mosaic column (2×2 at this scale) ─────────────────────────
for y in range(FLOOR_Y, ROOF_BOT_Y):
    s(CX, y, CZ, CENTER)
    s(CX + 1, y, CZ, CENTER)
    s(CX, y, CZ + 1, CENTER)
    s(CX + 1, y, CZ + 1, CENTER)

# ── Build: Animal ride poles + colored animal blocks ─────────────────────────
# Ring of animals at INNER_R from center, 8 positions (45° apart)
animal_blocks = [ANIMAL_1, ANIMAL_2, ANIMAL_3, ANIMAL_4,
                 ANIMAL_1, ANIMAL_2, ANIMAL_3, ANIMAL_4]

for i in range(8):
    angle = i * math.pi / 4
    ax = CX + round(INNER_R * math.cos(angle))
    az = CZ + round(INNER_R * math.sin(angle))
    # Pole from above animal to eave
    for y in range(FLOOR_Y + 3, EAVE_Y):
        s(ax, y, az, POLE)
    # Animal blocks — 2 blocks tall at ride height
    s(ax, FLOOR_Y + 1, az, animal_blocks[i])
    s(ax, FLOOR_Y + 2, az, animal_blocks[i])


# ── Generate outputs ─────────────────────────────────────────────────────────
OUT_DIR = os.path.join(os.path.dirname(__file__), "iconic_davis", "carousel")
os.makedirs(OUT_DIR, exist_ok=True)

nbt_path = os.path.join(OUT_DIR, "carousel.nbt")
sb.save(nbt_path)

html_path = os.path.join(OUT_DIR, "carousel_preview.html")

# Gather reference images
ref_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "iconic_davis", "references", "flying_carousel")
ref_images = sorted(
    glob.glob(os.path.join(ref_dir, "*.jpg")) +
    glob.glob(os.path.join(ref_dir, "*.png"))
)

generate_preview(
    sb,
    title="The Flying Carousel of the Delta Breeze",
    output_path=html_path,
    reference_images=ref_images
)

block_count = sum(
    1 for x in range(sb.width) for y in range(sb.height) for z in range(sb.depth)
    if sb._grid[x][y][z] is not None
)
print(f"Carousel: {sb.width}×{sb.height}×{sb.depth}  ({block_count} blocks)")
print(f"NBT:  {nbt_path}")
print(f"HTML: {html_path}")
