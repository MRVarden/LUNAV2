"""Tests for EmergentPhi -- phi discovered by cognitive dynamics.

Uses the real luna_commonV2 evolution engine for generating realistic
coupling energy data, ensuring the tests validate against actual system
behavior rather than synthetic patterns.
"""

import json
import math
import sys

import numpy as np
import pytest

# luna_commonV2 on the path
sys.path.insert(0, "/home/sayohmy/luna_commonV2")

from luna_common.consciousness.emergent_phi import (
    EmergentPhi,
    _FALLBACK_PHI,
    _FIB,
    _MIN_STEPS,
    _PHI_MAX,
    _PHI_MIN,
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
def ep() -> EmergentPhi:
    """Fresh EmergentPhi instance."""
    return EmergentPhi()


@pytest.fixture
def coupling_energies() -> list[float]:
    """Generate realistic coupling energies from the evolution engine.

    Runs 1200 steps of the real cognitive state equation with LUNA's
    identity profile and constant info_deltas.
    """
    psi0 = get_psi0("LUNA")
    psi = psi0.copy()
    mass = MassMatrix(psi0)
    Gt, Gx, Gc = gamma_temporal(), gamma_spatial(), gamma_info()
    G_total = Gt + Gx + Gc

    history: list[np.ndarray] = [psi.copy()]
    energies: list[float] = []

    for _ in range(1200):
        psi = evolution_step(
            psi, psi0, mass, (Gt, Gx, Gc),
            history=history,
            info_deltas=[0.01, 0.01, 0.01, 0.01],
        )
        history.append(psi.copy())
        energies.append(float(abs(psi @ G_total @ psi)))

    return energies


# -------------------------------------------------------------------------
# Tests
# -------------------------------------------------------------------------

class TestBootstrap:
    """Tests for the bootstrap phase (< 610 steps)."""

    def test_bootstrap_returns_fallback(self, ep: EmergentPhi) -> None:
        """Before _MIN_STEPS, get_phi() returns the mathematical fallback."""
        assert ep.is_bootstrapping()
        assert ep.get_phi() == _FALLBACK_PHI

        # Feed some steps but stay under the threshold.
        for _ in range(100):
            ep.update(0.063)

        assert ep.is_bootstrapping()
        assert ep.get_phi() == _FALLBACK_PHI

    def test_is_bootstrapping_true_before_threshold(self, ep: EmergentPhi) -> None:
        """is_bootstrapping() is True until _MIN_STEPS steps are reached."""
        for i in range(_MIN_STEPS - 1):
            ep.update(0.05)
            assert ep.is_bootstrapping(), f"Should bootstrap at step {i + 1}"

    def test_is_bootstrapping_false_after_threshold(
        self, coupling_energies: list[float],
    ) -> None:
        """After _MIN_STEPS, bootstrapping should be False."""
        ep = EmergentPhi()
        for energy in coupling_energies:
            ep.update(energy)

        assert not ep.is_bootstrapping()
        assert ep.snapshot()["step_count"] == len(coupling_energies)


class TestConvergence:
    """Tests for phi convergence after sufficient steps."""

    def test_convergence_after_fibonacci_steps(
        self, coupling_energies: list[float],
    ) -> None:
        """Fed realistic coupling energies, phi_e should approach the true PHI.

        At 1200 steps, we expect at least 2 decimal places of accuracy.
        """
        ep = EmergentPhi()
        for energy in coupling_energies:
            ep.update(energy)

        phi_e = ep.get_phi()
        error = abs(phi_e - PHI)

        # The estimate should be within 1% of true phi.
        assert error < 0.02, (
            f"phi_e={phi_e:.6f} too far from PHI={PHI:.6f} (error={error:.6f})"
        )
        # Precision should be at least 2 decimal places.
        assert ep.precision() >= 2

    def test_starts_at_1_5_not_1_618(self) -> None:
        """The internal estimate bootstraps at 1.5, not the golden ratio.

        This proves the system discovers phi on its own.
        """
        ep = EmergentPhi()
        snap = ep.snapshot()
        assert snap["current_phi"] == 1.5


class TestSafetyBounds:
    """Tests for safety bounds on extreme input."""

    def test_extreme_high_energy_stays_bounded(self, ep: EmergentPhi) -> None:
        """Extremely large energies should not push phi outside bounds."""
        for i in range(1, 1200):
            ep.update(1e10 * (i ** 2))

        phi_e = ep.get_phi()
        assert _PHI_MIN <= phi_e <= _PHI_MAX

    def test_extreme_low_energy_stays_bounded(self, ep: EmergentPhi) -> None:
        """Tiny energies should not cause issues."""
        for i in range(1, 1200):
            ep.update(1e-15)

        # Even with tiny energy, phi should be within bounds.
        # (After bootstrap, the ratios may be very close to 1.0)
        phi_e = ep.get_phi()
        assert _PHI_MIN <= phi_e <= _PHI_MAX

    def test_mixed_extreme_energies(self, ep: EmergentPhi) -> None:
        """Alternating extreme high and low energies stay bounded."""
        for i in range(1200):
            energy = 1e10 if i % 2 == 0 else 1e-10
            ep.update(energy)

        phi_e = ep.get_phi()
        assert _PHI_MIN <= phi_e <= _PHI_MAX


class TestPrecision:
    """Tests for precision tracking."""

    def test_precision_zero_during_bootstrap(self, ep: EmergentPhi) -> None:
        """precision() returns 0 before convergence begins."""
        assert ep.precision() == 0

    def test_precision_increases_with_steps(
        self, coupling_energies: list[float],
    ) -> None:
        """precision() should return at least 2 after 1200 real steps."""
        ep = EmergentPhi()
        for energy in coupling_energies:
            ep.update(energy)

        assert ep.precision() >= 2


class TestDerivedConstants:
    """Tests for derived constant accessors."""

    def test_inv_phi(self, coupling_energies: list[float]) -> None:
        """get_inv_phi() == 1 / get_phi()."""
        ep = EmergentPhi()
        for energy in coupling_energies:
            ep.update(energy)

        phi_e = ep.get_phi()
        assert math.isclose(ep.get_inv_phi(), 1.0 / phi_e, rel_tol=1e-12)

    def test_inv_phi2(self, coupling_energies: list[float]) -> None:
        """get_inv_phi2() == 1 / get_phi()**2."""
        ep = EmergentPhi()
        for energy in coupling_energies:
            ep.update(energy)

        phi_e = ep.get_phi()
        assert math.isclose(ep.get_inv_phi2(), 1.0 / phi_e ** 2, rel_tol=1e-12)

    def test_inv_phi3(self, coupling_energies: list[float]) -> None:
        """get_inv_phi3() == 1 / get_phi()**3."""
        ep = EmergentPhi()
        for energy in coupling_energies:
            ep.update(energy)

        phi_e = ep.get_phi()
        assert math.isclose(ep.get_inv_phi3(), 1.0 / phi_e ** 3, rel_tol=1e-12)

    def test_phi2(self, coupling_energies: list[float]) -> None:
        """get_phi2() == get_phi()**2."""
        ep = EmergentPhi()
        for energy in coupling_energies:
            ep.update(energy)

        phi_e = ep.get_phi()
        assert math.isclose(ep.get_phi2(), phi_e ** 2, rel_tol=1e-12)

    def test_derived_during_bootstrap(self, ep: EmergentPhi) -> None:
        """Derived constants use FALLBACK_PHI during bootstrap."""
        assert math.isclose(ep.get_phi(), _FALLBACK_PHI)
        assert math.isclose(ep.get_inv_phi(), 1.0 / _FALLBACK_PHI, rel_tol=1e-12)
        assert math.isclose(ep.get_phi2(), _FALLBACK_PHI ** 2, rel_tol=1e-12)


class TestSnapshotRestore:
    """Tests for checkpoint persistence."""

    def test_snapshot_is_json_serializable(
        self, coupling_energies: list[float],
    ) -> None:
        """snapshot() output must be valid JSON."""
        ep = EmergentPhi()
        for energy in coupling_energies:
            ep.update(energy)

        snap = ep.snapshot()
        # Should not raise.
        json_str = json.dumps(snap)
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

    def test_snapshot_restore_roundtrip(
        self, coupling_energies: list[float],
    ) -> None:
        """Restore from snapshot reproduces the exact same state."""
        ep1 = EmergentPhi()
        for energy in coupling_energies:
            ep1.update(energy)

        snap = ep1.snapshot()

        ep2 = EmergentPhi()
        ep2.restore(snap)

        snap2 = ep2.snapshot()

        assert snap["cumulative_energy"] == snap2["cumulative_energy"]
        assert snap["step_count"] == snap2["step_count"]
        assert snap["current_phi"] == snap2["current_phi"]
        assert snap["fib_checkpoints"] == snap2["fib_checkpoints"]
        assert snap["phi_history"] == snap2["phi_history"]

        assert ep1.get_phi() == ep2.get_phi()
        assert ep1.precision() == ep2.precision()
        assert ep1.is_bootstrapping() == ep2.is_bootstrapping()

    def test_restore_empty_dict(self, ep: EmergentPhi) -> None:
        """Restoring from an empty dict produces a valid default state."""
        ep.restore({})
        assert ep.is_bootstrapping()
        assert ep.get_phi() == _FALLBACK_PHI


class TestEdgeCases:
    """Tests for edge cases and robustness."""

    def test_zero_energy_handled(self, ep: EmergentPhi) -> None:
        """update(0.0) does not crash and is properly accumulated."""
        for _ in range(100):
            ep.update(0.0)

        assert ep.snapshot()["step_count"] == 100
        assert ep.snapshot()["cumulative_energy"] == 0.0

    def test_negative_energy_handled(self, ep: EmergentPhi) -> None:
        """Negative energy is taken as absolute value."""
        ep.update(-5.0)
        assert ep.snapshot()["cumulative_energy"] == 5.0

        ep.update(-3.0)
        assert ep.snapshot()["cumulative_energy"] == 8.0

    def test_nan_energy_handled(self, ep: EmergentPhi) -> None:
        """NaN energy is treated as 0.0."""
        ep.update(float("nan"))
        assert ep.snapshot()["cumulative_energy"] == 0.0
        assert ep.snapshot()["step_count"] == 1

    def test_inf_energy_handled(self, ep: EmergentPhi) -> None:
        """Inf energy is treated as 0.0."""
        ep.update(float("inf"))
        assert ep.snapshot()["cumulative_energy"] == 0.0
        assert ep.snapshot()["step_count"] == 1

    def test_fibonacci_checkpoints_recorded(self, ep: EmergentPhi) -> None:
        """Fibonacci-indexed steps get recorded as checkpoints."""
        for _ in range(50):
            ep.update(1.0)

        checkpoints = ep.snapshot()["fib_checkpoints"]
        # Steps 1, 1(dup), 2, 3, 5, 8, 13, 21, 34 are Fibonacci.
        # The set _FIB starts with (1, 1, 2, 3, 5, 8, 13, 21, 34, ...).
        # Step 1 is in the set, step 2, 3, 5, 8, 13, 21, 34 are too.
        assert "1" in checkpoints
        assert "2" in checkpoints
        assert "3" in checkpoints
        assert "5" in checkpoints
        assert "8" in checkpoints
        assert "13" in checkpoints
        assert "21" in checkpoints
        assert "34" in checkpoints

    def test_fib_sequence_correctness(self) -> None:
        """Verify the precomputed Fibonacci sequence is correct."""
        # Check first several values manually.
        expected_start = (1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610)
        assert _FIB[:15] == expected_start

        # Check F(21) = 10946 is in the sequence.
        assert 10946 in _FIB

        # Verify Fibonacci property: F(n) = F(n-1) + F(n-2)
        for i in range(2, len(_FIB)):
            assert _FIB[i] == _FIB[i - 1] + _FIB[i - 2]
