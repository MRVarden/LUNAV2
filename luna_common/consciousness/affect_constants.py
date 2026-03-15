"""Affect system constants — all phi-derived, single source of truth.

Every module in the affect pipeline imports from here.
Change inertia, impulse strength, or clustering in one place only.
"""

from luna_common.constants import PHI, INV_PHI, INV_PHI2, INV_PHI3

# --- Hysteresis ---
AFFECT_ALPHA: float = INV_PHI2          # 0.382 — affect moves with drag
MOOD_BETA: float = INV_PHI3             # 0.236 — mood moves slowly
MOOD_IMPULSE: float = INV_PHI           # 0.618 — impulse strength for significant episodes

# --- Interpretation ---
AFFECT_MOOD_BLEND: float = INV_PHI      # 0.618 — affect domine, mood colore
W_VALENCE: float = PHI                  # 1.618 — valence pese plus dans la distance PAD
W_AROUSAL: float = 1.0
W_DOMINANCE: float = 1.0

# --- Norm alignment ---
PSI0_DRIFT_CEILING: float = INV_PHI     # 0.618 — au-dela, identity_score = 0

# --- Uncovered zones ---
CLUSTER_RADIUS: float = INV_PHI3        # 0.236 — rayon de fusion entre zones
STABILITY_THRESHOLD: float = INV_PHI    # 0.618 — seuil de maturite
MAX_UNNAMED_ZONES: int = 8              # Fibonacci — cap anti-explosion
UNCOVERED_THRESHOLD: float = INV_PHI    # 0.618 — distance min pour detecter zone non couverte

# --- Significance ---
TRACE_SIGNIFICANCE_THRESHOLD: float = 0.7  # episodes above this get an AffectiveTrace

# --- Idle ---
IDLE_CYCLE_INTERVAL: int = 8            # Fibonacci — cycles avant emission idle event
