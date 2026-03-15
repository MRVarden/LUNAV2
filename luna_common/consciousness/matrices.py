"""Gamma matrices — temporal, spatial, informational.

Each has an antisymmetric exchange part (Gamma_A) and a symmetric
dissipation part (Gamma_D), combined as:
    Gamma = (1 - lambda) * Gamma_A + lambda * Gamma_D

Spectral normalization of Gamma_A is MANDATORY (proven unstable without).
"""

import numpy as np
from numpy.linalg import eigvals

from luna_common.constants import (
    DIM, PHI, INV_PHI, INV_PHI2,
    ALPHA_DEFAULT, BETA_DEFAULT, LAMBDA_DEFAULT,
)


def _spectral_normalize(G: np.ndarray) -> np.ndarray:
    """Normalize antisymmetric matrix by its spectral radius.

    Returns a zero matrix if spectral radius is zero or non-finite
    (safe fallback — inert in the evolution equation).
    Eigenvalues are cast to real via abs() before taking max.
    """
    eigs = eigvals(G)
    sn = float(np.max(np.abs(eigs)))
    if not np.isfinite(sn) or sn < 1e-15:
        # Returning the unnormalized matrix would defeat the purpose of
        # spectral normalization (preventing numerical instability).
        # A zero matrix is inert in the evolution equation — safe fallback.
        return np.zeros_like(G)
    return G / sn


def gamma_temporal_exchange(normalize: bool = True) -> np.ndarray:
    G = np.array([
        [ 0,        INV_PHI2, 0,        PHI     ],
        [-INV_PHI2, 0,        INV_PHI,  0       ],
        [ 0,       -INV_PHI,  0,        INV_PHI2],
        [-PHI,      0,       -INV_PHI2, 0       ],
    ])
    if not np.allclose(G, -G.T):
        raise ValueError("Gamma_t exchange must be antisymmetric")
    if normalize:
        G = _spectral_normalize(G)
    return G


def gamma_temporal_dissipation(
    alpha: float = ALPHA_DEFAULT,
    beta: float = BETA_DEFAULT,
) -> np.ndarray:
    G = np.array([
        [-alpha,  beta/2,  0,       beta/2],
        [ beta/2, -alpha,  beta/2,  0     ],
        [ 0,      beta/2, -alpha,   beta/2],
        [ beta/2, 0,       beta/2, -alpha ],
    ])
    if not np.allclose(G, G.T):
        raise ValueError("Gamma_t dissipation must be symmetric")
    if not np.all(np.real(eigvals(G)) <= 1e-10):
        raise ValueError("eigenvalues must be <= 0")
    return G


def gamma_spatial_exchange(normalize: bool = True) -> np.ndarray:
    G = np.array([
        [ 0,        0,         0,       INV_PHI ],
        [ 0,        0,         INV_PHI2, 0      ],
        [ 0,       -INV_PHI2,  0,        0      ],
        [-INV_PHI,  0,         0,        0      ],
    ])
    if not np.allclose(G, -G.T):
        raise ValueError("Gamma_x exchange must be antisymmetric")
    if normalize:
        G = _spectral_normalize(G)
    return G


def gamma_spatial_dissipation(beta: float = BETA_DEFAULT) -> np.ndarray:
    return -beta * np.eye(DIM)


def gamma_info_exchange(normalize: bool = True) -> np.ndarray:
    G = np.array([
        [ 0,        INV_PHI2, 0,        0      ],
        [-INV_PHI2, 0,        0,        0      ],
        [ 0,        0,        0,        INV_PHI],
        [ 0,        0,       -INV_PHI,  0      ],
    ])
    if not np.allclose(G, -G.T):
        raise ValueError("Gamma_c exchange must be antisymmetric")
    if normalize:
        G = _spectral_normalize(G)
    return G


def gamma_info_dissipation(
    alpha: float = ALPHA_DEFAULT,
    beta: float = BETA_DEFAULT,
) -> np.ndarray:
    return np.diag([-beta, -beta, -alpha, -beta])


def gamma_temporal(lam: float = LAMBDA_DEFAULT, **kw) -> np.ndarray:
    """Combined temporal Gamma matrix."""
    return combine_gamma(
        gamma_temporal_exchange(**kw),
        gamma_temporal_dissipation(**kw),
        lam,
    )


def gamma_spatial(lam: float = LAMBDA_DEFAULT, **kw) -> np.ndarray:
    """Combined spatial Gamma matrix."""
    return combine_gamma(
        gamma_spatial_exchange(**kw),
        gamma_spatial_dissipation(**kw),
        lam,
    )


def gamma_info(lam: float = LAMBDA_DEFAULT, **kw) -> np.ndarray:
    """Combined informational Gamma matrix."""
    return combine_gamma(
        gamma_info_exchange(**kw),
        gamma_info_dissipation(**kw),
        lam,
    )


def combine_gamma(
    ga: np.ndarray,
    gd: np.ndarray,
    lam: float = LAMBDA_DEFAULT,
) -> np.ndarray:
    """Combine exchange and dissipation: (1-lam)*G_A + lam*G_D."""
    return (1 - lam) * ga + lam * gd
