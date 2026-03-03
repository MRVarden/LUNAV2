"""Tests for metrics normalizer — raw metrics to [0,1] canonical values."""

from __future__ import annotations

import pytest

from luna_common.constants import METRIC_NAMES
from luna.metrics.base_runner import RawMetrics
from luna.metrics.normalizer import NormalizedMetrics, normalize, _clamp01


class TestNormalizedMetrics:
    """Tests for the NormalizedMetrics dataclass."""

    def test_empty(self):
        """Empty NormalizedMetrics has no values."""
        nm = NormalizedMetrics()
        assert nm.values == {}
        assert nm.zones == {}
        assert nm.raw_sources == []

    def test_get_existing(self):
        """get() returns the value for an existing metric."""
        nm = NormalizedMetrics(values={"coverage_pct": 0.85})
        assert nm.get("coverage_pct") == 0.85

    def test_get_missing(self):
        """get() returns None for a missing metric."""
        nm = NormalizedMetrics(values={"coverage_pct": 0.85})
        assert nm.get("complexity_score") is None


class TestClamp01:
    """Tests for the _clamp01 helper."""

    def test_in_range(self):
        assert _clamp01(0.5) == 0.5

    def test_below_zero(self):
        assert _clamp01(-0.5) == 0.0

    def test_above_one(self):
        assert _clamp01(1.5) == 1.0

    def test_boundaries(self):
        assert _clamp01(0.0) == 0.0
        assert _clamp01(1.0) == 1.0


class TestNormalize:
    """Tests for the normalize() function."""

    def test_empty_input(self):
        """Normalizing empty list returns empty metrics."""
        result = normalize([])
        assert result.values == {}
        assert result.zones == {}

    def test_radon_complexity(self):
        """Radon CC maps to complexity_score via 1/(1+cc)."""
        raw = RawMetrics(
            runner_name="radon",
            language="python",
            path="/test",
            data={"cc_average": 4.0, "mi_average": 75.0},
            success=True,
        )
        result = normalize([raw])
        # 1/(1+4) = 0.2
        assert abs(result.values["complexity_score"] - 0.2) < 0.01
        assert "radon" in result.raw_sources

    def test_radon_zero_complexity(self):
        """Zero complexity gives score 1.0."""
        raw = RawMetrics(
            runner_name="radon",
            language="python",
            path="/test",
            data={"cc_average": 0.0},
            success=True,
        )
        result = normalize([raw])
        assert result.values["complexity_score"] == 1.0

    def test_ast_abstraction_ratio(self):
        """AST data maps to abstraction_ratio."""
        raw = RawMetrics(
            runner_name="ast",
            language="python",
            path="/test",
            data={
                "abstraction_ratio": 0.3,
                "avg_function_lines": 17.0,
                "function_size_quality": 1.0,
                "test_ratio": 0.5,
            },
            success=True,
        )
        result = normalize([raw])
        assert result.values["abstraction_ratio"] == 0.3
        assert result.values["function_size_score"] == 1.0
        assert result.values["test_ratio"] == 0.5

    def test_coverage_normalization(self):
        """Coverage percentage is divided by 100."""
        raw = RawMetrics(
            runner_name="coverage_py",
            language="python",
            path="/test",
            data={"coverage_pct": 85.0, "branch_coverage_pct": 0.0},
            success=True,
        )
        result = normalize([raw])
        assert abs(result.values["coverage_pct"] - 0.85) < 0.01

    def test_branch_coverage_preferred(self):
        """Branch coverage is preferred over line coverage."""
        raw = RawMetrics(
            runner_name="coverage_py",
            language="python",
            path="/test",
            data={"coverage_pct": 90.0, "branch_coverage_pct": 75.0},
            success=True,
        )
        result = normalize([raw])
        assert abs(result.values["coverage_pct"] - 0.75) < 0.01

    def test_multiple_runners(self):
        """Multiple runners contribute to different metrics."""
        raws = [
            RawMetrics(
                runner_name="radon", language="python", path="/t",
                data={"cc_average": 2.0}, success=True,
            ),
            RawMetrics(
                runner_name="ast", language="python", path="/t",
                data={
                    "abstraction_ratio": 0.4,
                    "avg_function_lines": 17.0,
                    "function_size_quality": 1.0,
                    "test_ratio": 0.8,
                },
                success=True,
            ),
            RawMetrics(
                runner_name="coverage_py", language="python", path="/t",
                data={"coverage_pct": 70.0, "branch_coverage_pct": 0.0},
                success=True,
            ),
        ]
        result = normalize(raws)
        assert "complexity_score" in result.values
        assert "abstraction_ratio" in result.values
        assert "coverage_pct" in result.values
        assert len(result.raw_sources) == 3

    def test_failed_runners_excluded(self):
        """Failed runners are not included in normalization."""
        raws = [
            RawMetrics(
                runner_name="radon", language="python", path="/t",
                data={"cc_average": 2.0}, success=True,
            ),
            RawMetrics(
                runner_name="ast", language="python", path="/t",
                data={}, success=False, errors=["crashed"],
            ),
        ]
        result = normalize(raws)
        assert "complexity_score" in result.values
        assert "abstraction_ratio" not in result.values
        assert "ast" not in result.raw_sources

    def test_zones_classified(self):
        """All normalized values get Fibonacci zone classification."""
        raw = RawMetrics(
            runner_name="radon", language="python", path="/t",
            data={"cc_average": 0.5}, success=True,
        )
        result = normalize([raw])
        assert "complexity_score" in result.zones
        # 1/(1+0.5) ≈ 0.667 -> comfort zone [0.618, 1.0]
        assert result.zones["complexity_score"] == "comfort"

    def test_all_values_in_range(self):
        """All normalized values are in [0, 1]."""
        raw = RawMetrics(
            runner_name="radon", language="python", path="/t",
            data={"cc_average": 100.0, "mi_average": 150.0},
            success=True,
        )
        result = normalize([raw])
        for value in result.values.values():
            assert 0.0 <= value <= 1.0
