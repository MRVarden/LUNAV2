"""Tests for snapshot manager — tar + meta JSON, retention."""

from __future__ import annotations

import json

import pytest

from luna.safety.snapshot_manager import SnapshotManager, SnapshotMeta


@pytest.fixture
def snapshot_dir(tmp_path):
    return tmp_path / "snapshots"


@pytest.fixture
def manager(snapshot_dir):
    return SnapshotManager(snapshot_dir, max_snapshots=5, retention_days=7)


@pytest.fixture
def sample_dir(tmp_path):
    """Create a sample directory with files to snapshot."""
    src = tmp_path / "source"
    src.mkdir()
    (src / "file1.py").write_text("print('hello')")
    (src / "file2.py").write_text("print('world')")
    sub = src / "subdir"
    sub.mkdir()
    (sub / "file3.txt").write_text("nested content")
    return src


class TestSnapshotMeta:
    """Tests for SnapshotMeta dataclass."""

    def test_to_dict(self):
        meta = SnapshotMeta(
            snapshot_id="snap_abc123",
            source_path="/tmp/source",
            archive_path="/tmp/snaps/snap_abc123.tar.gz",
            meta_path="/tmp/snaps/snap_abc123.meta.json",
            created_at="2026-01-01T00:00:00Z",
            description="test snapshot",
            size_bytes=1024,
            file_count=3,
        )
        d = meta.to_dict()
        assert d["snapshot_id"] == "snap_abc123"
        assert d["file_count"] == 3

    def test_from_dict_roundtrip(self):
        meta = SnapshotMeta(
            snapshot_id="snap_abc123",
            source_path="/tmp/source",
            archive_path="/tmp/snaps/snap_abc123.tar.gz",
            meta_path="/tmp/snaps/snap_abc123.meta.json",
            created_at="2026-01-01T00:00:00Z",
            description="test",
            size_bytes=512,
            file_count=2,
        )
        restored = SnapshotMeta.from_dict(meta.to_dict())
        assert restored == meta

    def test_frozen(self):
        meta = SnapshotMeta(
            snapshot_id="snap_x",
            source_path="",
            archive_path="",
            meta_path="",
            created_at="",
            description="",
            size_bytes=0,
            file_count=0,
        )
        with pytest.raises(AttributeError):
            meta.snapshot_id = "changed"  # type: ignore[misc]


class TestSnapshotManager:
    """Tests for SnapshotManager."""

    @pytest.mark.asyncio
    async def test_create_snapshot(self, manager, sample_dir):
        """Create a snapshot of a directory."""
        meta = await manager.create(sample_dir, description="test")
        assert meta.snapshot_id.startswith("snap_")
        assert meta.file_count == 3
        assert meta.size_bytes > 0
        assert meta.description == "test"

    @pytest.mark.asyncio
    async def test_create_and_list(self, manager, sample_dir):
        """Created snapshots appear in list."""
        await manager.create(sample_dir, description="first")
        await manager.create(sample_dir, description="second")

        snapshots = await manager.list_snapshots()
        assert len(snapshots) == 2

    @pytest.mark.asyncio
    async def test_restore_snapshot(self, manager, sample_dir, tmp_path):
        """Restore a snapshot to a target directory."""
        meta = await manager.create(sample_dir)
        target = tmp_path / "restored"

        await manager.restore(meta.snapshot_id, target)

        assert (target / "file1.py").read_text() == "print('hello')"
        assert (target / "file2.py").read_text() == "print('world')"
        assert (target / "subdir" / "file3.txt").read_text() == "nested content"

    @pytest.mark.asyncio
    async def test_restore_nonexistent(self, manager, tmp_path):
        """Restoring a non-existent snapshot raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            await manager.restore("snap_deadbeef0000", tmp_path / "target")

    @pytest.mark.asyncio
    async def test_restore_invalid_id(self, manager, tmp_path):
        """Restoring with invalid snapshot ID raises ValueError."""
        with pytest.raises(ValueError, match="Invalid snapshot ID"):
            await manager.restore("snap_nonexistent", tmp_path / "target")

    @pytest.mark.asyncio
    async def test_delete_invalid_id(self, manager):
        """Deleting with invalid snapshot ID raises ValueError."""
        with pytest.raises(ValueError, match="Invalid snapshot ID"):
            await manager.delete("../../etc/passwd")

    @pytest.mark.asyncio
    async def test_delete_snapshot(self, manager, sample_dir):
        """Delete removes the snapshot."""
        meta = await manager.create(sample_dir)
        await manager.delete(meta.snapshot_id)

        snapshots = await manager.list_snapshots()
        assert len(snapshots) == 0

    @pytest.mark.asyncio
    async def test_enforce_retention_max_count(self, snapshot_dir, sample_dir):
        """Retention enforces max snapshot count."""
        manager = SnapshotManager(snapshot_dir, max_snapshots=2, retention_days=365)

        for i in range(4):
            await manager.create(sample_dir, description=f"snap-{i}")

        removed = await manager.enforce_retention()
        assert removed == 2
        snapshots = await manager.list_snapshots()
        assert len(snapshots) == 2

    @pytest.mark.asyncio
    async def test_meta_file_written(self, manager, sample_dir, snapshot_dir):
        """Meta JSON file is written alongside the archive."""
        meta = await manager.create(sample_dir)
        meta_path = snapshot_dir / f"{meta.snapshot_id}.meta.json"
        assert meta_path.exists()

        data = json.loads(meta_path.read_text())
        assert data["snapshot_id"] == meta.snapshot_id

    @pytest.mark.asyncio
    async def test_snapshot_single_file(self, manager, tmp_path):
        """Snapshot a single file (not a directory)."""
        single_file = tmp_path / "single.py"
        single_file.write_text("x = 1")

        meta = await manager.create(single_file)
        assert meta.file_count == 1

    def test_get_status(self, manager):
        """get_status returns expected structure."""
        status = manager.get_status()
        assert status["snapshot_count"] == 0
        assert status["max_snapshots"] == 5

    def test_creates_snapshot_dir(self, tmp_path):
        """Constructor creates snapshot dir if it doesn't exist."""
        snap_dir = tmp_path / "deep" / "path" / "snapshots"
        SnapshotManager(snap_dir)
        assert snap_dir.exists()
