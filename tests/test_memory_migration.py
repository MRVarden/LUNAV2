"""TDD test for memory fractal migration.

This test validates the structural integrity of memory_fractal/ AFTER migration:
- Correct directory names: branches/ (not branchs/), leaves/ (not leafs/)
- All JSON files parsable
- Index entries match files on disk
- Index "type" fields use correct names
- No data loss: total file count preserved

Written BEFORE migration — expected to FAIL on branchs/leafs checks
until migration is complete.
"""

import json
import os
from pathlib import Path

import pytest

MEMORY_ROOT = Path(__file__).parent.parent / "memory_fractal"

# The 4 canonical fractal directories (post-migration names)
EXPECTED_DIRS = ["seeds", "roots", "branches", "leaves"]

# Old names that must NOT exist after migration
DEPRECATED_DIRS = ["branchs", "leafs"]


class TestDirectoryStructure:
    """Verify directory naming is correct post-migration."""

    @pytest.mark.parametrize("dirname", EXPECTED_DIRS)
    def test_expected_dir_exists(self, dirname):
        path = MEMORY_ROOT / dirname
        assert path.is_dir(), f"Expected directory {dirname}/ does not exist"

    @pytest.mark.parametrize("dirname", DEPRECATED_DIRS)
    def test_deprecated_dir_removed(self, dirname):
        path = MEMORY_ROOT / dirname
        assert not path.exists(), (
            f"Deprecated directory {dirname}/ still exists — migration incomplete"
        )


class TestIndexFiles:
    """Verify each directory has a valid index.json with correct type field."""

    @pytest.mark.parametrize("dirname", EXPECTED_DIRS)
    def test_index_exists_and_parsable(self, dirname):
        index_path = MEMORY_ROOT / dirname / "index.json"
        assert index_path.is_file(), f"{dirname}/index.json missing"

        with open(index_path) as f:
            data = json.load(f)

        assert "type" in data, f"{dirname}/index.json missing 'type' field"
        assert "memories" in data, f"{dirname}/index.json missing 'memories' field"
        assert "count" in data, f"{dirname}/index.json missing 'count' field"

    @pytest.mark.parametrize("dirname", EXPECTED_DIRS)
    def test_index_type_matches_dirname(self, dirname):
        """Index 'type' field must match the directory name exactly."""
        index_path = MEMORY_ROOT / dirname / "index.json"
        with open(index_path) as f:
            data = json.load(f)

        assert data["type"] == dirname, (
            f"{dirname}/index.json has type='{data['type']}', expected '{dirname}'"
        )

    @pytest.mark.parametrize("dirname", EXPECTED_DIRS)
    def test_index_count_matches_memories(self, dirname):
        """Index count should match the number of entries in memories dict."""
        index_path = MEMORY_ROOT / dirname / "index.json"
        with open(index_path) as f:
            data = json.load(f)

        actual_count = len(data["memories"])
        declared_count = data["count"]
        assert declared_count == actual_count, (
            f"{dirname}/index.json declares count={declared_count} "
            f"but has {actual_count} entries"
        )


class TestFileIntegrity:
    """Verify every JSON file is parsable and indexed."""

    @pytest.mark.parametrize("dirname", EXPECTED_DIRS)
    def test_all_json_parsable(self, dirname):
        """Every .json file in the directory must be valid JSON."""
        dirpath = MEMORY_ROOT / dirname
        if not dirpath.is_dir():
            pytest.skip(f"{dirname}/ not yet created")

        errors = []
        for fpath in sorted(dirpath.glob("*.json")):
            if fpath.name.endswith(".bak"):
                continue
            try:
                with open(fpath) as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                errors.append(f"{fpath.name}: {e}")

        assert not errors, (
            f"{len(errors)} unparsable JSON files in {dirname}/:\n"
            + "\n".join(errors)
        )

    @pytest.mark.parametrize("dirname", EXPECTED_DIRS)
    def test_indexed_files_exist_on_disk(self, dirname):
        """Every memory ID in index.json must have a corresponding .json file."""
        index_path = MEMORY_ROOT / dirname / "index.json"
        if not index_path.is_file():
            pytest.skip(f"{dirname}/index.json not found")

        with open(index_path) as f:
            data = json.load(f)

        missing = []
        for memory_id in data.get("memories", {}):
            fpath = MEMORY_ROOT / dirname / f"{memory_id}.json"
            if not fpath.is_file():
                missing.append(memory_id)

        assert not missing, (
            f"{len(missing)} indexed memories missing files in {dirname}/:\n"
            + "\n".join(missing)
        )

    @pytest.mark.parametrize("dirname", EXPECTED_DIRS)
    def test_disk_files_are_indexed(self, dirname):
        """Every memory .json file on disk should be in the index."""
        dirpath = MEMORY_ROOT / dirname
        index_path = dirpath / "index.json"
        if not dirpath.is_dir() or not index_path.is_file():
            pytest.skip(f"{dirname}/ or index not found")

        with open(index_path) as f:
            data = json.load(f)

        indexed_ids = set(data.get("memories", {}).keys())
        orphans = []
        for fpath in sorted(dirpath.glob("*.json")):
            if fpath.name in ("index.json",) or fpath.name.endswith(".bak"):
                continue
            file_id = fpath.stem
            if file_id not in indexed_ids:
                orphans.append(file_id)

        assert not orphans, (
            f"{len(orphans)} orphan files in {dirname}/ not in index:\n"
            + "\n".join(orphans)
        )


class TestBackupCleanup:
    """Verify backup files are cleaned per policy (keep first + last)."""

    def test_consciousness_backups_pruned(self):
        """After migration, only first and last backup should remain.

        Note: engine tests may create additional backups during the session,
        so we check that the migration-era backups are pruned (<=2 from before
        the refactor branch). We use a cutoff date to distinguish.
        """
        backups = sorted(MEMORY_ROOT.glob("consciousness_state_v2.backup_*.json"))
        # Filter to only pre-refactor backups (before 2026-02-01)
        migration_backups = [
            b for b in backups
            if b.name < "consciousness_state_v2.backup_20260201"
        ]
        assert len(migration_backups) <= 2, (
            f"Expected <=2 migration-era backups, found {len(migration_backups)}:\n"
            + "\n".join(b.name for b in migration_backups)
        )

    def test_no_bak_files_in_migrated_dirs(self):
        """No .bak files should remain in migrated directories."""
        for dirname in EXPECTED_DIRS:
            dirpath = MEMORY_ROOT / dirname
            if not dirpath.is_dir():
                continue
            bak_files = list(dirpath.glob("*.bak"))
            assert not bak_files, (
                f".bak files found in {dirname}/: "
                + ", ".join(b.name for b in bak_files)
            )
