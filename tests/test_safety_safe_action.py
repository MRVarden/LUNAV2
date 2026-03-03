"""Tests for safe action — snapshot before, rollback on error."""

from __future__ import annotations

import pytest

from luna.safety.safe_action import SafeAction
from luna.safety.snapshot_manager import SnapshotManager


@pytest.fixture
def snapshot_dir(tmp_path):
    return tmp_path / "snapshots"


@pytest.fixture
def manager(snapshot_dir):
    return SnapshotManager(snapshot_dir)


@pytest.fixture
def safe_action(manager):
    return SafeAction(manager)


@pytest.fixture
def target_dir(tmp_path):
    """Create a target directory with initial content."""
    target = tmp_path / "target"
    target.mkdir()
    (target / "original.txt").write_text("original content")
    return target


class TestSafeAction:
    """Tests for SafeAction."""

    @pytest.mark.asyncio
    async def test_successful_action(self, safe_action, target_dir):
        """Successful action returns result without rollback."""

        async def good_action():
            (target_dir / "new_file.txt").write_text("new")
            return "success"

        result = await safe_action.execute(
            good_action, target_dir, description="test action"
        )
        assert result == "success"
        assert (target_dir / "new_file.txt").exists()

    @pytest.mark.asyncio
    async def test_failed_action_triggers_rollback(self, safe_action, target_dir):
        """Failed action triggers automatic rollback."""

        async def bad_action():
            (target_dir / "original.txt").write_text("CORRUPTED")
            raise ValueError("action failed")

        with pytest.raises(ValueError, match="action failed"):
            await safe_action.execute(
                bad_action, target_dir, description="failing action"
            )

        # Original content should be restored
        restored = (target_dir / "original.txt").read_text()
        assert restored == "original content"

    @pytest.mark.asyncio
    async def test_action_on_nonexistent_target(self, safe_action, tmp_path):
        """Action on non-existent target skips snapshot."""

        async def create_action():
            target = tmp_path / "new_target"
            target.mkdir()
            (target / "file.txt").write_text("created")
            return "created"

        result = await safe_action.execute(
            create_action, tmp_path / "new_target"
        )
        assert result == "created"

    @pytest.mark.asyncio
    async def test_execute_with_cleanup_success(self, safe_action, target_dir, snapshot_dir):
        """execute_with_cleanup removes snapshot on success."""

        async def good_action():
            return 42

        result = await safe_action.execute_with_cleanup(
            good_action, target_dir, cleanup_snapshot=True
        )
        assert result == 42

        # Snapshot should have been cleaned up
        snapshots = list(snapshot_dir.glob("*.tar.gz"))
        assert len(snapshots) == 0

    @pytest.mark.asyncio
    async def test_execute_with_cleanup_failure(self, safe_action, target_dir, snapshot_dir):
        """execute_with_cleanup keeps snapshot on failure."""

        async def bad_action():
            raise RuntimeError("oops")

        with pytest.raises(RuntimeError):
            await safe_action.execute_with_cleanup(
                bad_action, target_dir, cleanup_snapshot=True
            )

        # Snapshot should still exist (for manual recovery)
        snapshots = list(snapshot_dir.glob("*.tar.gz"))
        assert len(snapshots) == 1

    @pytest.mark.asyncio
    async def test_action_with_args(self, safe_action, target_dir):
        """Action receives positional and keyword arguments."""
        received = {}

        async def action_with_args(x, y, z=None):
            received["x"] = x
            received["y"] = y
            received["z"] = z
            return x + y

        result = await safe_action.execute(
            action_with_args, target_dir, "test", 1, 2, z=3
        )
        assert result == 3
        assert received == {"x": 1, "y": 2, "z": 3}
