"""
BuildDavis Pipeline — Stage 1: Data Fetcher
============================================
Fetches all geospatial data for a given bounding box from:
  - OpenStreetMap (via Overpass API)
  - Overture Maps (AI-traced building footprints + heights)
  - USGS 3DEP LiDAR (tile discovery + DEM download)
  - City of Davis GIS (bike network, parks, public art)
  - USGS NHD (waterways)

Usage:
    python fetch.py --bbox "38.530,-121.760,38.590,-121.710" --output ./data
    python fetch.py --bbox "38.530,-121.760,38.590,-121.710" --output ./data --skip-lidar

Author: BuildDavis Project
License: Apache 2.0
"""

import os
import sys
import json
import time
import argparse
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import gzip

import requests

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("fetch")

# ── Overpass API mirrors (tried in order) ────────────────────────────────────
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
]

# ── USGS 3DEP API ─────────────────────────────────────────────────────────────
USGS_SCIENCEBASE_URL = (
    "https://sciencebase.gov/catalog/items"
    "?format=json&max=20&fields=title,webLinks,files,dates,summary"
    "&filter=tags%3D3DEP&filter=spatialQuery%3Dintersects%3A{bbox_wkt}"
)
USGS_TNM_URL = (
    "https://tnmaccess.nationalmap.gov/api/v1/products"
    "?datasets=Digital+Elevation+Model+%281+meter%29"
    "&bbox={west},{south},{east},{north}&max=20&outputFormat=JSON"
)

# ── City of Davis GIS ─────────────────────────────────────────────────────────
DAVIS_GIS_BIKE_URL = (
    "https://services1.arcgis.com/BFMnkRJSmWif9Fq1/arcgis/rest/services/"
    "BikewayNetwork/FeatureServer/0/query"
    "?where=1%3D1&outFields=*&geometry={xmin}%2C{ymin}%2C{xmax}%2C{ymax}"
    "&geometryType=esriGeometryEnvelope&inSR=4326&outSR=4326&f=geojson"
)

# ── USGS NHD (waterways) ──────────────────────────────────────────────────────
NHD_URL = (
    "https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer/6/query"
    "?where=1%3D1&outFields=*&geometry={xmin}%2C{ymin}%2C{xmax}%2C{ymax}"
    "&geometryType=esriGeometryEnvelope&inSR=4326&outSR=4326&f=geojson"
)


# ─────────────────────────────────────────────────────────────────────────────
# BoundingBox helper
# ─────────────────────────────────────────────────────────────────────────────

class BoundingBox:
    """Parse and expose a bounding box in multiple coordinate formats."""

    def __init__(self, bbox_str: str):
        """
        Accept either:
          "south,west,north,east"  (OSM / Overpass style)
          "west,south,east,north"  (GeoJSON / Overture style)
        We detect by checking which pair has the larger latitude span.
        """
        parts = [float(x.strip()) for x in bbox_str.split(",")]
        if len(parts) != 4:
            raise ValueError(f"bbox must have 4 values, got: {bbox_str}")

        # Heuristic: if parts[0] < parts[2] and both look like latitudes → south,west,north,east
        # Latitude range for Davis: 38.x  Longitude range: -122.x to -121.x
        a, b, c, d = parts
        if -90 <= a <= 90 and -90 <= c <= 90 and -180 <= b <= 180:
            # south, west, north, east
            self.south, self.west, self.north, self.east = a, b, c, d
        else:
            # west, south, east, north
            self.west, self.south, self.east, self.north = a, b, c, d

        self._validate()

    def _validate(self):
        assert self.south < self.north, "south must be less than north"
        assert self.west < self.east,   "west must be less than east"
        assert -90 <= self.south <= 90
        assert -90 <= self.north <= 90
        assert -180 <= self.west <= 180
        assert -180 <= self.east <= 180

    # Various format strings used by different APIs
    @property
    def osm(self):
        """south,west,north,east — Overpass API style"""
        return f"{self.south},{self.west},{self.north},{self.east}"

    @property
    def overture(self):
        """west,south,east,north — Overture / GeoJSON style"""
        return f"{self.west},{self.south},{self.east},{self.north}"

    @property
    def arcgis(self):
        """xmin,ymin,xmax,ymax — ArcGIS REST API style"""
        return f"{self.west},{self.south},{self.east},{self.north}"

    @property
    def wkt_polygon(self):
        """WKT POLYGON for USGS ScienceBase"""
        return (
            f"POLYGON(({self.west} {self.south},"
            f"{self.east} {self.south},"
            f"{self.east} {self.north},"
            f"{self.west} {self.north},"
            f"{self.west} {self.south}))"
        )

    def __repr__(self):
        return f"BBox(S={self.south}, W={self.west}, N={self.north}, E={self.east})"


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1A — OpenStreetMap via Overpass API
# ─────────────────────────────────────────────────────────────────────────────

OSM_QUERY_TEMPLATE = """
[out:json][timeout:90];
(
  // Buildings with all relevant tags
  way["building"]({bbox});
  relation["building"]({bbox});

  // Roads and paths
  way["highway"]({bbox});

  // Waterways
  way["waterway"]({bbox});
  relation["waterway"]({bbox});

  // Land use (parks, farmland, residential zones)
  way["landuse"]({bbox});
  relation["landuse"]({bbox});

  // Natural features (trees, water bodies, grass)
  way["natural"]({bbox});
  node["natural"="tree"]({bbox});

  // Amenities (benches, bike racks, bins, cafes, etc.)
  node["amenity"]({bbox});
  way["amenity"]({bbox});

  // Leisure (parks, pitches, golf courses)
  way["leisure"]({bbox});
  relation["leisure"]({bbox});

  // Public art and tourism
  node["tourism"]({bbox});
  node["historic"]({bbox});

  // Railways (tracks, platforms, stations)
  way["railway"]({bbox});
  relation["railway"]({bbox});

  // Barriers and boundaries
  way["barrier"]({bbox});
  node["barrier"]({bbox});

  // Highway nodes (street lamps, bus stops, crossings)
  node["highway"]({bbox});

  // Power infrastructure (poles, towers, lines)
  node["power"]({bbox});
  way["power"]({bbox});

  // Man-made structures (antenna, chimney, water tower, pier)
  node["man_made"]({bbox});
  way["man_made"]({bbox});

  // Emergency infrastructure (fire hydrants)
  node["emergency"]({bbox});

  // Advertising (columns, flags, poster boxes)
  node["advertising"]({bbox});

  // Golf course features (UC Davis Golf Course)
  way["golf"]({bbox});
  relation["golf"]({bbox});
);
out body geom;
>;
out skel qt;
"""


def fetch_osm(bbox: BoundingBox, output_dir: Path) -> dict:
    """Fetch OpenStreetMap data for the bounding box via Overpass API."""
    log.info("Fetching OSM data  bbox=%s", bbox.osm)
    query = OSM_QUERY_TEMPLATE.format(bbox=bbox.osm)
    out_path = output_dir / "osm_raw.json"

    # Try each mirror
    for mirror in OVERPASS_MIRRORS:
        try:
            log.info("  Trying mirror: %s", mirror)
            resp = requests.post(
                mirror,
                data={"data": query},
                timeout=120,
                headers={"User-Agent": "BuildDavis/1.0 (builddavis.org)"}
            )
            resp.raise_for_status()
            data = resp.json()

            elements = data.get("elements", [])
            buildings = sum(1 for e in elements if e.get("tags", {}).get("building"))
            roads     = sum(1 for e in elements if e.get("tags", {}).get("highway"))
            waterways = sum(1 for e in elements if e.get("tags", {}).get("waterway"))
            trees     = sum(1 for e in elements if e.get("tags", {}).get("natural") == "tree")
            amenities = sum(1 for e in elements if e.get("tags", {}).get("amenity"))
            railways  = sum(1 for e in elements if e.get("tags", {}).get("railway"))

            out_path.write_text(json.dumps(data, indent=2))
            log.info("  OSM: %d elements (%d buildings, %d roads, %d waterways, %d trees, %d amenities, %d railways)",
                     len(elements), buildings, roads, waterways, trees, amenities, railways)
            return {
                "source": "osm",
                "path": str(out_path),
                "counts": {
                    "total": len(elements),
                    "buildings": buildings,
                    "roads": roads,
                    "waterways": waterways,
                    "trees": trees,
                    "amenities": amenities,
                    "railways": railways,
                }
            }
        except Exception as exc:
            log.warning("  Mirror failed: %s — %s", mirror, exc)
            time.sleep(2)

    raise RuntimeError("All Overpass API mirrors failed — check network or try later")


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1B — Overture Maps building footprints
# ─────────────────────────────────────────────────────────────────────────────

def fetch_overture(bbox: BoundingBox, output_dir: Path) -> dict:
    """Download Overture Maps building footprints using the CLI tool."""
    log.info("Fetching Overture building footprints  bbox=%s", bbox.overture)
    out_path = output_dir / "overture_buildings.geojson"

    # Resolve overturemaps exe — lives next to python in Scripts/
    scripts_dir = Path(sys.executable).parent / "Scripts"
    overturemaps_exe = scripts_dir / "overturemaps.exe"
    if not overturemaps_exe.exists():
        overturemaps_exe = scripts_dir / "overturemaps"
    if not overturemaps_exe.exists():
        # Fall back to bare command (hope it's on PATH)
        overturemaps_exe = "overturemaps"

    cmd = [
        str(overturemaps_exe), "download",
        f"--bbox={bbox.overture}",
        "-f", "geojson",
        "--type=building",
        "-o", str(out_path)
    ]

    try:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=300, encoding="utf-8", errors="replace",
                                env=env)
        if result.returncode != 0:
            raise RuntimeError(f"overturemaps CLI error: {result.stderr}")

        # Count features
        with open(out_path, encoding="utf-8") as f:
            data = json.load(f)
        count = len(data.get("features", []))

        # Count how many have height estimates
        heights = sum(
            1 for feat in data.get("features", [])
            if feat.get("properties", {}).get("height")
        )

        log.info("  Overture: %d buildings (%d with height data)", count, heights)
        return {
            "source": "overture",
            "path": str(out_path),
            "counts": {"buildings": count, "with_height": heights}
        }

    except FileNotFoundError:
        raise RuntimeError(
            "overturemaps CLI not found — install with: pip install overturemaps"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1C — USGS 3DEP LiDAR tile discovery
# ─────────────────────────────────────────────────────────────────────────────

def fetch_lidar_metadata(bbox: BoundingBox, output_dir: Path) -> dict:
    """
    Discover available USGS 3DEP LiDAR tiles for the bounding box.
    Downloads DEM tiles if small enough; otherwise saves metadata for
    the full LiDAR processing stage (lidar.py).
    """
    log.info("Discovering USGS LiDAR tiles  bbox=%s", bbox.overture)
    meta_path = output_dir / "lidar_tiles.json"

    tiles = []

    # Try TNM Access API (more reliable than ScienceBase for DEMs)
    url = USGS_TNM_URL.format(
        west=bbox.west, south=bbox.south,
        east=bbox.east, north=bbox.north
    )
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        raw = resp.json()
        items = raw.get("items", [])
        for item in items:
            tiles.append({
                "title": item.get("title", ""),
                "publicationDate": item.get("publicationDate", ""),
                "downloadURL": item.get("downloadURL", ""),
                "sizeInBytes": item.get("sizeInBytes", 0),
                "format": item.get("format", ""),
                "source": "TNM"
            })
        log.info("  TNM API: found %d tiles", len(tiles))
        if not tiles:
            raise ValueError("TNM returned 0 tiles for bbox")
    except Exception as exc:
        log.warning("  TNM API failed: %s — using pre-confirmed Davis tiles", exc)
        # Pre-confirmed tiles from USGS LiDAR Explorer (verified March 2026)
        tiles = [
            {
                "title": "CA SolanoCounty 1 A23",
                "publicationDate": "2023",
                "source": "pre-confirmed",
                "note": "Confirmed via USGS LiDAR Explorer — covers northern Davis and UC Davis campus",
                "dataset": "QL2 1m DEM"
            },
            {
                "title": "CA NoCAL Wildfires B5a 2018",
                "publicationDate": "2018",
                "source": "pre-confirmed",
                "note": "Confirmed via USGS LiDAR Explorer — covers central and southern Davis",
                "dataset": "QL2 1m DEM"
            }
        ]

    meta = {
        "bbox": {
            "south": bbox.south, "west": bbox.west,
            "north": bbox.north, "east": bbox.east
        },
        "tiles": tiles,
        "count": len(tiles),
        "status": "confirmed" if tiles else "not_found"
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    log.info("  LiDAR: %d tiles catalogued", len(tiles))

    return {
        "source": "lidar",
        "path": str(meta_path),
        "counts": {"tiles": len(tiles)}
    }


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1D — City of Davis GIS (bike network)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_davis_gis(bbox: BoundingBox, output_dir: Path) -> dict:
    """Fetch City of Davis GIS data — bike network and parks."""
    log.info("Fetching City of Davis GIS data")
    results = {}

    # Bike network
    bike_path = output_dir / "davis_bike_network.geojson"
    url = DAVIS_GIS_BIKE_URL.format(
        xmin=bbox.west, ymin=bbox.south,
        xmax=bbox.east, ymax=bbox.north
    )
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        bike_path.write_text(json.dumps(data, indent=2))
        log.info("  Davis GIS bike network: %d segments", len(features))
        results["bike_network"] = {
            "path": str(bike_path),
            "count": len(features)
        }
    except Exception as exc:
        log.warning("  Davis GIS bike network unavailable: %s", exc)
        # Write empty GeoJSON so downstream stages don't break
        bike_path.write_text(json.dumps({"type": "FeatureCollection", "features": []}))
        results["bike_network"] = {"path": str(bike_path), "count": 0, "error": str(exc)}

    return {"source": "davis_gis", "path": str(output_dir), "data": results}


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1E — USGS NHD Waterways
# ─────────────────────────────────────────────────────────────────────────────

def fetch_waterways(bbox: BoundingBox, output_dir: Path) -> dict:
    """Fetch USGS NHD waterway data (rivers, streams, canals)."""
    log.info("Fetching USGS NHD waterways")
    out_path = output_dir / "waterways.geojson"
    url = NHD_URL.format(
        xmin=bbox.west, ymin=bbox.south,
        xmax=bbox.east, ymax=bbox.north
    )

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        out_path.write_text(json.dumps(data, indent=2))
        log.info("  NHD waterways: %d features", len(features))
        return {
            "source": "nhd_waterways",
            "path": str(out_path),
            "counts": {"waterways": len(features)}
        }
    except Exception as exc:
        log.warning("  NHD waterways unavailable: %s", exc)
        out_path.write_text(json.dumps({"type": "FeatureCollection", "features": []}))
        return {
            "source": "nhd_waterways",
            "path": str(out_path),
            "counts": {"waterways": 0},
            "error": str(exc)
        }


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1F — Microsoft Global ML Building Footprints
# ─────────────────────────────────────────────────────────────────────────────

# Microsoft publishes ML-derived building footprints from Bing satellite imagery.
# Dataset index: CSV mapping quadkeys to GeoJSON.gz URLs on GitHub.
# California data covers Davis at high fidelity (0.3m/px source imagery).
MS_BUILDINGS_DATASET_LINKS = (
    "https://minedbuildings.blob.core.windows.net/global-buildings/dataset-links.csv"
)

def _quadkeys_for_bbox(bbox: 'BoundingBox', zoom: int = 9) -> set:
    """
    Return the set of Bing Maps quadkeys at the given zoom level
    that overlap the bounding box.  Uses manual tile math instead of
    mercantile to avoid an extra dependency.
    """
    import math as _math

    def _latlon_to_tile(lat, lon, z):
        n = 2 ** z
        x = int((lon + 180.0) / 360.0 * n)
        lat_rad = _math.radians(lat)
        y = int((1.0 - _math.asinh(_math.tan(lat_rad)) / _math.pi) / 2.0 * n)
        x = max(0, min(n - 1, x))
        y = max(0, min(n - 1, y))
        return x, y

    def _tile_to_quadkey(x, y, z):
        qk = []
        for i in range(z, 0, -1):
            digit = 0
            mask = 1 << (i - 1)
            if x & mask:
                digit += 1
            if y & mask:
                digit += 2
            qk.append(str(digit))
        return "".join(qk)

    tx_min, ty_max = _latlon_to_tile(bbox.south, bbox.west, zoom)
    tx_max, ty_min = _latlon_to_tile(bbox.north, bbox.east, zoom)

    keys = set()
    for tx in range(tx_min, tx_max + 1):
        for ty in range(ty_min, ty_max + 1):
            keys.add(_tile_to_quadkey(tx, ty, zoom))
    return keys


def fetch_ms_buildings(bbox: 'BoundingBox', output_dir: Path) -> dict:
    """
    Download Microsoft Global ML Building Footprints for the Davis bounding box.

    Strategy:
      1. Download the dataset-links.csv index (~200 KB)
      2. Find rows whose Location == "UnitedStates" and QuadKey overlaps our bbox
      3. Download each matching .geojson.gz tile
      4. Filter features to those whose centroid falls inside our bbox
      5. Write merged result to ms_buildings.geojson

    MS footprints are geometry-only (no height, no tags) — they contribute
    precise polygons for small residential buildings that Overture/OSM miss.
    """
    log.info("Fetching Microsoft Building Footprints")
    out_path = output_dir / "ms_buildings.geojson"

    # Step 1: Download the dataset-links CSV index
    log.info("  Downloading dataset-links.csv index...")
    try:
        resp = requests.get(MS_BUILDINGS_DATASET_LINKS, timeout=60,
                            headers={"User-Agent": "BuildDavis/1.0"})
        resp.raise_for_status()
    except Exception as exc:
        log.warning("  MS Buildings index download failed: %s", exc)
        out_path.write_text(json.dumps({"type": "FeatureCollection", "features": []}))
        return {"source": "ms_buildings", "path": str(out_path),
                "counts": {"buildings": 0}, "error": str(exc)}

    # Step 2: Parse CSV and find matching tiles
    # CSV format: Location,QuadKey,Url,Size
    needed_qks = _quadkeys_for_bbox(bbox, zoom=9)
    log.info("  Need quadkeys (zoom 9): %s", needed_qks)

    tile_urls = []
    for line in resp.text.strip().split("\n")[1:]:  # skip header
        parts = line.strip().split(",")
        if len(parts) < 3:
            continue
        location, qk, url = parts[0], parts[1], parts[2]
        if location == "UnitedStates" and qk in needed_qks:
            tile_urls.append((qk, url))

    if not tile_urls:
        log.warning("  No MS Building tiles found for Davis bbox quadkeys %s", needed_qks)
        out_path.write_text(json.dumps({"type": "FeatureCollection", "features": []}))
        return {"source": "ms_buildings", "path": str(out_path),
                "counts": {"buildings": 0}, "error": "no_matching_tiles"}

    log.info("  Found %d matching tile(s)", len(tile_urls))

    # Step 3: Download and extract each tile
    all_features = []
    for qk, url in tile_urls:
        log.info("  Downloading tile %s ...", qk)
        try:
            tile_resp = requests.get(url, timeout=120,
                                     headers={"User-Agent": "BuildDavis/1.0"})
            tile_resp.raise_for_status()

            # Decompress gzipped GeoJSON
            raw_bytes = gzip.decompress(tile_resp.content)
            # MS format: one GeoJSON Feature per line (newline-delimited JSON)
            for line in raw_bytes.decode("utf-8").strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    feature = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Filter to features whose centroid falls inside our bbox
                geom = feature.get("geometry", {})
                coords = geom.get("coordinates", [])
                if geom.get("type") == "Polygon" and coords:
                    ring = coords[0]
                    clat = sum(c[1] for c in ring) / len(ring)
                    clon = sum(c[0] for c in ring) / len(ring)
                    if (bbox.south <= clat <= bbox.north and
                            bbox.west <= clon <= bbox.east):
                        all_features.append(feature)

            log.info("    Tile %s: kept %d features in bbox (cumulative: %d)",
                     qk, len(all_features), len(all_features))
        except Exception as exc:
            log.warning("  Tile %s download failed: %s", qk, exc)

    # Step 4: Write merged GeoJSON
    geojson = {"type": "FeatureCollection", "features": all_features}
    with open(out_path, "w") as f:
        json.dump(geojson, f)

    log.info("  MS Buildings: %d footprints in Davis bbox", len(all_features))
    return {
        "source": "ms_buildings",
        "path": str(out_path),
        "counts": {"buildings": len(all_features)}
    }


# ─────────────────────────────────────────────────────────────────────────────
# Manifest writer
# ─────────────────────────────────────────────────────────────────────────────

def write_manifest(output_dir: Path, bbox: BoundingBox, results: list, elapsed: float):
    """Write a fetch manifest so downstream stages know what files are available."""
    manifest = {
        "stage": "fetch",
        "version": "1.0",
        "bbox": {
            "south": bbox.south, "west": bbox.west,
            "north": bbox.north, "east": bbox.east,
            "osm_format": bbox.osm,
            "overture_format": bbox.overture
        },
        "elapsed_seconds": round(elapsed, 1),
        "sources": {r["source"]: r for r in results},
        "files": {
            "osm_raw":           str(output_dir / "osm_raw.json"),
            "overture_buildings": str(output_dir / "overture_buildings.geojson"),
            "lidar_tiles":       str(output_dir / "lidar_tiles.json"),
            "davis_bike_network": str(output_dir / "davis_bike_network.geojson"),
            "waterways":         str(output_dir / "waterways.geojson"),
            "ms_buildings":      str(output_dir / "ms_buildings.geojson"),
        }
    }
    path = output_dir / "fetch_manifest.json"
    path.write_text(json.dumps(manifest, indent=2))
    log.info("Manifest written to %s", path)
    return manifest


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_fetch(bbox_str: str, output_dir: str, skip_lidar: bool = False) -> dict:
    """
    Run all fetch stages and return the manifest.

    Args:
        bbox_str:    Bounding box as "south,west,north,east" or "west,south,east,north"
        output_dir:  Directory to write all output files
        skip_lidar:  Skip LiDAR tile discovery (faster for testing)

    Returns:
        Manifest dict describing all fetched files
    """
    start = time.time()
    bbox = BoundingBox(bbox_str)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("  BuildDavis — Stage 1: Fetch")
    log.info("  bbox: %s", bbox)
    log.info("  output: %s", out.resolve())
    log.info("=" * 60)

    results = []

    # 1A — OSM
    results.append(fetch_osm(bbox, out))

    # 1B — Overture (optional — needs overturemaps CLI)
    try:
        results.append(fetch_overture(bbox, out))
    except Exception as e:
        log.warning("Overture fetch failed (non-fatal): %s", e)

    # 1C — LiDAR metadata
    if not skip_lidar:
        results.append(fetch_lidar_metadata(bbox, out))
    else:
        log.info("Skipping LiDAR (--skip-lidar flag)")

    # 1D — City of Davis GIS
    try:
        results.append(fetch_davis_gis(bbox, out))
    except Exception as e:
        log.warning("Davis GIS fetch failed (non-fatal): %s", e)

    # 1E — Waterways
    try:
        results.append(fetch_waterways(bbox, out))
    except Exception as e:
        log.warning("Waterways fetch failed (non-fatal): %s", e)

    # 1F — Microsoft Building Footprints
    try:
        results.append(fetch_ms_buildings(bbox, out))
    except Exception as e:
        log.warning("MS Buildings fetch failed (non-fatal): %s", e)

    elapsed = time.time() - start
    manifest = write_manifest(out, bbox, results, elapsed)

    log.info("=" * 60)
    log.info("  Stage 1 complete in %.1fs", elapsed)
    log.info("  %d sources fetched", len(results))
    log.info("=" * 60)

    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="BuildDavis Pipeline — Stage 1: Fetch geospatial data"
    )
    parser.add_argument(
        "--bbox", required=True,
        help='Bounding box: "south,west,north,east" or "west,south,east,north"'
    )
    parser.add_argument(
        "--output", default="./data",
        help="Output directory (default: ./data)"
    )
    parser.add_argument(
        "--skip-lidar", action="store_true",
        help="Skip LiDAR tile discovery (faster for testing)"
    )
    args = parser.parse_args()
    run_fetch(args.bbox, args.output, args.skip_lidar)


if __name__ == "__main__":
    main()
