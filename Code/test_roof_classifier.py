"""
Test the LiDAR roof shape classifier against known roof profiles.

Creates synthetic DSM elevation grids that simulate each roof type,
then verifies the classifier returns the correct shape.

Usage:
    python test_roof_classifier.py
"""

import numpy as np
import sys

# Import the classifier from lidar.py
from lidar import _classify_roof_shape


def make_flat_roof(w=15, h=12, base_height=5.0):
    """Flat roof — uniform elevation."""
    return np.full((h, w), base_height, dtype=np.float32)


def make_gabled_roof(w=15, h=12, base_height=5.0, ridge_height=3.0):
    """
    Gabled roof — ridge runs along the long axis (east-west),
    slopes on two sides (north and south).
    """
    roof = np.zeros((h, w), dtype=np.float32)
    mid = h // 2
    for r in range(h):
        dist_from_ridge = abs(r - mid)
        slope = max(0, ridge_height * (1 - dist_from_ridge / mid))
        roof[r, :] = base_height + slope
    return roof


def make_hipped_roof(w=15, h=12, base_height=5.0, ridge_height=3.0):
    """
    Hipped roof — ridge is shorter than building length,
    slopes on all four sides.
    """
    roof = np.zeros((h, w), dtype=np.float32)
    mid_r = h // 2
    mid_c = w // 2
    ridge_half_len = w // 4  # ridge is ~50% of building length

    for r in range(h):
        for c in range(w):
            dist_r = abs(r - mid_r) / max(mid_r, 1)
            dist_c = max(0, (abs(c - mid_c) - ridge_half_len)) / max(mid_c, 1)
            dist = max(dist_r, dist_c)
            elev = max(0, ridge_height * (1 - dist))
            roof[r, c] = base_height + elev
    return roof


def make_pyramidal_roof(w=12, h=12, base_height=5.0, peak_height=4.0):
    """Pyramidal roof — single peak at center, slopes in all directions."""
    roof = np.zeros((h, w), dtype=np.float32)
    center_r, center_c = h // 2, w // 2
    max_dist = np.sqrt(center_r**2 + center_c**2)
    for r in range(h):
        for c in range(w):
            dist = np.sqrt((r - center_r)**2 + (c - center_c)**2)
            elev = max(0, peak_height * (1 - dist / max_dist))
            roof[r, c] = base_height + elev
    return roof


def make_skillion_roof(w=15, h=12, low=4.0, high=7.0):
    """Skillion (shed) roof — consistent slope in one direction."""
    roof = np.zeros((h, w), dtype=np.float32)
    for r in range(h):
        elev = low + (high - low) * (r / max(h - 1, 1))
        roof[r, :] = elev
    return roof


def test_one(name, surface, expected_shape):
    """Run classifier on a surface and check result."""
    shape, orientation, confidence = _classify_roof_shape(surface)
    status = "PASS" if shape == expected_shape else "FAIL"
    print(f"  [{status}]  {name:20s}  expected={expected_shape:10s}  "
          f"got={shape:10s}  orientation={str(orientation):6s}  "
          f"confidence={confidence:.2f}")
    return shape == expected_shape


def main():
    print("=" * 70)
    print("  Roof Shape Classifier — Synthetic Tests")
    print("=" * 70)

    tests = [
        ("Flat (uniform)",       make_flat_roof(),                         "flat"),
        ("Flat (slight noise)",  make_flat_roof() + np.random.normal(0, 0.1, (12, 15)).astype(np.float32), "flat"),
        ("Gabled (standard)",    make_gabled_roof(),                       "gabled"),
        ("Gabled (steep)",       make_gabled_roof(ridge_height=5.0),       "gabled"),
        ("Gabled (wide)",        make_gabled_roof(w=20, h=10),             "gabled"),
        ("Hipped (standard)",    make_hipped_roof(),                       "hipped"),
        ("Hipped (square)",      make_hipped_roof(w=12, h=12),             "hipped"),
        ("Pyramidal (standard)", make_pyramidal_roof(),                     "pyramidal"),
        ("Pyramidal (tall)",     make_pyramidal_roof(peak_height=6.0),      "pyramidal"),
        ("Skillion (standard)",  make_skillion_roof(),                      "skillion"),
        ("Skillion (gentle)",    make_skillion_roof(low=5.0, high=6.5),     "skillion"),
    ]

    passed = 0
    total = len(tests)

    for name, surface, expected in tests:
        if test_one(name, surface, expected):
            passed += 1

    print()
    print(f"  Results: {passed}/{total} passed")
    print("=" * 70)

    if passed < total:
        print("  Some tests failed — classifier may need threshold tuning.")
        sys.exit(1)
    else:
        print("  All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
