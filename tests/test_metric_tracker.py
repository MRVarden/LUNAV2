"""Tests for MetricTracker provenance tracking (v2.4.0 Session 1).

Validates that MetricTracker correctly records metric observations with
source provenance (BOOTSTRAP / MEASURED / DREAM) and computes aggregate
statistics like bootstrap_ratio and measured_count.

CRITICAL INVARIANTS:
  - Only canonical METRIC_NAMES are accepted (KeyError otherwise)
  - bootstrap_ratio is 0.0 when nothing recorded
  - bootstrap_ratio reflects the LATEST source per metric
  - measured_count counts total MEASURED recordings, not unique metrics
  - get() returns None for unrecorded metrics
  - snapshot_sources() returns source strings for all recorded metrics
"""

from __future__ import annotations

from luna_common.constants import METRIC_NAMES

import pytest

from luna.metrics.tracker import MetricEntry, MetricSource, MetricTracker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tracker() -> MetricTracker:
    return MetricTracker()


def _bootstrap_all(tracker: MetricTracker) -> None:
    """Record all 7 metrics with BOOTSTRAP source."""
    for name in METRIC_NAMES:
        tracker.record(name, 0.5, MetricSource.BOOTSTRAP)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMetricTrackerRecord:
    """MetricTracker.record() correctness."""

    def test_record_returns_metric_entry(self):
        """record() returns a MetricEntry with correct fields."""
        tracker = _make_tracker()
        entry = tracker.record(
            "security_integrity", 0.9, MetricSource.MEASURED, pipeline_id="p-001"
        )
        assert isinstance(entry, MetricEntry)
        assert entry.value == 0.9
        assert entry.source == MetricSource.MEASURED
        assert entry.pipeline_id == "p-001"
        assert entry.timestamp is not None

    def test_record_unknown_metric_raises_key_error(self):
        """Recording an unknown metric name raises KeyError."""
        tracker = _make_tracker()
        with pytest.raises(KeyError, match="Unknown metric"):
            tracker.record("nonexistent_metric", 0.5, MetricSource.MEASURED)

    def test_record_overwrites_latest(self):
        """Multiple records for the same metric keep only the latest."""
        tracker = _make_tracker()
        tracker.record("coverage_pct", 0.3, MetricSource.BOOTSTRAP)
        tracker.record("coverage_pct", 0.8, MetricSource.MEASURED)

        entry = tracker.get("coverage_pct")
        assert entry is not None
        assert entry.value == 0.8
        assert entry.source == MetricSource.MEASURED


class TestMetricTrackerGet:
    """MetricTracker.get() correctness."""

    def test_get_unrecorded_returns_none(self):
        """Getting a metric that was never recorded returns None."""
        tracker = _make_tracker()
        assert tracker.get("security_integrity") is None

    def test_get_after_record_returns_entry(self):
        """Getting a recorded metric returns the entry."""
        tracker = _make_tracker()
        tracker.record("security_integrity", 0.75, MetricSource.MEASURED)
        entry = tracker.get("security_integrity")
        assert entry is not None
        assert entry.value == 0.75


class TestBootstrapRatio:
    """MetricTracker.bootstrap_ratio() correctness."""

    def test_bootstrap_ratio_empty_returns_zero(self):
        """No recordings -> bootstrap_ratio is 0.0."""
        tracker = _make_tracker()
        assert tracker.bootstrap_ratio() == 0.0

    def test_bootstrap_ratio_all_bootstrap_returns_one(self):
        """When all 7 metrics are BOOTSTRAP, ratio is 1.0."""
        tracker = _make_tracker()
        _bootstrap_all(tracker)
        assert tracker.bootstrap_ratio() == pytest.approx(1.0), (
            "All 7 metrics bootstrapped should give ratio 1.0"
        )

    def test_bootstrap_ratio_mixed(self):
        """Mixed sources give correct fraction."""
        tracker = _make_tracker()
        # 4 bootstrap, 3 measured
        for i, name in enumerate(METRIC_NAMES):
            source = MetricSource.BOOTSTRAP if i < 4 else MetricSource.MEASURED
            tracker.record(name, 0.5, source)

        expected = 4 / 7
        assert tracker.bootstrap_ratio() == pytest.approx(expected, abs=1e-6), (
            f"Expected {expected}, got {tracker.bootstrap_ratio()}"
        )

    def test_bootstrap_ratio_updates_when_source_changes(self):
        """Replacing a BOOTSTRAP with MEASURED decreases the ratio."""
        tracker = _make_tracker()
        _bootstrap_all(tracker)
        assert tracker.bootstrap_ratio() == pytest.approx(1.0)

        # Replace one with MEASURED
        tracker.record("security_integrity", 0.9, MetricSource.MEASURED)
        assert tracker.bootstrap_ratio() == pytest.approx(6 / 7, abs=1e-6)


class TestMeasuredCount:
    """MetricTracker.measured_count() correctness."""

    def test_measured_count_empty(self):
        """No recordings -> measured_count is 0."""
        tracker = _make_tracker()
        assert tracker.measured_count() == 0

    def test_measured_count_counts_only_measured(self):
        """Only MEASURED source recordings are counted."""
        tracker = _make_tracker()
        tracker.record("security_integrity", 0.5, MetricSource.BOOTSTRAP)
        tracker.record("coverage_pct", 0.7, MetricSource.MEASURED)
        tracker.record("coverage_pct", 0.8, MetricSource.MEASURED)  # second time
        tracker.record("complexity_score", 0.6, MetricSource.DREAM)

        assert tracker.measured_count() == 2, (
            "Only the two MEASURED recordings should be counted"
        )


class TestGetStatus:
    """MetricTracker.get_status() correctness."""

    def test_get_status_returns_well_formed_dict(self):
        """get_status() returns dict with expected top-level keys."""
        tracker = _make_tracker()
        tracker.record("security_integrity", 0.9, MetricSource.MEASURED)

        status = tracker.get_status()
        assert "bootstrap_ratio" in status
        assert "measured_count" in status
        assert "latest" in status
        assert isinstance(status["latest"], dict)

    def test_get_status_latest_contains_recorded_entries(self):
        """The 'latest' sub-dict reflects what was recorded."""
        tracker = _make_tracker()
        tracker.record("security_integrity", 0.9, MetricSource.MEASURED, pipeline_id="p-1")

        latest = tracker.get_status()["latest"]
        assert "security_integrity" in latest
        entry = latest["security_integrity"]
        assert entry["value"] == 0.9
        assert entry["source"] == "measured"
        assert entry["pipeline_id"] == "p-1"


class TestSnapshotSources:
    """MetricTracker.snapshot_sources() correctness."""

    def test_snapshot_sources_returns_source_strings(self):
        """Returns a dict mapping metric name to source string."""
        tracker = _make_tracker()
        tracker.record("security_integrity", 0.9, MetricSource.MEASURED)
        tracker.record("coverage_pct", 0.5, MetricSource.BOOTSTRAP)
        tracker.record("complexity_score", 0.6, MetricSource.DREAM)

        sources = tracker.snapshot_sources()
        assert sources["security_integrity"] == "measured"
        assert sources["coverage_pct"] == "bootstrap"
        assert sources["complexity_score"] == "dream"

    def test_snapshot_sources_empty_when_nothing_recorded(self):
        """Empty tracker returns empty dict."""
        tracker = _make_tracker()
        assert tracker.snapshot_sources() == {}


class TestMetricSourceEnum:
    """MetricSource enum values."""

    def test_metric_source_values(self):
        """All three source types exist with correct string values."""
        assert MetricSource.BOOTSTRAP.value == "bootstrap"
        assert MetricSource.MEASURED.value == "measured"
        assert MetricSource.DREAM.value == "dream"

    def test_metric_source_is_str_subclass(self):
        """MetricSource is a str enum (JSON-serializable)."""
        assert isinstance(MetricSource.BOOTSTRAP, str)
