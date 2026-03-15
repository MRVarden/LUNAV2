"""Periodic backup of Luna's critical cognitive state.

Creates timestamped compressed tar archives of all files in memory_fractal/
that constitute Luna's identity and learned experience. Backups use zstd
compression (with gzip fallback) and atomic writes for crash safety.

Rolling window: keeps the last N backups. When the window is exceeded,
the oldest backup is ARCHIVED to backups/archive/ -- never deleted.

Design rationale:
    A `rm -rf /*` destroyed all non-versioned state -- episodic memory,
    affect, identity ledger, learnable params, psi0_adaptive. This module
    ensures that critical state can always be recovered from a recent
    compressed snapshot.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tarfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

# Maximum size for a single file to be included in backup (50 MB).
_MAX_FILE_SIZE: int = 50 * 1024 * 1024

# Directories within memory_root to skip (avoid recursive backup).
_SKIP_DIRS: frozenset[str] = frozenset({"backups", "snapshots"})

# Try zstandard first; fall back to gzip.
try:
    import zstandard as _zstd

    _HAS_ZSTD = True
except ImportError:  # pragma: no cover
    _HAS_ZSTD = False


@dataclass(frozen=True, slots=True)
class BackupMeta:
    """Metadata for a single state backup."""

    timestamp: str
    archive_path: str
    file_count: int
    size_bytes: int
    content_hash: str
    compression: str

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "archive_path": self.archive_path,
            "file_count": self.file_count,
            "size_bytes": self.size_bytes,
            "content_hash": self.content_hash,
            "compression": self.compression,
        }

    @staticmethod
    def from_dict(data: dict) -> BackupMeta:
        return BackupMeta(
            timestamp=data["timestamp"],
            archive_path=data["archive_path"],
            file_count=data["file_count"],
            size_bytes=data["size_bytes"],
            content_hash=data["content_hash"],
            compression=data["compression"],
        )


class StateBackup:
    """Periodic backup of Luna's critical cognitive state.

    Creates timestamped zstd-compressed tar archives of critical files.
    Keeps the last *max_backups* backups (rolling window). Older backups
    are moved to an ``archive/`` subdirectory -- never deleted.

    Args:
        memory_root: Path to memory_fractal/.
        backup_dir:  Path for storing backups. Defaults to memory_root/backups/.
        max_backups: Rolling window size (default 13, Fibonacci).
    """

    def __init__(
        self,
        memory_root: Path,
        backup_dir: Path | None = None,
        max_backups: int = 13,
    ) -> None:
        self._memory_root = memory_root.resolve()
        self._backup_dir = (
            (backup_dir or (memory_root / "backups")).resolve()
        )
        self._archive_dir = self._backup_dir / "archive"
        self._max_backups = max_backups
        self._last_content_hash: str | None = None

        # Ensure directories exist.
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        self._archive_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_backup(self) -> Path | None:
        """Create a timestamped backup of critical state files.

        Returns the backup path, or None if nothing changed since the
        last backup (content hash identical).
        """
        critical_files = self._collect_critical_files()
        if not critical_files:
            log.warning("StateBackup: no critical files found in %s", self._memory_root)
            return None

        # Compute content hash to detect whether anything changed.
        content_hash = self._compute_content_hash(critical_files)
        if content_hash == self._last_content_hash:
            log.debug("StateBackup: content unchanged, skipping backup")
            return None

        now = datetime.now(timezone.utc)
        timestamp_str = now.strftime("%Y%m%d_%H%M%S_%f")
        compression = "zst" if _HAS_ZSTD else "gz"
        archive_name = f"luna_state_{timestamp_str}.tar.{compression}"
        archive_path = self._backup_dir / archive_name
        tmp_path = archive_path.with_suffix(f".{compression}.tmp")
        meta_path = archive_path.with_suffix(f".{compression}.meta.json")

        try:
            file_count = self._write_archive(tmp_path, critical_files, compression)
            # Atomic rename.
            os.rename(tmp_path, archive_path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            log.error("StateBackup: archive creation failed", exc_info=True)
            return None

        size_bytes = archive_path.stat().st_size
        self._last_content_hash = content_hash

        # Write metadata (atomic).
        meta = BackupMeta(
            timestamp=now.isoformat(),
            archive_path=str(archive_path),
            file_count=file_count,
            size_bytes=size_bytes,
            content_hash=content_hash,
            compression=compression,
        )
        tmp_meta = meta_path.with_suffix(".json.tmp")
        try:
            tmp_meta.write_text(
                json.dumps(meta.to_dict(), indent=2), encoding="utf-8"
            )
            os.rename(tmp_meta, meta_path)
        except Exception:
            tmp_meta.unlink(missing_ok=True)
            log.warning("StateBackup: meta write failed", exc_info=True)

        log.info(
            "StateBackup: created %s (%d files, %.1f KB, %s)",
            archive_name,
            file_count,
            size_bytes / 1024,
            compression,
        )

        # Enforce rolling window.
        self._enforce_rolling_window()

        return archive_path

    def list_backups(self) -> list[Path]:
        """List all existing backups, most recent first."""
        patterns = ["luna_state_*.tar.zst", "luna_state_*.tar.gz"]
        backups: list[Path] = []
        for pattern in patterns:
            backups.extend(self._backup_dir.glob(pattern))
        # Sort by filename (which encodes the timestamp) descending.
        backups.sort(key=lambda p: p.name, reverse=True)
        return backups

    def restore_latest(self, target: Path | None = None) -> bool:
        """Restore from the most recent backup.

        Args:
            target: Where to extract. Defaults to memory_root.

        Returns:
            True if restoration succeeded, False if no backup or error.
        """
        backups = self.list_backups()
        if not backups:
            log.warning("StateBackup: no backups available for restore")
            return False

        latest = backups[0]
        return self._restore_from(latest, target or self._memory_root)

    def restore_from(self, archive_path: Path, target: Path | None = None) -> bool:
        """Restore from a specific backup archive.

        Args:
            archive_path: Path to the .tar.zst or .tar.gz backup.
            target: Where to extract. Defaults to memory_root.

        Returns:
            True if restoration succeeded.
        """
        return self._restore_from(archive_path, target or self._memory_root)

    def get_status(self) -> dict:
        """Return current backup system status."""
        backups = self.list_backups()
        total_size = sum(b.stat().st_size for b in backups if b.exists())
        archived = list(self._archive_dir.glob("luna_state_*.tar.*"))
        return {
            "backup_count": len(backups),
            "max_backups": self._max_backups,
            "total_size_bytes": total_size,
            "backup_dir": str(self._backup_dir),
            "archive_count": len(archived),
            "compression": "zstd" if _HAS_ZSTD else "gzip",
            "last_content_hash": self._last_content_hash,
        }

    # ------------------------------------------------------------------
    # Internal: file collection
    # ------------------------------------------------------------------

    def _collect_critical_files(self) -> list[Path]:
        """Identify all critical state files to backup.

        Walks memory_root recursively, collecting all regular files
        except those inside _SKIP_DIRS or exceeding _MAX_FILE_SIZE.
        Skips symlinks and the lock file.
        """
        critical: list[Path] = []
        root = self._memory_root

        if not root.is_dir():
            return critical

        for entry in root.rglob("*"):
            # Skip symlinks.
            if entry.is_symlink():
                continue
            # Skip directories (rglob yields them but we only want files).
            if not entry.is_file():
                continue
            # Skip files in excluded directories.
            try:
                rel = entry.relative_to(root)
            except ValueError:
                continue
            if any(part in _SKIP_DIRS for part in rel.parts):
                continue
            # Skip lock files.
            if entry.suffix == ".state_lock" or entry.name.endswith(".lock"):
                continue
            # Skip tmp files.
            if entry.suffix == ".tmp":
                continue
            # Skip oversized files.
            try:
                if entry.stat().st_size > _MAX_FILE_SIZE:
                    log.debug(
                        "StateBackup: skipping oversized file %s (%.1f MB)",
                        entry.name,
                        entry.stat().st_size / (1024 * 1024),
                    )
                    continue
            except OSError:
                continue

            critical.append(entry)

        return sorted(critical)

    # ------------------------------------------------------------------
    # Internal: content hashing
    # ------------------------------------------------------------------

    def _compute_content_hash(self, files: list[Path]) -> str:
        """Compute a combined hash of all critical files.

        Uses SHA-256 over (relative_path + file_size + mtime_ns) for each
        file. This is fast (no file reads) and detects any modification.
        Uses nanosecond mtime for sub-second change detection.
        """
        h = hashlib.sha256()
        for f in files:
            try:
                stat = f.stat()
                rel = f.relative_to(self._memory_root)
                h.update(str(rel).encode())
                h.update(str(stat.st_size).encode())
                h.update(str(stat.st_mtime_ns).encode())
            except OSError:
                continue
        return h.hexdigest()[:16]

    # ------------------------------------------------------------------
    # Internal: archive creation
    # ------------------------------------------------------------------

    def _write_archive(
        self, tmp_path: Path, files: list[Path], compression: str
    ) -> int:
        """Write a tar archive (zstd or gzip) containing the given files.

        Uses tarfile with filter="data" for tar slip protection.
        Returns the number of files archived.
        """
        file_count = 0

        if compression == "zst" and _HAS_ZSTD:
            # zstd-compressed tar: write tar to a zstd compressor stream.
            cctx = _zstd.ZstdCompressor(level=3)
            with open(tmp_path, "wb") as fh:
                with cctx.stream_writer(fh) as writer:
                    with tarfile.open(fileobj=writer, mode="w|") as tar:
                        for f in files:
                            try:
                                arcname = str(f.relative_to(self._memory_root))
                                tar.add(f, arcname=arcname)
                                file_count += 1
                            except (OSError, ValueError) as exc:
                                log.debug("StateBackup: skipping %s: %s", f.name, exc)
        else:
            # gzip fallback.
            with tarfile.open(tmp_path, "w:gz") as tar:
                for f in files:
                    try:
                        arcname = str(f.relative_to(self._memory_root))
                        tar.add(f, arcname=arcname)
                        file_count += 1
                    except (OSError, ValueError) as exc:
                        log.debug("StateBackup: skipping %s: %s", f.name, exc)

        return file_count

    # ------------------------------------------------------------------
    # Internal: restore
    # ------------------------------------------------------------------

    def _restore_from(self, archive_path: Path, target: Path) -> bool:
        """Restore files from a backup archive into target directory."""
        if not archive_path.exists():
            log.error("StateBackup: archive not found: %s", archive_path)
            return False

        target.mkdir(parents=True, exist_ok=True)

        try:
            if archive_path.name.endswith(".tar.zst") and _HAS_ZSTD:
                dctx = _zstd.ZstdDecompressor()
                with open(archive_path, "rb") as fh:
                    with dctx.stream_reader(fh) as reader:
                        with tarfile.open(fileobj=reader, mode="r|") as tar:
                            tar.extractall(target, filter="data")
            elif archive_path.name.endswith(".tar.gz"):
                with tarfile.open(archive_path, "r:gz") as tar:
                    tar.extractall(target, filter="data")
            else:
                log.error(
                    "StateBackup: unknown archive format: %s", archive_path.name
                )
                return False
        except Exception:
            log.error("StateBackup: restore failed", exc_info=True)
            return False

        log.info("StateBackup: restored from %s -> %s", archive_path.name, target)
        return True

    # ------------------------------------------------------------------
    # Internal: rolling window enforcement
    # ------------------------------------------------------------------

    def _enforce_rolling_window(self) -> None:
        """Move excess backups to the archive directory.

        Keeps the most recent *max_backups* in the main backup_dir.
        Older backups are moved (not deleted) to backups/archive/.
        """
        backups = self.list_backups()  # Most recent first.

        if len(backups) <= self._max_backups:
            return

        # The excess are the oldest (end of the list).
        to_archive = backups[self._max_backups :]

        for backup_path in to_archive:
            try:
                dest = self._archive_dir / backup_path.name
                os.rename(backup_path, dest)
                log.info("StateBackup: archived %s", backup_path.name)

                # Also move the metadata file if it exists.
                meta_path = backup_path.with_suffix(
                    backup_path.suffix + ".meta.json"
                )
                if meta_path.exists():
                    os.rename(meta_path, self._archive_dir / meta_path.name)
            except OSError as exc:
                log.warning(
                    "StateBackup: failed to archive %s: %s",
                    backup_path.name,
                    exc,
                )
