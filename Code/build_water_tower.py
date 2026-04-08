"""
UC Davis Water Tower — Direct architectural build using StructureBuilder.

The iconic UC Davis water tower is a steel-legged elevated tank:
  - ~150ft (46m) total height
  - White spheroid tank: dome top + inverted-cone bowl bottom
  - 6 angled support legs with X-cross bracing at 3 tiers
  - Metal catwalk with railing at tank equator
  - "UC DAVIS" signage in blue on two opposite sides
  - Concrete pad base

Reference images studied:
  - Close-up front: dome profile, "UC DAVIS" lettering, catwalk railing detail
  - Aerial/sunset: full structure proportions, leg angles, cross-bracing pattern
  - Close-up angled: bowl underside shape, leg attachment, bracing detail
"""

import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structurize.nbt_writer import StructureBuilder
from structurize.preview import generate_preview

# ── Block palette ──
TANK    = "minecraft:white_concrete"       # tank body (clean white)
TANK_S  = "minecraft:smooth_quartz"        # tank highlights/rim accents
LEG     = "minecraft:light_gray_concrete"  # steel support legs
BRACE   = "minecraft:light_gray_concrete"  # cross bracing (solid, no floating)
CATWALK = "minecraft:light_gray_concrete"  # catwalk deck
RAIL    = "minecraft:iron_bars"             # catwalk railing (chain not in 1.21.11)
SIGN_UC = "minecraft:blue_concrete"        # "UC" letters
SIGN_DA = "minecraft:blue_concrete"        # "DAVIS" letters (same blue)
PAD     = "minecraft:smooth_stone"         # concrete base pad
AIR     = "minecraft:air"

# ── Dimensions ──
# Real proportions scaled to Minecraft (1 block = 1 meter)
# Tank diameter widened from 12 to 20 blocks so "UC DAVIS" text fits on one line.
# Legs and height scaled proportionally.

FOOTPRINT = 33     # x and z extent (square bounding box for circular structure)
TOTAL_H   = 48     # total height including dome cap
CX, CZ    = 16, 16 # center of the structure in x,z

# Vertical zones (y-coordinates, 0 = ground)
PAD_Y       = 0     # ground pad
LEG_BASE_Y  = 1     # legs start
BOWL_BOT_Y  = 30    # bottom of inverted bowl
BOWL_TOP_Y  = 37    # top of bowl / catwalk level
DOME_BOT_Y  = 37    # dome starts
DOME_TOP_Y  = 47    # dome apex

TANK_RADIUS    = 10  # radius of tank body at widest (20 blocks diameter)
LEG_BASE_RAD   = 14  # how far out legs are at ground level
LEG_TOP_RAD    = 8   # how far in legs are at bowl bottom
NUM_LEGS       = 6   # number of support legs

# Cross-brace tiers (y-levels for horizontal rings + X-braces between legs)
BRACE_TIERS = [8, 16, 24]

sb = StructureBuilder(width=FOOTPRINT, height=TOTAL_H, depth=FOOTPRINT)

# ═══════════════════════════════════════════════════════════════════════════
# STEP 1 — Ground pad (circular concrete slab)
# ═══════════════════════════════════════════════════════════════════════════
for x in range(FOOTPRINT):
    for z in range(FOOTPRINT):
        dx = x - CX
        dz = z - CZ
        if dx*dx + dz*dz <= (LEG_BASE_RAD + 1)**2:
            sb.set_block(x, PAD_Y, z, PAD)

# ═══════════════════════════════════════════════════════════════════════════
# STEP 2 — Support legs (6 angled columns)
# Each leg goes from (angle, LEG_BASE_RAD) at y=1 to (angle, LEG_TOP_RAD) at y=BOWL_BOT_Y
# ═══════════════════════════════════════════════════════════════════════════
leg_angles = [i * (2 * math.pi / NUM_LEGS) for i in range(NUM_LEGS)]

def leg_pos_at_y(angle, y):
    """Get the (x, z) of a leg column at height y, linearly interpolating radius."""
    t = (y - LEG_BASE_Y) / (BOWL_BOT_Y - LEG_BASE_Y)
    t = max(0.0, min(1.0, t))
    r = LEG_BASE_RAD * (1 - t) + LEG_TOP_RAD * t
    lx = CX + r * math.cos(angle)
    lz = CZ + r * math.sin(angle)
    return int(round(lx)), int(round(lz))

for angle in leg_angles:
    prev_x, prev_z = None, None
    for y in range(LEG_BASE_Y, BOWL_BOT_Y + 1):
        lx, lz = leg_pos_at_y(angle, y)
        sb.set_block(lx, y, lz, LEG)
        # Fill gaps if the leg moved diagonally
        if prev_x is not None:
            if abs(lx - prev_x) + abs(lz - prev_z) > 1:
                sb.set_block(prev_x, y, prev_z, LEG)
        prev_x, prev_z = lx, lz

# ═══════════════════════════════════════════════════════════════════════════
# STEP 3 — Horizontal ring beams at brace tiers
# ═══════════════════════════════════════════════════════════════════════════
for tier_y in BRACE_TIERS:
    # Get positions of all legs at this height
    leg_positions = [leg_pos_at_y(a, tier_y) for a in leg_angles]
    # Connect adjacent legs with horizontal beams
    for i in range(NUM_LEGS):
        x1, z1 = leg_positions[i]
        x2, z2 = leg_positions[(i + 1) % NUM_LEGS]
        # Bresenham-like line between two leg positions
        steps = max(abs(x2 - x1), abs(z2 - z1), 1)
        for s in range(steps + 1):
            t = s / steps
            bx = int(round(x1 + (x2 - x1) * t))
            bz = int(round(z1 + (z2 - z1) * t))
            sb.set_block(bx, tier_y, bz, BRACE)

# ═══════════════════════════════════════════════════════════════════════════
# STEP 4 — X-cross bracing between legs (diagonal members)
# Between each pair of adjacent legs, draw an X between two brace tiers
# ═══════════════════════════════════════════════════════════════════════════
for tier_idx in range(len(BRACE_TIERS) - 1):
    y_bot = BRACE_TIERS[tier_idx]
    y_top = BRACE_TIERS[tier_idx + 1]
    for i in range(NUM_LEGS):
        # Leg i at bottom, leg i+1 at top (and vice versa for the X)
        x1b, z1b = leg_pos_at_y(leg_angles[i], y_bot)
        x2b, z2b = leg_pos_at_y(leg_angles[(i + 1) % NUM_LEGS], y_bot)
        x1t, z1t = leg_pos_at_y(leg_angles[i], y_top)
        x2t, z2t = leg_pos_at_y(leg_angles[(i + 1) % NUM_LEGS], y_top)
        
        # Diagonal 1: bottom-left to top-right
        steps = y_top - y_bot
        for s in range(steps + 1):
            t = s / steps
            bx = int(round(x1b + (x2t - x1b) * t))
            bz = int(round(z1b + (z2t - z1b) * t))
            by = int(round(y_bot + (y_top - y_bot) * t))
            sb.set_block(bx, by, bz, BRACE)
        
        # Diagonal 2: bottom-right to top-left
        for s in range(steps + 1):
            t = s / steps
            bx = int(round(x2b + (x1t - x2b) * t))
            bz = int(round(z2b + (z1t - z2b) * t))
            by = int(round(y_bot + (y_top - y_bot) * t))
            sb.set_block(bx, by, bz, BRACE)

# Also add X-bracing from the last tier up to the bowl bottom
y_bot = BRACE_TIERS[-1]
y_top = BOWL_BOT_Y
for i in range(NUM_LEGS):
    x1b, z1b = leg_pos_at_y(leg_angles[i], y_bot)
    x2b, z2b = leg_pos_at_y(leg_angles[(i + 1) % NUM_LEGS], y_bot)
    x1t, z1t = leg_pos_at_y(leg_angles[i], y_top)
    x2t, z2t = leg_pos_at_y(leg_angles[(i + 1) % NUM_LEGS], y_top)
    steps = y_top - y_bot
    if steps > 0:
        for s in range(steps + 1):
            t = s / steps
            bx = int(round(x1b + (x2t - x1b) * t))
            bz = int(round(z1b + (z2t - z1b) * t))
            by = int(round(y_bot + (y_top - y_bot) * t))
            sb.set_block(bx, by, bz, BRACE)
        for s in range(steps + 1):
            t = s / steps
            bx = int(round(x2b + (x1t - x2b) * t))
            bz = int(round(z2b + (z1t - z2b) * t))
            by = int(round(y_bot + (y_top - y_bot) * t))
            sb.set_block(bx, by, bz, BRACE)

# ═══════════════════════════════════════════════════════════════════════════
# STEP 5 — Central pipe/column (water riser inside the leg structure)
# ═══════════════════════════════════════════════════════════════════════════
for y in range(LEG_BASE_Y, BOWL_BOT_Y + 1):
    sb.set_block(CX, y, CZ, LEG)

# ═══════════════════════════════════════════════════════════════════════════
# STEP 6 — Inverted bowl/cone (tank bottom: from narrow bottom to wide top)
# Profile: at BOWL_BOT_Y radius=2, expands to TANK_RADIUS at BOWL_TOP_Y
# Uses filled circles at each y-level (shell only = outline)
# ═══════════════════════════════════════════════════════════════════════════
BOWL_INNER_OFFSET = 1  # wall thickness = 1 block

for y in range(BOWL_BOT_Y, BOWL_TOP_Y + 1):
    t = (y - BOWL_BOT_Y) / (BOWL_TOP_Y - BOWL_BOT_Y)
    # Bowl profile: starts at radius 2 (bottom), expands to TANK_RADIUS (top)
    # Use a smooth curve (parabolic) for the bowl shape
    r = 2 + (TANK_RADIUS - 2) * math.sqrt(t)
    r_inner = max(0, r - BOWL_INNER_OFFSET)
    
    for x in range(FOOTPRINT):
        for z in range(FOOTPRINT):
            dx = x - CX
            dz = z - CZ
            dist = math.sqrt(dx*dx + dz*dz)
            if dist <= r + 0.5 and dist >= r_inner - 0.5:
                sb.set_block(x, y, z, TANK)
    
    # Fill the very bottom ring solid (no hollow)
    if y == BOWL_BOT_Y:
        for x in range(FOOTPRINT):
            for z in range(FOOTPRINT):
                dx = x - CX
                dz = z - CZ
                dist = math.sqrt(dx*dx + dz*dz)
                if dist <= r + 0.5:
                    sb.set_block(x, y, z, TANK)

# ═══════════════════════════════════════════════════════════════════════════
# STEP 7 — Catwalk and railing at BOWL_TOP_Y
# Ring of blocks just outside the tank wall + iron bar railing on top
# ═══════════════════════════════════════════════════════════════════════════
catwalk_r = TANK_RADIUS + 1

for x in range(FOOTPRINT):
    for z in range(FOOTPRINT):
        dx = x - CX
        dz = z - CZ
        dist = math.sqrt(dx*dx + dz*dz)
        # Catwalk deck: ring from TANK_RADIUS to TANK_RADIUS+1
        if TANK_RADIUS - 0.5 <= dist <= catwalk_r + 0.5:
            sb.set_block(x, BOWL_TOP_Y, z, CATWALK)
            # Railing on outer edge
            if dist >= catwalk_r - 0.3:
                sb.set_block(x, BOWL_TOP_Y + 1, z, RAIL)

# ═══════════════════════════════════════════════════════════════════════════
# STEP 8 — Dome (hemisphere on top of tank)
# From DOME_BOT_Y to DOME_TOP_Y: decreasing radius circles
# ═══════════════════════════════════════════════════════════════════════════
dome_height = DOME_TOP_Y - DOME_BOT_Y

for y in range(DOME_BOT_Y, DOME_TOP_Y + 1):
    t = (y - DOME_BOT_Y) / dome_height
    # Hemisphere: r = R * cos(arcsin(t)) = R * sqrt(1 - t^2)
    r = TANK_RADIUS * math.sqrt(max(0, 1 - t*t))
    
    if r < 0.5:
        # Cap — single block at apex
        sb.set_block(CX, y, CZ, TANK)
        continue
    
    r_inner = max(0, r - 1)
    
    for x in range(FOOTPRINT):
        for z in range(FOOTPRINT):
            dx = x - CX
            dz = z - CZ
            dist = math.sqrt(dx*dx + dz*dz)
            # Shell only for the dome
            if dist <= r + 0.5 and dist >= r_inner - 0.5:
                sb.set_block(x, y, z, TANK)
    
    # At dome base (y == DOME_BOT_Y), fill a solid disc as the tank floor/roof
    if y == DOME_BOT_Y:
        for x in range(FOOTPRINT):
            for z in range(FOOTPRINT):
                dx = x - CX
                dz = z - CZ
                if dx*dx + dz*dz <= TANK_RADIUS * TANK_RADIUS:
                    sb.set_block(x, y, z, TANK)

# ═══════════════════════════════════════════════════════════════════════════
# STEP 9 — "UC DAVIS" signage — painted ON the dome surface
# Letters are blue blocks replacing white dome blocks on the curved surface.
# Single line: "UC DAVIS" centered horizontally on the dome.
# ═══════════════════════════════════════════════════════════════════════════

# 3-row pixel font: each letter = [row0, row1, row2], each row = list of 0/1
# Designed for readability at small scale
FONT3 = {
    'U': [[1,0,1], [1,0,1], [1,1,1]],
    'C': [[1,1,1], [1,0,0], [1,1,1]],
    'D': [[1,1,0], [1,0,1], [1,1,0]],
    'A': [[1,1,1], [1,1,1], [1,0,1]],
    'V': [[1,0,1], [1,0,1], [0,1,0]],
    'I': [[1], [1], [1]],
    'S': [[1,1,1], [0,1,0], [1,1,1]],
}

def word_to_bitmap(word, gap=1):
    """Convert a word to a 3-row bitmap using FONT3."""
    rows = [[], [], []]
    for i, ch in enumerate(word):
        if i > 0:
            for r in range(3):
                rows[r].extend([0] * gap)
        letter = FONT3[ch]
        for r in range(3):
            rows[r].extend(letter[r])
    return rows

def paint_sign_on_dome(bitmap_rows, y_top, face):
    """Paint a bitmap on the dome surface by swapping white blocks to blue.
    face='south' paints on +Z side, face='north' on -Z side.
    North face flips X so text reads correctly from the outside."""
    width = len(bitmap_rows[0])
    dome_h = DOME_TOP_Y - DOME_BOT_Y
    for row_idx, row in enumerate(bitmap_rows):
        y = y_top - row_idx
        t = (y - DOME_BOT_Y) / dome_h
        if t < 0 or t > 1:
            continue
        dome_r = TANK_RADIUS * math.sqrt(max(0, 1 - t * t))
        for col_idx, pixel in enumerate(row):
            if pixel == 0:
                continue
            # South face: normal L-to-R; North face: flip so text reads correctly
            if face == 'south':
                x = CX - width // 2 + col_idx
            else:
                x = CX + width // 2 - col_idx
            dx = x - CX
            if abs(dx) > dome_r:
                continue
            dz = math.sqrt(max(0, dome_r * dome_r - dx * dx))
            if face == 'south':
                z = int(round(CZ + dz))
            else:
                z = int(round(CZ - dz))
            sb.set_block(x, y, z, SIGN_DA)

# Build "UC DAVIS" as a single line — gap=0 within each word so it fits dome width
uc_bitmap = word_to_bitmap("UC", gap=0)        # 6 blocks wide (touching)
davis_bitmap = word_to_bitmap("DAVIS", gap=0)   # 13 blocks wide (touching)
# Merge into one line: UC + 1-block space + DAVIS = 6+1+13 = 20 = dome diameter
sign_rows = [[], [], []]
for r in range(3):
    sign_rows[r] = uc_bitmap[r] + [0] + davis_bitmap[r]

# Vertical placement: centered on the dome's widest portion
SIGN_TOP_Y = DOME_BOT_Y + 4  # y=41, middle of dome

# Paint on south and north faces
for face in ('south', 'north'):
    paint_sign_on_dome(sign_rows, SIGN_TOP_Y, face)

# ═══════════════════════════════════════════════════════════════════════════
# STEP 10 — Accent details
# ═══════════════════════════════════════════════════════════════════════════

# Quartz trim ring at dome/bowl junction (the visible seam band)
for x in range(FOOTPRINT):
    for z in range(FOOTPRINT):
        dx = x - CX
        dz = z - CZ
        dist = math.sqrt(dx*dx + dz*dz)
        if abs(dist - TANK_RADIUS) < 1.0:
            sb.set_block(x, BOWL_TOP_Y - 1, z, TANK_S)

# Small dome cap accent at very top
sb.set_block(CX, DOME_TOP_Y, CZ, TANK_S)

# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY & EXPORT
# ═══════════════════════════════════════════════════════════════════════════

# Count non-air blocks
total = sum(
    1 for x in range(FOOTPRINT)
    for y in range(TOTAL_H)
    for z in range(FOOTPRINT)
    if sb._grid[x][y][z] is not None
)

print(f"UC Davis Water Tower built: {FOOTPRINT}×{TOTAL_H}×{FOOTPRINT}")
print(f"  Non-air blocks: {total}")
print(f"  Tank radius: {TANK_RADIUS} blocks ({TANK_RADIUS*2} diameter)")
print(f"  Height: {TOTAL_H} blocks ({TOTAL_H}m)")
print(f"  Legs: {NUM_LEGS}, base spread radius {LEG_BASE_RAD}")
print(f"  Brace tiers: {BRACE_TIERS}")

# Generate preview
preview_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "water_tower_preview.html")
generate_preview(sb, preview_path, title="UC Davis Water Tower")
print(f"  Preview: {preview_path}")
