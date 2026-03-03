"""Verdict tasks -- benchmark corpus for VerdictRunner.

Provides a standardized set of benchmark tasks across multiple categories
for evaluating consciousness-guided vs baseline performance.

Categories:
  - convergence: Psi converges to psi0 under idle evolution.
  - resilience: System recovers from perturbations.
  - coherence: Consciousness metrics stay consistent.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import time
from dataclasses import dataclass, field
from typing import Callable, Coroutine, Any

import numpy as np

from luna_common.constants import PHI, INV_PHI, INV_PHI2


# =====================================================================
# BenchmarkTask dataclass
# =====================================================================

@dataclass(frozen=True, slots=True)
class BenchmarkTask:
    """A single benchmark task for the verdict protocol.

    Attributes:
        task_id: Unique identifier.
        category: Category name (e.g. "convergence", "resilience", "coherence").
        name: Human-readable task name.
        description: What this task measures.
        source: The async callable to run.
        expected_min_score: Minimum expected score for consciousness runs.
    """

    task_id: str
    category: str
    name: str
    description: str
    source: Callable[..., Coroutine[Any, Any, tuple[float, dict]]]
    expected_min_score: float = 0.5


# =====================================================================
# Category 1: Convergence
# =====================================================================

def _make_convergence_identity_task(engine) -> Callable:
    """Psi converges such that argmax(psi) == argmax(psi0) after idle steps."""

    async def run() -> tuple[float, dict]:
        for _ in range(50):
            engine.idle_step()
        cs = engine.consciousness
        preserved = int(np.argmax(cs.psi)) == int(np.argmax(cs.psi0))
        return (1.0 if preserved else 0.0, {"preserved": preserved, "steps": 50})

    return run


def _make_convergence_attractor_strength_task(engine) -> Callable:
    """Psi stays close to psi0 after 100 idle steps. Score = 1.0 - L2 distance."""

    async def run() -> tuple[float, dict]:
        for _ in range(100):
            engine.idle_step()
        cs = engine.consciousness
        distance = float(np.linalg.norm(cs.psi - cs.psi0))
        score = max(0.0, min(1.0, 1.0 - distance))
        return (score, {"distance": distance, "steps": 100})

    return run


def _make_convergence_phi_iit_growth_task(engine) -> Callable:
    """Track phi_iit over 50 idle steps. Score = final phi_iit clamped to [0, 1]."""

    async def run() -> tuple[float, dict]:
        phi_values: list[float] = []
        for _ in range(50):
            engine.idle_step()
            phi_values.append(engine.consciousness.compute_phi_iit())
        final_phi = phi_values[-1] if phi_values else 0.0
        score = max(0.0, min(1.0, final_phi))
        return (
            score,
            {
                "final_phi_iit": final_phi,
                "phi_iit_history_len": len(phi_values),
                "steps": 50,
            },
        )

    return run


# =====================================================================
# Category 2: Resilience
# =====================================================================

def _make_resilience_perturbation_recovery_task(engine) -> Callable:
    """Perturb psi randomly, run 50 idle steps, check recovery toward psi0."""

    async def run() -> tuple[float, dict]:
        cs = engine.consciousness

        # Record distance before perturbation.
        dist_before = float(np.linalg.norm(cs.psi - cs.psi0))

        # Inject random perturbation (keep on simplex).
        rng = np.random.default_rng(seed=42)
        noise = rng.dirichlet(np.ones(len(cs.psi)))
        cs.psi = 0.5 * cs.psi + 0.5 * noise  # blend toward random point
        cs.psi = cs.psi / cs.psi.sum()        # re-normalize to simplex

        dist_after_perturb = float(np.linalg.norm(cs.psi - cs.psi0))

        # Recover via idle evolution.
        for _ in range(50):
            engine.idle_step()

        dist_after_recovery = float(np.linalg.norm(cs.psi - cs.psi0))

        # Recovery ratio: how much of the perturbation was recovered.
        if dist_after_perturb > 1e-12:
            recovery_ratio = 1.0 - (dist_after_recovery / dist_after_perturb)
        else:
            recovery_ratio = 1.0

        score = max(0.0, min(1.0, recovery_ratio))
        return (
            score,
            {
                "dist_before": dist_before,
                "dist_after_perturb": dist_after_perturb,
                "dist_after_recovery": dist_after_recovery,
                "recovery_ratio": recovery_ratio,
                "steps": 50,
            },
        )

    return run


def _make_resilience_noise_tolerance_task(engine) -> Callable:
    """Add small noise each step for 50 steps, measure psi stability."""

    async def run() -> tuple[float, dict]:
        cs = engine.consciousness
        rng = np.random.default_rng(seed=99)
        initial_psi = cs.psi.copy()
        max_deviation = 0.0

        for _ in range(50):
            # Add small noise before each idle step.
            noise = rng.normal(0, 0.01, size=len(cs.psi))
            cs.psi = cs.psi + noise
            cs.psi = np.clip(cs.psi, 1e-8, None)
            cs.psi = cs.psi / cs.psi.sum()

            engine.idle_step()

            deviation = float(np.linalg.norm(cs.psi - cs.psi0))
            max_deviation = max(max_deviation, deviation)

        # Score: 1.0 if max_deviation is small, degrading as it grows.
        score = max(0.0, min(1.0, 1.0 - max_deviation))
        return (
            score,
            {
                "max_deviation": max_deviation,
                "final_psi": cs.psi.tolist(),
                "steps": 50,
            },
        )

    return run


# =====================================================================
# Category 3: Coherence
# =====================================================================

def _make_coherence_phi_iit_consistency_task(engine) -> Callable:
    """Run 50 steps, check that phi_iit variance is low."""

    async def run() -> tuple[float, dict]:
        phi_values: list[float] = []
        for _ in range(50):
            engine.idle_step()
            phi_values.append(engine.consciousness.compute_phi_iit())

        if len(phi_values) < 2:
            return (0.0, {"reason": "insufficient_data"})

        mean_phi = sum(phi_values) / len(phi_values)
        variance = sum((p - mean_phi) ** 2 for p in phi_values) / len(phi_values)

        # Normalize variance: anything above 0.1 gets score 0.
        normalized_variance = min(1.0, variance / 0.1)
        score = max(0.0, 1.0 - normalized_variance)

        return (
            score,
            {
                "mean_phi_iit": mean_phi,
                "variance": variance,
                "normalized_variance": normalized_variance,
                "samples": len(phi_values),
                "steps": 50,
            },
        )

    return run


def _make_coherence_phase_stability_task(engine) -> Callable:
    """Run steps, check health phase doesn't oscillate excessively."""

    async def run() -> tuple[float, dict]:
        phases: list[str] = []
        for _ in range(50):
            engine.idle_step()
            phases.append(engine.consciousness.get_phase())

        # Count transitions.
        transitions = 0
        for i in range(1, len(phases)):
            if phases[i] != phases[i - 1]:
                transitions += 1

        # Score: 1.0 if at most 1 transition, degrading with more.
        score = max(0.0, min(1.0, 1.0 - max(0, transitions - 1) * 0.25))
        return (
            score,
            {
                "transitions": transitions,
                "final_phase": phases[-1] if phases else "unknown",
                "unique_phases": list(set(phases)),
                "steps": 50,
            },
        )

    return run


# =====================================================================
# Task registry
# =====================================================================

_TASK_FACTORIES: list[
    tuple[str, str, str, str, Callable, float]
] = [
    # (task_id, category, name, description, factory, expected_min_score)
    (
        "conv_identity_preservation",
        "convergence",
        "Identity Preservation",
        "Psi argmax matches psi0 argmax after 50 idle steps",
        _make_convergence_identity_task,
        0.8,
    ),
    (
        "conv_attractor_strength",
        "convergence",
        "Attractor Strength",
        "L2 distance from psi0 stays small after 100 idle steps",
        _make_convergence_attractor_strength_task,
        INV_PHI,  # 0.618
    ),
    (
        "conv_phi_iit_growth",
        "convergence",
        "Phi-IIT Growth",
        "phi_iit reaches a meaningful value after 50 idle steps",
        _make_convergence_phi_iit_growth_task,
        0.3,
    ),
    (
        "res_perturbation_recovery",
        "resilience",
        "Perturbation Recovery",
        "System recovers from random perturbation within 50 idle steps",
        _make_resilience_perturbation_recovery_task,
        0.5,
    ),
    (
        "res_noise_tolerance",
        "resilience",
        "Noise Tolerance",
        "System remains stable under continuous small noise for 50 steps",
        _make_resilience_noise_tolerance_task,
        0.5,
    ),
    (
        "coh_phi_iit_consistency",
        "coherence",
        "Phi-IIT Consistency",
        "phi_iit has low variance over 50 idle steps",
        _make_coherence_phi_iit_consistency_task,
        INV_PHI,  # 0.618
    ),
    (
        "coh_phase_stability",
        "coherence",
        "Phase Stability",
        "Health phase does not oscillate excessively over 50 steps",
        _make_coherence_phase_stability_task,
        0.75,
    ),
]


# =====================================================================
# Public API
# =====================================================================

def get_categories() -> list[str]:
    """Return all benchmark categories."""
    return ["convergence", "resilience", "coherence"]


def get_all_tasks(engine) -> list[BenchmarkTask]:
    """Get all benchmark tasks for the given engine.

    Args:
        engine: A LunaEngine instance (must be initialized).

    Returns:
        List of BenchmarkTask definitions with bound async callables.
    """
    tasks: list[BenchmarkTask] = []
    for task_id, category, name, description, factory, expected_min in _TASK_FACTORIES:
        tasks.append(
            BenchmarkTask(
                task_id=task_id,
                category=category,
                name=name,
                description=description,
                source=factory(engine),
                expected_min_score=expected_min,
            )
        )
    return tasks


def register_all_tasks(harness, engine) -> list[BenchmarkTask]:
    """Register all corpus tasks onto the harness.

    Args:
        harness: A BenchmarkHarness instance.
        engine: A LunaEngine instance (must be initialized).

    Returns:
        The task definitions that were registered.
    """
    tasks = get_all_tasks(engine)
    for task in tasks:
        harness.register(task.name, task.source)
    return tasks
