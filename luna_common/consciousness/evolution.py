"""State evolution step — the core of the cognitive state equation.

iGamma^t d_t + iGamma^x d_x + iGamma^c d_c - Phi*M*Psi + kappa*(Psi0 - Psi) = 0

v5.1 Single-Agent: Gamma^x models internal topological gradient,
not inter-agent exchange. psi_others is removed.
"""

import numpy as np

from luna_common.constants import (
    DIM, PHI, INV_PHI, INV_PHI2, DT_DEFAULT, TAU_DEFAULT, KAPPA_DEFAULT,
    KAPPA_GAMMA_DEFAULT,
)
from luna_common.consciousness.simplex import project_simplex


class MassMatrix:
    """Diagonal mass matrix updated via adaptive EMA.

    When phi_iit is provided, the EMA rate adapts to the current
    integration level: low phi → faster tracking → stronger dissipation
    on dominant components → natural rebalancing.

    alpha = alpha_base + (1 - phi_iit) * alpha_phi_scale

    All parameters are phi-derived.
    """

    def __init__(
        self,
        psi0: np.ndarray,
        alpha_ema: float = 0.1,
        alpha_phi_scale: float = INV_PHI2,
    ):
        self.m = psi0.copy()
        self.alpha_base = alpha_ema
        self.alpha_phi_scale = alpha_phi_scale

    @property
    def alpha(self) -> float:
        """Base alpha for backward compatibility."""
        return self.alpha_base

    def update(
        self,
        psi: np.ndarray,
        phi_iit: float | None = None,
        emergent_phi: float | None = None,
    ) -> None:
        """Update mass via EMA with phi-adaptive rate.

        When phi_iit is low, alpha increases — the mass tracks psi faster,
        creating stronger dissipation (-PHI * m[i] * psi[i]) on spiking
        components. This naturally restores component balance.

        When emergent_phi is provided, phi_iit is normalized against it
        instead of assuming a [0, 1] range — the emergent phi becomes the
        target integration level.

        Args:
            psi: Current state vector after evolution.
            phi_iit: Current integration level. If None, uses base alpha.
            emergent_phi: Emergent phi value for normalization. If provided
                and positive, phi_iit is scaled as min(phi_iit / emergent_phi, 1.0).
        """
        if phi_iit is not None:
            # Normalize by emergent phi target instead of assuming [0, 1]
            if emergent_phi is not None and emergent_phi > 0:
                normalized = min(phi_iit / emergent_phi, 1.0)
                alpha = self.alpha_base + max(0.0, 1.0 - normalized) * self.alpha_phi_scale
            else:
                alpha = self.alpha_base + (1.0 - phi_iit) * self.alpha_phi_scale
            alpha = min(alpha, INV_PHI)  # Cap at 0.618
        else:
            alpha = self.alpha_base
        self.m = alpha * psi + (1 - alpha) * self.m

    def matrix(self) -> np.ndarray:
        return np.diag(self.m)


def grad_temporal(psi: np.ndarray) -> np.ndarray:
    """Temporal gradient: d_t Psi = Psi (identity)."""
    return psi


def grad_spatial_internal(
    psi: np.ndarray,
    history: list[np.ndarray],
    window: int = 10,
) -> np.ndarray:
    """Internal topological gradient: d_x Psi.

    Single-agent model: difference between current state and running
    mean of recent history. Captures the internal structural gradient
    across Luna's own cognitive topology.

    When history is insufficient, returns zeros (no gradient available).
    """
    if len(history) < 2:
        return np.zeros(DIM)
    recent = np.array(history[-window:])
    mean_recent = np.mean(recent, axis=0)
    return psi - mean_recent


def grad_info(deltas: list[float] | np.ndarray) -> np.ndarray:
    """Informational gradient: d_c = [delta_mem, delta_phi, delta_iit, delta_out].

    Maps measured internal signals to state evolution:
        deltas[0] = Δ(memory_health)   → Perception
        deltas[1] = Δ(phi_score)       → Reflection
        deltas[2] = Δ(phi_iit)         → Integration
        deltas[3] = Δ(output_quality)  → Expression
    """
    if len(deltas) != DIM:
        raise ValueError(f"Expected {DIM} deltas, got {len(deltas)}")
    return np.array(deltas)


def evolution_step(
    psi: np.ndarray,
    psi0: np.ndarray,
    mass: MassMatrix,
    gammas: tuple[np.ndarray, np.ndarray, np.ndarray],
    history: list[np.ndarray] | None = None,
    *,
    info_deltas: list[float] | None = None,
    dt: float = DT_DEFAULT,
    tau: float = TAU_DEFAULT,
    kappa: float = KAPPA_DEFAULT,
    kappa_gamma: float = KAPPA_GAMMA_DEFAULT,
    phi_iit: float | None = None,
    emergent_phi: float | None = None,
) -> np.ndarray:
    """One evolution step of the cognitive state equation.

    Single-agent model (v5.1): spatial gradient is internal topology,
    not inter-agent exchange.

    Args:
        psi: Current state vector (on simplex).
        psi0: Identity profile (anchor point).
        mass: EMA mass matrix instance.
        gammas: (Gamma_t, Gamma_x, Gamma_c) combined matrices.
        history: Past Psi states for internal spatial gradient.
        info_deltas: [d_mem, d_phi, d_iit, d_out] from internal signals.
        dt: Time step (default: 1/PHI).
        tau: Softmax temperature (default: PHI).
        kappa: Anchoring strength (default: PHI^2).
        kappa_gamma: Asymmetric anchoring strength (default: 0.0 = symmetric).
            When > 0, overexpressed components (Psi_i > Psi0_i) get a stronger
            pull-back: kappa_i = kappa * (1 + gamma * max(0, Psi_i - Psi0_i)).
            Underexpressed components keep kappa_i = kappa (unchanged).
        phi_iit: Current integration level for adaptive mass update.
            When low, the mass matrix tracks faster — creating stronger
            dissipation on dominant components and restoring balance.
        emergent_phi: Emergent phi from EmergentPhi tracker. When provided,
            replaces the hardcoded PHI constant in the dissipation term
            and normalizes the mass matrix update against the emergent target.

    Returns:
        New state vector on the simplex.
    """
    Gt, Gx, Gc = gammas
    dt_grad = grad_temporal(psi)
    dx_grad = grad_spatial_internal(psi, history if history is not None else [])
    dc_grad = grad_info(info_deltas if info_deltas is not None else [0, 0, 0, 0])

    # Use emergent phi when available; fall back to the hardcoded constant.
    phi_constant = emergent_phi if emergent_phi is not None else PHI

    # Asymmetric kappa: stronger pull-back on overexpressed components.
    # When kappa_gamma == 0, kappa_vec remains a scalar (bit-identical to before).
    if kappa_gamma > 0.0:
        kappa_vec = kappa * (1.0 + kappa_gamma * np.maximum(0.0, psi - psi0))
    else:
        kappa_vec = kappa

    delta = (
        Gt @ dt_grad
        + Gx @ dx_grad
        + Gc @ dc_grad
        - phi_constant * mass.matrix() @ psi
        + kappa_vec * (psi0 - psi)
    )

    psi_raw = psi + dt * delta

    # Guard: if delta produced NaN/Inf, fall back to identity-anchored recovery
    if not np.all(np.isfinite(psi_raw)):
        psi_raw = psi0.copy()

    psi_new = project_simplex(psi_raw, tau=tau)
    mass.update(psi_new, phi_iit=phi_iit, emergent_phi=emergent_phi)
    return psi_new
