"""Message bus — asyncio.Queue-based local message passing.

Provides inter-component communication without network dependency.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Message:
    """A message on the bus."""

    topic: str
    sender: str
    data: Any
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MessageBus:
    """Local asyncio message bus — no network, just queues.

    Supports topic-based pub/sub with multiple subscribers per topic.
    """

    def __init__(self, maxsize: int = 100) -> None:
        self._maxsize = maxsize
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._total_published = 0

    def subscribe(self, topic: str) -> asyncio.Queue:
        """Subscribe to a topic.

        Args:
            topic: The topic to subscribe to.

        Returns:
            An asyncio.Queue that will receive messages for this topic.
        """
        if topic not in self._subscribers:
            self._subscribers[topic] = []

        queue: asyncio.Queue = asyncio.Queue(maxsize=self._maxsize)
        self._subscribers[topic].append(queue)
        log.debug("Subscriber added for topic: %s", topic)
        return queue

    async def publish(self, message: Message) -> int:
        """Publish a message to its topic.

        Args:
            message: The message to publish.

        Returns:
            Number of subscribers that received the message.
        """
        topic_queues = self._subscribers.get(message.topic, [])
        delivered = 0

        for queue in topic_queues:
            try:
                queue.put_nowait(message)
                delivered += 1
            except asyncio.QueueFull:
                log.warning("Message bus queue full for topic: %s", message.topic)

        self._total_published += 1
        return delivered

    def unsubscribe(self, topic: str, queue: asyncio.Queue) -> bool:
        """Remove a subscriber from a topic.

        Args:
            topic: The topic.
            queue: The queue to remove.

        Returns:
            True if the subscriber was found and removed.
        """
        if topic in self._subscribers:
            try:
                self._subscribers[topic].remove(queue)
                return True
            except ValueError:
                pass
        return False

    def get_status(self) -> dict:
        """Return bus status."""
        return {
            "topics": list(self._subscribers.keys()),
            "total_subscribers": sum(len(q) for q in self._subscribers.values()),
            "total_published": self._total_published,
        }
