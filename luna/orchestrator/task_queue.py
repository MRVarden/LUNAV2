"""Task queue — priority queue for orchestrator tasks.

Uses asyncio.PriorityQueue for prioritized task execution.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

log = logging.getLogger(__name__)


@dataclass(order=True, slots=True)
class PrioritizedTask:
    """A task with priority (lower number = higher priority)."""

    priority: int
    task_id: str = field(compare=False)
    task_type: str = field(compare=False)
    data: dict = field(compare=False, default_factory=dict)
    created_at: str = field(
        compare=False,
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


class TaskQueue:
    """Priority-based task queue for the orchestrator.

    Tasks are dequeued in priority order (lower number = higher priority).
    """

    def __init__(self, maxsize: int = 100) -> None:
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=maxsize)
        self._total_enqueued = 0
        self._total_dequeued = 0

    async def enqueue(self, task: PrioritizedTask) -> None:
        """Add a task to the queue.

        Args:
            task: The task to enqueue.
        """
        await self._queue.put(task)
        self._total_enqueued += 1
        log.debug("Task enqueued: %s (priority=%d)", task.task_id, task.priority)

    def enqueue_nowait(self, task: PrioritizedTask) -> None:
        """Add a task without waiting (raises QueueFull if full)."""
        self._queue.put_nowait(task)
        self._total_enqueued += 1

    async def dequeue(self) -> PrioritizedTask:
        """Get the highest priority task (blocks if empty).

        Returns:
            The next task in priority order.
        """
        task = await self._queue.get()
        self._total_dequeued += 1
        return task

    def dequeue_nowait(self) -> PrioritizedTask | None:
        """Get the highest priority task without waiting.

        Returns:
            The next task, or None if queue is empty.
        """
        try:
            task = self._queue.get_nowait()
            self._total_dequeued += 1
            return task
        except asyncio.QueueEmpty:
            return None

    @property
    def size(self) -> int:
        """Number of tasks in the queue."""
        return self._queue.qsize()

    @property
    def empty(self) -> bool:
        """Whether the queue is empty."""
        return self._queue.empty()

    def get_status(self) -> dict:
        """Return queue status."""
        return {
            "size": self.size,
            "total_enqueued": self._total_enqueued,
            "total_dequeued": self._total_dequeued,
        }
