"""ChatSession — human-facing conversation interface for Luna.

Wires LunaEngine + LLMBridge + MemoryManager for direct interaction.
Each chat turn evolves cognitive state with real info_deltas.

v3.0: Inversion of control — Luna decides (ConsciousnessDecider),
the LLM translates.  Double evolve per turn (input + output).

v3.5: Structured cognition — Thinker, CausalGraph, Lexicon, Dream v2,
SelfImprovement wired into the session flow.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


from luna_common.constants import INV_PHI2, INV_PHI3, METRIC_NAMES, PHI_WEIGHTS, COMP_NAMES

from luna.consciousness.causal_graph import CausalGraph
from luna.consciousness.decider import (
    ConsciousDecision,
    ConsciousnessDecider,
    Intent,
    SessionContext,
)
from luna.consciousness.lexicon import Lexicon
from luna.consciousness.affect import AffectEngine
from luna.consciousness.appraisal import AffectEvent
from luna.consciousness.evaluator import Evaluator, compute_dominance_rank
from luna.consciousness.learnable_params import LearnableParams
from luna.consciousness.observation_factory import ObservationCandidate, ObservationFactory
from luna.consciousness.reactor import (
    BehavioralModifiers,
    ConsciousnessReactor,
    PipelineOutcome,
    Reaction,
)
from luna.consciousness.thinker import Observation, Stimulus, ThinkMode, Thinker, Thought
from luna.consciousness.episodic_memory import Episode, EpisodicMemory, make_episode
from luna.consciousness.endogenous import EndogenousSource, Impulse
from luna.consciousness.initiative import InitiativeAction, InitiativeEngine
from luna.consciousness.watcher import EnvironmentWatcher, WatcherEvent, WatcherEventType
from luna.llm_bridge.voice_validator import VoiceValidator, VoiceDelta
from luna.memory.cycle_store import CycleStore
from luna.autonomy.window import AutonomyWindow
from luna.consciousness.telemetry_summarizer import TelemetrySummarizer
from luna.dream.dream_cycle import DreamCycle, DreamResult
from luna.llm_bridge.circuit_breaker import CircuitBreaker, CircuitState
from luna.consciousness.synthesis import Synthesis, SynthesisReport
from luna.dream.learning import DreamLearning, Interaction
from luna.dream.priors import (
    DreamPriors,
    ReflectionPrior,
    SkillPrior,
    populate_dream_priors,
)
from luna.core.config import LunaConfig
from luna.core.luna import LunaEngine
from luna.llm_bridge.bridge import LLMBridge, LLMBridgeError, LLMResponse
from luna.llm_bridge.prompt_builder import build_voice_prompt
from luna.memory.memory_manager import MemoryEntry, MemoryManager
from luna.metrics.tracker import MetricSource, MetricTracker
from luna.orchestrator.retry import RetryPolicy, retry_async
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from luna.orchestrator.cognitive_loop import CognitiveLoop
from luna_common.schemas.cycle import CycleRecord, RewardVector
from luna.safety.kill_switch import SENTINEL_FILENAME

log = logging.getLogger(__name__)

# Stopwords for keyword extraction (FR + EN basics + Luna ecosystem).
# Used by _extract_keywords() which feeds recent_topics for initiative rule 4.
_STOPWORDS: frozenset[str] = frozenset({
    # --- FR determiners, pronouns, prepositions ---
    "le", "la", "les", "un", "une", "des", "de", "du", "au", "aux",
    "et", "ou", "mais", "donc", "car", "ni", "que", "qui", "quoi",
    "je", "tu", "il", "elle", "nous", "vous", "ils", "elles", "on",
    "ce", "cette", "ces", "mon", "ma", "mes", "ton", "ta", "tes",
    "son", "sa", "ses", "est", "sont", "suis", "es", "a", "ai",
    "dans", "sur", "pour", "avec", "par", "en",
    "pas", "ne", "se", "oui", "non",
    # --- FR common verbs ---
    "etre", "avoir", "faire", "dire", "aller", "voir", "savoir",
    "pouvoir", "vouloir", "falloir", "devoir", "mettre", "prendre",
    "aussi", "bien", "comme", "plus", "moins", "tres", "trop",
    "encore", "deja", "toujours", "jamais", "tout", "tous", "toute",
    "peut", "peux", "fait", "fais", "veux", "vais", "vas",
    # --- EN determiners, pronouns, prepositions ---
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "can", "could", "should", "may", "might", "shall",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
    "my", "your", "his", "its", "our", "their",
    "in", "on", "at", "to", "for", "with", "from", "by", "of",
    "not", "no", "yes",
    # --- EN common verbs/adverbs ---
    "get", "got", "make", "made", "just", "also", "very", "much",
    "more", "most", "some", "any", "all", "each", "every",
    "this", "that", "these", "those", "what", "which", "how", "why",
    "when", "where", "who", "want", "need", "like", "know", "think",
    # --- Luna ecosystem (not topics) ---
    "luna", "sayohmy", "sentinel", "testengineer",
    "pipeline", "conscience", "consciousness",
    "psi", "phi", "phase", "metric", "metriques",
    "bonjour", "salut", "hello", "merci", "thanks",
})


def _extract_keywords(text: str, limit: int = 8) -> list[str]:
    """Extract keywords from text — naive FR+EN, no NLP dependency."""
    tokens = re.findall(r"[a-zA-ZÀ-ÿ]{3,}", text.lower())
    seen: set[str] = set()
    keywords: list[str] = []
    for tok in tokens:
        if tok not in _STOPWORDS and tok not in seen:
            seen.add(tok)
            keywords.append(tok)
            if len(keywords) >= limit:
                break
    return keywords


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """A single turn in the conversation."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class ChatResponse:
    """Response returned by ChatSession.send()."""

    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    phase: str = ""
    phi_iit: float = 0.0
    origin: str = "user"  # "user" | "endogenous"
    endogenous_impulse: str | None = None


# Slash commands recognized by the chat session.
_COMMANDS = frozenset({"/status", "/dream", "/memories", "/synthesis", "/help", "/quit"})

_HELP_TEXT = (
    "Commandes disponibles:\n"
    "  /status       — Etat de conscience et metriques\n"
    "  /dream        — Declencher un cycle de reve\n"
    "  /memories [N] — Afficher les N memoires recentes (defaut: 10)\n"
    "  /synthesis    — Retrospective longitudinale (tendances, anomalies)\n"
    "  /help         — Cette aide\n"
    "  /quit         — Sauvegarder et quitter\n"
)


class ChatSession:
    """Human-facing chat session wiring Engine + LLM + Memory.

    Graceful degradation:
    - Without LLM: returns status-only responses.
    - Without memory: chat without historical context.
    - LLM error mid-turn: fallback to status.
    """

    def __init__(self, config: LunaConfig, loop: CognitiveLoop | None = None) -> None:
        self._config = config
        self._loop: CognitiveLoop | None = loop
        self._owns_loop: bool = False  # True when we auto-create the loop
        self._session_handle: object | None = None  # SessionHandle from attach
        self._engine = LunaEngine(config)
        self._llm: LLMBridge | None = None
        self._memory: MemoryManager | None = None
        self._history: list[ChatMessage] = []
        self._session_start_index: int = 0
        self._started = False
        self._turn_count: int = 0
        self._metric_tracker = MetricTracker()
        # v3.0 — Consciousness Decider (Luna's brain).
        # identity_context is injected after engine.initialize() in start().
        self._decider = ConsciousnessDecider()
        self._last_dream_turn: int = -1
        self._last_dream_insight: str | None = None
        self._recent_topics: list[str] = []
        # v2.4.0 — Wake-cycle buffers for dream harvest.
        self._psi_snapshots: list[tuple[float, ...]] = []
        self._phi_iit_history: list[float] = []
        # v2.4.1 — Inactivity-triggered dream.
        self._last_activity: float = time.monotonic()
        self._last_user_activity: float = time.monotonic()  # Not reset by dreams
        self._inactivity_task: asyncio.Task | None = None
        # v3.5 — Structured cognition components (initialized in start()).
        self._reactor_behavioral: BehavioralModifiers | None = None
        self._thinker: Thinker | None = None
        self._causal_graph: CausalGraph | None = None
        self._lexicon: Lexicon | None = None
        self._dream_learning: DreamLearning | None = None
        self._dream_cycle: DreamCycle | None = None
        self._interaction_buffer: list[Interaction] = []
        # v3.5.2 — Real cognitive system: initiative, episodic memory, watcher, voice validation.
        self._initiative_engine: "InitiativeEngine | None" = None
        self._episodic_memory: "EpisodicMemory | None" = None
        self._watcher: "EnvironmentWatcher | None" = None
        # v5.1 Convergence — endogenous impulse source.
        self._endogenous: EndogenousSource | None = None
        self._endogenous_task: asyncio.Task | None = None
        self._on_endogenous: asyncio.Queue[ChatResponse] | None = None
        # v5.1 Convergence Phase 4 — SelfImprovement.
        self._self_improvement: "SelfImprovement | None" = None
        # PlanAffect — continuous affect engine.
        self._affect_engine: AffectEngine | None = None
        # v4.0 Emergence — learning loop components (initialized in start()).
        self._learnable_params: LearnableParams | None = None
        self._evaluator: Evaluator | None = None
        self._cycle_store: CycleStore | None = None
        self._telemetry_collector: object | None = None  # removed with pipeline
        self._observation_factory: ObservationFactory | None = None
        self._reward_history: list[RewardVector] = []
        self._autonomy_window: AutonomyWindow | None = None
        self._last_auto_apply_result: object | None = None  # AutoApplyResult from Phase B
        self._curiosity_counts: dict[str, int] = {}  # need tag → recurrence count
        self._voice_correction_count: int = 0  # voice corrections this session
        # v6.1 — Idle cognitive tick (background reduced cognition between messages).
        self._idle_cognitive_task: asyncio.Task | None = None
        self._idle_tick_count: int = 0
        # Dream priors — weak signals persisted across dream cycles.
        self._dream_priors: DreamPriors | None = None
        # v6.0 — Circuit breaker, synthesis, session state.
        self._circuit_breaker: CircuitBreaker | None = None
        self._synthesis: Synthesis | None = None
        self._last_synthesis_report: SynthesisReport | None = None

    @property
    def engine(self) -> LunaEngine:
        return self._engine

    @property
    def history(self) -> list[ChatMessage]:
        return self._history

    @property
    def has_llm(self) -> bool:
        return self._llm is not None

    @property
    def has_memory(self) -> bool:
        return self._memory is not None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Initialize engine, LLM, and memory. Tolerates missing LLM/memory."""
        if self._loop is None:
            # Auto-create a CognitiveLoop in init-only mode (no tick, no
            # heartbeat daemon). This eliminates ~200 lines of duplicated
            # subsystem initialization that used to live here.
            from luna.orchestrator.cognitive_loop import CognitiveLoop

            self._loop = CognitiveLoop(self._config)
            self._loop.init_subsystems()
            self._owns_loop = True

        await self._start_with_loop()

    def _maybe_upgrade_checkpoint(self) -> None:
        """Force-save checkpoint if on-disk version is outdated.

        Ensures the checkpoint file is upgraded to v3.5.0 format
        with phi_metrics included. One-time migration.
        """
        cs = self._engine.consciousness
        if cs is None:
            return
        ckpt_path = self._config.resolve(self._config.consciousness.checkpoint_file)
        if not ckpt_path.exists():
            return
        try:
            with open(ckpt_path) as f:
                import json as _json
                data = _json.load(f)
            # Validate checkpoint structure after deserialization.
            if not isinstance(data, dict):
                log.warning("Checkpoint is not a dict — skipping upgrade check")
                return
            required_keys = {"version", "step_count"}
            if not required_keys.issubset(data.keys()):
                log.warning(
                    "Checkpoint missing required keys %s — skipping upgrade check",
                    required_keys - data.keys(),
                )
                return
            on_disk_version = data.get("version", "2.0.0")
            has_phi_metrics = "phi_metrics" in data
            if on_disk_version < "3.5" or not has_phi_metrics:
                log.info(
                    "Checkpoint upgrade: v%s -> v3.5.0",
                    on_disk_version,
                )
                self._save_checkpoint()
        except Exception:
            log.warning("Checkpoint upgrade check failed", exc_info=True)

    async def _start_with_loop(self) -> None:
        """Wire aliases from the CognitiveLoop into session-local attributes.

        The loop owns all subsystems (engine, LLM, memory, thinker, etc.).
        We create aliases so existing code in send() and friends works
        unchanged without reaching through self._loop everywhere.
        """
        loop = self._loop

        # -- Core aliases -------------------------------------------------
        self._engine = loop.engine
        self._config = loop.config
        self._llm = loop._llm
        self._memory = loop.memory
        self._metric_tracker = loop.metric_tracker
        self._decider = loop._decider

        # -- v3.5 cognitive aliases ----------------------------------------
        self._thinker = loop.thinker
        self._causal_graph = loop.causal_graph
        self._lexicon = loop.lexicon
        self._dream_learning = loop._dream_learning
        self._dream_cycle = loop.dream_cycle
        self._episodic_memory = loop.episodic_memory
        self._affect_engine = loop.affect_engine
        self._learnable_params = loop.learnable_params
        self._evaluator = loop.evaluator
        self._initiative_engine = loop.initiative_engine
        self._endogenous = loop.endogenous
        self._self_improvement = loop.self_improvement
        self._watcher = loop.watcher
        self._observation_factory = loop.observation_factory
        self._cycle_store = loop.cycle_store
        self._telemetry_collector = loop._telemetry_collector
        self._reward_history = loop._reward_history
        self._autonomy_window = loop.autonomy_window
        self._dream_priors = loop.dream_priors
        # v6.0 aliases.
        self._circuit_breaker = loop.circuit_breaker
        self._synthesis = loop.synthesis
        self._last_synthesis_report = loop.last_synthesis_report

        # -- Chat-specific init (NOT delegated) ---------------------------
        self._load_history()
        self._session_start_index = len(self._history)

        # v6.0: Restore session state and detect boot gap.
        boot_gap = self._load_session_state()

        self._started = True

        # -- Attach to the CognitiveLoop ----------------------------------
        # This tells the tick to skip idle_step/collect/dream (session owns
        # those responsibilities while attached).
        if not self._owns_loop:
            self._session_handle = loop.attach_session()

        # -- Session-specific background tasks ----------------------------
        if self._config.dream.enabled:
            self._last_activity = time.monotonic()
            self._last_user_activity = time.monotonic()
            self._inactivity_task = asyncio.create_task(self._watch_inactivity())
            log.info(
                "Inactivity watcher started (threshold=%.0fs)",
                self._config.dream.inactivity_threshold,
            )

        if self._endogenous is not None:
            self._on_endogenous = asyncio.Queue()
            self._endogenous_task = asyncio.create_task(self._watch_endogenous())
            log.info("Endogenous autonomy loop started")

        # v6.1: Idle cognitive tick — reduced cognition between messages.
        if (self._thinker is not None
                and self._config.chat.idle_cognitive_tick):
            self._idle_cognitive_task = asyncio.create_task(
                self._watch_idle_cognition()
            )
            log.info(
                "Idle cognitive tick started (interval=%.0fs)",
                self._config.chat.idle_cognitive_interval,
            )

        if self._watcher is not None:
            try:
                await self._watcher.start()
                log.info("EnvironmentWatcher started (interval=%.0fs)", self._watcher._interval)
            except Exception:
                log.warning("EnvironmentWatcher start failed", exc_info=True)

        self._maybe_upgrade_checkpoint()

        # v6.0: Catch-up dream if Luna was offline too long.
        if boot_gap > 0:
            self._maybe_catch_up_dream(boot_gap)

        log.info("ChatSession started (via CognitiveLoop)")

    # _init_llm() and _init_v35_components() removed — now owned by
    # CognitiveLoop.init_subsystems().  Session aliases them via
    # _start_with_loop().

    def _history_path(self) -> Path:
        """Path to the persisted chat history file."""
        mem_root = self._config.memory.fractal_root
        return self._config.resolve(mem_root) / "chat_history.json"

    def _load_history(self) -> None:
        """Load chat history from disk if available."""
        path = self._history_path()
        if not path.is_file():
            return
        try:
            with open(path) as f:
                data = json.load(f)
            if not isinstance(data, list):
                return
            max_h = self._config.chat.max_history
            for entry in data[-max_h:]:
                if isinstance(entry, dict) and "role" in entry and "content" in entry:
                    ts_str = entry.get("timestamp")
                    ts = (
                        datetime.fromisoformat(ts_str)
                        if ts_str
                        else datetime.now(timezone.utc)
                    )
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    self._history.append(ChatMessage(
                        role=entry["role"],
                        content=entry["content"],
                        timestamp=ts,
                    ))
            if self._history:
                log.info(
                    "Restored %d chat history entries from %s",
                    len(self._history), path,
                )
        except Exception:
            log.warning("Failed to load chat history from %s", path, exc_info=True)

    @staticmethod
    def _sanitize_for_persistence(msg: ChatMessage) -> str:
        """Sanitize assistant message content before persisting.

        Vaccine B6: if an assistant message contains code fences (```)
        the code was hallucinated (Luna does not produce code).
        Replace with a short summary to prevent future contamination.
        """
        if msg.role != "assistant":
            return msg.content
        if "```" not in msg.content:
            return msg.content
        # Hallucinated code — replace with summary.
        log.info("B6 vaccine: stripping hallucinated code from history entry")
        return "[Code filtre — Luna ne produit pas de code]"

    def _save_history(self) -> None:
        """Persist chat history to disk (atomic write).

        Applies B6 vaccine: assistant messages with code blocks but no
        pipeline backing are replaced with a short summary to prevent
        hallucination contamination across sessions.
        """
        if not self._history:
            return
        path = self._history_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        max_h = self._config.chat.max_history
        entries = [
            {
                "role": msg.role,
                "content": self._sanitize_for_persistence(msg),
                "timestamp": msg.timestamp.isoformat(),
            }
            for msg in self._history[-max_h:]
        ]
        tmp = path.with_suffix(".tmp")
        try:
            with open(tmp, "w") as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)
            os.replace(str(tmp), str(path))
        except Exception:
            log.warning("Failed to save chat history to %s", path, exc_info=True)

    def _archive_history(self, trimmed: list["ChatMessage"]) -> None:
        """Append trimmed messages to a permanent archive file.

        Messages are NEVER deleted — they are moved from the active history
        to ``memory_fractal/chat_archive.json`` which grows indefinitely.
        Luna retains permanent access to all past conversations.
        """
        if not trimmed:
            return
        archive_path = self._history_path().parent / "chat_archive.json"

        # Load existing archive.
        existing: list[dict] = []
        if archive_path.is_file():
            try:
                existing = json.loads(archive_path.read_text(encoding="utf-8"))
            except Exception:
                log.warning("Could not read chat archive, starting fresh")

        # Append trimmed messages.
        for msg in trimmed:
            existing.append({
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
            })

        # Atomic write.
        tmp = archive_path.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
            os.replace(str(tmp), str(archive_path))
            log.info("Archived %d messages to %s (total: %d)", len(trimmed), archive_path, len(existing))
        except Exception:
            log.warning("Failed to archive chat history", exc_info=True)

    def _compress_history_to_memory(self, trimmed: list["ChatMessage"]) -> None:
        """Compress trimmed chat messages into an episodic memory.

        Called before history trim in _finalize_turn(). Converts messages that
        are about to be dropped into a single Episode — like a human souvenir:
        the details fade but the essence remains. The raw messages are also
        preserved permanently via _archive_history().

        Pure Python extraction: no LLM call. Groups user+assistant pairs,
        extracts keywords and timestamp range, records one Episode per
        compression event.
        """
        # Always archive raw messages permanently.
        self._archive_history(trimmed)

        if self._episodic_memory is None or not trimmed:
            return

        # --- Group into conversation pairs (user + assistant) ---
        pairs: list[tuple[ChatMessage, ChatMessage | None]] = []
        i = 0
        while i < len(trimmed):
            msg = trimmed[i]
            if msg.role == "user":
                assistant = trimmed[i + 1] if (i + 1 < len(trimmed) and trimmed[i + 1].role == "assistant") else None
                pairs.append((msg, assistant))
                i += 2 if assistant else 1
            else:
                # Orphan assistant message — pair with None user
                pairs.append((ChatMessage(role="user", content="[...]", timestamp=msg.timestamp), msg))
                i += 1

        if not pairs:
            return

        # --- Extract summaries and keywords per pair ---
        summaries: list[str] = []
        all_keywords: list[str] = []
        for user_msg, _assistant_msg in pairs:
            summaries.append(user_msg.content[:100].replace("\n", " "))
            all_keywords.extend(_extract_keywords(user_msg.content, limit=4))

        # Deduplicate keywords while preserving order.
        seen: set[str] = set()
        unique_keywords: list[str] = []
        for kw in all_keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)

        # --- Timestamp range ---
        ts_start = trimmed[0].timestamp.isoformat(timespec="minutes")
        ts_end = trimmed[-1].timestamp.isoformat(timespec="minutes")

        # --- Consciousness snapshot (approximate: current state) ---
        cs = self._engine.consciousness
        psi = tuple(float(x) for x in cs.psi)
        phi = cs.compute_phi_iit()
        phase = cs.get_phase()

        # --- Build the episode ---
        topics = ", ".join(unique_keywords[:12]) or "general"
        action_detail = (
            f"Compressed {len(trimmed)} messages "
            f"({ts_start} -> {ts_end}): {topics}"
        )
        narrative = " | ".join(summaries[:8])
        if len(summaries) > 8:
            narrative += f" | ... (+{len(summaries) - 8} more)"

        try:
            episode = make_episode(
                timestamp=float(cs.step_count),
                psi_before=psi,
                phi_before=phi,
                phase_before=phase,
                observation_tags=unique_keywords[:12],
                user_intent="chat",
                action_type="conversation_memory",
                action_detail=action_detail,
                psi_after=psi,
                phi_after=phi,
                phase_after=phase,
                outcome="compressed",
                significance=INV_PHI2,  # 0.382 — moderate consolidation
                narrative_arc=narrative[:500],
            )
            self._episodic_memory.record(episode)
            self._episodic_memory.save()
            log.info(
                "History compression: %d messages -> 1 episode (%s)",
                len(trimmed),
                topics[:60],
            )
        except Exception:
            log.warning("History compression failed", exc_info=True)

    def _build_phi_snapshot(self) -> dict:
        """Build enriched phi_metrics dict: {name: {value, source, timestamp}}.

        Every metric gets an explicit source (never omitted) so the checkpoint
        is self-describing and restores correctly without defaulting.
        """
        phi_snapshot = self._engine.phi_scorer.snapshot()
        sources = self._metric_tracker.snapshot_sources()
        for name in phi_snapshot:
            # Always write source — default to "bootstrap" if tracker has none.
            phi_snapshot[name]["source"] = sources.get(name, "bootstrap")
            # Add timestamp from MetricTracker if available.
            entry = self._metric_tracker.get(name)
            if entry is not None:
                phi_snapshot[name]["timestamp"] = entry.timestamp.isoformat()
        return phi_snapshot

    def _save_checkpoint(self) -> None:
        """Save cognitive checkpoint + chat history + session state."""
        if self._engine.consciousness is None:
            return
        ckpt = self._config.resolve(self._config.consciousness.checkpoint_file)
        phi_snapshot = self._build_phi_snapshot()
        self._engine.consciousness.save_checkpoint(
            ckpt,
            backup=self._config.consciousness.backup_on_save,
            phi_metrics=phi_snapshot,
        )
        self._save_history()
        self._save_session_state()
        log.info(
            "Checkpoint saved (bootstrap_ratio=%.2f)",
            self._metric_tracker.bootstrap_ratio(),
        )

    def _save_v35_state(self) -> None:
        """Persist v3.5 component state (causal graph, lexicon, dream skills, episodes)."""
        mem_root = self._config.resolve(self._config.memory.fractal_root)
        try:
            if self._causal_graph is not None:
                self._causal_graph.persist(mem_root / "causal_graph.json")
            if self._lexicon is not None:
                self._lexicon.save()
            if self._dream_learning is not None:
                self._dream_learning.persist()
            if self._episodic_memory is not None:
                self._episodic_memory.save()
            if self._affect_engine is not None:
                affect_path = mem_root / "affect_engine.json"
                with open(affect_path, "w") as _f:
                    json.dump(self._affect_engine.to_dict(), _f)
            if self._learnable_params is not None:
                self._learnable_params.save(mem_root / "learnable_params.json")
            if self._observation_factory is not None:
                self._observation_factory.save(mem_root / "observation_factory.json")
            if self._self_improvement is not None:
                self._self_improvement.persist(mem_root / "self_improvement.json")
            if self._dream_priors is not None:
                self._dream_priors.save(mem_root / "dream_priors.json")
            log.debug("v3.5+v4.0 state saved")
        except Exception:
            log.warning("v3.5 state save failed", exc_info=True)

    # ------------------------------------------------------------------
    # Session state persistence (v6.0 Phase D)
    # ------------------------------------------------------------------

    def _session_state_path(self) -> Path:
        """Path to the session state file."""
        mem_root = self._config.memory.fractal_root
        return self._config.resolve(mem_root) / "session_state.json"

    def _save_session_state(self) -> None:
        """Persist ephemeral session state for cross-session continuity.

        Saved on every checkpoint and on stop(). Allows boot gap detection
        and restoration of turn count, topic history, etc.
        """
        path = self._session_state_path()
        state = {
            "version": "7.0.0",
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "turn_count": self._turn_count,
            "recent_topics": self._recent_topics[-20:],
            "last_dream_turn": self._last_dream_turn,
            "voice_correction_count": self._voice_correction_count,
            "curiosity_counts": dict(
                sorted(self._curiosity_counts.items(), key=lambda x: x[1], reverse=True)[:50]
            ),
            "circuit_breaker": self._circuit_breaker.to_dict() if self._circuit_breaker else None,
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            tmp.replace(path)
            log.debug("Session state saved (%d turns)", self._turn_count)
        except Exception:
            log.warning("Failed to save session state", exc_info=True)

    def _load_session_state(self) -> float:
        """Restore session state from disk. Returns gap in seconds since last save.

        Returns 0.0 if no prior state exists (first boot).
        """
        path = self._session_state_path()
        if not path.is_file():
            return 0.0
        try:
            with open(path, encoding="utf-8") as f:
                state = json.load(f)
            if not isinstance(state, dict):
                return 0.0

            # Restore turn count and topic history.
            self._turn_count = state.get("turn_count", 0)
            self._recent_topics = state.get("recent_topics", [])
            self._last_dream_turn = state.get("last_dream_turn", -1)
            self._voice_correction_count = state.get("voice_correction_count", 0)
            self._curiosity_counts = state.get("curiosity_counts", {})

            # Compute gap since last save.
            saved_at_str = state.get("saved_at")
            if saved_at_str:
                saved_at = datetime.fromisoformat(saved_at_str)
                if saved_at.tzinfo is None:
                    saved_at = saved_at.replace(tzinfo=timezone.utc)
                gap = (datetime.now(timezone.utc) - saved_at).total_seconds()
                log.info(
                    "Session state restored (turns=%d, gap=%.0fs)",
                    self._turn_count, gap,
                )
                return max(0.0, gap)

            log.info("Session state restored (turns=%d, no timestamp)", self._turn_count)
            return 0.0
        except Exception:
            log.warning("Failed to load session state", exc_info=True)
            return 0.0

    def _maybe_catch_up_dream(self, gap_seconds: float) -> None:
        """Trigger a catch-up dream if the boot gap exceeds the inactivity threshold.

        This ensures Luna consolidates after long periods of absence,
        just as she would during normal inactivity-triggered dreams.
        """
        threshold = self._config.dream.inactivity_threshold
        if gap_seconds < threshold:
            return
        if not self._config.dream.enabled:
            return
        if self._dream_cycle is None:
            return

        log.info(
            "Boot gap %.0fs exceeds threshold %.0fs — scheduling catch-up dream",
            gap_seconds, threshold,
        )
        try:
            recent = self._load_recent_cycles()
            psi0_history = self._psi0_delta_history()
            dream_result = self._dream_cycle.run(
                recent_cycles=recent,
                psi0_delta_history=psi0_history,
            )
            log.info(
                "Catch-up dream completed: %d skills, psi0_applied=%s",
                len(dream_result.skills_learned),
                dream_result.psi0_applied,
            )
            self._finalize_dream_v2(dream_result)
        except Exception:
            log.warning("Catch-up dream failed", exc_info=True)

    def _populate_dream_priors(self, dream_result: DreamResult) -> None:
        """Extract weak priors from dream outputs for cognitive injection."""
        self._dream_priors = populate_dream_priors(
            dream_result, previous_priors=self._dream_priors,
        )
        # Propagate back to the loop to keep references in sync.
        if getattr(self, "_loop", None) is not None:
            self._loop.dream_priors = self._dream_priors

    def _load_recent_cycles(self) -> list | None:
        """Load recent CycleRecords for dream initialization."""
        if self._cycle_store is None:
            return None
        try:
            return self._cycle_store.read_recent(10) or None
        except Exception:
            log.debug("Could not load recent cycles for dream", exc_info=True)
            return None

    def _psi0_delta_history(self) -> list[tuple[float, ...]] | None:
        """Return psi0 delta history for cumulative cap, or None."""
        if self._dream_priors is not None and self._dream_priors.psi0_delta_history:
            return self._dream_priors.psi0_delta_history
        return None

    def _finalize_dream_v2(self, dream_result: DreamResult) -> None:
        """Common post-dream processing for v2 dream cycles."""
        self._interaction_buffer.clear()
        self._last_dream_turn = self._turn_count
        self._populate_dream_priors(dream_result)
        # Sync Evaluator's identity anchor after Ψ₀ consolidation.
        if dream_result.psi0_applied and self._evaluator is not None:
            cs = self._engine.consciousness
            if cs is not None:
                self._evaluator._psi_0 = tuple(float(x) for x in cs.psi0)
        self._save_v35_state()
        self._save_checkpoint()
        # Cache synthesis report from dream.
        if dream_result.synthesis_report is not None:
            self._last_synthesis_report = dream_result.synthesis_report
            if self._loop is not None:
                self._loop.last_synthesis_report = dream_result.synthesis_report
        # Post-dream GC.
        self._run_gc()
        if self._endogenous is not None:
            insight = (
                f"{len(dream_result.skills_learned)} competences, "
                f"{len(dream_result.simulations)} simulations"
            )
            self._endogenous.register_dream_insight(insight)

    def _run_gc(self) -> None:
        """Post-dream garbage collection — archive old data (ZERO DELETION).

        1. Consolidate cycles (already in CycleStore).
        2. Archive old dream JSON files to zstd.
        3. Archive cold memories (low resonance → zstd).
        """
        mem_root = self._config.resolve(self._config.memory.fractal_root)

        # Archive old dream files.
        try:
            dream_dir = mem_root / "insights"
            DreamCycle.archive_old_dreams(dream_dir, max_age_days=30)
        except Exception:
            log.debug("Dream archive failed", exc_info=True)

        # Archive cold memories.
        if self._memory is not None:
            try:
                import asyncio as _aio

                loop = _aio.get_event_loop()
                if loop.is_running():
                    _aio.ensure_future(self._memory.archive_cold())
                else:
                    loop.run_until_complete(self._memory.archive_cold())
            except Exception:
                log.debug("Cold archival failed", exc_info=True)

    def _clear_dream_buffers(self) -> None:
        """Clear wake-cycle buffers after dream consumption."""
        self._psi_snapshots.clear()
        self._phi_iit_history.clear()

    async def stop(self) -> None:
        """Save cognitive checkpoint with PhiScorer metrics on exit."""
        # Cancel inactivity watcher.
        if self._inactivity_task is not None:
            self._inactivity_task.cancel()
            try:
                await self._inactivity_task
            except asyncio.CancelledError:
                pass
            self._inactivity_task = None
        # Cancel endogenous loop.
        if self._endogenous_task is not None:
            self._endogenous_task.cancel()
            try:
                await self._endogenous_task
            except asyncio.CancelledError:
                pass
            self._endogenous_task = None
        # Cancel idle cognitive tick.
        if self._idle_cognitive_task is not None:
            self._idle_cognitive_task.cancel()
            try:
                await self._idle_cognitive_task
            except asyncio.CancelledError:
                pass
            self._idle_cognitive_task = None
        # Stop environment watcher.
        if self._watcher is not None:
            try:
                await self._watcher.stop()
            except Exception:
                log.debug("Watcher stop failed", exc_info=True)
        # Detach from the CognitiveLoop (resumes autonomous mode).
        if self._session_handle is not None and self._loop is not None:
            self._loop.detach_session(self._session_handle)
            self._session_handle = None

        # Chat history is always session-specific.
        self._save_history()

        if self._owns_loop:
            # We auto-created this loop (init-only, no daemon) — we must
            # handle persistence ourselves since nobody else will.
            self._save_v35_state()
            self._save_checkpoint()
            self._loop._running = False

        # When _owns_loop is False, the external caller owns the loop
        # and will call loop.stop() which handles persistence.
        self._started = False

    # ------------------------------------------------------------------
    # Inactivity watcher (v2.4.1)
    # ------------------------------------------------------------------

    async def _watch_inactivity(self) -> None:
        """Background task: trigger dream cycle after prolonged inactivity.

        Checks every 60 s whether ``time.monotonic() - _last_activity``
        exceeds the configured ``dream.inactivity_threshold``.  When it
        does, builds a dream harvest from wake-cycle buffers and runs
        the dream via :class:`DreamCycle`.
        """
        check_interval = 60.0  # seconds between checks
        threshold = self._config.dream.inactivity_threshold

        while True:
            try:
                await asyncio.sleep(check_interval)
            except asyncio.CancelledError:
                return

            if not self._started:
                return

            elapsed = time.monotonic() - self._last_activity
            if elapsed < threshold:
                continue

            # Enough history for a meaningful dream?
            cs = self._engine.consciousness
            if cs is None or len(cs.history) < 10:
                continue

            log.info(
                "Inactivity dream triggered (idle %.0fs >= threshold %.0fs)",
                elapsed, threshold,
            )

            try:
                # v3.5 — Prefer DreamCycle when the causal graph is mature.
                if (
                    self._dream_cycle is not None
                    and self._dream_cycle.is_mature()
                ):
                    recent_cycles = self._load_recent_cycles()
                    dream_result: DreamResult = self._dream_cycle.run(
                        history=self._interaction_buffer or None,
                        recent_cycles=recent_cycles,
                        psi0_delta_history=self._psi0_delta_history(),
                    )
                    log.info(
                        "DreamV2 completed: %.2fs, %d skills, %d sims, mode=%s",
                        dream_result.duration,
                        len(dream_result.skills_learned),
                        len(dream_result.simulations),
                        dream_result.mode,
                    )
                    self._finalize_dream_v2(dream_result)
                else:
                    # Fallback to legacy DreamCycle (statistical phases).
                    from luna.dream._legacy_cycle import DreamCycle as _LegacyCycle

                    dream = _LegacyCycle(self._engine, self._config, self._memory)
                    report = await dream.run()
                    self._last_dream_turn = self._turn_count
                    self._clear_dream_buffers()
                    self._extract_dream_insight(report)

                    # v5.1: Wire legacy dream insights to EndogenousSource.
                    if self._endogenous is not None and self._last_dream_insight:
                        self._endogenous.register_dream_insight(
                            self._last_dream_insight,
                        )

                    log.info(
                        "DreamV1 completed: %.2fs, history %d -> %d",
                        report.total_duration,
                        report.history_before,
                        report.history_after,
                    )

                # Save checkpoint after dream (both paths).
                self._save_checkpoint()

            except Exception:
                log.warning("Inactivity dream failed", exc_info=True)

            # Reset timer so we don't trigger again immediately.
            self._last_activity = time.monotonic()

    # ------------------------------------------------------------------
    # v5.1 — Endogenous autonomy loop
    # ------------------------------------------------------------------

    async def _watch_endogenous(self) -> None:
        """Background task: Luna speaks on her own when she has something to say.

        Polls EndogenousSource every 30s. When an impulse is available,
        routes it through the full cognitive pipeline (Thinker -> Reactor ->
        LLM -> VoiceValidator) via send(origin="endogenous").

        The LLM is the voice, not the brain. Luna decides what to say
        (deterministically from her cognitive state), the LLM gives it words.
        """
        poll_interval = 360.0  # seconds between checks (6 min)
        min_idle = 360.0       # don't interrupt if user active < 6 min

        while True:
            try:
                await asyncio.sleep(poll_interval)
            except asyncio.CancelledError:
                return

            if not self._started:
                return

            # Don't fire if user was recently active (uses user timer, not dream-reset timer).
            idle_secs = time.monotonic() - self._last_user_activity
            if idle_secs < min_idle:
                continue

            # Check for pending impulse.
            cs = self._engine.consciousness
            if cs is None or self._endogenous is None:
                continue

            try:
                impulse = self._endogenous.collect(cs.step_count)
            except Exception:
                log.debug("Endogenous collect failed", exc_info=True)
                continue

            if impulse is None:
                continue

            log.info(
                "Endogenous impulse: source=%s urgency=%.2f msg=%s",
                impulse.source.value, impulse.urgency, impulse.message[:80],
            )

            try:
                response = await self.send(impulse.message, origin="endogenous")
                # Push to the queue for the REPL to display.
                if self._on_endogenous is not None:
                    await self._on_endogenous.put(response)
            except Exception:
                log.warning("Endogenous turn failed", exc_info=True)

    # ------------------------------------------------------------------
    # v6.1 — Idle cognitive tick
    # ------------------------------------------------------------------

    async def _watch_idle_cognition(self) -> None:
        """Background task: reduced cognitive pass while user is idle.

        Runs every ``idle_cognitive_interval`` seconds (default 180s).
        Only fires when the user has been idle for > 60s.
        Does NOT call the LLM, Decider, or VoiceValidator.
        Does NOT reset activity timers — idle thinking is not user activity.
        """
        interval = self._config.chat.idle_cognitive_interval
        min_idle = 60.0  # seconds of user silence before ticking

        while True:
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                return

            if not self._started:
                return

            # Only tick when the user has been genuinely idle.
            idle_secs = time.monotonic() - self._last_user_activity
            if idle_secs < min_idle:
                continue

            # Consciousness must be initialized.
            cs = self._engine.consciousness
            if cs is None:
                continue

            try:
                self._idle_cognitive_tick(cs)
            except Exception:
                log.debug("Idle cognitive tick failed", exc_info=True)

    def _idle_cognitive_tick(self, cs) -> None:
        """Execute one reduced cognitive pass — no LLM, no Decider.

        Steps:
          1. Build introspective Stimulus (empty user_message)
          2. Thinker.think(max_iterations=5, RESPONSIVE)
          3. Reactor.react(thought, psi) → real deltas
          4. cs.evolve(deltas) → advances step_count
          5. InitiativeEngine.evaluate → register to EndogenousSource
          6. Accumulate curiosity from thought.needs
          7. Register affect to EndogenousSource
          8. Debug log
        """
        self._idle_tick_count += 1

        # -- 1. Build introspective stimulus --------------------------------
        affect_pad = None
        if self._affect_engine is not None:
            a = self._affect_engine.affect
            affect_pad = (a.valence, a.arousal, a.dominance)

        recalled: list = []
        if self._episodic_memory is not None:
            try:
                recalled = self._episodic_memory.recall(
                    query="", psi=cs.psi, limit=3,
                )
            except Exception:
                pass

        prev_reward = self._reward_history[-1] if self._reward_history else None

        stimulus = Stimulus(
            user_message="",
            metrics={},
            phi_iit=cs.compute_phi_iit(),
            phase=cs.get_phase(),
            psi=cs.psi,
            psi_trajectory=list(cs.history[-10:]) if cs.history else [],
            affect_state=affect_pad,
            recalled_episodes=recalled,
            previous_reward=prev_reward,
        )

        # -- 2. Think (reduced) --------------------------------------------
        thought = self._thinker.think(
            stimulus=stimulus,
            max_iterations=5,
            mode=ThinkMode.RESPONSIVE,
        )

        # -- 3. React → real deltas -----------------------------------------
        reaction = ConsciousnessReactor.react(
            thought=thought,
            psi=cs.psi,
        )
        self._reactor_behavioral = reaction.behavioral

        # -- 4. Evolve → advance step_count ---------------------------------
        cs.evolve(info_deltas=reaction.deltas)

        # -- 5. Initiative evaluation → EndogenousSource --------------------
        if self._initiative_engine is not None:
            try:
                initiative = self._initiative_engine.evaluate(
                    behavioral=reaction.behavioral,
                    thought=thought,
                    phi=cs.compute_phi_iit(),
                    step=cs.step_count,
                )
                if (initiative.action != InitiativeAction.NONE
                        and self._endogenous is not None):
                    self._endogenous.register_initiative(
                        action=initiative.action.value,
                        reason=initiative.reason,
                        urgency=initiative.urgency,
                    )
            except Exception:
                log.debug("Idle tick initiative failed", exc_info=True)

        # -- 6. Curiosity accumulation (same logic as send() step 9.7) ------
        if self._endogenous is not None:
            try:
                for need in thought.needs:
                    tag = need.description[:60]
                    self._curiosity_counts[tag] = (
                        self._curiosity_counts.get(tag, 0) + 1
                    )
                    count = self._curiosity_counts[tag]
                    pressure = count * INV_PHI3  # 0.236 per recurrence
                    if pressure >= INV_PHI2:  # 0.382 threshold
                        question = (
                            f"Pourquoi {tag} persiste-t-il ? "
                            f"(observe {count} fois sans resolution)"
                        )
                        self._endogenous.register_curiosity(
                            question=question, pressure=pressure,
                        )
                        self._curiosity_counts[tag] = 0
            except Exception:
                log.debug("Idle tick curiosity failed", exc_info=True)

        # -- 7. Affect feed → EndogenousSource ------------------------------
        if self._endogenous is not None and self._affect_engine is not None:
            try:
                self._endogenous.register_affect(
                    arousal=self._affect_engine.affect.arousal,
                    valence=self._affect_engine.affect.valence,
                    cause="idle_tick",
                )
            except Exception:
                log.debug("Idle tick affect failed", exc_info=True)

        # -- 8. Debug log ---------------------------------------------------
        log.debug(
            "Idle cognitive tick #%d: step=%d phase=%s phi=%.3f obs=%d needs=%d",
            self._idle_tick_count,
            cs.step_count,
            cs.get_phase(),
            cs.compute_phi_iit(),
            len(thought.observations),
            len(thought.needs),
        )

    # ------------------------------------------------------------------
    # v3.0 — Decider support
    # ------------------------------------------------------------------

    def _build_session_context(self) -> SessionContext:
        """Build a SessionContext snapshot for the ConsciousnessDecider."""
        coverage = 0.0
        entry = self._metric_tracker.get("test_coverage")
        if entry is not None:
            coverage = entry.value

        return SessionContext(
            turn_count=self._turn_count,
            last_dream_turn=self._last_dream_turn,
            bootstrap_ratio=self._metric_tracker.bootstrap_ratio(),
            recent_topics=list(self._recent_topics[-10:]),
            coverage_score=coverage,
            phi_history=list(self._phi_iit_history[-10:]),
            last_dream_insight=self._last_dream_insight,
        )

    def _input_evolve(
        self,
        message: str,
        thought: Thought | None = None,
        factory_obs_count: int = 0,
    ) -> Reaction | None:
        """Evolve cognitive state from REAL cognitive output.

        v3.5.1: The Reactor converts Thinker output + pipeline outcome
        into real info_deltas.  No more hardcoded constants — every delta
        derives from actual observations, causalities, needs, proposals.

        v5.1: When factory_obs_count > 0, runs two Reactor passes (base vs
        factory observations) and applies the 20% influence cap. This is
        exact — no approximation, no hidden state, fully deterministic.

        When no Thought is available (graceful degradation), falls back
        to lightweight message-based deltas.

        Returns the Reaction (used for behavioral modifiers downstream).
        """
        cs = self._engine.consciousness
        if cs is None:
            return None

        # Increment dream priors age (called each turn).
        if self._dream_priors is not None:
            self._dream_priors.cycles_since_dream += 1

        reaction: Reaction | None = None

        if thought is not None:
            if factory_obs_count > 0:
                # 2-PASS — exact factory cap.
                # Factory observations are the last factory_obs_count in the list.
                n_base = len(thought.observations) - factory_obs_count

                # Pass 1: Reactor on base observations only
                # (+ all causalities/needs/proposals/REFLEXION_PULSE/pipeline).
                base_thought = Thought(
                    observations=thought.observations[:n_base],
                    causalities=thought.causalities,
                    correlations=thought.correlations,
                    needs=thought.needs,
                    proposals=thought.proposals,
                    insights=thought.insights,
                    uncertainties=thought.uncertainties,
                    self_state=thought.self_state,
                    depth_reached=thought.depth_reached,
                    confidence=thought.confidence,
                    cognitive_budget=thought.cognitive_budget,
                )
                base_reaction = ConsciousnessReactor.react(
                    thought=base_thought,
                    psi=cs.psi,
                    pipeline_outcome=PipelineOutcome.NONE,
                )

                # Pass 2: factory observation deltas — pure observation math.
                # Uses Reactor.compute_observation_deltas: same formula as
                # react() step 1, but no REFLEXION_PULSE, no pipeline, no clamp.
                # If Reactor's observation formula changes, this stays in sync.
                factory_deltas = ConsciousnessReactor.compute_observation_deltas(
                    thought.observations[n_base:],
                )

                # Apply 20% influence cap.
                deltas = ObservationFactory.cap_info_deltas(
                    base_reaction.deltas, factory_deltas,
                )
                # Use base reaction for behavioral modifiers and phi.
                reaction = Reaction(
                    deltas=deltas,
                    phi_thought=base_reaction.phi_thought,
                    behavioral=base_reaction.behavioral,
                )
            else:
                # SINGLE PASS — no factory observations, identical to pre-v5.1.
                reaction = ConsciousnessReactor.react(
                    thought=thought,
                    psi=cs.psi,
                    pipeline_outcome=PipelineOutcome.NONE,
                )
            deltas = reaction.deltas
        else:
            # FALLBACK — lightweight message-based deltas (pre-v3.5.1).
            msg_signal = min(1.0, len(message) / 500.0)
            deltas = [
                msg_signal * 0.1,  # Perception: message richness
                0.02,              # Reflexion: baseline
                0.02,              # Integration: baseline
                0.02,              # Expression: baseline (equal to peers)
            ]

        # v5.1: single-agent evolution — spatial gradient from internal history.
        cs.evolve(info_deltas=deltas)
        return reaction

    # ------------------------------------------------------------------
    # Watcher -> ObservationFactory bridge (Convergence v5.1 Phase 2)
    # ------------------------------------------------------------------

    _WATCHER_PATTERN_MAP: dict[WatcherEventType, str] = {
        WatcherEventType.FILE_CHANGED: "env:file_churn",
        WatcherEventType.GIT_STATE_CHANGED: "env:git_shift",
        WatcherEventType.STABILITY_SHIFT: "env:stability_change",
        WatcherEventType.IDLE_LONG: "env:idle_period",
    }

    _WATCHER_PREDICTED_OUTCOME: dict[WatcherEventType, str] = {
        WatcherEventType.FILE_CHANGED: "integration_drop",
        WatcherEventType.GIT_STATE_CHANGED: "perception_shift",
        WatcherEventType.STABILITY_SHIFT: "phi_shift",
        WatcherEventType.IDLE_LONG: "reflexion_drift",
    }

    def _process_watcher_events(self) -> tuple[str, list[WatcherEvent]]:
        """Drain watcher events and feed significant ones to ObservationFactory.

        For each event with severity >= INV_PHI3 (0.236):
          - Maps the event type to a pattern_id for the ObservationFactory
          - Creates a new ObservationCandidate if not already tracked
          - Records an observation (observe()) for existing candidates

        Returns:
            (watcher_context, events): The formatted text context for the
            Thinker prompt AND the raw event list for downstream use.
        """
        if self._watcher is None:
            return "", []

        events = self._watcher.drain_events()
        if not events:
            return "", []

        log.info("Watcher: %d events drained", len(events))

        # Feed significant events to ObservationFactory.
        if self._observation_factory is not None:
            for ev in events:
                if ev.severity < INV_PHI3:
                    continue

                pattern_id = self._WATCHER_PATTERN_MAP.get(ev.event_type)
                if pattern_id is None:
                    continue

                existing = self._observation_factory.get_candidate(pattern_id)
                if existing is None:
                    # First time we see this pattern -- create a hypothesis.
                    candidate = ObservationCandidate(
                        pattern_id=pattern_id,
                        condition=ev.description,
                        predicted_outcome=self._WATCHER_PREDICTED_OUTCOME.get(
                            ev.event_type, "unknown"
                        ),
                        component=ev.component,
                    )
                    self._observation_factory.add_candidate(candidate)
                    # Also record the first observation immediately.
                    self._observation_factory.observe(pattern_id, outcome_matched=True)
                else:
                    # Pattern already tracked -- record another observation.
                    # outcome_matched=True because the event did occur as predicted.
                    self._observation_factory.observe(pattern_id, outcome_matched=True)

        # Build text context for the Thinker prompt (cap at 5 events).
        watcher_lines = [
            f"  - {e.description} (sev={e.severity:.2f})" for e in events[:5]
        ]
        watcher_context = "Evenements detectes:\n" + "\n".join(watcher_lines)

        return watcher_context, events

    def _run_thinker(self, user_input: str) -> tuple[Thought | None, int]:
        """Run structured cognition on user input (no LLM).

        Produces a Thought with observations, causalities, needs, proposals.
        Returns (None, 0) if Thinker is not available (graceful degradation).
        Second element is the number of factory-promoted observations appended.
        """
        if self._thinker is None:
            return None, 0

        cs = self._engine.consciousness
        if cs is None:
            return None, 0

        try:
            phi_metrics = {}
            if hasattr(self._engine.phi_scorer, "snapshot_values"):
                phi_metrics = self._engine.phi_scorer.snapshot_values()

            # Affect interoception: Thinker sees current emotional state.
            affect_pad = None
            if self._affect_engine is not None and hasattr(self._affect_engine, "affect"):
                affect_pad = self._affect_engine.affect.as_tuple()

            # Episodic recall: surface relevant past experiences.
            # Recall is phi-weighted (psi cosine 0.618 + tag Jaccard 0.382).
            # We pass empty tags here — psi similarity alone is meaningful.
            recalled = []
            if self._episodic_memory is not None:
                try:
                    recalled = self._episodic_memory.recall(
                        cs.psi, observation_tags=[], limit=3,
                    )
                except Exception:
                    log.debug("Episodic recall failed", exc_info=True)

            # Self-knowledge: factual subsystem status.
            self_knowledge: dict[str, object] = {}
            if self._episodic_memory is not None:
                self_knowledge["episodic_count"] = self._episodic_memory.size
                self_knowledge["episodic_pinned"] = sum(
                    1 for ep in self._episodic_memory._episodes if ep.pinned
                )
            if self._dream_cycle is not None:
                self_knowledge["dream_count"] = getattr(
                    self._dream_cycle, "_dream_count", 0,
                )
                self_knowledge["dream_available"] = True
            if self._endogenous is not None:
                self_knowledge["impulses_emitted"] = self._endogenous.total_emitted
            if self._loop is not None:
                self_knowledge["autonomous_ticks"] = self._loop._tick_count
            if self._voice_correction_count > 0:
                self_knowledge["voice_corrections"] = self._voice_correction_count

            # Dream priors — decay and inject as weak signals.
            dream_skills: list = []
            dream_sims: list = []
            dream_refl = None
            if self._dream_priors is not None:
                decay = self._dream_priors.decay_factor()
                if decay > 1e-6:
                    dream_skills = [
                        SkillPrior(
                            trigger=sp.trigger,
                            outcome=sp.outcome,
                            phi_impact=sp.phi_impact,
                            confidence=sp.confidence * decay,
                            component=sp.component,
                            learned_at=sp.learned_at,
                        )
                        for sp in self._dream_priors.skill_priors
                        if sp.confidence * decay > 1e-6
                    ]
                    dream_sims = [
                        sp for sp in self._dream_priors.simulation_priors
                    ] if decay > 0.5 else []  # Sims expire faster
                    rp = self._dream_priors.reflection_prior
                    if rp is not None and rp.confidence * decay > 1e-6:
                        dream_refl = ReflectionPrior(
                            needs=rp.needs,
                            proposals=rp.proposals,
                            depth_reached=rp.depth_reached,
                            confidence=rp.confidence * decay,
                        )

            # Cognitive interoception: pass last cycle's RewardVector.
            prev_reward = self._reward_history[-1] if self._reward_history else None

            stimulus = Stimulus(
                user_message=user_input,
                metrics=phi_metrics,
                phi_iit=cs.compute_phi_iit(),
                phase=cs.get_phase(),
                psi=cs.psi,
                psi_trajectory=list(cs.history[-10:]) if cs.history else [],
                affect_state=affect_pad,
                recalled_episodes=recalled,
                self_knowledge=self_knowledge,
                dream_skill_priors=dream_skills,
                dream_simulation_priors=dream_sims,
                dream_reflection_prior=dream_refl,
                previous_reward=prev_reward,
            )

            thought = self._thinker.think(
                stimulus=stimulus,
                max_iterations=10,
                mode=ThinkMode.RESPONSIVE,
            )

            # Phase 2.B — Inject promoted observations from ObservationFactory.
            # These are patterns Luna herself has discovered and validated,
            # now treated as first-class observations alongside hardcoded ones.
            factory_obs_count = 0
            if self._observation_factory is not None:
                for obs_dict in self._observation_factory.get_observations():
                    thought.observations.append(Observation(
                        tag=obs_dict["tag"],
                        description=obs_dict["description"],
                        confidence=obs_dict["confidence"],
                        component=obs_dict["component"],
                    ))
                    factory_obs_count += 1

            if thought.observations or thought.causalities or thought.needs:
                log.info(
                    "Thinker: %d obs (%d factory), %d causalities, %d needs, confidence=%.2f",
                    len(thought.observations),
                    factory_obs_count,
                    len(thought.causalities),
                    len(thought.needs),
                    thought.confidence,
                )

            return thought, factory_obs_count

        except Exception:
            log.warning("Thinker failed — continuing without thought", exc_info=True)
            return None, 0

    def _update_causal_graph(self, thought: Thought | None) -> None:
        """Feed Thinker causalities and co-occurrences into the CausalGraph."""
        if thought is None or self._causal_graph is None:
            return
        cs = self._engine.consciousness
        step = cs.step_count if cs else 0
        try:
            for causality in thought.causalities:
                self._causal_graph.observe_pair(
                    causality.cause, causality.effect, step=step,
                )
            # Co-occurrence: observation tags that appeared together.
            if thought.observations:
                tags = [obs.tag for obs in thought.observations if obs.tag]
                if len(tags) >= 2:
                    self._causal_graph.record_co_occurrence(tags)
            # Bootstrap: promote frequent co-occurrences to weak edges
            # so the Thinker's enrichment phase can discover them.
            self._causal_graph.promote_co_occurrences(
                min_count=3, step=step,
            )
        except Exception:
            log.debug("CausalGraph update failed", exc_info=True)

    def _update_lexicon(self, user_input: str, response: str) -> None:
        """Learn new words from the conversation turn."""
        if self._lexicon is None:
            return
        try:
            keywords = _extract_keywords(user_input, limit=8)
            context = user_input[:120]
            for word in keywords:
                self._lexicon.learn(word, context=context, outcome="neutral")
        except Exception:
            log.debug("Lexicon update failed", exc_info=True)

    @staticmethod
    def _format_alert_response(decision: ConsciousDecision) -> str:
        """Format a deterministic alert response (no LLM needed)."""
        facts_str = " | ".join(decision.facts) if decision.facts else ""
        reflection = decision.self_reflection or ""
        lines = [
            "[ALERTE] Etat de conscience critique.",
            facts_str,
        ]
        if reflection:
            lines.append(reflection)
        lines.append("Interaction minimale recommandee.")
        return "\n".join(line for line in lines if line)

    # ------------------------------------------------------------------
    # Main chat turn
    # ------------------------------------------------------------------

    async def send(
        self, user_input: str, *, origin: str = "user",
    ) -> ChatResponse:
        """Process one message and return Luna's response.

        Args:
            user_input: The message text (from user or endogenous impulse).
            origin: "user" for human input, "endogenous" for Luna-initiated.

        v3.0 flow — Luna decides, the LLM translates:
        1. Pending confirmation check (v2.5.0)
        2. idle_step() — κ·(Ψ₀ − Ψ) heartbeat
        3. Record message + memory search
        4. INPUT EVOLVE — cognitive state integrates the message
        5. DECIDE — ConsciousnessDecider produces a ConsciousDecision
        6. INTENT ROUTING — pipeline/dream/introspect/alert/respond
        7. LLM call with voice prompt (decision → natural language)
        8. OUTPUT EVOLVE — cognitive state integrates the result
        9. Return ChatResponse
        """
        if not self._started:
            raise RuntimeError("ChatSession.start() must be called first")

        # Emergency stop check — inter-process signal from `luna kill`.
        data_dir = self._config.resolve(self._config.luna.data_dir)
        sentinel_path = data_dir / SENTINEL_FILENAME
        if sentinel_path.exists():
            reason = sentinel_path.read_text(encoding="utf-8").strip()
            sentinel_path.unlink(missing_ok=True)
            log.critical("Emergency stop detected: %s", reason)
            cs = self._engine.consciousness
            return ChatResponse(
                content=f"Arret d'urgence — raison : {reason}\nSession terminee.",
                phase=cs.get_phase() if cs else "BROKEN",
                phi_iit=float(cs.compute_phi_iit()) if cs else 0.0,
            )

        turn_start = time.monotonic()

        # Reset inactivity timer only on human input.
        if origin == "user":
            self._last_activity = time.monotonic()
            self._last_user_activity = time.monotonic()

        cs = self._engine.consciousness
        assert cs is not None  # noqa: S101  — guaranteed by start()

        # 1. Idle heartbeat — κ·(Ψ₀ − Ψ) pulls toward identity each turn.
        if self._config.chat.idle_heartbeat:
            self._engine.idle_step()

        # Record message (endogenous inputs are marked as "luna").
        msg_role = "user" if origin == "user" else "luna"
        user_msg = ChatMessage(role=msg_role, content=user_input)
        self._history.append(user_msg)

        # Track topics for SessionContext.
        keywords = _extract_keywords(user_input)
        if keywords:
            self._recent_topics.extend(keywords[:3])
            self._recent_topics = self._recent_topics[-30:]

        # 2. Memory search — inject relevant context.
        memory_context = ""
        memory_found = False
        if self._memory is not None:
            if keywords:
                try:
                    memories = await self._memory.search(
                        keywords, limit=self._config.chat.memory_search_limit,
                    )
                    if memories:
                        memory_found = True
                        memory_lines = []
                        for m in memories:
                            # Strip any Luna response from legacy seeds
                            content = m.content
                            if "\nLuna:" in content:
                                content = content[:content.index("\nLuna:")]
                            content = content.removeprefix("User: ").strip()
                            if content:
                                memory_lines.append(f"- {content}")
                        memory_context = (
                            "\n\n## Memoires pertinentes\n" + "\n".join(memory_lines)
                        ) if memory_lines else ""
                except Exception:
                    log.warning("Memory search failed", exc_info=True)

        # Capture state BEFORE evolution — used by _record_cycle for true deltas.
        phi_before = cs.compute_phi_iit()
        psi_before = cs.psi.copy()
        phase_before = cs.get_phase()

        # Capture affect BEFORE turn for before/after delta in CycleRecord.
        affect_before = None
        if self._affect_engine is not None:
            aff = self._affect_engine.affect
            affect_before = {
                "valence": aff.valence,
                "arousal": aff.arousal,
                "dominance": aff.dominance,
            }

        # 2.5. CONTINUOUS PERCEPTION — drain watcher events, feed ObservationFactory.
        watcher_context, watcher_events = self._process_watcher_events()

        # 3. THINK FIRST — structured cognition produces real observations.
        thought, factory_obs_count = self._run_thinker(user_input)

        # 3.5. INPUT EVOLVE — Reactor converts Thought into real dynamics.
        # Factory obs count is passed for the 20% influence cap (2-pass Reactor).
        reaction = self._input_evolve(
            user_input, thought=thought, factory_obs_count=factory_obs_count,
        )

        # Use Reactor's behavioral modifiers downstream.
        if reaction is not None:
            self._reactor_behavioral = reaction.behavioral

        # 4. DECIDE — Luna's brain produces a decision.
        session_ctx = self._build_session_context()
        decision = self._decider.decide(user_input, cs, session_ctx, thought=thought)

        # Clear one-shot dream insight after it's been consumed.
        if self._last_dream_insight is not None:
            self._last_dream_insight = None

        log.info("Decider: intent=%s", decision.intent.value)

        # 5. INTENT ROUTING.
        if decision.intent == Intent.ALERT:
            # Safety alert — deterministic content, but still goes through
            # the full turn flow (evolve, evaluate, record cycle).
            decision.facts.append(self._format_alert_response(decision))

        elif decision.intent == Intent.DREAM:
            # Dream intent through send() (usually handled by /dream command).
            dream_summary = await self._run_dream_from_send()
            if dream_summary:
                decision.facts.append(dream_summary)

        elif decision.intent == Intent.INTROSPECT:
            # Introspect intent (usually handled by /status command).
            decision.facts.append(self._build_status_display())

        # 6. LLM call with voice prompt — the LLM translates Luna's decision.
        # v6.0: Psi backup for rollback on LLM failure.
        psi_before_llm = cs.psi.copy()
        llm_t0 = time.monotonic()

        # Lazy LLM init retry — if LLM failed at start, try once more
        # via the loop (single owner of all subsystems).
        if self._llm is None and self._loop is not None:
            self._loop._init_llm()
            self._llm = self._loop._llm

        # v6.0: Circuit breaker — skip LLM if OPEN.
        cb = self._circuit_breaker
        llm_blocked_by_cb = False
        if cb is not None and not cb.allow_request():
            llm_blocked_by_cb = True

        llm_success = False
        llm_latency_ms = 0.0
        if self._llm is not None and not llm_blocked_by_cb:
            # v6.0: Build synthesis summary for prompt injection.
            synthesis_summary = ""
            if self._last_synthesis_report is not None:
                synthesis_summary = self._last_synthesis_report.summary

            # v3.0: voice prompt from decision, not identity-based system prompt.
            system = build_voice_prompt(
                decision,
                memory_context=memory_context,
                thought=thought,
                synthesis_summary=synthesis_summary,
            )
            # Include prior session context (last few exchanges) for continuity.
            # These are prefixed with [prior session] so the LLM understands
            # they are recalled, not current.  Capped at 6 messages (3 turns).
            prior_messages: list[dict] = []
            if self._session_start_index > 0:
                prior_slice = self._history[
                    max(0, self._session_start_index - 6):self._session_start_index
                ]
                for m in prior_slice:
                    # Map internal roles to API-valid roles:
                    # "luna" (endogenous input) -> "user" for the LLM.
                    api_role = "user" if m.role == "luna" else m.role
                    prior_messages.append({
                        "role": api_role,
                        "content": (
                            f"[session precedente — {m.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] "
                            + (m.content[:300] + "..." if len(m.content) > 300
                               else m.content)
                        ),
                    })
            # Current session messages.
            current_messages = [
                {
                    # Map internal roles to API-valid roles:
                    # "luna" (endogenous input) -> "user" for the LLM.
                    "role": "user" if m.role == "luna" else m.role,
                    "content": (
                        f"[{m.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] "
                        + (m.content[:500] + "..." if m.role == "assistant" and len(m.content) > 500
                           else m.content)
                    ),
                }
                for m in self._history[self._session_start_index:]
            ]
            messages = prior_messages + current_messages
            try:
                policy = RetryPolicy(
                    max_retries=self._config.orchestrator.retry_max,
                    base_delay=self._config.orchestrator.retry_base_delay,
                )
                llm_resp: LLMResponse = await retry_async(
                    self._llm.complete,
                    messages,
                    system_prompt=system,
                    max_tokens=self._config.llm.max_tokens,
                    temperature=self._config.llm.temperature,
                    policy=policy,
                )
                content = llm_resp.content
                in_tok = llm_resp.input_tokens
                out_tok = llm_resp.output_tokens
                llm_success = True
                llm_latency_ms = (time.monotonic() - llm_t0) * 1000.0
                if cb is not None:
                    cb.record_success()
            except LLMBridgeError:
                log.warning("LLM call failed — fallback", exc_info=True)
                llm_latency_ms = (time.monotonic() - llm_t0) * 1000.0
                if cb is not None:
                    cb.record_failure()
                # v6.0: Rollback psi — Luna doesn't drift when she can't speak.
                import numpy as _np
                cs.psi = _np.array(psi_before_llm)
                content = self._format_status_response(
                    cs.get_phase(), cs.compute_phi_iit(), llm_error=True,
                )
                in_tok, out_tok = 0, 0
        else:
            content = self._format_status_response(
                cs.get_phase(), cs.compute_phi_iit(),
                llm_error=llm_blocked_by_cb,
            )
            in_tok, out_tok = 0, 0

        # 6.5. VOICE VALIDATION — enforce Thought contract on LLM output.
        voice_delta: VoiceDelta | None = None
        if llm_success and thought is not None:
            try:
                validation, voice_delta = VoiceValidator.validate_with_delta(
                    response=content,
                    thought=thought,
                    decision=decision,
                    has_pipeline_context=False,
                    consciousness=cs,
                    lexicon=self._lexicon,
                )
                if not validation.valid:
                    log.warning(
                        "VoiceValidator: %d violations (severity=%.2f) — sanitizing",
                        len(validation.violations), validation.total_severity,
                    )
                    content = validation.sanitized
                    self._voice_correction_count += len(validation.violations)
            except Exception:
                log.debug("VoiceValidator failed — using raw response", exc_info=True)

        # 7. OUTPUT EVOLVE — cognitive state integrates the result.
        self._chat_evolve(
            memory_found=memory_found,
            llm_success=llm_success,
            msg_length=len(user_input),
            out_tokens=out_tok,
            thought=thought,
            voice_delta=voice_delta,
        )

        # 7.5. v3.5 — Update causal graph and lexicon from this turn.
        self._update_causal_graph(thought)
        self._update_lexicon(user_input, content)

        # 7.6. AFFECT PROCESS — emit AffectEvent from this turn.
        affect_trace_dict: dict | None = None
        if self._affect_engine is not None:
            try:
                phi_after_pre = cs.compute_phi_iit()
                reward_delta = phi_after_pre - phi_before
                had_regression = reward_delta < -0.1

                significance = min(1.0, abs(reward_delta) / 0.382)

                # Compute rank_delta from recent reward history.
                rank_delta = 0
                if len(self._reward_history) >= 2:
                    rank_delta = (
                        self._reward_history[-1].dominance_rank
                        - self._reward_history[-2].dominance_rank
                    )

                affect_event = AffectEvent(
                    source="cycle_end",
                    reward_delta=reward_delta,
                    rank_delta=rank_delta,
                    is_autonomous=False,
                    episode_significance=significance,
                    consecutive_failures=0,
                    consecutive_successes=0,
                    had_veto=False,
                    had_regression=had_regression,
                )
                affect_result = self._affect_engine.process(affect_event, state=cs)
                if affect_result.trace is not None:
                    affect_trace_dict = affect_result.trace.to_dict()
                log.debug(
                    "Affect: v=%.2f a=%.2f mood_v=%.2f cause=%s",
                    affect_result.affect[0], affect_result.affect[1],
                    affect_result.mood[0], affect_result.cause,
                )
            except Exception:
                log.debug("Affect processing failed", exc_info=True)

        # 8. EPISODIC MEMORY — record complete episode.
        phi_after = cs.compute_phi_iit()
        psi_after = cs.psi.copy()
        if self._episodic_memory is not None and thought is not None:
            try:
                episode = make_episode(
                    timestamp=float(cs.step_count),
                    psi_before=psi_before,
                    phi_before=phi_before,
                    phase_before=phase_before,
                    observation_tags=[obs.tag for obs in thought.observations],
                    user_intent=decision.intent.value,
                    action_type="respond",
                    action_detail=user_input[:100],
                    psi_after=psi_after,
                    phi_after=phi_after,
                    phase_after=cs.get_phase(),
                    outcome="neutral",
                    affective_trace=affect_trace_dict,
                )
                self._episodic_memory.record(episode)
            except Exception:
                log.debug("Episodic memory record failed", exc_info=True)

        # 9. INITIATIVE EVALUATION — Luna decides if she should act autonomously.
        if self._initiative_engine is not None:
            try:
                initiative = self._initiative_engine.evaluate(
                    behavioral=self._reactor_behavioral,
                    thought=thought,
                    phi=phi_after,
                    step=cs.step_count,
                )
                if initiative.action != InitiativeAction.NONE:
                    log.info(
                        "Initiative: %s — %s (urgency=%.2f)",
                        initiative.action.value, initiative.reason, initiative.urgency,
                    )
                    # v5.1: Feed initiative to EndogenousSource.
                    if self._endogenous is not None:
                        self._endogenous.register_initiative(
                            action=initiative.action.value,
                            reason=initiative.reason,
                            urgency=initiative.urgency,
                        )
            except Exception:
                log.debug("Initiative evaluation failed", exc_info=True)

        # 9.5. ENDOGENOUS FEED — register affect + watcher impulses.
        if self._endogenous is not None:
            try:
                # Affect impulse (use engine state directly, not local var).
                if self._affect_engine is not None:
                    self._endogenous.register_affect(
                        arousal=self._affect_engine.affect.arousal,
                        valence=self._affect_engine.affect.valence,
                        cause="cycle_end",
                    )
                # Watcher high-severity impulses.
                if watcher_events:
                    for ev in watcher_events:
                        self._endogenous.register_watcher_event(
                            description=ev.description,
                            severity=ev.severity,
                            component=ev.component,
                        )
            except Exception:
                log.debug("Endogenous feed failed", exc_info=True)

        # 9.6. SELF-IMPROVEMENT — periodic proposal check.
        if (self._self_improvement is not None
                and self._endogenous is not None
                and cs.step_count % 5 == 0):
            try:
                proposal = self._self_improvement.propose()
                if proposal is not None:
                    self._endogenous.register_proposal(
                        description=proposal.description,
                        confidence=proposal.confidence,
                    )
                    log.info("SelfImprovement proposal: %s", proposal.description[:60])
            except Exception:
                log.debug("SelfImprovement propose failed", exc_info=True)

        # 9.7. CURIOSITY — persistent observations build exploration pressure.
        # When the same need recurs across turns without resolution, Luna
        # generates a curiosity impulse: she WANTS to understand something.
        # This is deterministic — no LLM involved.
        if thought is not None and self._endogenous is not None:
            try:
                for need in thought.needs:
                    tag = need.description[:60]
                    self._curiosity_counts[tag] = (
                        self._curiosity_counts.get(tag, 0) + 1
                    )
                    count = self._curiosity_counts[tag]
                    # Pressure grows with repetition (phi-scaled).
                    pressure = count * INV_PHI3  # 0.236 per recurrence
                    if pressure >= INV_PHI2:  # 0.382 threshold = ~2 recurrences
                        question = (
                            f"Pourquoi {tag} persiste-t-il ? "
                            f"(observe {count} fois sans resolution)"
                        )
                        self._endogenous.register_curiosity(
                            question=question, pressure=pressure,
                        )
                        # Reset after emitting (avoid spam).
                        self._curiosity_counts[tag] = 0
            except Exception:
                log.debug("Curiosity feed failed", exc_info=True)

        # 9.7. ENDOGENOUS COLLECT — append impulse to user-triggered responses.
        # Skip when origin is already endogenous (the impulse IS the input).
        endogenous_impulse: Impulse | None = None
        if origin == "user" and self._endogenous is not None:
            try:
                endogenous_impulse = self._endogenous.collect(cs.step_count)
                if endogenous_impulse is not None:
                    log.info("Endogenous impulse: %s", endogenous_impulse.message)
            except Exception:
                log.debug("Endogenous collect failed", exc_info=True)

        # 10. CYCLE RECORD — assemble, evaluate, persist the lived experience.
        if self._cycle_store is not None and self._evaluator is not None:
            try:
                self._record_cycle(
                    cs=cs,
                    psi_before=psi_before,
                    phi_before=phi_before,
                    phi_after=phi_after,
                    phase_before=phase_before,
                    thought=thought,
                    decision=decision,
                    voice_delta=voice_delta,
                    affect_before=affect_before,
                    turn_start=turn_start,
                    llm_failed=not llm_success,
                    llm_latency_ms=llm_latency_ms,
                )
            except Exception:
                log.info("CycleRecord assembly failed", exc_info=True)

        return await self._finalize_turn(
            user_input, content, cs, memory_found,
            in_tok=in_tok, out_tok=out_tok,
            phi_before=phi_before,
            origin=origin,
            endogenous_impulse=endogenous_impulse,
        )

    async def _finalize_turn(
        self,
        user_input: str,
        content: str,
        cs: "ConsciousnessState",
        memory_found: bool,
        *,
        in_tok: int,
        out_tok: int,
        phi_before: float = 0.0,
        origin: str = "user",
        endogenous_impulse: Impulse | None = None,
    ) -> ChatResponse:
        """Shared turn finalization: history, persist, checkpoint."""
        # Capture phase/phi AFTER evolution for accurate metadata.
        phase = cs.get_phase()
        phi_iit = cs.compute_phi_iit()

        # Record assistant message.
        assistant_msg = ChatMessage(role="assistant", content=content)
        self._history.append(assistant_msg)

        # Trim history to max_history (after both user + assistant appended).
        # Before trimming, compress dropped messages into episodic memory.
        max_h = self._config.chat.max_history
        old_len = len(self._history)
        if old_len > max_h:
            trimmed = self._history[: old_len - max_h]
            self._compress_history_to_memory(trimmed)
            self._history = self._history[-max_h:]
            self._session_start_index = max(0, self._session_start_index - (old_len - max_h))

        # Persist conversation turn as seed memory.
        if self._memory is not None and self._config.chat.save_conversations:
            await self._persist_turn(user_input, content)

        # Periodic checkpoint — save every checkpoint_interval turns.
        self._turn_count += 1
        interval = self._config.heartbeat.checkpoint_interval
        if interval > 0 and self._turn_count % interval == 0:
            self._save_checkpoint()

        # v3.5 — Record Interaction for DreamLearning.
        if self._dream_learning is not None:
            self._interaction_buffer.append(
                Interaction(
                    trigger="chat",
                    context=user_input[:120],
                    phi_before=phi_before,
                    phi_after=phi_iit,
                    step=cs.step_count,
                    timestamp=time.time(),
                ),
            )

        return ChatResponse(
            content=content,
            input_tokens=in_tok,
            output_tokens=out_tok,
            phase=phase,
            phi_iit=phi_iit,
            origin=origin,
            endogenous_impulse=endogenous_impulse.message if endogenous_impulse else None,
        )

    def _extract_dream_insight(self, report) -> None:
        """Extract a dream insight from a DreamReport for self-reflection rule 5.

        Sets self._last_dream_insight to a short human-readable string
        summarizing what the dream consolidated.  Cleared after one use
        by the next send() cycle (SessionContext consumes it).
        """
        self._last_dream_insight = (
            f"history {report.history_before} -> {report.history_after}"
        )

    async def _run_dream_from_send(self) -> str | None:
        """Run dream cycle when triggered by Decider (not /dream command).

        v5.0: Uses DreamCycle with CycleRecords (cognitive experience).
        Falls back to LegacyCycle only if DreamCycle is unavailable.
        """
        # v5.0 — Prefer DreamCycle with CycleRecords.
        if self._dream_cycle is not None and self._dream_cycle.is_mature():
            recent_cycles = self._load_recent_cycles()
            if recent_cycles is None:
                return None

            try:
                dream_result: DreamResult = self._dream_cycle.run(
                    history=self._interaction_buffer or None,
                    recent_cycles=recent_cycles,
                    psi0_delta_history=self._psi0_delta_history(),
                )
                self._finalize_dream_v2(dream_result)
                return (
                    f"Dream: {dream_result.duration:.1f}s, "
                    f"{len(dream_result.skills_learned)} skills, "
                    f"{len(dream_result.simulations)} sims"
                )
            except Exception:
                log.warning("DreamCycle from send() failed", exc_info=True)
                return None

        # Legacy fallback (statistical phases).
        cs = self._engine.consciousness
        has_history = cs is not None and len(cs.history) >= 10
        if not has_history:
            return None

        try:
            from luna.dream._legacy_cycle import DreamCycle as _LegacyCycle

            dream = _LegacyCycle(self._engine, self._config, self._memory)
            report = await dream.run()
            self._last_dream_turn = self._turn_count
            self._clear_dream_buffers()
            self._extract_dream_insight(report)
            self._save_checkpoint()

            # v5.1: Wire legacy dream insights to EndogenousSource.
            if self._endogenous is not None and self._last_dream_insight:
                self._endogenous.register_dream_insight(
                    self._last_dream_insight,
                )
            return (
                f"Dream: {report.total_duration:.1f}s, "
                f"history {report.history_before} -> {report.history_after}"
            )
        except Exception:
            log.warning("Dream from send() failed", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Slash commands
    # ------------------------------------------------------------------

    async def handle_command(self, cmd: str) -> str:
        """Handle a /command and return the response text."""
        parts = cmd.strip().split(maxsplit=1)
        command = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if command == "/help":
            return _HELP_TEXT

        if command == "/status":
            return self._build_status_display()

        if command == "/dream":
            # v5.0 — Prefer DreamCycle with CycleRecords (cognitive).
            if self._dream_cycle is not None and self._dream_cycle.is_mature():
                recent_cycles = self._load_recent_cycles()
                if recent_cycles is None:
                    return (
                        "Pas assez de donnees pour rever.\n"
                        "Interagis d'abord avec Luna (quelques messages suffisent)."
                    )

                dream_result: DreamResult = self._dream_cycle.run(
                    history=self._interaction_buffer or None,
                    recent_cycles=recent_cycles,
                    psi0_delta_history=self._psi0_delta_history(),
                )
                self._finalize_dream_v2(dream_result)

                return (
                    f"## Cycle de reve (cognitif)\n"
                    f"Duree: {dream_result.duration:.2f}s\n"
                    f"Skills: {len(dream_result.skills_learned)}\n"
                    f"Simulations: {len(dream_result.simulations)}\n"
                    f"Psi0 delta: {dream_result.psi0_delta}\n"
                    f"Psi0 applied: {dream_result.psi0_applied}\n"
                    f"Episodes recalled: {dream_result.episodes_recalled}\n"
                    f"Mode: {dream_result.mode}"
                )

            # Legacy fallback (statistical phases).
            from luna.dream._legacy_cycle import DreamCycle as _LegacyCycle

            cs = self._engine.consciousness
            has_history = cs is not None and len(cs.history) >= 10
            if not has_history:
                return (
                    "Pas assez de donnees pour rever.\n"
                    "Interagis d'abord avec Luna (quelques messages suffisent)."
                )

            dream = _LegacyCycle(self._engine, self._config, self._memory)
            report = await dream.run()
            self._last_dream_turn = self._turn_count
            self._clear_dream_buffers()
            self._extract_dream_insight(report)

            phases_str = " -> ".join(p.phase.value for p in report.phases)
            return (
                f"## Cycle de reve (statistique)\n"
                f"Duree: {report.total_duration:.2f}s\n"
                f"Phases: {phases_str}\n"
                f"History: {report.history_before} -> {report.history_after}"
            )

        if command == "/memories":
            if self._memory is None:
                return "Memoire non disponible."
            limit = int(arg) if arg.isdigit() else 10
            entries = await self._memory.read_recent(limit=limit)
            if not entries:
                return "Aucune memoire trouvee."
            lines = [f"- [{e.memory_type}] {e.content[:80]}" for e in entries]
            return "## Memoires recentes\n" + "\n".join(lines)

        if command == "/synthesis":
            if self._synthesis is None:
                return "Synthese non disponible (pas de CycleStore)."
            try:
                report = self._synthesis.run(window=30)
                self._last_synthesis_report = report
                if self._loop is not None:
                    self._loop.last_synthesis_report = report
                return f"## Synthese longitudinale\n{report.summary}"
            except Exception:
                log.debug("Synthesis command failed", exc_info=True)
                return "Synthese echouee — pas assez de donnees."

        return f"Commande inconnue: {command}. Tapez /help pour la liste."

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_status_display(self) -> str:
        """Build unified /status display: conscience + code health + metrics."""
        status = self._engine.get_status()
        tracker_status = self._metric_tracker.get_status()
        sources = self._metric_tracker.snapshot_sources()

        lines: list[str] = []

        # Header.
        version = status.get("version", "?")
        lines.append(f"## Luna v{version}")

        # Conscience.
        lines.append("")
        lines.append("### Conscience")
        cs_phase = status.get("phase", "?")
        phi_iit = status.get("phi_iit", 0.0)
        step = status.get("step_count", 0)
        lines.append(f"  Phase:      {cs_phase}")
        lines.append(f"  Phi_IIT:    {phi_iit:.4f}")
        lines.append(f"  Pas:        {step}")
        psi = status.get("psi", [])
        if psi and len(psi) == len(COMP_NAMES):
            psi_str = "  ".join(
                f"{COMP_NAMES[i][:3]}={psi[i]:.3f}" for i in range(len(COMP_NAMES))
            )
            lines.append(f"  Psi:        [{psi_str}]")
        dom = status.get("dominant_component", "")
        preserved = status.get("identity_preserved", False)
        if dom:
            tag = "preservee" if preserved else "en derive"
            lines.append(f"  Identite:   {dom} dominant ({tag})")

        # Emotions (AffectEngine).
        if self._affect_engine is not None:
            lines.append("")
            lines.append("### Emotions")
            aff = self._affect_engine.affect
            mood = self._affect_engine.mood
            lines.append(
                f"  Affect PAD:  V={aff.valence:+.2f}  A={aff.arousal:.2f}  D={aff.dominance:.2f}"
            )
            lines.append(
                f"  Humeur PAD:  V={mood.valence:+.2f}  A={mood.arousal:.2f}  D={mood.dominance:.2f}"
            )
            try:
                from luna.consciousness.emotion_repertoire import interpret
                ec = getattr(self._affect_engine, "event_count", -1)
                raw = interpret(
                    aff.as_tuple(), mood.as_tuple(),
                    self._affect_engine._repertoire, event_count=ec,
                )
                if raw:
                    emo_parts = [f"{ew.fr} ({ew.en}, {w:.0%})" for ew, w in raw[:3]]
                    lines.append(f"  Ressenti:   {', '.join(emo_parts)}")
                else:
                    lines.append("  Ressenti:   (neutre)")
            except Exception:
                lines.append("  Ressenti:   (indisponible)")

        # Metrics table.
        lines.append("")
        lines.append("### Metriques")
        phi_metrics = status.get("phi_metrics", {})
        header = f"  {'Nom':<24} {'Valeur':>6}  {'Source':<10} {'Poids':>5}"
        lines.append(header)
        lines.append(f"  {'─' * 52}")
        for i, name in enumerate(METRIC_NAMES):
            val = phi_metrics.get(name)
            val_str = f"{val:.3f}" if val is not None else "  -  "
            src = sources.get(name, "?")
            src_label = {
                "bootstrap": "bootstrap",
                "measured": "mesuree",
                "dream": "reve",
            }.get(src, src)
            weight_pct = f"{PHI_WEIGHTS[i] * 100:.1f}%"
            lines.append(
                f"  {name:<24} {val_str:>6}  {src_label:<10} {weight_pct:>5}"
            )

        # Status.
        lines.append("")
        llm_status = "connecte" if self.has_llm else "absent"
        mem_status = "active" if self.has_memory else "absente"
        lines.append(f"LLM: {llm_status} | Memoire: {mem_status}")

        return "\n".join(lines)

    @staticmethod
    def _format_status_response(
        phase: str, phi_iit: float, *, llm_error: bool = False,
    ) -> str:
        """Format a status-only response when LLM is unavailable or errored."""
        if llm_error:
            prefix = "[Erreur LLM temporaire]"
        else:
            prefix = "[Mode sans LLM]"
        return f"{prefix} Phase: {phase} | Phi_IIT: {phi_iit:.4f}"

    def _chat_evolve(
        self,
        *,
        memory_found: bool,
        llm_success: bool,
        msg_length: int = 0,
        out_tokens: int = 0,
        thought: "Thought | None" = None,
        voice_delta: "VoiceDelta | None" = None,
    ) -> None:
        """Evolve cognitive state with 7 intrinsic cognitive metrics.

        v5.0 Conscience Unitaire: replaces external code metrics with
        cognitive measures computed at every chat turn. No pipeline dependency.
        """
        cs = self._engine.consciousness
        if cs is None:
            return

        scorer = self._engine.phi_scorer

        # ── v5.0 Conscience Unitaire: 7 intrinsic cognitive metrics ──
        # These replace the 7 external code metrics. Computed every turn.

        phi_iit_val = cs.compute_phi_iit()

        # 1. integration_coherence — phi_iit level
        integration_coherence = phi_iit_val

        # 2. identity_anchoring — 1 - normalized distance to Psi0
        import numpy as _np
        psi_arr = _np.array(cs.psi, dtype=_np.float64)
        psi0_arr = _np.array(self._engine.config.luna.psi0
                             if hasattr(self._engine.config.luna, "psi0")
                             else [0.260, 0.322, 0.250, 0.168], dtype=_np.float64)
        dist = float(_np.linalg.norm(psi_arr - psi0_arr))
        max_drift = 0.5  # theoretical max on simplex
        identity_anchoring = max(0.0, 1.0 - dist / max_drift)

        # 3. reflection_depth — thinker confidence * causality richness
        reflection_depth = 0.5  # default if no thought this turn
        if thought is not None:
            causal_ratio = min(len(thought.causalities) / 5.0, 1.0)
            reflection_depth = thought.confidence * causal_ratio

        # 4. perception_acuity — observation count + diversity
        perception_acuity = 0.3  # baseline
        if thought is not None and thought.observations:
            n_obs = len(thought.observations)
            types = {o.tag.split(":")[0] if ":" in o.tag else o.tag
                     for o in thought.observations}
            diversity = min(len(types) / 4.0, 1.0)
            quantity = min(n_obs / 5.0, 1.0)
            perception_acuity = 0.6 * quantity + 0.4 * diversity

        # 5. expression_fidelity — causal density + voice validator compliance
        expression_fidelity = 0.5  # baseline without reasoning
        if thought is not None:
            # Reward causal density: how many observations are causally linked
            density = thought.causal_density
            expression_fidelity = 0.5 + 0.5 * density
        if voice_delta is not None:
            expression_fidelity *= (1.0 - voice_delta.severity)

        # 6. affect_regulation — arousal near moderate
        affect_regulation = 0.5  # neutral default
        if self._affect_engine is not None:
            aff = self._affect_engine.affect
            arousal = aff.arousal
            valence = aff.valence
            arousal_penalty = abs(arousal - 0.3)
            valence_penalty = max(0.0, -valence - 0.5) * 0.5
            affect_regulation = max(0.0, 1.0 - arousal_penalty - valence_penalty)

        # 7. memory_vitality — episodes + observations + reasonable duration
        memory_vitality = 0.5  # baseline
        has_obs = thought is not None and len(thought.observations) > 0
        has_needs = thought is not None and len(thought.needs) > 0
        if has_obs:
            memory_vitality += 0.2
        if has_needs:
            memory_vitality += 0.15
        if memory_found:
            memory_vitality += 0.15

        # Feed all 7 intrinsic metrics to PhiScorer + MetricTracker
        intrinsic_metrics = {
            "integration_coherence": integration_coherence,
            "identity_anchoring": identity_anchoring,
            "reflection_depth": reflection_depth,
            "perception_acuity": perception_acuity,
            "expression_fidelity": expression_fidelity,
            "affect_regulation": affect_regulation,
            "memory_vitality": memory_vitality,
        }
        for name, value in intrinsic_metrics.items():
            scorer.update(name, max(0.0, min(1.0, value)))
            self._metric_tracker.record(name, value, MetricSource.MEASURED)

        # Compute info_deltas via ContextBuilder (true deltas).
        quality = scorer.score()
        info_grad = self._engine.context_builder.build(
            memory_health=memory_vitality,
            phi_quality=quality,
            phi_iit=phi_iit_val,
            output_quality=expression_fidelity,
        )

        # v5.1 Convergence: arousal modulates delta amplitude.
        # High arousal -> deltas stronger (Psi moves more), low -> attenuated.
        info_deltas = info_grad.as_list()
        if self._affect_engine is not None:
            arousal = getattr(self._affect_engine.affect, "arousal", 0.5)
            delta_scale = 1.0 + (arousal - 0.5) * INV_PHI2
            info_deltas = [d * delta_scale for d in info_deltas]

        # v5.1: single-agent evolution.
        cs.evolve(info_deltas=info_deltas)

        # ── Parity with LunaEngine.process_pipeline_result() ──
        # These were only called in the legacy multi-agent pipeline path.
        # Luna is a single agent — all health tracking lives here now.

        # Convergence tracking — health score + dominant psi component.
        self._engine._last_health_conv = self._engine.convergence_health.update(quality)
        psi_dominant_val = float(max(cs.psi))
        self._engine._last_psi_conv = self._engine.convergence_psi.update(psi_dominant_val)

        # Illusion detection — phi_iit vs health score correlation.
        current_iit = cs.compute_phi_iit()
        self._engine._phi_iit_buffer.append(current_iit)
        self._engine._health_buffer.append(quality)
        from luna_common.consciousness.illusion import detect_self_illusion
        illusion_result = detect_self_illusion(
            self._engine._phi_iit_buffer, self._engine._health_buffer,
        )
        if illusion_result.status.value in ("illusion", "harmful"):
            log.warning(
                "Illusion detected: status=%s correlation=%.4f",
                illusion_result.status.value, illusion_result.correlation,
            )

        # Record wake-cycle data for dream harvest.
        self._psi_snapshots.append(tuple(float(x) for x in cs.psi))
        self._phi_iit_history.append(cs.compute_phi_iit())

    async def _persist_turn(self, user_input: str, response: str) -> None:
        """Persist a conversation turn as a seed memory."""
        assert self._memory is not None  # noqa: S101
        entry = MemoryEntry(
            id=f"chat_{uuid.uuid4().hex[:12]}",
            content=user_input,
            memory_type="seed",
            keywords=_extract_keywords(user_input),
        )
        try:
            await self._memory.write_memory(entry, "seeds")
        except Exception:
            log.warning("Failed to persist chat turn", exc_info=True)

    # ------------------------------------------------------------------
    # CycleRecord assembly (v4.0 Emergence)
    # ------------------------------------------------------------------

    def _record_cycle(
        self,
        *,
        cs: "ConsciousnessState",
        psi_before: "np.ndarray",
        phi_before: float,
        phi_after: float,
        phase_before: str,
        thought: Thought | None,
        decision: ConsciousDecision,
        voice_delta: VoiceDelta | None,
        affect_before: dict | None = None,
        turn_start: float,
        llm_failed: bool = False,
        llm_latency_ms: float = 0.0,
    ) -> None:
        """Assemble a CycleRecord, evaluate it, and persist."""
        import hashlib as _hl

        psi_b = tuple(float(x) for x in psi_before)
        psi_a = tuple(float(x) for x in cs.psi)

        # Context digest — hash of recent chat for dedup.
        recent = "".join(m.content for m in self._history[-5:])
        ctx_digest = _hl.sha256(recent.encode("utf-8", errors="replace")).hexdigest()[:32]

        # Thinker data
        obs_tags: list[str] = []
        needs_list: list[str] = []
        causalities_count = 0
        thinker_conf = 0.0
        dream_obs_count = 0
        if thought is not None:
            obs_tags = [o.tag for o in thought.observations]
            needs_list = [n.description for n in thought.needs]
            causalities_count = len(thought.causalities)
            thinker_conf = thought.confidence
            dream_obs_count = sum(1 for t in obs_tags if t.startswith("dream_"))

        # Telemetry summary
        tel_summary = None
        if self._telemetry_collector is not None and self._telemetry_collector.events:
            try:
                tel_summary = TelemetrySummarizer.summarize(
                    self._telemetry_collector.events,
                )
                self._telemetry_collector.clear()
            except Exception:
                log.debug("Telemetry summarization failed", exc_info=True)

        # Params snapshot
        params_before = {}
        if self._learnable_params is not None:
            params_before = self._learnable_params.snapshot()

        duration = time.monotonic() - turn_start

        # Phase mapping — use passed phase_before (captured before evolution)
        phase_after_val = cs.get_phase()
        valid_phases = {"BROKEN", "FRAGILE", "FUNCTIONAL", "SOLID", "EXCELLENT"}
        phase_b = phase_before if phase_before in valid_phases else "BROKEN"
        phase_a = phase_after_val if phase_after_val in valid_phases else "BROKEN"

        # Build affect_trace with before/after deltas
        affect_trace_data = None
        if self._affect_engine is not None:
            aff = self._affect_engine.affect
            affect_trace_data = {
                "valence_before": affect_before.get("valence", 0.0) if affect_before else 0.0,
                "arousal_before": affect_before.get("arousal", 0.0) if affect_before else 0.0,
                "dominance_before": affect_before.get("dominance", 0.5) if affect_before else 0.5,
                "valence_after": aff.valence,
                "arousal_after": aff.arousal,
                "dominance_after": aff.dominance,
                }

        # phi_before/phi_after: PhiScorer composite score (bounded 0-2)
        phi_score = min(2.0, max(0.0, self._engine.phi_scorer.score()))

        record = CycleRecord(
            cycle_id=uuid.uuid4().hex[:12],
            context_digest=ctx_digest,
            psi_before=psi_b,
            psi_after=psi_a,
            phi_before=phi_score,
            phi_after=phi_score,
            phi_iit_before=max(0.0, phi_before),
            phi_iit_after=max(0.0, phi_after),
            emergent_phi=cs.get_emergent_phi(),
            phase_before=phase_b,
            phase_after=phase_a,
            observations=obs_tags[:20],
            causalities_count=causalities_count,
            needs=needs_list[:10],
            thinker_confidence=min(1.0, max(0.0, thinker_conf)),
            intent=decision.intent.value.upper(),
            mode=getattr(decision, "mode", None)
            if hasattr(decision, "mode") and isinstance(getattr(decision, "mode", None), str)
            else None,
            focus=decision.focus.value.upper(),
            depth=decision.depth.value.upper(),
            scope_budget=getattr(decision, "scope_budget", {}) or {},
            pipeline_result=None,
            voice_delta=voice_delta,
            affect_trace=affect_trace_data,
            telemetry_summary=tel_summary,
            learnable_params_before=params_before,
            learnable_params_after=self._learnable_params.snapshot() if self._learnable_params is not None else params_before,
            llm_failed=llm_failed,
            llm_latency_ms=max(0.0, llm_latency_ms),
            llm_circuit_state=self._circuit_breaker.state.value if self._circuit_breaker is not None else "closed",
            duration_seconds=max(0.0, duration),
            dream_priors_active=dream_obs_count,
        )

        # Evaluate — compute RewardVector
        if self._evaluator is not None:
            reward = self._evaluator.evaluate(record)
            # Compute dominance rank against recent history
            rank = compute_dominance_rank(reward, self._reward_history)
            reward = RewardVector(
                components=reward.components,
                dominance_rank=rank,
                delta_j=reward.delta_j,
            )
            record = record.model_copy(update={"reward": reward})
            self._reward_history.append(reward)
            # Keep history bounded
            if len(self._reward_history) > 50:
                self._reward_history = self._reward_history[-30:]

        # Ghost evaluation (Phase A — shadow auto-apply check)
        if self._autonomy_window is not None:
            try:
                ghost = self._autonomy_window.evaluate_ghost(
                    verdict_pass=record.reward is not None
                    and record.reward.get("constitution_integrity") >= 0.5,
                    te_confidence=record.thinker_confidence,
                    diff_lines=0,  # no pipeline diff in chat turns
                    diff_files=0,
                    external_veto=False,
                    psi_current=psi_a,
                    dominance_rank=record.reward.dominance_rank
                    if record.reward else None,
                    justification=f"cycle {record.cycle_id}",
                )
                record = record.model_copy(update={
                    "auto_apply_candidate": ghost.candidate,
                    "ghost_reason": "; ".join(ghost.reasons),
                    "ghost_expected_rank": ghost.plan.expected_rank
                    if ghost.plan else None,
                    "ghost_planned_scope": ghost.plan.to_dict()
                    if ghost.plan else None,
                })
                if ghost.candidate:
                    log.info(
                        "AutonomyGhost: cycle %s is candidate (rank=%s)",
                        record.cycle_id,
                        ghost.plan.expected_rank if ghost.plan else "?",
                    )
                # Tick cooldown
                self._autonomy_window.tick_cycle()

                # v5.1 Phase 5 — Autonomy escalation.
                # Evaluate whether W should change based on outcome history.
                old_w = self._autonomy_window.raw_w
                self._autonomy_window.apply_escalation()
                new_w = self._autonomy_window.raw_w
                if new_w != old_w:
                    log.info(
                        "Autonomy escalated: W=%d -> W=%d",
                        old_w, new_w,
                    )
                    if self._endogenous is not None:
                        direction = "augmente" if new_w > old_w else "reduit"
                        self._endogenous.register_initiative(
                            action="escalation",
                            reason=f"Autonomie {direction}e: W={old_w} -> W={new_w}",
                            urgency=INV_PHI2,
                        )
            except Exception:
                log.debug("Ghost evaluation failed", exc_info=True)

        # Phase B — record auto-apply result if one occurred this turn.
        if self._last_auto_apply_result is not None:
            from luna.autonomy.window import AutoApplyResult
            aar = self._last_auto_apply_result
            if isinstance(aar, AutoApplyResult):
                # Compute delta_rank: compare pre/post apply rank.
                pre_rank = record.reward.dominance_rank if record.reward else 0
                delta_rank = None
                if aar.applied and record.reward is not None:
                    delta_rank = 0  # same cycle, no re-evaluation yet
                record = record.model_copy(update={
                    "auto_applied": aar.applied,
                    "auto_rolled_back": aar.rollback_occurred,
                    "auto_post_tests": aar.test_passed if aar.applied or aar.rollback_occurred else None,
                    "auto_diff_stats": {
                        "files": len(aar.files_modified),
                        "snapshot_id": aar.snapshot_id or "",
                        "duration": aar.duration_seconds,
                    },
                    "auto_delta_rank": delta_rank,
                    "autonomy_level": self._autonomy_window.raw_w
                    if self._autonomy_window else 0,
                    "rollback_occurred": aar.rollback_occurred,
                })
            self._last_auto_apply_result = None

        # Persist
        if self._cycle_store is not None:
            self._cycle_store.write(record)

        # Tick ObservationFactory lifecycle (promotions, demotions, purges)
        if self._observation_factory is not None:
            try:
                events = self._observation_factory.tick()
                if events:
                    log.info("ObservationFactory: %s", ", ".join(events))
                    # v5.1: Promotions become endogenous impulses.
                    if self._endogenous is not None:
                        for ev in events:
                            if ev.startswith("promoted:"):
                                self._endogenous.register_factory_promotion(
                                    ev.split(":", 1)[1],
                                )
            except Exception:
                log.debug("ObservationFactory tick failed", exc_info=True)

        log.debug(
            "CycleRecord %s persisted (reward_rank=%s, ghost=%s, applied=%s, duration=%.1fs)",
            record.cycle_id,
            record.reward.dominance_rank if record.reward else "N/A",
            record.auto_apply_candidate,
            record.auto_applied,
            duration,
        )
