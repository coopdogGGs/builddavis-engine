"""
Tests for backup.py and run_manifest.py — Phase 0A: Backups & Recovery
======================================================================
Uses tmp_path so no real Minecraft saves or data dirs are touched.
"""

import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Helpers: build fake directories that look like the real ones
# ---------------------------------------------------------------------------

def _fake_mc_saves(tmp_path: Path) -> Path:
    """Create a fake .minecraft/saves/ with two tiny worlds."""
    saves = tmp_path / ".minecraft" / "saves"
    for name in ("POC11", "POC12_WaterTower"):
        world_dir = saves / name
        world_dir.mkdir(parents=True)
        (world_dir / "level.dat").write_bytes(b"\x00" * 64)
        (world_dir / "region").mkdir()
        (world_dir / "region" / "r.0.0.mca").write_bytes(b"\x01" * 128)
    return saves


def _fake_workspace(tmp_path: Path) -> Path:
    """Create a fake workspace with data/ and Code/ dirs."""
    ws = tmp_path / "BuildDavis"
    data = ws / "data"
    data.mkdir(parents=True)
    code = ws / "Code"
    code.mkdir(parents=True)

    # Data artifacts (small)
    (data / "elements.json").write_text('{"elements":[]}')
    (data / "fused_features.geojson").write_text('{"features":[]}')
    # A .tif that should be SKIPPED
    (data / "big_dem.tif").write_bytes(b"\x00" * 256)

    # Config files
    (code / "pyproject.toml").write_text("[tool.pytest.ini_options]")
    (code / "spec003_zones.geojson").write_text('{"type":"FeatureCollection"}')

    return ws


# ===========================================================================
# backup.py tests
# ===========================================================================

class TestBackupWorlds:
    """backup.py — world backup logic."""

    def test_backup_creates_zip(self, tmp_path):
        from backup import backup_worlds

        saves = _fake_mc_saves(tmp_path)
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        with patch("backup.MC_SAVES", saves), \
             patch("backup.BACKUP_DIR", backup_dir):
            backup_worlds()

        # backup_worlds creates one zip per world: world_POC11_*.zip, etc.
        zips = list(backup_dir.glob("world_*.zip"))
        assert len(zips) == 2, f"Expected 2 world zips, got {[z.name for z in zips]}"

        all_names = []
        for z in zips:
            with zipfile.ZipFile(z) as zf:
                all_names.extend(zf.namelist())
        assert any("POC11" in n for n in all_names)
        assert any("POC12_WaterTower" in n for n in all_names)

    def test_backup_skips_missing_saves(self, tmp_path, capsys):
        from backup import backup_worlds

        fake_saves = tmp_path / "nonexistent" / "saves"
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        with patch("backup.MC_SAVES", fake_saves), \
             patch("backup.BACKUP_DIR", backup_dir):
            backup_worlds()

        out = capsys.readouterr().out
        assert "not found" in out.lower() or "no" in out.lower()


class TestBackupData:
    """backup.py — data artifact backup."""

    def test_artifact_list_excludes_tif(self):
        """The real DATA_ARTIFACTS list should never include .tif DEM files."""
        from backup import DATA_ARTIFACTS
        tifs = [a for a in DATA_ARTIFACTS if a.endswith(".tif")]
        assert tifs == [], f"DATA_ARTIFACTS should not include .tif: {tifs}"

    def test_backup_data_zips_artifacts(self, tmp_path):
        from backup import backup_data

        ws = _fake_workspace(tmp_path)
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        with patch("backup.WORKSPACE", ws), \
             patch("backup.BACKUP_DIR", backup_dir), \
             patch("backup.DATA_DIR", ws / "data"), \
             patch("backup.DATA_ARTIFACTS", ["elements.json", "fused_features.geojson"]):
            backup_data()

        zips = list(backup_dir.glob("data_*.zip"))
        assert len(zips) == 1

        with zipfile.ZipFile(zips[0]) as zf:
            names = zf.namelist()
            assert any("elements.json" in n for n in names)


class TestListBackups:
    """backup.py — list mode."""

    def test_list_empty(self, tmp_path, capsys):
        from backup import list_backups

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        with patch("backup.BACKUP_DIR", backup_dir):
            list_backups()

        out = capsys.readouterr().out
        assert "no backups" in out.lower() or out.strip() == ""


# ===========================================================================
# run_manifest.py tests
# ===========================================================================

class TestManifest:
    """run_manifest.py — manifest creation and diff."""

    def test_create_manifest(self, tmp_path):
        from run_manifest import create_manifest

        ws = _fake_workspace(tmp_path)
        manifest_dir = tmp_path / "manifests"

        with patch("run_manifest.WORKSPACE", ws), \
             patch("run_manifest.MANIFEST_DIR", manifest_dir), \
             patch("run_manifest.CODE_DIR", ws / "Code"), \
             patch("run_manifest.DATA_DIR", ws / "data"), \
             patch("run_manifest.VERSIONED_FILES", [
                 ws / "Code" / "pyproject.toml",
                 ws / "Code" / "spec003_zones.geojson",
             ]):
            out = create_manifest(
                name="test_run",
                bbox="38.5,-121.7,38.6,-121.6",
                notes="unit test",
            )

        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["name"] == "test_run"
        assert data["bbox"] == "38.5,-121.7,38.6,-121.6"
        assert "pyproject.toml" in str(data["file_hashes"])

    def test_manifest_hashes_change_on_edit(self, tmp_path):
        from run_manifest import create_manifest

        ws = _fake_workspace(tmp_path)
        manifest_dir = tmp_path / "manifests"
        toml_path = ws / "Code" / "pyproject.toml"

        def _create():
            with patch("run_manifest.WORKSPACE", ws), \
                 patch("run_manifest.MANIFEST_DIR", manifest_dir), \
                 patch("run_manifest.CODE_DIR", ws / "Code"), \
                 patch("run_manifest.DATA_DIR", ws / "data"), \
                 patch("run_manifest.VERSIONED_FILES", [toml_path]):
                return create_manifest(name="hash_test")

        m1 = _create()
        d1 = json.loads(m1.read_text(encoding="utf-8"))

        # Modify the tracked file
        toml_path.write_text("[tool.pytest.ini_options]\naddopts = '-v'")

        m2 = _create()
        d2 = json.loads(m2.read_text(encoding="utf-8"))

        # Hashes must differ
        h1 = list(d1["file_hashes"].values())
        h2 = list(d2["file_hashes"].values())
        assert h1 != h2, "File hash should change after edit"

    def test_diff_detects_bbox_change(self, tmp_path, capsys):
        from run_manifest import create_manifest, diff_manifests

        ws = _fake_workspace(tmp_path)
        manifest_dir = tmp_path / "manifests"

        def _create(name, bbox):
            with patch("run_manifest.WORKSPACE", ws), \
                 patch("run_manifest.MANIFEST_DIR", manifest_dir), \
                 patch("run_manifest.CODE_DIR", ws / "Code"), \
                 patch("run_manifest.DATA_DIR", ws / "data"), \
                 patch("run_manifest.VERSIONED_FILES", []):
                return create_manifest(name=name, bbox=bbox)

        m1 = _create("run_a", "38.5,-121.7,38.6,-121.6")
        m2 = _create("run_b", "38.55,-121.74,38.56,-121.73")

        diff_manifests(m1, m2)
        out = capsys.readouterr().out
        assert "bbox" in out
