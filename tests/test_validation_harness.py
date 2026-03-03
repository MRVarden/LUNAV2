"""Tests for benchmark harness — isolated task runner."""

from __future__ import annotations

import asyncio

import pytest

from luna.validation.benchmark_harness import BenchmarkHarness, BenchmarkResult


class TestBenchmarkResult:
    """Tests for BenchmarkResult."""

    def test_to_dict(self):
        """to_dict serializes all fields."""
        result = BenchmarkResult(
            task_name="test_task",
            success=True,
            duration_seconds=1.5,
            score=0.85,
        )
        d = result.to_dict()
        assert d["task_name"] == "test_task"
        assert d["score"] == 0.85
        assert d["success"] is True

    def test_frozen(self):
        """BenchmarkResult is immutable."""
        result = BenchmarkResult(
            task_name="test", success=True, duration_seconds=1.0, score=0.5
        )
        with pytest.raises(AttributeError):
            result.score = 0.9  # type: ignore[misc]


class TestBenchmarkHarness:
    """Tests for BenchmarkHarness."""

    @pytest.mark.asyncio
    async def test_run_empty(self):
        """Running with no tasks produces empty report."""
        harness = BenchmarkHarness()
        report = await harness.run_all()
        assert report.total_tasks == 0
        assert report.passed == 0

    @pytest.mark.asyncio
    async def test_run_successful_task(self):
        """Successful task produces passing result."""
        harness = BenchmarkHarness()

        async def good_task():
            return (0.85, {"complexity": "low"})

        harness.register("good_task", good_task)
        report = await harness.run_all()
        assert report.total_tasks == 1
        assert report.passed == 1
        assert report.failed == 0
        assert report.mean_score == pytest.approx(0.85)

    @pytest.mark.asyncio
    async def test_run_failing_task(self):
        """Failing task produces error result."""
        harness = BenchmarkHarness()

        async def bad_task():
            raise RuntimeError("task failed")

        harness.register("bad_task", bad_task)
        report = await harness.run_all()
        assert report.total_tasks == 1
        assert report.passed == 0
        assert report.failed == 1
        assert report.results[0].score == 0.0
        assert "task failed" in report.results[0].errors[0]

    @pytest.mark.asyncio
    async def test_run_timeout_task(self):
        """Timed out task produces timeout error."""
        harness = BenchmarkHarness(timeout_seconds=0.1)

        async def slow_task():
            await asyncio.sleep(999)
            return (1.0, {})

        harness.register("slow_task", slow_task)
        report = await harness.run_all()
        assert report.failed == 1
        assert "timeout" in report.results[0].errors[0].lower()

    @pytest.mark.asyncio
    async def test_multiple_tasks(self):
        """Multiple tasks run sequentially."""
        harness = BenchmarkHarness()

        async def task_a():
            return (0.9, {})

        async def task_b():
            return (0.7, {})

        async def task_c():
            raise ValueError("oops")

        harness.register("a", task_a)
        harness.register("b", task_b)
        harness.register("c", task_c)

        report = await harness.run_all()
        assert report.total_tasks == 3
        assert report.passed == 2
        assert report.failed == 1

    @pytest.mark.asyncio
    async def test_report_to_dict(self):
        """Report serializes to dict."""
        harness = BenchmarkHarness()

        async def task():
            return (0.8, {})

        harness.register("test", task)
        report = await harness.run_all()
        d = report.to_dict()
        assert d["total_tasks"] == 1
        assert len(d["results"]) == 1

    @pytest.mark.asyncio
    async def test_mean_duration(self):
        """Mean duration is calculated."""
        harness = BenchmarkHarness()

        async def task():
            return (1.0, {})

        harness.register("t1", task)
        harness.register("t2", task)
        report = await harness.run_all()
        assert report.mean_duration > 0
