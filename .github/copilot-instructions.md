# BuildDavis — Copilot Project Instructions

## What This Is
1:1 scale Minecraft recreation of Davis, CA. 6-stage geospatial ETL pipeline (OSM/Overture/LiDAR → Arnis Rust engine → Java .mca world). Hosted on Paper 1.21.4 + GeyserMC on Apex Hosting.

## Owner
coopdogGGs on GitHub. Project root referenced via repo-relative paths.

## Key Paths
- **Pipeline code:** `Code/` (fetch.py → parse.py → fuse.py → adapter.py → transform.py)
- **Engine (Rust):** Sibling repo `builddavis-engine`
- **Iconic build scripts:** `Code/build_<name>.py`
- **Staging tool:** `Code/stage.py`
- **Preservation:** `Code/preserve_zones.py`
- **Deploy to Apex:** `Code/deploy_apex.py`
- **RCON commands:** `Code/rcon_cmd.py`
- **World dir (local):** `server\BuildDavis\region\`
- **Datapack:** `server\BuildDavis\datapacks\builddavis\data\builddavis\function\`
- **Minecraft saves:** `%APPDATA%\.minecraft\saves\`
- **Python venv:** `.venv\Scripts\python.exe`

## Coordinate System
- **Full-city bbox:** `38.527,-121.812,38.591,-121.670`
- **World extents:** X: 0→12347, Z: 0→7116 (from Arnis metadata)
- **Ground level:** Y=49
- **Bedrock:** Y=34 (ground - 15, per ADR-004)
- **Scale:** 1 block = 1 meter (1:1)
- **Conversion:** Use `deploy_iconic.geo_to_mc(lat, lon)` and `mc_to_geo(x, z)` — NOT `world_config.geo_to_mc` (wrong bbox)

## Iconic Asset Build Pipeline — STRICT
Every iconic asset follows this exact sequence. **Do not advance without explicit user approval.**

1. Write `Code/build_<name>.py` → generates NBT + HTML preview
2. Run build script to generate structure
3. Open HTML preview → **STOP. Wait for user approval.**
4. `stage.py <name>` → stage to pad for in-game review
5. User reviews in-game → **STOP. Wait for user approval.**
6. `stage.py <name> --live --lat <LAT> --lon <LON>` → live placement
7. User verifies in-game → **STOP.**

**Rules:**
- ALWAYS use full 1:1 scale OSM footprint. Never shrink to fit staging pad.
- Always start from step 1. Never jump ahead.
- After each step, state what was done and what comes next.
- Use `--force` flag when user approves despite collision warnings.

## Placed Iconic Assets (DO NOT overwrite without user approval)
| Asset | Origin (X, Y, Z) | Command |
|-------|-------------------|---------|
| UC Davis Water Tower | (5285, 49, 6211) | `stage.py water_tower --live --lat 38.535 --lon -121.751011 --offset -2 1` |
| Davis Amtrak Station | (6435, 49, 5283) | `stage.py amtrak --live --lat 38.5434 --lon -121.7378 --force` |
| Toad Tunnel | (7397, 49, 5333) | `stage.py toad_tunnel --live --lat 38.5430 --lon -121.7268 --force` |
| Varsity Theatre | (6225, 49, 5309) | `stage.py varsity_theater --live --lat 38.5431 --lon -121.7403 --force` |
| Manetti Shrem Museum | (5544, 49, 6356) | `stage.py manetti_shrem --live --lat 38.5334 --lon -121.7478 --force` |
| UCD Health Stadium | (4213, 49, 5957) | **USER MANUALLY EDITED — DO NOT overwrite/re-place** |
| Yin & Yang (Egghead) | (5435, 49, 5844) | `stage.py yin_yang --live` at Wright Hall |
| Bookhead (Egghead) | (5472, 49, 5733) | `stage.py bookhead --live` at Shields Library |
| See No Evil (Egghead) | (5465, 49, 5443) | `stage.py see_no_evil --live --lat 38.542002 --lon -121.749091 --force` |
| Hear No Evil (Egghead) | (5496, 49, 5443) | `stage.py hear_no_evil --live --lat 38.542002 --lon -121.748723 --force` |
| Eye on Mrak (Egghead) | (5455, 49, 5476) | `stage.py eye_on_mrak --live --lat 38.5417 --lon -121.7492 --force` |
| Stargazer (Egghead) | (5298, 49, 5776) | `stage.py stargazer --live --lat 38.5390 --lon -121.7510 --force` |
| Flying Carousel | (5834, 49, 4997) | **USER MANUALLY EDITED — DO NOT overwrite/re-place** |

## Safety Rules
- **NEVER re-render or overwrite region files containing iconic assets with custom work**
- **NEVER selectively swap individual region files** — coordinate mappings differ between renders
- **Always do a full re-render** to a separate output dir, then replace ALL region files
- **Always backup before re-render:** `python Code/backup.py`
- **Stop Apex server before FTP upload** — server auto-saves over files, corrupting chunks
- **Re-place all iconics after any re-render** using `place_all_iconics.py`
- UCD Health Stadium has user hand-edits — NEVER overwrite

## Server Info
- **Local:** Paper at `server/start.bat`, RCON port 25575, password in `.env` (RCON_PASS)
- **Apex:** 209.192.243.20:25606 (Java), Bedrock via Geyser on same port
- **FTP:** FTPS to 6195.node.apexhosting.gdn:21, root `default/`
- **World path on Apex:** `default/paper_1_21_4_3817181/region/`

## Session Workflow
- Before `/compact` or ending a session, update `Code/PHASE4_ISSUES.md` and `/memories/repo/BuildDavis-ProjectState.md`
- Save transcript: `python Code\extract_chat2.py`

## Known Open Issues
- **GS-001:** Stone ground everywhere with `--city-boundaries` (needs grass in residential/campus)
- **HV-004:** Arnis ignores `building:levels` for window rendering
- **Colour enrichment:** Still at 0%
- 65-landmark iconic list — 12 placed so far (5 major + 7 eggheads complete)

## Arnis Render Flags
```
--ground-level 49 --fillground --interior --roof
```
