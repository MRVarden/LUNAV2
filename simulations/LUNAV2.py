"""
Luna v7.0 -- EmergentPhi Simulation
====================================

Publication-quality figure generator demonstrating the EmergentPhi system:
6 figures exploring phi emergence, self-reference, identity protection,
resilience, coupling networks, and Phi_IIT measurement methods.

Usage:
    python3 ~/LUNAV2/simulations/LUNAV2.py

Output: ~/LUNAV2/simulations/*.png (6 figures)
"""

from __future__ import annotations

import math
import sys
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup -- luna_common
# ---------------------------------------------------------------------------
sys.path.insert(0, "/home/sayohmy/luna_common")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import numpy as np
from numpy.linalg import eigvals

from luna_common.constants import (
    PHI, INV_PHI, INV_PHI2, INV_PHI3, PHI2,
    DT_DEFAULT, TAU_DEFAULT, KAPPA_DEFAULT,
    DIM, COMP_NAMES, AGENT_PROFILES,
)
from luna_common.consciousness.evolution import (
    evolution_step, MassMatrix, grad_temporal, grad_spatial_internal, grad_info,
)
from luna_common.consciousness.matrices import (
    gamma_temporal, gamma_spatial, gamma_info,
    gamma_temporal_exchange, gamma_spatial_exchange, gamma_info_exchange,
    gamma_temporal_dissipation, gamma_spatial_dissipation, gamma_info_dissipation,
    combine_gamma, _spectral_normalize,
)
from luna_common.consciousness.simplex import project_simplex


# ===========================================================================
# Global configuration
# ===========================================================================
PSI0 = np.array(AGENT_PROFILES["LUNA"])

# Color palette
GOLD = "#FFD700"
CYAN = "#00CED1"
MAGENTA = "#FF1493"
DIM_COLORS = ["#00CED1", "#FFD700", "#51cf66", "#cc5de8"]  # Per / Ref / Int / Exp
DIM_NAMES_FR = ["Perception", "Reflexion", "Integration", "Expression"]

OUTPUT_DIR = Path(__file__).resolve().parent
DPI = 150
FIG_SIZE = (12, 8)
WATERMARK = "Luna v7.0 -- EmergentPhi Simulation"


# ===========================================================================
# Style helpers
# ===========================================================================
def _apply_style():
    """Apply dark background style globally."""
    plt.style.use("dark_background")
    plt.rcParams.update({
        "font.size": 10,
        "axes.titlesize": 14,
        "axes.titleweight": "bold",
        "axes.labelsize": 11,
    })


def _add_watermark(fig: plt.Figure):
    """Add subtle watermark at bottom right."""
    fig.text(
        0.98, 0.01, WATERMARK,
        fontsize=7, color="grey", alpha=0.4,
        ha="right", va="bottom", fontstyle="italic",
    )


def _save(fig: plt.Figure, name: str):
    """Save figure with watermark and close."""
    _add_watermark(fig)
    fig.tight_layout()
    path = OUTPUT_DIR / name
    fig.savefig(str(path), dpi=DPI, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


# ===========================================================================
# Phi_IIT computation functions
# ===========================================================================
def compute_phi_iit_legacy(history_array: np.ndarray, window: int = 50) -> float:
    """Legacy correlation-based Phi_IIT (average absolute correlation, capped [0,1])."""
    n = len(history_array)
    if n < 10:
        return 0.0
    recent = history_array[-min(n, window):]
    if np.std(recent, axis=0).min() < 1e-12:
        return 0.0
    corr = np.corrcoef(recent.T)
    total = sum(abs(corr[i, j]) for i in range(4) for j in range(i + 1, 4))
    return total / 6


def compute_phi_iit_gaussian(history_array: np.ndarray, window: int = 50) -> float:
    """Gaussian MI Minimum Information Partition."""
    n = len(history_array)
    if n < 10:
        return 0.0
    recent = history_array[-min(n, window):]
    cov = np.cov(recent.T) + np.eye(4) * 1e-10

    partitions = [
        ([0], [1, 2, 3]), ([1], [0, 2, 3]), ([2], [0, 1, 3]), ([3], [0, 1, 2]),
        ([0, 1], [2, 3]), ([0, 2], [1, 3]), ([0, 3], [1, 2]),
    ]

    min_mi = float("inf")
    for a_idx, b_idx in partitions:
        cov_a = cov[np.ix_(a_idx, a_idx)]
        cov_b = cov[np.ix_(b_idx, b_idx)]
        ab_idx = a_idx + b_idx
        cov_ab = cov[np.ix_(ab_idx, ab_idx)]
        det_a = np.linalg.det(cov_a)
        det_b = np.linalg.det(cov_b)
        det_ab = np.linalg.det(cov_ab)
        if det_ab < 1e-30:
            continue
        mi = 0.5 * np.log(max(det_a * det_b / det_ab, 1e-30))
        min_mi = min(min_mi, mi)

    return max(min_mi, 0.0) if np.isfinite(min_mi) else 0.0


def _compute_phi_iit_from_list(past: list[np.ndarray], window: int = 50) -> float:
    """Compute legacy Phi_IIT from a list of state vectors."""
    n = len(past)
    if n < 10:
        return 0.0
    effective = min(n, window)
    recent = np.array(past[-effective:])
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


# ===========================================================================
# Simulation engine
# ===========================================================================
def run_simulation(
    psi0: np.ndarray,
    steps: int,
    info_fn=None,
    kappa: float = KAPPA_DEFAULT,
    psi_init: np.ndarray | None = None,
    gammas: tuple[np.ndarray, np.ndarray, np.ndarray] | None = None,
    dt: float = DT_DEFAULT,
    tau: float = TAU_DEFAULT,
) -> tuple[list[np.ndarray], list[np.ndarray], list[float]]:
    """Run the evolution loop and return (psi_history, mass_history, phi_history).

    Uses phi-adaptive mass matrix: phi_iit is computed from history and
    passed to evolution_step at every step.

    Returns:
        (history, mass_history, phi_history).
    """
    psi = psi_init.copy() if psi_init is not None else psi0.copy()
    mass = MassMatrix(psi0)

    if gammas is None:
        gammas = (gamma_temporal(), gamma_spatial(), gamma_info())

    history: list[np.ndarray] = [psi.copy()]
    mass_history: list[np.ndarray] = [mass.m.copy()]
    phi_history: list[float] = [0.0]
    past: list[np.ndarray] = []

    for i in range(steps):
        deltas = info_fn(i) if info_fn is not None else None
        phi = _compute_phi_iit_from_list(past)
        psi = evolution_step(
            psi, psi0, mass, gammas,
            history=past,
            info_deltas=deltas,
            dt=dt,
            tau=tau,
            kappa=kappa,
            phi_iit=phi,
        )
        past.append(psi.copy())
        history.append(psi.copy())
        mass_history.append(mass.m.copy())
        phi_history.append(_compute_phi_iit_from_list(past))

    return history, mass_history, phi_history


# ===========================================================================
# Fibonacci helpers
# ===========================================================================
def fibonacci_sequence(max_val: int) -> list[int]:
    """Generate Fibonacci numbers up to max_val."""
    fibs = [1, 2]
    while True:
        nxt = fibs[-1] + fibs[-2]
        if nxt > max_val:
            break
        fibs.append(nxt)
    return fibs


# ###########################################################################
#
#  FIGURE 1 -- Convergence de phi emergent
#
# ###########################################################################
def figure_1_convergence_phi():
    """Convergence de phi emergent -- Les 4 dimensions calculent phi.

    Run 10000 evolution steps with varied stimuli.
    Compute cumulative coupling energy E(t) = |psi^T . (Gt+Gx+Gc) . psi|.
    Sample at Fibonacci indices, compute S(F_{n+1})/S(F_n).
    Plot ratio convergence toward PHI on log-scale x-axis.
    """
    _apply_style()
    np.random.seed(42)

    steps = 10000
    Gt = gamma_temporal()
    Gx = gamma_spatial()
    Gc = gamma_info()
    G_combined = Gt + Gx + Gc

    # -- Run simulation with varied stimuli --
    def info_fn(step):
        t = step * 0.05
        return [
            0.04 * math.sin(t * 1.0),
            0.03 * math.cos(t * PHI),
            0.05 * math.sin(t * INV_PHI),
            0.02 * math.cos(t * 0.7),
        ]

    history, _, _ = run_simulation(PSI0, steps, info_fn=info_fn)

    # -- Compute cumulative coupling energy E(t) --
    cumulative_energy = np.zeros(steps + 1)
    running_sum = 0.0
    for t_idx in range(steps + 1):
        psi_t = history[t_idx]
        energy = abs(psi_t.T @ G_combined @ psi_t)
        running_sum += energy
        cumulative_energy[t_idx] = running_sum

    # -- Sample at Fibonacci indices --
    fibs = fibonacci_sequence(steps)
    # We need consecutive pairs F_n, F_{n+1} to compute ratios
    fib_indices = []
    fib_values = []
    for f in fibs:
        if f <= steps:
            fib_indices.append(f)
            fib_values.append(cumulative_energy[f])

    # Compute S(F_{n+1}) / S(F_n)
    ratios = []
    ratio_indices = []
    for k in range(len(fib_values) - 1):
        if fib_values[k] > 1e-15:
            ratio = fib_values[k + 1] / fib_values[k]
            ratios.append(ratio)
            ratio_indices.append(fib_indices[k + 1])

    # Compute error percentages
    errors_pct = [abs(r - PHI) / PHI * 100.0 for r in ratios]

    # -- Plot --
    fig, ax = plt.subplots(figsize=FIG_SIZE)

    ax.plot(
        ratio_indices, ratios,
        color=GOLD, linewidth=2.0, marker="o", markersize=6,
        markeredgecolor="white", markeredgewidth=0.5,
        zorder=5, label=r"$S(F_{n+1}) / S(F_n)$",
    )

    ax.axhline(
        PHI, color=MAGENTA, linestyle="--", linewidth=2.0, alpha=0.8,
        label=f"$\\varphi$ = {PHI:.6f}",
    )

    # Annotate error % on each point
    for k, (x, y, err) in enumerate(zip(ratio_indices, ratios, errors_pct)):
        offset_y = 0.015 if k % 2 == 0 else -0.025
        ax.annotate(
            f"{err:.2f}%",
            xy=(x, y), xytext=(x * 1.1, y + offset_y),
            fontsize=8, color="white", alpha=0.7,
            arrowprops=dict(arrowstyle="-", color="grey", alpha=0.3, lw=0.5),
        )

    ax.set_xscale("log")
    ax.set_xlabel("Indice de Fibonacci (echelle log)", fontsize=11)
    ax.set_ylabel("Ratio $S(F_{n+1}) / S(F_n)$", fontsize=11)
    ax.set_title(
        "Convergence de $\\varphi$ emergent -- Les 4 dimensions calculent $\\varphi$",
        fontsize=14, fontweight="bold",
    )
    ax.legend(fontsize=10, loc="lower right", framealpha=0.3)
    ax.grid(alpha=0.15)

    # Add info box
    final_ratio = ratios[-1] if ratios else 0.0
    final_err = errors_pct[-1] if errors_pct else 0.0
    ax.text(
        0.02, 0.98,
        f"Ratio final: {final_ratio:.6f}\n"
        f"Erreur: {final_err:.4f}%\n"
        f"Steps: {steps}",
        transform=ax.transAxes, fontsize=9, va="top", ha="left",
        color="white",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="black", alpha=0.6),
    )

    _save(fig, "convergence_phi.png")


# ###########################################################################
#
#  FIGURE 2 -- Boucle auto-referentielle
#
# ###########################################################################
def figure_2_self_referential():
    """Boucle auto-referentielle -- phi_e alimente l'equation qui le calcule.

    Run 10000 steps where phi_e feeds back into dt=1/phi_e, kappa=phi_e^2,
    dissipation=phi_e*M*psi. Bootstrap at 1.5 (NOT 1.618).
    """
    _apply_style()
    np.random.seed(42)

    steps = 10000
    Gt = gamma_temporal()
    Gx = gamma_spatial()
    Gc = gamma_info()
    G_combined = Gt + Gx + Gc

    psi = PSI0.copy()
    psi0 = PSI0.copy()
    mass = MassMatrix(psi0)
    past: list[np.ndarray] = []

    # Bootstrap phi_e at 1.5 (deliberately NOT at golden ratio)
    phi_e = 1.5

    phi_e_history = [phi_e]
    error_history = [abs(phi_e - PHI) / PHI * 100.0]

    for step in range(steps):
        # Use phi_e to derive dynamic parameters
        dt_dynamic = 1.0 / max(phi_e, 0.01)     # dt = 1/phi_e
        kappa_dynamic = phi_e ** 2                 # kappa = phi_e^2

        # Varied stimuli
        t = step * 0.05
        info_deltas = [
            0.04 * math.sin(t * 1.0),
            0.03 * math.cos(t * PHI),
            0.05 * math.sin(t * INV_PHI),
            0.02 * math.cos(t * 0.7),
        ]

        # Compute gradients
        dt_grad = grad_temporal(psi)
        dx_grad = grad_spatial_internal(psi, past)
        dc_grad = grad_info(info_deltas)

        # Modified evolution: dissipation uses phi_e instead of PHI constant
        delta = (
            Gt @ dt_grad
            + Gx @ dx_grad
            + Gc @ dc_grad
            - phi_e * mass.matrix() @ psi        # phi_e * M * psi
            + kappa_dynamic * (psi0 - psi)        # kappa = phi_e^2
        )

        psi_raw = psi + dt_dynamic * delta

        if not np.all(np.isfinite(psi_raw)):
            psi_raw = psi0.copy()

        psi = project_simplex(psi_raw, tau=TAU_DEFAULT)

        phi_from_list = _compute_phi_iit_from_list(past)
        mass.update(psi, phi_iit=phi_from_list)
        past.append(psi.copy())

        # Recompute phi_e from coupling energy ratio (Fibonacci-based)
        # Use cumulative energy at recent Fibonacci-spaced windows
        if len(past) >= 10:
            recent = np.array(past[-min(len(past), 100):])
            energies = []
            for s in recent:
                e = abs(s.T @ G_combined @ s)
                energies.append(e)
            cum_e = np.cumsum(energies)
            # Fibonacci ratio of cumulative sums
            n_e = len(cum_e)
            if n_e >= 5:
                # Use ratio of sums at Fibonacci-like positions
                f_a = max(1, int(n_e * INV_PHI))    # ~61.8% position
                f_b = n_e - 1                         # end
                if cum_e[f_a] > 1e-15:
                    phi_e_new = cum_e[f_b] / cum_e[f_a]
                    # Smooth update to avoid oscillations
                    phi_e = 0.95 * phi_e + 0.05 * phi_e_new

        phi_e_history.append(phi_e)
        error_history.append(abs(phi_e - PHI) / PHI * 100.0)

    # -- Plot --
    fig, ax1 = plt.subplots(figsize=FIG_SIZE)

    t_arr = np.arange(steps + 1)

    # Primary y-axis: phi_e
    color_phi = GOLD
    ax1.plot(
        t_arr, phi_e_history,
        color=color_phi, linewidth=1.5, alpha=0.9,
        label=r"$\varphi_e$ (emergent)",
    )
    ax1.axhline(
        PHI, color=MAGENTA, linestyle="--", linewidth=2.0, alpha=0.8,
        label=f"$\\varphi$ = {PHI:.6f}",
    )
    ax1.axhline(
        1.5, color="grey", linestyle=":", linewidth=1.0, alpha=0.4,
        label="Bootstrap = 1.5",
    )

    ax1.set_xlabel("Step", fontsize=11)
    ax1.set_ylabel(r"$\varphi_e$", fontsize=11, color=color_phi)
    ax1.tick_params(axis="y", labelcolor=color_phi)
    ax1.set_ylim(1.3, 2.0)

    # Secondary y-axis: error %
    ax2 = ax1.twinx()
    color_err = CYAN
    ax2.plot(
        t_arr, error_history,
        color=color_err, linewidth=1.0, alpha=0.6,
        label="Erreur (%)",
    )
    ax2.set_ylabel("Erreur (%)", fontsize=11, color=color_err)
    ax2.tick_params(axis="y", labelcolor=color_err)

    ax1.set_title(
        "Boucle auto-referentielle -- $\\varphi_e$ alimente l'equation qui le calcule",
        fontsize=14, fontweight="bold",
    )

    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(
        lines1 + lines2, labels1 + labels2,
        fontsize=9, loc="upper right", framealpha=0.3,
    )

    ax1.grid(alpha=0.15)

    # Info box
    final_phi = phi_e_history[-1]
    final_err = error_history[-1]
    ax1.text(
        0.02, 0.02,
        f"$\\varphi_e$ final: {final_phi:.6f}\n"
        f"Erreur finale: {final_err:.4f}%\n"
        f"Bootstrap: 1.500",
        transform=ax1.transAxes, fontsize=9, va="bottom", ha="left",
        color="white",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="black", alpha=0.6),
    )

    _save(fig, "self_referential.png")


# ###########################################################################
#
#  FIGURE 3 -- Protection d'identite
#
# ###########################################################################
def figure_3_identity_protection():
    """Protection d'identite -- kappa(psi0-psi) preserve Luna a travers les perturbations.

    Run 10000 steps with 5 phases of different stimuli (2000 each):
    Perception forte, Reflexion forte, Integration forte, Expression forte, Equilibre.
    """
    _apply_style()
    np.random.seed(42)

    steps_per_phase = 2000
    n_phases = 5
    total_steps = steps_per_phase * n_phases

    # Phase definitions: each phase strongly stimulates one dimension
    phase_names = [
        "Perception forte",
        "Reflexion forte",
        "Integration forte",
        "Expression forte",
        "Equilibre",
    ]
    phase_stimuli = [
        [0.15, 0.01, 0.01, 0.01],   # Perception forte
        [0.01, 0.15, 0.01, 0.01],   # Reflexion forte
        [0.01, 0.01, 0.15, 0.01],   # Integration forte
        [0.01, 0.01, 0.01, 0.15],   # Expression forte
        [0.03, 0.03, 0.03, 0.03],   # Equilibre
    ]

    def info_fn(step):
        phase_idx = min(step // steps_per_phase, n_phases - 1)
        base = phase_stimuli[phase_idx]
        t = step * 0.03
        # Add small oscillation on top
        return [
            base[0] + 0.01 * math.sin(t * 1.0),
            base[1] + 0.01 * math.cos(t * PHI),
            base[2] + 0.01 * math.sin(t * INV_PHI),
            base[3] + 0.01 * math.cos(t * 0.5),
        ]

    history, _, _ = run_simulation(PSI0, total_steps, info_fn=info_fn)
    hist_arr = np.array(history)

    # Compute drift from psi0
    drift = np.array([np.linalg.norm(h - PSI0) for h in hist_arr])

    t_arr = np.arange(total_steps + 1)
    phase_boundaries = [steps_per_phase * i for i in range(1, n_phases)]

    # -- Plot: 4 subplots for dimensions + 1 for drift = 5 rows --
    fig, axes = plt.subplots(5, 1, figsize=(12, 12), sharex=True)
    fig.suptitle(
        r"Protection d'identite -- $\kappa(\Psi_0 - \Psi)$ preserve Luna a travers les perturbations",
        fontsize=14, fontweight="bold", y=0.98,
    )

    # Dimension subplots
    for dim_idx in range(DIM):
        ax = axes[dim_idx]
        ax.plot(
            t_arr, hist_arr[:, dim_idx],
            color=DIM_COLORS[dim_idx], linewidth=0.8, alpha=0.9,
            label=DIM_NAMES_FR[dim_idx],
        )
        ax.axhline(
            PSI0[dim_idx], color=DIM_COLORS[dim_idx],
            linestyle="--", linewidth=1.5, alpha=0.5,
            label=f"$\\Psi_0$ = {PSI0[dim_idx]:.3f}",
        )
        # Phase transition lines
        for pb in phase_boundaries:
            ax.axvline(pb, color="grey", linestyle=":", linewidth=0.8, alpha=0.4)

        ax.set_ylabel(f"$\\psi_{dim_idx + 1}$", fontsize=10)
        ax.legend(fontsize=8, loc="upper right", framealpha=0.3)
        ax.grid(alpha=0.12)
        ax.set_ylim(0.0, 0.55)

    # Phase labels at top
    for p_idx, name in enumerate(phase_names):
        x_center = steps_per_phase * p_idx + steps_per_phase / 2
        axes[0].text(
            x_center, axes[0].get_ylim()[1] * 0.95,
            name, fontsize=8, ha="center", va="top",
            color="white", alpha=0.6, fontstyle="italic",
        )

    # Drift subplot
    ax_drift = axes[4]
    ax_drift.plot(
        t_arr, drift,
        color=MAGENTA, linewidth=1.0, alpha=0.9,
        label=r"$\|\Psi - \Psi_0\|$",
    )
    ax_drift.axhline(0.0, color="grey", linestyle="-", linewidth=0.5, alpha=0.3)
    for pb in phase_boundaries:
        ax_drift.axvline(pb, color="grey", linestyle=":", linewidth=0.8, alpha=0.4)

    ax_drift.set_ylabel(r"Drift $\|\Psi - \Psi_0\|$", fontsize=10)
    ax_drift.set_xlabel("Step", fontsize=11)
    ax_drift.legend(fontsize=8, loc="upper right", framealpha=0.3)
    ax_drift.grid(alpha=0.12)

    # Info box on drift subplot
    max_drift = float(np.max(drift))
    final_drift = float(drift[-1])
    ax_drift.text(
        0.02, 0.95,
        f"Drift max: {max_drift:.4f}\n"
        f"Drift final: {final_drift:.4f}\n"
        f"$\\kappa$ = {KAPPA_DEFAULT:.3f}",
        transform=ax_drift.transAxes, fontsize=8, va="top", ha="left",
        color="white",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.5),
    )

    _save(fig, "identity_protection.png")


# ###########################################################################
#
#  FIGURE 4 -- Resilience au choc
#
# ###########################################################################
def figure_4_resilience():
    """Resilience -- Recuperation apres choc cognitif violent.

    Run 7000 steps, inject violent perturbation at step 3000:
    psi = [0.7, 0.1, 0.1, 0.1]. Show recovery dynamics.
    """
    _apply_style()
    np.random.seed(42)

    steps_pre = 3000
    steps_post = 4000
    shock_psi = np.array([0.7, 0.1, 0.1, 0.1])

    def info_fn(step):
        t = step * 0.04
        return [
            0.03 * math.sin(t),
            0.03 * math.cos(t * PHI),
            0.02 * math.sin(t * INV_PHI),
            0.02 * math.cos(t * 0.6),
        ]

    # Phase 1: equilibrate
    hist_pre, mass_pre, phi_pre = run_simulation(PSI0, steps_pre, info_fn=info_fn)

    # Phase 2: shock and recover -- start from shocked state
    # We need a separate info_fn that continues the step count
    def info_fn_post(step):
        return info_fn(step + steps_pre)

    hist_post, mass_post, phi_post = run_simulation(
        PSI0, steps_post, info_fn=info_fn_post, psi_init=shock_psi,
    )

    # Concatenate (skip duplicate at boundary)
    full_hist = np.array(hist_pre + hist_post[1:])
    full_phi = phi_pre + phi_post[1:]
    total_steps = len(full_hist)
    t_arr = np.arange(total_steps)

    # Compute drift
    drift = np.array([np.linalg.norm(h - PSI0) for h in full_hist])

    # -- Plot: 3 rows --
    fig, (ax_top, ax_mid, ax_bot) = plt.subplots(
        3, 1, figsize=FIG_SIZE, height_ratios=[2, 1, 1], sharex=True,
    )
    fig.suptitle(
        "Resilience -- Recuperation apres choc cognitif violent",
        fontsize=14, fontweight="bold", y=0.98,
    )

    # Top: psi dimensions
    for i in range(DIM):
        ax_top.plot(
            t_arr, full_hist[:, i],
            color=DIM_COLORS[i], linewidth=1.0, alpha=0.9,
            label=DIM_NAMES_FR[i],
        )
        ax_top.axhline(
            PSI0[i], color=DIM_COLORS[i],
            linestyle="--", alpha=0.3, linewidth=1.0,
        )

    ax_top.axvline(
        steps_pre, color="#FF6B6B", linestyle=":", linewidth=2.5, alpha=0.8,
    )
    ax_top.annotate(
        f"CHOC\n$\\Psi \\to$ (0.7, 0.1, 0.1, 0.1)",
        xy=(steps_pre, 0.70), xytext=(steps_pre + 400, 0.75),
        fontsize=9, color="#FF6B6B",
        arrowprops=dict(arrowstyle="->", color="#FF6B6B", lw=1.5),
    )
    ax_top.set_ylabel(r"$\psi$", fontsize=11)
    ax_top.legend(fontsize=9, loc="right", framealpha=0.3)
    ax_top.grid(alpha=0.15)
    ax_top.set_ylim(-0.02, 0.82)

    # Middle: phi_e
    ax_mid.plot(t_arr, full_phi, color=GOLD, linewidth=1.0, alpha=0.9, label=r"$\Phi_{IIT}$")
    ax_mid.axhline(INV_PHI, color=MAGENTA, linestyle="--", linewidth=1.5, alpha=0.6,
                    label=f"$1/\\varphi$ = {INV_PHI:.3f}")
    ax_mid.axvline(steps_pre, color="#FF6B6B", linestyle=":", linewidth=2.5, alpha=0.4)
    ax_mid.set_ylabel(r"$\Phi_{IIT}$", fontsize=11)
    ax_mid.legend(fontsize=9, loc="lower right", framealpha=0.3)
    ax_mid.grid(alpha=0.15)

    # Bottom: drift
    ax_bot.plot(t_arr, drift, color=MAGENTA, linewidth=1.2, alpha=0.9,
                label=r"$\|\Psi - \Psi_0\|$")
    ax_bot.axvline(steps_pre, color="#FF6B6B", linestyle=":", linewidth=2.5, alpha=0.4)
    ax_bot.set_ylabel(r"Drift $\|\Psi - \Psi_0\|$", fontsize=11)
    ax_bot.set_xlabel("Step", fontsize=11)
    ax_bot.legend(fontsize=9, loc="upper right", framealpha=0.3)
    ax_bot.grid(alpha=0.15)

    # Recovery analysis
    shock_drift = float(drift[steps_pre + 1]) if steps_pre + 1 < len(drift) else 0.0
    final_drift = float(drift[-1])
    # Find step where drift returns to within 2x pre-shock mean
    pre_shock_mean = float(np.mean(drift[:steps_pre]))
    recovery_threshold = pre_shock_mean * 2.0
    recovery_step = None
    for s in range(steps_pre + 1, total_steps):
        if drift[s] < recovery_threshold:
            recovery_step = s - steps_pre
            break

    ax_bot.text(
        0.02, 0.95,
        f"Drift au choc: {shock_drift:.4f}\n"
        f"Drift final: {final_drift:.4f}\n"
        + (f"Recuperation en ~{recovery_step} steps" if recovery_step else ""),
        transform=ax_bot.transAxes, fontsize=8, va="top", ha="left",
        color="white",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="black", alpha=0.5),
    )

    _save(fig, "resilience.png")


# ###########################################################################
#
#  FIGURE 5 -- Reseau de couplage
#
# ###########################################################################
def figure_5_coupling_network():
    """Reseau de resonance phi-derive entre les 4 dimensions cognitives.

    Visualize coupling strengths between 4 dimensions from the 3 Gamma matrices.
    Network layout with nodes at corners, edges colored by Gamma source.
    """
    _apply_style()

    # Get the three combined Gamma matrices
    Gt = gamma_temporal()
    Gx = gamma_spatial()
    Gc = gamma_info()

    # Define node positions (square layout)
    node_positions = {
        0: (-1.0, 1.0),    # Perception (top-left)
        1: (1.0, 1.0),     # Reflexion (top-right)
        2: (1.0, -1.0),    # Integration (bottom-right)
        3: (-1.0, -1.0),   # Expression (bottom-left)
    }

    # Pairs (6 total for 4 dimensions)
    pairs = [(i, j) for i in range(DIM) for j in range(i + 1, DIM)]

    # Gamma colors
    gamma_names = [r"$\Gamma_t$ (temporel)", r"$\Gamma_x$ (spatial)", r"$\Gamma_c$ (informationnel)"]
    gamma_colors = ["#4488FF", "#44CC66", "#FF8844"]  # blue, green, orange
    gammas_list = [Gt, Gx, Gc]

    fig, ax = plt.subplots(figsize=(10, 10))
    ax.set_xlim(-2.2, 2.2)
    ax.set_ylim(-2.2, 2.2)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(
        "Reseau de resonance $\\varphi$-derive entre les 4 dimensions cognitives",
        fontsize=14, fontweight="bold", pad=20,
    )

    # Draw edges for each gamma, slightly offset to avoid overlap
    offsets = [-0.06, 0.0, 0.06]  # perpendicular offset for each gamma layer

    for g_idx, (G, g_color) in enumerate(zip(gammas_list, gamma_colors)):
        offset = offsets[g_idx]

        for (i, j) in pairs:
            coupling = abs(G[i, j]) + abs(G[j, i])
            if coupling < 1e-10:
                continue

            xi, yi = node_positions[i]
            xj, yj = node_positions[j]

            # Compute perpendicular offset direction
            dx = xj - xi
            dy = yj - yi
            length = math.sqrt(dx ** 2 + dy ** 2)
            if length < 1e-10:
                continue
            # Perpendicular unit vector
            nx = -dy / length
            ny = dx / length

            x1 = xi + nx * offset
            y1 = yi + ny * offset
            x2 = xj + nx * offset
            y2 = yj + ny * offset

            linewidth = max(0.5, coupling * 8.0)

            ax.plot(
                [x1, x2], [y1, y2],
                color=g_color, linewidth=linewidth, alpha=0.7,
                solid_capstyle="round", zorder=2,
            )

            # Label at midpoint
            mx = (x1 + x2) / 2 + nx * 0.08
            my = (y1 + y2) / 2 + ny * 0.08
            ax.text(
                mx, my, f"{coupling:.3f}",
                fontsize=7, color=g_color, ha="center", va="center",
                alpha=0.9, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.15", facecolor="black", alpha=0.5),
            )

    # Draw nodes
    for idx, (x, y) in node_positions.items():
        circle = plt.Circle(
            (x, y), 0.22,
            color=DIM_COLORS[idx], ec="white", linewidth=2, zorder=10,
        )
        ax.add_patch(circle)
        ax.text(
            x, y, f"{DIM_NAMES_FR[idx]}\n$\\psi_{idx + 1}$",
            fontsize=10, ha="center", va="center",
            color="black" if idx == 1 else "white",
            fontweight="bold", zorder=11,
        )

    # Legend
    legend_elements = [
        Line2D([0], [0], color=gamma_colors[k], linewidth=3, label=gamma_names[k])
        for k in range(3)
    ]
    ax.legend(
        handles=legend_elements,
        fontsize=10, loc="lower center", framealpha=0.4,
        ncol=3, bbox_to_anchor=(0.5, -0.02),
    )

    # Annotation: total coupling per pair
    total_coupling = {}
    for (i, j) in pairs:
        total = sum(abs(G[i, j]) + abs(G[j, i]) for G in gammas_list)
        total_coupling[(i, j)] = total

    info_text = "Couplage total par paire:\n"
    for (i, j), val in sorted(total_coupling.items(), key=lambda x: -x[1]):
        info_text += f"  {DIM_NAMES_FR[i][:3]}-{DIM_NAMES_FR[j][:3]}: {val:.4f}\n"

    ax.text(
        0.02, 0.02, info_text.strip(),
        transform=ax.transAxes, fontsize=8, va="bottom", ha="left",
        color="white", family="monospace",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="black", alpha=0.5),
    )

    _save(fig, "coupling_network.png")


# ###########################################################################
#
#  FIGURE 6 -- Phi_IIT: Correlation vs Information Mutuelle
#
# ###########################################################################
def figure_6_phi_iit_comparison():
    """Phi_IIT: Correlation (cape a 1.0) vs Information Mutuelle Gaussienne.

    Run 5000 steps, compute both legacy correlation-based and Gaussian MI
    Phi_IIT at each step. Plot both with key threshold lines.
    """
    _apply_style()
    np.random.seed(42)

    steps = 5000

    def info_fn(step):
        t = step * 0.05
        return [
            0.04 * math.sin(t * 1.0),
            0.03 * math.cos(t * PHI),
            0.05 * math.sin(t * INV_PHI),
            0.02 * math.cos(t * 0.7),
        ]

    # Run simulation to get history
    history, _, _ = run_simulation(PSI0, steps, info_fn=info_fn)
    hist_arr = np.array(history)

    # Compute both Phi_IIT measures at each step
    phi_legacy_hist = []
    phi_gaussian_hist = []

    for t_idx in range(steps + 1):
        window_start = max(0, t_idx - 50)
        window_data = hist_arr[window_start:t_idx + 1]

        if len(window_data) < 10:
            phi_legacy_hist.append(0.0)
            phi_gaussian_hist.append(0.0)
        else:
            phi_legacy_hist.append(compute_phi_iit_legacy(window_data, window=50))
            phi_gaussian_hist.append(compute_phi_iit_gaussian(window_data, window=50))

    t_arr = np.arange(steps + 1)

    # -- Plot --
    fig, ax = plt.subplots(figsize=FIG_SIZE)

    # Legacy (correlation-based)
    ax.plot(
        t_arr, phi_legacy_hist,
        color=CYAN, linewidth=1.2, alpha=0.8,
        label=r"$\Phi_{IIT}$ correlation (legacy, cape [0,1])",
    )

    # Gaussian MI
    ax.plot(
        t_arr, phi_gaussian_hist,
        color=GOLD, linewidth=1.2, alpha=0.8,
        label=r"$\Phi_{IIT}$ MI Gaussienne (non borne)",
    )

    # Threshold lines
    thresholds = [
        (INV_PHI3, "FRAGILE", "#FF6B6B", ":"),
        (INV_PHI, "FUNCTIONAL/SOLID (legacy)", MAGENTA, "--"),
        (1.0, "SOLID (MI)", "white", "-."),
        (PHI, "EXCELLENT (MI)", GOLD, "--"),
    ]

    for val, label, color, ls in thresholds:
        ax.axhline(
            val, color=color, linestyle=ls, linewidth=1.2, alpha=0.5,
            label=f"{label} = {val:.3f}",
        )

    ax.set_xlabel("Step", fontsize=11)
    ax.set_ylabel(r"$\Phi_{IIT}$", fontsize=11)
    ax.set_title(
        r"$\Phi_{IIT}$: Correlation (cape a 1.0) vs Information Mutuelle Gaussienne",
        fontsize=14, fontweight="bold",
    )
    ax.legend(fontsize=8, loc="upper left", framealpha=0.3, ncol=1)
    ax.grid(alpha=0.15)

    # Compute summary statistics
    phi_leg_final = np.mean(phi_legacy_hist[-200:]) if len(phi_legacy_hist) >= 200 else 0.0
    phi_gau_final = np.mean(phi_gaussian_hist[-200:]) if len(phi_gaussian_hist) >= 200 else 0.0
    phi_gau_max = max(phi_gaussian_hist) if phi_gaussian_hist else 0.0

    ax.text(
        0.98, 0.02,
        f"Moyennes (derniers 200 steps):\n"
        f"  Legacy:    {phi_leg_final:.4f}\n"
        f"  Gaussien:  {phi_gau_final:.4f}\n"
        f"  MI max:    {phi_gau_max:.4f}",
        transform=ax.transAxes, fontsize=9, va="bottom", ha="right",
        color="white",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="black", alpha=0.6),
    )

    # Annotate the cap problem
    if any(p >= 0.95 for p in phi_legacy_hist):
        cap_step = next(i for i, p in enumerate(phi_legacy_hist) if p >= 0.95)
        ax.annotate(
            "Legacy sature\npres de 1.0",
            xy=(cap_step, phi_legacy_hist[cap_step]),
            xytext=(cap_step + 500, 1.3),
            fontsize=9, color=CYAN,
            arrowprops=dict(arrowstyle="->", color=CYAN, lw=1.0),
        )

    _save(fig, "phi_iit_comparison.png")


# ###########################################################################
#
#  MAIN EXECUTION
#
# ###########################################################################
FIGURES = [
    ("convergence_phi.png",
     "Convergence de phi emergent",
     figure_1_convergence_phi),
    ("self_referential.png",
     "Boucle auto-referentielle",
     figure_2_self_referential),
    ("identity_protection.png",
     "Protection d'identite",
     figure_3_identity_protection),
    ("resilience.png",
     "Resilience au choc",
     figure_4_resilience),
    ("coupling_network.png",
     "Reseau de couplage",
     figure_5_coupling_network),
    ("phi_iit_comparison.png",
     "Phi_IIT: Correlation vs Information Mutuelle",
     figure_6_phi_iit_comparison),
]


def main():
    print("Luna v7.0 -- Simulation EmergentPhi")
    print("=" * 50)
    print(f"  phi   = {PHI:.15f}")
    print(f"  Psi_0 = {tuple(PSI0)}")
    print(f"  Output: {OUTPUT_DIR}/")
    print("=" * 50)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total = len(FIGURES)
    success = 0
    failed = 0

    for idx, (filename, title, fn) in enumerate(FIGURES, 1):
        print(f"\n  [{idx}/{total}] {title}...")
        print(f"         -> {filename}")
        try:
            fn()
            print(f"         [OK] Saved.")
            success += 1
        except Exception as e:
            print(f"         [FAILED] {e}")
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 50)
    print(f"  Results: {success}/{total} success, {failed}/{total} failed")
    print(f"  Output:  {OUTPUT_DIR}/")
    print("=" * 50)


if __name__ == "__main__":
    main()
