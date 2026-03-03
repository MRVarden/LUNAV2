"""Snapshot manager — tar + meta JSON, configurable retention.

Creates compressed snapshots of directories with metadata.
Uses atomic writes for crash safety.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tarfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SnapshotMeta:
    """Metadata for a single snapshot."""

    snapshot_id: str
    source_path: str
    archive_path: str
    meta_path: str
    created_at: str
    description: str
    size_bytes: int
    file_count: int

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "source_path": self.source_path,
            "archive_path": self.archive_path,
            "meta_path": self.meta_path,
            "created_at": self.created_at,
            "description": self.description,
            "size_bytes": self.size_bytes,
            "file_count": self.file_count,
        }

    @staticmethod
    def from_dict(data: dict) -> SnapshotMeta:
        """Deserialize from dictionary."""
        return SnapshotMeta(
            snapshot_id=data["snapshot_id"],
            source_path=data["source_path"],
            archive_path=data["archive_path"],
            meta_path=data["meta_path"],
            created_at=data["created_at"],
            description=data["description"],
            size_bytes=data["size_bytes"],
            file_count=data["file_count"],
        )


class SnapshotManager:
    """Manages directory snapshots with retention policies.

    Snapshots are stored as tar.gz archives with accompanying JSON metadata.
    Retention is enforced by max count and age in days.
    """

    def __init__(
        self,
        snapshot_dir: Path,
        max_snapshots: int = 10,
        retention_days: int = 7,
    ) -> None:
        self._snapshot_dir = snapshot_dir
        self._max_snapshots = max_snapshots
        self._retention_days = retention_days
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)

    _SNAPSHOT_ID_RE = re.compile(r"^snap_[a-f0-9]+$")

    def _validate_snapshot_id(self, snapshot_id: str) -> None:
        """Validate *snapshot_id* format and prevent path traversal.

        Raises:
            ValueError: If the ID is malformed or resolves outside the
                snapshot directory.
        """
        if not self._SNAPSHOT_ID_RE.match(snapshot_id):
            raise ValueError(
                f"Invalid snapshot ID format: {snapshot_id!r}"
            )
        # Double-check: resolved path must stay under the snapshot dir.
        resolved = (self._snapshot_dir / f"{snapshot_id}.tar.gz").resolve()
        if not resolved.is_relative_to(self._snapshot_dir.resolve()):
            raise ValueError(
                f"Snapshot ID resolves outside snapshot directory: {snapshot_id!r}"
            )

    async def create(
        self, source_path: Path, description: str = ""
    ) -> SnapshotMeta:
        """Create a snapshot of the given directory.

        Args:
            source_path: Directory to snapshot.
            description: Human-readable description.

        Returns:
            Metadata for the created snapshot.
        """
        return await asyncio.to_thread(
            self._create_sync, source_path, description
        )

    def _create_sync(self, source_path: Path, description: str) -> SnapshotMeta:
        """Synchronous snapshot creation."""
        snapshot_id = f"snap_{uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()
        archive_name = f"{snapshot_id}.tar.gz"
        meta_name = f"{snapshot_id}.meta.json"

        archive_path = self._snapshot_dir / archive_name
        meta_path = self._snapshot_dir / meta_name
        tmp_archive = archive_path.with_suffix(".tar.gz.tmp")

        file_count = 0
        try:
            with tarfile.open(tmp_archive, "w:gz") as tar:
                if source_path.is_dir():
                    for entry in source_path.rglob("*"):
                        if entry.is_symlink():
                            log.warning("Skipping symlink: %s", entry)
                            continue
                        if entry.is_file():
                            tar.add(entry, arcname=entry.relative_to(source_path))
                            file_count += 1
                elif source_path.is_file():
                    tar.add(source_path, arcname=source_path.name)
                    file_count = 1

            os.rename(tmp_archive, archive_path)
        except Exception:
            tmp_archive.unlink(missing_ok=True)
            raise

        size_bytes = archive_path.stat().st_size

        meta = SnapshotMeta(
            snapshot_id=snapshot_id,
            source_path=str(source_path),
            archive_path=str(archive_path),
            meta_path=str(meta_path),
            created_at=timestamp,
            description=description,
            size_bytes=size_bytes,
            file_count=file_count,
        )

        # Atomic write for metadata
        tmp_meta = meta_path.with_suffix(".json.tmp")
        try:
            tmp_meta.write_text(
                json.dumps(meta.to_dict(), indent=2), encoding="utf-8"
            )
            os.rename(tmp_meta, meta_path)
        except Exception:
            tmp_meta.unlink(missing_ok=True)
            raise

        log.info("Snapshot created: %s (%d files, %d bytes)", snapshot_id, file_count, size_bytes)
        return meta

    async def restore(self, snapshot_id: str, target_path: Path) -> None:
        """Restore a snapshot to the target directory.

        Args:
            snapshot_id: ID of the snapshot to restore.
            target_path: Where to extract the snapshot.

        Raises:
            FileNotFoundError: If the snapshot does not exist.
        """
        await asyncio.to_thread(self._restore_sync, snapshot_id, target_path)

    def _restore_sync(self, snapshot_id: str, target_path: Path) -> None:
        """Synchronous restore."""
        self._validate_snapshot_id(snapshot_id)
        archive_path = self._snapshot_dir / f"{snapshot_id}.tar.gz"
        if not archive_path.exists():
            raise FileNotFoundError(f"Snapshot not found: {snapshot_id}")

        target_path.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(target_path, filter="data")

        log.info("Snapshot restored: %s → %s", snapshot_id, target_path)

    async def list_snapshots(self) -> list[SnapshotMeta]:
        """List all snapshots, sorted by creation time (oldest first)."""
        return await asyncio.to_thread(self._list_sync)

    def _list_sync(self) -> list[SnapshotMeta]:
        """Synchronous listing."""
        snapshots: list[SnapshotMeta] = []
        for meta_file in self._snapshot_dir.glob("*.meta.json"):
            try:
                data = json.loads(meta_file.read_text(encoding="utf-8"))
                snapshots.append(SnapshotMeta.from_dict(data))
            except (json.JSONDecodeError, KeyError) as exc:
                log.warning("Failed to parse snapshot meta %s: %s", meta_file, exc)
        snapshots.sort(key=lambda s: s.created_at)
        return snapshots

    async def delete(self, snapshot_id: str) -> None:
        """Delete a snapshot and its metadata.

        Args:
            snapshot_id: ID of the snapshot to delete.
        """
        await asyncio.to_thread(self._delete_sync, snapshot_id)

    def _delete_sync(self, snapshot_id: str) -> None:
        """Synchronous deletion."""
        self._validate_snapshot_id(snapshot_id)
        archive_path = self._snapshot_dir / f"{snapshot_id}.tar.gz"
        meta_path = self._snapshot_dir / f"{snapshot_id}.meta.json"
        archive_path.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)
        log.info("Snapshot deleted: %s", snapshot_id)

    async def enforce_retention(self) -> int:
        """Enforce retention policy — remove old or excess snapshots.

        Returns:
            Number of snapshots removed.
        """
        return await asyncio.to_thread(self._enforce_retention_sync)

    def _enforce_retention_sync(self) -> int:
        """Synchronous retention enforcement."""
        snapshots = self._list_sync()
        removed = 0
        now = time.time()

        # Remove snapshots older than retention_days
        cutoff_seconds = self._retention_days * 86400
        retained: list[SnapshotMeta] = []
        for snap in snapshots:
            try:
                created = datetime.fromisoformat(snap.created_at).timestamp()
                if now - created > cutoff_seconds:
                    self._delete_sync(snap.snapshot_id)
                    removed += 1
                else:
                    retained.append(snap)
            except (ValueError, OSError):
                retained.append(snap)

        # Remove oldest if exceeding max count
        while len(retained) > self._max_snapshots:
            oldest = retained.pop(0)
            self._delete_sync(oldest.snapshot_id)
            removed += 1

        if removed:
            log.info("Retention enforced: %d snapshots removed", removed)
        return removed

    def get_status(self) -> dict:
        """Return current snapshot manager status."""
        snapshots = self._list_sync()
        total_size = sum(s.size_bytes for s in snapshots)
        return {
            "snapshot_count": len(snapshots),
            "max_snapshots": self._max_snapshots,
            "retention_days": self._retention_days,
            "total_size_bytes": total_size,
            "snapshot_dir": str(self._snapshot_dir),
        }

    @property
    def snapshot_dir(self) -> Path:
        """Path to the snapshot directory."""
        return self._snapshot_dir
