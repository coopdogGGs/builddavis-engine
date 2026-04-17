"""
Generate a 64x64 server-icon.png for the BuildDavis Paper server.

Style: Chunky Minecraft pixel-art of Davis CA — a small TOWN, not a city.
       Short houses, big oak trees, the water tower, grass everywhere.
       Drawn at 16×16 then nearest-neighbor 4× upscale for maximum chunkiness.
       Big bold "DAVIS" pixel text dominates the image.

Output: server/server-icon.png (64x64 PNG, required by Minecraft)
"""
from PIL import Image, ImageDraw
import os

# 16×16 canvas → 4× upscale = 64×64. Every pixel becomes a 4×4 block.
W = H = 16
SCALE = 4

# ── Palette ──────────────────────────────────────────────────────
SKY_HI  = (100, 170, 235)      # upper sky
SKY_LO  = (140, 200, 245)      # lower sky
GRASS   = (75, 135, 50)         # lush Davis grass
GRASS2  = (65, 120, 45)         # darker grass accent

# Town buildings — short, warm tones (Davis stucco/brick)
HOUSE1  = (195, 170, 140)      # stucco tan
HOUSE2  = (170, 120, 90)       # brick
HOUSE3  = (185, 160, 135)      # light stucco
ROOF1   = (120, 75, 50)        # brown roof
ROOF2   = (100, 65, 45)        # dark roof

# Water tower
TOWER_BODY = (180, 180, 185)   # steel grey
TOWER_LEG  = (130, 130, 135)   # dark steel

# Trees — Davis is "Tree City USA"
LEAF1   = (45, 115, 40)
LEAF2   = (55, 130, 48)
LEAF3   = (40, 105, 38)
TRUNK   = (90, 60, 35)

# Text
WHITE   = (255, 255, 255)
BLACK   = (20, 20, 20)
OUTLINE = (50, 50, 50)

# ── Big 5×3 pixel font for "DAVIS" ──────────────────────────────
# Each letter: 3px wide × 5px tall. At 4× scale each dot = 4×4 block.
# "DAVIS" = 5 letters × 3px + 4 gaps × 1px = 19px — too wide for 16px.
# Use a tighter 2px-wide font so "DAVIS" = 5×2 + 4×1 = 14px → fits with 1px margin each side.
FONT = {
    'D': [(0,0),(0,1),(0,2),(0,3),(0,4), (1,0),(1,4), (1,1)],  # |> shape
    'A': [(0,1),(0,2),(0,3),(0,4), (1,0), (1,2), (1,4)],       # triangle
    'V': [(0,0),(0,1),(0,2), (1,3),(1,4), (1,0),(1,1)],         # \ shape — rewritten
    'I': [(0,0),(1,0), (0,4),(1,4), (0,1),(0,2),(0,3)],         # serifed I
    'S': [(1,0),(0,1),(1,2),(0,3),(1,3),(1,4)],                  # zigzag S — tightened
}
# Actually let me re-do these properly as 3-wide so they're readable at 4× scale
# 3 wide × 5 tall, total width = 5*3 + 4*1 = 19 — won't fit in 16.
# So use 3-wide but overlap: render at shifted canvas. Or… just make canvas 20 wide.
# Better: use the 16-wide canvas for the scene, but render text in a separate pass
# at the final 64×64 resolution using a 4px-per-dot font drawn directly.

# 4px-per-dot font glyphs at 64×64 scale (each coordinate = 4px block)
# Letters are 3 dots wide × 5 dots tall → 12px × 20px per letter
# "DAVIS" = 5*12 + 4*4 gap = 76px — too wide for 64.
# Use 3 dots wide × 5 tall but 3px per dot: 5*(3*3) + 4*3 = 57px. With 2px gap: 5*9+4*2=53. Fits!
DOT = 3  # pixels per dot in the final 64×64 image
GAP = 2  # pixels between letters
GLYPH = {
    'D': [
        (0,0),(1,0),
        (0,1),(2,1),
        (0,2),(2,2),
        (0,3),(2,3),
        (0,4),(1,4),
    ],
    'A': [
        (0,0),(1,0),(2,0),
        (0,1),(2,1),
        (0,2),(1,2),(2,2),
        (0,3),(2,3),
        (0,4),(2,4),
    ],
    'V': [
        (0,0),(2,0),
        (0,1),(2,1),
        (0,2),(2,2),
        (0,3),(2,3),
        (1,4),
    ],
    'I': [
        (0,0),(1,0),(2,0),
        (1,1),
        (1,2),
        (1,3),
        (0,4),(1,4),(2,4),
    ],
    'S': [
        (1,0),(2,0),
        (0,1),
        (0,2),(1,2),
        (2,3),
        (0,4),(1,4),
    ],
}
GLYPH_W = 3  # dots
GLYPH_H = 5  # dots


def draw_scene(draw: ImageDraw.Draw):
    """Small-town Davis: grass, short houses, big trees, water tower."""

    # Sky — two bands
    draw.rectangle([0, 0, W-1, 5], fill=SKY_HI)
    draw.rectangle([0, 6, W-1, 8], fill=SKY_LO)

    # Ground — grass from y=9 down
    draw.rectangle([0, 9, W-1, H-1], fill=GRASS)
    # A few darker grass accent pixels
    for gx in [1, 5, 10, 14]:
        draw.point((gx, 10), fill=GRASS2)

    horizon = 9  # grass starts here

    # ── Water tower (Davis landmark) — right side ──
    # Tank: 2px wide × 2px tall at top
    draw.rectangle([12, 3, 13, 4], fill=TOWER_BODY)
    # Legs: 2 single pixels below
    draw.point((12, 5), fill=TOWER_LEG)
    draw.point((13, 5), fill=TOWER_LEG)
    draw.point((12, 6), fill=TOWER_LEG)
    draw.point((13, 6), fill=TOWER_LEG)

    # ── Houses — short (2-3px tall), spread out ──
    # House 1: left
    draw.rectangle([1, 7, 3, 8], fill=HOUSE1)
    draw.rectangle([1, 6, 3, 6], fill=ROOF1)  # roof

    # House 2: center-left
    draw.rectangle([5, 7, 7, 8], fill=HOUSE2)
    draw.rectangle([5, 6, 7, 6], fill=ROOF2)

    # House 3: center-right
    draw.rectangle([9, 7, 10, 8], fill=HOUSE3)
    draw.rectangle([9, 6, 10, 6], fill=ROOF1)

    # Windows — single bright pixels
    draw.point((2, 7), fill=(200, 220, 240))
    draw.point((6, 7), fill=(200, 220, 240))

    # ── Trees — big oaks, taller than houses (Davis = Tree City USA) ──
    # Tree 1: far left
    draw.point((0, 8), fill=TRUNK)
    draw.rectangle([0, 5, 0, 7], fill=LEAF1)  # single-pixel-wide canopy

    # Tree 2: between houses
    draw.point((4, 8), fill=TRUNK)
    draw.rectangle([3, 5, 5, 7], fill=LEAF2)  # 3px wide canopy — big oak

    # Tree 3: right of houses
    draw.point((11, 8), fill=TRUNK)
    draw.rectangle([11, 5, 11, 7], fill=LEAF3)

    # Tree 4: far right behind water tower
    draw.point((15, 8), fill=TRUNK)
    draw.rectangle([14, 5, 15, 7], fill=LEAF1)


def draw_text_on_final(img: Image.Image):
    """Draw big bold 'DAVIS' text directly on the 64×64 image."""
    draw = ImageDraw.Draw(img)

    text = "DAVIS"
    letter_px = GLYPH_W * DOT                    # 9px per letter
    total_w = len(text) * letter_px + (len(text) - 1) * GAP  # 5*9 + 4*2 = 53px
    ox = (64 - total_w) // 2                      # ~5px left margin
    oy = 64 // 2 - (GLYPH_H * DOT) // 2 + 6      # vertically centered, nudged down over town

    # Dark banner behind text
    draw.rectangle([ox - 2, oy - 2, ox + total_w + 1, oy + GLYPH_H * DOT + 1],
                   fill=(15, 15, 15))

    # Draw each letter
    cx = ox
    for ch in text:
        dots = GLYPH.get(ch, [])
        for dx, dy in dots:
            px = cx + dx * DOT
            py = oy + dy * DOT
            # Outline (1px border around each dot-block)
            draw.rectangle([px - 1, py - 1, px + DOT, py + DOT], fill=OUTLINE)
        for dx, dy in dots:
            px = cx + dx * DOT
            py = oy + dy * DOT
            draw.rectangle([px, py, px + DOT - 1, py + DOT - 1], fill=WHITE)
        cx += letter_px + GAP


def main():
    # Draw scene at 16×16
    img = Image.new('RGB', (W, H))
    draw = ImageDraw.Draw(img)
    draw_scene(draw)

    # Scale 4× with NEAREST — every pixel becomes a 4×4 Minecraft-style block
    big = img.resize((64, 64), Image.NEAREST)

    # Overlay crisp text at full 64×64 resolution
    draw_text_on_final(big)

    out_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "server", "server-icon.png")
    big.save(out_path, "PNG")
    print(f"Server icon saved: {out_path} ({os.path.getsize(out_path)} bytes)")


if __name__ == "__main__":
    main()
