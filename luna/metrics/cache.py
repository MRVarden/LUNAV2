"""Metrics cache — hash-based invalidation for deterministic results.

Cache key = hash(path + mtime + size). Auto-invalidation when file changes.
Uses atomic writes (.tmp -> rename) for persistence.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from luna.metrics.normalizer import NormalizedMetrics

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CacheKey:
    """Cache key derived from file identity.

    Attributes:
        path: Absolute path to the analyzed file/directory.
        mtime: Last modification time.
        size: File size in bytes (or -1 for directories).
    """

    path: str
    mtime: float
    size: int

    @staticmethod
    def from_path(p: Path, *, max_files: int = 10_000) -> CacheKey:
        """Create a cache key from a filesystem path.

        For directories, uses the max mtime of all contained files.

        Args:
            p: Filesystem path (file or directory).
            max_files: Maximum number of files to scan for directories.
                       Prevents unbounded traversal on large projects.
        """
        if p.is_file():
            stat = p.stat()
            return CacheKey(str(p.resolve()), stat.st_mtime, stat.st_size)

        # For directories, aggregate
        max_mtime = 0.0
        total_size = 0
        file_count = 0
        for child in p.rglob("*"):
            if child.is_file():
                stat = child.stat()
                max_mtime = max(max_mtime, stat.st_mtime)
                total_size += stat.st_size
                file_count += 1
                if file_count >= max_files:
                    break

        return CacheKey(str(p.resolve()), max_mtime, total_size)

    def hexdigest(self) -> str:
        """Compute a short hex hash for this cache key."""
        raw = f"{self.path}:{self.mtime}:{self.size}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


class MetricsCache:
    """File-based cache for NormalizedMetrics results.

    Uses hash(path+mtime+size) as cache key.
    Atomic writes via .tmp -> rename pattern.
    """

    def __init__(self, cache_dir: Path, enabled: bool = True) -> None:
        self._cache_dir = cache_dir
        self._enabled = enabled
        if enabled:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self) -> bool:
        """Whether caching is enabled."""
        return self._enabled

    def get(self, key: CacheKey) -> NormalizedMetrics | None:
        """Look up cached metrics for the given key.

        Returns None on cache miss or if caching is disabled.
        """
        if not self._enabled:
            return None

        cache_file = self._cache_path(key)
        if not cache_file.exists():
            return None

        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            # Verify the stored key matches (collision check)
            if data.get("key_hash") != key.hexdigest():
                return None

            return NormalizedMetrics(
                values=data.get("values", {}),
                zones=data.get("zones", {}),
                raw_sources=data.get("raw_sources", []),
            )
        except (json.JSONDecodeError, KeyError, OSError) as exc:
            log.debug("Cache read error for %s: %s", key.hexdigest(), exc)
            return None

    def put(self, key: CacheKey, metrics: NormalizedMetrics) -> None:
        """Store normalized metrics in the cache.

        Uses atomic write: write to .tmp, then rename.
        """
        if not self._enabled:
            return

        cache_file = self._cache_path(key)
        tmp_file = cache_file.with_suffix(".tmp")

        data = {
            "key_hash": key.hexdigest(),
            "path": key.path,
            "mtime": key.mtime,
            "size": key.size,
            "values": metrics.values,
            "zones": metrics.zones,
            "raw_sources": metrics.raw_sources,
        }

        try:
            tmp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp_file.replace(cache_file)
            log.debug("Cached metrics for %s", key.hexdigest())
        except OSError as exc:
            log.warning("Cache write error for %s: %s", key.hexdigest(), exc)
            tmp_file.unlink(missing_ok=True)

    def invalidate(self, key: CacheKey) -> bool:
        """Remove a cache entry. Returns True if an entry was removed."""
        cache_file = self._cache_path(key)
        if cache_file.exists():
            cache_file.unlink()
            return True
        return False

    def clear(self) -> int:
        """Remove all cached entries. Returns count of entries removed."""
        if not self._cache_dir.exists():
            return 0

        count = 0
        for f in self._cache_dir.glob("*.json"):
            f.unlink()
            count += 1
        return count

    def _cache_path(self, key: CacheKey) -> Path:
        """File path for a given cache key."""
        return self._cache_dir / f"{key.hexdigest()}.json"
