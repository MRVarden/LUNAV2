"""ChatSession — human-facing conversation interface for Luna.

Parallel to the agent-to-agent orchestrator. Wires LunaEngine + LLMBridge +
MemoryManager directly without passing through the pipeline circuit.
Each chat turn evolves consciousness with real info_deltas.

v2.4.0: Self-Evolution Loop — chat detects pipeline intent, triggers real
agent pipeline, and feeds measured metrics back into PhiScorer.
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


from luna_common.constants import INV_PHI, METRIC_NAMES
from luna_common.consciousness import get_psi0

from luna.core.config import LunaConfig
from luna.core.luna import LunaEngine
from luna.llm_bridge.bridge import LLMBridge, LLMBridgeError, LLMResponse
from luna.llm_bridge.prompt_builder import build_system_prompt
from luna.llm_bridge.providers import create_provider
from luna.memory.memory_manager import MemoryEntry, MemoryManager
from luna.metrics.tracker import MetricSource, MetricTracker
from luna.orchestrator.retry import RetryPolicy, retry_async
from luna.pipeline.detector import TaskDetector
from luna.pipeline.needs import NeedIdentifier
from luna.pipeline.runner import PipelineRunner
from luna.pipeline.task import PipelineResult, TaskStatus

log = logging.getLogger(__name__)

# Stopwords for keyword extraction (FR + EN basics).
_STOPWORDS: frozenset[str] = frozenset({
    "le", "la", "les", "un", "une", "des", "de", "du", "au", "aux",
    "et", "ou", "mais", "donc", "car", "ni", "que", "qui", "quoi",
    "je", "tu", "il", "elle", "nous", "vous", "ils", "elles", "on",
    "ce", "cette", "ces", "mon", "ma", "mes", "ton", "ta", "tes",
    "son", "sa", "ses", "est", "sont", "suis", "es", "a", "ai",
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "can", "could", "should", "may", "might", "shall",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
    "my", "your", "his", "its", "our", "their",
    "in", "on", "at", "to", "for", "with", "from", "by", "of",
    "not", "no", "yes", "oui", "non", "pas", "ne", "se",
    "dans", "sur", "pour", "avec", "par", "en",
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


# Slash commands recognized by the chat session.
_COMMANDS = frozenset({"/status", "/dream", "/memories", "/needs", "/help", "/quit"})

_HELP_TEXT = (
    "Commandes disponibles:\n"
    "  /status       — Etat actuel de la conscience\n"
    "  /dream        — Declencher un cycle de reve\n"
    "  /memories [N] — Afficher les N memoires recentes (defaut: 10)\n"
    "  /needs        — Identifier les besoins d'amelioration\n"
    "  /help         — Cette aide\n"
    "  /quit         — Quitter"
)


class ChatSession:
    """Human-facing chat session wiring Engine + LLM + Memory.

    Graceful degradation:
    - Without LLM: returns status-only responses.
    - Without memory: chat without historical context.
    - LLM error mid-turn: fallback to status.
    """

    def __init__(self, config: LunaConfig) -> None:
        self._config = config
        self._engine = LunaEngine(config)
        self._llm: LLMBridge | None = None
        self._memory: MemoryManager | None = None
        self._history: list[ChatMessage] = []
        self._started = False
        self._turn_count: int = 0
        # v2.4.0 — Self-Evolution Loop
        self._task_detector = TaskDetector()
        self._need_identifier = NeedIdentifier()
        self._metric_tracker = MetricTracker()
        self._pipeline_runner: PipelineRunner | None = None
        # v2.4.0 — Wake-cycle buffers for dream harvest.
        self._psi_snapshots: list[tuple[float, ...]] = []
        self._phi_iit_history: list[float] = []
        self._pipeline_events: list[dict] = []
        # v2.4.1 — Inactivity-triggered dream.
        self._last_activity: float = time.monotonic()
        self._inactivity_task: asyncio.Task | None = None

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

    @property
    def has_pipeline(self) -> bool:
        return self._pipeline_runner is not None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Initialize engine, LLM, and memory. Tolerates missing LLM/memory."""
        self._engine.initialize()

        # Restore or bootstrap PhiScorer metrics.
        if self._engine.phi_metrics_restored:
            log.info(
                "PhiScorer restored from checkpoint (score=%.4f) — "
                "no bootstrap needed",
                self._engine.phi_scorer.score(),
            )
        else:
            # BOOTSTRAP SEED — not earned metrics.
            # Prevents health phase from starting at BROKEN before any real
            # measurement. Will be overwritten by actual data from chat_evolve().
            log.warning(
                "Seeding PhiScorer with bootstrap values (%.3f) — "
                "not earned, will be replaced by real interaction data",
                INV_PHI,
            )
            for metric_name in METRIC_NAMES:
                self._engine.phi_scorer.update(metric_name, INV_PHI)

        # Seed MetricTracker with source info.
        if self._engine.phi_metrics_restored:
            # Mark all restored metrics as their persisted source.
            snapshot = getattr(self._engine.consciousness, "phi_metrics_snapshot", None)
            if snapshot:
                for name, entry in snapshot.items():
                    if name not in METRIC_NAMES:
                        log.warning("Ignoring unknown metric in checkpoint: %s", name)
                        continue
                    value = entry.get("value", INV_PHI)
                    source_str = entry.get("source", "bootstrap")
                    # S07-010: compare against value->member map, not objects.
                    source = (
                        MetricSource(source_str)
                        if source_str in MetricSource._value2member_map_
                        else MetricSource.BOOTSTRAP
                    )
                    self._metric_tracker.record(name, value, source)
        else:
            for metric_name in METRIC_NAMES:
                self._metric_tracker.record(
                    metric_name, INV_PHI, MetricSource.BOOTSTRAP,
                )

        # LLM — optional, degrades gracefully.
        self._init_llm()

        # Memory — optional.
        try:
            self._memory = MemoryManager(self._config)
            log.info("Memory manager initialized: %s", self._memory.root)
        except Exception:
            log.warning(
                "Memory unavailable — chat without historical context",
                exc_info=True,
            )
            self._memory = None

        # v2.4.0 — Pipeline runner (if enabled).
        self._init_pipeline_runner()

        # Gap 3 — Restore chat history from disk.
        self._load_history()

        self._started = True

        # v2.4.1 — Background inactivity watcher for automatic dream.
        if self._config.dream.enabled:
            self._last_activity = time.monotonic()
            self._inactivity_task = asyncio.create_task(self._watch_inactivity())
            log.info(
                "Inactivity watcher started (threshold=%.0fs)",
                self._config.dream.inactivity_threshold,
            )

        # v2.4.1 — Force checkpoint upgrade on first start if version mismatch.
        self._maybe_upgrade_checkpoint()

    def _maybe_upgrade_checkpoint(self) -> None:
        """Force-save checkpoint if on-disk version is outdated.

        Ensures the checkpoint file is upgraded from v2.2.0 to v2.4.0+
        format with phi_metrics included. This is a one-time migration.
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
            on_disk_version = data.get("version", "2.0.0")
            has_phi_metrics = "phi_metrics" in data
            if on_disk_version < "2.4" or not has_phi_metrics:
                log.info(
                    "Checkpoint upgrade: v%s -> v2.4.0 (adding phi_metrics)",
                    on_disk_version,
                )
                self._save_checkpoint()
        except Exception:
            log.warning("Checkpoint upgrade check failed", exc_info=True)

    def _init_llm(self) -> None:
        """Attempt to create the LLM provider. Sets self._llm or None."""
        try:
            self._llm = create_provider(self._config.llm)
            log.info(
                "LLM bridge initialized: %s/%s",
                self._config.llm.provider,
                self._config.llm.model,
            )
        except Exception as exc:
            log.warning(
                "LLM unavailable (%s/%s): %s — chat will return status-only responses",
                self._config.llm.provider,
                self._config.llm.model,
                exc,
            )
            self._llm = None

    def _init_pipeline_runner(self) -> None:
        """Initialize the pipeline runner if enabled in config."""
        if not self._config.pipeline.runner_enabled:
            log.info("Pipeline runner disabled (runner_enabled=false)")
            return
        try:
            pipeline_root = self._config.resolve(self._config.pipeline.root)
            pipeline_root.mkdir(parents=True, exist_ok=True)
            # Build env extras from config: if luna.toml has an explicit
            # api_key, inject it as {PROVIDER}_API_KEY for agent subprocesses.
            env_extras: dict[str, str] = {}
            if self._config.llm.api_key:
                provider = self._config.llm.provider.upper()
                env_key = f"{provider}_API_KEY"
                env_extras[env_key] = self._config.llm.api_key

            self._pipeline_runner = PipelineRunner(
                pipeline_root=pipeline_root,
                sayohmy_cwd=Path(self._config.pipeline.sayohmy_path).expanduser(),
                sentinel_cwd=Path(self._config.pipeline.sentinel_path).expanduser(),
                testengineer_cwd=Path(self._config.pipeline.testengineer_path).expanduser(),
                agent_timeout=self._config.pipeline.agent_timeout,
                project_root=self._config.resolve(Path(".")),
                env_extras=env_extras or None,
            )
            log.info(
                "Pipeline runner initialized (autonomy=%s, root=%s)",
                self._config.pipeline.autonomy,
                pipeline_root,
            )
        except Exception as exc:
            log.warning(
                "Pipeline runner initialization failed: %s", exc, exc_info=True,
            )
            self._pipeline_runner = None

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

    def _save_history(self) -> None:
        """Persist chat history to disk (atomic write)."""
        if not self._history:
            return
        path = self._history_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        max_h = self._config.chat.max_history
        entries = [
            {
                "role": msg.role,
                "content": msg.content,
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
        """Save consciousness checkpoint + chat history (called on stop and periodically)."""
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
        log.info(
            "Checkpoint saved (bootstrap_ratio=%.2f)",
            self._metric_tracker.bootstrap_ratio(),
        )

    def _build_dream_harvest(self) -> DreamHarvest | None:
        """Build a DreamHarvest from wake-cycle buffers accumulated during chat.

        Returns None if there is insufficient data for a meaningful dream.
        """
        from luna.dream.harvest import DreamHarvest
        from luna_common.constants import AGENT_PROFILES

        if not self._psi_snapshots and not self._pipeline_events:
            return None

        # Collect current profiles: defaults + live Luna Ψ₀.
        current_profiles: dict[str, tuple[float, ...]] = dict(AGENT_PROFILES)
        cs = self._engine.consciousness
        if cs is not None:
            current_profiles[cs.agent_name] = tuple(
                float(x) for x in cs.psi0
            )

        # Build metrics history from tracker.
        metrics_history: list[dict[str, float]] = []
        tracker_snap = self._metric_tracker.snapshot_sources()
        if tracker_snap:
            entry_dict: dict[str, float] = {}
            for name in METRIC_NAMES:
                entry = self._metric_tracker.get(name)
                if entry is not None:
                    entry_dict[name] = entry.value
            if entry_dict:
                metrics_history.append(entry_dict)

        harvest = DreamHarvest(
            pipeline_events=tuple(self._pipeline_events),
            luna_psi_snapshots=tuple(self._psi_snapshots),
            metrics_history=tuple(metrics_history),
            phi_iit_history=tuple(self._phi_iit_history),
            current_profiles=current_profiles,
        )

        # Clear buffers after harvest (consumed by dream).
        self._psi_snapshots.clear()
        self._phi_iit_history.clear()
        self._pipeline_events.clear()

        return harvest

    async def stop(self) -> None:
        """Save consciousness checkpoint with PhiScorer metrics on exit."""
        # Cancel inactivity watcher.
        if self._inactivity_task is not None:
            self._inactivity_task.cancel()
            try:
                await self._inactivity_task
            except asyncio.CancelledError:
                pass
            self._inactivity_task = None
        self._save_checkpoint()
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
                from luna.dream.dream_cycle import DreamCycle

                dream = DreamCycle(self._engine, self._config, self._memory)
                harvest = self._build_dream_harvest()
                report = await dream.run(harvest=harvest)

                log.info(
                    "Inactivity dream completed: %.2fs, history %d -> %d",
                    report.total_duration,
                    report.history_before,
                    report.history_after,
                )

                # Save checkpoint after dream.
                self._save_checkpoint()

            except Exception:
                log.warning("Inactivity dream failed", exc_info=True)

            # Reset timer so we don't trigger again immediately.
            self._last_activity = time.monotonic()

    # ------------------------------------------------------------------
    # Main chat turn
    # ------------------------------------------------------------------

    async def send(self, user_input: str) -> ChatResponse:
        """Process one user message and return Luna's response.

        Flow:
        1. idle_step() — κ·(Ψ₀ − Ψ) heartbeat, the breath
        2. memory.search(keywords) — relevant context
        3. detect_task() — check for pipeline intent
        4. if pipeline intent + runner: run pipeline, LLM interprets result
           else: normal LLM conversation
        5. chat_evolve() — real info_deltas from this turn
        6. memory.write_memory(seed) — persist conversation
        7. Return ChatResponse
        """
        if not self._started:
            raise RuntimeError("ChatSession.start() must be called first")

        # Reset inactivity timer on every user message.
        self._last_activity = time.monotonic()

        cs = self._engine.consciousness
        assert cs is not None  # noqa: S101  — guaranteed by start()

        # 1. Idle heartbeat — κ·(Ψ₀ − Ψ) pulls toward identity each turn.
        if self._config.chat.idle_heartbeat:
            self._engine.idle_step()

        # Record user message.
        user_msg = ChatMessage(role="user", content=user_input)
        self._history.append(user_msg)

        # 2. Memory search — inject relevant context.
        memory_context = ""
        memory_found = False
        if self._memory is not None:
            keywords = _extract_keywords(user_input)
            if keywords:
                try:
                    memories = await self._memory.search(
                        keywords, limit=self._config.chat.memory_search_limit,
                    )
                    if memories:
                        memory_found = True
                        memory_lines = [f"- {m.content}" for m in memories]
                        memory_context = (
                            "\n\n## Memoires pertinentes\n" + "\n".join(memory_lines)
                        )
                except Exception:
                    log.warning("Memory search failed", exc_info=True)

        # 3. Detect pipeline task intent.
        pipeline_result: PipelineResult | None = None
        intent = self._task_detector.detect(user_input)

        if intent is not None and self._pipeline_runner is not None:
            # Pipeline detected — run the self-evolution cycle.
            pipeline_result = await self._run_pipeline(intent)

        # 4. LLM call (or fallback).
        # Lazy LLM init retry — if LLM failed at start, try once more.
        if self._llm is None:
            self._init_llm()

        llm_success = False
        if self._llm is not None:
            system = build_system_prompt(cs) + memory_context
            if pipeline_result is not None:
                # Inject pipeline result into LLM context.
                system += self._format_pipeline_context(pipeline_result)
            messages = [
                {"role": m.role, "content": m.content}
                for m in self._history
            ]
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
            except LLMBridgeError:
                log.warning("LLM call failed — fallback", exc_info=True)
                if pipeline_result is not None:
                    content = self._format_pipeline_response(pipeline_result)
                else:
                    content = self._format_status_response(
                        cs.get_phase(), cs.compute_phi_iit(), llm_error=True,
                    )
                in_tok, out_tok = 0, 0
        else:
            # No LLM available — but if a pipeline ran, show its result
            # instead of the generic status-only fallback.
            if pipeline_result is not None:
                content = self._format_pipeline_response(pipeline_result)
            else:
                content = self._format_status_response(
                    cs.get_phase(), cs.compute_phi_iit(), llm_error=False,
                )
            in_tok, out_tok = 0, 0

        # 5. Evolve consciousness with real info_deltas from this turn.
        self._chat_evolve(
            memory_found=memory_found,
            llm_success=llm_success,
            pipeline_result=pipeline_result,
            msg_length=len(user_input),
            out_tokens=out_tok,
        )

        # Capture phase/phi AFTER evolution for accurate metadata.
        phase = cs.get_phase()
        phi_iit = cs.compute_phi_iit()

        # Record assistant message.
        assistant_msg = ChatMessage(role="assistant", content=content)
        self._history.append(assistant_msg)

        # Trim history to max_history (after both user + assistant appended).
        max_h = self._config.chat.max_history
        if len(self._history) > max_h:
            self._history = self._history[-max_h:]

        # 6. Persist conversation turn as seed memory.
        if self._memory is not None and self._config.chat.save_conversations:
            await self._persist_turn(user_input, content)

        # 7. Periodic checkpoint — save every checkpoint_interval turns.
        self._turn_count += 1
        interval = self._config.heartbeat.checkpoint_interval
        if interval > 0 and self._turn_count % interval == 0:
            self._save_checkpoint()

        return ChatResponse(
            content=content,
            input_tokens=in_tok,
            output_tokens=out_tok,
            phase=phase,
            phi_iit=phi_iit,
        )

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
            status = self._engine.get_status()
            lines = [f"  {k}: {v}" for k, v in status.items()]
            return "## Etat Luna\n" + "\n".join(lines)

        if command == "/dream":
            from luna.dream.dream_cycle import DreamCycle

            # Guard: refuse if insufficient data for any meaningful dream.
            cs = self._engine.consciousness
            has_buffers = bool(self._psi_snapshots or self._pipeline_events)
            has_history = cs is not None and len(cs.history) >= 10
            if not has_buffers and not has_history:
                return (
                    "Pas assez de donnees pour rever.\n"
                    "Interagis d'abord avec Luna (quelques messages suffisent)."
                )

            dream = DreamCycle(self._engine, self._config, self._memory)
            harvest = self._build_dream_harvest()
            report = await dream.run(harvest=harvest)

            if harvest is not None:
                # Real simulation ran.
                cr = report.consolidation_report
                profiles_info = ""
                if cr is not None:
                    drift_str = ", ".join(
                        f"{a}: {d:.4f}" for a, d in cr.drift_per_agent.items()
                    )
                    profiles_info = (
                        f"\nProfils mis a jour: {cr.dominant_preserved}"
                        f"\nDrift: {drift_str}"
                    )
                phases_str = " -> ".join(p.phase.value for p in report.phases)
                return (
                    f"## Cycle de reve (simulation)\n"
                    f"Duree: {report.total_duration:.2f}s\n"
                    f"Phases: {phases_str}\n"
                    f"History: {report.history_before} -> {report.history_after}"
                    f"{profiles_info}"
                )
            else:
                return (
                    f"Cycle de reve (legacy): {report.total_duration:.2f}s, "
                    f"history {report.history_before} -> {report.history_after}"
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

        if command == "/needs":
            needs = self._need_identifier.identify(self._metric_tracker)
            if not needs:
                return "Aucun besoin identifie — toutes les metriques sont saines."
            return self._need_identifier.propose_to_human(needs)

        return f"Commande inconnue: {command}. Tapez /help pour la liste."

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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

    @staticmethod
    def _format_pipeline_response(result: PipelineResult) -> str:
        """Format pipeline result as a direct user-facing response.

        Used when LLM is unavailable — presents the raw pipeline outcome
        so the user sees real results instead of a generic status fallback.
        """
        status_label = {
            TaskStatus.COMPLETED: "Termine",
            TaskStatus.FAILED: "Echec",
            TaskStatus.VETOED: "Veto SENTINEL",
        }.get(result.status, result.status.value)

        lines = [
            f"## Pipeline {status_label}",
            f"Tache: {result.task_id}",
            f"Duree: {result.duration_seconds:.1f}s",
        ]
        if result.reason:
            lines.append(f"Raison: {result.reason}")
        for step in result.steps:
            icon = "+" if step.success else "x"
            lines.append(
                f"  [{icon}] {step.agent}: {step.duration_seconds:.1f}s"
            )
            if not step.success and step.stderr:
                lines.append(f"      {step.stderr[:120]}")
        if result.metrics:
            lines.append("Metriques:")
            for name, value in result.metrics.items():
                lines.append(f"  - {name}: {value:.3f}")
        return "\n".join(lines)

    @staticmethod
    def _format_pipeline_context(result: PipelineResult) -> str:
        """Format pipeline result as context for the LLM system prompt."""
        lines = [
            "\n\n## Resultat pipeline",
            f"Status: {result.status.value}",
            f"Raison: {result.reason}",
        ]
        if result.metrics:
            lines.append("Metriques mesurees:")
            for name, value in result.metrics.items():
                lines.append(f"  - {name}: {value:.3f}")
        for step in result.steps:
            status = "OK" if step.success else "ECHEC"
            lines.append(f"  {step.agent}: {status} ({step.duration_seconds:.1f}s)")
        return "\n".join(lines)

    async def _run_pipeline(self, intent) -> PipelineResult:
        """Execute the pipeline for a detected intent.

        Autonomy enforcement (S07-008):
        - supervised/semi_autonomous: pipeline runs, user reviews result.
        - autonomous: not yet implemented, raises NotImplementedError.
        """
        from luna.pipeline.task import PipelineTask

        assert self._pipeline_runner is not None  # noqa: S101

        # S07-008: Enforce autonomy level.
        autonomy = self._config.pipeline.autonomy
        if autonomy not in ("supervised", "semi_autonomous"):
            raise NotImplementedError(
                f"Autonomy level '{autonomy}' is not yet implemented. "
                "Use 'supervised' or 'semi_autonomous'."
            )

        task = PipelineTask.from_intent(intent, source="chat")
        log.info(
            "Pipeline triggered [%s]: type=%s confidence=%.2f desc='%s'",
            autonomy,
            intent.task_type.value,
            intent.confidence,
            intent.description[:80],
        )

        result = await self._pipeline_runner.run(task)

        log.info(
            "Pipeline completed: task=%s status=%s duration=%.1fs metrics=%s",
            result.task_id,
            result.status.value,
            result.duration_seconds,
            list(result.metrics.keys()) if result.metrics else "none",
        )

        # Feed measured metrics into PhiScorer + MetricTracker.
        if result.status == TaskStatus.COMPLETED and result.metrics:
            for name, value in result.metrics.items():
                self._engine.phi_scorer.update(name, value)
                self._metric_tracker.record(
                    name, value, MetricSource.MEASURED, pipeline_id=result.task_id,
                )
            log.info(
                "Pipeline metrics fed: %d measured (bootstrap_ratio=%.2f)",
                len(result.metrics),
                self._metric_tracker.bootstrap_ratio(),
            )

        # Record pipeline event for dream harvest.
        self._pipeline_events.append({
            "task_id": result.task_id,
            "status": result.status.value,
            "metrics": result.metrics or {},
            "duration": result.duration_seconds,
        })

        return result

    def _chat_evolve(
        self,
        *,
        memory_found: bool,
        llm_success: bool,
        pipeline_result: PipelineResult | None = None,
        msg_length: int = 0,
        out_tokens: int = 0,
    ) -> None:
        """Evolve consciousness with real info_deltas from the chat turn.

        Feeds the PhiScorer with interaction metrics and runs one evolution
        step with meaningful deltas via ContextBuilder.

        Per-turn signals injected (v2.4.1 — Phase 4C):
          - msg_length → memory_health modulation (longer = richer context)
          - out_tokens → output_quality modulation (more tokens = richer response)
          - time since last message → phi_iit modulation (reflection time)
        """
        cs = self._engine.consciousness
        if cs is None:
            return

        scorer = self._engine.phi_scorer

        # Per-turn variation signals (normalized to [0, 1]).
        msg_signal = min(1.0, msg_length / 500.0)  # 500 chars = saturated
        token_signal = min(1.0, out_tokens / 200.0)  # 200 tokens = saturated

        has_result = (
            pipeline_result is not None
            and pipeline_result.status == TaskStatus.COMPLETED
        )
        if has_result:
            # Pipeline ran — metrics already fed in _run_pipeline().
            output_quality = 1.0
            memory_health = 0.9
        else:
            # Normal chat turn — feed PhiScorer AND MetricTracker.
            sec_val = 1.0  # no code execution risk in chat
            perf_val = 1.0 if llm_success else 0.382
            scorer.update("security_integrity", sec_val)
            scorer.update("performance_score", perf_val)
            self._metric_tracker.record(
                "security_integrity", sec_val, MetricSource.MEASURED,
            )
            self._metric_tracker.record(
                "performance_score", perf_val, MetricSource.MEASURED,
            )
            # Modulate output quality with token richness.
            output_quality = perf_val * (0.7 + 0.3 * token_signal)
            # Modulate memory health with message depth.
            base_mem = 0.8 if memory_found else 0.5
            memory_health = base_mem * (0.7 + 0.3 * msg_signal)

        # Compute info_deltas via ContextBuilder (true deltas).
        quality = scorer.score()
        phi_iit_val = cs.compute_phi_iit()

        info_grad = self._engine.context_builder.build(
            memory_health=memory_health,
            phi_quality=quality,
            phi_iit=phi_iit_val,
            output_quality=output_quality,
        )

        # Gather other agents' Psi0 profiles for coupling.
        psi_others = self._engine._cached_psi_others
        if psi_others is None:
            psi_others = [
                get_psi0("SAYOHMY"),
                get_psi0("SENTINEL"),
                get_psi0("TESTENGINEER"),
            ]

        cs.evolve(psi_others, info_deltas=info_grad.as_list())

        # Record wake-cycle data for dream harvest.
        self._psi_snapshots.append(tuple(float(x) for x in cs.psi))
        self._phi_iit_history.append(cs.compute_phi_iit())

    async def _persist_turn(self, user_input: str, response: str) -> None:
        """Persist a conversation turn as a seed memory."""
        assert self._memory is not None  # noqa: S101
        entry = MemoryEntry(
            id=f"chat_{uuid.uuid4().hex[:12]}",
            content=f"User: {user_input}\nLuna: {response[:200]}",
            memory_type="seed",
            keywords=_extract_keywords(user_input + " " + response),
        )
        try:
            await self._memory.write_memory(entry, "seeds")
        except Exception:
            log.warning("Failed to persist chat turn", exc_info=True)
