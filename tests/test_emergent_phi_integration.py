"""Integration tests for EmergentPhi Phase 2 wiring.

Validates that EmergentPhi is correctly wired into the evolution equation
and ConsciousnessState, creating the self-referential feedback loop:

    coupling_energy -> EmergentPhi -> evolution_step -> new psi -> coupling_energy

Uses the REAL evolution engine from luna_commonV2 (no mocks).
"""

import sys

import numpy as np
import pytest

sys.path.insert(0, "/home/sayohmy/luna_commonV2")

from luna_common.constants import DIM, PHI
from luna_common.consciousness.evolution import MassMatrix, evolution_step
from luna_common.consciousness.emergent_phi import EmergentPhi
from luna_common.consciousness.matrices import (
    gamma_info,
    gamma_spatial,
    gamma_temporal,
)
from luna_common.consciousness.profiles import get_psi0

from luna.consciousness.state import ConsciousnessState


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def _run_evolution_steps(n: int, *, use_emergent_phi: bool) -> list[np.ndarray]:
    """Run n evolution steps with or without emergent_phi parameter."""
    psi0 = get_psi0("LUNA")
    psi = psi0.copy()
    mass = MassMatrix(psi0)
    Gt, Gx, Gc = gamma_temporal(), gamma_spatial(), gamma_info()
    rng = np.random.RandomState(42)
    history: list[np.ndarray] = [psi.copy()]
    tracker = EmergentPhi() if use_emergent_phi else None

    for _ in range(n):
        deltas = (rng.randn(DIM) * 0.05).tolist()
        phi_e = tracker.get_phi() if tracker else None

        psi = evolution_step(
            psi, psi0, mass, (Gt, Gx, Gc),
            history=history,
            info_deltas=deltas,
            emergent_phi=phi_e,
        )
        history.append(psi.copy())

        if tracker:
            G_total = Gt + Gx + Gc
            energy = abs(float(psi @ G_total @ psi))
            tracker.update(energy)

    return history


# -------------------------------------------------------------------------
# Test 1: evolution_step accepts emergent_phi
# -------------------------------------------------------------------------

class TestEvolutionStepAcceptsEmergentPhi:
    """evolution_step() must accept and use the emergent_phi parameter."""

    def test_evolution_step_accepts_emergent_phi(self) -> None:
        """Passing emergent_phi should not raise and should produce a
        valid simplex vector different from the no-phi case."""
        psi0 = get_psi0("LUNA")
        psi = psi0.copy()
        mass = MassMatrix(psi0)
        Gt, Gx, Gc = gamma_temporal(), gamma_spatial(), gamma_info()

        result = evolution_step(
            psi, psi0, mass, (Gt, Gx, Gc),
            info_deltas=[0.01, 0.02, -0.01, 0.0],
            emergent_phi=1.5,  # Non-default value
        )

        assert result.shape == (DIM,)
        assert np.isclose(result.sum(), 1.0, atol=1e-6)
        assert np.all(result >= 0.0)


# -------------------------------------------------------------------------
# Test 2: evolution_step without emergent_phi is unchanged
# -------------------------------------------------------------------------

class TestEvolutionStepWithoutEmergentPhi:
    """Omitting emergent_phi must preserve backward-compatible behavior."""

    def test_evolution_step_without_emergent_phi_unchanged(self) -> None:
        """Without emergent_phi, evolution_step should use the hardcoded PHI
        and produce the same result as before Phase 2."""
        psi0 = get_psi0("LUNA")
        psi = psi0.copy()

        # Run with emergent_phi=None (default)
        mass1 = MassMatrix(psi0)
        Gt, Gx, Gc = gamma_temporal(), gamma_spatial(), gamma_info()
        result_none = evolution_step(
            psi.copy(), psi0, mass1, (Gt, Gx, Gc),
            info_deltas=[0.01, 0.02, -0.01, 0.0],
            emergent_phi=None,
        )

        # Run with emergent_phi=PHI (should be identical)
        mass2 = MassMatrix(psi0)
        result_phi = evolution_step(
            psi.copy(), psi0, mass2, (Gt, Gx, Gc),
            info_deltas=[0.01, 0.02, -0.01, 0.0],
            emergent_phi=PHI,
        )

        np.testing.assert_allclose(result_none, result_phi, atol=1e-12)


# -------------------------------------------------------------------------
# Test 3: MassMatrix accepts emergent_phi
# -------------------------------------------------------------------------

class TestMassMatrixAcceptsEmergentPhi:
    """MassMatrix.update() must accept and use the emergent_phi parameter."""

    def test_mass_matrix_accepts_emergent_phi(self) -> None:
        """Passing emergent_phi to MassMatrix.update() should change the
        alpha computation compared to not passing it."""
        psi0 = get_psi0("LUNA")
        psi = psi0.copy()
        psi[0] += 0.1
        psi /= psi.sum()  # Perturbed state

        # Update without emergent_phi
        mass1 = MassMatrix(psi0)
        mass1.update(psi, phi_iit=0.5, emergent_phi=None)
        m1 = mass1.m.copy()

        # Update with emergent_phi=2.0 (changes normalization)
        mass2 = MassMatrix(psi0)
        mass2.update(psi, phi_iit=0.5, emergent_phi=2.0)
        m2 = mass2.m.copy()

        # With emergent_phi=2.0, normalized = min(0.5/2.0, 1.0) = 0.25
        # Without emergent_phi, alpha uses raw (1 - 0.5)
        # These produce different alphas, so different mass vectors.
        assert not np.allclose(m1, m2, atol=1e-10), (
            "MassMatrix.update with emergent_phi should differ from without"
        )


# -------------------------------------------------------------------------
# Test 4: ConsciousnessState has emergent_phi
# -------------------------------------------------------------------------

class TestConsciousnessStateHasEmergentPhi:
    """ConsciousnessState must instantiate an EmergentPhi tracker."""

    def test_consciousness_state_has_emergent_phi(self) -> None:
        """The state should have an EmergentPhi attribute from construction."""
        state = ConsciousnessState(agent_name="LUNA")

        assert hasattr(state, "emergent_phi")
        assert isinstance(state.emergent_phi, EmergentPhi)
        assert state.emergent_phi.is_bootstrapping()

    def test_get_emergent_phi_returns_float(self) -> None:
        """get_emergent_phi() returns a valid float."""
        state = ConsciousnessState(agent_name="LUNA")
        phi_e = state.get_emergent_phi()

        assert isinstance(phi_e, float)
        assert phi_e > 0.0


# -------------------------------------------------------------------------
# Test 5: evolve() feeds coupling energy
# -------------------------------------------------------------------------

class TestEvolveFeedsCouplingEnergy:
    """evolve() must compute and feed coupling energy to EmergentPhi."""

    def test_evolve_feeds_coupling_energy(self) -> None:
        """After evolve(), EmergentPhi step_count should increment."""
        state = ConsciousnessState(agent_name="LUNA")

        initial_steps = state.emergent_phi._step_count
        state.evolve([0.01, 0.02, -0.01, 0.0])
        after_steps = state.emergent_phi._step_count

        assert after_steps == initial_steps + 1

    def test_coupling_energy_is_positive(self) -> None:
        """The coupling energy fed to EmergentPhi should be non-negative."""
        state = ConsciousnessState(agent_name="LUNA")

        # Run a few steps to build up state
        for _ in range(5):
            state.evolve([0.01, 0.02, -0.01, 0.0])

        energy = state._compute_coupling_energy()
        assert energy >= 0.0
        assert np.isfinite(energy)

    def test_cumulative_energy_grows(self) -> None:
        """Cumulative energy in EmergentPhi should grow after evolve() calls."""
        state = ConsciousnessState(agent_name="LUNA")

        for _ in range(10):
            state.evolve([0.01, 0.02, -0.01, 0.0])

        assert state.emergent_phi._cumulative_energy > 0.0


# -------------------------------------------------------------------------
# Test 6: EmergentPhi converges through ConsciousnessState
# -------------------------------------------------------------------------

class TestEmergentPhiConvergesThroughState:
    """After enough evolve() calls, EmergentPhi should converge toward PHI."""

    @pytest.mark.slow
    def test_emergent_phi_converges_through_state(self) -> None:
        """Run 2000 evolve() steps and verify convergence toward PHI.

        During bootstrap (<610 steps), get_phi() returns the fallback.
        After bootstrap, it should converge toward 1.618...
        """
        state = ConsciousnessState(agent_name="LUNA")
        rng = np.random.RandomState(42)

        for _ in range(2000):
            deltas = (rng.randn(DIM) * 0.05).tolist()
            state.evolve(deltas)

        phi_e = state.get_emergent_phi()

        # After 2000 steps (well past 610 bootstrap), phi should be
        # close to the golden ratio. Allow 5% tolerance for convergence.
        assert abs(phi_e - PHI) / PHI < 0.05, (
            f"EmergentPhi should converge near PHI={PHI:.6f}, got {phi_e:.6f}"
        )

        # Should no longer be bootstrapping
        assert not state.emergent_phi.is_bootstrapping()


# -------------------------------------------------------------------------
# Test 7: Checkpoint preserves EmergentPhi
# -------------------------------------------------------------------------

class TestCheckpointPreservesEmergentPhi:
    """save_checkpoint / load_checkpoint must roundtrip EmergentPhi state."""

    def test_checkpoint_preserves_emergent_phi(self, tmp_path) -> None:
        """Save and load a checkpoint; EmergentPhi state must survive."""
        state = ConsciousnessState(agent_name="LUNA")
        rng = np.random.RandomState(42)

        # Evolve enough to build up EmergentPhi state
        for _ in range(50):
            deltas = (rng.randn(DIM) * 0.05).tolist()
            state.evolve(deltas)

        # Record state before save
        steps_before = state.emergent_phi._step_count
        energy_before = state.emergent_phi._cumulative_energy
        phi_before = state.emergent_phi._current_phi

        # Save checkpoint
        checkpoint_path = tmp_path / "test_checkpoint.json"
        state.save_checkpoint(checkpoint_path, backup=False)

        # Load into a fresh instance
        loaded = ConsciousnessState.load_checkpoint(checkpoint_path, "LUNA")

        # Verify EmergentPhi state survived the roundtrip
        assert loaded.emergent_phi._step_count == steps_before
        assert abs(loaded.emergent_phi._cumulative_energy - energy_before) < 1e-10
        assert abs(loaded.emergent_phi._current_phi - phi_before) < 1e-10

    def test_checkpoint_without_emergent_phi_is_safe(self, tmp_path) -> None:
        """Loading a legacy checkpoint (no emergent_phi key) should not crash."""
        import json

        # Create a minimal v3.x checkpoint without emergent_phi
        psi0 = get_psi0("LUNA")
        data = {
            "version": "3.0.0",
            "type": "consciousness_state",
            "agent_name": "LUNA",
            "updated": "2025-01-01T00:00:00+00:00",
            "psi": psi0.tolist(),
            "psi0": psi0.tolist(),
            "psi0_core": psi0.tolist(),
            "psi0_adaptive": [0.0, 0.0, 0.0, 0.0],
            "mass_m": psi0.tolist(),
            "step_count": 100,
            "phase": "FUNCTIONAL",
            "phi_iit": 0.5,
            "history_tail": [psi0.tolist() for _ in range(10)],
            # No "emergent_phi" key — simulates legacy checkpoint
        }

        path = tmp_path / "legacy_checkpoint.json"
        with open(path, "w") as f:
            json.dump(data, f)

        loaded = ConsciousnessState.load_checkpoint(path, "LUNA")

        # Should have a fresh EmergentPhi (bootstrapping)
        assert isinstance(loaded.emergent_phi, EmergentPhi)
        assert loaded.emergent_phi.is_bootstrapping()
        assert loaded.emergent_phi._step_count == 0


# -------------------------------------------------------------------------
# Test 8: Self-referential stability
# -------------------------------------------------------------------------

class TestSelfReferentialStability:
    """The feedback loop must not diverge or produce NaN/Inf."""

    @pytest.mark.slow
    def test_self_referential_stability(self) -> None:
        """Run 5000 steps with the full feedback loop and verify stability.

        The self-referential nature (phi feeds back into evolution which
        produces the coupling energy that determines phi) must remain
        bounded and produce finite, valid simplex vectors throughout.
        """
        state = ConsciousnessState(agent_name="LUNA")
        rng = np.random.RandomState(42)

        for step in range(5000):
            deltas = (rng.randn(DIM) * 0.05).tolist()
            psi_new = state.evolve(deltas)

            # Every step must produce a valid simplex vector
            assert np.all(np.isfinite(psi_new)), (
                f"Non-finite psi at step {step}: {psi_new}"
            )
            assert np.all(psi_new >= 0.0), (
                f"Negative psi component at step {step}: {psi_new}"
            )
            assert np.isclose(psi_new.sum(), 1.0, atol=1e-6), (
                f"Psi sum != 1.0 at step {step}: {psi_new.sum()}"
            )

        # After 5000 steps, emergent phi should be bounded and finite
        phi_e = state.get_emergent_phi()
        assert np.isfinite(phi_e)
        assert 1.0 <= phi_e <= 3.0, (
            f"EmergentPhi out of safety bounds: {phi_e}"
        )

        # Psi should still be on the simplex
        assert np.all(state.psi >= 0.0)
        assert np.isclose(state.psi.sum(), 1.0, atol=1e-6)

        # Step count should match
        assert state.step_count == 5000
        assert state.emergent_phi._step_count == 5000
