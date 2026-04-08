"""
fetch_ucdavis_trees.py - Download UC Davis Tree Database and convert to OSM GeoJSON
Adds GPS-located trees with species tags that Arnis maps to correct Minecraft tree types.

Arnis TreeType mapping (from natural.rs):
  species contains "Betula"  → Birch  (white bark, light leaves)
  species contains "Quercus" → Oak    (brown bark, dark green leaves)
  species contains "Picea"   → Spruce (dark green, conical)
  genus "Betula"             → Birch
  genus "Quercus"            → Oak
  genus "Picea"              → Spruce
  leaf_type "broadleaved"    → Oak or Birch (random)
  leaf_type "needleleaved"   → Spruce
  default                    → random Oak/Spruce/Birch

UC Davis common species → OSM tags → Arnis TreeType:
  Coast Redwood (Sequoia sempervirens) → leaf_type=needleleaved → Spruce (tall dark)
  Valley Oak (Quercus lobata)          → species=Quercus lobata → Oak
  Blue Oak (Quercus douglasii)         → species=Quercus douglasii → Oak
  Interior Live Oak (Quercus wislizeni)→ species=Quercus wislizeni → Oak
  Cork Oak (Quercus suber)             → species=Quercus suber → Oak
  Eucalyptus (Eucalyptus spp.)         → leaf_type=broadleaved → Oak/Birch (approximation)
  Fan Palm (Washingtonia robusta)      → leaf_type=broadleaved → Oak (no palm in Minecraft)
  Acacia (Acacia spp.)                 → leaf_type=broadleaved → Oak/Birch
  Birch (Betula spp.)                  → species=Betula → Birch
  Pine (Pinus spp.)                    → leaf_type=needleleaved → Spruce
  Cedar (Cedrus spp.)                  → leaf_type=needleleaved → Spruce
  Fir (Abies spp.)                     → leaf_type=needleleaved → Spruce
  Redbud (Cercis occidentalis)         → leaf_type=broadleaved → Oak/Birch
  Deodar Cedar (Cedrus deodara)        → leaf_type=needleleaved → Spruce

Usage:
    python fetch_ucdavis_trees.py --output REDACTED_PATH\\BuildDavis\\poc2\\data
"""

import argparse
import json
import logging
import urllib.request
from pathlib import Path

log = logging.getLogger("fetch_ucdavis_trees")

# UC Davis Tree Database - public ArcGIS REST API
# Returns all trees as GeoJSON points with species data
UCDAVIS_TREE_API = (
    "https://services1.arcgis.com/r9Mg8HKGmFKdTerH/arcgis/rest/services/"
    "Grounds_Tree_Database/FeatureServer/0/query"
    "?where=1%3D1&outFields=*&outSR=4326&f=geojson"
)

# Species name → OSM tags mapping
# Priority: specific latin species → genus → leaf_type
# This maps UC Davis tree database common/scientific names to OSM tags
# that Arnis's natural.rs species detection will recognise.
SPECIES_TAG_MAP = [
    # Oaks → Quercus → Arnis Oak tree
    ("quercus",           {"species": "Quercus sp.", "genus": "Quercus",  "leaf_type": "broadleaved"}),
    ("oak",               {"species": "Quercus sp.", "genus": "Quercus",  "leaf_type": "broadleaved"}),

    # Birches → Betula → Arnis Birch tree
    ("betula",            {"species": "Betula sp.",  "genus": "Betula",   "leaf_type": "broadleaved"}),
    ("birch",             {"species": "Betula sp.",  "genus": "Betula",   "leaf_type": "broadleaved"}),

    # Conifers → needleleaved → Arnis Spruce tree
    ("sequoia",           {"species": "Sequoia sempervirens", "leaf_type": "needleleaved"}),
    ("redwood",           {"species": "Sequoia sempervirens", "leaf_type": "needleleaved"}),
    ("picea",             {"species": "Picea sp.",   "genus": "Picea",    "leaf_type": "needleleaved"}),
    ("spruce",            {"species": "Picea sp.",   "genus": "Picea",    "leaf_type": "needleleaved"}),
    ("pinus",             {"species": "Pinus sp.",   "leaf_type": "needleleaved"}),
    ("pine",              {"species": "Pinus sp.",   "leaf_type": "needleleaved"}),
    ("cedrus",            {"species": "Cedrus sp.",  "leaf_type": "needleleaved"}),
    ("cedar",             {"species": "Cedrus sp.",  "leaf_type": "needleleaved"}),
    ("abies",             {"species": "Abies sp.",   "leaf_type": "needleleaved"}),
    ("fir",               {"species": "Abies sp.",   "leaf_type": "needleleaved"}),
    ("cupressus",         {"species": "Cupressus sp.", "leaf_type": "needleleaved"}),
    ("cypress",           {"species": "Cupressus sp.", "leaf_type": "needleleaved"}),
    ("taxodium",          {"species": "Taxodium sp.", "leaf_type": "needleleaved"}),
    ("juniperus",         {"species": "Juniperus sp.", "leaf_type": "needleleaved"}),
    ("juniper",           {"species": "Juniperus sp.", "leaf_type": "needleleaved"}),
    ("pseudotsuga",       {"species": "Pseudotsuga sp.", "leaf_type": "needleleaved"}),
    ("douglas",           {"species": "Pseudotsuga sp.", "leaf_type": "needleleaved"}),

    # Broadleaved → Oak/Birch random in Arnis
    ("eucalyptus",        {"leaf_type": "broadleaved"}),
    ("acacia",            {"leaf_type": "broadleaved"}),
    ("washingtonia",      {"leaf_type": "broadleaved"}),  # fan palm → approx as broadleaved
    ("palm",              {"leaf_type": "broadleaved"}),
    ("cercis",            {"leaf_type": "broadleaved"}),
    ("redbud",            {"leaf_type": "broadleaved"}),
    ("platanus",          {"leaf_type": "broadleaved"}),  # sycamore/plane
    ("sycamore",          {"leaf_type": "broadleaved"}),
    ("plane",             {"leaf_type": "broadleaved"}),
    ("acer",              {"leaf_type": "broadleaved"}),  # maple
    ("maple",             {"leaf_type": "broadleaved"}),
    ("fraxinus",          {"leaf_type": "broadleaved"}),  # ash
    ("ash",               {"leaf_type": "broadleaved"}),
    ("ulmus",             {"leaf_type": "broadleaved"}),  # elm
    ("elm",               {"leaf_type": "broadleaved"}),
    ("populus",           {"leaf_type": "broadleaved"}),  # poplar/cottonwood
    ("poplar",            {"leaf_type": "broadleaved"}),
    ("cottonwood",        {"leaf_type": "broadleaved"}),
    ("liquidambar",       {"leaf_type": "broadleaved"}),  # sweetgum
    ("sweetgum",          {"leaf_type": "broadleaved"}),
    ("liriodendron",      {"leaf_type": "broadleaved"}),  # tulip tree
    ("magnolia",          {"leaf_type": "broadleaved"}),
    ("tilia",             {"leaf_type": "broadleaved"}),  # linden/basswood
    ("linden",            {"leaf_type": "broadleaved"}),
    ("jacaranda",         {"leaf_type": "broadleaved"}),
    ("lagerstroemia",     {"leaf_type": "broadleaved"}),  # crape myrtle
    ("myrtle",            {"leaf_type": "broadleaved"}),
    ("gleditsia",         {"leaf_type": "broadleaved"}),  # honey locust
    ("locust",            {"leaf_type": "broadleaved"}),
    ("robinia",           {"leaf_type": "broadleaved"}),
    ("pyrus",             {"leaf_type": "broadleaved"}),  # pear/ornamental
    ("prunus",            {"leaf_type": "broadleaved"}),  # cherry/plum
    ("cherry",            {"leaf_type": "broadleaved"}),
    ("plum",              {"leaf_type": "broadleaved"}),
]


def species_to_osm_tags(scientific_name: str, common_name: str) -> dict:
    """
    Convert UC Davis tree database species names to OSM tags.
    Returns dict of OSM tags that Arnis will use to select tree type.
    """
    search_str = (scientific_name + " " + common_name).lower()

    for keyword, tags in SPECIES_TAG_MAP:
        if keyword in search_str:
            return tags

    # Default: broadleaved (will randomise between oak and birch in Arnis)
    return {"leaf_type": "broadleaved"}


def fetch_ucdavis_trees(output_dir: Path) -> Path:
    """
    Download UC Davis Tree Database and save as OSM-compatible GeoJSON.
    Each tree becomes a natural=tree node with species tags.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "ucdavis_trees.geojson"

    log.info("Fetching UC Davis Tree Database...")
    log.info("URL: %s", UCDAVIS_TREE_API)

    try:
        req = urllib.request.Request(
            UCDAVIS_TREE_API,
            headers={"User-Agent": "BuildDavis/1.0 (builddavis-world)"}
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        log.error("Failed to fetch UC Davis tree database: %s", exc)
        log.error("Creating empty tree file as fallback")
        empty = {"type": "FeatureCollection", "features": []}
        with open(output_path, "w") as f:
            json.dump(empty, f)
        return output_path

    features = raw.get("features", [])
    log.info("Downloaded %d raw tree features", len(features))

    # Convert to OSM-compatible GeoJSON
    # Each tree becomes a node with natural=tree and species tags
    osm_trees = []
    species_counts = {}
    skipped = 0

    for feat in features:
        geom = feat.get("geometry", {})
        props = feat.get("properties", {}) or {}

        if not geom or geom.get("type") != "Point":
            skipped += 1
            continue

        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            skipped += 1
            continue

        lon, lat = float(coords[0]), float(coords[1])

        # Extract species info from UC Davis tree database fields
        # Field names may vary — try common variants
        scientific = (
            props.get("ScientificName") or
            props.get("scientificname") or
            props.get("SCIENTIFIC_NAME") or
            props.get("Genus_Species") or
            props.get("genus_species") or
            ""
        )
        common = (
            props.get("CommonName") or
            props.get("commonname") or
            props.get("COMMON_NAME") or
            props.get("common_name") or
            ""
        )

        # Get species-appropriate OSM tags
        species_tags = species_to_osm_tags(scientific, common)

        # Build the OSM-style tags
        osm_tags = {
            "natural": "tree",
            **species_tags,
        }
        if scientific:
            osm_tags["name"] = scientific
        if common:
            osm_tags["description"] = common

        # Track species distribution
        leaf_type = species_tags.get("leaf_type", "unknown")
        species_key = species_tags.get("genus", species_tags.get("leaf_type", "unknown"))
        species_counts[species_key] = species_counts.get(species_key, 0) + 1

        osm_trees.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "id": f"ucdavis_tree_{props.get('OBJECTID', props.get('objectid', len(osm_trees)))}",
                "source": "ucdavis_tree_db",
                "osm_id": None,
                "osm_type": "node",
                "type": "natural",
                "subtype": "tree",
                "geometry": "point",
                "lat": lat,
                "lon": lon,
                "tags": osm_tags,
                "priority": 30,
                "name": scientific or common,
                "is_landmark": False,
            }
        })

    result = {"type": "FeatureCollection", "features": osm_trees}

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f)

    log.info("─" * 60)
    log.info("UC Davis trees saved: %d trees", len(osm_trees))
    log.info("Skipped (no geometry): %d", skipped)
    log.info("Species breakdown:")
    for sp, count in sorted(species_counts.items(), key=lambda x: -x[1])[:10]:
        log.info("  %-20s %d trees", sp, count)
    log.info("Output: %s", output_path)

    return output_path


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(
        description="Fetch UC Davis Tree Database for BuildDavis pipeline"
    )
    parser.add_argument("--output", required=True,
                        help="Output directory for ucdavis_trees.geojson")
    args = parser.parse_args()
    fetch_ucdavis_trees(Path(args.output))


if __name__ == "__main__":
    main()
