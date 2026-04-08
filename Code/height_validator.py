"""
BuildDavis — Height Validation Module v3 (Multi-Source Confidence)
==================================================================
Triangulates building heights from multiple independent data sources:
  - OSM explicit tags (human-verified)
  - LiDAR DSM-DTM (direct physical measurement, ±0.1-0.3m)
  - Overture ML estimates (AI-derived from satellite imagery)

When sources agree (within tolerance), confidence is high.
When sources disagree, the building is flagged for review.

Trust hierarchy (used when sources conflict):
  1. OSM explicit (1.0) — never override
  2. LiDAR DSM-DTM (0.95) — direct measurement
  3. Overture ML (0.7) — AI estimate, subject to plausibility check
  4. Type defaults (0.3) — last resort

Flags:
  - RED: sources disagree by >3m — needs manual verification
  - YELLOW: sources disagree by 1-3m — low priority review
  - GREEN: sources agree within 1m — confident

Usage:
    from height_validator import MultiSourceValidator
    validator = MultiSourceValidator(dsm_path="data/davis_dsm_1m.tif",
                                     dtm_path="data/davis_dem_1m.tif")
    result = validator.validate(tags, building_subtype, footprint_area_m2,
                                centroid_lat, centroid_lon, source_info)
"""

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger("height_validator")

# ── Constants ────────────────────────────────────────────────────────
METRES_PER_LEVEL = 3.5

# Agreement thresholds (metres)
AGREE_THRESHOLD_M = 1.0     # sources within 1m = agree (GREEN)
DISAGREE_MINOR_M = 3.0      # 1-3m gap = minor disagreement (YELLOW)
                              # >3m gap = major disagreement (RED)

# Minimum building height from DSM (below this = noise/ground)
DSM_MIN_BUILDING_HEIGHT_M = 2.0

# ── Plausibility limits (used for Overture check) ────────────────────
PLAUSIBILITY_MAX_HEIGHT_M = {
    "house":              9.0,
    "residential":        9.0,
    "detached":           9.0,
    "semidetached_house": 9.0,
    "terrace":           10.0,
    "bungalow":           6.0,
    "apartments":        16.0,
    "dormitory":         16.0,
    "school":            10.0,
    "kindergarten":       6.0,
    "university":        25.0,
    "college":           25.0,
    "commercial":        14.0,
    "retail":            10.0,
    "office":            18.0,
    "garage":             5.0,
    "shed":               4.0,
    "carport":            4.0,
    "yes":               12.0,
    "default":           14.0,
}

FOOTPRINT_RATIO_CHECKS = {
    "school": [
        (500,   6.0),
        (200,  10.0),
        (0,    12.0),
    ],
    "house": [
        (300,   7.0),
        (150,   9.0),
        (0,    10.0),
    ],
    "residential": [
        (300,   7.0),
        (150,   9.0),
        (0,    10.0),
    ],
    "kindergarten": [
        (200,   4.5),
        (0,     6.0),
    ],
}

DEFAULT_HEIGHT_M = {
    "house":        5.0,
    "residential":  5.0,
    "detached":     5.0,
    "apartments":  10.5,
    "school":       4.5,
    "kindergarten": 4.0,
    "university":  10.5,
    "commercial":   7.0,
    "retail":       5.0,
    "office":       7.0,
    "garage":       3.0,
    "shed":         2.5,
    "church":       8.0,
    "yes":          5.0,
    "default":      5.0,
}


@dataclass
class HeightReading:
    """A single height reading from one data source."""
    source: str
    height_m: float
    trust: float
    raw_value: str = ""


@dataclass
class HeightResult:
    """Result of multi-source height validation for one building."""
    final_height_m: float
    final_levels: int
    confidence: float
    flag: str               # "green", "yellow", "red"
    source_used: str
    readings: list = field(default_factory=list)
    note: str = ""


class MultiSourceValidator:
    """Validates building heights by triangulating OSM, LiDAR DSM, and Overture."""

    def __init__(self, dsm_path=None, dtm_path=None):
        self._dsm = None
        self._dtm = None
        self._dsm_transform = None
        self._dtm_transform = None
        self._has_lidar = False

        if dsm_path and dtm_path:
            self._load_rasters(dsm_path, dtm_path)

    def _load_rasters(self, dsm_path, dtm_path):
        try:
            import rasterio
            dsm_p, dtm_p = Path(dsm_path), Path(dtm_path)
            if dsm_p.exists() and dtm_p.exists():
                dsm_src = rasterio.open(dsm_p)
                dtm_src = rasterio.open(dtm_p)
                self._dsm = dsm_src.read(1)
                self._dtm = dtm_src.read(1)
                self._dsm_transform = dsm_src.transform
                self._dtm_transform = dtm_src.transform
                self._dsm_nodata = dsm_src.nodata or -9999.0
                self._dtm_nodata = dtm_src.nodata or -9999.0
                dsm_src.close()
                dtm_src.close()
                self._has_lidar = True
                log.info("LiDAR DSM+DTM loaded for height validation")
            else:
                if not dsm_p.exists():
                    log.warning("DSM not found: %s", dsm_path)
                if not dtm_p.exists():
                    log.warning("DTM not found: %s", dtm_path)
        except ImportError:
            log.warning("rasterio not available — LiDAR heights disabled")
        except Exception as exc:
            log.warning("Failed to load DSM/DTM: %s", exc)

    def _lookup_lidar_height(self, lat, lon):
        if not self._has_lidar:
            return None
        try:
            dsm_col, dsm_row = ~self._dsm_transform * (lon, lat)
            dsm_row, dsm_col = int(dsm_row), int(dsm_col)
            dtm_col, dtm_row = ~self._dtm_transform * (lon, lat)
            dtm_row, dtm_col = int(dtm_row), int(dtm_col)

            if (0 <= dsm_row < self._dsm.shape[0] and
                0 <= dsm_col < self._dsm.shape[1] and
                0 <= dtm_row < self._dtm.shape[0] and
                0 <= dtm_col < self._dtm.shape[1]):

                dsm_val = float(self._dsm[dsm_row, dsm_col])
                dtm_val = float(self._dtm[dtm_row, dtm_col])

                if dsm_val == self._dsm_nodata or dtm_val == self._dtm_nodata:
                    return None

                height = dsm_val - dtm_val
                return round(height, 1) if height >= DSM_MIN_BUILDING_HEIGHT_M else None
        except Exception:
            return None
        return None

    def validate(self, tags, building_subtype=None, footprint_area_m2=None,
                 centroid_lat=None, centroid_lon=None, source_info=None):
        if source_info is None:
            source_info = {}

        subtype = building_subtype or tags.get("building", "yes") or "default"
        readings = []

        # Source 1: OSM explicit
        osm_height = self._get_osm_height(tags)
        if osm_height is not None:
            readings.append(HeightReading("osm", osm_height, 1.0,
                                          tags.get("height", tags.get("building:levels", ""))))

        # Source 2: LiDAR DSM-DTM
        if centroid_lat is not None and centroid_lon is not None:
            lidar_height = self._lookup_lidar_height(centroid_lat, centroid_lon)
            if lidar_height is not None:
                readings.append(HeightReading("lidar_dsm", lidar_height, 0.95,
                                              f"DSM-DTM={lidar_height}m"))

        # Source 3: Overture ML
        overture_height = self._get_overture_height(tags, source_info)
        if overture_height is not None:
            max_plausible = PLAUSIBILITY_MAX_HEIGHT_M.get(
                subtype, PLAUSIBILITY_MAX_HEIGHT_M["default"])
            if footprint_area_m2 and subtype in FOOTPRINT_RATIO_CHECKS:
                for min_fp, max_h in FOOTPRINT_RATIO_CHECKS[subtype]:
                    if footprint_area_m2 >= min_fp:
                        max_plausible = min(max_plausible, max_h)
                        break
            trust = 0.3 if overture_height > max_plausible else 0.7
            readings.append(HeightReading("overture", overture_height, trust,
                                          f"Overture={overture_height}m"))

        result = self._triangulate(readings, subtype)

        # Apply to tags
        tags["height"] = str(round(result.final_height_m, 1))
        tags["building:levels"] = str(result.final_levels)
        tags["_height_source"] = result.source_used
        tags["_height_confidence"] = str(round(result.confidence, 2))
        tags["_height_flag"] = result.flag
        tags["_height_sources"] = json.dumps([
            {"source": r.source, "height_m": r.height_m, "trust": r.trust}
            for r in result.readings
        ])
        return result

    def _get_osm_height(self, tags):
        h_str = tags.get("height")
        if h_str:
            try:
                h = float(str(h_str).rstrip("m "))
                if h > 0:
                    return h
            except (ValueError, TypeError):
                pass
        lv_str = tags.get("building:levels")
        if lv_str:
            try:
                lv = int(float(str(lv_str).strip()))
                if lv > 0:
                    return lv * METRES_PER_LEVEL
            except (ValueError, TypeError):
                pass
        return None

    def _get_overture_height(self, tags, source_info):
        h = source_info.get("overture_height_m")
        if h and float(h) > 0:
            return float(h)
        if source_info.get("height_source") == "overture":
            h_str = tags.get("height")
            if h_str:
                try:
                    return float(str(h_str).rstrip("m "))
                except (ValueError, TypeError):
                    pass
        return None

    def _triangulate(self, readings, subtype):
        if not readings:
            default_h = DEFAULT_HEIGHT_M.get(subtype, DEFAULT_HEIGHT_M["default"])
            return HeightResult(default_h, max(1, round(default_h / METRES_PER_LEVEL)),
                                0.3, "yellow", "type_default", readings,
                                f"No height data — default for {subtype}")

        if len(readings) == 1:
            r = readings[0]
            flag = "yellow" if r.trust < 0.9 else "green"
            return HeightResult(r.height_m, max(1, round(r.height_m / METRES_PER_LEVEL)),
                                r.trust * 0.8, flag, r.source, readings,
                                f"Single source: {r.source}")

        sorted_r = sorted(readings, key=lambda r: r.trust, reverse=True)
        best = sorted_r[0]

        agreements, disagreements = [], []
        for i in range(len(sorted_r)):
            for j in range(i + 1, len(sorted_r)):
                diff = abs(sorted_r[i].height_m - sorted_r[j].height_m)
                pair = (sorted_r[i].source, sorted_r[j].source, diff)
                (agreements if diff <= AGREE_THRESHOLD_M else disagreements).append(pair)

        if agreements and not disagreements:
            total_trust = sum(r.trust for r in sorted_r)
            weighted_h = sum(r.height_m * r.trust for r in sorted_r) / total_trust
            return HeightResult(
                round(weighted_h, 1), max(1, round(weighted_h / METRES_PER_LEVEL)),
                min(1.0, total_trust / len(sorted_r)), "green",
                "multi_source_agree", readings,
                f"{len(sorted_r)} sources agree within {AGREE_THRESHOLD_M}m")

        max_diff = max(d[2] for d in disagreements)
        flag = "yellow" if max_diff <= DISAGREE_MINOR_M else "red"
        notes = [f"Disagreement: max {max_diff:.1f}m"]
        for d in disagreements:
            notes.append(f"{d[0]} vs {d[1]}: {d[2]:.1f}m")

        return HeightResult(best.height_m, max(1, round(best.height_m / METRES_PER_LEVEL)),
                            best.trust * 0.6, flag, best.source, readings,
                            "; ".join(notes))


# ── Backward compatibility ───────────────────────────────────────────
_default_validator = None


def validate_height(tags, building_subtype=None, footprint_area_m2=None,
                    source_info=None, centroid_lat=None, centroid_lon=None):
    global _default_validator
    if _default_validator is None:
        _default_validator = MultiSourceValidator()
    _default_validator.validate(tags, building_subtype, footprint_area_m2,
                                centroid_lat, centroid_lon, source_info)
    return tags


def init_validator(dsm_path=None, dtm_path=None):
    global _default_validator
    _default_validator = MultiSourceValidator(dsm_path=dsm_path, dtm_path=dtm_path)
    return _default_validator

    # 5: Small school (gym) moderate height — accept
    t = {"building": "school", "height": "8.0", "building:levels": "2"}
    r = validate_height(t, "school", 150, {"height_source": "overture"})
    assert r["height"] == "8.0"
    print(f"  5. School gym: 8m (150m2) -> accepted  PASS")

    # 6: No height data — default
    t = {"building": "house"}
    r = validate_height(t, "house", source_info={"height_source": "none"})
    assert r["height"] == "5.0" and r["building:levels"] == "1"
    print(f"  6. No data house -> {r['height']}m / {r['building:levels']}lvl  PASS")

    # 7: Apartments within limits — accept
    t = {"building": "apartments", "height": "12.0", "building:levels": "3"}
    r = validate_height(t, "apartments", 400, {"height_source": "overture"})
    assert r["height"] == "12.0"
    print(f"  7. Apartments 12m (400m2) -> accepted  PASS")

    # 8: UC Davis tall building — accept
    t = {"building": "university", "height": "20.0", "building:levels": "5"}
    r = validate_height(t, "university", 600, {"height_source": "overture"})
    assert r["height"] == "20.0"
    print(f"  8. UC Davis 20m (600m2) -> accepted  PASS")

    # 9: Davis High 2-storey addition (small footprint) — accept
    t = {"building": "school", "height": "9.0", "building:levels": "2"}
    r = validate_height(t, "school", 100, {"height_source": "overture"})
    assert r["height"] == "9.0"
    print(f"  9. DHS addition: 9m (100m2) -> accepted  PASS")

    # 10: Large rambling ranch house — cap height
    t = {"building": "house", "height": "10.0", "building:levels": "3"}
    r = validate_height(t, "house", 350, {"height_source": "overture"})
    assert float(r["height"]) <= 7.0
    print(f"  10. Large ranch: 10m (350m2) -> {r['height']}m  PASS")

    print("\nAll 10 tests passed.")
    print("\nKey: large footprint + tall = implausible. Small footprint + tall = could be legit.")
    print("OSM explicit data is NEVER overridden.")
