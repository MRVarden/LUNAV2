"""Tests for message bus — local asyncio pub/sub."""

from __future__ import annotations

import asyncio

import pytest

from luna.orchestrator.message_bus import Message, MessageBus


@pytest.fixture
def bus():
    return MessageBus()


class TestMessageBus:
    """Tests for MessageBus."""

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self, bus):
        """Subscribe to a topic and receive messages."""
        queue = bus.subscribe("events")
        msg = Message(topic="events", sender="test", data={"key": "value"})
        delivered = await bus.publish(msg)
        assert delivered == 1

        received = queue.get_nowait()
        assert received.sender == "test"
        assert received.data == {"key": "value"}

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, bus):
        """Multiple subscribers receive the same message."""
        q1 = bus.subscribe("events")
        q2 = bus.subscribe("events")

        msg = Message(topic="events", sender="test", data="hello")
        delivered = await bus.publish(msg)
        assert delivered == 2

        assert q1.get_nowait().data == "hello"
        assert q2.get_nowait().data == "hello"

    @pytest.mark.asyncio
    async def test_topic_isolation(self, bus):
        """Messages only go to the correct topic."""
        q1 = bus.subscribe("topic_a")
        q2 = bus.subscribe("topic_b")

        msg = Message(topic="topic_a", sender="test", data="a_only")
        await bus.publish(msg)

        assert not q1.empty()
        assert q2.empty()

    @pytest.mark.asyncio
    async def test_no_subscribers(self, bus):
        """Publishing to topic with no subscribers returns 0."""
        msg = Message(topic="empty", sender="test", data=None)
        delivered = await bus.publish(msg)
        assert delivered == 0

    @pytest.mark.asyncio
    async def test_unsubscribe(self, bus):
        """Unsubscribed queue no longer receives messages."""
        queue = bus.subscribe("events")
        bus.unsubscribe("events", queue)

        msg = Message(topic="events", sender="test", data="after")
        delivered = await bus.publish(msg)
        assert delivered == 0

    def test_unsubscribe_nonexistent(self, bus):
        """Unsubscribing unknown queue returns False."""
        queue = asyncio.Queue()
        assert bus.unsubscribe("events", queue) is False

    def test_get_status(self, bus):
        """get_status returns expected structure."""
        bus.subscribe("topic_a")
        bus.subscribe("topic_b")
        status = bus.get_status()
        assert "topic_a" in status["topics"]
        assert "topic_b" in status["topics"]
        assert status["total_subscribers"] == 2

    @pytest.mark.asyncio
    async def test_message_timestamp(self, bus):
        """Messages have auto-generated timestamps."""
        msg = Message(topic="test", sender="test", data=None)
        assert "T" in msg.timestamp

    @pytest.mark.asyncio
    async def test_message_frozen(self):
        """Message is immutable."""
        msg = Message(topic="test", sender="test", data=None)
        with pytest.raises(AttributeError):
            msg.topic = "changed"  # type: ignore[misc]
