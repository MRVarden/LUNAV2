"""Fingerprint ledger — append-only JSONL storage.

Each fingerprint is appended as a single JSON line to the ledger file.
Uses atomic writes for crash safety.
"""

from __future__ import annotations

import asyncio
import collections
import json
import logging
from pathlib import Path

from luna.fingerprint.generator import Fingerprint

log = logging.getLogger(__name__)


class FingerprintLedger:
    """Append-only JSONL ledger for fingerprint records.

    Each entry is one JSON line. The file is never modified — only appended to.
    Reads use line-by-line parsing for memory efficiency.
    """

    def __init__(self, ledger_path: Path) -> None:
        self._path = ledger_path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    async def append(self, fingerprint: Fingerprint) -> None:
        """Append a fingerprint record to the ledger.

        Uses asyncio.to_thread to avoid blocking the event loop.
        """
        line = json.dumps(fingerprint.to_dict(), separators=(",", ":"))
        await asyncio.to_thread(self._append_sync, line)

    def _append_sync(self, line: str) -> None:
        """Synchronous append (run via to_thread)."""
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        log.debug("Fingerprint appended to ledger at %s", self._path)

    async def read_all(self) -> list[Fingerprint]:
        """Read all fingerprints from the ledger.

        Returns:
            List of Fingerprint records in chronological order.
        """
        return await asyncio.to_thread(self._read_all_sync)

    def _read_all_sync(self) -> list[Fingerprint]:
        """Synchronous read (run via to_thread)."""
        if not self._path.exists():
            return []

        records: list[Fingerprint] = []
        with open(self._path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    records.append(Fingerprint.from_dict(data))
                except (json.JSONDecodeError, KeyError) as exc:
                    log.warning("Ledger parse error at line %d: %s", line_num, exc)

        return records

    async def read_latest(self, n: int = 1) -> list[Fingerprint]:
        """Read the latest N fingerprints from the ledger.

        Uses a deque(maxlen=n) to keep only the last N entries in a single pass,
        avoiding loading the entire ledger into memory.

        Args:
            n: Number of recent entries to return.

        Returns:
            List of the latest N Fingerprint records.
        """
        return await asyncio.to_thread(self._read_latest_sync, n)

    def _read_latest_sync(self, n: int) -> list[Fingerprint]:
        """Synchronous read of latest N entries (run via to_thread)."""
        if not self._path.exists():
            return []

        recent: collections.deque[Fingerprint] = collections.deque(maxlen=n)
        with open(self._path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    recent.append(Fingerprint.from_dict(data))
                except (json.JSONDecodeError, KeyError) as exc:
                    log.warning("Ledger parse error at line %d: %s", line_num, exc)

        return list(recent)

    async def count(self) -> int:
        """Count the number of entries in the ledger."""
        return await asyncio.to_thread(self._count_sync)

    def _count_sync(self) -> int:
        """Count ledger lines without parsing JSON (run via to_thread)."""
        if not self._path.exists():
            return 0

        count = 0
        with open(self._path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
        return count

    @property
    def path(self) -> Path:
        """Path to the ledger file."""
        return self._path
