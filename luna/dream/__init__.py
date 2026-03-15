"""Dream Cycle — nocturnal consolidation of cognitive history.

4 dream modes (v3.5):
  1. Learning: extract skills from interaction history
  2. Reflection: deep thought (100 iterations, CREATIVE)
  3. Simulation: auto-generated scenarios on state copies
  4. CEM optimization: counterfactual param tuning

Plus statistical consolidation (legacy 4-phase) and sleep/wake lifecycle.
"""

from luna.dream.awakening import Awakening, AwakeningReport
from luna.dream.consolidation import load_profiles, save_profiles
from luna.dream.dream_cycle import (
    DreamCycle,
    DreamResult,
    # Legacy re-exports (v1 fallback, used by SleepManager/Awakening)
    LegacyDreamCycle,
    DreamPhase,
    DreamReport,
    PhaseResult,
)
from luna.dream.harvest import DreamHarvest
from luna.dream.sleep_manager import SleepManager, SleepState, SleepStatus
from luna.dream.learning import DreamLearning, Interaction, Skill
from luna.dream.reflection import DreamReflection
from luna.dream.priors import (
    DreamPriors,
    ReflectionPrior,
    SimulationPrior,
    SkillPrior,
    populate_dream_priors,
)
from luna.dream.simulation import DreamSimulation, Scenario, SimulationResult
from luna.dream.dream_journal import (
    DreamJournal,
    DreamJournalEntry,
    build_journal_entry,
    format_journal_context,
)

__all__ = [
    "Awakening",
    "AwakeningReport",
    "build_journal_entry",
    "DreamCycle",
    "DreamHarvest",
    "DreamJournal",
    "DreamJournalEntry",
    "DreamLearning",
    "DreamPhase",
    "DreamPriors",
    "DreamReflection",
    "DreamReport",
    "DreamResult",
    "DreamSimulation",
    "Interaction",
    "LegacyDreamCycle",
    "PhaseResult",
    "ReflectionPrior",
    "Scenario",
    "SimulationPrior",
    "Skill",
    "SkillPrior",
    "SimulationResult",
    "SleepManager",
    "SleepState",
    "SleepStatus",
    "format_journal_context",
    "load_profiles",
    "populate_dream_priors",
    "save_profiles",
]
