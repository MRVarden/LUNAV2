"""Heartbeat — background async pulse that keeps the cognitive loop alive.

ORCHESTRATOR-ONLY: This async loop runs in the standalone orchestrator
mode (luna start). In chat mode (session.py), idle_step, checkpoint,
dream trigger, and emergency stop are handled directly by ChatSession.send().

Runs idle_step() at regular intervals, performs identity fingerprint checks,
saves periodic checkpoints, and triggers dream cycles when inactive.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import numpy as np

from luna.core.config import LunaConfig
from luna.heartbeat.monitor import HeartbeatMonitor
from luna.heartbeat.rhythm import AdaptiveRhythm
from luna.heartbeat.vitals import measure_vitals
from luna_common.constants import INV_PHI3
from luna.observability.audit_trail import AuditEvent

log = logging.getLogger(__name__)


@dataclass(slots=True)
class HeartbeatStatus:
    """Snapshot of current heartbeat state."""

    is_running: bool = False
    idle_steps: int = 0
    identity_ok: bool = True
    last_beat: datetime | None = None
    checkpoints_saved: int = 0


class Heartbeat:
    """Background pulse — idle evolution, fingerprint, checkpoint, dream trigger."""

    def __init__(
        self,
        engine: object,
        config: LunaConfig,
        dream_cycle: object | None = None,
        rhythm: AdaptiveRhythm | None = None,
        monitor: HeartbeatMonitor | None = None,
    ) -> None:
        self._engine = engine
        self._config = config
        self._dream_cycle = dream_cycle
        self._rhythm = rhythm or AdaptiveRhythm(
            base_seconds=config.heartbeat.interval_seconds,
        )
        self._monitor = monitor or HeartbeatMonitor()
        self._sleep_manager: object | None = None
        self._task: asyncio.Task | None = None
        self._identity_ok: bool = True
        self._last_beat: datetime | None = None
        self._checkpoints_saved: int = 0
        self._start_time: float = time.monotonic()
        self._last_vitals: dict | None = None

        # Observability — set via set_observability() to avoid circular init.
        self._audit: object | None = None
        self._alert_manager: object | None = None
        self._prometheus: object | None = None
        self._redis_store: object | None = None
        self._kill_switch: object | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> asyncio.Task:
        """Create and return the background heartbeat task."""
        if self._task is not None and not self._task.done():
            return self._task
        self._task = asyncio.create_task(self._run(), name="heartbeat")
        log.info("Heartbeat started")
        return self._task

    async def stop(self) -> None:
        """Cancel the background task and wait for cleanup."""
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        log.info("Heartbeat stopped")

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def set_sleep_manager(self, sleep_manager: object) -> None:
        """Set the sleep manager (avoids circular init)."""
        self._sleep_manager = sleep_manager

    def set_observability(
        self,
        audit: object | None = None,
        alert_manager: object | None = None,
        prometheus: object | None = None,
        redis_store: object | None = None,
        kill_switch: object | None = None,
    ) -> None:
        """Set observability references (avoids circular init)."""
        self._audit = audit
        self._alert_manager = alert_manager
        self._prometheus = prometheus
        self._redis_store = redis_store
        self._kill_switch = kill_switch

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def _run(self) -> None:
        """Main heartbeat loop — runs until cancelled."""
        ckpt_interval = self._config.heartbeat.checkpoint_interval

        try:
            while True:
                # 1. Idle step — skip if engine not yet initialized.
                try:
                    self._engine.idle_step()
                except RuntimeError:
                    interval = self._rhythm.current_interval("BROKEN")
                    await asyncio.sleep(interval)
                    continue
                self._last_beat = datetime.now(timezone.utc)

                # 1b. Check emergency stop (inter-process signal from CLI).
                if self._kill_switch is not None:
                    data_dir = self._config.resolve(self._config.luna.data_dir)
                    sentinel_reason = self._kill_switch.check_sentinel(data_dir)
                    if sentinel_reason is not None:
                        log.critical("Emergency stop detected: %s", sentinel_reason)
                        self._kill_switch.kill(reason=f"emergency_stop: {sentinel_reason}")
                        if self._audit is not None:
                            await self._audit.record(AuditEvent.create(
                                "emergency_stop",
                                data={"reason": sentinel_reason},
                            ))
                        break

                # 2. Measure vitals.
                uptime = time.monotonic() - self._start_time
                memory_count = 0  # placeholder until memory manager is wired
                vitals = measure_vitals(self._engine, uptime, memory_count)
                self._last_vitals = asdict(vitals)

                # 2b. Feed prometheus from vitals.
                if self._prometheus is not None:
                    self._prometheus.update_from_vitals(self._last_vitals)

                # 2c. Publish vitals to redis.
                if self._redis_store is not None:
                    overall_vitality = self._last_vitals.get("overall_vitality", 0.0)
                    self._redis_store.publish_health(overall_vitality, "heartbeat")

                # 3. Monitor for anomalies.
                alerts = self._monitor.check(vitals)
                if alerts:
                    for alert in alerts:
                        log.warning(
                            "Heartbeat anomaly: %s (severity=%s)",
                            alert.details,
                            alert.severity,
                        )
                    self._rhythm.set_anomaly(True)

                    # 3b. Record anomalies to audit trail.
                    if self._audit is not None:
                        for alert in alerts:
                            await self._audit.record(AuditEvent.create(
                                "heartbeat_anomaly",
                                data={"severity": alert.severity, "details": alert.details},
                            ))

                    # 3c. Alert on anomalies.
                    if self._alert_manager is not None:
                        self._alert_manager.alert(
                            "anomaly",
                            message=f"Heartbeat anomaly: {alerts[0].details}",
                            severity=alerts[0].severity,
                            data={"anomaly_count": len(alerts)},
                        )
                else:
                    self._rhythm.set_anomaly(False)

                # 4. Periodic checkpoint.
                if ckpt_interval > 0 and self._engine._idle_steps % ckpt_interval == 0:
                    self._save_checkpoint()

                # 5. Fingerprint check.
                if self._config.heartbeat.fingerprint_enabled:
                    self._identity_ok = self._check_identity()
                    if not self._identity_ok:
                        log.warning(
                            "Identity drift detected: dominant component shifted from psi0"
                        )

                # 6. Dream trigger.
                if self._dream_cycle is not None and self._dream_cycle.should_dream():
                    self._rhythm.set_dreaming(True)
                    try:
                        if self._sleep_manager is not None:
                            report = await self._sleep_manager.enter_sleep()
                        else:
                            await self._dream_cycle.run()
                            report = None
                    finally:
                        self._rhythm.set_dreaming(False)

                    # 6b. Record dream event.
                    if self._audit is not None:
                        await self._audit.record(AuditEvent.create(
                            "dream_complete",
                            data={"had_report": report is not None},
                        ))

                # 7. Adaptive interval.
                cs = getattr(self._engine, "consciousness", None)
                phase = cs.get_phase() if cs is not None else "SOLID"
                interval = self._rhythm.current_interval(phase)

                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _check_identity(self) -> bool:
        """True if argmax(psi) == argmax(psi0), with tolerance for ambiguous dominance."""
        cs = self._engine.consciousness
        if cs is None:
            return True
        dom_idx = int(np.argmax(cs.psi))
        psi0_dom = int(np.argmax(cs.psi0))
        if dom_idx == psi0_dom:
            return True
        # Tolerance: if gap between top two is < INV_PHI3, dominance is ambiguous
        gap = float(cs.psi[dom_idx] - cs.psi[psi0_dom])
        return gap < INV_PHI3

    def _save_checkpoint(self) -> None:
        """Save a cognitive checkpoint."""
        cs = self._engine.consciousness
        if cs is None:
            return
        ckpt_path = self._config.resolve(self._config.consciousness.checkpoint_file)
        cs.save_checkpoint(ckpt_path, backup=False)
        self._checkpoints_saved += 1
        log.debug("Heartbeat checkpoint saved (%d)", self._checkpoints_saved)

    def get_status(self) -> HeartbeatStatus:
        """Return a snapshot of heartbeat state."""
        return HeartbeatStatus(
            is_running=self.is_running,
            idle_steps=self._engine._idle_steps,
            identity_ok=self._identity_ok,
            last_beat=self._last_beat,
            checkpoints_saved=self._checkpoints_saved,
        )
