"""Tests for PhiScorer snapshot/restore persistence (v2.4.0 Session 0).

Validates that PhiScorer can serialize its internal EMA state to a dict
and restore it faithfully, enabling metric persistence across restarts.

CRITICAL INVARIANTS:
  - snapshot() only includes initialized metrics
  - restore() is tolerant of unknown names (forward compat)
  - restore() rejects NaN/Inf/missing values
  - restore() clamps values to [0, 1]
  - snapshot -> restore round-trip preserves EMA values exactly
  - score() after restore yields the same composite as before
"""

from __future__ import annotations

import math

import pytest

from luna_common.constants import METRIC_NAMES, PHI_WEIGHTS
from luna_common.phi_engine.scorer import PhiScorer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scorer() -> PhiScorer:
    """Create a fresh PhiScorer with default canonical metrics."""
    return PhiScorer()


def _seed_all_metrics(scorer: PhiScorer, value: float = 0.75) -> None:
    """Initialize all 7 metrics to a uniform value."""
    for name in METRIC_NAMES:
        scorer.update(name, value)


def _seed_partial_metrics(scorer: PhiScorer, count: int = 3) -> list[str]:
    """Initialize the first *count* metrics and return their names."""
    names = list(METRIC_NAMES[:count])
    for i, name in enumerate(names):
        scorer.update(name, 0.5 + i * 0.1)
    return names


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPhiScorerSnapshot:
    """PhiScorer.snapshot() must return a faithful, serializable dict."""

    def test_snapshot_empty_scorer_returns_empty_dict(self):
        """A scorer with no updates should snapshot to {}."""
        scorer = _make_scorer()
        snap = scorer.snapshot()
        assert snap == {}, (
            f"Expected empty dict from uninitialized scorer, got {snap}"
        )

    def test_snapshot_partial_only_includes_initialized(self):
        """Only metrics that have received at least one update appear."""
        scorer = _make_scorer()
        seeded = _seed_partial_metrics(scorer, count=3)

        snap = scorer.snapshot()
        assert set(snap.keys()) == set(seeded), (
            f"Expected keys {seeded}, got {list(snap.keys())}"
        )
        # Remaining metrics must NOT appear
        for name in METRIC_NAMES:
            if name not in seeded:
                assert name not in snap

    def test_snapshot_full_returns_all_seven_metrics(self):
        """After updating all 7 metrics, snapshot has 7 entries."""
        scorer = _make_scorer()
        _seed_all_metrics(scorer, value=0.8)

        snap = scorer.snapshot()
        assert len(snap) == 7, f"Expected 7 entries, got {len(snap)}"
        for name in METRIC_NAMES:
            assert name in snap, f"Missing metric {name!r} in snapshot"
            assert "value" in snap[name], f"Missing 'value' key for {name!r}"

    def test_snapshot_values_are_finite_bounded(self):
        """All snapshot values must be finite floats in [0, 1]."""
        scorer = _make_scorer()
        _seed_all_metrics(scorer, value=0.65)

        snap = scorer.snapshot()
        for name, entry in snap.items():
            v = entry["value"]
            assert isinstance(v, float), f"{name}: value is not float: {type(v)}"
            assert math.isfinite(v), f"{name}: value is not finite: {v}"
            assert 0.0 <= v <= 1.0, f"{name}: value out of [0,1]: {v}"

    def test_snapshot_reflects_latest_ema_not_raw(self):
        """Snapshot returns the EMA smoothed value, not the last raw input."""
        scorer = _make_scorer()
        scorer.update("security_integrity", 1.0)
        scorer.update("security_integrity", 0.0)  # EMA != 0.0

        snap = scorer.snapshot()
        v = snap["security_integrity"]["value"]
        # After two updates with alpha=0.5: EMA = 0.5*0.0 + 0.5*1.0 = 0.5
        assert v == pytest.approx(0.5, abs=1e-10), (
            f"Expected EMA value ~0.5, got {v}"
        )


class TestPhiScorerRestore:
    """PhiScorer.restore() must faithfully reinstate EMA values."""

    def test_restore_empty_dict_returns_zero(self):
        """Restoring from {} should restore zero metrics."""
        scorer = _make_scorer()
        count = scorer.restore({})
        assert count == 0
        assert scorer.initialized_count() == 0

    def test_restore_partial_returns_correct_count(self):
        """Restoring a subset returns the count of successfully restored metrics."""
        scorer = _make_scorer()
        snap = {
            "security_integrity": {"value": 0.9},
            "coverage_pct": {"value": 0.7},
        }
        count = scorer.restore(snap)
        assert count == 2, f"Expected 2 restored, got {count}"
        assert scorer.initialized_count() == 2

    def test_restore_full_roundtrip_preserves_values(self):
        """snapshot() -> restore() round-trip preserves all EMA values exactly."""
        scorer1 = _make_scorer()
        values = [0.95, 0.72, 0.60, 0.45, 0.38, 0.25, 0.10]
        for name, val in zip(METRIC_NAMES, values):
            scorer1.update(name, val)

        snap = scorer1.snapshot()

        scorer2 = _make_scorer()
        count = scorer2.restore(snap)
        assert count == 7

        for name in METRIC_NAMES:
            v1 = scorer1.get_metric(name)
            v2 = scorer2.get_metric(name)
            assert v2 == pytest.approx(v1, abs=1e-12), (
                f"{name}: restored {v2} != original {v1}"
            )

    def test_restore_ignores_unknown_metric_names(self):
        """Unknown names are silently skipped (forward compatibility)."""
        scorer = _make_scorer()
        snap = {
            "security_integrity": {"value": 0.9},
            "future_metric_2030": {"value": 0.5},
            "another_unknown": {"value": 0.3},
        }
        count = scorer.restore(snap)
        assert count == 1, (
            "Only security_integrity should be restored; unknown names skipped"
        )
        assert scorer.get_metric("security_integrity") == pytest.approx(0.9)

    def test_restore_ignores_nan_values(self):
        """NaN values are rejected."""
        scorer = _make_scorer()
        snap = {"security_integrity": {"value": float("nan")}}
        count = scorer.restore(snap)
        assert count == 0, "NaN should be rejected"
        assert scorer.get_metric("security_integrity") is None

    def test_restore_ignores_inf_values(self):
        """Inf values are rejected."""
        scorer = _make_scorer()
        snap = {
            "security_integrity": {"value": float("inf")},
            "coverage_pct": {"value": float("-inf")},
        }
        count = scorer.restore(snap)
        assert count == 0, "Inf values should be rejected"

    def test_restore_ignores_missing_value_key(self):
        """Entries without a 'value' key are skipped."""
        scorer = _make_scorer()
        snap = {
            "security_integrity": {"source": "measured"},  # no "value"
            "coverage_pct": {"value": 0.8},
        }
        count = scorer.restore(snap)
        assert count == 1, "Entry without 'value' key should be skipped"
        assert scorer.get_metric("security_integrity") is None
        assert scorer.get_metric("coverage_pct") == pytest.approx(0.8)

    def test_restore_clamps_out_of_bounds_values(self):
        """Values outside [0, 1] are clamped, not rejected."""
        scorer = _make_scorer()
        snap = {
            "security_integrity": {"value": 1.5},
            "coverage_pct": {"value": -0.3},
        }
        count = scorer.restore(snap)
        assert count == 2, "Out-of-bounds values should be clamped, not rejected"
        assert scorer.get_metric("security_integrity") == pytest.approx(1.0)
        assert scorer.get_metric("coverage_pct") == pytest.approx(0.0)

    def test_restore_overwrites_existing_ema(self):
        """Restore overwrites a previously-initialized EMA value."""
        scorer = _make_scorer()
        scorer.update("security_integrity", 0.3)
        assert scorer.get_metric("security_integrity") == pytest.approx(0.3)

        scorer.restore({"security_integrity": {"value": 0.9}})
        assert scorer.get_metric("security_integrity") == pytest.approx(0.9), (
            "Restore should overwrite the existing EMA value"
        )


class TestPhiScorerScoreAfterRestore:
    """score() must compute correctly from restored EMA values."""

    def test_score_after_restore_matches_original(self):
        """Composite score from restored state matches the original."""
        scorer1 = _make_scorer()
        values = [0.95, 0.72, 0.60, 0.45, 0.38, 0.25, 0.10]
        for name, val in zip(METRIC_NAMES, values):
            scorer1.update(name, val)
        original_score = scorer1.score()
        snap = scorer1.snapshot()

        scorer2 = _make_scorer()
        scorer2.restore(snap)
        restored_score = scorer2.score()

        assert restored_score == pytest.approx(original_score, abs=1e-12), (
            f"Restored score {restored_score} != original {original_score}"
        )

    def test_score_after_partial_restore(self):
        """Partial restore computes score from only the restored metrics."""
        scorer = _make_scorer()
        scorer.restore({
            "security_integrity": {"value": 0.8},
            "coverage_pct": {"value": 0.6},
        })
        score = scorer.score()
        # Manual: (0.396*0.8 + 0.244*0.6) / (0.396 + 0.244)
        expected = (0.396 * 0.8 + 0.244 * 0.6) / (0.396 + 0.244)
        assert score == pytest.approx(expected, abs=1e-4), (
            f"Partial restore score {score} != expected {expected}"
        )

    def test_score_zero_after_empty_restore(self):
        """Score remains 0.0 after restoring nothing."""
        scorer = _make_scorer()
        scorer.restore({})
        assert scorer.score() == 0.0
