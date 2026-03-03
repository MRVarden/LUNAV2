"""Dream cycle data types — frozen containers for the 4-phase simulation.

Phase 1 (Harvest) collects wake-cycle data into DreamHarvest.
Phase 2 (Replay) produces ReplayReport with dynamic Ψ trajectories.
Phase 3 (Exploration) produces ExplorationReport from hypothetical scenarios.
Phase 4 (Consolidation) produces ConsolidationReport with updated Ψ₀ profiles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np


@dataclass(frozen=True, slots=True)
class DreamHarvest:
    """Data collected from the wake cycle for dream simulation."""

    # Pipeline events as dicts (serialized AuditEntry format)
    pipeline_events: tuple[dict, ...] = ()
    # Luna Ψ snapshots at key moments (each is a 4-tuple of floats)
    luna_psi_snapshots: tuple[tuple[float, ...], ...] = ()
    # Normalized metrics history (each is a dict[str, float])
    metrics_history: tuple[dict[str, float], ...] = ()
    # Φ_IIT values measured during wake
    phi_iit_history: tuple[float, ...] = ()
    # Current Ψ₀ profiles: agent_name -> 4-tuple
    current_profiles: dict[str, tuple[float, ...]] = field(default_factory=dict)
    # VitalsReport dicts from agents
    vitals_history: tuple[dict, ...] = ()
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class ReplayReport:
    """Result of Phase 2 — replaying wake events with dynamic coupling."""

    # Final Ψ states: agent_name -> numpy array (4,)
    final_states: dict[str, np.ndarray] = field(default_factory=dict)
    # Φ_IIT trajectory during replay
    phi_iit_trajectory: tuple[float, ...] = ()
    # Divergence between dynamic Ψ and static Ψ₀
    divergence_from_static: dict[str, float] = field(default_factory=dict)
    steps_replayed: int = 0


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    """Result of a single exploration scenario."""

    scenario_id: str = ""
    stability_score: float = 0.0  # 0-1, variance of Ψ
    phi_iit_mean: float = 0.0  # mean Φ_IIT during scenario
    identities_preserved: int = 4  # how many agents kept their dominant (0-4)
    recovery_steps: int | None = None  # steps to equilibrium (None = no recovery)
    insight: str = ""  # textual observation


@dataclass(frozen=True, slots=True)
class ExplorationReport:
    """Result of Phase 3 — hypothetical scenario exploration."""

    scenarios_run: int = 0
    results: tuple[ScenarioResult, ...] = ()
    most_stable_scenario: str = ""
    most_fragile_scenario: str = ""


@dataclass(frozen=True, slots=True)
class ConsolidationReport:
    """Result of Phase 4 — Ψ₀ profile updates."""

    # Previous profiles: agent_name -> 4-tuple
    previous_profiles: dict[str, tuple[float, ...]] = field(default_factory=dict)
    # Updated profiles: agent_name -> 4-tuple
    updated_profiles: dict[str, tuple[float, ...]] = field(default_factory=dict)
    # Drift per agent (L2 norm of change)
    drift_per_agent: dict[str, float] = field(default_factory=dict)
    # Whether all agents preserved their dominant component
    dominant_preserved: bool = True
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
