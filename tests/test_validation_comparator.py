"""Tests for comparator — statistical comparison."""

from __future__ import annotations

import pytest

from luna.validation.comparator import Comparator, ComparisonResult


class TestComparisonResult:
    """Tests for ComparisonResult."""

    def test_to_dict(self):
        """to_dict serializes all fields."""
        result = ComparisonResult(
            baseline_mean=0.5,
            consciousness_mean=0.7,
            delta=0.2,
            improvement_pct=40.0,
            p_value=0.01,
            significant=True,
            n_samples=10,
        )
        d = result.to_dict()
        assert d["delta"] == 0.2
        assert d["significant"] is True

    def test_frozen(self):
        """ComparisonResult is immutable."""
        result = ComparisonResult(
            baseline_mean=0.5,
            consciousness_mean=0.7,
            delta=0.2,
            improvement_pct=40.0,
            p_value=0.01,
            significant=True,
            n_samples=10,
        )
        with pytest.raises(AttributeError):
            result.delta = 0.5  # type: ignore[misc]


class TestComparator:
    """Tests for Comparator."""

    @pytest.fixture
    def comparator(self):
        return Comparator()

    def test_clear_improvement(self, comparator):
        """Clear improvement is detected."""
        baseline = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
        conscious = [0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9]
        result = comparator.compare(baseline, conscious)
        assert result.delta > 0
        assert result.consciousness_mean > result.baseline_mean

    def test_no_improvement(self, comparator):
        """Equal scores show no improvement."""
        scores = [0.5, 0.5, 0.5, 0.5, 0.5]
        result = comparator.compare(scores, scores)
        assert result.delta == 0.0

    def test_different_lengths_raises(self, comparator):
        """Different length lists raise ValueError."""
        with pytest.raises(ValueError, match="same length"):
            comparator.compare([0.5], [0.5, 0.7])

    def test_empty_lists_raises(self, comparator):
        """Empty lists raise ValueError."""
        with pytest.raises(ValueError, match="not be empty"):
            comparator.compare([], [])

    def test_improvement_percentage(self, comparator):
        """Improvement percentage is calculated correctly."""
        baseline = [0.5, 0.5, 0.5, 0.5, 0.5]
        conscious = [0.75, 0.75, 0.75, 0.75, 0.75]
        result = comparator.compare(baseline, conscious)
        assert result.improvement_pct == pytest.approx(50.0)

    def test_n_samples(self, comparator):
        """n_samples reflects the number of paired observations."""
        baseline = [0.5, 0.6, 0.7]
        conscious = [0.6, 0.7, 0.8]
        result = comparator.compare(baseline, conscious)
        assert result.n_samples == 3

    def test_custom_significance_level(self):
        """Custom significance level changes threshold."""
        comp = Comparator(significance_level=0.01)
        baseline = [0.5, 0.5, 0.5]
        conscious = [0.6, 0.6, 0.6]
        result = comp.compare(baseline, conscious)
        # p-value calculated, significance based on 0.01
        assert isinstance(result.significant, bool)
