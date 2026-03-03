"""Audit trail — append-only JSONL event log.

Records all significant system events with timestamps.
Uses asyncio.to_thread for non-blocking I/O.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """A single audit trail event."""

    event_id: str
    timestamp: str
    event_type: str
    agent_name: str
    data: dict = field(default_factory=dict)
    severity: str = "info"

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "agent_name": self.agent_name,
            "data": self.data,
            "severity": self.severity,
        }

    @staticmethod
    def from_dict(data: dict) -> AuditEvent:
        """Deserialize from dictionary."""
        return AuditEvent(
            event_id=data["event_id"],
            timestamp=data["timestamp"],
            event_type=data["event_type"],
            agent_name=data["agent_name"],
            data=data.get("data", {}),
            severity=data.get("severity", "info"),
        )

    def to_audit_entry(self) -> object:
        """Convert to luna_common AuditEntry.

        Maps the dataclass severity string to the Severity enum.
        Uses lazy import to avoid circular dependencies.

        Returns:
            AuditEntry instance from luna_common.schemas.
        """
        from luna_common.schemas import AuditEntry, Severity

        # Map severity string to Severity enum (default to INFO)
        severity_map = {
            "info": Severity.INFO,
            "low": Severity.LOW,
            "medium": Severity.MEDIUM,
            "warning": Severity.MEDIUM,
            "high": Severity.HIGH,
            "critical": Severity.CRITICAL,
            "error": Severity.HIGH,
        }
        sev = severity_map.get(self.severity.lower(), Severity.INFO)

        return AuditEntry(
            agent_id=self.agent_name,
            event_type=self.event_type,
            severity=sev,
            payload={
                "event_id": self.event_id,
                **self.data,
            },
        )

    @staticmethod
    def create(
        event_type: str,
        agent_name: str = "LUNA",
        data: dict | None = None,
        severity: str = "info",
    ) -> AuditEvent:
        """Create a new audit event with auto-generated ID and timestamp."""
        return AuditEvent(
            event_id=f"evt_{uuid4().hex[:12]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            agent_name=agent_name,
            data=data or {},
            severity=severity,
        )


class AuditTrail:
    """Append-only JSONL audit trail.

    Each event is a single JSON line. The file is never modified — only
    appended to. Uses asyncio.to_thread for non-blocking writes.
    """

    def __init__(self, trail_path: Path) -> None:
        self._path = trail_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = asyncio.Lock()

    async def record(self, event: AuditEvent) -> None:
        """Record an event to the audit trail."""
        line = json.dumps(event.to_dict(), separators=(",", ":"))
        async with self._write_lock:
            await asyncio.to_thread(self._append_sync, line)

    def _append_sync(self, line: str) -> None:
        """Synchronous append."""
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    async def read_all(self) -> list[AuditEvent]:
        """Read all events from the audit trail."""
        return await asyncio.to_thread(self._read_all_sync)

    def _read_all_sync(self) -> list[AuditEvent]:
        """Synchronous read."""
        if not self._path.exists():
            return []

        events: list[AuditEvent] = []
        with open(self._path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    events.append(AuditEvent.from_dict(data))
                except (json.JSONDecodeError, KeyError) as exc:
                    log.warning("Audit trail parse error at line %d: %s", line_num, exc)
        return events

    async def read_by_type(self, event_type: str) -> list[AuditEvent]:
        """Read events filtered by type."""
        all_events = await self.read_all()
        return [e for e in all_events if e.event_type == event_type]

    async def count(self) -> int:
        """Count the number of events."""
        events = await self.read_all()
        return len(events)

    @property
    def path(self) -> Path:
        """Path to the audit trail file."""
        return self._path
