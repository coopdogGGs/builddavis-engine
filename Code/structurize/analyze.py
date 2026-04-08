"""
Vision AI analyzer — sends an image to Claude and gets a structured
building/object analysis for Minecraft structure generation.

Supports:
  - Claude API (anthropic SDK) with vision
  - Loading a pre-made JSON analysis file (for testing without API)
"""

import base64
import json
import os
import sys
from pathlib import Path
from typing import Optional

ANALYSIS_PROMPT = """You are a Minecraft structure architect. Analyze this image and produce a JSON specification that describes how to recreate this structure in Minecraft at 1:1 scale (1 block = 1 meter).

IMPORTANT RULES:
- All dimensions are in Minecraft blocks (1 block = 1 meter)
- The structure faces SOUTH (front_face is at z=0, looking toward +Z)
- Y=0 is ground level, Y increases upward
- X increases to the right when facing the front
- Z increases away from the viewer (depth)
- Use realistic dimensions: a door is 1-2 wide × 3 tall, a window is 1-3 wide × 2 tall
- A typical floor is 4 blocks tall (3 interior + 1 ceiling)
- Colors should be hex codes matching what you see

Return ONLY valid JSON (no markdown, no comments) with this exact structure:

{
    "description": "Brief description of what this is",
    "dimensions": {
        "width": <int, total X span in blocks>,
        "height": <int, total wall height in blocks, not including roof>,
        "depth": <int, total Z span in blocks>
    },
    "walls": {
        "material": "<material name from: brick, red_brick, stone, concrete, stucco, wood, wood_dark, wood_light, metal, glass, sandstone, plaster, adobe, marble, cinder_block>",
        "color": "<hex color of the primary wall material>"
    },
    "roof": {
        "type": "<flat, gabled, or hipped>",
        "material": "<shingles, tile_roof, metal_roof, flat_roof, slate, thatch>",
        "color": "<hex color>",
        "overhang": <int, blocks of overhang, usually 0 or 1>
    },
    "floors": {
        "count": <int, number of stories>,
        "height": 4,
        "material": "wood_floor",
        "color": null
    },
    "front_face": {
        "features": [
            {
                "type": "<door|window|sign|awning|column|pillar>",
                "material": "<material name or null for default>",
                "color": "<hex or null>",
                "x": <int, left edge position on this face>,
                "y": <int, bottom edge position>,
                "width": <int>,
                "height": <int>,
                "text": "<only for signs, the text to display>"
            }
        ]
    },
    "back_face": { "features": [] },
    "left_face": { "features": [] },
    "right_face": { "features": [] },
    "interior": "<hollow|floors|solid>",
    "ground_features": [
        {
            "type": "<step|path|planter>",
            "material": "<material name>",
            "color": "<hex or null>",
            "x": <int>,
            "z": <int, negative = in front of building>,
            "width": <int>,
            "depth": <int>
        }
    ],
    "accent_blocks": [
        {
            "material": "<material name>",
            "color": "<hex or null>",
            "positions": "<corners|top_edge|base|floor_lines>"
        }
    ],
    "custom_blocks": []
}

Analyze the image carefully:
1. Estimate real-world dimensions and convert to blocks
2. Identify all visible doors, windows, and architectural features
3. Note materials and colors
4. Describe the roof type
5. Place features at accurate positions on the correct face
6. If this is not a building (e.g., statue, bike, sign), adapt the schema — use custom_blocks for freeform shapes

Return ONLY the JSON."""


def analyze_image(
    image_path: str,
    api_key: Optional[str] = None,
    model: str = "claude-sonnet-4-20250514",
    constraint_width: Optional[int] = None,
    constraint_depth: Optional[int] = None,
    constraint_height: Optional[int] = None,
) -> dict:
    """
    Send an image to Claude vision API and get structural analysis.

    Args:
        image_path: Path to the image file (PNG, JPG, GIF, TIFF).
        api_key: Anthropic API key. Defaults to ANTHROPIC_API_KEY env var.
        model: Claude model to use.
        constraint_width: Max width in blocks (from OSM footprint).
        constraint_depth: Max depth in blocks (from OSM footprint).
        constraint_height: Max height in blocks.

    Returns:
        Parsed JSON dict with the structural analysis.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("ERROR: No API key. Set ANTHROPIC_API_KEY env var or pass --api-key.")
        sys.exit(1)

    # Read and encode image
    img_path = Path(image_path)
    if not img_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    suffix = img_path.suffix.lower()
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".tiff": "image/png",  # convert TIFF below
        ".tif": "image/png",
        ".webp": "image/webp",
    }
    media_type = media_types.get(suffix, "image/png")

    # Handle TIFF → PNG conversion
    if suffix in (".tiff", ".tif"):
        try:
            from PIL import Image
            img = Image.open(image_path)
            import io
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            image_data = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
            media_type = "image/png"
        except ImportError:
            raise RuntimeError("Pillow required for TIFF support: pip install Pillow")
    else:
        with open(image_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    # Build constraint addendum
    extra = ""
    if constraint_width or constraint_depth or constraint_height:
        extra = "\n\nCONSTRAINTS — the structure MUST fit within these bounds:"
        if constraint_width:
            extra += f"\n- Maximum width (X): {constraint_width} blocks"
        if constraint_depth:
            extra += f"\n- Maximum depth (Z): {constraint_depth} blocks"
        if constraint_height:
            extra += f"\n- Maximum height (Y): {constraint_height} blocks"
        extra += "\nScale the structure proportionally to fit if needed."

    prompt = ANALYSIS_PROMPT + extra

    # Call Claude API
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic SDK required: pip install anthropic")

    client = anthropic.Anthropic(api_key=key)

    message = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
        ],
    )

    # Extract JSON from response
    response_text = message.content[0].text.strip()

    # Try to parse JSON — handle markdown code fences if present
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        # Remove first and last lines (code fences)
        json_lines = []
        in_json = False
        for line in lines:
            if line.strip().startswith("```") and not in_json:
                in_json = True
                continue
            elif line.strip() == "```":
                break
            elif in_json:
                json_lines.append(line)
        response_text = "\n".join(json_lines)

    try:
        analysis = json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"WARNING: Failed to parse AI response as JSON: {e}")
        print(f"Raw response:\n{response_text[:500]}")
        # Try to find JSON object in response
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                analysis = json.loads(response_text[start:end])
            except json.JSONDecodeError:
                raise ValueError(f"Could not extract valid JSON from AI response")
        else:
            raise ValueError(f"No JSON object found in AI response")

    return analysis


def load_analysis(json_path: str) -> dict:
    """Load a pre-made analysis JSON file (for testing without API)."""
    with open(json_path, "r") as f:
        return json.load(f)


def save_analysis(analysis: dict, output_path: str):
    """Save an analysis dict to JSON for caching / editing."""
    with open(output_path, "w") as f:
        json.dump(analysis, f, indent=2)
    print(f"Analysis saved to {output_path}")
