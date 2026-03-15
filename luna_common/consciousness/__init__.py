"""Cognitive dynamics — matrices, simplex projection, evolution step."""

from luna_common.consciousness.simplex import project_simplex
from luna_common.consciousness.matrices import (
    gamma_temporal,
    gamma_spatial,
    gamma_info,
    combine_gamma,
)
from luna_common.consciousness.evolution import evolution_step
from luna_common.consciousness.profiles import get_psi0
from luna_common.consciousness.context import Context, ContextBuilder
from luna_common.consciousness.illusion import (
    AgentIllusionResult,
    IllusionResult,
    IllusionStatus,
    SystemIllusionResult,
    compute_correlation,
    classify_status,
    detect_self_illusion,
    detect_system_illusion,
    linear_trend,
    std_dev,
)
from luna_common.consciousness.emergent_phi import EmergentPhi
from luna_common.consciousness.phi_iit_gaussian import (
    compute_phi_iit_gaussian,
    compute_phi_iit_legacy,
)

__all__ = [
    "project_simplex",
    "gamma_temporal",
    "gamma_spatial",
    "gamma_info",
    "combine_gamma",
    "evolution_step",
    "get_psi0",
    "Context",
    "ContextBuilder",
    "IllusionStatus",
    "IllusionResult",
    "AgentIllusionResult",
    "SystemIllusionResult",
    "compute_correlation",
    "classify_status",
    "detect_self_illusion",
    "detect_system_illusion",
    "linear_trend",
    "std_dev",
    "EmergentPhi",
    "compute_phi_iit_gaussian",
    "compute_phi_iit_legacy",
]
