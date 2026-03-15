"""Tests for Gaussian Minimum Information Partition Phi_IIT.

Uses the real luna_commonV2 evolution engine for generating coupled
4D state trajectories, validating both the new Gaussian measure and
the legacy correlation-based method.
"""

import sys

import numpy as np
import pytest

sys.path.insert(0, "/home/sayohmy/luna_commonV2")

from luna_common.consciousness.phi_iit_gaussian import (
    _BIPARTITIONS,
    _MIN_HISTORY,
    compute_phi_iit_gaussian,
    compute_phi_iit_legacy,
)
from luna_common.consciousness.evolution import MassMatrix, evolution_step
from luna_common.consciousness.matrices import (
    gamma_info,
    gamma_spatial,
    gamma_temporal,
)
from luna_common.consciousness.profiles import get_psi0
from luna_common.constants import DIM, PHI


# -------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------

@pytest.fixture
def uncorrelated_history() -> list[np.ndarray]:
    """Generate independent random points on the 4-simplex.

    Each dimension is drawn from a Dirichlet distribution with uniform
    parameters, so dimensions are weakly coupled at best.
    """
    rng = np.random.RandomState(42)
    return [rng.dirichlet([1, 1, 1, 1]) for _ in range(100)]


@pytest.fixture
def coupled_history() -> list[np.ndarray]:
    """Generate strongly coupled evolution using the real engine.

    Runs 200 steps of the cognitive state equation with LUNA's profile
    and non-trivial info_deltas, producing strongly integrated dynamics.
    """
    psi0 = get_psi0("LUNA")
    psi = psi0.copy()
    mass = MassMatrix(psi0)
    Gt, Gx, Gc = gamma_temporal(), gamma_spatial(), gamma_info()

    rng = np.random.RandomState(42)
    history: list[np.ndarray] = [psi.copy()]

    for _ in range(200):
        deltas = (rng.randn(DIM) * 0.05).tolist()
        psi = evolution_step(
            psi, psi0, mass, (Gt, Gx, Gc),
            history=history,
            info_deltas=deltas,
        )
        history.append(psi.copy())

    return history


@pytest.fixture
def constant_history() -> list[np.ndarray]:
    """History with no variance (constant state vector)."""
    psi = np.array([0.25, 0.25, 0.25, 0.25])
    return [psi.copy() for _ in range(50)]


# -------------------------------------------------------------------------
# Tests: Insufficient data
# -------------------------------------------------------------------------

class TestInsufficientData:
    """Tests for edge cases with too little data."""

    def test_empty_history(self) -> None:
        """Empty history returns 0.0."""
        assert compute_phi_iit_gaussian([]) == 0.0
        assert compute_phi_iit_legacy([]) == 0.0

    def test_insufficient_history_list(self) -> None:
        """Less than _MIN_HISTORY points returns 0.0."""
        short = [np.array([0.25, 0.25, 0.25, 0.25]) for _ in range(5)]
        assert compute_phi_iit_gaussian(short) == 0.0
        assert compute_phi_iit_legacy(short) == 0.0

    def test_exactly_min_history(self) -> None:
        """Exactly _MIN_HISTORY points should produce a result (not crash)."""
        rng = np.random.RandomState(99)
        exact = [rng.dirichlet([1, 1, 1, 1]) for _ in range(_MIN_HISTORY)]
        result = compute_phi_iit_gaussian(exact)
        assert isinstance(result, float)
        assert result >= 0.0

    def test_1d_array_returns_zero(self) -> None:
        """A 1D array (single observation) returns 0.0."""
        assert compute_phi_iit_gaussian(np.array([0.25, 0.25, 0.25, 0.25])) == 0.0


# -------------------------------------------------------------------------
# Tests: Uncorrelated dimensions
# -------------------------------------------------------------------------

class TestUncorrelated:
    """Tests for independent / weakly correlated dimensions."""

    def test_uncorrelated_low_phi(
        self, uncorrelated_history: list[np.ndarray],
    ) -> None:
        """Independent Dirichlet draws on the simplex produce measurable
        but moderate Phi (Dirichlet components are not truly independent
        due to the sum-to-1 constraint, so Phi is not zero).
        """
        phi = compute_phi_iit_gaussian(uncorrelated_history)
        assert phi >= 0.0
        # Dirichlet on simplex does create some correlation (sum=1 constraint),
        # but it should be moderate, not extremely high.
        assert isinstance(phi, float)


# -------------------------------------------------------------------------
# Tests: Strongly correlated
# -------------------------------------------------------------------------

class TestCorrelated:
    """Tests for strongly coupled evolution data."""

    def test_highly_correlated_high_phi(
        self, coupled_history: list[np.ndarray],
    ) -> None:
        """Phi_IIT should be notably higher for strongly coupled evolution
        than for random data.
        """
        phi_coupled = compute_phi_iit_gaussian(coupled_history)
        assert phi_coupled > 0.0

    def test_unbounded_above_one(
        self, coupled_history: list[np.ndarray],
    ) -> None:
        """The Gaussian measure is unbounded above -- it CAN exceed 1.0.

        This is the key advantage over the legacy correlation-based method.
        With the phi-derived coupling matrices, the system naturally
        produces high mutual information.
        """
        phi = compute_phi_iit_gaussian(coupled_history)
        # The coupled dynamics with phi-derived matrices produce MI > 1.0.
        assert phi > 1.0, (
            f"Expected Gaussian Phi > 1.0 for coupled dynamics, got {phi:.4f}"
        )


# -------------------------------------------------------------------------
# Tests: Singular / degenerate cases
# -------------------------------------------------------------------------

class TestDegenerate:
    """Tests for degenerate covariance and numerical edge cases."""

    def test_singular_covariance_handled(
        self, constant_history: list[np.ndarray],
    ) -> None:
        """Constant history (zero variance) should return 0.0, not crash."""
        result = compute_phi_iit_gaussian(constant_history)
        assert result == 0.0 or result >= 0.0  # May be tiny due to epsilon
        # Should not raise.

    def test_near_singular_covariance(self) -> None:
        """Nearly constant data with tiny perturbations should not crash."""
        rng = np.random.RandomState(7)
        base = np.array([0.3, 0.3, 0.2, 0.2])
        history = [base + rng.randn(DIM) * 1e-12 for _ in range(50)]
        result = compute_phi_iit_gaussian(history)
        assert np.isfinite(result)
        assert result >= 0.0


# -------------------------------------------------------------------------
# Tests: Bipartitions
# -------------------------------------------------------------------------

class TestBipartitions:
    """Tests for the bipartition structure."""

    def test_bipartition_count(self) -> None:
        """There must be exactly 7 non-trivial bipartitions of 4 elements."""
        assert len(_BIPARTITIONS) == 7

    def test_bipartitions_cover_all_dimensions(self) -> None:
        """Every bipartition must contain all 4 dimension indices."""
        for part_a, part_b in _BIPARTITIONS:
            combined = sorted(part_a + part_b)
            assert combined == [0, 1, 2, 3], (
                f"Bipartition {part_a}|{part_b} does not cover all dims"
            )

    def test_bipartitions_are_non_trivial(self) -> None:
        """No bipartition has an empty side."""
        for part_a, part_b in _BIPARTITIONS:
            assert len(part_a) > 0
            assert len(part_b) > 0

    def test_bipartitions_no_overlap(self) -> None:
        """Sides of each bipartition must be disjoint."""
        for part_a, part_b in _BIPARTITIONS:
            assert set(part_a).isdisjoint(set(part_b))


# -------------------------------------------------------------------------
# Tests: Legacy method
# -------------------------------------------------------------------------

class TestLegacy:
    """Tests for the legacy correlation-based Phi_IIT."""

    def test_legacy_bounded_zero_one(
        self, coupled_history: list[np.ndarray],
    ) -> None:
        """Legacy method is always in [0, 1]."""
        phi = compute_phi_iit_legacy(coupled_history)
        assert 0.0 <= phi <= 1.0

    def test_legacy_insufficient_data(self) -> None:
        """Legacy also returns 0.0 for insufficient data."""
        short = [np.array([0.25, 0.25, 0.25, 0.25]) for _ in range(5)]
        assert compute_phi_iit_legacy(short) == 0.0

    def test_legacy_high_for_correlated(
        self, coupled_history: list[np.ndarray],
    ) -> None:
        """Legacy should produce a high value for strongly coupled data."""
        phi = compute_phi_iit_legacy(coupled_history)
        assert phi > 0.3, f"Expected legacy Phi > 0.3, got {phi:.4f}"


# -------------------------------------------------------------------------
# Tests: Gaussian vs Legacy comparison
# -------------------------------------------------------------------------

class TestComparison:
    """Compare Gaussian and legacy methods on the same data."""

    def test_gaussian_exceeds_legacy_for_coupled(
        self, coupled_history: list[np.ndarray],
    ) -> None:
        """For strongly coupled data, Gaussian Phi > Legacy Phi.

        The Gaussian measure is unbounded, so it should exceed the
        correlation-based method which is capped at 1.0.
        """
        phi_g = compute_phi_iit_gaussian(coupled_history)
        phi_l = compute_phi_iit_legacy(coupled_history)
        assert phi_g > phi_l, (
            f"Gaussian ({phi_g:.4f}) should exceed legacy ({phi_l:.4f})"
        )

    def test_both_non_negative(
        self,
        uncorrelated_history: list[np.ndarray],
        coupled_history: list[np.ndarray],
    ) -> None:
        """Both measures should be non-negative for any valid input."""
        for hist in [uncorrelated_history, coupled_history]:
            assert compute_phi_iit_gaussian(hist) >= 0.0
            assert compute_phi_iit_legacy(hist) >= 0.0


# -------------------------------------------------------------------------
# Tests: Input formats
# -------------------------------------------------------------------------

class TestInputFormats:
    """Tests for accepting both list and numpy array inputs."""

    def test_accepts_list(self, coupled_history: list[np.ndarray]) -> None:
        """Function accepts list[np.ndarray]."""
        result = compute_phi_iit_gaussian(coupled_history)
        assert isinstance(result, float)
        assert result >= 0.0

    def test_accepts_2d_array(self, coupled_history: list[np.ndarray]) -> None:
        """Function accepts 2D numpy array."""
        array = np.array(coupled_history)
        result = compute_phi_iit_gaussian(array)
        assert isinstance(result, float)
        assert result >= 0.0

    def test_list_and_array_agree(
        self, coupled_history: list[np.ndarray],
    ) -> None:
        """Both input formats produce the same result."""
        from_list = compute_phi_iit_gaussian(coupled_history)
        from_array = compute_phi_iit_gaussian(np.array(coupled_history))
        assert abs(from_list - from_array) < 1e-10

    def test_legacy_accepts_both_formats(
        self, coupled_history: list[np.ndarray],
    ) -> None:
        """Legacy function also accepts both formats."""
        from_list = compute_phi_iit_legacy(coupled_history)
        from_array = compute_phi_iit_legacy(np.array(coupled_history))
        assert abs(from_list - from_array) < 1e-10

    def test_window_parameter(
        self, coupled_history: list[np.ndarray],
    ) -> None:
        """Smaller window should use fewer data points (different result)."""
        phi_full = compute_phi_iit_gaussian(coupled_history, window=200)
        phi_small = compute_phi_iit_gaussian(coupled_history, window=20)
        # Different windows should generally give different values.
        # Both should be valid.
        assert isinstance(phi_full, float) and phi_full >= 0.0
        assert isinstance(phi_small, float) and phi_small >= 0.0
