"""Phi_IIT via Gaussian Minimum Information Partition.

Replaces the correlation-based Phi_IIT (capped at 1.0) with an
information-theoretic measure that is UNBOUNDED above.  For 4 dimensions,
computes mutual information across all 7 non-trivial bipartitions and
returns the minimum -- the weakest link in integration.

    MI(A;B) = 1/2 * ln( det(Sigma_A) * det(Sigma_B) / det(Sigma_AB) )

With phi-derived coupling matrices, the system can reach and exceed
phi = 1.618 on this measure.

Also exports ``compute_phi_iit_legacy`` -- the old correlation-based
method bounded to [0, 1] -- for comparison and backward compatibility.
"""

from __future__ import annotations

import numpy as np
from numpy.linalg import det, eigvalsh

# -------------------------------------------------------------------------
# All 7 non-trivial bipartitions of {0, 1, 2, 3}
# -------------------------------------------------------------------------
# 4 singleton splits: one dimension vs the other three.
# 3 balanced splits: two dimensions vs the other two.
# Total = C(4,1) + C(4,2)/2 = 4 + 3 = 7  (divided by 2 for balanced
# because {A,B} and {B,A} are the same partition).
_BIPARTITIONS: list[tuple[list[int], list[int]]] = [
    # Singleton splits
    ([0], [1, 2, 3]),
    ([1], [0, 2, 3]),
    ([2], [0, 1, 3]),
    ([3], [0, 1, 2]),
    # Balanced splits
    ([0, 1], [2, 3]),
    ([0, 2], [1, 3]),
    ([0, 3], [1, 2]),
]

# Regularization epsilon for covariance matrices.
_EPSILON: float = 1e-10

# Minimum data points required for a meaningful covariance estimate.
_MIN_HISTORY: int = 10


def compute_phi_iit_gaussian(
    history: list[np.ndarray] | np.ndarray,
    window: int = 50,
) -> float:
    """Compute Phi_IIT using Gaussian mutual information.

    For each of the 7 non-trivial bipartitions of {0,1,2,3}, computes
    the Gaussian mutual information between the two subsets of dimensions.
    Returns the *minimum* across all 7 -- the weakest informational link,
    which is the IIT definition of integrated information.

    Args:
        history: Sequence of 4D state vectors (list of arrays or 2D array).
            Each row is one time step, each column is one cognitive dimension.
        window: Number of most recent steps to use.  Older history is ignored.

    Returns:
        Phi_IIT (non-negative, unbounded above).
        Returns 0.0 if history is too short or covariance is degenerate.
    """
    # Normalize input to a 2D numpy array.
    if isinstance(history, list):
        if len(history) < _MIN_HISTORY:
            return 0.0
        data = np.array(history[-window:])
    else:
        if history.ndim == 1:
            return 0.0
        if history.shape[0] < _MIN_HISTORY:
            return 0.0
        data = history[-window:]

    n_samples, n_dims = data.shape
    if n_samples < _MIN_HISTORY or n_dims < 2:
        return 0.0

    # Full covariance matrix with regularization.
    cov_full = np.cov(data, rowvar=False)
    cov_full += _EPSILON * np.eye(n_dims)

    # Check that the full covariance is not degenerate.
    if not _is_positive_definite(cov_full):
        return 0.0

    # Compute MI for each bipartition; Phi_IIT = min over all.
    phi_values: list[float] = []

    for part_a, part_b in _BIPARTITIONS:
        mi = _gaussian_mi(cov_full, part_a, part_b)
        if not np.isfinite(mi):
            return 0.0
        phi_values.append(mi)

    if not phi_values:
        return 0.0

    result = min(phi_values)
    return max(0.0, result)


def compute_phi_iit_legacy(
    history: list[np.ndarray] | np.ndarray,
    window: int = 50,
) -> float:
    """Legacy correlation-based Phi_IIT, bounded to [0, 1].

    Computes mean absolute off-diagonal correlation across the window,
    clamped to [0, 1].  Kept for backward compatibility and comparison
    with the new Gaussian measure.

    Args:
        history: Sequence of 4D state vectors.
        window: Number of most recent steps to use.

    Returns:
        Phi_IIT in [0.0, 1.0].
    """
    if isinstance(history, list):
        if len(history) < _MIN_HISTORY:
            return 0.0
        data = np.array(history[-window:])
    else:
        if history.ndim == 1:
            return 0.0
        if history.shape[0] < _MIN_HISTORY:
            return 0.0
        data = history[-window:]

    n_samples, n_dims = data.shape
    if n_samples < _MIN_HISTORY or n_dims < 2:
        return 0.0

    # Compute correlation matrix.
    # If any dimension has zero variance, corrcoef returns NaN there.
    with np.errstate(invalid="ignore", divide="ignore"):
        corr = np.corrcoef(data, rowvar=False)

    if not np.all(np.isfinite(corr)):
        return 0.0

    # Mean absolute off-diagonal correlation.
    mask = ~np.eye(n_dims, dtype=bool)
    mean_abs_corr = float(np.mean(np.abs(corr[mask])))

    return max(0.0, min(1.0, mean_abs_corr))


# -------------------------------------------------------------------------
# Internal helpers
# -------------------------------------------------------------------------

def _gaussian_mi(
    cov: np.ndarray,
    part_a: list[int],
    part_b: list[int],
) -> float:
    """Compute Gaussian mutual information MI(A; B).

    MI(A;B) = 1/2 * ln( det(Sigma_A) * det(Sigma_B) / det(Sigma_AB) )

    where Sigma_A, Sigma_B are the marginal covariances and Sigma_AB
    is the joint covariance of the combined indices.

    Args:
        cov: Full regularized covariance matrix.
        part_a: Indices of subset A.
        part_b: Indices of subset B.

    Returns:
        MI value (non-negative for valid covariances).
    """
    idx_ab = sorted(part_a + part_b)

    # Extract sub-matrices.
    cov_a = cov[np.ix_(part_a, part_a)]
    cov_b = cov[np.ix_(part_b, part_b)]
    cov_ab = cov[np.ix_(idx_ab, idx_ab)]

    det_a = det(cov_a)
    det_b = det(cov_b)
    det_ab = det(cov_ab)

    # Guard against non-positive determinants.
    if det_a <= 0.0 or det_b <= 0.0 or det_ab <= 0.0:
        return 0.0

    ratio = (det_a * det_b) / det_ab
    if ratio <= 0.0 or not np.isfinite(ratio):
        return 0.0

    mi = 0.5 * float(np.log(ratio))
    return max(0.0, mi)


def _is_positive_definite(matrix: np.ndarray) -> bool:
    """Check whether a symmetric matrix is positive definite."""
    try:
        eigs = eigvalsh(matrix)
        return bool(np.all(eigs > 0))
    except np.linalg.LinAlgError:
        return False
