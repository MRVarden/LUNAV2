"""Safe action — snapshot before, rollback on error.

Wraps an action with automatic snapshot creation and rollback
if the action raises an exception.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Coroutine

from luna.safety.snapshot_manager import SnapshotManager, SnapshotMeta

log = logging.getLogger(__name__)


class SafeAction:
    """Execute an action with snapshot-based rollback safety.

    Creates a snapshot of the target path before executing the action.
    If the action fails, automatically restores from the snapshot.
    """

    def __init__(self, snapshot_manager: SnapshotManager) -> None:
        self._snapshot_manager = snapshot_manager

    async def execute(
        self,
        action: Callable[..., Coroutine[Any, Any, Any]],
        target_path: Path,
        description: str = "",
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute an action with snapshot safety.

        Args:
            action: Async callable to execute.
            target_path: Path to snapshot before the action.
            description: Description for the snapshot.
            *args: Positional arguments for the action.
            **kwargs: Keyword arguments for the action.

        Returns:
            The result of the action.

        Raises:
            Exception: Re-raises the original exception after rollback.
        """
        snapshot: SnapshotMeta | None = None

        # Create snapshot if target exists
        if target_path.exists():
            snapshot = await self._snapshot_manager.create(
                target_path,
                description=description or f"pre-action snapshot of {target_path}",
            )
            log.info(
                "SafeAction: snapshot %s created before action",
                snapshot.snapshot_id,
            )

        try:
            result = await action(*args, **kwargs)
            log.debug("SafeAction: action completed successfully")
            return result
        except Exception as exc:
            log.error("SafeAction: action failed — %s", exc)
            if snapshot is not None:
                await self._rollback(snapshot, target_path)
            raise

    async def _rollback(self, snapshot: SnapshotMeta, target_path: Path) -> None:
        """Restore from snapshot after a failed action."""
        try:
            await self._snapshot_manager.restore(
                snapshot.snapshot_id, target_path
            )
            log.info(
                "SafeAction: rolled back to snapshot %s",
                snapshot.snapshot_id,
            )
        except Exception as rollback_exc:
            log.error(
                "SafeAction: rollback FAILED — %s (snapshot %s still available)",
                rollback_exc,
                snapshot.snapshot_id,
            )

    async def execute_with_cleanup(
        self,
        action: Callable[..., Coroutine[Any, Any, Any]],
        target_path: Path,
        description: str = "",
        cleanup_snapshot: bool = True,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute with snapshot safety, optionally cleaning up on success.

        Same as execute(), but removes the snapshot on success if
        cleanup_snapshot is True.
        """
        snapshot: SnapshotMeta | None = None

        if target_path.exists():
            snapshot = await self._snapshot_manager.create(
                target_path,
                description=description or f"pre-action snapshot of {target_path}",
            )

        try:
            result = await action(*args, **kwargs)
            if cleanup_snapshot and snapshot is not None:
                await self._snapshot_manager.delete(snapshot.snapshot_id)
                log.debug("SafeAction: cleaned up snapshot %s", snapshot.snapshot_id)
            return result
        except Exception as exc:
            log.error("SafeAction: action failed — %s", exc)
            if snapshot is not None:
                await self._rollback(snapshot, target_path)
            raise
