"""Tests for metrics base_runner module — BaseRunner + RawMetrics."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from luna.metrics.base_runner import BaseRunner, RawMetrics


# ─── RawMetrics Tests ───


class TestRawMetrics:
    """Tests for the RawMetrics frozen dataclass."""

    def test_create_success(self):
        """RawMetrics can be created with success=True."""
        raw = RawMetrics(
            runner_name="test_runner",
            language="python",
            path="/tmp/test",
            data={"cc_average": 3.5},
            errors=[],
            success=True,
        )
        assert raw.runner_name == "test_runner"
        assert raw.language == "python"
        assert raw.success is True
        assert raw.data["cc_average"] == 3.5
        assert raw.errors == []

    def test_create_failure(self):
        """RawMetrics can be created with success=False and errors."""
        raw = RawMetrics(
            runner_name="broken",
            language="rust",
            path="/tmp/broken",
            errors=["tool not found"],
            success=False,
        )
        assert raw.success is False
        assert "tool not found" in raw.errors

    def test_frozen(self):
        """RawMetrics is immutable."""
        raw = RawMetrics(runner_name="x", language="y", path="/z")
        with pytest.raises(AttributeError):
            raw.success = False  # type: ignore[misc]

    def test_default_values(self):
        """RawMetrics has sensible defaults."""
        raw = RawMetrics(runner_name="x", language="y", path="/z")
        assert raw.data == {}
        assert raw.errors == []
        assert raw.success is True


# ─── BaseRunner Tests ───


class _StubRunner(BaseRunner):
    """Concrete runner for testing the abstract base."""

    @property
    def name(self) -> str:
        return "stub"

    @property
    def language(self) -> str:
        return "python"

    async def run(self, path: Path) -> RawMetrics:
        return RawMetrics(
            runner_name=self.name,
            language=self.language,
            path=str(path),
            data={"test": True},
        )


class _ExternalRunner(BaseRunner):
    """Runner that requires an external tool."""

    @property
    def name(self) -> str:
        return "external"

    @property
    def language(self) -> str:
        return "python"

    @property
    def _tool_binary(self) -> str | None:
        return "nonexistent_tool_12345"

    async def run(self, path: Path) -> RawMetrics:
        return RawMetrics(runner_name=self.name, language=self.language, path=str(path))


class TestBaseRunner:
    """Tests for the BaseRunner abstract class."""

    @pytest.mark.asyncio
    async def test_stub_runner_run(self, tmp_path):
        """A concrete runner produces RawMetrics."""
        runner = _StubRunner()
        result = await runner.run(tmp_path)
        assert result.success is True
        assert result.runner_name == "stub"
        assert result.data["test"] is True

    def test_runner_properties(self):
        """Runner exposes name and language."""
        runner = _StubRunner()
        assert runner.name == "stub"
        assert runner.language == "python"

    @pytest.mark.asyncio
    async def test_is_available_no_tool(self):
        """Runner with no tool_binary is always available."""
        runner = _StubRunner()
        assert await runner.is_available() is True

    @pytest.mark.asyncio
    async def test_is_available_missing_tool(self):
        """Runner with missing external tool returns False."""
        runner = _ExternalRunner()
        assert await runner.is_available() is False

    def test_make_error(self, tmp_path):
        """_make_error produces a failed RawMetrics."""
        runner = _StubRunner()
        result = runner._make_error(tmp_path, "something went wrong")
        assert result.success is False
        assert "something went wrong" in result.errors
        assert result.runner_name == "stub"
