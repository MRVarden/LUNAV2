"""Tests for Radon runner — Python complexity analysis."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from luna.metrics.runners.radon_runner import RadonRunner


@pytest.fixture
def radon_runner():
    return RadonRunner(timeout=10.0)


class TestRadonRunner:
    """Tests for RadonRunner."""

    def test_properties(self, radon_runner):
        """RadonRunner has correct name and language."""
        assert radon_runner.name == "radon"
        assert radon_runner.language == "python"
        assert radon_runner._tool_binary == "radon"

    @pytest.mark.asyncio
    async def test_run_nonexistent_path(self, radon_runner):
        """Radon runner handles nonexistent paths."""
        result = await radon_runner.run(Path("/nonexistent/path"))
        assert result.success is False
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_run_cc_parsing(self, radon_runner, tmp_path):
        """Radon runner parses CC JSON output correctly."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def f():\n  pass\n")

        cc_output = json.dumps({
            str(test_file): [
                {"name": "f", "complexity": 1, "type": "function"},
            ]
        })

        mi_output = json.dumps({
            str(test_file): 100.0,
        })

        def mock_subprocess(args, **kwargs):
            result = MagicMock()
            result.returncode = 0
            if "cc" in args:
                result.stdout = cc_output
            else:
                result.stdout = mi_output
            result.stderr = ""
            return result

        with patch("luna.metrics.runners.radon_runner.subprocess.run", side_effect=mock_subprocess):
            result = await radon_runner.run(tmp_path)

        assert result.success is True
        assert result.data["cc_average"] == 1.0
        assert result.data["cc_max"] == 1
        assert result.data["cc_count"] == 1

    @pytest.mark.asyncio
    async def test_run_mi_parsing(self, radon_runner, tmp_path):
        """Radon runner parses MI JSON output correctly."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        cc_output = json.dumps({})
        mi_output = json.dumps({
            str(test_file): 85.5,
        })

        def mock_subprocess(args, **kwargs):
            result = MagicMock()
            result.returncode = 0
            if "cc" in args:
                result.stdout = cc_output
            else:
                result.stdout = mi_output
            result.stderr = ""
            return result

        with patch("luna.metrics.runners.radon_runner.subprocess.run", side_effect=mock_subprocess):
            result = await radon_runner.run(tmp_path)

        assert result.success is True
        assert result.data["mi_average"] == 85.5

    @pytest.mark.asyncio
    async def test_run_tool_failure(self, radon_runner, tmp_path):
        """Radon runner handles tool errors gracefully."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        def mock_subprocess(args, **kwargs):
            result = MagicMock()
            result.returncode = 1
            result.stdout = ""
            result.stderr = "radon: error"
            return result

        with patch("luna.metrics.runners.radon_runner.subprocess.run", side_effect=mock_subprocess):
            result = await radon_runner.run(tmp_path)

        # Both CC and MI fail -> still returns (but with errors)
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_run_timeout(self, radon_runner, tmp_path):
        """Radon runner handles timeouts gracefully."""
        import subprocess
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        with patch(
            "luna.metrics.runners.radon_runner.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="radon", timeout=10),
        ):
            result = await radon_runner.run(tmp_path)

        assert len(result.errors) > 0
        assert any("timed out" in e for e in result.errors)
