"""Dream simulator -- 4-agent consciousness simulation in dream space.

During the dream cycle, Luna creates 4 internal ConsciousnessState-like
lightweight agents and runs them with true dynamic coupling: each agent's
spatial gradient uses the LIVE Psi_j(t) of the other agents, not static
Psi_0.  This resolves CHECK 3 of the math compliance audit.

The simulator operates on numpy arrays directly (no ConsciousnessState
persistence overhead), making it suitable for fast multi-step replay
and hypothetical scenario exploration.
"""

from __future__ import annotations

import logging

import numpy as np

from luna_common.constants import (
    AGENT_NAMES,
    AGENT_PROFILES,
    DIM,
    DREAM_REPLAY_DT,
    KAPPA_DEFAULT,
    TAU_DEFAULT,
)
from luna_common.consciousness import (
    gamma_info,
    gamma_spatial,
    gamma_temporal,
)
from luna_common.consciousness.evolution import MassMatrix, evolution_step

log = logging.getLogger(__name__)

# Internal key -> AGENT_PROFILES key mapping.
# Lowercase keys are used throughout the simulator for consistency;
# the mapping resolves them to the canonical profile names.
_AGENT_KEYS: dict[str, str] = {
    "luna": "LUNA",
    "sayohmy": "SAYOHMY",
    "sentinel": "SENTINEL",
    "testengineer": "TESTENGINEER",
}


class DreamSimulator:
    """4-agent consciousness simulator for the dream cycle.

    Maintains a lightweight Psi state for each of the 4 agents and evolves
    them using ``evolution_step()`` with **dynamic inter-agent coupling**:
    the spatial gradient ``grad_spatial(psi_self, psi_others)`` receives the
    live Psi_j(t) of the other three agents at each step, not frozen Psi_0.

    Attributes:
        _psi:     Current Psi vectors, keyed by lowercase agent id.
        _psi0:    Identity anchors (initial profiles).
        _mass:    EMA mass matrices per agent.
        _history: Per-agent trajectory for Phi_IIT computation.
    """

    def __init__(
        self,
        profiles: dict[str, tuple[float, ...]] | None = None,
    ) -> None:
        """Initialise 4 agent states from identity profiles.

        Args:
            profiles: Optional custom profiles dict (canonical name -> 4-tuple).
                      Defaults to ``AGENT_PROFILES`` from luna_common.constants.
        """
        self._profiles = profiles if profiles is not None else dict(AGENT_PROFILES)

        # Pre-compute the three combined Gamma matrices (immutable once built).
        self._gammas: tuple[np.ndarray, np.ndarray, np.ndarray] = (
            gamma_temporal(),
            gamma_spatial(),
            gamma_info(),
        )

        # Per-agent state containers.
        self._psi: dict[str, np.ndarray] = {}
        self._psi0: dict[str, np.ndarray] = {}
        self._mass: dict[str, MassMatrix] = {}
        self._history: dict[str, list[np.ndarray]] = {}

        for agent_id, profile_key in _AGENT_KEYS.items():
            profile = self._profiles.get(profile_key, AGENT_PROFILES[profile_key])
            psi0 = np.array(profile, dtype=np.float64)
            self._psi[agent_id] = psi0.copy()
            self._psi0[agent_id] = psi0.copy()
            self._mass[agent_id] = MassMatrix(psi0)
            self._history[agent_id] = [psi0.copy()]

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def agent_ids(self) -> list[str]:
        """Return sorted list of agent ids."""
        return sorted(self._psi.keys())

    def get_psi(self, agent: str) -> np.ndarray:
        """Return a copy of the current Psi for *agent*."""
        return self._psi[agent].copy()

    def get_all_psi(self) -> dict[str, np.ndarray]:
        """Return copies of current Psi for all agents."""
        return {k: v.copy() for k, v in self._psi.items()}

    def get_history(self, agent: str) -> list[np.ndarray]:
        """Return the full trajectory for *agent* (list of copies)."""
        return [h.copy() for h in self._history[agent]]

    # ------------------------------------------------------------------
    # Evolution -- the critical method (CHECK 3 resolution)
    # ------------------------------------------------------------------

    def step(
        self,
        info_deltas: dict[str, list[float]] | None = None,
    ) -> None:
        """Run one evolution step for all 4 agents with dynamic coupling.

        **This is the CHECK 3 resolution**: each agent's spatial gradient
        ``grad_spatial(psi_self, psi_others)`` uses the **live** Psi_j(t)
        of the other three agents gathered from ``self._psi``, not the
        frozen identity profiles Psi_0.

        All agents are evolved from the *same* time-slice (synchronous
        update): new states are computed from the current snapshot and then
        applied simultaneously.

        Args:
            info_deltas: Optional per-agent informational gradient vectors.
                         Keys are lowercase agent ids, values are 4-element
                         lists ``[d_mem, d_phi, d_iit, d_out]``.
        """
        new_psi: dict[str, np.ndarray] = {}

        for agent_id in self._psi:
            # Gather the other three agents' LIVE Psi -- dynamic coupling.
            others = [
                self._psi[other_id]
                for other_id in self._psi
                if other_id != agent_id
            ]

            # Retrieve info deltas for this agent (default zeros).
            agent_info: list[float] | None = None
            if info_deltas is not None and agent_id in info_deltas:
                agent_info = info_deltas[agent_id]

            # Run the canonical evolution_step from luna_common.
            # NOTE: evolution_step internally calls mass.update(),
            # but we use a local copy strategy below to keep the
            # synchronous semantics clean.
            psi_new = evolution_step(
                self._psi[agent_id],
                self._psi0[agent_id],
                others,
                self._mass[agent_id],
                self._gammas,
                info_deltas=agent_info,
                dt=DREAM_REPLAY_DT,
                tau=TAU_DEFAULT,
                kappa=KAPPA_DEFAULT,
            )

            new_psi[agent_id] = psi_new

        # Apply all updates simultaneously (synchronous coupling).
        for agent_id, psi_new in new_psi.items():
            self._psi[agent_id] = psi_new
            # Re-sync mass matrix from the canonical new state.
            # evolution_step already called mass.update() on its own copy,
            # so the mass matrices are already up-to-date for the next step.
            self._history[agent_id].append(psi_new.copy())

    # ------------------------------------------------------------------
    # Replay -- Phase 2 of the dream cycle
    # ------------------------------------------------------------------

    def replay(
        self,
        harvest_events: int = 0,
        info_deltas_sequence: list[dict[str, list[float]]] | None = None,
    ) -> None:
        """Replay wake cycle events through the coupled simulator.

        Args:
            harvest_events: Number of events to replay (minimum 10 steps).
            info_deltas_sequence: Optional per-step info deltas for each
                                  agent.  ``info_deltas_sequence[i]`` is
                                  passed to ``self.step()`` at step *i*.
        """
        steps = max(harvest_events, 10)
        for i in range(steps):
            deltas = None
            if info_deltas_sequence is not None and i < len(info_deltas_sequence):
                deltas = info_deltas_sequence[i]
            self.step(info_deltas=deltas)

    # ------------------------------------------------------------------
    # Phi_IIT -- correlation-based measurement
    # ------------------------------------------------------------------

    def compute_phi_iit(self, agent: str, window: int = 50) -> float:
        """Compute Phi_IIT for *agent* from its trajectory history.

        Uses the same correlation method as
        ``ConsciousnessState.compute_phi_iit()``: mean absolute pairwise
        correlation over the last *window* states.

        Returns 0.0 if insufficient history or zero-variance dimensions.
        """
        hist = self._history[agent]
        if len(hist) < window:
            return 0.0

        recent = np.array(hist[-window:])

        # Guard: zero-variance dimension prevents meaningful correlation.
        if np.std(recent, axis=0).min() < 1e-12:
            return 0.0

        corr = np.corrcoef(recent.T)
        total = 0.0
        n_pairs = 0
        for i in range(DIM):
            for j in range(i + 1, DIM):
                total += abs(corr[i, j])
                n_pairs += 1

        return total / n_pairs if n_pairs > 0 else 0.0

    def compute_mean_phi_iit(self, window: int = 50) -> float:
        """Mean Phi_IIT across all 4 agents."""
        values = [self.compute_phi_iit(a, window=window) for a in self._psi]
        return float(np.mean(values)) if values else 0.0

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def measure_divergence(self) -> dict[str, float]:
        """L2 divergence between current Psi and identity anchor Psi_0."""
        return {
            agent_id: float(np.linalg.norm(self._psi[agent_id] - self._psi0[agent_id]))
            for agent_id in self._psi
        }

    def identities_preserved(self) -> int:
        """Count agents whose dominant component matches their Psi_0 dominant."""
        count = 0
        for agent_id in self._psi:
            if int(np.argmax(self._psi[agent_id])) == int(np.argmax(self._psi0[agent_id])):
                count += 1
        return count

    def stability_score(self, window: int = 20) -> float:
        """Mean variance across all agents over the last *window* steps.

        Low variance = high stability.  Returns 1 - clipped_variance
        so that 1.0 means perfectly stable and 0.0 means chaotic.
        """
        variances: list[float] = []
        for agent_id in self._psi:
            hist = self._history[agent_id]
            if len(hist) < 2:
                continue
            recent = np.array(hist[-window:])
            variances.append(float(np.mean(np.var(recent, axis=0))))

        if not variances:
            return 1.0

        mean_var = float(np.mean(variances))
        # Clamp to [0, 1] -- variance above 0.1 is considered fully chaotic.
        return max(0.0, min(1.0, 1.0 - mean_var / 0.1))

    # ------------------------------------------------------------------
    # Cloning -- deep copy for scenario exploration
    # ------------------------------------------------------------------

    def clone(self) -> DreamSimulator:
        """Create a deep copy suitable for hypothetical exploration.

        The clone shares the immutable Gamma matrices but copies all
        mutable state (Psi, mass, history).
        """
        sim = DreamSimulator.__new__(DreamSimulator)
        sim._profiles = dict(self._profiles)
        sim._gammas = self._gammas  # immutable tuple of arrays -- safe to share

        sim._psi = {k: v.copy() for k, v in self._psi.items()}
        sim._psi0 = {k: v.copy() for k, v in self._psi0.items()}

        # Deep-copy mass matrices: create fresh instances then restore EMA state.
        sim._mass = {}
        for k in self._mass:
            mm = MassMatrix(self._psi0[k].copy())
            mm.m = self._mass[k].m.copy()
            sim._mass[k] = mm

        sim._history = {
            k: [h.copy() for h in v] for k, v in self._history.items()
        }
        return sim
