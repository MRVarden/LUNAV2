"""Safety module — rollback, kill switch, rate limiting, watchdog.

Provides crash-safe operations with snapshot/rollback, emergency stop,
configurable rate limiting, and automatic degradation detection.
"""

from __future__ import annotations

from luna.safety.kill_switch import KillSwitch
from luna.safety.rate_limiter import RateLimiter
from luna.safety.safe_action import SafeAction
from luna.safety.snapshot_manager import SnapshotManager, SnapshotMeta
from luna.safety.watchdog import Watchdog

__all__ = [
    "KillSwitch",
    "RateLimiter",
    "SafeAction",
    "SnapshotManager",
    "SnapshotMeta",
    "Watchdog",
]
