"""Safety module — rollback, kill switch, rate limiting, watchdog, backup.

Provides crash-safe operations with snapshot/rollback, emergency stop,
configurable rate limiting, automatic degradation detection, and
periodic state backup for resilience.
"""

from __future__ import annotations

from luna.safety.kill_auth import (
    DEFAULT_HASH_FILE,
    hash_password,
    load_hash,
    require_kill_password,
    save_hash,
    verify_password,
)
from luna.safety.kill_switch import KillSwitch
from luna.safety.rate_limiter import RateLimiter
from luna.safety.safe_action import SafeAction
from luna.safety.snapshot_manager import SnapshotManager, SnapshotMeta
from luna.safety.state_backup import BackupMeta, StateBackup
from luna.safety.watchdog import Watchdog

__all__ = [
    "BackupMeta",
    "DEFAULT_HASH_FILE",
    "KillSwitch",
    "RateLimiter",
    "SafeAction",
    "SnapshotManager",
    "SnapshotMeta",
    "StateBackup",
    "Watchdog",
    "hash_password",
    "load_hash",
    "require_kill_password",
    "save_hash",
    "verify_password",
]
