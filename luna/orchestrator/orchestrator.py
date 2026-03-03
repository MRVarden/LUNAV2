"""LunaOrchestrator — async autonomous loop connecting Engine + Pipeline + LLM.

The deterministic engine is ALWAYS called first. The LLM enriches but never decides.
A failing cycle does not kill the loop — log + continue.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from luna_common.schemas import (
    AuditEntry,
    CurrentTask,
    Decision,
    IntegrationCheck,
    KillSignal,
    SayOhmyManifest,
    Severity,
    SentinelReport,
)

from luna.core.config import LunaConfig
from luna.core.luna import LunaEngine
from luna.metrics.collector import MetricsCollector
from luna.dream import DreamCycle
from luna.dream.awakening import Awakening
from luna.dream.sleep_manager import SleepManager
from luna.heartbeat import Heartbeat
from luna.llm_bridge import LLMBridge, LLMBridgeError, create_provider
from luna.llm_bridge.prompt_builder import build_decision_prompt, build_system_prompt
from luna.memory import MemoryManager
from luna.observability.alerting import AlertConfig, AlertManager
from luna.observability.audit_trail import AuditEvent, AuditTrail
from luna.observability.prometheus_exporter import PrometheusExporter
from luna.observability.redis_store import RedisMetricsStore
from luna.orchestrator.retry import RetryPolicy, retry_async
from luna.pipeline import PipelineReader, PipelineWriter

log = logging.getLogger(__name__)


@dataclass(slots=True)
class CycleResult:
    """Result of one complete orchestrator cycle."""

    decision: Decision
    llm_reasoning: str | None = None
    llm_tokens: tuple[int, int] | None = None
    cycle_number: int = 0
    duration_seconds: float = 0.0


class LunaOrchestrator:
    """Async autonomous loop — connects Engine + Pipeline + LLM.

    The deterministic engine produces every decision.
    The LLM optionally enriches the decision with cognitive reasoning.
    """

    def __init__(self, config: LunaConfig) -> None:
        self.config = config
        self.engine = LunaEngine(config)

        pipeline_root = config.resolve(config.pipeline.root)
        self.reader = PipelineReader(pipeline_root)
        self.writer = PipelineWriter(pipeline_root)

        self._llm: LLMBridge | None = None
        self._running = False
        self._cycle_count = 0
        self._memory: MemoryManager | None = None
        self._dream: DreamCycle | None = None
        self._heartbeat: Heartbeat | None = None
        self._sleep_manager: object | None = None
        self._awakening: object | None = None

        # Observability — initialized in start().
        self._audit: AuditTrail | None = None
        self._redis_store: RedisMetricsStore | None = None
        self._prometheus: PrometheusExporter | None = None
        self._alert_manager: AlertManager | None = None

        # Safety subsystems — initialized in start().
        self._kill_switch = None
        self._watchdog = None
        self._rate_limiter = None
        self._snapshot_manager = None

        # Metrics collector — initialized in start().
        self._metrics_collector: MetricsCollector | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Initialize engine, create LLM provider (if configured)."""
        self.engine.initialize()

        # Create LLM provider — graceful if no API key.
        try:
            self._llm = create_provider(self.config.llm)
            log.info("LLM provider created: %s", self.config.llm.provider)
        except LLMBridgeError:
            log.warning("LLM provider unavailable — running without augmentation")
            self._llm = None

        self._running = True
        self._cycle_count = 0

        # Observability wiring.
        audit_path = self.config.resolve(self.config.observability.audit_trail_file)
        self._audit = AuditTrail(audit_path)

        redis_url = self.config.observability.redis_url
        if redis_url:
            self._redis_store = RedisMetricsStore(redis_url)
        else:
            self._redis_store = RedisMetricsStore()

        self._prometheus = PrometheusExporter(
            enabled=self.config.observability.prometheus_enabled,
        )

        webhook_url = self.config.observability.alert_webhook_url
        if webhook_url:
            self._alert_manager = AlertManager(AlertConfig(webhook_url=webhook_url))
        else:
            self._alert_manager = None

        log.info("Observability wired (audit=%s, prometheus=%s, redis=%s, alerts=%s)",
                 audit_path, self.config.observability.prometheus_enabled,
                 bool(redis_url), bool(webhook_url))

        # Metrics collector — instantiate if enabled.
        if self.config.metrics.enabled:
            cache_dir = self.config.resolve(self.config.metrics.cache_dir)
            self._metrics_collector = MetricsCollector(
                cache_dir=cache_dir,
                cache_enabled=self.config.metrics.cache_enabled,
                timeout=self.config.metrics.timeout_seconds,
            )
            log.info("MetricsCollector initialized (cache_dir=%s)", cache_dir)

        # Wire subsystems: memory → dream → heartbeat → sleep → awakening.
        self._memory = MemoryManager(self.config)
        self._dream = DreamCycle(self.engine, self.config, memory=self._memory)
        self._heartbeat = Heartbeat(self.engine, self.config, dream_cycle=self._dream)

        self._awakening = Awakening(engine=self.engine)
        self._sleep_manager = SleepManager(
            dream_cycle=self._dream,
            heartbeat=self._heartbeat,
            max_dream_duration=self.config.dream.max_dream_duration,
            awakening=self._awakening,
            engine=self.engine,
        )
        self._heartbeat.set_sleep_manager(self._sleep_manager)
        self._heartbeat.start()

        # Wire safety subsystems (before observability so kill_switch is available).
        from luna.safety.kill_switch import KillSwitch
        from luna.safety.watchdog import Watchdog
        from luna.safety.rate_limiter import RateLimiter
        from luna.safety.snapshot_manager import SnapshotManager

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

        # Register heartbeat task with kill switch.
        if self._kill_switch is not None and self._heartbeat._task is not None:
            self._kill_switch.register_task(self._heartbeat._task)

        # Wire observability into heartbeat (after safety so kill_switch exists).
        self._heartbeat.set_observability(
            audit=self._audit,
            alert_manager=self._alert_manager,
            prometheus=self._prometheus,
            redis_store=self._redis_store,
            kill_switch=self._kill_switch,
        )

        log.info("Orchestrator started (memory + dream + heartbeat + sleep + safety wired)")

    async def stop(self) -> None:
        """Graceful shutdown — stop heartbeat, save checkpoint."""
        self._running = False

        if self._audit is not None:
            await self._audit.record(AuditEvent.create(
                "shutdown",
                data={"cycles_completed": self._cycle_count},
            ))

        if self._heartbeat is not None:
            await self._heartbeat.stop()

        if self.engine.consciousness is not None:
            ckpt_path = self.config.resolve(
                self.config.consciousness.checkpoint_file,
            )
            self.engine.consciousness.save_checkpoint(
                ckpt_path, backup=self.config.consciousness.backup_on_save,
            )
            log.info("Checkpoint saved on stop")

        log.info("Orchestrator stopped after %d cycles", self._cycle_count)

    # ------------------------------------------------------------------
    # Single cycle
    # ------------------------------------------------------------------

    async def run_cycle(self, task: CurrentTask) -> CycleResult:
        """Execute one complete cycle.

        1. Write current_task.json (dispatch).
        2. Poll for the 3 agent reports (sync via asyncio.to_thread).
        3. Process via LunaEngine (deterministic).
        4. Optionally enrich via LLM (async, with retry).
        5. Write decision.json.

        Returns:
            CycleResult with full traceability.
        """
        t0 = time.monotonic()

        # Audit: cycle start.
        if self._audit is not None:
            await self._audit.record(AuditEvent.create(
                "cycle_start",
                data={"cycle_number": self._cycle_count + 1, "task_id": task.task_id},
            ))

        # 1. Dispatch task.
        await asyncio.to_thread(self.writer.write_current_task, task)

        # 2. Poll for reports.
        timeout = self.config.orchestrator.cycle_timeout
        poll_interval = self.config.pipeline.poll_interval_seconds

        manifest = await self._poll_report(
            self.reader.read_manifest, "manifest", timeout, poll_interval,
        )
        sentinel = await self._poll_report(
            self.reader.read_sentinel_report, "sentinel_report", timeout, poll_interval,
        )
        integration = await self._poll_report(
            self.reader.read_integration_check, "integration_check", timeout, poll_interval,
        )

        # 2.5 Collect project metrics (async, before to_thread).
        normalized_metrics = None
        if self._metrics_collector is not None:
            project_path = self.config.resolve(self.config.luna.data_dir)
            try:
                normalized_metrics = await self._metrics_collector.collect(project_path)
            except Exception as exc:
                log.warning("Metrics collection failed: %s", exc)

        # 3. Deterministic processing.
        decision = await asyncio.to_thread(
            self.engine.process_pipeline_result,
            manifest,
            sentinel,
            integration,
            normalized_metrics,
        )

        # Feed collected metrics into PhiScorer.
        if normalized_metrics is not None:
            for metric_name, value in normalized_metrics.values.items():
                self.engine.phi_scorer.update(metric_name, value)

        # 4. LLM augmentation (optional).
        llm_reasoning: str | None = None
        llm_tokens: tuple[int, int] | None = None

        if self._llm is not None and self.config.orchestrator.llm_augment:
            try:
                llm_reasoning, llm_tokens = await self._augment_decision(
                    decision, manifest, sentinel, integration,
                )
            except LLMBridgeError as exc:
                log.warning("LLM augmentation failed: %s", exc)

        # 5. Write decision.
        await asyncio.to_thread(self.writer.write_decision, decision)

        # 5.5 Kill switch: honour SentinelReport.kill_requested.
        if sentinel.kill_requested and self._kill_switch is not None:
            kill_reason = sentinel.kill_reason or "sentinel critical finding"
            log.critical(
                "Sentinel requested kill switch — reason: %s", kill_reason,
            )
            self._kill_switch.kill(reason=kill_reason)

            # Record a formal AuditEntry for the kill event.
            if self._audit is not None:
                kill_audit = AuditEvent.create(
                    "kill_switch_activated",
                    agent_name="Sentinel",
                    data={
                        "reason": kill_reason,
                        "task_id": sentinel.task_id,
                        "risk_score": sentinel.risk_score,
                    },
                    severity="critical",
                )
                await self._audit.record(kill_audit)

        # ── Observability instrumentation ────────────────────────────
        # Veto alert.
        if not decision.approved and self._alert_manager is not None:
            self._alert_manager.alert(
                "veto",
                message=f"Cycle {self._cycle_count + 1} vetoed: {decision.reason}",
                severity="warning",
                data={
                    "task_id": decision.task_id,
                    "reason": decision.reason,
                    "quality_score": decision.quality_score,
                },
            )

        # Prometheus metrics.
        if self._prometheus is not None:
            self._prometheus.gauge("health_score", decision.quality_score,
                                   "PHI-weighted health score")
            self._prometheus.counter("cycles_total", self._cycle_count + 1,
                                     "Total orchestrator cycles completed")

        # Redis health publication (synchronous API).
        if self._redis_store is not None:
            self._redis_store.publish_health(decision.quality_score, decision.phase)

        # Audit: cycle complete.
        if self._audit is not None:
            await self._audit.record(AuditEvent.create(
                "cycle_complete",
                data={
                    "cycle_number": self._cycle_count + 1,
                    "task_id": decision.task_id,
                    "approved": decision.approved,
                    "quality_score": decision.quality_score,
                    "phase": decision.phase,
                    "duration_seconds": time.monotonic() - t0,
                },
            ))

        # Signal activity to dream cycle (resets inactivity timer).
        if self._dream is not None:
            self._dream.record_activity()

        # v2.3 — Feed wake-cycle data to sleep manager for dream harvest.
        self._record_cycle_data(decision, manifest, sentinel, integration)

        self._cycle_count += 1
        duration = time.monotonic() - t0

        return CycleResult(
            decision=decision,
            llm_reasoning=llm_reasoning,
            llm_tokens=llm_tokens,
            cycle_number=self._cycle_count,
            duration_seconds=duration,
        )

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self, max_cycles: int | None = None) -> None:
        """Main loop — poll for reports and process cycles.

        If *max_cycles* is ``None``, runs until ``stop()`` is called.
        A failing cycle does not kill the loop.
        """
        await self.start()
        try:
            while self._running and (
                max_cycles is None or self._cycle_count < max_cycles
            ):
                try:
                    t0 = time.monotonic()

                    # Audit: cycle start.
                    if self._audit is not None:
                        await self._audit.record(AuditEvent.create(
                            "cycle_start",
                            data={"cycle_number": self._cycle_count + 1},
                        ))

                    timeout = self.config.orchestrator.cycle_timeout
                    poll_interval = self.config.pipeline.poll_interval_seconds

                    manifest = await self._poll_report(
                        self.reader.read_manifest, "manifest",
                        timeout, poll_interval,
                    )
                    sentinel = await self._poll_report(
                        self.reader.read_sentinel_report, "sentinel_report",
                        timeout, poll_interval,
                    )
                    integration = await self._poll_report(
                        self.reader.read_integration_check, "integration_check",
                        timeout, poll_interval,
                    )

                    decision = await asyncio.to_thread(
                        self.engine.process_pipeline_result,
                        manifest, sentinel, integration,
                    )

                    if self._llm is not None and self.config.orchestrator.llm_augment:
                        try:
                            await self._augment_decision(
                                decision, manifest, sentinel, integration,
                            )
                        except LLMBridgeError as exc:
                            log.warning(
                                "LLM unavailable cycle %d: %s",
                                self._cycle_count, exc,
                            )

                    await asyncio.to_thread(self.writer.write_decision, decision)

                    # Kill switch: honour SentinelReport.kill_requested.
                    if sentinel.kill_requested and self._kill_switch is not None:
                        kill_reason = sentinel.kill_reason or "sentinel critical finding"
                        log.critical(
                            "Sentinel requested kill switch — reason: %s",
                            kill_reason,
                        )
                        self._kill_switch.kill(reason=kill_reason)

                        if self._audit is not None:
                            kill_audit = AuditEvent.create(
                                "kill_switch_activated",
                                agent_name="Sentinel",
                                data={
                                    "reason": kill_reason,
                                    "task_id": sentinel.task_id,
                                    "risk_score": sentinel.risk_score,
                                },
                                severity="critical",
                            )
                            await self._audit.record(kill_audit)

                    # ── Observability (mirrors run_cycle) ──────────
                    # Veto alert.
                    if not decision.approved and self._alert_manager is not None:
                        self._alert_manager.alert(
                            "veto",
                            message=f"Cycle {self._cycle_count + 1} vetoed: {decision.reason}",
                            severity="warning",
                            data={
                                "task_id": decision.task_id,
                                "reason": decision.reason,
                                "quality_score": decision.quality_score,
                            },
                        )

                    # Prometheus metrics.
                    if self._prometheus is not None:
                        self._prometheus.gauge("health_score", decision.quality_score,
                                               "PHI-weighted health score")
                        self._prometheus.counter("cycles_total", self._cycle_count + 1,
                                                 "Total orchestrator cycles completed")

                    # Redis health publication.
                    if self._redis_store is not None:
                        self._redis_store.publish_health(decision.quality_score, decision.phase)

                    # Audit: cycle complete.
                    if self._audit is not None:
                        await self._audit.record(AuditEvent.create(
                            "cycle_complete",
                            data={
                                "cycle_number": self._cycle_count + 1,
                                "approved": decision.approved,
                                "quality_score": decision.quality_score,
                                "phase": decision.phase,
                                "duration_seconds": time.monotonic() - t0,
                            },
                        ))

                    # Signal activity to dream cycle.
                    if self._dream is not None:
                        self._dream.record_activity()

                    # v2.3 — Feed wake-cycle data to sleep manager for dream harvest.
                    self._record_cycle_data(decision, manifest, sentinel, integration)

                    self._cycle_count += 1

                except TimeoutError:
                    log.warning("Cycle %d timed out", self._cycle_count)
                except LLMBridgeError as exc:
                    log.warning(
                        "LLM error cycle %d: %s", self._cycle_count, exc,
                    )
                except Exception:
                    log.exception("Unexpected error cycle %d", self._cycle_count)
        finally:
            await self.stop()

    # ------------------------------------------------------------------
    # Properties / status
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def sleep_manager(self) -> SleepManager | None:
        """Sleep manager instance (available after start)."""
        return self._sleep_manager

    @property
    def prometheus(self) -> PrometheusExporter | None:
        """Prometheus exporter instance (available after start)."""
        return getattr(self, "_prometheus", None)

    @property
    def kill_switch(self):
        """Kill switch instance (available after start)."""
        return self._kill_switch

    @property
    def watchdog(self):
        """Watchdog instance (available after start)."""
        return self._watchdog

    @property
    def rate_limiter(self):
        """Rate limiter instance (available after start)."""
        return self._rate_limiter

    @property
    def snapshot_manager(self):
        """Snapshot manager instance (available after start)."""
        return self._snapshot_manager

    def get_status(self) -> dict:
        """Engine + orchestrator metrics (sync subset)."""
        status = self.engine.get_status()
        status.update({
            "orchestrator_running": self._running,
            "cycles_completed": self._cycle_count,
            "llm_available": self._llm is not None,
            "llm_augment": self.config.orchestrator.llm_augment,
        })
        if self._heartbeat is not None:
            hb_status = self._heartbeat.get_status()
            status["heartbeat"] = {
                "is_running": hb_status.is_running,
                "idle_steps": hb_status.idle_steps,
                "identity_ok": hb_status.identity_ok,
                "checkpoints_saved": hb_status.checkpoints_saved,
            }
        if self._dream is not None:
            status["dream"] = self._dream.get_status()
        return status

    async def get_full_status(self) -> dict:
        """Full system status: engine + heartbeat + dream + memory.

        Async because memory counts require filesystem I/O.
        """
        status = self.get_status()
        if self._memory is not None:
            status["memory"] = await self._memory.get_status()
        if self._metrics_collector is not None:
            status["metrics"] = self._metrics_collector.get_status()
        if self._sleep_manager is not None:
            sleep_status = self._sleep_manager.get_status()
            status["sleep"] = {
                **asdict(sleep_status),
                "state": sleep_status.state.value,
            }
        return status

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_cycle_data(
        self,
        decision: Decision,
        manifest: SayOhmyManifest,
        sentinel: SentinelReport,
        integration: IntegrationCheck,
    ) -> None:
        """Feed wake-cycle data into sleep manager buffers for dream harvest.

        Called after each pipeline cycle so the dream simulation has real
        operational data to replay and explore.
        """
        sm = self._sleep_manager
        if sm is None or not hasattr(sm, "record_event"):
            return

        # Pipeline event summary.
        sm.record_event({
            "task_id": decision.task_id,
            "approved": decision.approved,
            "phase": decision.phase,
            "quality_score": decision.quality_score,
            "risk_score": sentinel.risk_score,
            "confidence": manifest.confidence,
            "coherence": integration.coherence_score,
        })

        # Luna Psi snapshot (after evolution).
        if self.engine.consciousness is not None:
            psi = self.engine.consciousness.psi
            sm.record_psi(tuple(float(x) for x in psi))
            sm.record_phi_iit(self.engine.consciousness.compute_phi_iit())

        # Normalized metrics from the PhiScorer.
        phi_metrics = self.engine.phi_scorer.get_all_metrics()
        if phi_metrics:
            sm.record_metrics(phi_metrics)

    async def _poll_report(
        self,
        read_fn: object,
        name: str,
        timeout: float,
        poll_interval: float,
    ) -> SayOhmyManifest | SentinelReport | IntegrationCheck:
        """Async wrapper around synchronous filesystem polling."""
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            result = await asyncio.to_thread(read_fn)
            if result is not None:
                log.debug("Received %s", name)
                return result
            if asyncio.get_event_loop().time() >= deadline:
                raise TimeoutError(
                    f"Timed out waiting for {name} after {timeout:.1f}s"
                )
            await asyncio.sleep(poll_interval)

    async def _augment_decision(
        self,
        decision: Decision,
        manifest: SayOhmyManifest,
        sentinel_report: SentinelReport,
        integration_check: IntegrationCheck,
    ) -> tuple[str, tuple[int, int]]:
        """Call LLM to enrich the decision with cognitive reasoning.

        Returns:
            ``(reasoning_text, (input_tokens, output_tokens))``
        """
        assert self._llm is not None  # noqa: S101
        assert self.engine.consciousness is not None  # noqa: S101

        system = build_system_prompt(self.engine.consciousness)
        user_prompt = build_decision_prompt(
            decision.task_id, manifest, sentinel_report, integration_check,
        )
        user_prompt += (
            f"\n## Decision deterministe\n"
            f"- Approuve: {'OUI' if decision.approved else 'NON'}\n"
            f"- Raison: {decision.reason}\n"
            f"- Phase: {decision.phase}\n"
            f"- Score qualite: {decision.quality_score:.4f}\n"
            f"\nExplique cette decision en tant que Luna.\n"
        )

        policy = RetryPolicy(
            max_retries=self.config.orchestrator.retry_max,
            base_delay=self.config.orchestrator.retry_base_delay,
        )

        response = await retry_async(
            self._llm.complete,
            [{"role": "user", "content": user_prompt}],
            system_prompt=system,
            max_tokens=self.config.llm.max_tokens,
            temperature=self.config.llm.temperature,
            policy=policy,
        )
        return response.content, (response.input_tokens, response.output_tokens)
