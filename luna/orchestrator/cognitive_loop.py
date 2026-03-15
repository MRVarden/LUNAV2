"""CognitiveLoop — the cognitive heart of Luna.

This module replaces the dead LunaOrchestrator (pipeline 4-agents) with a
unified owner of all subsystems. Every subsystem that was previously scattered
across ChatSession and LunaOrchestrator lives here under one roof.

CognitiveLoop owns the lifecycle of:
- Core engine and LLM bridge
- Consciousness subsystems (Thinker, Decider, CausalGraph, Lexicon, ...)
- Affect and emotion (AffectEngine, EpisodicMemory, ...)
- Dream and self-improvement (DreamCycle, DreamLearning, SelfImprovement, ...)
- Observability (AuditTrail, Prometheus, Redis, Alerting)
- Safety (KillSwitch, Watchdog, RateLimiter, SnapshotManager)
- Autonomy (AutonomyWindow, InitiativeEngine, EndogenousSource, ...)

ChatSession attaches to CognitiveLoop via attach_session() and receives a
SessionHandle for bidirectional communication.

Vague 1: Structure only -- all slots declared.
Vague 2: start()/stop() and persistence implementation.
Vague 3: Subsystem initialization.
Vague 4 (this version): Cognitive tick loop and session attachment.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

# --- Core ---
from luna.core.config import LunaConfig
from luna.core.luna import LunaEngine

# --- LLM ---
from luna.llm_bridge.bridge import LLMBridge

# --- Memory ---
from luna.memory.memory_manager import MemoryManager
from luna.memory.cycle_store import CycleStore

# --- Consciousness ---
from luna.consciousness.thinker import Thinker
from luna.consciousness.causal_graph import CausalGraph
from luna.consciousness.lexicon import Lexicon
from luna.consciousness.affect import AffectEngine
from luna.consciousness.episodic_memory import EpisodicMemory
from luna.consciousness.evaluator import Evaluator
from luna.consciousness.decider import ConsciousnessDecider
from luna.consciousness.learnable_params import LearnableParams
from luna.consciousness.endogenous import EndogenousSource
from luna.consciousness.initiative import InitiativeEngine
from luna.consciousness.observation_factory import ObservationCandidate, ObservationFactory
from luna.consciousness.watcher import EnvironmentWatcher, WatcherEvent, WatcherEventType

# --- Dream ---
from luna.dream.dream_cycle import DreamCycle, DreamResult, LegacyDreamCycle
from luna.dream.dream_journal import DreamJournal
from luna.dream.learning import DreamLearning
from luna.dream.priors import DreamPriors
from luna.dream.reflection import DreamReflection
from luna.dream.simulation import DreamSimulation

# --- LLM health ---
from luna.llm_bridge.circuit_breaker import CircuitBreaker, CircuitState

# --- Synthesis ---
from luna.consciousness.synthesis import Synthesis, SynthesisReport

# --- Metrics ---
from luna.metrics.tracker import MetricSource, MetricTracker

# --- Observability ---
from luna.observability.audit_trail import AuditEvent, AuditTrail
from luna.observability.redis_store import RedisMetricsStore
from luna.observability.prometheus_exporter import PrometheusExporter
from luna.observability.alerting import AlertConfig, AlertManager

# --- Safety ---
from luna.safety.kill_switch import KillSwitch
from luna.safety.watchdog import Watchdog
from luna.safety.rate_limiter import RateLimiter
from luna.safety.snapshot_manager import SnapshotManager
from luna.safety.state_backup import StateBackup

# --- Fingerprint ---
from luna.fingerprint.ledger import FingerprintLedger

# --- Heartbeat & Sleep ---
from luna.heartbeat import Heartbeat
from luna.dream.sleep_manager import SleepManager
from luna.dream.awakening import Awakening

# --- Autonomy ---
from luna.autonomy.window import AutonomyWindow


# --- Schemas ---
from luna_common.schemas.cycle import RewardVector

# --- Constants ---
from luna_common.constants import INV_PHI, INV_PHI3, PHI, METRIC_NAMES

if TYPE_CHECKING:
    from luna.consciousness.self_improvement import SelfImprovement

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Session attachment handle
# ──────────────────────────────────────────────────────────────────────

@dataclass
class SessionHandle:
    """Handle returned when a ChatSession attaches to the cognitive loop.

    Provides a queue for endogenous impulses that the session can display
    to the user, plus metadata about the attachment.
    """

    impulse_queue: asyncio.Queue  # endogenous impulses for display
    attached_at: float = field(default_factory=time.monotonic)
    autonomous_journal: list[dict] = field(default_factory=list)  # impulses from while away


# ──────────────────────────────────────────────────────────────────────
# CognitiveLoop
# ──────────────────────────────────────────────────────────────────────

class CognitiveLoop:
    """Unified owner of all Luna subsystems.

    Replaces the dead LunaOrchestrator and absorbs subsystem ownership
    from ChatSession. Every subsystem is declared here; ChatSession
    becomes a thin I/O adapter that attaches via ``attach_session()``.

    Attributes are split by convention:
    - Public (no underscore): part of the API contract read by dashboard,
      session, and external consumers.
    - Private (underscore): internal infrastructure, not accessed directly
      by sessions.
    """

    def __init__(self, config: LunaConfig) -> None:
        # ── Core infrastructure ──────────────────────────────────────
        self.config: LunaConfig = config
        self.engine: LunaEngine = LunaEngine(config)

        # ── LLM bridge ──────────────────────────────────────────────
        self._llm: LLMBridge | None = None

        # ── Memory ──────────────────────────────────────────────────
        self.memory: MemoryManager | None = None
        self.cycle_store: CycleStore | None = None

        # ── Consciousness — structured cognition (v3.5+) ────────────
        self.thinker: Thinker | None = None
        self.causal_graph: CausalGraph | None = None
        self.lexicon: Lexicon | None = None
        self._decider: ConsciousnessDecider = ConsciousnessDecider()

        # ── Affect & episodic ────────────────────────────────────────
        self.affect_engine: AffectEngine | None = None
        self.episodic_memory: EpisodicMemory | None = None

        # ── Evaluation & learning ────────────────────────────────────
        self.evaluator: Evaluator | None = None
        self.learnable_params: LearnableParams | None = None
        self.self_improvement: SelfImprovement | None = None
        self.metric_tracker: MetricTracker = MetricTracker()

        # ── Dream ────────────────────────────────────────────────────
        self.dream_cycle: DreamCycle | None = None
        self._dream_learning: DreamLearning | None = None
        self.dream_priors: DreamPriors | None = None
        self.dream_journal: DreamJournal | None = None

        # ── LLM health (v6.0) ────────────────────────────────────────
        self.circuit_breaker: CircuitBreaker = CircuitBreaker()

        # ── Synthesis (v6.0) ──────────────────────────────────────────
        self.synthesis: Synthesis | None = None
        self.last_synthesis_report: SynthesisReport | None = None

        # ── Endogenous & initiative (v5.1+) ──────────────────────────
        self.endogenous: EndogenousSource | None = None
        self.initiative_engine: InitiativeEngine | None = None

        # ── Perception (v5.1+) ───────────────────────────────────────
        self.watcher: EnvironmentWatcher | None = None
        self.observation_factory: ObservationFactory | None = None

        # ── Autonomy (v4.0+) ────────────────────────────────────────
        self.autonomy_window: AutonomyWindow | None = None

        # ── Observability ────────────────────────────────────────────
        self._audit: AuditTrail | None = None
        self._redis_store: RedisMetricsStore | None = None
        self._prometheus: PrometheusExporter | None = None
        self._alert_manager: AlertManager | None = None

        # ── Safety ───────────────────────────────────────────────────
        self._kill_switch: KillSwitch | None = None
        self._watchdog: Watchdog | None = None
        self._rate_limiter: RateLimiter | None = None
        self._snapshot_manager: SnapshotManager | None = None
        self._state_backup: StateBackup | None = None

        # ── Heartbeat & sleep ────────────────────────────────────────
        self._heartbeat: Heartbeat | None = None
        self._sleep_manager: SleepManager | None = None

        # ── Fingerprint ────────────────────────────────────────────
        self.fingerprint_ledger: FingerprintLedger | None = None

        # ── Telemetry ────────────────────────────────────────────────
        self._telemetry_collector: object | None = None  # removed with pipeline

        # ── Internal state ───────────────────────────────────────────
        self._reward_history: list[RewardVector] = []
        self._running: bool = False
        self._last_activity: float = time.monotonic()
        self._session_handle: SessionHandle | None = None
        self._tick_task: asyncio.Task | None = None
        self._tick_count: int = 0
        self._autonomous_journal: list[dict] = []  # impulses collected while no session

    # ──────────────────────────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────────────────────────

    def init_subsystems(self) -> None:
        """Initialize all subsystems without starting background tasks.

        Call this when you need subsystems ready but don't want the
        daemon (tick loop, heartbeat) running.  Used by ChatSession
        when it auto-creates a loop.

        Order:
        1. Engine initialization (cognitive state, phi_scorer, identity).
        2. Decider with identity context.
        3. PhiScorer restore/bootstrap + MetricTracker seeding.
        4. LLM bridge (optional, degrades gracefully).
        5. Base infrastructure (observability, safety, heartbeat, memory).
        6. v3.5+ cognitive components (thinker, causal graph, dream, etc.).
        7. Re-create Decider with all available components (affect, params).
        """
        self.engine.initialize()

        # Decider with identity context.
        if self.engine.identity_context is not None:
            self._decider = ConsciousnessDecider(
                identity_context=self.engine.identity_context,
            )

        # PhiScorer + MetricTracker.
        self._init_phi_scorer()

        # LLM bridge.
        self._init_llm()

        # Base infrastructure (observability, safety, heartbeat, memory).
        self._init_base_subsystems()

        # v3.5+ cognitive components.
        self._init_v35_components()

        # Re-create Decider with all available components.
        if self.affect_engine is not None or self.learnable_params is not None:
            self._decider = ConsciousnessDecider(
                params=self.learnable_params,
                identity_context=self.engine.identity_context,
                affect_engine=self.affect_engine,
            )

        # Load autonomous journal from previous session.
        self._load_journal()

        # Load dream priors from previous session.
        mem_root = self.config.resolve(self.config.memory.fractal_root)
        priors_path = mem_root / "dream_priors.json"
        if priors_path.exists():
            self.dream_priors = DreamPriors.load(priors_path)

        self._running = True

    async def start(self) -> None:
        """Full lifecycle: init subsystems + start daemon background tasks."""
        self.init_subsystems()
        self._start_daemon()

    def _start_daemon(self) -> None:
        """Start heartbeat + tick background tasks."""
        if self._heartbeat is not None:
            self._heartbeat.start()
            if self._kill_switch is not None and self._heartbeat._task is not None:
                self._kill_switch.register_task(self._heartbeat._task)

        self._tick_task = asyncio.create_task(self._cognitive_tick_loop())
        log.info(
            "CognitiveLoop daemon started (tick=%.1fs, max=%.1fs)",
            self.config.cognitive_loop.tick_interval,
            self.config.cognitive_loop.max_tick_interval,
        )

    async def stop(self) -> None:
        """Graceful shutdown — save state, stop background tasks."""
        self._running = False

        # Cancel cognitive tick.
        if self._tick_task is not None:
            self._tick_task.cancel()
            try:
                await self._tick_task
            except asyncio.CancelledError:
                pass
            self._tick_task = None

        # Stop watcher.
        if self.watcher is not None:
            try:
                await self.watcher.stop()
            except Exception:
                log.debug("Watcher stop failed", exc_info=True)

        # Stop heartbeat.
        if self._heartbeat is not None:
            await self._heartbeat.stop()

        # Save state.
        self.save_v35_state()
        self.save_checkpoint()

        # Final resilience backup on shutdown.
        if self._state_backup is not None:
            try:
                path = self._state_backup.create_backup()
                if path is not None:
                    log.info("Shutdown resilience backup: %s", path.name)
            except Exception:
                log.warning("Shutdown resilience backup failed", exc_info=True)

        # Audit shutdown.
        if self._audit is not None:
            await self._audit.record(
                AuditEvent.create("shutdown", data={"source": "cognitive_loop"}),
            )

        log.info("CognitiveLoop stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    # ──────────────────────────────────────────────────────────────────
    # Initialization helpers (called from start)
    # ──────────────────────────────────────────────────────────────────

    def _init_llm(self) -> None:
        """Attempt to create the LLM provider. Sets self._llm or None."""
        try:
            from luna.llm_bridge.providers import create_provider

            self._llm = create_provider(self.config.llm)
            log.info(
                "LLM bridge initialized: %s/%s",
                self.config.llm.provider,
                self.config.llm.model,
            )
        except Exception as exc:
            log.warning(
                "LLM unavailable (%s/%s): %s",
                self.config.llm.provider,
                self.config.llm.model,
                exc,
            )
            self._llm = None

    def _init_phi_scorer(self) -> None:
        """Restore or bootstrap PhiScorer metrics and seed MetricTracker."""
        if self.engine.phi_metrics_restored:
            log.info(
                "PhiScorer restored from checkpoint (score=%.4f)",
                self.engine.phi_scorer.score(),
            )
            snapshot = getattr(self.engine.consciousness, "phi_metrics_snapshot", None)
            if snapshot:
                for name, entry in snapshot.items():
                    if name not in METRIC_NAMES:
                        log.warning("Ignoring unknown metric in checkpoint: %s", name)
                        continue
                    value = entry.get("value", INV_PHI)
                    source_str = entry.get("source", "bootstrap")
                    source = (
                        MetricSource(source_str)
                        if source_str in MetricSource._value2member_map_
                        else MetricSource.BOOTSTRAP
                    )
                    self.metric_tracker.record(name, value, source)
        else:
            log.warning("Seeding PhiScorer with bootstrap values (%.3f)", INV_PHI)
            for metric_name in METRIC_NAMES:
                self.engine.phi_scorer.update(metric_name, INV_PHI)
                self.metric_tracker.record(metric_name, INV_PHI, MetricSource.BOOTSTRAP)

    def _init_base_subsystems(self) -> None:
        """Initialize observability, safety, heartbeat, sleep, and memory."""
        # ── Observability ──────────────────────────────────────────────
        audit_path = self.config.resolve(self.config.observability.audit_trail_file)
        self._audit = AuditTrail(audit_path)

        redis_url = self.config.observability.redis_url
        self._redis_store = RedisMetricsStore(redis_url) if redis_url else RedisMetricsStore()

        self._prometheus = PrometheusExporter(
            enabled=self.config.observability.prometheus_enabled,
        )

        webhook_url = self.config.observability.alert_webhook_url
        self._alert_manager = (
            AlertManager(AlertConfig(webhook_url=webhook_url)) if webhook_url else None
        )

        # ── Memory ─────────────────────────────────────────────────────
        try:
            self.memory = MemoryManager(self.config)
            log.info("Memory manager initialized: %s", self.memory.root)
        except Exception:
            log.warning("Memory unavailable", exc_info=True)
            self.memory = None

        # ── Safety ─────────────────────────────────────────────────────
        self._kill_switch = KillSwitch(enabled=self.config.safety.enabled)
        self._rate_limiter = RateLimiter(
            max_generations_per_hour=self.config.safety.max_generations_per_hour,
            max_commits_per_hour=self.config.safety.max_commits_per_hour,
        )
        self._watchdog = Watchdog(
            kill_switch=self._kill_switch,
            threshold=self.config.safety.watchdog_threshold,
        )
        snapshot_dir = self.config.resolve(self.config.safety.snapshot_dir)
        self._snapshot_manager = SnapshotManager(
            snapshot_dir=snapshot_dir,
            max_snapshots=self.config.safety.max_snapshots,
            retention_days=self.config.safety.retention_days,
        )

        # ── State backup (resilience) ────────────────────────────────
        if self.config.backup.enabled:
            memory_root = self.config.resolve(self.config.memory.fractal_root)
            backup_dir = self.config.resolve(self.config.backup.backup_dir)
            self._state_backup = StateBackup(
                memory_root=memory_root,
                backup_dir=backup_dir,
                max_backups=self.config.backup.max_backups,
            )
            log.info(
                "StateBackup initialized: %s (max %d, every %d ticks)",
                backup_dir,
                self.config.backup.max_backups,
                self.config.backup.backup_interval_ticks,
            )

        # ── Fingerprint ────────────────────────────────────────────────
        if self.config.fingerprint.enabled:
            ledger_path = self.config.resolve(self.config.fingerprint.ledger_file)
            self.fingerprint_ledger = FingerprintLedger(ledger_path)

        # ── Legacy dream + heartbeat + sleep (backward compat) ─────────
        _legacy_dream = LegacyDreamCycle(self.engine, self.config, memory=self.memory)
        self._heartbeat = Heartbeat(self.engine, self.config, dream_cycle=_legacy_dream)

        awakening = Awakening(engine=self.engine)
        self._sleep_manager = SleepManager(
            dream_cycle=_legacy_dream,
            heartbeat=self._heartbeat,
            max_dream_duration=self.config.dream.max_dream_duration,
            awakening=awakening,
            engine=self.engine,
        )
        self._heartbeat.set_sleep_manager(self._sleep_manager)

        self._heartbeat.set_observability(
            audit=self._audit,
            alert_manager=self._alert_manager,
            prometheus=self._prometheus,
            redis_store=self._redis_store,
            kill_switch=self._kill_switch,
        )

        log.info(
            "Base subsystems wired (observability + safety + heartbeat + sleep + memory)",
        )

    def _init_v35_components(self) -> None:
        """Initialize v3.5+ structured cognition components.

        Creates: CausalGraph, Lexicon, Thinker, DreamLearning,
        DreamReflection, DreamSimulation, DreamCycle, EpisodicMemory,
        AffectEngine, LearnableParams, Evaluator, InitiativeEngine,
        EndogenousSource, SelfImprovement, EnvironmentWatcher, CycleStore,
        TelemetryCollector, ObservationFactory, AutonomyWindow.

        Loads persisted state from memory_fractal if available.
        Tolerates errors — all components default to None on failure.
        """
        cs = self.engine.consciousness
        if cs is None:
            log.warning("v3.5 init skipped — no cognitive state")
            return

        mem_root = self.config.resolve(self.config.memory.fractal_root)

        try:
            # CausalGraph — Luna's learned knowledge.
            self.causal_graph = CausalGraph()
            graph_path = mem_root / "causal_graph.json"
            if graph_path.exists():
                self.causal_graph.load(graph_path)
                stats = self.causal_graph.stats()
                log.info(
                    "CausalGraph loaded: %d nodes, %d edges",
                    stats["node_count"], stats["edge_count"],
                )

            # Lexicon — autonomous vocabulary.
            lexicon_path = mem_root / "lexicon.json"
            self.lexicon = Lexicon(persist_path=lexicon_path)
            if lexicon_path.exists():
                self.lexicon.load()
                log.info("Lexicon loaded: %d words", self.lexicon.size())

            # Thinker — structured reasoning without LLM.
            phi_metrics: dict = {}
            if hasattr(self.engine.phi_scorer, "snapshot_values"):
                phi_metrics = self.engine.phi_scorer.snapshot_values()
            self.thinker = Thinker(
                state=cs,
                metrics=phi_metrics or None,
                causal_graph=self.causal_graph,
                lexicon=self.lexicon,
                identity_context=self.engine.identity_context,
            )

            # DreamLearning — skill extraction from history.
            skills_path = mem_root / "dream_skills.json"
            self._dream_learning = DreamLearning(skills_path=skills_path)
            if skills_path.exists():
                self._dream_learning.load()
                log.info(
                    "DreamLearning loaded: %d skills",
                    len(self._dream_learning.get_skills()),
                )

            # DreamReflection + DreamSimulation + DreamCycle.
            reflection = DreamReflection(
                thinker=self.thinker,
                causal_graph=self.causal_graph,
            )
            simulation = DreamSimulation(
                thinker=self.thinker,
                state=cs,
            )

            # EpisodicMemory.
            ep_path = mem_root / "episodic_memory.json"
            self.episodic_memory = EpisodicMemory(persist_path=ep_path)
            if ep_path.exists():
                self.episodic_memory.load()
                log.info("EpisodicMemory loaded: %d episodes", self.episodic_memory.size)

            # v5.1 Convergence Phase 1 — Identity incarnation.
            # Bootstrap founding episodes on first ever start (empty memory).
            if self.episodic_memory.size == 0:
                try:
                    from luna.identity.bootstrap import bootstrap_founding_episodes

                    bundle = getattr(self.engine, "identity_bundle", None)
                    if bundle is not None:
                        count = bootstrap_founding_episodes(bundle, self.episodic_memory)
                        log.info("Identity bootstrap: %d founding episodes", count)
                except Exception:
                    log.debug("Identity bootstrap skipped", exc_info=True)

            # PlanAffect — AffectEngine (continuous emotions).
            affect_path = mem_root / "affect_engine.json"
            self.affect_engine = AffectEngine()
            if affect_path.exists():
                import json as _json

                with open(affect_path) as _f:
                    self.affect_engine = AffectEngine.from_dict(_json.load(_f))
                log.info(
                    "AffectEngine loaded (v=%.2f, mood_v=%.2f)",
                    self.affect_engine.affect.valence,
                    self.affect_engine.mood.valence,
                )

            # v4.0 Emergence — LearnableParams + Evaluator BEFORE DreamCycle.
            params_path = mem_root / "learnable_params.json"
            self.learnable_params = LearnableParams.load(params_path)
            log.info("LearnableParams loaded: %s", self.learnable_params)

            self.evaluator = Evaluator(
                psi_0=tuple(float(x) for x in cs.psi0),
                identity_context=self.engine.identity_context,
            )

            # DreamJournal — persistent cumulative dream memory (append-only JSONL).
            journal_path = mem_root / "dream_journal.jsonl"
            self.dream_journal = DreamJournal(journal_path)
            if self.dream_journal.count > 0:
                log.info("DreamJournal loaded: %d entries", self.dream_journal.count)

            # DreamCycle — after EpisodicMemory + AffectEngine + Params + Evaluator.
            # Synthesis is set to None here; will be wired after CycleStore init below.
            self.dream_cycle = DreamCycle(
                thinker=self.thinker,
                causal_graph=self.causal_graph,
                learning=self._dream_learning,
                reflection=reflection,
                simulation=simulation,
                state=cs,
                evaluator=self.evaluator,
                params=self.learnable_params,
                affect_engine=self.affect_engine,
                episodic_memory=self.episodic_memory,
                dream_journal=self.dream_journal,
            )

            # InitiativeEngine.
            self.initiative_engine = InitiativeEngine()

            # v5.1 Convergence — EndogenousSource.
            self.endogenous = EndogenousSource()

            # v5.1 Convergence Phase 4 — SelfImprovement.
            from luna.consciousness.self_improvement import SelfImprovement

            self.self_improvement = SelfImprovement(
                thinker=self.thinker,
                causal_graph=self.causal_graph,
                skills=self._dream_learning,
                state=cs,
            )
            improvement_path = mem_root / "self_improvement.json"
            self.self_improvement.load(improvement_path)
            log.info(
                "SelfImprovement loaded (threshold=%.3f)",
                self.self_improvement.threshold,
            )

            # EnvironmentWatcher (continuous perception).
            project_root = self.config.resolve(Path("."))
            if (project_root / ".git").exists():
                self.watcher = EnvironmentWatcher(project_root)

            # CycleStore — cycle record persistence.
            cycles_dir = mem_root / "cycles"
            self.cycle_store = CycleStore(cycles_dir)

            # Synthesis (v6.0) — retrospective analysis during dream.
            self.synthesis = Synthesis(cycle_store=self.cycle_store)
            if self.dream_cycle is not None:
                self.dream_cycle._synthesis = self.synthesis

            # TelemetryCollector removed with pipeline dissociation.
            self._telemetry_collector = None

            # ObservationFactory — custom sensor promotion.
            obs_path = mem_root / "observation_factory.json"
            if obs_path.exists():
                self.observation_factory = ObservationFactory.load(obs_path)
                promoted = self.observation_factory.promoted_candidates()
                if promoted:
                    log.info("ObservationFactory loaded: %d promoted sensors", len(promoted))
            else:
                self.observation_factory = ObservationFactory(step=cs.step_count)

            # Load recent reward history for dominance rank computation.
            try:
                recent = self.cycle_store.read_recent(20)
                self._reward_history = [
                    r.reward for r in recent if r.reward is not None
                ]
            except Exception:
                log.debug("Could not load reward history", exc_info=True)

            # AutonomyWindow — ghost (Phase A) + real apply (Phase B).
            snap_dir = mem_root / "snapshots"
            snap_manager = SnapshotManager(snap_dir)
            autonomy_mode = getattr(self.config.orchestrator, "autonomy", "supervised")
            initial_w = 1 if autonomy_mode == "autonomous" else 0
            self.autonomy_window = AutonomyWindow(
                snapshot_manager=snap_manager,
                params=self.learnable_params,
                initial_w=initial_w,
                project_root=project_root,
            )

            log.info(
                "v3.5+v4.0 components initialized "
                "(Thinker + CausalGraph + Lexicon + DreamV2 + EpisodicMemory + "
                "Initiative + SelfImprovement + Watcher + Affect + Params + "
                "Evaluator + CycleStore + AutonomyGhost)",
            )

        except Exception:
            log.warning("v3.5 component initialization failed — degraded mode", exc_info=True)
            self.thinker = None
            self.causal_graph = None
            self.lexicon = None
            self._dream_learning = None
            self.dream_cycle = None
            self.episodic_memory = None
            self.affect_engine = None
            self.initiative_engine = None
            self.watcher = None
            self.endogenous = None
            self.self_improvement = None
            self.learnable_params = None
            self.evaluator = None
            self.cycle_store = None
            self._telemetry_collector = None
            self.observation_factory = None
            self.autonomy_window = None

    # ──────────────────────────────────────────────────────────────────
    # Persistence
    # ──────────────────────────────────────────────────────────────────

    def build_phi_snapshot(self) -> dict:
        """Build enriched phi_metrics dict: {name: {value, source, timestamp}}.

        Every metric gets an explicit source (never omitted) so the checkpoint
        is self-describing and restores correctly without defaulting.
        """
        phi_snapshot = self.engine.phi_scorer.snapshot()
        sources = self.metric_tracker.snapshot_sources()
        for name in phi_snapshot:
            phi_snapshot[name]["source"] = sources.get(name, "bootstrap")
            entry = self.metric_tracker.get(name)
            if entry is not None:
                phi_snapshot[name]["timestamp"] = entry.timestamp.isoformat()
        return phi_snapshot

    def save_checkpoint(self) -> None:
        """Save cognitive checkpoint with PhiScorer metrics."""
        if self.engine.consciousness is None:
            return
        ckpt = self.config.resolve(self.config.consciousness.checkpoint_file)
        phi_snapshot = self.build_phi_snapshot()
        self.engine.consciousness.save_checkpoint(
            ckpt,
            backup=self.config.consciousness.backup_on_save,
            phi_metrics=phi_snapshot,
        )
        log.info(
            "Checkpoint saved (bootstrap_ratio=%.2f)",
            self.metric_tracker.bootstrap_ratio(),
        )

    def save_v35_state(self) -> None:
        """Persist v3.5+ component state (causal graph, lexicon, episodes, etc.)."""
        import json as _json

        mem_root = self.config.resolve(self.config.memory.fractal_root)
        try:
            if self.causal_graph is not None:
                self.causal_graph.persist(mem_root / "causal_graph.json")
            if self.lexicon is not None:
                self.lexicon.save()
            if self._dream_learning is not None:
                self._dream_learning.persist()
            if self.episodic_memory is not None:
                self.episodic_memory.save()
            if self.affect_engine is not None:
                affect_path = mem_root / "affect_engine.json"
                with open(affect_path, "w") as _f:
                    _json.dump(self.affect_engine.to_dict(), _f)
            if self.learnable_params is not None:
                self.learnable_params.save(mem_root / "learnable_params.json")
            if self.observation_factory is not None:
                self.observation_factory.save(mem_root / "observation_factory.json")
            if self.self_improvement is not None:
                self.self_improvement.persist(mem_root / "self_improvement.json")
            if self.dream_priors is not None:
                self.dream_priors.save(mem_root / "dream_priors.json")
            log.debug("v3.5+v4.0 state saved")
        except Exception:
            log.warning("v3.5 state save failed", exc_info=True)

    # ──────────────────────────────────────────────────────────────────
    # Autonomous journal -- impulses collected while no session
    # ──────────────────────────────────────────────────────────────────

    def _journal_path(self) -> Path:
        """Path to the autonomous impulse journal."""
        return self.config.resolve(self.config.memory.fractal_root) / "autonomous_journal.json"

    def _load_journal(self) -> None:
        """Load journal from disk (survives restarts)."""
        path = self._journal_path()
        if path.exists():
            try:
                import json as _json
                self._autonomous_journal = _json.loads(path.read_text())
                log.info("Autonomous journal loaded: %d entries", len(self._autonomous_journal))
            except Exception:
                log.debug("Journal load failed", exc_info=True)
                self._autonomous_journal = []

    def _save_journal(self) -> None:
        """Persist journal to disk."""
        path = self._journal_path()
        try:
            import json as _json
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_json.dumps(self._autonomous_journal, indent=2))
        except Exception:
            log.debug("Journal save failed", exc_info=True)

    # ──────────────────────────────────────────────────────────────────
    # Cognitive tick loop -- Luna's heartbeat between sessions
    # ──────────────────────────────────────────────────────────────────

    async def _cognitive_tick_loop(self) -> None:
        """Background loop: micro-cycles that keep Luna alive.

        Adaptive interval:
        - Session attached: base interval (fast responsiveness).
        - No session: base x PHI (~30s), capped at max_tick_interval.

        Each tick performs lightweight cognitive housekeeping -- NO LLM calls.
        """
        base = self.config.cognitive_loop.tick_interval
        cap = self.config.cognitive_loop.max_tick_interval

        while self._running:
            # Adaptive interval.
            if self._session_handle is not None:
                interval = base
            else:
                interval = min(base * PHI, cap)

            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                return

            if not self._running:
                return

            try:
                await self._do_tick()
            except Exception:
                log.warning("Tick %d failed", self._tick_count, exc_info=True)

    async def _do_tick(self) -> None:
        """Execute one cognitive micro-cycle.

        Steps:
        1. PERCEIVE  -- drain Watcher events -> ObservationFactory
        2. FEEL      -- register affect state in EndogenousSource
        3. SENSE     -- register high-severity watcher events in EndogenousSource
        4. IMPROVE   -- every 5 ticks: SelfImprovement.propose() -> EndogenousSource
        5. OBSERVE   -- ObservationFactory.tick() (promotions/demotions)
        6. COLLECT   -- EndogenousSource.collect() -> route impulse to session
        7. HEARTBEAT -- engine.idle_step() (only if no session attached)
        8. DREAM     -- if idle > threshold and no session -> autonomous dream
        9. AUTOSAVE  -- every N ticks -> save state
        """
        self._tick_count += 1
        cs = self.engine.consciousness
        if cs is None:
            return

        # Only log ticks in autonomous mode — don't pollute chat session.
        if self._session_handle is None:
            log.info(
                "Tick %d | ψ=[%.3f,%.3f,%.3f,%.3f] | step=%d | autonomous",
                self._tick_count,
                *cs.psi[:4],
                cs.step_count,
            )
        else:
            log.debug(
                "Tick %d | step=%d | attached",
                self._tick_count, cs.step_count,
            )

        # 1. PERCEIVE -- drain watcher events.
        watcher_events: list[WatcherEvent] = []
        if self.watcher is not None:
            try:
                watcher_events = self.watcher.drain_events()
                if watcher_events and self.observation_factory is not None:
                    self._feed_watcher_to_factory(watcher_events)
            except Exception:
                log.debug("Tick perceive failed", exc_info=True)

        # 2. FEEL -- register affect in endogenous source.
        if self.endogenous is not None and self.affect_engine is not None:
            try:
                affect = self.affect_engine.affect
                self.endogenous.register_affect(
                    arousal=affect.arousal,
                    valence=affect.valence,
                    cause="tick",
                )
            except Exception:
                log.debug("Tick feel failed", exc_info=True)

        # 3. SENSE -- register high-severity watcher events.
        if self.endogenous is not None:
            for ev in watcher_events:
                if ev.severity >= INV_PHI3:
                    try:
                        self.endogenous.register_watcher_event(
                            description=ev.description,
                            severity=ev.severity,
                            component=ev.component,
                        )
                    except Exception:
                        pass

        # 4. IMPROVE -- every 5 ticks.
        if self._tick_count % 5 == 0 and self.self_improvement is not None:
            try:
                proposal = self.self_improvement.propose()
                if proposal is not None and self.endogenous is not None:
                    self.endogenous.register_proposal(
                        description=proposal.description,
                        confidence=proposal.confidence,
                    )
            except Exception:
                log.debug("Tick improve failed", exc_info=True)

        # 5. OBSERVE -- ObservationFactory tick (promotions/demotions).
        if self.observation_factory is not None:
            try:
                self.observation_factory.tick()
            except Exception:
                log.debug("Tick observe failed", exc_info=True)

        # 6. COLLECT -- EndogenousSource.collect() -> route to session.
        # When a ChatSession is attached, IT owns collect() (via
        # _watch_endogenous which routes impulses through the LLM).
        # The tick only collects when autonomous (no session).
        if self.endogenous is not None and self._session_handle is None:
            try:
                impulse = self.endogenous.collect(cs.step_count)
                if impulse is not None:
                    log.info("Autonomous impulse: %s", impulse.message[:60])
                    # Journal the impulse for the next session.
                    from datetime import datetime, timezone
                    entry = {
                        "source": impulse.source.value,
                        "message": impulse.message,
                        "urgency": round(impulse.urgency, 3),
                        "component": impulse.component,
                        "time": datetime.now(timezone.utc).isoformat(),
                        "tick": self._tick_count,
                    }
                    self._autonomous_journal.append(entry)
                    # Cap journal size (Fibonacci).
                    if len(self._autonomous_journal) > 13:
                        self._autonomous_journal = self._autonomous_journal[-13:]
                    self._save_journal()
            except Exception:
                log.debug("Tick collect failed", exc_info=True)

        # 7. HEARTBEAT -- idle step only if no session attached.
        if self._session_handle is None:
            try:
                self.engine.idle_step()
            except Exception:
                log.debug("Tick heartbeat failed", exc_info=True)

        # 8. DREAM CHECK -- autonomous dream when idle.
        if self._session_handle is None:
            idle = time.monotonic() - self._last_activity
            threshold = self.config.cognitive_loop.idle_dream_threshold
            if idle >= threshold:
                await self._trigger_autonomous_dream()
                self._last_activity = time.monotonic()

        # 9. AUTOSAVE -- periodic state save.
        autosave_every = self.config.cognitive_loop.autosave_ticks
        if autosave_every > 0 and self._tick_count % autosave_every == 0:
            try:
                self.save_v35_state()
                self.save_checkpoint()
                log.debug("Autosave at tick %d", self._tick_count)
            except Exception:
                log.warning("Autosave failed", exc_info=True)

        # 10. BACKUP -- periodic resilience backup of critical state.
        if self._state_backup is not None:
            backup_every = self.config.backup.backup_interval_ticks
            if backup_every > 0 and self._tick_count % backup_every == 0:
                try:
                    path = self._state_backup.create_backup()
                    if path is not None:
                        log.info("Resilience backup at tick %d: %s", self._tick_count, path.name)
                except Exception:
                    log.warning("Resilience backup failed at tick %d", self._tick_count, exc_info=True)

    def _feed_watcher_to_factory(self, events: list[WatcherEvent]) -> None:
        """Feed significant watcher events to ObservationFactory."""
        _PATTERN_MAP = {
            WatcherEventType.FILE_CHANGED: "env:file_churn",
            WatcherEventType.GIT_STATE_CHANGED: "env:git_shift",
            WatcherEventType.STABILITY_SHIFT: "env:stability_change",
            WatcherEventType.IDLE_LONG: "env:idle_period",
        }
        _PREDICTED = {
            WatcherEventType.FILE_CHANGED: "integration_drop",
            WatcherEventType.GIT_STATE_CHANGED: "perception_shift",
            WatcherEventType.STABILITY_SHIFT: "phi_shift",
            WatcherEventType.IDLE_LONG: "reflexion_drift",
        }
        for ev in events:
            if ev.severity < INV_PHI3:
                continue
            pattern_id = _PATTERN_MAP.get(ev.event_type)
            if pattern_id is None:
                continue
            existing = self.observation_factory.get_candidate(pattern_id)
            if existing is None:
                candidate = ObservationCandidate(
                    pattern_id=pattern_id,
                    condition=ev.description,
                    predicted_outcome=_PREDICTED.get(ev.event_type, "unknown"),
                    component=ev.component,
                )
                self.observation_factory.add_candidate(candidate)
                self.observation_factory.observe(pattern_id, outcome_matched=True)
            else:
                self.observation_factory.observe(pattern_id, outcome_matched=True)

    def _populate_dream_priors(self, dream_result: DreamResult) -> None:
        """Extract weak priors from dream outputs for cognitive injection."""
        from luna.dream.priors import populate_dream_priors
        self.dream_priors = populate_dream_priors(
            dream_result, previous_priors=self.dream_priors,
        )

    async def _trigger_autonomous_dream(self) -> None:
        """Trigger a dream cycle when Luna has been idle long enough."""
        cs = self.engine.consciousness
        if cs is None or len(cs.history) < 10:
            return

        log.info("Autonomous dream triggered (idle >= threshold)")

        try:
            if self.dream_cycle is not None and self.dream_cycle.is_mature():
                recent_cycles = None
                if self.cycle_store is not None:
                    try:
                        recent_cycles = self.cycle_store.read_recent(10) or None
                    except Exception:
                        log.debug("Could not load recent cycles for dream", exc_info=True)
                psi0_hist = None
                if self.dream_priors is not None and self.dream_priors.psi0_delta_history:
                    psi0_hist = self.dream_priors.psi0_delta_history
                dream_result: DreamResult = self.dream_cycle.run(
                    history=None,
                    recent_cycles=recent_cycles,
                    psi0_delta_history=psi0_hist,
                )
                log.info(
                    "Autonomous DreamV2: %.2fs, %d skills, %d sims, mode=%s",
                    dream_result.duration,
                    len(dream_result.skills_learned),
                    len(dream_result.simulations),
                    dream_result.mode,
                )
                # Populate dream priors for cognitive injection.
                self._populate_dream_priors(dream_result)
                # Sync Evaluator's identity anchor after Ψ₀ consolidation.
                if dream_result.psi0_applied and self.evaluator is not None:
                    new_psi0 = tuple(float(x) for x in cs.psi0)
                    self.evaluator._psi_0 = new_psi0
                if self.endogenous is not None:
                    insight = (
                        f"{len(dream_result.skills_learned)} competences, "
                        f"{len(dream_result.simulations)} simulations"
                    )
                    self.endogenous.register_dream_insight(insight)
            else:
                # Legacy fallback.
                from luna.dream._legacy_cycle import DreamCycle as _LegacyCycle

                dream = _LegacyCycle(self.engine, self.config, self.memory)
                report = await dream.run()
                log.info(
                    "Autonomous DreamV1: %.2fs, history %d -> %d",
                    report.total_duration,
                    report.history_before,
                    report.history_after,
                )
                if self.endogenous is not None:
                    self.endogenous.register_dream_insight(
                        getattr(report, "insight", "dream complete"),
                    )

            self.save_v35_state()
            self.save_checkpoint()

            # Post-dream resilience backup — dreams consolidate critical state.
            if self._state_backup is not None:
                try:
                    path = self._state_backup.create_backup()
                    if path is not None:
                        log.info("Post-dream resilience backup: %s", path.name)
                except Exception:
                    log.warning("Post-dream resilience backup failed", exc_info=True)
        except Exception:
            log.warning("Autonomous dream failed", exc_info=True)

    # ──────────────────────────────────────────────────────────────────
    # Session attachment
    # ──────────────────────────────────────────────────────────────────

    def attach_session(self) -> SessionHandle:
        """Attach a ChatSession -- adjusts tick behavior.

        Transfers the autonomous journal to the handle so the session
        can display what Luna experienced while the user was away.
        """
        handle = SessionHandle(
            impulse_queue=asyncio.Queue(),
            autonomous_journal=list(self._autonomous_journal),
        )
        # Clear journal — it's been handed off.
        self._autonomous_journal.clear()
        self._save_journal()
        self._session_handle = handle
        self._last_activity = time.monotonic()
        log.info(
            "Session attached (journal: %d entries transferred)",
            len(handle.autonomous_journal),
        )
        return handle

    def detach_session(self, handle: SessionHandle) -> None:
        """Detach a ChatSession -- save state and resume idle behavior."""
        if self._session_handle is handle:
            self._session_handle = None
        self.save_v35_state()
        self.save_checkpoint()
        log.info("Session detached -- state saved")

    def record_user_activity(self) -> None:
        """Record that a user interacted (for idle tracking)."""
        self._last_activity = time.monotonic()

    # ──────────────────────────────────────────────────────────────────
    # Properties — API / dashboard access
    # ──────────────────────────────────────────────────────────────────

    @property
    def prometheus(self) -> PrometheusExporter | None:
        """Prometheus exporter instance (available after start)."""
        return self._prometheus

    @property
    def kill_switch(self) -> KillSwitch | None:
        """Kill switch instance (available after start)."""
        return self._kill_switch

    @property
    def watchdog(self) -> Watchdog | None:
        """Watchdog instance (available after start)."""
        return self._watchdog

    @property
    def rate_limiter(self) -> RateLimiter | None:
        """Rate limiter instance (available after start)."""
        return self._rate_limiter

    @property
    def snapshot_manager(self) -> SnapshotManager | None:
        """Snapshot manager instance (available after start)."""
        return self._snapshot_manager

    @property
    def state_backup(self) -> StateBackup | None:
        """State backup instance for resilience (available after start)."""
        return self._state_backup

    @property
    def sleep_manager(self) -> SleepManager | None:
        """Sleep manager instance (available after start)."""
        return self._sleep_manager

    @property
    def heartbeat(self) -> Heartbeat | None:
        """Heartbeat instance (available after start)."""
        return self._heartbeat

    @property
    def audit(self) -> AuditTrail | None:
        """Audit trail instance (available after start)."""
        return self._audit

    @property
    def decider(self) -> ConsciousnessDecider:
        """Consciousness decider (always available)."""
        return self._decider
