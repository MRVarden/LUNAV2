"""Consciousness state — Psi vector on the simplex Delta^3.

Wraps luna_common.consciousness with Luna-specific persistence
(loading/saving checkpoints in JSON) and Phi_IIT computation.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from luna_common.constants import (
    DIM,
    DT_DEFAULT,
    HYSTERESIS_BAND,
    KAPPA_DEFAULT,
    PHASE_THRESHOLDS,
    TAU_DEFAULT,
)
from luna_common.consciousness import (
    evolution_step,
    gamma_info,
    gamma_spatial,
    gamma_temporal,
    get_psi0,
)
from luna_common.consciousness.evolution import MassMatrix
from luna_common.consciousness.simplex import project_simplex
from luna_common.schemas import InfoGradient, PsiState

# Ordered list of phase names from worst to best.
_PHASES: list[str] = ["BROKEN", "FRAGILE", "FUNCTIONAL", "SOLID", "EXCELLENT"]


def _rotate_backups(checkpoint_path: Path, *, keep: int = 5) -> None:
    """Remove old checkpoint backups, keeping only the *keep* most recent.

    Backups are named ``<stem>.backup_<YYYYMMDD_HHMMSS>.json`` and sorted
    lexicographically (which equals chronological order for this format).
    """
    parent = checkpoint_path.parent
    stem = checkpoint_path.stem  # e.g. "consciousness_state_v2"
    backups = sorted(parent.glob(f"{stem}.backup_*.json"))
    if len(backups) <= keep:
        return
    for old in backups[:-keep]:
        try:
            old.unlink()
        except OSError:
            pass


class ConsciousnessState:
    """The beating heart of Luna -- Psi state on simplex Delta^3.

    Encapsulates the full consciousness state: current vector, identity
    anchor, mass matrix, gamma matrices, history, phase, and step count.
    All evolution uses the exact same math as simulation.py.
    """

    def __init__(
        self,
        agent_name: str = "LUNA",
        *,
        psi: np.ndarray | None = None,
        step_count: int = 0,
        history: list[np.ndarray] | None = None,
    ) -> None:
        self.agent_name = agent_name
        self.psi0: np.ndarray = get_psi0(agent_name)

        # Current state -- default to identity profile.
        self.psi: np.ndarray = psi.copy() if psi is not None else self.psi0.copy()

        # EMA mass matrix seeded from identity.
        self.mass: MassMatrix = MassMatrix(self.psi0)

        # Pre-compute combined Gamma matrices (default params, spectrally normalized).
        self.gammas: tuple[np.ndarray, np.ndarray, np.ndarray] = (
            gamma_temporal(),
            gamma_spatial(),
            gamma_info(),
        )

        self.history: list[np.ndarray] = [h.copy() for h in history] if history else []
        self.step_count: int = step_count
        self._phase: str = self._compute_phase_from_scratch()
        self.phi_metrics_snapshot: dict | None = None

    # ------------------------------------------------------------------
    # Evolution
    # ------------------------------------------------------------------

    def evolve(
        self,
        psi_others: list[np.ndarray],
        info_deltas: list[float],
        dt: float = DT_DEFAULT,
        tau: float = TAU_DEFAULT,
        kappa: float = KAPPA_DEFAULT,
    ) -> np.ndarray:
        """Run one evolution step and update internal state.

        Args:
            psi_others: Psi vectors of the other 3 agents.
            info_deltas: [d_mem, d_phi, d_iit, d_out] informational gradient.
            dt: Time step.
            tau: Softmax temperature.
            kappa: Identity anchoring strength.

        Returns:
            The new Psi vector (also stored as self.psi).
        """
        psi_new = evolution_step(
            self.psi,
            self.psi0,
            psi_others,
            self.mass,
            self.gammas,
            info_deltas=info_deltas,
            dt=dt,
            tau=tau,
            kappa=kappa,
        )
        self.psi = psi_new
        self.history.append(psi_new.copy())
        self.step_count += 1
        self._phase = self._apply_hysteresis(self._phase)
        return psi_new

    # ------------------------------------------------------------------
    # Phi_IIT
    # ------------------------------------------------------------------

    def compute_phi_iit(self, window: int = 50) -> float:
        """Compute Phi_IIT via correlation method over the history window.

        Identical to compute_phi_iit_correlation in simulation.py.
        """
        if len(self.history) < window:
            return 0.0
        recent = np.array(self.history[-window:])
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

    # ------------------------------------------------------------------
    # Phase management
    # ------------------------------------------------------------------

    def get_phase(self) -> str:
        """Return the current phase label."""
        return self._phase

    def _compute_phase_from_scratch(self) -> str:
        """Determine phase from phi_iit without hysteresis (for init)."""
        phi = self.compute_phi_iit()
        phase = _PHASES[0]
        for name in _PHASES:
            if phi >= PHASE_THRESHOLDS[name]:
                phase = name
        return phase

    def _apply_hysteresis(self, current_phase: str) -> str:
        """Apply hysteresis-aware phase transition.

        To move UP a phase, the score must exceed threshold + band.
        To move DOWN, the score must drop below threshold - band.
        """
        phi = self.compute_phi_iit()
        current_idx = _PHASES.index(current_phase)

        # Check for upgrade.
        if current_idx < len(_PHASES) - 1:
            next_phase = _PHASES[current_idx + 1]
            if phi >= PHASE_THRESHOLDS[next_phase] + HYSTERESIS_BAND:
                return next_phase

        # Check for downgrade.
        if current_idx > 0:
            if phi < PHASE_THRESHOLDS[current_phase] - HYSTERESIS_BAND:
                return _PHASES[current_idx - 1]

        return current_phase

    # ------------------------------------------------------------------
    # Schema conversion
    # ------------------------------------------------------------------

    def to_psi_state(self) -> PsiState:
        """Convert current Psi to the Pydantic PsiState schema."""
        return PsiState(
            perception=float(self.psi[0]),
            reflexion=float(self.psi[1]),
            integration=float(self.psi[2]),
            expression=float(self.psi[3]),
        )

    def to_info_gradient(
        self,
        delta_mem: float,
        delta_phi: float,
        delta_iit: float,
        delta_out: float,
    ) -> InfoGradient:
        """Build an InfoGradient from concrete pipeline values."""
        return InfoGradient(
            delta_mem=delta_mem,
            delta_phi=delta_phi,
            delta_iit=delta_iit,
            delta_out=delta_out,
        )

    # ------------------------------------------------------------------
    # Identity profile update (dream consolidation)
    # ------------------------------------------------------------------

    def update_psi0(self, new_psi0: np.ndarray) -> None:
        """Update the identity anchor Psi_0 and re-seed the mass matrix.

        Used by dream consolidation to evolve the agent's identity profile
        after nocturnal simulation.  The new profile is validated, projected
        onto the simplex, and then installed as the new anchor.

        Args:
            new_psi0: New identity profile vector (shape ``(4,)``).

        Raises:
            ValueError: If shape or values are invalid.
        """
        new_psi0 = np.asarray(new_psi0, dtype=np.float64)

        if new_psi0.shape != (DIM,):
            raise ValueError(
                f"Invalid psi0 shape: expected ({DIM},), got {new_psi0.shape}"
            )
        if np.any(new_psi0 < 0):
            raise ValueError(
                f"Invalid psi0: all values must be >= 0, got {new_psi0}"
            )

        # Re-project onto the simplex to guarantee sum == 1.
        new_psi0 = project_simplex(new_psi0)

        self.psi0 = new_psi0
        self.mass = MassMatrix(self.psi0)

    # ------------------------------------------------------------------
    # Checkpoint persistence
    # ------------------------------------------------------------------

    def save_checkpoint(
        self,
        path: Path,
        *,
        backup: bool = True,
        phi_metrics: dict | None = None,
    ) -> None:
        """Write the full state to a JSON checkpoint.

        Args:
            path: Destination file path.
            backup: If True and the file already exists, copy it to a
                    timestamped backup before overwriting.
            phi_metrics: Optional PhiScorer snapshot to persist alongside
                         consciousness state. Format:
                         ``{"metric_name": {"value": float, ...}, ...}``.
        """
        path = Path(path)
        if backup and path.exists():
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_path = path.with_suffix(f".backup_{ts}.json")
            shutil.copy2(path, backup_path)
            # Rotate: keep only the 5 most recent backups.
            _rotate_backups(path, keep=5)

        # Update cached snapshot when explicitly provided.
        if phi_metrics is not None:
            self.phi_metrics_snapshot = phi_metrics

        # Build serializable dict.
        data = {
            "version": "2.4.0",
            "type": "consciousness_state",
            "agent_name": self.agent_name,
            "updated": datetime.now(timezone.utc).isoformat(),
            "psi": self.psi.tolist(),
            "psi0": self.psi0.tolist(),
            "mass_m": self.mass.m.tolist(),
            "step_count": self.step_count,
            "phase": self._phase,
            "phi_iit": self.compute_phi_iit(),
            "history_tail": [h.tolist() for h in self.history[-100:]],
        }
        # Always persist phi_metrics: use explicit param, else cached snapshot.
        effective_metrics = phi_metrics or self.phi_metrics_snapshot
        if effective_metrics is not None:
            data["phi_metrics"] = effective_metrics

        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        tmp.replace(path)

    @classmethod
    def load_checkpoint(
        cls, path: Path, agent_name: str = "LUNA",
    ) -> ConsciousnessState:
        """Restore a ConsciousnessState from a JSON checkpoint.

        Handles both v2.2.0 format (with Psi vector) and legacy v2.0.0
        format (without Psi vector, falls back to identity profile).

        Args:
            path: Path to the checkpoint JSON.
            agent_name: Name of the agent (must match AGENT_PROFILES).

        Returns:
            Restored ConsciousnessState instance.

        Raises:
            FileNotFoundError: If the checkpoint file does not exist.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {path}")

        with open(path) as f:
            data = json.load(f)

        version = data.get("version", "2.0.0")

        if version.startswith("2.2") or version.startswith("2.4"):
            # v2.2+ format -- full state with Psi vector.
            psi = np.array(data["psi"])

            # Validate psi vector shape and values.
            if psi.shape != (4,):
                raise ValueError(f"Invalid psi shape: expected (4,), got {psi.shape}")
            if np.any(psi < 0):
                raise ValueError(f"Invalid psi: all values must be >= 0, got {psi}")
            psi_sum = float(psi.sum())
            if not np.isclose(psi_sum, 1.0, atol=1e-6):
                raise ValueError(
                    f"Invalid psi: sum must be ~1.0, got {psi_sum}"
                )

            step_count = data.get("step_count", 0)
            history_raw = data.get("history_tail", [])
            history = [np.array(h) for h in history_raw]

            state = cls(agent_name, psi=psi, step_count=step_count, history=history)

            # Restore mass matrix if available.
            if "mass_m" in data:
                state.mass.m = np.array(data["mass_m"])

            # Restore cached phase.
            if "phase" in data:
                state._phase = data["phase"]

            # v2.4+ — PhiScorer metrics snapshot (None if absent = backward-compat).
            state.phi_metrics_snapshot: dict | None = data.get("phi_metrics")

            return state

        # Legacy v2.0.0 format -- no Psi vector stored.
        # Start from identity profile with zero history.
        state = cls(agent_name)
        state.phi_metrics_snapshot = None
        return state
