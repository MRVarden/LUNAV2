"""MemoryEntry + MemoryManager — async fractal memory adapter.

Reads two JSON formats:
  - Format A (canonical): {"id", "type", "content", "metadata", "created", ...}
  - Format B (legacy v2):  {"memory_pure_v2": {"experience": {...}}}

Writes always in Format A. Updates index.json on each write.
All filesystem I/O is offloaded via asyncio.to_thread.

Promotion lifecycle: seed → leaf → branch → root
  Based on phi_resonance thresholds (Phi-derived) and access frequency.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from luna.core.config import LunaConfig

log = logging.getLogger(__name__)

from luna_common.constants import INV_PHI, INV_PHI2, INV_PHI3

_VALID_LEVELS = frozenset({"seeds", "roots", "branches", "leaves"})
_VALID_ID_RE = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')

# Singular names used in Format B's memory_type field.
_LEVEL_TO_SINGULAR: dict[str, str] = {
    "seeds": "seed",
    "roots": "root",
    "branches": "branch",
    "leaves": "leaf",
}
_SINGULAR_TO_LEVEL: dict[str, str] = {v: k for k, v in _LEVEL_TO_SINGULAR.items()}

# Promotion path: seed → leaf → branch → root (fractal lifecycle).
_PROMOTION_PATH: list[str] = ["seed", "leaf", "branch", "root"]

# Promotion thresholds — all Phi-derived.
# To promote from level N to N+1, entry must meet BOTH:
#   phi_resonance >= resonance threshold AND accessed_count >= access threshold.
_PROMOTION_THRESHOLDS: dict[str, dict[str, float]] = {
    "seed": {"phi_resonance": INV_PHI3, "accessed_count": 1},     # 0.236 — easy to sprout
    "leaf": {"phi_resonance": INV_PHI2, "accessed_count": 3},     # 0.382 — needs substance
    "branch": {"phi_resonance": INV_PHI, "accessed_count": 7},    # 0.618 — needs significance
}
# Roots are the final level — no promotion from root.


@dataclass(slots=True)
class MemoryEntry:
    """A single memory in the fractal hierarchy."""

    id: str
    content: str
    memory_type: str  # singular: seed/root/branch/leaf
    keywords: list[str] = field(default_factory=list)
    phi_resonance: float = 0.0
    accessed_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)


def _parse_file(path: Path) -> MemoryEntry | None:
    """Parse a single JSON file into a MemoryEntry, or None on failure.

    Handles both Format A and Format B.
    """
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        log.warning("Skipping corrupt/unreadable file: %s", path)
        return None

    # Format B: {"memory_pure_v2": {"experience": {...}}}
    if "memory_pure_v2" in data:
        exp = data["memory_pure_v2"].get("experience", {})
        entry_id = exp.get("id", path.stem)
        if not _VALID_ID_RE.match(entry_id):
            log.warning("Invalid entry id %r in %s — skipping", entry_id, path)
            return None
        raw_content = exp.get("content", "")
        return MemoryEntry(
            id=entry_id,
            content=raw_content if isinstance(raw_content, str) else json.dumps(raw_content, ensure_ascii=False),
            memory_type=exp.get("memory_type", "leaf"),
            keywords=exp.get("keywords", []),
            phi_resonance=exp.get("phi_metrics", {}).get("phi_resonance", 0.0),
            created_at=_parse_dt(exp.get("created_at")),
            updated_at=_parse_dt(exp.get("updated_at")),
            metadata=exp.get("session_context", {}),
        )

    # Format A: {"id", "type", "content", ...}
    if "id" in data:
        entry_id = data["id"]
        if not _VALID_ID_RE.match(entry_id):
            log.warning("Invalid entry id %r in %s — skipping", entry_id, path)
            return None
        raw_content = data.get("content", "")
        return MemoryEntry(
            id=entry_id,
            content=raw_content if isinstance(raw_content, str) else json.dumps(raw_content, ensure_ascii=False),
            memory_type=data.get("type", "leaf"),
            keywords=data.get("metadata", {}).get("keywords", []),
            phi_resonance=data.get("metadata", {}).get("phi_resonance", 0.0),
            accessed_count=data.get("accessed_count", 0),
            created_at=_parse_dt(data.get("created")),
            updated_at=_parse_dt(data.get("created")),
            metadata=data.get("metadata", {}),
        )

    log.warning("Unknown format in %s — skipping", path)
    return None


def _parse_dt(value: str | None) -> datetime:
    """Parse an ISO datetime string, falling back to now()."""
    if not value:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


def _validate_level(level: str) -> None:
    """Raise ValueError if level is not a known fractal level."""
    if level not in _VALID_LEVELS:
        raise ValueError(
            f"Invalid memory level: {level!r}. Must be one of {sorted(_VALID_LEVELS)}"
        )


def _can_promote(entry: MemoryEntry) -> bool:
    """Check if an entry is eligible for promotion to the next level."""
    if entry.memory_type not in _PROMOTION_THRESHOLDS:
        return False  # root or unknown — can't promote
    thresholds = _PROMOTION_THRESHOLDS[entry.memory_type]
    return (
        entry.phi_resonance >= thresholds["phi_resonance"]
        and entry.accessed_count >= thresholds["accessed_count"]
    )


class MemoryManager:
    """Async adapter for reading/writing fractal memory JSON files."""

    def __init__(self, config: LunaConfig) -> None:
        self._root = config.resolve(config.memory.fractal_root)
        self._levels = config.memory.levels

    @property
    def root(self) -> Path:
        return self._root

    # ------------------------------------------------------------------
    # Public API (all async)
    # ------------------------------------------------------------------

    async def read_level(self, level: str) -> list[MemoryEntry]:
        """Read all memory entries from a given fractal level."""
        _validate_level(level)
        return await asyncio.to_thread(self._read_level_sync, level)

    async def read_recent(self, limit: int = 50) -> list[MemoryEntry]:
        """Read the most recent entries across all levels, sorted by created_at."""
        entries: list[MemoryEntry] = []
        for level in self._levels:
            entries.extend(await asyncio.to_thread(self._read_level_sync, level))
        entries.sort(key=lambda e: e.created_at, reverse=True)
        return entries[:limit]

    async def write_memory(self, entry: MemoryEntry, level: str) -> Path:
        """Write a memory entry in Format A and update index.json."""
        _validate_level(level)
        return await asyncio.to_thread(self._write_sync, entry, level)

    async def count_by_level(self) -> dict[str, int]:
        """Count JSON files per level (excluding index.json and subdirs)."""
        result: dict[str, int] = {}
        for level in self._levels:
            level_dir = self._root / level
            if level_dir.is_dir():
                count = sum(
                    1 for p in level_dir.iterdir()
                    if p.is_file() and p.suffix == ".json" and p.name != "index.json"
                )
            else:
                count = 0
            result[level] = count
        return result

    async def search(self, keywords: list[str], limit: int = 20) -> list[MemoryEntry]:
        """Search for entries whose keywords overlap with the query."""
        kw_set = {k.lower() for k in keywords}
        all_entries: list[MemoryEntry] = []
        for level in self._levels:
            all_entries.extend(await asyncio.to_thread(self._read_level_sync, level))

        matches = [
            e for e in all_entries
            if kw_set & {k.lower() for k in e.keywords}
        ]
        matches.sort(key=lambda e: e.phi_resonance, reverse=True)
        return matches[:limit]

    # ------------------------------------------------------------------
    # Access tracking & promotion
    # ------------------------------------------------------------------

    async def record_access(self, entry_id: str, level: str) -> MemoryEntry | None:
        """Increment accessed_count and update the entry on disk."""
        _validate_level(level)
        return await asyncio.to_thread(self._record_access_sync, entry_id, level)

    async def promote(self, entry: MemoryEntry) -> MemoryEntry | None:
        """Promote a memory to the next fractal level if eligible.

        Returns the promoted entry, or None if not eligible.
        """
        return await asyncio.to_thread(self._promote_sync, entry)

    async def get_promotable(self) -> list[MemoryEntry]:
        """Find all entries eligible for promotion across all levels."""
        promotable: list[MemoryEntry] = []
        for level in self._levels:
            entries = await asyncio.to_thread(self._read_level_sync, level)
            for e in entries:
                if _can_promote(e):
                    promotable.append(e)
        return promotable

    async def run_promotion_cycle(self) -> list[MemoryEntry]:
        """Scan all levels and promote eligible entries. Returns promoted list."""
        promoted: list[MemoryEntry] = []
        for level in self._levels:
            entries = await asyncio.to_thread(self._read_level_sync, level)
            for e in entries:
                result = await self.promote(e)
                if result is not None:
                    promoted.append(result)
        return promoted

    async def get_status(self) -> dict:
        """Memory subsystem status for aggregation."""
        counts = await self.count_by_level()
        total = sum(counts.values())
        return {
            "root": str(self._root),
            "counts_by_level": counts,
            "total_memories": total,
        }

    # ------------------------------------------------------------------
    # Cold archival (v6.0) — ZERO DELETION, compress to zstd
    # ------------------------------------------------------------------

    async def archive_cold(self, threshold_resonance: float = 0.236) -> int:
        """Archive low-resonance memories to cold storage (zstd compressed).

        Memories are NEVER deleted — they are moved to _cold_storage.json.zst.
        This is a JSONL file compressed with zstd for efficient storage.

        Args:
            threshold_resonance: Entries with phi_resonance below this
                                 are archived. Default: INV_PHI3 (0.236).

        Returns:
            Number of entries archived.
        """
        return await asyncio.to_thread(self._archive_cold_sync, threshold_resonance)

    def _archive_cold_sync(self, threshold: float) -> int:
        """Sync cold archival — move low-resonance entries to zstd archive."""
        cold_path = self._root / "_cold_storage.json.zst"
        archived = 0

        # Read existing cold storage.
        existing = self._read_cold_storage(cold_path)

        for level in self._levels:
            level_dir = self._root / level
            if not level_dir.is_dir():
                continue

            for path in sorted(level_dir.iterdir()):
                if not path.is_file() or path.suffix != ".json" or path.name == "index.json":
                    continue
                entry = _parse_file(path)
                if entry is None:
                    continue
                if entry.phi_resonance < threshold:
                    # Serialize to JSONL entry.
                    record = {
                        "id": entry.id,
                        "type": entry.memory_type,
                        "content": entry.content,
                        "keywords": entry.keywords,
                        "phi_resonance": entry.phi_resonance,
                        "accessed_count": entry.accessed_count,
                        "created_at": entry.created_at.isoformat(),
                        "updated_at": entry.updated_at.isoformat(),
                        "level": level,
                    }
                    existing.append(record)
                    # Remove from hot storage.
                    try:
                        path.unlink()
                    except OSError:
                        pass
                    archived += 1

        if archived > 0:
            self._write_cold_storage(cold_path, existing)
            log.info("Cold archival: %d entries -> %s", archived, cold_path)

        return archived

    async def search_cold(
        self,
        keywords: list[str],
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Search cold storage for entries matching keywords."""
        return await asyncio.to_thread(self._search_cold_sync, keywords, limit)

    def _search_cold_sync(self, keywords: list[str], limit: int) -> list[MemoryEntry]:
        """Sync cold search — decompress and search."""
        cold_path = self._root / "_cold_storage.json.zst"
        records = self._read_cold_storage(cold_path)
        if not records:
            return []

        kw_set = {k.lower() for k in keywords}
        matches: list[MemoryEntry] = []

        for rec in records:
            rec_kw = {k.lower() for k in rec.get("keywords", [])}
            if kw_set & rec_kw:
                matches.append(MemoryEntry(
                    id=rec["id"],
                    content=rec.get("content", ""),
                    memory_type=rec.get("type", "leaf"),
                    keywords=rec.get("keywords", []),
                    phi_resonance=rec.get("phi_resonance", 0.0),
                    accessed_count=rec.get("accessed_count", 0),
                    created_at=_parse_dt(rec.get("created_at")),
                    updated_at=_parse_dt(rec.get("updated_at")),
                ))
                if len(matches) >= limit:
                    break

        return matches

    @staticmethod
    def _read_cold_storage(cold_path: Path) -> list[dict]:
        """Read cold storage (JSONL+zstd). Returns list of dicts."""
        if not cold_path.exists():
            return []
        try:
            import zstandard as zstd

            with open(cold_path, "rb") as f:
                dctx = zstd.ZstdDecompressor()
                data = dctx.decompress(f.read())
            records = []
            for line in data.decode("utf-8").strip().split("\n"):
                if line.strip():
                    records.append(json.loads(line))
            return records
        except ImportError:
            # zstd not available — try reading as plain JSONL.
            try:
                records = []
                with open(cold_path, "r") as f:
                    for line in f:
                        if line.strip():
                            records.append(json.loads(line))
                return records
            except Exception:
                return []
        except Exception:
            log.debug("Cold storage read failed", exc_info=True)
            return []

    @staticmethod
    def _write_cold_storage(cold_path: Path, records: list[dict]) -> None:
        """Write cold storage (JSONL+zstd). Atomic write."""
        cold_path.parent.mkdir(parents=True, exist_ok=True)
        jsonl = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)

        try:
            import zstandard as zstd

            cctx = zstd.ZstdCompressor(level=3)
            compressed = cctx.compress(jsonl.encode("utf-8", errors="replace"))
            tmp = cold_path.with_suffix(".tmp")
            with open(tmp, "wb") as f:
                f.write(compressed)
            tmp.replace(cold_path)
        except ImportError:
            # Fallback: write plain JSONL.
            tmp = cold_path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(jsonl)
            tmp.replace(cold_path)

    # ------------------------------------------------------------------
    # Sync internals
    # ------------------------------------------------------------------

    def _read_level_sync(self, level: str) -> list[MemoryEntry]:
        """Read all JSON files in a level directory (sync)."""
        level_dir = self._root / level
        if not level_dir.is_dir():
            return []

        entries: list[MemoryEntry] = []
        for path in sorted(level_dir.iterdir()):
            if not path.is_file() or path.suffix != ".json" or path.name == "index.json":
                continue
            entry = _parse_file(path)
            if entry is not None:
                entries.append(entry)
        return entries

    def _write_sync(self, entry: MemoryEntry, level: str) -> Path:
        """Write an entry in Format A and update the index (sync)."""
        level_dir = self._root / level
        level_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "id": entry.id,
            "type": entry.memory_type,
            "content": entry.content,
            "metadata": {
                "keywords": entry.keywords,
                "phi_resonance": entry.phi_resonance,
                **entry.metadata,
            },
            "created": entry.created_at.isoformat(),
            "accessed_count": entry.accessed_count,
            "last_accessed": entry.updated_at.isoformat(),
            "connected_to": [],
        }

        file_path = level_dir / f"{entry.id}.json"
        tmp = file_path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        tmp.replace(file_path)

        self._update_index(level_dir, level, entry)
        return file_path

    def _record_access_sync(self, entry_id: str, level: str) -> MemoryEntry | None:
        """Bump accessed_count on an existing entry and re-write it."""
        level_dir = self._root / level
        file_path = level_dir / f"{entry_id}.json"
        if not file_path.exists():
            return None

        entry = _parse_file(file_path)
        if entry is None:
            return None

        entry.accessed_count += 1
        entry.updated_at = datetime.now(timezone.utc)
        self._write_sync(entry, level)
        return entry

    def _promote_sync(self, entry: MemoryEntry) -> MemoryEntry | None:
        """Promote entry to next level if eligible. Returns promoted entry or None."""
        if not _can_promote(entry):
            return None

        current_type = entry.memory_type
        current_idx = _PROMOTION_PATH.index(current_type)
        next_type = _PROMOTION_PATH[current_idx + 1]

        current_level = _SINGULAR_TO_LEVEL[current_type]
        next_level = _SINGULAR_TO_LEVEL[next_type]

        # Remove from current level.
        old_path = self._root / current_level / f"{entry.id}.json"
        if old_path.exists():
            old_path.unlink()

        # Write to next level with updated type.
        entry.memory_type = next_type
        entry.updated_at = datetime.now(timezone.utc)
        self._write_sync(entry, next_level)

        log.info(
            "Promoted %s: %s → %s (phi=%.3f, access=%d)",
            entry.id, current_type, next_type,
            entry.phi_resonance, entry.accessed_count,
        )
        return entry

    def _update_index(self, level_dir: Path, level: str, entry: MemoryEntry) -> None:
        """Update index.json in the level directory with the new entry."""
        index_path = level_dir / "index.json"

        if index_path.exists():
            try:
                with open(index_path) as f:
                    index = json.load(f)
            except (json.JSONDecodeError, OSError):
                index = {"type": level, "updated": "", "count": 0, "memories": {}}
        else:
            index = {"type": level, "updated": "", "count": 0, "memories": {}}

        index["memories"][entry.id] = {
            "created_at": entry.created_at.isoformat(),
            "keywords": entry.keywords,
            "phi_resonance": entry.phi_resonance,
        }
        index["count"] = len(index["memories"])
        index["updated"] = datetime.now(timezone.utc).isoformat()

        tmp = index_path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(index, f, indent=2)
        tmp.replace(index_path)
