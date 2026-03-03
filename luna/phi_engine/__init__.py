"""Phi Engine — thin re-exports from the shared luna_common.phi_engine package.

All implementation lives in luna_common.phi_engine.
This module exists so that intra-project imports like
``from luna.phi_engine import PhiScorer`` work as expected.
"""

from luna_common.phi_engine import (
    CRITICAL_SYSTEM_RULES,
    ConvergenceDetector,
    ConvergenceResult,
    DEFAULT_VETO_RULES,
    FibonacciZone,
    MetricEMA,
    PhaseChangeEvent,
    PhaseTransitionMachine,
    PhiScorer,
    Severity,
    SoftConstraint,
    VetoEvent,
    VetoResolution,
    VetoRule,
    build_veto_event,
    function_size_score,
    resolve_veto,
)

__all__ = [
    "MetricEMA",
    "PhiScorer",
    "ConvergenceDetector",
    "ConvergenceResult",
    "PhaseTransitionMachine",
    "PhaseChangeEvent",
    "SoftConstraint",
    "FibonacciZone",
    "function_size_score",
    "Severity",
    "VetoEvent",
    "VetoRule",
    "VetoResolution",
    "build_veto_event",
    "resolve_veto",
    "DEFAULT_VETO_RULES",
    "CRITICAL_SYSTEM_RULES",
]
