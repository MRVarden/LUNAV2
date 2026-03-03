"""Phase 2 — Phi Engine test suite.

Validates the shared scoring module: EMA tracking, composite scoring,
convergence detection, phase transitions with hysteresis, and
Fibonacci-derived soft constraints.

All imports target luna_common.phi_engine (the source of truth),
NOT luna.phi_engine (the re-export).
"""

from __future__ import annotations

import math

import pytest

from luna_common.constants import (
    FIBONACCI_ZONES,
    FUNCTION_SIZE_TARGET,
    HYSTERESIS_BAND,
    INV_PHI,
    INV_PHI2,
    INV_PHI3,
    METRIC_NAMES,
    PHI_EMA_ALPHAS,
    PHI_HEALTH_THRESHOLDS,
    PHI_WEIGHTS,
)
from luna_common.phi_engine.convergence import ConvergenceDetector, ConvergenceResult
from luna_common.phi_engine.phase_transition import PhaseChangeEvent, PhaseTransitionMachine
from luna_common.phi_engine.scorer import MetricEMA, PhiScorer
from luna_common.phi_engine.soft_constraint import (
    FibonacciZone,
    SoftConstraint,
    function_size_score,
)


# ---------------------------------------------------------------------------
#  TestConstants — structural invariants on the Fibonacci weight system
# ---------------------------------------------------------------------------

class TestConstants:
    """Validate Phase 2 constants that the entire scoring system relies on."""

    def test_weights_sum_to_one(self):
        """PHI_WEIGHTS must sum to 1.000 (within rounding tolerance).

        If this fails, the weighted average in PhiScorer is fundamentally
        biased and every composite score is wrong.
        """
        assert sum(PHI_WEIGHTS) == pytest.approx(1.0, abs=0.001), (
            f"PHI_WEIGHTS sum = {sum(PHI_WEIGHTS)}, expected 1.000"
        )

    def test_health_thresholds_phi_derived(self):
        """FRAGILE and SOLID thresholds must be INV_PHI2 and INV_PHI.

        These are the golden-ratio boundaries that anchor the phase
        transition system. Hardcoding rounded values would drift.
        """
        assert PHI_HEALTH_THRESHOLDS["FRAGILE"] == pytest.approx(INV_PHI2, abs=1e-10), (
            f"FRAGILE threshold = {PHI_HEALTH_THRESHOLDS['FRAGILE']}, expected INV_PHI2={INV_PHI2}"
        )
        assert PHI_HEALTH_THRESHOLDS["SOLID"] == pytest.approx(INV_PHI, abs=1e-10), (
            f"SOLID threshold = {PHI_HEALTH_THRESHOLDS['SOLID']}, expected INV_PHI={INV_PHI}"
        )

    def test_metric_names_length_matches_weights_and_alphas(self):
        """METRIC_NAMES, PHI_WEIGHTS, and PHI_EMA_ALPHAS must be aligned."""
        assert len(METRIC_NAMES) == len(PHI_WEIGHTS) == len(PHI_EMA_ALPHAS) == 7, (
            f"Lengths: names={len(METRIC_NAMES)}, weights={len(PHI_WEIGHTS)}, "
            f"alphas={len(PHI_EMA_ALPHAS)} -- all must be 7"
        )

    def test_fibonacci_zones_cover_full_range(self):
        """Zone boundaries must cover [0.0, 1.0] without gaps.

        If there is a gap, SoftConstraint.classify() could fall through to
        the fallback branch, producing incorrect penalties.
        """
        # The zones should be: critical [0.0, INV_PHI3), warning [INV_PHI3, INV_PHI2),
        # acceptable [INV_PHI2, INV_PHI), comfort [INV_PHI, 1.0]
        assert FIBONACCI_ZONES["critical"][0] == pytest.approx(0.0, abs=1e-10)
        assert FIBONACCI_ZONES["comfort"][1] == pytest.approx(1.0, abs=1e-10)
        # Adjacent zones share a boundary: critical upper == warning lower
        assert FIBONACCI_ZONES["critical"][1] == pytest.approx(FIBONACCI_ZONES["warning"][0], abs=1e-10)
        assert FIBONACCI_ZONES["warning"][1] == pytest.approx(FIBONACCI_ZONES["acceptable"][0], abs=1e-10)
        assert FIBONACCI_ZONES["acceptable"][1] == pytest.approx(FIBONACCI_ZONES["comfort"][0], abs=1e-10)


# ---------------------------------------------------------------------------
#  TestMetricEMA — exponential moving average tracker
# ---------------------------------------------------------------------------

class TestMetricEMA:
    """Validate MetricEMA: the atomic building block of PhiScorer."""

    def test_ema_initial_none(self):
        """A freshly created EMA has value=None (not 0.0, not NaN).

        First call to update() should use the raw value as seed, not
        blend with zero.
        """
        ema = MetricEMA("test_metric", alpha=0.5)
        assert ema.value is None, "EMA must start at None before any update"

        # First update: value should equal the raw input exactly
        result = ema.update(0.8)
        assert result == pytest.approx(0.8, abs=1e-10), (
            f"First update should seed EMA with raw value, got {result}"
        )
        assert ema.value == pytest.approx(0.8, abs=1e-10)

    def test_ema_update_basic(self):
        """EMA formula: new = alpha * raw + (1 - alpha) * old.

        With alpha=0.5, old=0.8, raw=0.4:
            new = 0.5 * 0.4 + 0.5 * 0.8 = 0.60
        """
        ema = MetricEMA("coverage", alpha=0.5)
        ema.update(0.8)   # seed: value = 0.8
        result = ema.update(0.4)
        expected = 0.5 * 0.4 + 0.5 * 0.8
        assert result == pytest.approx(expected, abs=1e-10), (
            f"EMA(alpha=0.5) of [0.8, 0.4] should be {expected}, got {result}"
        )

    def test_ema_nan_guard(self):
        """NaN input must be silently ignored -- EMA value stays unchanged.

        This protects against corrupt metric data propagating through the
        scoring pipeline (e.g., division by zero in a runner).
        """
        ema = MetricEMA("security", alpha=0.3)
        ema.update(0.7)  # seed
        old_value = ema.value

        result = ema.update(float("nan"))
        assert result == pytest.approx(old_value, abs=1e-10), (
            f"NaN should not change EMA: expected {old_value}, got {result}"
        )
        assert ema.value == pytest.approx(old_value, abs=1e-10)

    def test_ema_inf_guard(self):
        """Inf input must also be silently ignored."""
        ema = MetricEMA("perf", alpha=0.2)
        result_before_init = ema.update(float("inf"))
        assert result_before_init == pytest.approx(0.0, abs=1e-10), (
            "Inf on uninitialized EMA should return 0.0"
        )
        assert ema.value is None, "Inf should not initialize the EMA"

    def test_ema_history_tracking(self):
        """history deque must record raw (clamped) values with maxlen=100.

        This ensures old data is evicted and memory is bounded, even if
        a metric is updated millions of times.
        """
        ema = MetricEMA("complexity", alpha=0.3)
        for i in range(150):
            ema.update(i / 200.0)  # values 0.0 .. 0.745

        assert len(ema.history) == 100, (
            f"History should cap at 100 entries, has {len(ema.history)}"
        )
        # The oldest entries (0..49) should have been evicted
        assert ema.history[0] == pytest.approx(50 / 200.0, abs=1e-10), (
            "Oldest surviving entry should be the 51st value pushed"
        )

    def test_ema_clamps_out_of_range(self):
        """Values outside [0, 1] must be clamped, not rejected.

        A raw value of 1.5 becomes 1.0; a raw value of -0.3 becomes 0.0.
        """
        ema = MetricEMA("test", alpha=0.5)
        ema.update(1.5)
        assert ema.value == pytest.approx(1.0, abs=1e-10), (
            "Values > 1.0 must be clamped to 1.0"
        )
        ema.update(-0.3)
        expected = 0.5 * 0.0 + 0.5 * 1.0  # = 0.5
        assert ema.value == pytest.approx(expected, abs=1e-10), (
            "Values < 0.0 must be clamped to 0.0 before EMA blending"
        )


# ---------------------------------------------------------------------------
#  TestPhiScorer — composite weighted scoring
# ---------------------------------------------------------------------------

class TestPhiScorer:
    """Validate PhiScorer: the composite health calculator."""

    def test_scorer_no_metrics_returns_zero(self):
        """score() on a fresh PhiScorer must return 0.0 (no data = no health).

        This is the base case that the renormalization formula must handle
        gracefully (denominator == 0 path).
        """
        scorer = PhiScorer()
        assert scorer.score() == pytest.approx(0.0, abs=1e-10), (
            "Empty scorer should return 0.0, not NaN or crash"
        )

    def test_scorer_composite_bounded(self):
        """After updating multiple metrics, score must remain in [0, 1].

        This is a hard invariant. If score() ever returns > 1.0 or < 0.0,
        the phase transition machine will produce incorrect transitions.
        """
        scorer = PhiScorer()
        # Feed a spread of values across different metrics
        test_values = [0.95, 0.72, 0.61, 0.88, 0.45, 0.50, 0.33]
        for name, val in zip(METRIC_NAMES, test_values):
            scorer.update(name, val)

        composite = scorer.score()
        assert 0.0 <= composite <= 1.0, (
            f"Composite score out of [0,1]: {composite}"
        )

    def test_scorer_missing_metrics_renormalized(self):
        """When only some metrics are set, weights are renormalized.

        If we set only security_integrity=1.0, the score should be 1.0
        (the only initialized metric gets 100% of the renormalized weight).
        """
        scorer = PhiScorer()
        scorer.update("security_integrity", 1.0)
        # Only 1 metric initialized, weight gets renormalized to 1.0
        assert scorer.score() == pytest.approx(1.0, abs=1e-10), (
            "Single metric at 1.0 should produce composite = 1.0 after renormalization"
        )

        # Now add a second metric with a lower value
        scorer.update("coverage_pct", 0.5)
        composite = scorer.score()
        # Expected: (0.396*1.0 + 0.244*0.5) / (0.396 + 0.244)
        expected = (0.396 * 1.0 + 0.244 * 0.5) / (0.396 + 0.244)
        assert composite == pytest.approx(expected, abs=0.01), (
            f"Two-metric composite should be ~{expected:.4f}, got {composite:.4f}"
        )

    def test_scorer_unknown_metric_raises(self):
        """Updating an unknown metric name must raise KeyError immediately.

        Silent acceptance of typos would produce invisible data loss.
        """
        scorer = PhiScorer()
        with pytest.raises(KeyError, match="Unknown metric"):
            scorer.update("nonexistent_metric", 0.5)


# ---------------------------------------------------------------------------
#  TestPhaseTransition — state machine with hysteresis
# ---------------------------------------------------------------------------

class TestPhaseTransition:
    """Validate PhaseTransitionMachine: the hysteresis-guarded phase system."""

    def test_initial_phase_is_broken(self):
        """Default initial phase must be BROKEN."""
        machine = PhaseTransitionMachine()
        assert machine.phase == "BROKEN"

    def test_phase_upgrade(self):
        """Score clearly above next threshold + hysteresis triggers upgrade.

        FRAGILE threshold = INV_PHI2 (~0.382), hysteresis = 0.025.
        Score of 0.42 > 0.382 + 0.025 = 0.407 => should upgrade to FRAGILE.
        """
        machine = PhaseTransitionMachine()
        event = machine.update(0.42)

        assert event is not None, "Score 0.42 should trigger upgrade from BROKEN"
        assert event.new_phase == "FRAGILE", (
            f"Expected FRAGILE, got {event.new_phase}"
        )
        assert event.direction == "up"
        assert machine.phase == "FRAGILE"

    def test_phase_downgrade(self):
        """Score clearly below current threshold - hysteresis triggers downgrade.

        Start at FRAGILE (threshold=0.382). Downgrade requires score < 0.382 - 0.025 = 0.357.
        """
        machine = PhaseTransitionMachine(initial_phase="FRAGILE")
        event = machine.update(0.30)

        assert event is not None, "Score 0.30 should trigger downgrade from FRAGILE"
        assert event.new_phase == "BROKEN", (
            f"Expected BROKEN, got {event.new_phase}"
        )
        assert event.direction == "down"

    def test_hysteresis_no_flipflop(self):
        """Scores oscillating within the hysteresis band must NOT trigger transitions.

        This is the core purpose of hysteresis: preventing rapid phase flipping
        when a score hovers near a threshold.

        FRAGILE threshold = 0.382, hysteresis = 0.025.
        From BROKEN: must exceed 0.407 to upgrade.
        Scores at 0.39, 0.40 are inside the band -- no upgrade.
        """
        machine = PhaseTransitionMachine()

        # These are above FRAGILE threshold (0.382) but below threshold+hysteresis (0.407)
        for score in [0.39, 0.40, 0.39, 0.40, 0.385, 0.395, 0.405]:
            event = machine.update(score)
            assert event is None, (
                f"Score {score} is in hysteresis band -- should NOT trigger transition, "
                f"but got event: {event}"
            )
        assert machine.phase == "BROKEN", (
            f"Phase should still be BROKEN, got {machine.phase}"
        )

    def test_phase_can_jump_multiple_levels(self):
        """A high enough score should jump directly past intermediate phases.

        Score 0.85 is above EXCELLENT threshold (0.786) + hysteresis (0.025) = 0.811.
        From BROKEN, it should jump straight to EXCELLENT.
        """
        machine = PhaseTransitionMachine()
        event = machine.update(0.85)

        assert event is not None, "Score 0.85 should trigger multi-level jump"
        assert event.new_phase == "EXCELLENT", (
            f"Score 0.85 from BROKEN should jump to EXCELLENT, got {event.new_phase}"
        )
        assert event.previous_phase == "BROKEN"
        assert event.direction == "up"


# ---------------------------------------------------------------------------
#  TestConvergence — sliding window stability detection
# ---------------------------------------------------------------------------

class TestConvergence:
    """Validate ConvergenceDetector: the stability oracle."""

    def test_insufficient_samples(self):
        """Fewer than min_iterations samples must return converged=False.

        The reason should be "insufficient_data" so callers can distinguish
        'not enough data' from 'actively diverging'.
        """
        detector = ConvergenceDetector(window=5, min_iterations=3)
        r1 = detector.update(0.7)
        r2 = detector.update(0.7)

        assert r1.converged is False
        assert "insufficient_data" in r1.reason
        assert r2.converged is False
        assert "insufficient_data" in r2.reason

    def test_convergence_detected(self):
        """Identical values across the window must trigger convergence.

        Five values of 0.7 have spread=0 and relative spread=0 < tol=0.01.
        """
        detector = ConvergenceDetector(window=5, tol_relative=0.01, min_iterations=3)
        for _ in range(5):
            result = detector.update(0.7)

        assert result.converged is True, (
            f"5 identical values should converge, got reason={result.reason}"
        )
        assert result.final_score == pytest.approx(0.7, abs=1e-10)
        assert result.plateau_mean == pytest.approx(0.7, abs=1e-10)
        assert result.trend == "plateau"

    def test_divergence_trend_improving(self):
        """Strictly increasing values should show trend='improving', converged=False.

        The spread will be too large for convergence, and the positive slope
        should classify as 'improving'.
        """
        detector = ConvergenceDetector(window=5, tol_relative=0.01, min_iterations=3)
        for v in [0.1, 0.2, 0.3, 0.4, 0.5]:
            result = detector.update(v)

        assert result.converged is False, (
            "Increasing values should not converge"
        )
        assert result.trend == "improving", (
            f"Strictly increasing should be 'improving', got '{result.trend}'"
        )

    def test_degrading_trend(self):
        """Strictly decreasing values should show trend='degrading'."""
        detector = ConvergenceDetector(window=5, tol_relative=0.01, min_iterations=3)
        for v in [0.9, 0.8, 0.7, 0.6, 0.5]:
            result = detector.update(v)

        assert result.converged is False
        assert result.trend == "degrading", (
            f"Strictly decreasing should be 'degrading', got '{result.trend}'"
        )


# ---------------------------------------------------------------------------
#  TestSoftConstraint — Fibonacci zone classification
# ---------------------------------------------------------------------------

class TestSoftConstraint:
    """Validate SoftConstraint and function_size_score."""

    def test_fibonacci_zone_comfort(self):
        """Value 0.7 is in [INV_PHI, 1.0] = comfort zone, penalty=1.0.

        Comfort zone means no penalty -- the metric is healthy.
        """
        sc = SoftConstraint()
        result = sc.classify(0.7)

        assert result.zone == "comfort", (
            f"0.7 should be in comfort zone (>= {INV_PHI:.4f}), got '{result.zone}'"
        )
        assert result.penalty == pytest.approx(1.0, abs=1e-10)
        assert result.penalized_value == pytest.approx(0.7, abs=1e-10), (
            "With penalty=1.0, penalized_value should equal value"
        )

    def test_fibonacci_zone_critical(self):
        """Value 0.1 is in [0.0, INV_PHI3) = critical zone, penalty=0.10.

        Critical zone applies a 90% penalty -- the metric is severely impaired.
        """
        sc = SoftConstraint()
        result = sc.classify(0.1)

        assert result.zone == "critical", (
            f"0.1 should be in critical zone (< {INV_PHI3:.4f}), got '{result.zone}'"
        )
        assert result.penalty == pytest.approx(0.10, abs=1e-10)
        assert result.penalized_value == pytest.approx(0.1 * 0.10, abs=1e-10)

    def test_fibonacci_zone_acceptable(self):
        """Value 0.5 is in [INV_PHI2, INV_PHI) = acceptable zone, penalty=0.85."""
        sc = SoftConstraint()
        result = sc.classify(0.5)

        assert result.zone == "acceptable", (
            f"0.5 should be in acceptable zone [{INV_PHI2:.4f}, {INV_PHI:.4f}), got '{result.zone}'"
        )
        assert result.penalty == pytest.approx(0.85, abs=1e-10)

    def test_fibonacci_zone_warning(self):
        """Value 0.3 is in [INV_PHI3, INV_PHI2) = warning zone, penalty=0.50."""
        sc = SoftConstraint()
        result = sc.classify(0.3)

        assert result.zone == "warning", (
            f"0.3 should be in warning zone [{INV_PHI3:.4f}, {INV_PHI2:.4f}), got '{result.zone}'"
        )
        assert result.penalty == pytest.approx(0.50, abs=1e-10)

    def test_function_size_score_at_target(self):
        """At target=17 lines, score must be exactly 1.0 (perfect size)."""
        assert function_size_score(17) == pytest.approx(1.0, abs=1e-10), (
            "Function at target size should score 1.0"
        )

    def test_function_size_score_symmetric(self):
        """Score is symmetric around the target: 0 and 34 both score 0.0.

        This validates the formula max(0, 1 - |avg - target| / target):
          f(0)  = max(0, 1 - 17/17) = 0.0
          f(34) = max(0, 1 - 17/17) = 0.0
          f(8)  = max(0, 1 - 9/17)  = 0.4706...
        """
        assert function_size_score(0) == pytest.approx(0.0, abs=1e-10), (
            "Zero-line functions should score 0.0"
        )
        assert function_size_score(34) == pytest.approx(0.0, abs=1e-10), (
            "Functions at 2x target should score 0.0"
        )
        expected_8 = max(0.0, 1.0 - abs(8 - 17) / 17)
        assert function_size_score(8) == pytest.approx(expected_8, abs=1e-4), (
            f"function_size_score(8) should be ~{expected_8:.4f}"
        )
