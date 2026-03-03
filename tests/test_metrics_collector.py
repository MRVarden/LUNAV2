"""Tests for metrics collector — orchestrates runners and caching."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from luna.metrics.base_runner import BaseRunner, RawMetrics
from luna.metrics.collector import MetricsCollector
from luna.metrics.normalizer import NormalizedMetrics


class _MockRunner(BaseRunner):
    """Mock runner for testing collector logic."""

    def __init__(self, name: str = "mock", language: str = "python"):
        self._name = name
        self._language = language

    @property
    def name(self) -> str:
        return self._name

    @property
    def language(self) -> str:
        return self._language

    async def run(self, path: Path) -> RawMetrics:
        return RawMetrics(
            runner_name=self.name,
            language=self.language,
            path=str(path),
            data={"mock_value": 42},
            success=True,
        )

    async def is_available(self) -> bool:
        return True


@pytest.fixture
def collector(tmp_path):
    return MetricsCollector(
        cache_dir=tmp_path / "cache",
        cache_enabled=False,
        timeout=10.0,
    )


@pytest.fixture
def python_project(tmp_path):
    """Create a minimal Python project."""
    src = tmp_path / "project"
    src.mkdir()
    (src / "main.py").write_text("def main():\n    pass\n")
    (src / "utils.py").write_text("def helper():\n    return 1\n")
    return src


class TestMetricsCollector:
    """Tests for MetricsCollector."""

    @pytest.mark.asyncio
    async def test_collect_empty_path(self, collector, tmp_path):
        """Collecting from nonexistent path returns empty metrics."""
        result = await collector.collect(tmp_path / "nonexistent")
        assert result.values == {}

    @pytest.mark.asyncio
    async def test_collect_empty_dir(self, collector, tmp_path):
        """Collecting from dir with no recognized files returns empty."""
        empty = tmp_path / "empty"
        empty.mkdir()
        result = await collector.collect(empty)
        assert result.values == {}

    @pytest.mark.asyncio
    async def test_collect_python_project(self, collector, python_project):
        """Collecting from Python project runs Python runners."""
        result = await collector.collect(python_project)
        # AST runner should always succeed (stdlib)
        assert isinstance(result, NormalizedMetrics)
        # AST data should be present
        assert "ast" in result.raw_sources

    @pytest.mark.asyncio
    async def test_detect_python(self, collector, python_project):
        """Collector detects Python language from .py files."""
        languages = collector._detect_languages(python_project)
        assert "python" in languages

    @pytest.mark.asyncio
    async def test_detect_no_language(self, collector, tmp_path):
        """Collector returns empty for unrecognized files."""
        (tmp_path / "data.csv").write_text("a,b,c")
        languages = collector._detect_languages(tmp_path)
        assert len(languages) == 0

    def test_register_runner(self, collector):
        """Custom runners can be registered."""
        mock_runner = _MockRunner(name="custom", language="rust")
        collector.register_runner("rust", mock_runner)
        assert "rust" in collector._runners

    @pytest.mark.asyncio
    async def test_cache_hit(self, tmp_path):
        """Cached results are returned without re-running."""
        project = tmp_path / "proj"
        project.mkdir()
        (project / "main.py").write_text("x = 1")

        collector = MetricsCollector(
            cache_dir=tmp_path / "cache",
            cache_enabled=True,
        )

        # First call — cache miss
        result1 = await collector.collect(project)
        # Second call — should be cache hit
        result2 = await collector.collect(project)
        assert result1.values == result2.values

    def test_get_status(self, collector):
        """get_status returns collector info."""
        status = collector.get_status()
        assert "registered_languages" in status
        assert "python" in status["registered_languages"]
        assert "runners_per_language" in status

    @pytest.mark.asyncio
    async def test_unavailable_runner_skipped(self, tmp_path):
        """Runners that are not available are skipped."""

        class _UnavailableRunner(BaseRunner):
            @property
            def name(self) -> str:
                return "unavailable"

            @property
            def language(self) -> str:
                return "python"

            async def run(self, path: Path) -> RawMetrics:
                raise AssertionError("Should not be called")

            async def is_available(self) -> bool:
                return False

        collector = MetricsCollector(
            cache_dir=tmp_path / "cache",
            cache_enabled=False,
        )
        collector._runners["python"].append(_UnavailableRunner())

        project = tmp_path / "proj"
        project.mkdir()
        (project / "test.py").write_text("pass")

        # Should not raise — unavailable runner is skipped
        result = await collector.collect(project)
        assert isinstance(result, NormalizedMetrics)
