"""Tests for snapshot security — symlink filtering and path traversal prevention.

Validates P1 corrections: symlinks are excluded from archives and
snapshot IDs are validated against path traversal attacks.
"""

from __future__ import annotations

import os
import tarfile

import pytest

from luna.safety.snapshot_manager import SnapshotManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def snapshot_dir(tmp_path):
    """Dedicated directory for snapshot storage."""
    return tmp_path / "snapshots"


@pytest.fixture()
def manager(snapshot_dir):
    """SnapshotManager instance with default settings."""
    return SnapshotManager(snapshot_dir, max_snapshots=10, retention_days=7)


@pytest.fixture()
def source_with_symlink(tmp_path):
    """Directory containing real files and a symlink."""
    src = tmp_path / "source"
    src.mkdir()
    (src / "real_file.txt").write_text("real content")
    (src / "another.txt").write_text("also real")

    # Create a symlink pointing to an outside target
    target = tmp_path / "outside_secret.txt"
    target.write_text("SECRET DATA")
    symlink = src / "link_to_secret"
    symlink.symlink_to(target)

    return src


# ===========================================================================
# Symlink exclusion
# ===========================================================================


class TestSymlinkExclusion:
    """Symlinks must be excluded from snapshot archives."""

    @pytest.mark.asyncio
    async def test_symlinks_not_archived(self, manager, source_with_symlink, snapshot_dir):
        """Symlinks in the source directory are skipped during archiving."""
        meta = await manager.create(source_with_symlink, description="symlink test")

        # The archive should contain only real files, not the symlink
        assert meta.file_count == 2  # real_file.txt + another.txt

        # Double-check by inspecting the archive contents
        archive_path = snapshot_dir / f"{meta.snapshot_id}.tar.gz"
        with tarfile.open(archive_path, "r:gz") as tar:
            names = tar.getnames()

        assert "real_file.txt" in names
        assert "another.txt" in names
        assert "link_to_secret" not in names


# ===========================================================================
# Path traversal prevention
# ===========================================================================


class TestPathTraversalPrevention:
    """Snapshot IDs containing path traversal sequences must be rejected."""

    @pytest.mark.asyncio
    async def test_path_traversal_restore_blocked(self, manager, tmp_path):
        """restore() rejects snapshot_id with '../' traversal."""
        with pytest.raises(ValueError, match="Invalid snapshot ID"):
            await manager.restore("../../etc", tmp_path / "target")

    @pytest.mark.asyncio
    async def test_path_traversal_delete_blocked(self, manager):
        """delete() rejects snapshot_id with '../' traversal."""
        with pytest.raises(ValueError, match="Invalid snapshot ID"):
            await manager.delete("../../etc")

    @pytest.mark.asyncio
    async def test_path_traversal_with_slashes(self, manager, tmp_path):
        """Snapshot IDs with embedded slashes are rejected."""
        with pytest.raises(ValueError, match="Invalid snapshot ID"):
            await manager.restore("snap_abc/../../etc", tmp_path / "target")

    @pytest.mark.asyncio
    async def test_path_traversal_delete_passwd(self, manager):
        """Classic /etc/passwd traversal is caught."""
        with pytest.raises(ValueError, match="Invalid snapshot ID"):
            await manager.delete("../../etc/passwd")


# ===========================================================================
# Snapshot ID format validation
# ===========================================================================


class TestSnapshotIDValidation:
    """Snapshot IDs must match the expected hex format: snap_[a-f0-9]+."""

    @pytest.mark.asyncio
    async def test_valid_hex_id_accepted(self, manager, tmp_path):
        """A well-formed hex ID passes validation (even if the file doesn't exist)."""
        # This should not raise ValueError — it should raise FileNotFoundError
        # because the ID format is valid but the archive doesn't exist.
        with pytest.raises(FileNotFoundError):
            await manager.restore("snap_abcdef123456", tmp_path / "target")

    @pytest.mark.asyncio
    async def test_invalid_chars_rejected(self, manager, tmp_path):
        """Non-hex characters in the ID suffix trigger ValueError."""
        # 'Z' and uppercase are not in [a-f0-9]
        with pytest.raises(ValueError, match="Invalid snapshot ID"):
            await manager.restore("snap_ZZZZ", tmp_path / "target")

    @pytest.mark.asyncio
    async def test_missing_prefix_rejected(self, manager, tmp_path):
        """IDs without the 'snap_' prefix are rejected."""
        with pytest.raises(ValueError, match="Invalid snapshot ID"):
            await manager.restore("abcdef123456", tmp_path / "target")

    @pytest.mark.asyncio
    async def test_empty_id_rejected(self, manager, tmp_path):
        """Empty string is rejected as snapshot ID."""
        with pytest.raises(ValueError, match="Invalid snapshot ID"):
            await manager.restore("", tmp_path / "target")
