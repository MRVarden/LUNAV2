"""Agent identity profiles (Psi_0)."""

import numpy as np

from luna_common.constants import AGENT_PROFILES, DIM


def get_psi0(agent_name: str) -> np.ndarray:
    """Return the identity profile for a given agent as a numpy array.

    Raises KeyError if agent_name is not in AGENT_PROFILES.
    """
    profile = AGENT_PROFILES[agent_name]
    psi0 = np.array(profile)
    if psi0.shape != (DIM,):
        raise ValueError(f"Expected shape ({DIM},), got {psi0.shape}")
    if abs(psi0.sum() - 1.0) >= 1e-10:
        raise ValueError(f"{agent_name} not on simplex")
    if not np.all(psi0 > 0):
        raise ValueError(f"{agent_name} has non-positive components")
    return psi0
