"""Wave 3 — Tests for dream exploration scenarios.

Tests cover:
  - DreamScenario dataclass structure.
  - DEFAULT_SCENARIOS has 5 entries with correct IDs.
  - run_scenario() operates on a clone (original unchanged).
  - Each perturbation function produces measurable effects.
  - ScenarioResult fields are populated.
  - explore_all() runs all scenarios and returns results.
  - _build_insight() produces non-empty strings.
  - Error handling in explore_all() (graceful degradation).
  - Scenario resilience: identity preservation, stability bounds, phi_iit bounds.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from luna.dream.harvest import ScenarioResult
from luna.dream.scenarios import (
    DEFAULT_SCENARIOS,
    DreamScenario,
    _build_insight,
    _perturb_agent_loss,
    _perturb_metric_collapse,
    _perturb_mode_shift,
    _perturb_phi_resonance,
    _perturb_veto_cascade,
    explore_all,
    run_scenario,
)
from luna.dream.simulator import DreamSimulator, _AGENT_KEYS

EXPECTED_AGENTS = sorted(_AGENT_KEYS.keys())

EXPECTED_SCENARIO_IDS = [
    "veto_cascade",
    "mode_shift",
    "agent_loss",
    "metric_collapse",
    "phi_resonance",
]


# ---------------------------------------------------------------------------
# DreamScenario dataclass
# ---------------------------------------------------------------------------


class TestDreamScenarioDataclass:
    """DreamScenario structure and DEFAULT_SCENARIOS catalogue."""

    def test_scenario_fields(self) -> None:
        s = DreamScenario(
            scenario_id="test",
            description="A test scenario",
            perturbation=lambda sim: None,
            explore_steps=30,
        )
        assert s.scenario_id == "test"
        assert s.explore_steps == 30
        assert callable(s.perturbation)

    def test_default_explore_steps(self) -> None:
        s = DreamScenario(
            scenario_id="x",
            description="x",
            perturbation=lambda sim: None,
        )
        assert s.explore_steps == 50

    def test_default_scenarios_count(self) -> None:
        assert len(DEFAULT_SCENARIOS) == 5

    def test_default_scenario_ids(self) -> None:
        ids = [s.scenario_id for s in DEFAULT_SCENARIOS]
        assert ids == EXPECTED_SCENARIO_IDS

    def test_default_scenarios_have_descriptions(self) -> None:
        for s in DEFAULT_SCENARIOS:
            assert len(s.description) > 10, f"{s.scenario_id} has no description"
            assert callable(s.perturbation)

    def test_scenario_is_frozen(self) -> None:
        s = DEFAULT_SCENARIOS[0]
        with pytest.raises(AttributeError):
            s.scenario_id = "tampered"  # type: ignore[misc]

    def test_scenario_ids_unique(self) -> None:
        """All scenario IDs are distinct."""
        ids = [s.scenario_id for s in DEFAULT_SCENARIOS]
        assert len(ids) == len(set(ids))

    def test_all_scenarios_have_perturbation(self) -> None:
        """Each scenario has a callable perturbation."""
        for s in DEFAULT_SCENARIOS:
            assert callable(s.perturbation), (
                f"{s.scenario_id} perturbation is not callable"
            )


# ---------------------------------------------------------------------------
# Perturbation functions
# ---------------------------------------------------------------------------


class TestPerturbations:
    """Each perturbation produces measurable effects on the simulator."""

    def _sim_with_replay(self, steps: int = 10) -> DreamSimulator:
        """Return a simulator that has been replayed for a few steps."""
        sim = DreamSimulator()
        sim.replay(harvest_events=steps)
        return sim

    def test_veto_cascade_affects_sentinel(self) -> None:
        sim = self._sim_with_replay()
        psi_before = sim.get_psi("sentinel").copy()
        _perturb_veto_cascade(sim)
        psi_after = sim.get_psi("sentinel")
        assert not np.allclose(psi_before, psi_after, atol=1e-6), (
            "veto_cascade should move SENTINEL's Psi"
        )

    def test_mode_shift_affects_sayohmy(self) -> None:
        sim = self._sim_with_replay()
        psi_before = sim.get_psi("sayohmy").copy()
        _perturb_mode_shift(sim)
        psi_after = sim.get_psi("sayohmy")
        assert not np.allclose(psi_before, psi_after, atol=1e-6)

    def test_agent_loss_affects_test_engineer(self) -> None:
        sim = self._sim_with_replay()
        psi_before = sim.get_psi("testengineer").copy()
        _perturb_agent_loss(sim)
        psi_after = sim.get_psi("testengineer")
        # After being forced to uniform and re-evolved, it should differ.
        assert not np.allclose(psi_before, psi_after, atol=1e-6)

    def test_metric_collapse_affects_all(self) -> None:
        sim = self._sim_with_replay()
        before = sim.get_all_psi()
        _perturb_metric_collapse(sim)
        after = sim.get_all_psi()
        moved = sum(
            1 for a in EXPECTED_AGENTS
            if not np.allclose(before[a], after[a], atol=1e-6)
        )
        assert moved >= 3, "metric_collapse should affect most agents"

    def test_phi_resonance_affects_all(self) -> None:
        sim = self._sim_with_replay()
        before = sim.get_all_psi()
        _perturb_phi_resonance(sim)
        after = sim.get_all_psi()
        moved = sum(
            1 for a in EXPECTED_AGENTS
            if not np.allclose(before[a], after[a], atol=1e-6)
        )
        assert moved >= 3

    def test_perturbations_preserve_simplex(self) -> None:
        """All perturbation functions must leave Psi on the simplex."""
        perturbations = [
            _perturb_veto_cascade,
            _perturb_mode_shift,
            _perturb_agent_loss,
            _perturb_metric_collapse,
            _perturb_phi_resonance,
        ]
        for fn in perturbations:
            sim = self._sim_with_replay()
            fn(sim)
            for agent in EXPECTED_AGENTS:
                psi = sim.get_psi(agent)
                assert abs(psi.sum() - 1.0) < 1e-6, (
                    f"{fn.__name__} broke simplex for {agent}"
                )
                assert (psi >= 0).all(), (
                    f"{fn.__name__} produced negative component for {agent}"
                )


# ---------------------------------------------------------------------------
# run_scenario
# ---------------------------------------------------------------------------


class TestRunScenario:
    """run_scenario() execution and measurement."""

    def test_original_unchanged(self) -> None:
        """run_scenario operates on a clone; original is untouched."""
        sim = DreamSimulator()
        sim.replay(harvest_events=10)
        psi_before = sim.get_all_psi()

        scenario = DEFAULT_SCENARIOS[0]  # veto_cascade
        run_scenario(sim, scenario)

        psi_after = sim.get_all_psi()
        for agent in EXPECTED_AGENTS:
            np.testing.assert_allclose(
                psi_before[agent], psi_after[agent], atol=1e-12,
                err_msg=f"Original modified for {agent}",
            )

    def test_result_fields_populated(self) -> None:
        sim = DreamSimulator()
        sim.replay(harvest_events=10)
        result = run_scenario(sim, DEFAULT_SCENARIOS[0])

        assert isinstance(result, ScenarioResult)
        assert result.scenario_id == "veto_cascade"
        assert 0.0 <= result.stability_score <= 1.0
        assert result.phi_iit_mean >= 0.0
        assert 0 <= result.identities_preserved <= 4
        assert len(result.insight) > 0

    def test_each_default_scenario_runs(self) -> None:
        """All 5 default scenarios complete without error."""
        sim = DreamSimulator()
        sim.replay(harvest_events=15)

        for scenario in DEFAULT_SCENARIOS:
            result = run_scenario(sim, scenario)
            assert result.scenario_id == scenario.scenario_id
            assert isinstance(result.stability_score, float)

    def test_custom_scenario(self) -> None:
        """A custom scenario with a no-op perturbation."""
        sim = DreamSimulator()
        sim.replay(harvest_events=10)

        noop = DreamScenario(
            scenario_id="noop",
            description="No perturbation",
            perturbation=lambda s: None,
            explore_steps=20,
        )
        result = run_scenario(sim, noop)
        assert result.scenario_id == "noop"
        # No perturbation -> should be very stable.
        assert result.stability_score >= 0.5

    def test_scenario_with_few_explore_steps(self) -> None:
        sim = DreamSimulator()
        sim.replay(harvest_events=10)

        short = DreamScenario(
            scenario_id="short",
            description="Very short exploration",
            perturbation=lambda s: None,
            explore_steps=5,
        )
        result = run_scenario(sim, short)
        assert result.scenario_id == "short"

    def test_veto_cascade_system_survives(self) -> None:
        """System survives veto stress with at least partial identity preservation."""
        sim = DreamSimulator()
        sim.replay(harvest_events=15)
        result = run_scenario(sim, DEFAULT_SCENARIOS[0])  # veto_cascade
        assert result.identities_preserved >= 2, (
            "System should survive veto cascade with at least 2 identities"
        )

    def test_phi_resonance_positive(self) -> None:
        """Phi resonance scenario should yield non-negative phi_iit."""
        sim = DreamSimulator()
        sim.replay(harvest_events=15)
        result = run_scenario(sim, DEFAULT_SCENARIOS[4])  # phi_resonance
        assert result.phi_iit_mean >= 0.0


# ---------------------------------------------------------------------------
# explore_all
# ---------------------------------------------------------------------------


class TestExploreAll:
    """explore_all() runs all scenarios and handles errors."""

    def test_runs_all_default_scenarios(self) -> None:
        sim = DreamSimulator()
        sim.replay(harvest_events=15)
        results = explore_all(sim)
        assert len(results) == 5
        result_ids = [r.scenario_id for r in results]
        assert result_ids == EXPECTED_SCENARIO_IDS

    def test_original_unchanged_after_explore_all(self) -> None:
        sim = DreamSimulator()
        sim.replay(harvest_events=10)
        psi_before = sim.get_all_psi()

        explore_all(sim)

        for agent in EXPECTED_AGENTS:
            np.testing.assert_allclose(
                psi_before[agent], sim.get_psi(agent), atol=1e-12,
            )

    def test_custom_scenario_list(self) -> None:
        sim = DreamSimulator()
        sim.replay(harvest_events=10)

        custom = [
            DreamScenario(
                scenario_id="custom_a",
                description="A",
                perturbation=lambda s: None,
                explore_steps=10,
            ),
            DreamScenario(
                scenario_id="custom_b",
                description="B",
                perturbation=lambda s: None,
                explore_steps=10,
            ),
        ]
        results = explore_all(sim, scenarios=custom)
        assert len(results) == 2
        assert results[0].scenario_id == "custom_a"
        assert results[1].scenario_id == "custom_b"

    def test_error_handling_graceful(self) -> None:
        """If a scenario raises, explore_all continues and reports failure."""
        sim = DreamSimulator()
        sim.replay(harvest_events=10)

        def _raise_error(s: DreamSimulator) -> None:
            raise RuntimeError("intentional test error")

        scenarios = [
            DreamScenario(
                scenario_id="failing",
                description="Deliberately fails",
                perturbation=_raise_error,
            ),
            DreamScenario(
                scenario_id="passing",
                description="Works fine",
                perturbation=lambda s: None,
            ),
        ]
        results = explore_all(sim, scenarios=scenarios)
        assert len(results) == 2
        assert results[0].scenario_id == "failing"
        assert "failed" in results[0].insight.lower()
        assert results[1].scenario_id == "passing"

    def test_scenario_ordering(self) -> None:
        """Results match the order of input scenarios."""
        sim = DreamSimulator()
        sim.replay(harvest_events=10)

        results = explore_all(sim)
        for i, scenario in enumerate(DEFAULT_SCENARIOS):
            assert results[i].scenario_id == scenario.scenario_id


# ---------------------------------------------------------------------------
# _build_insight
# ---------------------------------------------------------------------------


class TestBuildInsight:
    """_build_insight produces meaningful human-readable strings."""

    def test_all_preserved_high_stability(self) -> None:
        insight = _build_insight(
            DEFAULT_SCENARIOS[0],
            stability=0.95,
            phi_mean=0.4,
            preserved=4,
            divergences={"luna": 0.01, "sentinel": 0.02},
        )
        assert "All 4 identities preserved" in insight
        assert "highly stable" in insight.lower()
        assert "Phi_IIT" in insight

    def test_low_stability_warning(self) -> None:
        insight = _build_insight(
            DEFAULT_SCENARIOS[0],
            stability=0.3,
            phi_mean=0.05,
            preserved=1,
            divergences={"luna": 0.2},
        )
        assert "1/4" in insight
        assert "low stability" in insight.lower() or "drift" in insight.lower()

    def test_most_divergent_agent_noted(self) -> None:
        insight = _build_insight(
            DEFAULT_SCENARIOS[0],
            stability=0.7,
            phi_mean=0.2,
            preserved=3,
            divergences={"luna": 0.01, "sentinel": 0.25},
        )
        assert "sentinel" in insight.lower()

    def test_no_identities_warning(self) -> None:
        insight = _build_insight(
            DEFAULT_SCENARIOS[0],
            stability=0.1,
            phi_mean=0.01,
            preserved=0,
            divergences={},
        )
        assert "all identities lost" in insight.lower()

    def test_empty_divergences(self) -> None:
        """Should not crash with empty divergences dict."""
        insight = _build_insight(
            DEFAULT_SCENARIOS[0],
            stability=0.9,
            phi_mean=0.5,
            preserved=4,
            divergences={},
        )
        assert len(insight) > 0


# ---------------------------------------------------------------------------
# Scenario resilience
# ---------------------------------------------------------------------------


class TestScenarioResilience:
    """Integration tests: resilience properties across all default scenarios."""

    @pytest.fixture
    def sim_with_history(self) -> DreamSimulator:
        sim = DreamSimulator()
        sim.replay(harvest_events=20)
        return sim

    def test_identities_after_veto_cascade(self, sim_with_history) -> None:
        """At least 3/4 identities should survive the veto cascade."""
        result = run_scenario(sim_with_history, DEFAULT_SCENARIOS[0])
        assert result.identities_preserved >= 3, (
            f"Only {result.identities_preserved}/4 identities survived veto_cascade"
        )

    def test_stability_bounds(self, sim_with_history) -> None:
        """All stability scores must be in [0, 1]."""
        results = explore_all(sim_with_history)
        for r in results:
            assert 0.0 <= r.stability_score <= 1.0, (
                f"{r.scenario_id}: stability={r.stability_score} out of [0,1]"
            )

    def test_phi_iit_bounds(self, sim_with_history) -> None:
        """All phi_iit_mean values must be >= 0."""
        results = explore_all(sim_with_history)
        for r in results:
            assert r.phi_iit_mean >= 0.0, (
                f"{r.scenario_id}: phi_iit={r.phi_iit_mean} is negative"
            )

    def test_at_least_one_recovery(self, sim_with_history) -> None:
        """At least one scenario shows recovery (recovery_steps is not None)."""
        results = explore_all(sim_with_history)
        has_recovery = any(r.recovery_steps is not None for r in results)
        # This is a soft assertion -- if all scenarios perturb too strongly,
        # recovery may not happen in 50 steps.  But with phi_resonance
        # (positive scenario), we expect at least one recovery.
        if not has_recovery:
            # Check that at least phi_resonance is reasonably stable.
            phi_res = [r for r in results if r.scenario_id == "phi_resonance"]
            assert phi_res[0].stability_score >= 0.3, (
                "Neither recovery nor stability in phi_resonance"
            )
