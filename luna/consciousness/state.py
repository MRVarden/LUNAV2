"""Cognitive state — Psi vector on the simplex Delta^3.

Wraps luna_common.consciousness with Luna-specific persistence
(loading/saving checkpoints in JSON) and Phi_IIT computation.
"""

from __future__ import annotations

import fcntl
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from luna_common.constants import (
    DIM,
    DT_DEFAULT,
    HYSTERESIS_BAND,
    INV_PHI3,
    KAPPA_DEFAULT,
    KAPPA_GAMMA_DEFAULT,
    PHASE_THRESHOLDS,
    TAU_DEFAULT,
)
from luna_common.consciousness.phi_iit_gaussian import (
    compute_phi_iit_gaussian,
)
from luna_common.consciousness import (
    evolution_step,
    gamma_info,
    gamma_spatial,
    gamma_temporal,
    get_psi0,
)
from luna_common.consciousness.emergent_phi import EmergentPhi
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

    Encapsulates the full cognitive state: current vector, identity
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

        # Two-layer identity: immutable core + adaptive dream overlay.
        self.psi0_core: np.ndarray = get_psi0(agent_name)
        self._psi0_adaptive: np.ndarray = np.zeros(DIM, dtype=np.float64)
        self.psi0: np.ndarray = self._recompute_psi0()

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

        # EmergentPhi tracker — discovers phi from coupling dynamics.
        # Must be initialized before _compute_phase_from_scratch() which
        # uses _get_dynamic_thresholds() derived from emergent phi.
        self.emergent_phi: EmergentPhi = EmergentPhi()

        self._phase: str = self._compute_phase_from_scratch()
        self.phi_metrics_snapshot: dict | None = None

    # ------------------------------------------------------------------
    # Evolution
    # ------------------------------------------------------------------

    def evolve(
        self,
        info_deltas: list[float],
        dt: float = DT_DEFAULT,
        tau: float = TAU_DEFAULT,
        kappa: float = KAPPA_DEFAULT,
        kappa_gamma: float = KAPPA_GAMMA_DEFAULT,
    ) -> np.ndarray:
        """Run one evolution step and update internal state.

        v5.1 Single-agent: spatial gradient uses internal history,
        not other agents' states. Phi_IIT is passed to the mass matrix
        for adaptive dissipation (v5.3).

        EmergentPhi feeds back into the evolution equation: the phi constant
        in the dissipation term is the emergent value discovered by the
        system's own coupling dynamics (Phase 2).

        Args:
            info_deltas: [d_mem, d_phi, d_iit, d_out] informational gradient.
            dt: Time step.
            tau: Softmax temperature.
            kappa: Identity anchoring strength.
            kappa_gamma: Asymmetric anchoring strength (0.0 = symmetric).

        Returns:
            The new Psi vector (also stored as self.psi).
        """
        # Current phi_iit drives adaptive mass matrix rate.
        phi = self.compute_phi_iit()

        # Get emergent phi (fallback to hardcoded PHI during bootstrap).
        phi_e = self.emergent_phi.get_phi()

        psi_new = evolution_step(
            self.psi,
            self.psi0,
            self.mass,
            self.gammas,
            history=self.history,
            info_deltas=info_deltas,
            dt=dt,
            tau=tau,
            kappa=kappa,
            kappa_gamma=kappa_gamma,
            phi_iit=phi,
            emergent_phi=phi_e,
        )
        self.psi = psi_new
        # Anti-stagnation: skip history append if psi is identical to last entry.
        # Frozen history (all-duplicate) poisons phi_iit → 0 → phase BROKEN.
        if not self.history or not np.allclose(psi_new, self.history[-1], atol=1e-10):
            self.history.append(psi_new.copy())
        self.step_count += 1
        self._phase = self._apply_hysteresis(self._phase)

        # Feed coupling energy to EmergentPhi tracker.
        coupling_energy = self._compute_coupling_energy()
        self.emergent_phi.update(coupling_energy)

        return psi_new

    # ------------------------------------------------------------------
    # Phi_IIT
    # ------------------------------------------------------------------

    def compute_phi_iit(self, window: int = 50) -> float:
        """Compute Phi_IIT via Gaussian Mutual Information (Phase 3).

        Uses the information-theoretic measure from phi_iit_gaussian which
        computes MI across all 7 non-trivial bipartitions and returns the
        minimum.  This measure is UNBOUNDED above (can exceed 1.0 and reach
        phi ~ 1.618 with strong coupling).

        Falls back to the legacy correlation method if Gaussian MI returns 0
        despite sufficient history (e.g. degenerate covariance).
        """
        result = compute_phi_iit_gaussian(self.history, window=window)
        if result > 0.0:
            return result
        # Fallback: if Gaussian MI returned 0 but we have enough data,
        # try the correlation method as a safety net.
        return self._compute_phi_iit_correlation(window=window)

    def _compute_phi_iit_correlation(self, window: int = 50) -> float:
        """Legacy Phi_IIT via correlation method, bounded to [0, 1].

        Kept as private fallback for cases where the Gaussian measure
        returns 0 despite sufficient history (degenerate covariance, etc.).
        """
        n = len(self.history)
        if n < 10:
            return 0.0
        effective = min(n, window)
        recent = np.array(self.history[-effective:])
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

    def _compute_coupling_energy(self) -> float:
        """Compute coupling energy E(t) = |psi^T . (Gt + Gx + Gc) . psi|."""
        Gt, Gx, Gc = self.gammas
        G_total = Gt + Gx + Gc
        return abs(float(self.psi @ G_total @ self.psi))

    def get_emergent_phi(self) -> float:
        """Return the current emergent phi value."""
        return self.emergent_phi.get_phi()

    # ------------------------------------------------------------------
    # Phase management
    # ------------------------------------------------------------------

    def get_phase(self) -> str:
        """Return the current phase label."""
        return self._phase

    def _get_dynamic_thresholds(self) -> dict[str, float]:
        """Phase thresholds derived from emergent phi.

        BROKEN:     0.0        (fixed)
        FRAGILE:    1/phi_e^3  (~0.236)
        FUNCTIONAL: 1/phi_e    (~0.618)
        SOLID:      1.0        (fixed -- 1 bit of integrated information)
        EXCELLENT:  phi_e      (~1.618 -- the golden attractor)
        """
        phi_e = self.emergent_phi.get_phi()
        return {
            "BROKEN": 0.0,
            "FRAGILE": 1.0 / (phi_e ** 3),
            "FUNCTIONAL": 1.0 / phi_e,
            "SOLID": 1.0,
            "EXCELLENT": phi_e,
        }

    def _compute_phase_from_scratch(self) -> str:
        """Determine phase from phi_iit without hysteresis (for init)."""
        phi = self.compute_phi_iit()
        thresholds = self._get_dynamic_thresholds()
        phase = _PHASES[0]
        for name in _PHASES:
            if phi >= thresholds[name]:
                phase = name
        return phase

    def _apply_hysteresis(self, current_phase: str) -> str:
        """Apply hysteresis-aware phase transition.

        To move UP a phase, the score must exceed threshold + band.
        To move DOWN, the score must drop below threshold - band.
        Allows multiple steps per call so the phase converges in one evolve().
        """
        phi = self.compute_phi_iit()
        thresholds = self._get_dynamic_thresholds()
        current_idx = _PHASES.index(current_phase)

        # Upgrade — walk up as far as phi justifies.
        while current_idx < len(_PHASES) - 1:
            next_phase = _PHASES[current_idx + 1]
            if phi >= thresholds[next_phase] + HYSTERESIS_BAND:
                current_idx += 1
            else:
                break

        # Downgrade — walk down as far as phi dictates.
        while current_idx > 0:
            if phi < thresholds[_PHASES[current_idx]] - HYSTERESIS_BAND:
                current_idx -= 1
            else:
                break

        return _PHASES[current_idx]

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

    def _recompute_psi0(self) -> np.ndarray:
        """Compute effective psi0 = normalize(psi0_core + alpha * adaptive).

        When _psi0_adaptive is all zeros (default), psi0 == psi0_core.
        Alpha = INV_PHI3 (0.236) dampens adaptive changes.

        Uses L1 normalization (clamp + divide by sum) to preserve the
        core profile exactly when adaptive is zero. project_simplex uses
        softmax which distorts valid simplex vectors.
        """
        raw = self.psi0_core + INV_PHI3 * self._psi0_adaptive
        # Clamp negative values to zero, then L1 normalize.
        clamped = np.maximum(raw, 0.0)
        total = clamped.sum()
        if total < 1e-12:
            return self.psi0_core.copy()
        return clamped / total

    def update_psi0_adaptive(self, delta: np.ndarray | tuple) -> None:
        """Update the adaptive identity layer and recompute psi0.

        Used by dream consolidation. The delta is added to _psi0_adaptive,
        then psi0 is recomputed as normalize(psi0_core + alpha * adaptive).
        The mass matrix is re-seeded.

        Args:
            delta: Change to apply to the adaptive layer (shape ``(4,)``).

        Raises:
            ValueError: If delta has the wrong shape.
        """
        delta = np.asarray(delta, dtype=np.float64)
        if delta.shape != (DIM,):
            raise ValueError(
                f"Invalid delta shape: expected ({DIM},), got {delta.shape}"
            )
        self._psi0_adaptive = self._psi0_adaptive + delta
        self.psi0 = self._recompute_psi0()
        self.mass = MassMatrix(self.psi0)

    def update_psi0(self, new_psi0: np.ndarray) -> None:
        """Update the identity anchor Psi_0 (backward-compatible).

        Back-derives the adaptive layer from the requested new_psi0.
        Prefer :meth:`update_psi0_adaptive` for dream consolidation.

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

        # Back-derive adaptive: new_psi0 ~ normalize(core + alpha*adaptive)
        # Approximate: adaptive ~ (new_psi0 - core) / alpha
        if INV_PHI3 > 1e-8:
            self._psi0_adaptive = (new_psi0 - self.psi0_core) / INV_PHI3

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
            "version": "3.5.0",
            "type": "consciousness_state",
            "agent_name": self.agent_name,
            "updated": datetime.now(timezone.utc).isoformat(),
            "psi": self.psi.tolist(),
            "psi0": self.psi0.tolist(),
            "psi0_core": self.psi0_core.tolist(),
            "psi0_adaptive": self._psi0_adaptive.tolist(),
            "mass_m": self.mass.m.tolist(),
            "step_count": self.step_count,
            "phase": self._phase,
            "phi_iit": self.compute_phi_iit(),
            "history_tail": [h.tolist() for h in self.history[-100:]],
            "emergent_phi": self.emergent_phi.snapshot(),
        }
        # Always persist phi_metrics: use explicit param, else cached snapshot.
        effective_metrics = phi_metrics or self.phi_metrics_snapshot
        if effective_metrics is not None:
            data["phi_metrics"] = effective_metrics

        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.with_suffix(".state_lock")
        tmp = path.with_suffix(".tmp")
        try:
            lock_path.touch(exist_ok=True)
            with open(lock_path) as lf:
                fcntl.flock(lf, fcntl.LOCK_EX)
                with open(tmp, "w") as f:
                    json.dump(data, f, indent=2)
                tmp.replace(path)
        except OSError:
            # Fallback: write without lock (e.g. read-only FS).
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

        lock_path = path.with_suffix(".state_lock")
        try:
            lock_path.touch(exist_ok=True)
            with open(lock_path) as lf:
                fcntl.flock(lf, fcntl.LOCK_SH)
                with open(path) as f:
                    data = json.load(f)
        except OSError:
            with open(path) as f:
                data = json.load(f)

        version = data.get("version", "2.0.0")

        if version.startswith("2.2") or version.startswith("2.4") or version.startswith("3."):
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

            # Restore adaptive identity layer if available (v5.3+).
            if "psi0_adaptive" in data:
                state._psi0_adaptive = np.array(
                    data["psi0_adaptive"], dtype=np.float64,
                )
                state.psi0 = state._recompute_psi0()
                state.mass = MassMatrix(state.psi0)

            # Restore mass matrix if available.
            if "mass_m" in data:
                state.mass.m = np.array(data["mass_m"])

            # Restore cached phase — but validate against current phi_iit.
            # The saved phase may be stale (e.g., from a bug that returned
            # phi=0.0). Recompute from scratch and use the better of the two.
            if "phase" in data:
                saved_phase = data["phase"]
                computed_phase = state._compute_phase_from_scratch()
                saved_idx = _PHASES.index(saved_phase) if saved_phase in _PHASES else 0
                computed_idx = _PHASES.index(computed_phase)
                # Trust the higher of saved vs computed — a stale-low phase
                # from a past bug should not hold Luna back.
                state._phase = _PHASES[max(saved_idx, computed_idx)]

            # v2.4+ — PhiScorer metrics snapshot (None if absent = backward-compat).
            state.phi_metrics_snapshot: dict | None = data.get("phi_metrics")

            # Restore EmergentPhi tracker state if available.
            if "emergent_phi" in data:
                state.emergent_phi.restore(data["emergent_phi"])

            return state

        # Legacy v2.0.0 format -- no Psi vector stored.
        # Start from identity profile with zero history.
        state = cls(agent_name)
        state.phi_metrics_snapshot = None
        return state
