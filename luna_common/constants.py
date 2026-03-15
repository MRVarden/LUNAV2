"""
Phi-derived constants — validated by simulation.py (seed=42, 400 steps, 4/4 identities).

ALL values derive from PHI = (1 + sqrt(5)) / 2.
Do NOT hardcode approximations — compute from PHI.
"""

import math

# The golden ratio
PHI: float = (1 + math.sqrt(5)) / 2  # 1.618033988749895

# ── EmergentPhi runtime override ─────────────────────────────────────────────
# At runtime, EmergentPhi (consciousness/emergent_phi.py) computes phi from
# the system's own coupling dynamics.  The constants below are used only:
#   - HARDCODED_PHI: alias for backward-compat code that needs the static value.
#   - PHI_INITIAL_ESTIMATE: documents the EmergentPhi bootstrap seed (1.5).
# The *live* phi fed into the evolution equation comes from EmergentPhi.get_phi().
HARDCODED_PHI: float = PHI              # static alias — never changes at runtime
PHI_INITIAL_ESTIMATE: float = 1.5       # EmergentPhi bootstrap seed (NOT 1.618)

# Derived constants
INV_PHI: float = 1.0 / PHI           # 0.6180339887498949
INV_PHI2: float = 1.0 / PHI**2       # 0.3819660112501051
INV_PHI3: float = 1.0 / PHI**3       # 0.2360679774997897
PHI2: float = PHI**2                  # 2.6180339887498949

# Model parameters (all validated)
LAMBDA_DEFAULT: float = INV_PHI2      # 0.382 — dissipation ratio in Gamma decomposition
ALPHA_DEFAULT: float = INV_PHI2       # 0.382 — self-damping coefficient
BETA_DEFAULT: float = INV_PHI3        # 0.236 — cross-dissipative coupling
KAPPA_DEFAULT: float = PHI2           # 2.618 — identity anchoring strength
KAPPA_GAMMA_DEFAULT: float = 0.0     # 0.0 — asymmetric kappa disabled (symmetric fallback)
TAU_DEFAULT: float = PHI              # 1.618 — softmax temperature
DT_DEFAULT: float = INV_PHI          # 0.618 — time step

# Dimensions
DIM: int = 4  # Perception, Reflexion, Integration, Expression

# Component names (indexed 0-3)
COMP_NAMES: list[str] = ["Perception", "Reflexion", "Integration", "Expression"]

# Agent names — v5.1: single-agent model (Luna only)
AGENT_NAMES: list[str] = ["LUNA"]

# Agent identity profiles (Psi_0) — each on simplex Delta^3
# v5.1: Only LUNA is active internally. External project profiles kept
# because ~/SAYOHMY, ~/SENTINEL, ~/TESTENGINEER import from here.
AGENT_PROFILES: dict[str, tuple[float, float, float, float]] = {
    "LUNA":          (0.260, 0.322, 0.250, 0.168),  # v5.3 — identity-equilibrium compromise (alpha=0.25)
    # External projects (decoupled from Luna engine)
    "SAYOHMY":       (0.15, 0.15, 0.20, 0.50),  # Expression dominant
    "SENTINEL":      (0.50, 0.20, 0.20, 0.10),  # Perception dominant
    "TESTENGINEER":  (0.15, 0.20, 0.50, 0.15),  # Integration dominant
}

# Phase thresholds (with hysteresis band +/- 0.025)
PHASE_THRESHOLDS: dict[str, float] = {
    "BROKEN": 0.0,
    "FRAGILE": 0.25,
    "FUNCTIONAL": 0.50,
    "SOLID": 0.75,
    "EXCELLENT": 0.90,
}
HYSTERESIS_BAND: float = 0.025

# Phi_IIT threshold during activity
PHI_IIT_THRESHOLD: float = INV_PHI   # 0.618

# Memory fractal directory names (post-migration)
FRACTAL_DIRS: list[str] = ["seeds", "roots", "branches", "leaves"]

# ═══════════════════════════════════════════════════════════════════════════════
# PHI ENGINE — Scoring constants (Phase 2)
# ═══════════════════════════════════════════════════════════════════════════════

# Canonical metric names — 7 intrinsic cognitive metrics (v5.0 Conscience Unitaire)
# These replace the 7 external code metrics. Measurable at every chat turn.
METRIC_NAMES: tuple[str, ...] = (
    "integration_coherence",    # psi3 — phi_iit level, coherence is queen
    "identity_anchoring",       # transversal — distance to Psi0
    "reflection_depth",         # psi2 — confidence * causalities
    "perception_acuity",        # psi1 — observation count + diversity
    "expression_fidelity",      # psi4 — voice validator compliance
    "affect_regulation",        # transversal — emotional balance
    "memory_vitality",          # transversal — episode production
)

# Legacy metric names — kept for checkpoint migration compatibility
LEGACY_METRIC_NAMES: tuple[str, ...] = (
    "security_integrity", "coverage_pct", "complexity_score",
    "test_ratio", "abstraction_ratio", "function_size_score",
    "performance_score",
)

# Fibonacci-derived weights (sum = 1.000)
#   Fibonacci seq: 1, 1, 2, 3, 5, 8, 13 -> reversed -> 13, 8, 5, 3, 2, 1, 1
#   Total = 33, weights = each / 33 rounded so sum = 1.000
PHI_WEIGHTS: tuple[float, ...] = (
    0.394,   # integration_coherence  (13/33 — coherence is queen)
    0.242,   # identity_anchoring     (8/33  — stay yourself)
    0.152,   # reflection_depth       (5/33  — depth of thought)
    0.091,   # perception_acuity      (3/33  — observation quality)
    0.061,   # expression_fidelity    (2/33  — voice fidelity)
    0.030,   # affect_regulation      (1/33  — emotional balance)
    0.030,   # memory_vitality        (1/33  — memory health)
)

# EMA smoothing factors per metric
PHI_EMA_ALPHAS: tuple[float, ...] = (
    0.3,   # integration_coherence — balanced: phi_iit evolves smoothly
    0.2,   # identity_anchoring    — stable: identity drifts slowly
    0.4,   # reflection_depth      — responsive: varies per message
    0.4,   # perception_acuity     — responsive: varies per message
    0.3,   # expression_fidelity   — balanced
    0.2,   # affect_regulation     — stable: affect has its own hysteresis
    0.2,   # memory_vitality       — stable: memory builds over time
)

# Health score thresholds (from LUNA_CONSCIOUSNESS_FRAMEWORK.md §IV [phi.thresholds])
PHI_HEALTH_THRESHOLDS: dict[str, float] = {
    "BROKEN":     0.0,
    "FRAGILE":    INV_PHI2,   # 0.382
    "FUNCTIONAL": 0.500,
    "SOLID":      INV_PHI,    # 0.618
    "EXCELLENT":  0.786,      # ≈ sqrt(INV_PHI)
}

# Fibonacci zone boundaries for soft constraints
FIBONACCI_ZONES: dict[str, tuple[float, float]] = {
    "comfort":    (INV_PHI,  1.0),       # [0.618, 1.0]  — no penalty
    "acceptable": (INV_PHI2, INV_PHI),   # [0.382, 0.618) — mild penalty
    "warning":    (INV_PHI3, INV_PHI2),  # [0.236, 0.382) — moderate penalty
    "critical":   (0.0,      INV_PHI3),  # [0.0,   0.236) — severe penalty
}

# Target function size (lines), used by function_size_score soft constraint
FUNCTION_SIZE_TARGET: int = 17  # Middle of Fibonacci [13, 21]

# ═══════════════════════════════════════════════════════════════════════════════
# DREAM CYCLE — Simulation parameters (v2.3.0)
# ═══════════════════════════════════════════════════════════════════════════════

ALPHA_DREAM: float = INV_PHI3           # 0.236 — Ψ₀ update step (conservative)
PHI_DRIFT_MAX: float = INV_PHI2         # 0.382 — max displacement per dream cycle
PSI_COMPONENT_MIN: float = 0.05         # Floor per component (no extinction)
DREAM_REPLAY_DT: float = INV_PHI        # 0.618 — dt for evolve() in dream
DREAM_EXPLORE_STEPS_FACTOR: float = PHI2  # 2.618 — step multiplier for exploration
