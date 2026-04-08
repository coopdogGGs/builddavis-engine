"""Generate the Davis Amtrak Station analysis JSON from reference photos."""
import json

W, H, D = 33, 9, 15

analysis = {
    "description": "Davis Amtrak Station — Mission Revival",
    "dimensions": {"width": W, "height": H, "depth": D},
    "walls": {"material": "stucco", "color": "#C49567"},
    "roof": {"type": "flat", "material": "tile_roof", "color": "#4A3728", "overhang": 1},
    "floors": {"count": 1, "height": 9, "material": "tile_floor"},
    "interior": "hollow",
    "front_face": {
        "features": [
            # Left wing — 3 open arches (covered colonnade)
            {"type": "arch", "material": "minecraft:air", "x": 1,  "y": 1, "width": 3, "height": 5},
            {"type": "arch", "material": "minecraft:air", "x": 6,  "y": 1, "width": 3, "height": 5},
            {"type": "arch", "material": "minecraft:air", "x": 11, "y": 1, "width": 3, "height": 5},
            # Central entrance — dark double doors
            {"type": "door", "material": "minecraft:dark_oak_planks", "x": 15, "y": 1, "width": 3, "height": 6},
            # Right wing — 3 open arches
            {"type": "arch", "material": "minecraft:air", "x": 19, "y": 1, "width": 3, "height": 5},
            {"type": "arch", "material": "minecraft:air", "x": 24, "y": 1, "width": 3, "height": 5},
            {"type": "arch", "material": "minecraft:air", "x": 29, "y": 1, "width": 3, "height": 5},
            # DAVIS sign above entrance
            {"type": "sign", "text": "DAVIS", "x": 14, "y": 7, "width": 5, "height": 1, "bg_color": "#1A1A1A"},
        ]
    },
    "back_face": {
        "features": [
            # Back side — fewer arches, some windows
            {"type": "arch", "material": "minecraft:air",           "x": 3,  "y": 1, "width": 3, "height": 5},
            {"type": "arch", "material": "minecraft:air",           "x": 9,  "y": 1, "width": 3, "height": 4},
            {"type": "door", "material": "minecraft:dark_oak_planks","x": 15, "y": 1, "width": 3, "height": 5},
            {"type": "arch", "material": "minecraft:air",           "x": 21, "y": 1, "width": 3, "height": 4},
            {"type": "arch", "material": "minecraft:air",           "x": 27, "y": 1, "width": 3, "height": 5},
        ]
    },
    "left_face": {
        "features": [
            # Left side arcade — 3 arches wrapping around
            # x here = z position along depth
            {"type": "arch", "material": "minecraft:air", "x": 1,  "y": 1, "width": 3, "height": 5},
            {"type": "arch", "material": "minecraft:air", "x": 6,  "y": 1, "width": 3, "height": 5},
            {"type": "arch", "material": "minecraft:air", "x": 11, "y": 1, "width": 3, "height": 5},
        ]
    },
    "right_face": {
        "features": [
            {"type": "arch", "material": "minecraft:air", "x": 1,  "y": 1, "width": 3, "height": 5},
            {"type": "arch", "material": "minecraft:air", "x": 6,  "y": 1, "width": 3, "height": 5},
            {"type": "arch", "material": "minecraft:air", "x": 11, "y": 1, "width": 3, "height": 5},
        ]
    },
    "accent_blocks": [
        # Stepped castellated top edge (parapet detail)
        {"material": "stucco", "color": "#B8886A", "positions": "top_edge"},
    ],
    "ground_features": [
        # Front plaza / pavement
        {"type": "path", "material": "stone", "color": "#808080",
         "x": 0, "z": -1, "width": 33, "depth": 1},
    ],
    "custom_blocks": [],
}

custom = analysis["custom_blocks"]
stucco = "#C49567"
dark_wood = "#432B14"
roof_tile = "#4A3728"

# --------------------------------------------------------------------------- #
# Central Mission-style parapet (stepped arch rising above the entrance)
# --------------------------------------------------------------------------- #
# Front face parapet (z=0 and z=1 for thickness)
parapet_layers = [
    (9,  range(12, 21)),  # y=9:  x=12..20 (9 wide)
    (10, range(13, 20)),  # y=10: x=13..19 (7 wide)
    (11, range(14, 19)),  # y=11: x=14..18 (5 wide)
    (12, range(15, 18)),  # y=12: x=15..17 (3 wide)
]
for y, xs in parapet_layers:
    for x in xs:
        for z in range(2):  # 2 blocks thick
            custom.append({"x": x, "y": y, "z": z, "block": "minecraft:white_terracotta"})

# --------------------------------------------------------------------------- #
# Left wing raised parapet (smaller hump with "SP" sign in real life)
# --------------------------------------------------------------------------- #
for x in range(2, 8):
    for z in range(2):
        custom.append({"x": x, "y": 9, "z": z, "block": "minecraft:white_terracotta"})
# Smaller peak
for x in range(3, 7):
    for z in range(2):
        custom.append({"x": x, "y": 10, "z": z, "block": "minecraft:white_terracotta"})
for x in range(4, 6):
    for z in range(2):
        custom.append({"x": x, "y": 11, "z": z, "block": "minecraft:white_terracotta"})

# --------------------------------------------------------------------------- #
# Right wing raised parapet (mirror of left)
# --------------------------------------------------------------------------- #
for x in range(25, 31):
    for z in range(2):
        custom.append({"x": x, "y": 9, "z": z, "block": "minecraft:white_terracotta"})
for x in range(26, 30):
    for z in range(2):
        custom.append({"x": x, "y": 10, "z": z, "block": "minecraft:white_terracotta"})
for x in range(27, 29):
    for z in range(2):
        custom.append({"x": x, "y": 11, "z": z, "block": "minecraft:white_terracotta"})

# --------------------------------------------------------------------------- #
# Dark wooden beam brackets (vigas/corbels) under eaves — front face
# Along y=7, z=0 at regular intervals (the exposed beam ends)
# --------------------------------------------------------------------------- #
beam_xs = [4, 5, 8, 9, 14, 18, 23, 24, 27, 28]
for x in beam_xs:
    custom.append({"x": x, "y": 7, "z": 0, "block": "minecraft:dark_oak_planks"})

# Dark wooden beam row at top of wall — eave trim (y=8, z=0 front face)
for x in range(W):
    custom.append({"x": x, "y": 8, "z": 0, "block": "minecraft:spruce_planks"})
    # Also along back face
    custom.append({"x": x, "y": 8, "z": D - 1, "block": "minecraft:spruce_planks"})

# Side eave trim
for z in range(D):
    custom.append({"x": 0, "y": 8, "z": z, "block": "minecraft:spruce_planks"})
    custom.append({"x": W - 1, "y": 8, "z": z, "block": "minecraft:spruce_planks"})

# --------------------------------------------------------------------------- #
# Tile roof cap (dark clay tiles visible above the wooden beams)
# The flat roof already handles y=9, but the parapet sections rise above
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# Decorative clock/medallion above entrance (y=6, z=0, center)
# --------------------------------------------------------------------------- #
custom.append({"x": 16, "y": 6, "z": 0, "block": "minecraft:polished_andesite"})

# --------------------------------------------------------------------------- #
# Lanterns flanking the entrance (at pillar tops)
# --------------------------------------------------------------------------- #
custom.append({"x": 14, "y": 6, "z": 0, "block": "minecraft:lantern"})
custom.append({"x": 18, "y": 6, "z": 0, "block": "minecraft:lantern"})

# --------------------------------------------------------------------------- #
# Front planters (raised stone beds at ground level, in front of building)
# These are in the z=-1 row (ground features) — but we can't go outside
# the building footprint easily. Place them at z=0, y=0 as accent.
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# Arcade depth — make the colonnade a real covered walkway
# The arcade is about 3 blocks deep on the front. Interior blocks at z=1,2
# should be air where the arches are open.
# --------------------------------------------------------------------------- #
# Left wing arcade interior (z=1 and z=2)
arch_ranges = [(1, 4), (6, 9), (11, 14)]  # same x ranges as front arches
for x_start, x_end in arch_ranges:
    for x in range(x_start, x_end):
        for z in [1, 2]:
            for y in range(1, 6):
                custom.append({"x": x, "y": y, "z": z, "block": "minecraft:air"})

# Central entrance depth
for x in range(15, 18):
    for z in [1, 2]:
        for y in range(1, 7):
            custom.append({"x": x, "y": y, "z": z, "block": "minecraft:air"})

# Right wing arcade interior
arch_ranges_right = [(19, 22), (24, 27), (29, 32)]
for x_start, x_end in arch_ranges_right:
    for x in range(x_start, x_end):
        for z in [1, 2]:
            for y in range(1, 6):
                custom.append({"x": x, "y": y, "z": z, "block": "minecraft:air"})

# Left side arcade depth (x=0 face, arcade extends inward at x=1,2)
side_arch_ranges = [(1, 4), (6, 9), (11, 14)]
for z_start, z_end in side_arch_ranges:
    for z in range(z_start, z_end):
        for x in [1, 2]:
            for y in range(1, 6):
                custom.append({"x": x, "y": y, "z": z, "block": "minecraft:air"})

# Right side arcade depth (x=W-1 face)
for z_start, z_end in side_arch_ranges:
    for z in range(z_start, z_end):
        for x in [W - 2, W - 3]:
            for y in range(1, 6):
                custom.append({"x": x, "y": y, "z": z, "block": "minecraft:air"})

# --------------------------------------------------------------------------- #
# Arcade ceiling — floor slab at y=6 over the arcade walkway areas
# to separate the arcade from the upper portion
# --------------------------------------------------------------------------- #
for x_start, x_end in [(1, 14), (19, 32)]:
    for x in range(x_start, x_end):
        for z in [1, 2]:
            custom.append({"x": x, "y": 6, "z": z, "block": "minecraft:white_terracotta"})

# Pillars between arches — reinforce the columns at arcade depth
pillar_xs_front = [0, 4, 5, 9, 10, 14, 18, 22, 23, 27, 28, 32]
for px in pillar_xs_front:
    for z in [1, 2]:
        for y in range(1, 7):
            custom.append({"x": px, "y": y, "z": z, "block": "minecraft:white_terracotta"})

print(f"Generated {len(custom)} custom blocks")
print(f"Total dimensions: {W}×{H}×{D} + parapets")

with open("davis_amtrak_analysis.json", "w") as f:
    json.dump(analysis, f, indent=2)

print("Saved to davis_amtrak_analysis.json")
