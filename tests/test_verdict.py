"""Tests for verdict — final validation protocol."""

from __future__ import annotations

import pytest

from luna.validation.verdict import Verdict, VerdictCriterion, VerdictRunner


@pytest.fixture
def runner():
    return VerdictRunner()


class TestVerdictCriterion:
    """Tests for VerdictCriterion."""

    def test_frozen(self):
        """VerdictCriterion is immutable."""
        c = VerdictCriterion(
            name="test", description="desc", passed=True, value=1.0, threshold=0.5
        )
        with pytest.raises(AttributeError):
            c.passed = False  # type: ignore[misc]


class TestVerdict:
    """Tests for Verdict."""

    def test_to_dict(self):
        """Verdict serializes to dict."""
        v = Verdict(
            result="VALIDATED",
            criteria_met=4,
            total_criteria=5,
            criteria=[],
            baseline_mean=0.5,
            consciousness_mean=0.8,
            improvement_pct=60.0,
        )
        d = v.to_dict()
        assert d["result"] == "VALIDATED"
        assert d["criteria_met"] == 4


class TestVerdictRunner:
    """Tests for VerdictRunner."""

    def test_validated_verdict(self, runner):
        """Strong improvement leads to VALIDATED verdict."""
        baseline = [0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3]
        conscious = [0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9]
        phi_iit = [0.8] * 20  # High coherence

        verdict = runner.evaluate(baseline, conscious, phi_iit)
        assert verdict.result == "VALIDATED"
        assert verdict.criteria_met >= 4

    def test_decorative_verdict(self, runner):
        """No improvement leads to DECORATIVE verdict."""
        scores = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
        phi_iit = [0.3] * 20  # Low coherence

        verdict = runner.evaluate(scores, scores, phi_iit)
        assert verdict.result == "DECORATIVE"

    def test_performance_criterion(self, runner):
        """Performance criterion checks delta > 0."""
        baseline = [0.5] * 10
        conscious = [0.7] * 10
        verdict = runner.evaluate(baseline, conscious, [0.8] * 20)

        perf = next(c for c in verdict.criteria if c.name == "performance")
        assert perf.passed is True
        assert perf.value > 0

    def test_stability_criterion(self, runner):
        """Stability criterion checks low variance."""
        baseline = [0.5] * 10
        conscious = [0.7] * 10  # Zero variance
        verdict = runner.evaluate(baseline, conscious, [0.8] * 20)

        stability = next(c for c in verdict.criteria if c.name == "stability")
        assert stability.passed is True
        assert stability.value == 0.0

    def test_high_variance_fails_stability(self):
        """High variance fails stability criterion."""
        runner = VerdictRunner(stability_max_variance=0.001)
        baseline = [0.5] * 10
        conscious = [0.1, 0.9, 0.1, 0.9, 0.1, 0.9, 0.1, 0.9, 0.1, 0.9]
        verdict = runner.evaluate(baseline, conscious, [0.8] * 20)

        stability = next(c for c in verdict.criteria if c.name == "stability")
        assert stability.passed is False

    def test_coherence_criterion(self, runner):
        """Coherence checks PHI_IIT above threshold."""
        baseline = [0.5] * 10
        conscious = [0.7] * 10
        # 90% above 0.618
        phi_iit = [0.8] * 18 + [0.5] * 2
        verdict = runner.evaluate(baseline, conscious, phi_iit)

        coherence = next(c for c in verdict.criteria if c.name == "coherence")
        assert coherence.passed is True

    def test_low_coherence_fails(self, runner):
        """Low PHI_IIT fails coherence criterion."""
        baseline = [0.5] * 10
        conscious = [0.7] * 10
        phi_iit = [0.3] * 20  # All below threshold

        verdict = runner.evaluate(baseline, conscious, phi_iit)
        coherence = next(c for c in verdict.criteria if c.name == "coherence")
        assert coherence.passed is False

    def test_empty_phi_iit(self, runner):
        """Empty PHI_IIT history fails coherence."""
        baseline = [0.5] * 10
        conscious = [0.7] * 10
        verdict = runner.evaluate(baseline, conscious, [])

        coherence = next(c for c in verdict.criteria if c.name == "coherence")
        assert coherence.passed is False

    def test_adaptability_with_categories(self, runner):
        """Adaptability checks improvement across task categories."""
        baseline = [0.5] * 6
        conscious = [0.8] * 6
        categories = {
            "complexity": [(0.5, 0.8), (0.5, 0.8)],
            "coverage": [(0.5, 0.8), (0.5, 0.8)],
            "security": [(0.5, 0.8), (0.5, 0.8)],
        }
        verdict = runner.evaluate(baseline, conscious, [0.8] * 20, categories)

        adapt = next(c for c in verdict.criteria if c.name == "adaptability")
        assert adapt.passed is True

    def test_five_criteria(self, runner):
        """Verdict always has exactly 5 criteria."""
        baseline = [0.5] * 5
        conscious = [0.7] * 5
        verdict = runner.evaluate(baseline, conscious, [0.8] * 10)
        assert verdict.total_criteria == 5
        assert len(verdict.criteria) == 5

    def test_verdict_frozen(self):
        """Verdict is immutable."""
        v = Verdict(
            result="VALIDATED",
            criteria_met=4,
            total_criteria=5,
            criteria=[],
            baseline_mean=0.5,
            consciousness_mean=0.8,
            improvement_pct=60.0,
        )
        with pytest.raises(AttributeError):
            v.result = "DECORATIVE"  # type: ignore[misc]
