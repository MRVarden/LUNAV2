"""Tests for audit trail — append-only JSONL event log."""

from __future__ import annotations

import pytest

from luna.observability.audit_trail import AuditEvent, AuditTrail


@pytest.fixture
def trail_path(tmp_path):
    return tmp_path / "audit.jsonl"


@pytest.fixture
def trail(trail_path):
    return AuditTrail(trail_path)


class TestAuditEvent:
    """Tests for AuditEvent."""

    def test_create(self):
        """create() generates ID and timestamp."""
        event = AuditEvent.create("test_event", agent_name="LUNA")
        assert event.event_id.startswith("evt_")
        assert "T" in event.timestamp
        assert event.event_type == "test_event"

    def test_to_dict_roundtrip(self):
        """to_dict/from_dict roundtrip preserves data."""
        event = AuditEvent.create("pipeline_complete", data={"score": 0.85})
        restored = AuditEvent.from_dict(event.to_dict())
        assert restored == event

    def test_frozen(self):
        """AuditEvent is immutable."""
        event = AuditEvent.create("test")
        with pytest.raises(AttributeError):
            event.event_type = "changed"  # type: ignore[misc]

    def test_severity_default(self):
        """Default severity is info."""
        event = AuditEvent.create("test")
        assert event.severity == "info"

    def test_custom_severity(self):
        """Custom severity is preserved."""
        event = AuditEvent.create("alert", severity="critical")
        assert event.severity == "critical"


class TestAuditTrail:
    """Tests for AuditTrail."""

    @pytest.mark.asyncio
    async def test_record_and_read(self, trail):
        """Record an event and read it back."""
        event = AuditEvent.create("test_event", agent_name="LUNA")
        await trail.record(event)

        events = await trail.read_all()
        assert len(events) == 1
        assert events[0].event_type == "test_event"

    @pytest.mark.asyncio
    async def test_multiple_records(self, trail):
        """Multiple records accumulate in order."""
        for i in range(5):
            await trail.record(AuditEvent.create(f"event_{i}"))

        events = await trail.read_all()
        assert len(events) == 5

    @pytest.mark.asyncio
    async def test_read_empty(self, trail):
        """Reading empty trail returns empty list."""
        events = await trail.read_all()
        assert events == []

    @pytest.mark.asyncio
    async def test_read_by_type(self, trail):
        """Filter events by type."""
        await trail.record(AuditEvent.create("pipeline"))
        await trail.record(AuditEvent.create("veto"))
        await trail.record(AuditEvent.create("pipeline"))

        pipeline_events = await trail.read_by_type("pipeline")
        assert len(pipeline_events) == 2

    @pytest.mark.asyncio
    async def test_count(self, trail):
        """Count returns number of events."""
        assert await trail.count() == 0
        await trail.record(AuditEvent.create("test"))
        await trail.record(AuditEvent.create("test"))
        assert await trail.count() == 2

    def test_path_property(self, trail, trail_path):
        """path property returns trail file path."""
        assert trail.path == trail_path

    @pytest.mark.asyncio
    async def test_creates_parent_dirs(self, tmp_path):
        """Trail creates parent directories if needed."""
        deep_path = tmp_path / "a" / "b" / "audit.jsonl"
        trail = AuditTrail(deep_path)
        await trail.record(AuditEvent.create("test"))
        assert deep_path.exists()

    @pytest.mark.asyncio
    async def test_data_preserved(self, trail):
        """Event data dict is preserved through serialization."""
        event = AuditEvent.create(
            "pipeline", data={"score": 0.85, "phase": "SOLID"}
        )
        await trail.record(event)

        events = await trail.read_all()
        assert events[0].data["score"] == 0.85
        assert events[0].data["phase"] == "SOLID"
