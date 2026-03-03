"""Dream exploration scenarios -- hypothetical perturbations for resilience testing.

Each scenario perturbs the DreamSimulator state and runs N steps to observe
the system's response.  Scenarios always operate on CLONES of the simulator,
never on real state.

The 5 default scenarios probe different failure modes:
  1. veto_cascade    -- sustained veto stress on SENTINEL
  2. mode_shift      -- SayOhMy perception overload (Virtuose -> Debugger)
  3. agent_loss      -- Test-Engineer goes offline
  4. metric_collapse -- coverage/phi dimension crash
  5. phi_resonance   -- positive resonance seeking high Phi_IIT
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

import numpy as np

from luna_common.constants import DIM, PHI2, DREAM_EXPLORE_STEPS_FACTOR
from luna.dream.harvest import ScenarioResult

if TYPE_CHECKING:
    from luna.dream.simulator import DreamSimulator

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scenario descriptor
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class DreamScenario:
    """A hypothetical scenario to simulate in dream space.

    Attributes:
        scenario_id:   Unique identifier for this scenario.
        description:   Human-readable explanation of the perturbation.
        perturbation:  Callable that receives a DreamSimulator (already a
                       clone) and applies the perturbation in-place.
        explore_steps: Number of evolution steps to run after perturbation.
    """

    scenario_id: str
    description: str
    perturbation: Callable[..., None]
    explore_steps: int = 50


# ---------------------------------------------------------------------------
# Perturbation functions
# ---------------------------------------------------------------------------

def _perturb_veto_cascade(sim: DreamSimulator) -> None:
    """Inject 3 consecutive strong negative info_deltas into SENTINEL.

    Simulates sustained veto stress: the perception-dominant agent receives
    repeated negative signals in its dominant dimension (index 0 = perception)
    and in the integration dimension (index 2), mimicking a cascade of
    vetoed operations.
    """
    veto_deltas: dict[str, list[float]] = {
        "sentinel": [-0.5, 0.0, -0.3, 0.0],
    }
    for _ in range(3):
        sim.step(info_deltas=veto_deltas)


def _perturb_mode_shift(sim: DreamSimulator) -> None:
    """Shift SayOhMy toward perception-heavy profile.

    Simulates a mode change from Virtuose (expression-dominant) to Debugger
    (perception-heavy) by injecting strong positive perception deltas and
    negative expression deltas over 5 steps.
    """
    shift_deltas: dict[str, list[float]] = {
        "sayohmy": [0.4, 0.0, 0.0, -0.4],
    }
    for _ in range(5):
        sim.step(info_deltas=shift_deltas)


def _perturb_agent_loss(sim: DreamSimulator) -> None:
    """Zero out Test-Engineer's contribution for several steps.

    Simulates the Test-Engineer agent going offline: its Psi is forced to
    uniform distribution (no signal), removing its integration-dominant
    influence from the spatial coupling.
    """
    uniform = np.ones(DIM, dtype=np.float64) / DIM
    # Force Test-Engineer to uniform for 10 steps.
    for _ in range(10):
        # Override the agent's state before each step.
        sim._psi["testengineer"] = uniform.copy()
        sim.step()


def _perturb_metric_collapse(sim: DreamSimulator) -> None:
    """Inject strong negative info_deltas in phi/coverage dimensions.

    Simulates a sudden coverage crash: the informational gradient drives
    all agents toward negative phi (index 1) and negative integration
    (index 2), as if test coverage and code quality collapsed simultaneously.
    """
    collapse_deltas: dict[str, list[float]] = {
        agent_id: [0.0, -0.6, -0.6, 0.0]
        for agent_id in ("luna", "sayohmy", "sentinel", "testengineer")
    }
    for _ in range(3):
        sim.step(info_deltas=collapse_deltas)


def _perturb_phi_resonance(sim: DreamSimulator) -> None:
    """Inject positive deltas in all dimensions seeking high Phi_IIT.

    Simulates an ideal scenario where all metrics improve simultaneously.
    The deltas are tuned to create inter-agent resonance: each agent
    receives positive signal in its dominant dimension, amplifying its
    natural profile while coupling it with the others.
    """
    # Each agent gets a boost in its dominant dimension.
    resonance_deltas: dict[str, list[float]] = {
        "luna":          [0.1, 0.3, 0.1, 0.05],   # reflexion boost
        "sayohmy":       [0.05, 0.05, 0.1, 0.3],  # expression boost
        "sentinel":      [0.3, 0.1, 0.1, 0.05],   # perception boost
        "testengineer": [0.05, 0.1, 0.3, 0.05],  # integration boost
    }
    for _ in range(5):
        sim.step(info_deltas=resonance_deltas)


# ---------------------------------------------------------------------------
# Default scenario catalogue
# ---------------------------------------------------------------------------

DEFAULT_SCENARIOS: list[DreamScenario] = [
    DreamScenario(
        scenario_id="veto_cascade",
        description=(
            "3 consecutive negative info_deltas on SENTINEL's perception "
            "and integration dimensions, simulating sustained veto stress."
        ),
        perturbation=_perturb_veto_cascade,
        explore_steps=50,
    ),
    DreamScenario(
        scenario_id="mode_shift",
        description=(
            "Shift SayOhMy from expression-dominant (Virtuose) toward "
            "perception-heavy (Debugger) over 5 steps."
        ),
        perturbation=_perturb_mode_shift,
        explore_steps=50,
    ),
    DreamScenario(
        scenario_id="agent_loss",
        description=(
            "Test-Engineer goes offline: forced to uniform distribution "
            "for 10 steps, removing integration-dominant coupling."
        ),
        perturbation=_perturb_agent_loss,
        explore_steps=50,
    ),
    DreamScenario(
        scenario_id="metric_collapse",
        description=(
            "Sudden coverage crash: strong negative info_deltas in phi "
            "and integration dimensions for all agents over 3 steps."
        ),
        perturbation=_perturb_metric_collapse,
        explore_steps=50,
    ),
    DreamScenario(
        scenario_id="phi_resonance",
        description=(
            "Positive resonance: each agent receives a boost in its "
            "dominant dimension over 5 steps, seeking high Phi_IIT."
        ),
        perturbation=_perturb_phi_resonance,
        explore_steps=50,
    ),
]


# ---------------------------------------------------------------------------
# Scenario execution
# ---------------------------------------------------------------------------

def run_scenario(
    simulator: DreamSimulator,
    scenario: DreamScenario,
) -> ScenarioResult:
    """Run a scenario on a CLONE of the simulator, measure the outcome.

    The original simulator is never modified.

    Steps:
      1. Clone the simulator.
      2. Apply the perturbation (may run several internal steps).
      3. Run ``scenario.explore_steps`` additional evolution steps.
      4. Measure stability, Phi_IIT, identity preservation, recovery.

    Args:
        simulator: The base simulator (not modified).
        scenario:  The scenario descriptor.

    Returns:
        A frozen ``ScenarioResult`` with diagnostics.
    """
    clone = simulator.clone()

    # Capture pre-perturbation state for recovery measurement.
    pre_psi = clone.get_all_psi()

    # Phase A: apply perturbation (may run internal steps).
    scenario.perturbation(clone)

    # Phase B: run exploration steps and track Phi_IIT.
    phi_trajectory: list[float] = []
    for _ in range(scenario.explore_steps):
        clone.step()
        phi_trajectory.append(clone.compute_mean_phi_iit(window=20))

    # -- Measurements --

    # Stability: how much variance in the trajectory?
    stability = clone.stability_score(window=min(20, scenario.explore_steps))

    # Mean Phi_IIT over the exploration window.
    phi_mean = float(np.mean(phi_trajectory)) if phi_trajectory else 0.0

    # Identity preservation: how many agents kept their dominant component?
    preserved = clone.identities_preserved()

    # Recovery: find the first step where divergence from pre-perturbation
    # state drops below a threshold.  None = did not recover.
    recovery_steps: int | None = None
    divergences = clone.measure_divergence()
    mean_divergence = float(np.mean(list(divergences.values())))
    if mean_divergence < 0.05:
        # System is close to pre-perturbation -- estimate recovery step.
        # Rough heuristic: if final state is close, assume recovery happened
        # at roughly the midpoint of exploration.
        recovery_steps = scenario.explore_steps // 2

    # Build insight string.
    insight = _build_insight(scenario, stability, phi_mean, preserved, divergences)

    return ScenarioResult(
        scenario_id=scenario.scenario_id,
        stability_score=round(stability, 4),
        phi_iit_mean=round(phi_mean, 4),
        identities_preserved=preserved,
        recovery_steps=recovery_steps,
        insight=insight,
    )


def explore_all(
    simulator: DreamSimulator,
    scenarios: list[DreamScenario] | None = None,
) -> list[ScenarioResult]:
    """Run all scenarios and return sorted results.

    Args:
        simulator: The base simulator (not modified).
        scenarios: Optional custom list.  Defaults to ``DEFAULT_SCENARIOS``.

    Returns:
        List of ``ScenarioResult``, one per scenario.
    """
    if scenarios is None:
        scenarios = DEFAULT_SCENARIOS

    results: list[ScenarioResult] = []
    for scenario in scenarios:
        try:
            result = run_scenario(simulator, scenario)
            results.append(result)
            log.info(
                "Scenario '%s': stability=%.3f  phi_iit=%.3f  preserved=%d/4",
                scenario.scenario_id,
                result.stability_score,
                result.phi_iit_mean,
                result.identities_preserved,
            )
        except Exception:
            log.warning(
                "Scenario '%s' failed",
                scenario.scenario_id,
                exc_info=True,
            )
            results.append(ScenarioResult(
                scenario_id=scenario.scenario_id,
                insight="Scenario execution failed.",
            ))

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_insight(
    scenario: DreamScenario,
    stability: float,
    phi_mean: float,
    preserved: int,
    divergences: dict[str, float],
) -> str:
    """Build a human-readable insight string from scenario results."""
    parts: list[str] = []

    if preserved == 4:
        parts.append("All 4 identities preserved.")
    elif preserved == 0:
        parts.append("WARNING: all identities lost.")
    else:
        parts.append(f"{preserved}/4 identities preserved.")

    if stability > 0.8:
        parts.append("System highly stable.")
    elif stability > 0.5:
        parts.append("Moderate stability.")
    else:
        parts.append("Low stability -- significant drift observed.")

    if phi_mean > 0.3:
        parts.append(f"Strong Phi_IIT resonance ({phi_mean:.3f}).")
    elif phi_mean > 0.1:
        parts.append(f"Moderate Phi_IIT ({phi_mean:.3f}).")
    else:
        parts.append(f"Weak Phi_IIT ({phi_mean:.3f}).")

    # Note the most divergent agent.
    if divergences:
        most_divergent = max(divergences, key=divergences.get)  # type: ignore[arg-type]
        max_div = divergences[most_divergent]
        if max_div > 0.1:
            parts.append(
                f"Most affected agent: {most_divergent} "
                f"(divergence={max_div:.3f})."
            )

    return " ".join(parts)
