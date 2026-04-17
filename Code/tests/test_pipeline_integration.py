"""
Test Pipeline Integration
==========================
End-to-end smoke test:  parse → fuse → adapter  on the micro fixture set.
Validates that data flows through all stages without error and the final
output (enriched Overpass JSON) is structurally sound.
"""

import json
from pathlib import Path


def test_full_pipeline_parse_fuse_adapter(fetch_dir):
    """
    Run parse → fuse → adapter on micro fixtures.
    The resulting Overpass JSON must be non-empty, valid, and free of
    bicycle_parking (BT-002).
    """
    from parse import run_parse
    from fuse import run_fuse
    from adapter import convert

    out_dir = fetch_dir  # reuse same temp dir for all outputs

    # Stage 3: Parse
    run_parse(
        fetch_dir=str(out_dir),
        output_dir=str(out_dir),
        origin_lat=38.5435,
        origin_lon=-121.7377,
    )
    elements_path = out_dir / "elements.json"
    assert elements_path.exists(), "parse did not write elements.json"

    # Stage 4: Fuse
    run_fuse(
        elements_path=str(elements_path),
        output_dir=str(out_dir),
    )
    fused_path = out_dir / "fused_features.geojson"
    assert fused_path.exists(), "fuse did not write fused_features.geojson"

    # Stage 4.5: Adapter
    overpass_path, log_path, summary_path = convert(
        fused_path=fused_path,
        output_dir=out_dir,
    )
    assert overpass_path.exists(), "adapter did not write enriched_overpass.json"

    with open(overpass_path, encoding="utf-8") as f:
        overpass = json.load(f)

    # ── Structural assertions ──
    assert "elements" in overpass
    assert len(overpass["elements"]) > 0, "enriched output has 0 elements"

    # ── BT-002 regression ──
    for elem in overpass["elements"]:
        tags = elem.get("tags", {})
        assert tags.get("amenity") != "bicycle_parking", (
            "bicycle_parking leaked through full pipeline"
        )

    # ── All elements have valid types ──
    for elem in overpass["elements"]:
        assert elem["type"] in ("node", "way", "relation")


def test_pipeline_element_count_reasonable(fetch_dir):
    """
    The micro fixture has 5 OSM elements + 2 Overture buildings.
    After fusion and adapter, we expect the _way_ count to be at least 3
    (2 buildings + 1 road — some may merge, park may drop).
    """
    from parse import run_parse
    from fuse import run_fuse
    from adapter import convert

    out_dir = fetch_dir
    run_parse(str(out_dir), str(out_dir), 38.5435, -121.7377)
    run_fuse(str(out_dir / "elements.json"), str(out_dir))
    op, _, _ = convert(out_dir / "fused_features.geojson", out_dir)

    with open(op) as f:
        data = json.load(f)

    ways = [e for e in data["elements"] if e["type"] == "way"]
    assert len(ways) >= 3, (
        f"Expected >= 3 ways from micro fixtures, got {len(ways)}"
    )
