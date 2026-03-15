"""Simplex projection via softmax with temperature tau."""

import numpy as np

from luna_common.constants import TAU_DEFAULT, DIM

# Minimum tau to prevent division-by-zero / numerical explosion
_TAU_MIN: float = 1e-12


def project_simplex(raw: np.ndarray, tau: float = TAU_DEFAULT) -> np.ndarray:
    """Project a raw 4-vector onto the probability simplex Delta^3.

    Uses softmax with temperature tau (default: PHI = 1.618).
    Guarantees: sum = 1.0, all components > 0.

    If raw contains NaN/Inf, falls back to uniform distribution.
    tau is clamped to >= 1e-12 to prevent division by zero.
    """
    if not np.all(np.isfinite(raw)):
        return np.ones(DIM) / DIM
    tau = max(float(tau), _TAU_MIN)
    scaled = raw / tau - np.max(raw / tau)
    e = np.exp(scaled)
    denom = np.sum(e)
    if denom == 0 or not np.isfinite(denom):
        return np.ones(DIM) / DIM
    result = e / denom
    if not np.all(np.isfinite(result)):
        return np.ones(DIM) / DIM
    # Ensure strict positivity: floor at machine-tiny, then renormalize.
    # Prevents softmax underflow from producing exact zeros.
    tiny = np.finfo(result.dtype).tiny
    if np.any(result <= 0):
        result = np.maximum(result, tiny)
        result /= result.sum()
    return result


def validate_simplex(psi: np.ndarray, tol: float = 1e-8) -> bool:
    """Check that psi is on the simplex: sum=1, all > 0, dim=DIM."""
    if psi.shape != (DIM,):
        return False
    if abs(psi.sum() - 1.0) > tol:
        return False
    if np.any(psi <= 0):
        return False
    return True
