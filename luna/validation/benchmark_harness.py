"""Benchmark harness — isolated runner for validation tasks.

Executes a standardized corpus of tasks and collects performance
metrics for statistical comparison.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """Result from a single benchmark task."""

    task_name: str
    success: bool
    duration_seconds: float
    score: float  # [0, 1]
    errors: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "task_name": self.task_name,
            "success": self.success,
            "duration_seconds": self.duration_seconds,
            "score": self.score,
            "errors": self.errors,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class BenchmarkReport:
    """Aggregated report from a benchmark run."""

    timestamp: str = ""
    total_tasks: int = 0
    passed: int = 0
    failed: int = 0
    mean_score: float = 0.0
    mean_duration: float = 0.0
    results: list[BenchmarkResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "total_tasks": self.total_tasks,
            "passed": self.passed,
            "failed": self.failed,
            "mean_score": self.mean_score,
            "mean_duration": self.mean_duration,
            "results": [r.to_dict() for r in self.results],
        }


class BenchmarkHarness:
    """Runs benchmark tasks and collects results.

    Tasks are async callables that return (score, metadata) tuples.
    Each task is run in isolation with timeout protection.
    """

    def __init__(self, timeout_seconds: float = 60.0) -> None:
        self._timeout = timeout_seconds
        self._tasks: list[tuple[str, Callable[..., Coroutine[Any, Any, tuple[float, dict]]]]] = []

    def register(
        self, name: str, task: Callable[..., Coroutine[Any, Any, tuple[float, dict]]]
    ) -> None:
        """Register a benchmark task.

        Args:
            name: Task name.
            task: Async callable returning (score, metadata).
        """
        self._tasks.append((name, task))

    async def run_all(self) -> BenchmarkReport:
        """Run all registered benchmark tasks sequentially.

        Returns:
            BenchmarkReport with aggregated results.
        """
        report = BenchmarkReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_tasks=len(self._tasks),
        )

        for name, task in self._tasks:
            result = await self._run_one(name, task)
            report.results.append(result)
            if result.success:
                report.passed += 1
            else:
                report.failed += 1

        if report.results:
            scores = [r.score for r in report.results]
            durations = [r.duration_seconds for r in report.results]
            report.mean_score = sum(scores) / len(scores)
            report.mean_duration = sum(durations) / len(durations)

        log.info(
            "Benchmark: %d/%d passed, mean score=%.3f",
            report.passed,
            report.total_tasks,
            report.mean_score,
        )
        return report

    async def _run_one(
        self, name: str, task: Callable[..., Coroutine[Any, Any, tuple[float, dict]]]
    ) -> BenchmarkResult:
        """Run a single benchmark task with timeout."""
        t0 = time.monotonic()
        try:
            score, metadata = await asyncio.wait_for(
                task(), timeout=self._timeout
            )
            duration = time.monotonic() - t0
            return BenchmarkResult(
                task_name=name,
                success=True,
                duration_seconds=duration,
                score=score,
                metadata=metadata,
            )
        except asyncio.TimeoutError:
            duration = time.monotonic() - t0
            return BenchmarkResult(
                task_name=name,
                success=False,
                duration_seconds=duration,
                score=0.0,
                errors=[f"timeout after {self._timeout}s"],
            )
        except Exception as exc:
            duration = time.monotonic() - t0
            return BenchmarkResult(
                task_name=name,
                success=False,
                duration_seconds=duration,
                score=0.0,
                errors=[str(exc)],
            )
