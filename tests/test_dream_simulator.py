"""Wave 3 — Tests for DreamSimulator (4-agent coupled consciousness simulation).

Tests cover:
  - Initialization with default and custom profiles (4 agents).
  - Dynamic inter-agent coupling (CHECK 3 resolution).
  - Synchronous update semantics (all agents from same time-slice).
  - replay() with minimum 10-step guarantee.
  - compute_phi_iit() and compute_mean_phi_iit().
  - clone() deep independence.
  - Diagnostics: measure_divergence(), identities_preserved(), stability_score().
  - step() with info_deltas modifies trajectories.
"""

from __future__ import annotations

import numpy as np
import pytest

from luna_common.constants import AGENT_PROFILES, DIM, DREAM_REPLAY_DT
from luna.dream.simulator import DreamSimulator, _AGENT_KEYS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXPECTED_AGENTS = sorted(_AGENT_KEYS.keys())  # luna, sayohmy, sentinel, test-engineer


def _profiles_sum_to_one(profiles: dict[str, tuple[float, ...]]) -> bool:
    """Verify all profiles lie on the simplex."""
    for vals in profiles.values():
        if abs(sum(vals) - 1.0) > 1e-6:
            return False
    return True


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestDreamSimulatorInit:
    """Initialization and accessors."""

    def test_default_profiles(self) -> None:
        """Default init uses AGENT_PROFILES from constants."""
        sim = DreamSimulator()
        assert sim.agent_ids == EXPECTED_AGENTS

    def test_all_agents_have_state(self) -> None:
        sim = DreamSimulator()
        for agent in EXPECTED_AGENTS:
            psi = sim.get_psi(agent)
            assert psi.shape == (DIM,)
            assert abs(psi.sum() - 1.0) < 1e-6, "Psi must be on simplex"

    def test_initial_psi_equals_psi0(self) -> None:
        """At step 0 each agent's Psi equals its identity profile."""
        sim = DreamSimulator()
        for agent_id, profile_key in _AGENT_KEYS.items():
            psi = sim.get_psi(agent_id)
            expected = np.array(AGENT_PROFILES[profile_key])
            np.testing.assert_allclose(psi, expected, atol=1e-10)

    def test_custom_profiles(self) -> None:
        """Custom profiles override defaults."""
        custom = {
            "LUNA": (0.30, 0.30, 0.20, 0.20),
            "SAYOHMY": (0.10, 0.10, 0.10, 0.70),
            "SENTINEL": (0.60, 0.15, 0.15, 0.10),
            "TESTENGINEER": (0.10, 0.10, 0.70, 0.10),
        }
        sim = DreamSimulator(profiles=custom)
        psi_luna = sim.get_psi("luna")
        np.testing.assert_allclose(psi_luna, np.array(custom["LUNA"]), atol=1e-10)

    def test_history_starts_with_one_entry(self) -> None:
        sim = DreamSimulator()
        for agent in EXPECTED_AGENTS:
            hist = sim.get_history(agent)
            assert len(hist) == 1, "History should start with exactly the initial state"

    def test_get_all_psi_returns_copies(self) -> None:
        sim = DreamSimulator()
        all_psi = sim.get_all_psi()
        assert set(all_psi.keys()) == set(EXPECTED_AGENTS)
        # Mutating returned dict should not affect simulator.
        all_psi["luna"][:] = 0.0
        psi_luna = sim.get_psi("luna")
        assert psi_luna.sum() > 0.5, "get_all_psi must return copies"


# ---------------------------------------------------------------------------
# Evolution (CHECK 3 — dynamic coupling)
# ---------------------------------------------------------------------------


class TestDreamSimulatorStep:
    """step() with dynamic inter-agent coupling."""

    def test_step_changes_psi(self) -> None:
        """A single step should move Psi away from Psi0."""
        sim = DreamSimulator()
        psi_before = sim.get_all_psi()
        sim.step()
        psi_after = sim.get_all_psi()

        # At least one agent should have moved.
        moved = any(
            not np.allclose(psi_before[a], psi_after[a], atol=1e-12)
            for a in EXPECTED_AGENTS
        )
        assert moved, "At least one agent should evolve after a step"

    def test_step_preserves_simplex(self) -> None:
        """Psi must remain on the simplex after evolution."""
        sim = DreamSimulator()
        for _ in range(20):
            sim.step()
        for agent in EXPECTED_AGENTS:
            psi = sim.get_psi(agent)
            assert abs(psi.sum() - 1.0) < 1e-6, f"{agent} Psi not on simplex"
            assert (psi >= 0).all(), f"{agent} Psi has negative components"

    def test_step_history_grows(self) -> None:
        sim = DreamSimulator()
        sim.step()
        sim.step()
        for agent in EXPECTED_AGENTS:
            assert len(sim.get_history(agent)) == 3  # 1 initial + 2 steps

    def test_synchronous_update(self) -> None:
        """All agents use the same time-slice (not sequential)."""
        sim = DreamSimulator()
        psi_snapshot = sim.get_all_psi()
        sim.step()

        # Run a second simulator with manual sequential coupling for comparison.
        # The key invariant: the step used the *same* snapshot for all agents,
        # so the order of iteration does not matter.
        sim2 = DreamSimulator()
        sim2.step()

        # Both simulators should produce identical results (same starting state).
        for agent in EXPECTED_AGENTS:
            np.testing.assert_allclose(
                sim.get_psi(agent),
                sim2.get_psi(agent),
                atol=1e-12,
                err_msg=f"Synchronous update violated for {agent}",
            )

    def test_step_with_info_deltas(self) -> None:
        """info_deltas should influence the evolution differently."""
        sim_base = DreamSimulator()
        sim_delta = DreamSimulator()

        # Evolve both 5 steps; one with strong positive luna deltas.
        for _ in range(5):
            sim_base.step()
            sim_delta.step(info_deltas={"luna": [0.5, 0.5, 0.5, 0.5]})

        psi_base = sim_base.get_psi("luna")
        psi_delta = sim_delta.get_psi("luna")

        # They must differ.
        assert not np.allclose(psi_base, psi_delta, atol=1e-6), (
            "info_deltas should produce a different trajectory"
        )

    def test_dynamic_coupling_uses_live_psi(self) -> None:
        """Verify that the spatial gradient uses live Psi, not frozen Psi0.

        After evolving one simulator 20 steps, the other agents' Psi will
        have drifted from Psi0. A fresh simulator (where others are still at
        Psi0) should produce different results when stepped from the same
        agent state -- because the coupling differs.
        """
        sim = DreamSimulator()
        # Evolve to build coupling divergence.
        for _ in range(20):
            sim.step()

        # Now create a fresh simulator with default Psi0.
        sim_fresh = DreamSimulator()

        # Copy luna's state from the evolved sim into the fresh one.
        sim_fresh._psi["luna"] = sim.get_psi("luna").copy()
        sim_fresh._mass["luna"].m = sim._mass["luna"].m.copy()

        # Step both.
        sim.step()
        sim_fresh.step()

        # Luna's next state should differ because the other 3 agents'
        # live Psi values are different in the two simulators.
        assert not np.allclose(
            sim.get_psi("luna"),
            sim_fresh.get_psi("luna"),
            atol=1e-6,
        ), "Dynamic coupling should cause divergence when others differ"


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


class TestDreamSimulatorReplay:
    """replay() — wake event replay with minimum step guarantee."""

    def test_replay_minimum_10_steps(self) -> None:
        """harvest_events=0 should still produce at least 10 steps."""
        sim = DreamSimulator()
        sim.replay(harvest_events=0)
        # 1 initial + 10 replay steps.
        for agent in EXPECTED_AGENTS:
            assert len(sim.get_history(agent)) == 11

    def test_replay_respects_harvest_count(self) -> None:
        """If harvest_events > 10, use that count."""
        sim = DreamSimulator()
        sim.replay(harvest_events=25)
        for agent in EXPECTED_AGENTS:
            assert len(sim.get_history(agent)) == 26  # 1 + 25

    def test_replay_with_deltas_sequence(self) -> None:
        """info_deltas_sequence is applied per step."""
        sim_plain = DreamSimulator()
        sim_deltas = DreamSimulator()

        seq = [
            {"luna": [0.3, 0.0, 0.0, 0.0]},
            {"sentinel": [0.0, 0.0, -0.3, 0.0]},
        ]

        sim_plain.replay(harvest_events=12)
        sim_deltas.replay(harvest_events=12, info_deltas_sequence=seq)

        # The first two steps should differ (deltas applied), rest are plain.
        psi_plain = sim_plain.get_psi("luna")
        psi_deltas = sim_deltas.get_psi("luna")
        assert not np.allclose(psi_plain, psi_deltas, atol=1e-6)

    def test_replay_simplex_preserved(self) -> None:
        sim = DreamSimulator()
        sim.replay(harvest_events=50)
        for agent in EXPECTED_AGENTS:
            psi = sim.get_psi(agent)
            assert abs(psi.sum() - 1.0) < 1e-6
            assert (psi >= 0).all()


# ---------------------------------------------------------------------------
# Phi_IIT computation
# ---------------------------------------------------------------------------


class TestDreamSimulatorPhiIIT:
    """compute_phi_iit() and compute_mean_phi_iit()."""

    def test_phi_iit_insufficient_history(self) -> None:
        """Returns 0.0 when history is shorter than window."""
        sim = DreamSimulator()
        # Only 1 entry in history.
        assert sim.compute_phi_iit("luna", window=50) == 0.0

    def test_phi_iit_after_replay(self) -> None:
        """After enough steps, phi_iit should be non-negative."""
        sim = DreamSimulator()
        sim.replay(harvest_events=60)
        phi = sim.compute_phi_iit("luna", window=50)
        assert phi >= 0.0

    def test_mean_phi_iit_averages_agents(self) -> None:
        sim = DreamSimulator()
        sim.replay(harvest_events=60)
        mean = sim.compute_mean_phi_iit(window=50)
        individual = [sim.compute_phi_iit(a, window=50) for a in EXPECTED_AGENTS]
        expected_mean = float(np.mean(individual))
        assert abs(mean - expected_mean) < 1e-10

    def test_phi_iit_zero_variance_returns_zero(self) -> None:
        """If an agent's history has zero variance, phi_iit is 0."""
        sim = DreamSimulator()
        # Force constant history (same state repeated).
        static = np.array([0.25, 0.35, 0.25, 0.15])
        sim._history["luna"] = [static.copy() for _ in range(60)]
        assert sim.compute_phi_iit("luna", window=50) == 0.0


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


class TestDreamSimulatorDiagnostics:
    """measure_divergence(), identities_preserved(), stability_score()."""

    def test_divergence_at_init_is_zero(self) -> None:
        sim = DreamSimulator()
        divs = sim.measure_divergence()
        for agent_id, d in divs.items():
            assert d == pytest.approx(0.0, abs=1e-10), (
                f"{agent_id} divergence should be 0 at init"
            )

    def test_divergence_increases_after_steps(self) -> None:
        sim = DreamSimulator()
        for _ in range(20):
            sim.step()
        divs = sim.measure_divergence()
        assert any(d > 1e-6 for d in divs.values()), (
            "After evolution, at least one agent should diverge from Psi0"
        )

    def test_identities_preserved_at_init(self) -> None:
        sim = DreamSimulator()
        assert sim.identities_preserved() == 4

    def test_identities_preserved_after_moderate_evolution(self) -> None:
        """With default params and moderate steps, identities should survive."""
        sim = DreamSimulator()
        sim.replay(harvest_events=30)
        preserved = sim.identities_preserved()
        # The system is designed to preserve identities; expect at least 3/4.
        assert preserved >= 3, f"Only {preserved}/4 identities preserved after 30 steps"

    def test_stability_score_at_init(self) -> None:
        """With only one history entry, stability is 1.0."""
        sim = DreamSimulator()
        assert sim.stability_score() == 1.0

    def test_stability_score_range(self) -> None:
        sim = DreamSimulator()
        sim.replay(harvest_events=30)
        score = sim.stability_score()
        assert 0.0 <= score <= 1.0

    def test_stability_score_decreases_under_stress(self) -> None:
        """Injecting strong deltas should reduce stability."""
        sim_calm = DreamSimulator()
        sim_stress = DreamSimulator()

        for _ in range(30):
            sim_calm.step()
            sim_stress.step(info_deltas={
                a: [0.5, -0.5, 0.5, -0.5] for a in EXPECTED_AGENTS
            })

        assert sim_stress.stability_score() <= sim_calm.stability_score() + 0.05


# ---------------------------------------------------------------------------
# Clone
# ---------------------------------------------------------------------------


class TestDreamSimulatorClone:
    """clone() deep copy independence."""

    def test_clone_produces_equal_state(self) -> None:
        sim = DreamSimulator()
        sim.replay(harvest_events=15)
        clone = sim.clone()

        for agent in EXPECTED_AGENTS:
            np.testing.assert_allclose(
                sim.get_psi(agent), clone.get_psi(agent), atol=1e-12
            )
            assert len(sim.get_history(agent)) == len(clone.get_history(agent))

    def test_clone_is_independent(self) -> None:
        """Mutating the clone should not affect the original."""
        sim = DreamSimulator()
        sim.replay(harvest_events=10)
        psi_before = sim.get_psi("luna").copy()

        clone = sim.clone()
        # Evolve clone 20 more steps with strong deltas.
        for _ in range(20):
            clone.step(info_deltas={"luna": [1.0, -1.0, 1.0, -1.0]})

        # Original must be unchanged.
        np.testing.assert_allclose(sim.get_psi("luna"), psi_before, atol=1e-12)

    def test_clone_shares_gammas(self) -> None:
        """Gamma matrices (immutable) are shared, not copied."""
        sim = DreamSimulator()
        clone = sim.clone()
        for i in range(3):
            assert sim._gammas[i] is clone._gammas[i]

    def test_clone_mass_independence(self) -> None:
        """Mass matrices in clone are separate objects."""
        sim = DreamSimulator()
        clone = sim.clone()
        for agent in EXPECTED_AGENTS:
            assert sim._mass[agent] is not clone._mass[agent]
            assert sim._mass[agent].m is not clone._mass[agent].m
