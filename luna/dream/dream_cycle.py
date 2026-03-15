"""Dream Cycle — orchestrates 4 dream modes (Phase H + Emergence + Affect).

Sequence:
  1. Learning — extract skills from history (fast, ~0.1s)
  2. Reflection — deep thought 100 iterations (~0.5s)
  3. Simulation — test auto-generated scenarios (~0.5s)
  4. CEM optimization — counterfactual param tuning (~1s)
  5. Psi_0 consolidation — identity update (protected)
  6. Affect dream — episode recall, mood apaisement, unnamed zone scan
  7. Save checkpoint

Called by:
  - Inactivity watcher (every 2h)
  - /dream command
  - Decider when intent=DREAM

Compatibility: falls back to LegacyDreamCycle if causal graph has < 10 edges.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from luna.consciousness.causal_graph import CausalGraph
from luna.consciousness.evaluator import Evaluator
from luna.consciousness.learnable_params import LearnableParams
from luna.consciousness.state import ConsciousnessState
from luna.consciousness.thinker import Thought
from luna.dream.learnable_optimizer import (
    CEMOptimizer,
    LearningTrace,
    consolidate_psi0,
)
from luna.dream.dream_journal import (
    DreamJournal,
    DreamJournalEntry,
    build_journal_entry,
    format_journal_context,
)
from luna.dream.learning import DreamLearning, Interaction, Skill
from luna.dream.reflection import DreamReflection
from luna.dream.simulation import DreamSimulation, SimulationResult
from luna_common.schemas.cycle import CycleRecord

# Backward-compatible re-exports from legacy v1 cycle.
# These are used by SleepManager, Awakening, and session.py fallback.
from luna.dream._legacy_cycle import (  # noqa: F401
    DreamCycle as LegacyDreamCycle,
    DreamPhase,
    DreamReport,
    PhaseResult,
)

log = logging.getLogger(__name__)


# Minimum edges in causal graph to use full dream (otherwise fallback to legacy)
_MIN_GRAPH_EDGES: int = 10


# ══════════════════════════════════════════════════════════════════════════════
#  DATA MODEL
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class DreamResult:
    """Complete result of a Dream cycle."""

    skills_learned: list[Skill] = field(default_factory=list)
    thought: Thought | None = None
    simulations: list[SimulationResult] = field(default_factory=list)
    learning_trace: LearningTrace | None = None
    psi0_delta: tuple[float, ...] = ()
    psi0_applied: bool = False  # True ONLY if update_psi0() succeeded
    graph_stats: dict = field(default_factory=dict)
    duration: float = 0.0
    mode: str = "full"  # "full" or "quick"
    synthesis_report: object | None = None  # v6.0 — SynthesisReport
    # PlanAffect Phase 5 — dream affect outputs
    episodes_recalled: int = 0
    mood_apaisement: bool = False
    unnamed_zones_mature: int = 0


# ══════════════════════════════════════════════════════════════════════════════
#  DREAM CYCLE
# ══════════════════════════════════════════════════════════════════════════════

class DreamCycle:
    """Orchestrates the 4 dream modes.

    Mode 1 (Learning)    -> Expression  (psi_4): extract skills
    Mode 2 (Reflection)  -> Reflexion   (psi_2): deep thought
    Mode 3 (Simulation)  -> Integration (psi_3): test scenarios
    Mode 4 (CEM)         -> Optimization: tune LearnableParams
    Perception (psi_1) is INACTIVE during dream — no external stimuli.
    """

    def __init__(
        self,
        thinker: object,
        causal_graph: CausalGraph,
        learning: DreamLearning,
        reflection: DreamReflection,
        simulation: DreamSimulation,
        state: ConsciousnessState,
        evaluator: Evaluator | None = None,
        params: LearnableParams | None = None,
        affect_engine: object | None = None,
        episodic_memory: object | None = None,
        synthesis: object | None = None,
        dream_journal: DreamJournal | None = None,
    ) -> None:
        self._thinker = thinker
        self._graph = causal_graph
        self._learning = learning
        self._reflection = reflection
        self._simulation = simulation
        self._state = state
        self._evaluator = evaluator
        self._params = params
        self._affect_engine = affect_engine
        self._episodic_memory = episodic_memory
        self._synthesis = synthesis
        self._journal = dream_journal

    def is_mature(self) -> bool:
        """True if causal graph has enough edges for full dream.

        Falls back to legacy if graph is too sparse (Luna just born).
        """
        stats = self._graph.stats()
        return stats["edge_count"] >= _MIN_GRAPH_EDGES

    def run(
        self,
        history: list[Interaction] | None = None,
        recent_cycles: list[CycleRecord] | None = None,
        psi0_delta_history: list[tuple[float, ...]] | None = None,
    ) -> DreamResult:
        """Execute the full dream cycle.

        Sequence:
          1. Learning — extract skills from history
          2. Reflection — 100 iterations of deep thought
          3. Simulation — test auto-generated scenarios
          4. CEM optimization — tune LearnableParams (if evaluator+params)
          5. Psi_0 consolidation — adjust identity anchor
          6. Collect stats

        Args:
            history: Interaction history for skill extraction.
            recent_cycles: Recent CycleRecords for CEM replay.

        Returns:
            DreamResult with all outputs.
        """
        start = time.monotonic()
        result = DreamResult(mode="full")

        # Capture phi before dream for journal entry.
        phi_before_dream = self._state.compute_phi_iit()

        # Recall previous dream insights as weak context (cumulative memory).
        journal_context = ""
        if self._journal is not None:
            recalled = self._journal.recall(limit=5)
            if recalled:
                journal_context = format_journal_context(recalled)
                log.info(
                    "Dream journal: recalled %d previous dream(s) as context",
                    len(recalled),
                )

        # Mode 1: Learning (Expression psi_4)
        # v5.0: Prefer learning from CycleRecords (cognitive experience).
        # Fall back to Interaction history for backward compatibility.
        if recent_cycles:
            result.skills_learned = self._learning.learn_from_cycles(recent_cycles)
        elif history:
            result.skills_learned = self._learning.learn(history)
        if result.skills_learned:
            triggers = [s.trigger for s in result.skills_learned]
            impacts = [f"{s.phi_impact:+.3f}" for s in result.skills_learned]
            log.info(
                "Dream skills: %d learned (triggers=%s, impacts=%s)",
                len(result.skills_learned), triggers, impacts,
            )

        # Mode 2: Reflection (Reflexion psi_2)
        result.thought = self._reflection.reflect(
            max_iterations=100, journal_context=journal_context,
        )

        # Mode 3: Simulation (Integration psi_3)
        result.simulations = self._simulation.simulate(
            journal_context=journal_context,
        )

        # Mode 4: CEM optimization (if evaluator and params are available)
        if self._evaluator is not None and self._params is not None:
            cycles = recent_cycles or []
            if cycles:
                cem = CEMOptimizer(self._evaluator)
                optimized, trace = cem.optimize(self._params, cycles)
                # Apply optimized params in place
                self._params.restore(optimized.snapshot())
                result.learning_trace = trace
                log.info("Dream CEM: %s", trace.summary())

        # Mode 5: Psi_0 consolidation (protected)
        # v6.0 fix: Use update_psi0(new_psi0) which back-derives adaptive correctly.
        # update_psi0_adaptive(delta) dampens by INV_PHI3 (4.2x weaker), causing
        # consolidation to have almost no effect.
        if recent_cycles:
            psi0 = tuple(float(x) for x in self._state.psi0)
            new_psi0, delta = consolidate_psi0(
                psi0, recent_cycles, psi0_delta_history=psi0_delta_history,
            )
            result.psi0_delta = delta
            if any(abs(d) > 1e-8 for d in delta):
                import numpy as np
                try:
                    self._state.update_psi0(np.array(new_psi0))
                    result.psi0_applied = True
                    log.info("Psi0 consolidated: delta=%s", tuple(round(d, 4) for d in delta))
                except Exception:
                    log.warning("Psi0 consolidation failed", exc_info=True)
                    result.psi0_applied = False

        # Mode 6: Affect dream (PlanAffect Phase 5)
        self._dream_affect(result)

        # Mode 7: Synthesis longitudinale (v6.0) — read-only retrospective.
        if self._synthesis is not None:
            try:
                report = self._synthesis.run(cycles=recent_cycles, window=50)
                result.synthesis_report = report
                log.info("Dream synthesis: %d trends, %d anomalies", len(report.trends), len(report.anomalies))
            except Exception:
                log.debug("Dream synthesis failed", exc_info=True)

        # Collect final stats
        result.graph_stats = self._graph.stats()
        result.duration = time.monotonic() - start

        # Record dream in journal (persistent cumulative memory).
        if self._journal is not None:
            try:
                phi_after_dream = self._state.compute_phi_iit()
                entry = build_journal_entry(
                    result, self._journal, phi_before_dream, phi_after_dream,
                )
                self._journal.record(entry)
            except Exception:
                log.warning("Dream journal recording failed", exc_info=True)

        return result

    def _dream_affect(self, result: DreamResult) -> None:
        """Affect processing during dream.

        Three sub-phases:
          a) Episode recall → EPISODE_RECALLED events (memory→emotion bridge)
          b) Mood apaisement — arousal decreases, valence trends neutral
          c) UnnamedZone scan — log mature unnamed zones
        """
        if self._affect_engine is None:
            return

        try:
            from luna.consciousness.affect import AffectiveTrace
            from luna.consciousness.appraisal import AffectEvent

            # (a) Episode recall → EPISODE_RECALLED
            if self._episodic_memory is not None and hasattr(self._episodic_memory, "recall"):
                import numpy as np
                psi_now = self._state.psi
                recalls = self._episodic_memory.recall(
                    psi=psi_now,
                    observation_tags=[],
                    limit=3,
                )
                for rc in recalls:
                    ep = rc.episode
                    trace_dict = getattr(ep, "affective_trace", None)
                    if trace_dict is None:
                        continue
                    trace = AffectiveTrace.from_dict(trace_dict)
                    event = AffectEvent(
                        source="episode_recalled",
                        reward_delta=0.0,
                        rank_delta=0,
                        is_autonomous=False,
                        episode_significance=ep.significance,
                        consecutive_failures=0,
                        consecutive_successes=0,
                        recalled_trace=trace,
                    )
                    self._affect_engine.process(event, state=self._state)
                    result.episodes_recalled += 1
                    log.debug(
                        "Dream recall: episode %s (sig=%.2f) → EPISODE_RECALLED",
                        ep.episode_id, ep.significance,
                    )

            # (b) Mood apaisement — dream calms arousal, valence trends neutral
            eng = self._affect_engine
            if hasattr(eng, "mood"):
                mood = eng.mood
                # Reduce arousal (sleep calms)
                old_arousal = mood.arousal
                mood.arousal = max(0.0, mood.arousal * 0.7)
                # Valence trends toward neutral (emotional reset during rest)
                mood.valence = mood.valence * 0.85
                if old_arousal > mood.arousal:
                    result.mood_apaisement = True
                    log.debug(
                        "Dream apaisement: arousal %.2f→%.2f, valence %.2f",
                        old_arousal, mood.arousal, mood.valence,
                    )

            # (c) UnnamedZone scan — report mature zones
            if hasattr(eng, "zone_tracker"):
                for zone in eng.zone_tracker.zones:
                    if zone.mature:
                        result.unnamed_zones_mature += 1
                if result.unnamed_zones_mature > 0:
                    log.info(
                        "Dream: %d mature unnamed zone(s) detected",
                        result.unnamed_zones_mature,
                    )

        except Exception:
            log.debug("Dream affect processing failed", exc_info=True)

    @staticmethod
    def archive_old_dreams(dream_dir: Path, max_age_days: int = 30) -> int:
        """Archive old dream JSON files to a zstd-compressed JSONL.

        ZERO DELETION: files are moved to dreams_archive.json.zst,
        never deleted. Original JSON files are removed from hot storage
        only after successful archival.

        Args:
            dream_dir: Directory containing dream_*.json files.
            max_age_days: Files older than this are archived.

        Returns:
            Number of files archived.
        """
        if not dream_dir.is_dir():
            return 0

        import time as _time

        cutoff = _time.time() - (max_age_days * 86400)
        archive_path = dream_dir / "dreams_archive.json.zst"
        archived = 0

        # Read existing archive.
        existing_lines: list[str] = []
        if archive_path.exists():
            try:
                import zstandard as zstd

                with open(archive_path, "rb") as f:
                    data = zstd.ZstdDecompressor().decompress(f.read())
                existing_lines = [l for l in data.decode("utf-8").strip().split("\n") if l.strip()]
            except (ImportError, Exception):
                pass

        # Find old dream files.
        for path in sorted(dream_dir.glob("dream_*.json")):
            if path.stat().st_mtime < cutoff:
                try:
                    content = path.read_text(encoding="utf-8")
                    existing_lines.append(content.strip())
                    path.unlink()
                    archived += 1
                except Exception:
                    pass

        if archived > 0:
            jsonl = "\n".join(existing_lines)
            try:
                import zstandard as zstd

                compressed = zstd.ZstdCompressor(level=3).compress(jsonl.encode("utf-8"))
                tmp = archive_path.with_suffix(".tmp")
                with open(tmp, "wb") as f:
                    f.write(compressed)
                tmp.replace(archive_path)
            except ImportError:
                # Fallback: plain JSONL.
                tmp = archive_path.with_suffix(".tmp")
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(jsonl)
                tmp.replace(archive_path)

            log.info("Dream archive: %d files -> %s", archived, archive_path)

        return archived

    @staticmethod
    def cleanup_old_dreams(dream_dir: Path, max_age_days: int = 30) -> int:
        """Alias for archive_old_dreams — backward compatible name."""
        return DreamCycle.archive_old_dreams(dream_dir, max_age_days)

    def run_quick(self) -> DreamResult:
        """Quick version — only Mode 2 (reflection, 30 iterations).

        For frequent dream triggers without overloading.
        """
        start = time.monotonic()
        result = DreamResult(mode="quick")

        # Only reflection, fewer iterations
        result.thought = self._reflection.reflect(max_iterations=30)

        result.graph_stats = self._graph.stats()
        result.duration = time.monotonic() - start

        return result


# Backward-compatible alias (used by existing code that imported DreamCycleV2)
DreamCycleV2 = DreamCycle
