"""Kill switch — immediate emergency stop.

Provides a global emergency stop mechanism that cancels all registered
asyncio tasks and prevents new operations from starting.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

SENTINEL_FILENAME = "kill_sentinel"


class KillSwitch:
    """Emergency stop mechanism for Luna.

    When activated, cancels all registered asyncio tasks and sets a
    persistent killed flag. No new operations should start while killed.
    """

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._killed = False
        self._killed_at: str | None = None
        self._killed_reason: str | None = None
        self._registered_tasks: list[asyncio.Task] = []

    @property
    def is_killed(self) -> bool:
        """Whether the kill switch has been activated."""
        return self._killed

    @property
    def is_enabled(self) -> bool:
        """Whether the kill switch is enabled."""
        return self._enabled

    def register_task(self, task: asyncio.Task) -> None:
        """Register an asyncio task to be cancelled on kill.

        Args:
            task: The asyncio task to register.
        """
        self._registered_tasks.append(task)
        # Clean up completed tasks
        self._registered_tasks = [
            t for t in self._registered_tasks if not t.done()
        ]

    def kill(self, reason: str = "manual") -> int:
        """Activate the kill switch — cancel all registered tasks.

        Args:
            reason: Why the kill switch was activated.

        Returns:
            Number of tasks cancelled.
        """
        if not self._enabled:
            log.warning("KillSwitch: disabled — ignoring kill request")
            return 0

        self._killed = True
        self._killed_at = datetime.now(timezone.utc).isoformat()
        self._killed_reason = reason

        cancelled = 0
        for task in self._registered_tasks:
            if not task.done():
                task.cancel()
                cancelled += 1

        log.critical(
            "KILL SWITCH ACTIVATED — reason: %s, tasks cancelled: %d",
            reason,
            cancelled,
        )
        return cancelled

    def write_sentinel(self, sentinel_dir: Path, reason: str) -> Path:
        """Write a kill sentinel file for inter-process signaling."""
        sentinel_dir.mkdir(parents=True, exist_ok=True)
        sentinel_path = sentinel_dir / SENTINEL_FILENAME
        sentinel_path.write_text(reason, encoding="utf-8")
        log.info("Kill sentinel written: %s", sentinel_path)
        return sentinel_path

    def check_sentinel(self, sentinel_dir: Path) -> str | None:
        """Check for a kill sentinel file. Returns reason if found, None otherwise."""
        sentinel_path = sentinel_dir / SENTINEL_FILENAME
        if sentinel_path.exists():
            reason = sentinel_path.read_text(encoding="utf-8").strip()
            sentinel_path.unlink()
            return reason
        return None

    def reset(self) -> None:
        """Reset the kill switch — allow operations to resume.

        Should only be called after the issue has been resolved.
        """
        self._killed = False
        self._killed_at = None
        self._killed_reason = None
        self._registered_tasks = []
        log.info("KillSwitch: reset — operations may resume")

    def check(self) -> None:
        """Check if the system is killed and raise if so.

        Raises:
            RuntimeError: If the kill switch is active.
        """
        if self._killed:
            raise RuntimeError(
                f"Kill switch active (reason: {self._killed_reason})"
            )

    def get_status(self) -> dict:
        """Return current kill switch status."""
        active_tasks = [t for t in self._registered_tasks if not t.done()]
        return {
            "enabled": self._enabled,
            "killed": self._killed,
            "killed_at": self._killed_at,
            "killed_reason": self._killed_reason,
            "registered_tasks": len(active_tasks),
        }
