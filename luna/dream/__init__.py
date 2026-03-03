"""Dream Cycle — nocturnal consolidation of consciousness history.

Four algorithmic phases:
  1. Consolidation: statistics on recent Psi history
  2. Reinterpretation: cross-component correlations
  3. Defragmentation: remove near-duplicate states, cap buffer
  4. Creative connections: non-adjacent pipeline couplings

Plus sleep/wake lifecycle management and dream simulation (v2.3.0):
  - harvest: frozen data containers for the 4-phase dream simulation
  - consolidation: Ψ₀ profile update with φ-derived safeguards
"""

from luna.dream.awakening import Awakening, AwakeningReport
from luna.dream.consolidation import consolidate_profiles, load_profiles, save_profiles
from luna.dream.dream_cycle import DreamCycle, DreamPhase, DreamReport, PhaseResult
from luna.dream.harvest import (
    ConsolidationReport,
    DreamHarvest,
    ExplorationReport,
    ReplayReport,
    ScenarioResult,
)
from luna.dream.scenarios import DEFAULT_SCENARIOS, DreamScenario, explore_all, run_scenario
from luna.dream.simulator import DreamSimulator
from luna.dream.sleep_manager import SleepManager, SleepState, SleepStatus

__all__ = [
    "Awakening",
    "AwakeningReport",
    "ConsolidationReport",
    "DEFAULT_SCENARIOS",
    "DreamCycle",
    "DreamHarvest",
    "DreamPhase",
    "DreamReport",
    "DreamScenario",
    "DreamSimulator",
    "ExplorationReport",
    "PhaseResult",
    "ReplayReport",
    "ScenarioResult",
    "SleepManager",
    "SleepState",
    "SleepStatus",
    "consolidate_profiles",
    "explore_all",
    "load_profiles",
    "run_scenario",
    "save_profiles",
]
