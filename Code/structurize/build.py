"""
Structure builder — converts an AI structural analysis into a 3D Minecraft block grid.

Takes a structured JSON description (from analyze.py) and produces
a populated StructureBuilder ready to export as .nbt.
"""

from .nbt_writer import StructureBuilder
from .palette import nearest_block_hex, nearest_block, BLOCK_COLORS, AIR


# --------------------------------------------------------------------------- #
# Material mapping — semantic names → Minecraft blocks
# --------------------------------------------------------------------------- #

MATERIAL_MAP: dict[str, str] = {
    # Walls
    "brick":           "minecraft:bricks",
    "red_brick":       "minecraft:bricks",
    "stone":           "minecraft:stone_bricks",
    "concrete":        "minecraft:light_gray_concrete",
    "stucco":          "minecraft:white_terracotta",
    "wood":            "minecraft:oak_planks",
    "wood_dark":       "minecraft:dark_oak_planks",
    "wood_light":      "minecraft:birch_planks",
    "metal":           "minecraft:iron_block",
    "glass":           "minecraft:glass",
    "sandstone":       "minecraft:sandstone",
    "plaster":         "minecraft:white_concrete",
    "adobe":           "minecraft:terracotta",
    "marble":          "minecraft:quartz_block",
    "cinder_block":    "minecraft:gray_concrete",

    # Roof
    "shingles":        "minecraft:gray_terracotta",
    "tile_roof":       "minecraft:red_terracotta",
    "metal_roof":      "minecraft:light_gray_concrete",
    "flat_roof":       "minecraft:smooth_stone",
    "slate":           "minecraft:deepslate",
    "thatch":          "minecraft:hay_block",

    # Windows
    "window":          "minecraft:light_blue_stained_glass",
    "window_clear":    "minecraft:glass",
    "window_dark":     "minecraft:gray_stained_glass",
    "window_tinted":   "minecraft:tinted_glass",

    # Doors
    "door_wood":       "minecraft:oak_door",
    "door_metal":      "minecraft:iron_door",
    "door_glass":      "minecraft:glass",

    # Ground / floor
    "concrete_floor":  "minecraft:smooth_stone",
    "wood_floor":      "minecraft:oak_planks",
    "carpet":          "minecraft:white_wool",
    "tile_floor":      "minecraft:white_terracotta",

    # Accents
    "trim":            "minecraft:quartz_block",
    "awning":          "minecraft:green_wool",
    "railing":         "minecraft:iron_bars",
    "fence":           "minecraft:oak_fence",
    "lamp":            "minecraft:lantern",
    "light":           "minecraft:glowstone",
    "sign":            "minecraft:oak_wall_sign",
}


def resolve_material(material_name: str, color_hex: str | None = None) -> str:
    """
    Resolve a material name (from AI analysis) to a Minecraft block ID.
    Optionally tint by colour hex.
    """
    if material_name in MATERIAL_MAP:
        block = MATERIAL_MAP[material_name]
        # If a colour is specified and the block is concrete/wool/terracotta,
        # try to pick the nearest colour variant
        if color_hex and any(k in material_name for k in
                             ("concrete", "wool", "terracotta", "stucco",
                              "plaster")):
            return nearest_block_hex(color_hex)
        return block
    # If the material name looks like a Minecraft block ID, use it directly
    if material_name.startswith("minecraft:"):
        return material_name
    # Fall back to colour matching
    if color_hex:
        return nearest_block_hex(color_hex)
    return "minecraft:stone_bricks"


# --------------------------------------------------------------------------- #
# Structure generation from AI analysis
# --------------------------------------------------------------------------- #

def build_structure(analysis: dict) -> StructureBuilder:
    """
    Build a 3D Minecraft structure from an AI structural analysis.

    Expected analysis format:
    {
        "dimensions": {"width": 12, "height": 8, "depth": 10},
        "walls": {
            "material": "brick",
            "color": "#8B4513",
        },
        "roof": {
            "type": "flat" | "gabled" | "hipped",
            "material": "shingles",
            "color": "#555555",
            "overhang": 0
        },
        "floors": {
            "count": 2,
            "height": 4,  // blocks per floor
            "material": "wood_floor"
        },
        "front_face": {
            "features": [
                {
                    "type": "door",
                    "material": "door_wood",
                    "x": 5,
                    "y": 0,
                    "width": 2,
                    "height": 3
                },
                {
                    "type": "window",
                    "material": "window",
                    "x": 1,
                    "y": 4,
                    "width": 2,
                    "height": 2
                },
                {
                    "type": "sign",
                    "text": "DAVIS CO-OP",
                    "x": 3,
                    "y": 6,
                    "width": 5,
                    "color": "#FFFFFF",
                    "bg_color": "#000000"
                },
                // more features...
            ]
        },
        "back_face": { "features": [...] },
        "left_face": { "features": [...] },
        "right_face": { "features": [...] },
        "interior": "hollow" | "floors" | "solid",
        "ground_features": [
            {"type": "steps", "material": "stone", "x": 4, "z": -1, "width": 4},
        ],
        "accent_blocks": [
            {"type": "trim", "material": "quartz", "positions": "corners"},
        ]
    }
    """
    dims = analysis.get("dimensions", {})
    W = dims.get("width", 10)
    H = dims.get("height", 8)
    D = dims.get("depth", 8)

    # Add 2 extra blocks in each direction for overhangs / steps
    pad = analysis.get("roof", {}).get("overhang", 0)
    sb = StructureBuilder(W + pad * 2, H + 6, D + pad * 2)  # +6 for roof
    ox, oz = pad, pad  # offset for padded origin

    # ── Resolve materials ──
    wall_info = analysis.get("walls", {})
    wall_block = resolve_material(
        wall_info.get("material", "brick"),
        wall_info.get("color")
    )

    floor_info = analysis.get("floors", {})
    floor_count = floor_info.get("count", 1)
    floor_h = floor_info.get("height", 4)
    floor_block = resolve_material(
        floor_info.get("material", "wood_floor"),
        floor_info.get("color")
    )

    roof_info = analysis.get("roof", {})
    roof_block = resolve_material(
        roof_info.get("material", "flat_roof"),
        roof_info.get("color")
    )
    roof_type = roof_info.get("type", "flat")

    interior = analysis.get("interior", "hollow")

    # ── 1. Build walls (hollow box) ──
    for x in range(W):
        for y in range(H):
            for z in range(D):
                is_wall = (x == 0 or x == W - 1 or
                           z == 0 or z == D - 1)
                is_floor_level = (y == 0)

                if is_floor_level:
                    sb.set_block(x + ox, y, z + oz, floor_block)
                elif is_wall:
                    sb.set_block(x + ox, y, z + oz, wall_block)
                elif interior == "floors" and y > 0 and y % floor_h == 0:
                    sb.set_block(x + ox, y, z + oz, floor_block)
                # else: air (interior)

    # ── 2. Place face features ──
    face_map = {
        "front_face": ("z", 0,       "x", 1),   # z=0 face, iterate x
        "back_face":  ("z", D - 1,   "x", 1),   # z=D-1 face
        "left_face":  ("x", 0,       "z", 1),   # x=0 face, iterate z
        "right_face": ("x", W - 1,   "z", 1),   # x=W-1 face
    }

    for face_name, (fixed_axis, fixed_val, var_axis, _) in face_map.items():
        face_data = analysis.get(face_name, {})
        features = face_data.get("features", [])

        for feat in features:
            ft = feat.get("type", "window")
            fx = feat.get("x", 0)
            fy = feat.get("y", 0)
            fw = feat.get("width", 1)
            fh = feat.get("height", 1)

            if ft == "door":
                mat = resolve_material(
                    feat.get("material", "door_wood"),
                    feat.get("color")
                )
            elif ft == "window":
                mat = resolve_material(
                    feat.get("material", "window"),
                    feat.get("color")
                )
            elif ft == "sign":
                mat = resolve_material("sign")
                bg = nearest_block_hex(
                    feat.get("bg_color", "#000000")
                ) if feat.get("bg_color") else wall_block
                # Place sign background
                for dx in range(fw):
                    for dy in range(fh):
                        bx = fx + dx
                        by = fy + dy
                        if fixed_axis == "z":
                            sb.set_block(bx + ox, by, fixed_val + oz, bg)
                        else:
                            sb.set_block(fixed_val + ox, by, bx + oz, bg)
                continue  # sign handled
            elif ft == "awning":
                mat = resolve_material(
                    "awning",
                    feat.get("color", "#2E8B57")
                )
            elif ft == "column" or ft == "pillar":
                mat = resolve_material(
                    feat.get("material", "stone"),
                    feat.get("color")
                )
            else:
                mat = resolve_material(
                    feat.get("material", "stone"),
                    feat.get("color")
                )

            # Place the feature blocks
            for dx in range(fw):
                for dy in range(fh):
                    bx = fx + dx
                    by = fy + dy
                    if fixed_axis == "z":
                        sb.set_block(bx + ox, by, fixed_val + oz, mat)
                    else:
                        sb.set_block(fixed_val + ox, by, bx + oz, mat)

    # ── 3. Build roof ──
    roof_y = H

    if roof_type == "flat":
        for x in range(W):
            for z in range(D):
                sb.set_block(x + ox, roof_y, z + oz, roof_block)

    elif roof_type == "gabled":
        # Ridge along longer axis (X if W >= D)
        if W >= D:
            half = D // 2
            for layer in range(half + 1):
                y = roof_y + layer
                for x in range(W):
                    sb.set_block(x + ox, y, layer + oz, roof_block)
                    sb.set_block(x + ox, y, (D - 1 - layer) + oz, roof_block)
        else:
            half = W // 2
            for layer in range(half + 1):
                y = roof_y + layer
                for z in range(D):
                    sb.set_block(layer + ox, y, z + oz, roof_block)
                    sb.set_block((W - 1 - layer) + ox, y, z + oz, roof_block)

    elif roof_type == "hipped":
        layer = 0
        cx1, cx2 = 0, W - 1
        cz1, cz2 = 0, D - 1
        while cx1 <= cx2 and cz1 <= cz2:
            y = roof_y + layer
            for x in range(cx1, cx2 + 1):
                sb.set_block(x + ox, y, cz1 + oz, roof_block)
                sb.set_block(x + ox, y, cz2 + oz, roof_block)
            for z in range(cz1, cz2 + 1):
                sb.set_block(cx1 + ox, y, z + oz, roof_block)
                sb.set_block(cx2 + ox, y, z + oz, roof_block)
            cx1 += 1; cx2 -= 1
            cz1 += 1; cz2 -= 1
            layer += 1

    # ── 4. Ground features (steps, paths, etc.) ──
    for gf in analysis.get("ground_features", []):
        gf_type = gf.get("type", "step")
        gf_mat = resolve_material(
            gf.get("material", "stone"),
            gf.get("color")
        )
        gfx = gf.get("x", 0)
        gfz = gf.get("z", 0)
        gfw = gf.get("width", 1)
        gfd = gf.get("depth", 1)
        for dx in range(gfw):
            for dz in range(gfd):
                bx = gfx + dx + ox
                bz = gfz + dz + oz
                if 0 <= bx < sb.width and 0 <= bz < sb.depth:
                    sb.set_block(bx, 0, bz, gf_mat)

    # ── 5. Accent / trim ──
    for accent in analysis.get("accent_blocks", []):
        acc_mat = resolve_material(
            accent.get("material", "trim"),
            accent.get("color")
        )
        pos_type = accent.get("positions", "")

        if pos_type == "corners":
            # Vertical corner columns
            for y in range(H):
                sb.set_block(0 + ox, y, 0 + oz, acc_mat)
                sb.set_block(W - 1 + ox, y, 0 + oz, acc_mat)
                sb.set_block(0 + ox, y, D - 1 + oz, acc_mat)
                sb.set_block(W - 1 + ox, y, D - 1 + oz, acc_mat)

        elif pos_type == "top_edge":
            for x in range(W):
                sb.set_block(x + ox, H - 1, 0 + oz, acc_mat)
                sb.set_block(x + ox, H - 1, D - 1 + oz, acc_mat)
            for z in range(D):
                sb.set_block(0 + ox, H - 1, z + oz, acc_mat)
                sb.set_block(W - 1 + ox, H - 1, z + oz, acc_mat)

        elif pos_type == "base":
            for x in range(W):
                sb.set_block(x + ox, 0, 0 + oz, acc_mat)
                sb.set_block(x + ox, 0, D - 1 + oz, acc_mat)
            for z in range(D):
                sb.set_block(0 + ox, 0, z + oz, acc_mat)
                sb.set_block(W - 1 + ox, 0, z + oz, acc_mat)

        elif pos_type == "floor_lines":
            for fl in range(1, floor_count):
                y = fl * floor_h
                for x in range(W):
                    sb.set_block(x + ox, y, 0 + oz, acc_mat)
                    sb.set_block(x + ox, y, D - 1 + oz, acc_mat)
                for z in range(D):
                    sb.set_block(0 + ox, y, z + oz, acc_mat)
                    sb.set_block(W - 1 + ox, y, z + oz, acc_mat)

    # ── 6. Custom block placements (explicit overrides from AI) ──
    for cb in analysis.get("custom_blocks", []):
        cb_id = cb.get("block", "minecraft:stone")
        if not cb_id.startswith("minecraft:"):
            cb_id = resolve_material(cb_id, cb.get("color"))
        cb_x = cb.get("x", 0) + ox
        cb_y = cb.get("y", 0)
        cb_z = cb.get("z", 0) + oz
        if 0 <= cb_x < sb.width and 0 <= cb_y < sb.height and 0 <= cb_z < sb.depth:
            sb.set_block(cb_x, cb_y, cb_z, cb_id)

    return sb
