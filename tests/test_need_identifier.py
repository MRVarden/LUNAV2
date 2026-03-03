"""Session 3 -- NeedIdentifier: 10 tests for metric-driven need detection.

Validates bootstrap detection, weak-metric improvement proposals,
priority ordering, task type mapping, and propose_to_human formatting.
No I/O -- MetricTracker is seeded in-memory.
"""

from __future__ import annotations

import pytest

from luna_common.constants import INV_PHI, METRIC_NAMES

from luna.metrics.tracker import MetricSource, MetricTracker
from luna.pipeline.needs import NeedIdentifier, _METRIC_TASK_MAP, _PRIORITY_WEIGHTS
from luna.pipeline.task import PipelineTask, TaskType


@pytest.fixture
def identifier() -> NeedIdentifier:
    return NeedIdentifier()


def _bootstrap_tracker() -> MetricTracker:
    """Tracker where ALL 7 metrics are seeded as BOOTSTRAP."""
    tracker = MetricTracker()
    for name in METRIC_NAMES:
        tracker.record(name, INV_PHI, MetricSource.BOOTSTRAP)
    return tracker


def _healthy_tracker() -> MetricTracker:
    """Tracker where ALL 7 metrics are MEASURED and above INV_PHI."""
    tracker = MetricTracker()
    for name in METRIC_NAMES:
        tracker.record(name, 0.85, MetricSource.MEASURED)
    return tracker


def _mixed_tracker() -> MetricTracker:
    """Tracker with some bootstrap, some weak, some healthy metrics."""
    tracker = MetricTracker()
    # 2 bootstrap (never measured)
    tracker.record("security_integrity", INV_PHI, MetricSource.BOOTSTRAP)
    tracker.record("coverage_pct", INV_PHI, MetricSource.BOOTSTRAP)
    # 2 weak measured (below INV_PHI)
    tracker.record("complexity_score", 0.30, MetricSource.MEASURED)
    tracker.record("performance_score", 0.40, MetricSource.MEASURED)
    # 3 healthy measured (above INV_PHI)
    tracker.record("test_ratio", 0.80, MetricSource.MEASURED)
    tracker.record("abstraction_ratio", 0.75, MetricSource.MEASURED)
    tracker.record("function_size_score", 0.90, MetricSource.MEASURED)
    return tracker


# =====================================================================
#  I. IDENTIFY NEEDS
# =====================================================================


class TestIdentifyNeeds:
    """Core behavior: bootstrap -> MEASURE, weak -> improvement, healthy -> skip."""

    def test_all_bootstrap_returns_measure_tasks(
        self, identifier: NeedIdentifier,
    ) -> None:
        """All 7 metrics at BOOTSTRAP -> 7 MEASURE tasks."""
        tracker = _bootstrap_tracker()
        needs = identifier.identify(tracker)
        assert len(needs) == 7, f"Expected 7 MEASURE needs, got {len(needs)}"
        for task in needs:
            assert task.task_type == TaskType.MEASURE
            assert task.source == "need"

    def test_all_measured_healthy_returns_empty(
        self, identifier: NeedIdentifier,
    ) -> None:
        """All metrics MEASURED and above INV_PHI -> no needs."""
        tracker = _healthy_tracker()
        needs = identifier.identify(tracker)
        assert needs == [], f"Expected empty needs, got {len(needs)} tasks"

    def test_weak_metric_returns_improvement(
        self, identifier: NeedIdentifier,
    ) -> None:
        """A single weak MEASURED metric -> corresponding TaskType."""
        tracker = _healthy_tracker()
        # Override one metric to be weak.
        tracker.record("security_integrity", 0.30, MetricSource.MEASURED)
        needs = identifier.identify(tracker)
        assert len(needs) == 1, f"Expected 1 need, got {len(needs)}"
        assert needs[0].task_type == TaskType.AUDIT
        assert "security_integrity" in needs[0].description
        assert "0.300" in needs[0].description

    def test_mixed_bootstrap_and_weak(
        self, identifier: NeedIdentifier,
    ) -> None:
        """Mix of bootstrap (MEASURE) and weak (improvement) tasks."""
        tracker = _mixed_tracker()
        needs = identifier.identify(tracker)
        # 2 bootstrap -> MEASURE + 2 weak measured -> improvements
        measure_count = sum(1 for t in needs if t.task_type == TaskType.MEASURE)
        improvement_count = sum(1 for t in needs if t.task_type != TaskType.MEASURE)
        assert measure_count == 2, f"Expected 2 MEASURE, got {measure_count}"
        assert improvement_count == 2, f"Expected 2 improvement, got {improvement_count}"

    def test_priority_ordering(
        self, identifier: NeedIdentifier,
    ) -> None:
        """Needs are sorted by priority descending (highest first)."""
        tracker = _mixed_tracker()
        needs = identifier.identify(tracker)
        assert len(needs) >= 2, "Need at least 2 tasks to verify ordering"
        for i in range(len(needs) - 1):
            assert needs[i].priority >= needs[i + 1].priority, (
                f"Priority ordering violated: [{i}]={needs[i].priority:.3f} "
                f"< [{i+1}]={needs[i+1].priority:.3f}"
            )

    def test_correct_task_types_per_metric(
        self, identifier: NeedIdentifier,
    ) -> None:
        """Each weak metric maps to the expected TaskType from _METRIC_TASK_MAP."""
        tracker = MetricTracker()
        # Set all metrics as measured but weak.
        for name in METRIC_NAMES:
            tracker.record(name, 0.20, MetricSource.MEASURED)

        needs = identifier.identify(tracker)
        task_map = {t.description: t.task_type for t in needs}

        for name, expected_type in _METRIC_TASK_MAP.items():
            # Find the task that mentions this metric name.
            matching = [t for t in needs if name in t.description]
            assert len(matching) == 1, (
                f"Expected exactly 1 task for {name}, found {len(matching)}"
            )
            assert matching[0].task_type == expected_type, (
                f"{name}: expected {expected_type}, got {matching[0].task_type}"
            )


# =====================================================================
#  II. PROPOSE TO HUMAN
# =====================================================================


class TestProposeToHuman:
    """Formatting of needs into a French proposal for chat display."""

    def test_empty_needs_returns_empty_string(
        self, identifier: NeedIdentifier,
    ) -> None:
        """No needs -> empty string (not 'Aucun besoin')."""
        result = identifier.propose_to_human([])
        assert result == ""

    def test_formats_with_header(
        self, identifier: NeedIdentifier,
    ) -> None:
        """Non-empty needs produce a header '## Besoins identifies'."""
        tracker = _bootstrap_tracker()
        needs = identifier.identify(tracker)
        text = identifier.propose_to_human(needs)
        assert "## Besoins identifies" in text

    def test_includes_bootstrap_warning(
        self, identifier: NeedIdentifier,
    ) -> None:
        """When MEASURE tasks exist, a bootstrap warning is appended."""
        tracker = _bootstrap_tracker()
        needs = identifier.identify(tracker)
        text = identifier.propose_to_human(needs)
        assert "bootstrap" in text.lower()
        assert "7 metrique(s)" in text

    def test_numbered_list(
        self, identifier: NeedIdentifier,
    ) -> None:
        """Each need is numbered (1., 2., etc.)."""
        tracker = _mixed_tracker()
        needs = identifier.identify(tracker)
        text = identifier.propose_to_human(needs)
        for i in range(1, len(needs) + 1):
            assert f"{i}." in text, f"Missing numbered entry {i}. in output"
