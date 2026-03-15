"""Phi Engine — shared scoring module for the Luna ecosystem.

Provides EMA-based quality scoring, convergence detection,
phase transition state machine, and soft constraint evaluation.

All classes are pure computation — no I/O, no LLM calls.
"""

from luna_common.phi_engine.scorer import MetricEMA, PhiScorer
from luna_common.phi_engine.convergence import ConvergenceDetector, ConvergenceResult
from luna_common.phi_engine.phase_transition import PhaseTransitionMachine, PhaseChangeEvent
from luna_common.phi_engine.soft_constraint import SoftConstraint, FibonacciZone, function_size_score
from luna_common.phi_engine.veto import (
    Severity,
    VetoEvent,
    VetoRule,
    VetoResolution,
    build_veto_event,
    resolve_veto,
    DEFAULT_VETO_RULES,
    CRITICAL_SYSTEM_RULES,
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
