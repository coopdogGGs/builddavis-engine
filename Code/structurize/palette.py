"""
Minecraft block color palette and nearest-color matching.

Maps ~80 commonly used Minecraft blocks to their average RGB face colors.
Uses CIELAB ΔE (CIE76) for perceptually accurate color distance matching.
"""

import math
from typing import Tuple, Optional

# --------------------------------------------------------------------------- #
# Block RGB database — average visible face colour for each block
# Tuples are (R, G, B) 0-255
# --------------------------------------------------------------------------- #

BLOCK_COLORS: dict[str, Tuple[int, int, int]] = {
    # ── Concrete (16) ──
    "minecraft:white_concrete":        (207, 213, 214),
    "minecraft:orange_concrete":       (224,  97,   1),
    "minecraft:magenta_concrete":      (169,  48, 159),
    "minecraft:light_blue_concrete":   ( 58, 179, 218),
    "minecraft:yellow_concrete":       (240, 175,  21),
    "minecraft:lime_concrete":         ( 94, 169,  25),
    "minecraft:pink_concrete":         (213, 101, 143),
    "minecraft:gray_concrete":         ( 54,  57,  61),
    "minecraft:light_gray_concrete":   (125, 125, 115),
    "minecraft:cyan_concrete":         ( 21, 119, 136),
    "minecraft:purple_concrete":       (100,  32, 156),
    "minecraft:blue_concrete":         ( 45,  47, 143),
    "minecraft:brown_concrete":        ( 96,  60,  32),
    "minecraft:green_concrete":        ( 73,  91,  36),
    "minecraft:red_concrete":          (142,  33,  33),
    "minecraft:black_concrete":        (  8,  10,  15),

    # ── Terracotta (17) ──
    "minecraft:terracotta":            (152,  94,  68),
    "minecraft:white_terracotta":      (210, 178, 161),
    "minecraft:orange_terracotta":     (162,  84,  38),
    "minecraft:magenta_terracotta":    (150,  88, 109),
    "minecraft:light_blue_terracotta": (113, 109, 138),
    "minecraft:yellow_terracotta":     (186, 133,  35),
    "minecraft:lime_terracotta":       (104, 118,  53),
    "minecraft:pink_terracotta":       (162,  78,  79),
    "minecraft:gray_terracotta":       ( 58,  42,  36),
    "minecraft:light_gray_terracotta": (135, 107,  98),
    "minecraft:cyan_terracotta":       ( 87,  91,  91),
    "minecraft:purple_terracotta":     (118,  70,  86),
    "minecraft:blue_terracotta":       ( 74,  60,  91),
    "minecraft:brown_terracotta":      ( 77,  51,  36),
    "minecraft:green_terracotta":      ( 76,  83,  42),
    "minecraft:red_terracotta":        (143,  61,  47),
    "minecraft:black_terracotta":      ( 37,  23,  16),

    # ── Wool (16) ──
    "minecraft:white_wool":            (234, 236, 236),
    "minecraft:orange_wool":           (241, 118,  20),
    "minecraft:magenta_wool":          (189,  68, 179),
    "minecraft:light_blue_wool":       ( 58, 175, 217),
    "minecraft:yellow_wool":           (248, 199,  40),
    "minecraft:lime_wool":             (112, 185,  26),
    "minecraft:pink_wool":             (238, 141, 172),
    "minecraft:gray_wool":             ( 63,  68,  72),
    "minecraft:light_gray_wool":       (142, 142, 135),
    "minecraft:cyan_wool":             ( 21, 138, 145),
    "minecraft:purple_wool":           (122,  42, 173),
    "minecraft:blue_wool":             ( 53,  57, 157),
    "minecraft:brown_wool":            (114,  72,  41),
    "minecraft:green_wool":            ( 85, 110,  28),
    "minecraft:red_wool":              (161,  39,  35),
    "minecraft:black_wool":            ( 20,  21,  26),

    # ── Stone / Mineral ──
    "minecraft:stone":                 (126, 126, 126),
    "minecraft:cobblestone":           (127, 127, 127),
    "minecraft:stone_bricks":          (122, 122, 122),
    "minecraft:mossy_stone_bricks":    (115, 121, 105),
    "minecraft:cracked_stone_bricks":  (118, 117, 118),
    "minecraft:smooth_stone":          (160, 160, 160),
    "minecraft:andesite":              (136, 136, 136),
    "minecraft:polished_andesite":     (132, 135, 133),
    "minecraft:diorite":               (188, 188, 188),
    "minecraft:granite":               (154, 107,  89),
    "minecraft:deepslate":             ( 80,  80,  82),
    "minecraft:deepslate_bricks":      ( 70,  70,  72),
    "minecraft:blackstone":            ( 42,  36,  41),
    "minecraft:obsidian":              ( 20,  18,  30),

    # ── Sandstone ──
    "minecraft:sandstone":             (219, 211, 160),
    "minecraft:smooth_sandstone":      (223, 214, 163),
    "minecraft:red_sandstone":         (186, 100,  29),
    "minecraft:smooth_red_sandstone":  (181,  97,  31),

    # ── Brick / Nether ──
    "minecraft:bricks":                (150,  97,  83),
    "minecraft:nether_bricks":         ( 44,  22,  26),
    "minecraft:red_nether_bricks":     ( 69,   7,  10),
    "minecraft:mud_bricks":            (137, 104,  76),

    # ── Wood Planks ──
    "minecraft:oak_planks":            (162, 131,  79),
    "minecraft:spruce_planks":         (115,  85,  49),
    "minecraft:birch_planks":          (196, 179, 123),
    "minecraft:dark_oak_planks":       ( 67,  43,  20),
    "minecraft:acacia_planks":         (168,  90,  50),
    "minecraft:jungle_planks":         (160, 115,  81),
    "minecraft:mangrove_planks":       (117,  54,  48),
    "minecraft:cherry_planks":         (226, 178, 172),

    # ── Metal / Precious ──
    "minecraft:iron_block":            (220, 220, 220),
    "minecraft:gold_block":            (249, 212,  57),
    "minecraft:copper_block":          (192, 107,  80),
    "minecraft:oxidized_copper":       ( 82, 162, 132),

    # ── Glass ──
    "minecraft:glass":                 (175, 213, 219),
    "minecraft:tinted_glass":          ( 44,  38,  51),
    "minecraft:white_stained_glass":   (255, 255, 255),
    "minecraft:light_gray_stained_glass": (153, 153, 153),
    "minecraft:gray_stained_glass":    ( 76,  76,  76),
    "minecraft:black_stained_glass":   ( 25,  25,  25),
    "minecraft:light_blue_stained_glass": (102, 153, 216),
    "minecraft:cyan_stained_glass":    ( 76, 127, 153),
    "minecraft:blue_stained_glass":    ( 51,  76, 178),

    "minecraft:iron_bars":             (169, 169, 169),
    "minecraft:iron_chain":            (150, 150, 160),

    # ── Misc ──
    "minecraft:smooth_quartz":         (236, 230, 223),
    "minecraft:quartz_block":          (236, 230, 223),
    "minecraft:prismarine":            ( 99, 172, 158),
    "minecraft:sea_lantern":           (172, 199, 190),
    "minecraft:glowstone":             (171, 131,  68),
    "minecraft:bone_block":            (229, 225, 207),
    "minecraft:calcite":               (224, 225, 221),
    "minecraft:snow_block":            (249, 254, 254),
    "minecraft:packed_ice":            (141, 180, 224),
    "minecraft:clay":                  (160, 166, 179),
    "minecraft:dried_kelp_block":      ( 50,  55,  27),
    "minecraft:hay_block":             (166, 137,  24),
    "minecraft:melon":                 (111, 145,  30),
    "minecraft:pumpkin":               (198, 119,  10),

    # ── Functional ──
    "minecraft:oak_door":              (140, 110,  60),
    "minecraft:iron_door":             (195, 195, 195),
    "minecraft:oak_trapdoor":          (130, 100,  55),
    "minecraft:oak_log":               (109,  85,  51),
    "minecraft:stripped_oak_log":       (177, 144,  86),
}

# Transparent / air
AIR = "minecraft:air"

# --------------------------------------------------------------------------- #
# CIELAB colour-space utilities
# --------------------------------------------------------------------------- #

def _srgb_to_linear(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def rgb_to_lab(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """Convert sRGB (0-255) to CIELAB."""
    lr = _srgb_to_linear(r)
    lg = _srgb_to_linear(g)
    lb = _srgb_to_linear(b)

    x = 0.4124564 * lr + 0.3575761 * lg + 0.1804375 * lb
    y = 0.2126729 * lr + 0.7151522 * lg + 0.0721750 * lb
    z = 0.0193339 * lr + 0.1191920 * lg + 0.9503041 * lb

    x /= 0.95047
    z /= 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    L = 116 * fy - 16
    a = 500 * (fx - fy)
    b_val = 200 * (fy - fz)
    return (L, a, b_val)


def delta_e(lab1: Tuple[float, float, float],
            lab2: Tuple[float, float, float]) -> float:
    """CIE76 colour distance."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(lab1, lab2)))


# Pre-compute LAB values for all blocks
_BLOCK_LAB: dict[str, Tuple[float, float, float]] = {}
for _bid, _rgb in BLOCK_COLORS.items():
    _BLOCK_LAB[_bid] = rgb_to_lab(*_rgb)


def nearest_block(r: int, g: int, b: int,
                  exclude: Optional[set] = None) -> str:
    """Find the Minecraft block whose colour is closest to the given RGB."""
    target_lab = rgb_to_lab(r, g, b)
    best_id = "minecraft:stone"
    best_dist = float("inf")
    for bid, blab in _BLOCK_LAB.items():
        if exclude and bid in exclude:
            continue
        d = delta_e(target_lab, blab)
        if d < best_dist:
            best_dist = d
            best_id = bid
    return best_id


def nearest_block_hex(hex_color: str,
                      exclude: Optional[set] = None) -> str:
    """Find nearest block from a hex colour string like '#8B4513'."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return nearest_block(r, g, b, exclude)


def block_rgb(block_id: str) -> Optional[Tuple[int, int, int]]:
    """Return the RGB tuple for a known block, or None."""
    return BLOCK_COLORS.get(block_id)
