"""Tests for awakening — post-dream processing and reporting."""

from __future__ import annotations

import pytest

from luna.dream.awakening import Awakening, AwakeningReport
from luna.dream.dream_cycle import DreamPhase, DreamReport, PhaseResult


def _make_dream_report(
    drift: float = 0.05,
    significant: int = 2,
    removed: int = 3,
    creative: int = 1,
) -> DreamReport:
    """Create a DreamReport with configurable data."""
    sig_list = [
        {"components": ["perception", "reflection"], "correlation": 0.8}
    ] * significant

    creative_list = [
        {"components": ["perception", "integration"], "correlation": 0.7}
    ] * creative

    return DreamReport(
        phases=[
            PhaseResult(
                phase=DreamPhase.CONSOLIDATION,
                data={
                    "mean_psi": [0.25, 0.35, 0.25, 0.15],
                    "drift_from_psi0": drift,
                    "num_entries": 50,
                },
                duration_seconds=0.01,
            ),
            PhaseResult(
                phase=DreamPhase.REINTERPRETATION,
                data={"significant": sig_list},
                duration_seconds=0.01,
            ),
            PhaseResult(
                phase=DreamPhase.DEFRAGMENTATION,
                data={"removed": removed, "capped": False, "final_size": 47},
                duration_seconds=0.01,
            ),
            PhaseResult(
                phase=DreamPhase.CREATIVE,
                data={"unexpected_couplings": creative_list},
                duration_seconds=0.01,
            ),
        ],
        total_duration=0.04,
        history_before=50,
        history_after=47,
    )


@pytest.fixture
def awakening():
    return Awakening()


class TestAwakeningReport:
    """Tests for AwakeningReport."""

    def test_frozen(self):
        """AwakeningReport is immutable."""
        report = AwakeningReport(
            timestamp="2026-01-01T00:00:00Z",
            dream_duration=1.0,
            history_before=50,
            history_after=47,
            entries_removed=3,
            significant_correlations=2,
            creative_connections=1,
            drift_from_psi0=0.05,
            psi_updated=False,
        )
        with pytest.raises(AttributeError):
            report.drift_from_psi0 = 0.1  # type: ignore[misc]

    def test_to_dict(self):
        """to_dict serializes all fields."""
        report = AwakeningReport(
            timestamp="2026-01-01T00:00:00Z",
            dream_duration=1.5,
            history_before=50,
            history_after=47,
            entries_removed=3,
            significant_correlations=2,
            creative_connections=1,
            drift_from_psi0=0.05,
            psi_updated=False,
        )
        d = report.to_dict()
        assert d["dream_duration"] == 1.5
        assert d["entries_removed"] == 3
        assert d["significant_correlations"] == 2
        assert d["creative_connections"] == 1
        assert d["drift_from_psi0"] == 0.05
        assert d["psi_updated"] is False


class TestAwakening:
    """Tests for Awakening."""

    def test_process_extracts_drift(self, awakening):
        """Drift from psi0 is extracted from consolidation phase."""
        dream = _make_dream_report(drift=0.123)
        report = awakening.process(dream)
        assert report.drift_from_psi0 == pytest.approx(0.123)

    def test_process_counts_significant_correlations(self, awakening):
        """Significant correlations count is extracted."""
        dream = _make_dream_report(significant=4)
        report = awakening.process(dream)
        assert report.significant_correlations == 4

    def test_process_counts_creative_connections(self, awakening):
        """Creative connections count is extracted."""
        dream = _make_dream_report(creative=3)
        report = awakening.process(dream)
        assert report.creative_connections == 3

    def test_process_counts_removed_entries(self, awakening):
        """Removed entries count is extracted from defragmentation."""
        dream = _make_dream_report(removed=7)
        report = awakening.process(dream)
        assert report.entries_removed == 7

    def test_process_history_counts(self, awakening):
        """History before/after are passed through."""
        dream = _make_dream_report()
        report = awakening.process(dream)
        assert report.history_before == 50
        assert report.history_after == 47

    def test_process_dream_duration(self, awakening):
        """Dream duration is passed through."""
        dream = _make_dream_report()
        report = awakening.process(dream)
        assert report.dream_duration == pytest.approx(0.04)

    def test_process_returns_awakening_report(self, awakening):
        """process() returns an AwakeningReport."""
        dream = _make_dream_report()
        report = awakening.process(dream)
        assert isinstance(report, AwakeningReport)

    def test_process_timestamp_set(self, awakening):
        """Awakening report has a timestamp."""
        dream = _make_dream_report()
        report = awakening.process(dream)
        assert report.timestamp is not None
        assert "T" in report.timestamp

    def test_process_empty_dream(self, awakening):
        """Processing a minimal dream report works."""
        dream = DreamReport(
            phases=[],
            total_duration=0.0,
            history_before=0,
            history_after=0,
        )
        report = awakening.process(dream)
        assert report.drift_from_psi0 == 0.0
        assert report.significant_correlations == 0
        assert report.creative_connections == 0
        assert report.entries_removed == 0
