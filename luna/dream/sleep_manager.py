"""Sleep manager — orchestrates the dream cycle lifecycle.

Handles transition to sleep mode (heartbeat → deep rhythm),
sequential execution of dream phases, API suspension signal,
and crash-safe recovery.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from luna.dream.dream_cycle import DreamCycle, DreamReport
from luna.dream.harvest import DreamHarvest

log = logging.getLogger(__name__)


class SleepState(str, Enum):
    """State of the sleep manager."""

    AWAKE = "awake"
    ENTERING_SLEEP = "entering_sleep"
    SLEEPING = "sleeping"
    WAKING_UP = "waking_up"


@dataclass(slots=True)
class SleepStatus:
    """Snapshot of current sleep manager state."""

    state: SleepState = SleepState.AWAKE
    dream_count: int = 0
    last_dream_at: str | None = None
    last_dream_duration: float = 0.0
    total_dream_time: float = 0.0


class SleepManager:
    """Orchestrates the full sleep/dream/wake lifecycle.

    Coordinates heartbeat transition, API suspension, dream execution,
    and awakening with crash recovery.
    """

    def __init__(
        self,
        dream_cycle: DreamCycle,
        heartbeat: object | None = None,
        max_dream_duration: float = 300.0,
        awakening: object | None = None,
        engine: object | None = None,
    ) -> None:
        self._dream_cycle = dream_cycle
        self._heartbeat = heartbeat
        self._max_dream_duration = max_dream_duration
        self._awakening = awakening
        self._engine = engine
        self._state = SleepState.AWAKE
        self._dream_count = 0
        self._last_dream_at: str | None = None
        self._last_dream_duration = 0.0
        self._total_dream_time = 0.0
        self._sleeping_event = asyncio.Event()
        self._sleeping_event.set()  # Start awake (not blocked)

        # v2.3 — wake-cycle data buffers for dream harvest.
        self._pipeline_events: list[dict] = []
        self._luna_psi_snapshots: list[tuple[float, ...]] = []
        self._metrics_history: list[dict[str, float]] = []
        self._phi_iit_history: list[float] = []

    @property
    def state(self) -> SleepState:
        """Current sleep state."""
        return self._state

    @property
    def is_sleeping(self) -> bool:
        """Whether the system is currently sleeping."""
        return self._state in (SleepState.ENTERING_SLEEP, SleepState.SLEEPING, SleepState.WAKING_UP)

    @property
    def sleeping_event(self) -> asyncio.Event:
        """Event that is cleared during sleep (for API suspension).

        API handlers can await this event — it blocks while sleeping
        and unblocks when awake.
        """
        return self._sleeping_event

    # ------------------------------------------------------------------
    # Wake-cycle data recording (v2.3)
    # ------------------------------------------------------------------

    def record_event(self, event: dict) -> None:
        """Record a pipeline event for dream harvest."""
        self._pipeline_events.append(event)

    def record_psi(self, psi_snapshot: tuple[float, ...]) -> None:
        """Record a Luna Psi snapshot for dream harvest."""
        self._luna_psi_snapshots.append(psi_snapshot)

    def record_metrics(self, metrics: dict[str, float]) -> None:
        """Record normalized metrics for dream harvest."""
        self._metrics_history.append(metrics)

    def record_phi_iit(self, phi_iit: float) -> None:
        """Record a Phi_IIT measurement for dream harvest."""
        self._phi_iit_history.append(phi_iit)

    def _build_harvest(self) -> DreamHarvest | None:
        """Build a DreamHarvest from accumulated buffers.

        Returns None if there is no meaningful data to harvest.
        """
        if not self._pipeline_events and not self._luna_psi_snapshots:
            return None

        # Collect current profiles from engine if available.
        current_profiles: dict[str, tuple[float, ...]] = {}
        if self._engine is not None and hasattr(self._engine, "consciousness"):
            cs = self._engine.consciousness
            if cs is not None:
                from luna_common.constants import AGENT_PROFILES

                current_profiles = dict(AGENT_PROFILES)
                # Override Luna's profile with the live psi0.
                current_profiles[cs.agent_name] = tuple(
                    float(x) for x in cs.psi0
                )

        harvest = DreamHarvest(
            pipeline_events=tuple(self._pipeline_events),
            luna_psi_snapshots=tuple(self._luna_psi_snapshots),
            metrics_history=tuple(self._metrics_history),
            phi_iit_history=tuple(self._phi_iit_history),
            current_profiles=current_profiles,
        )

        # Clear buffers after harvest.
        self._pipeline_events.clear()
        self._luna_psi_snapshots.clear()
        self._metrics_history.clear()
        self._phi_iit_history.clear()

        return harvest

    # ------------------------------------------------------------------
    # Sleep lifecycle
    # ------------------------------------------------------------------

    async def enter_sleep(self) -> DreamReport | None:
        """Enter sleep mode and execute the dream cycle.

        Returns:
            DreamReport if the dream completed, None if interrupted or failed.
        """
        if self._state != SleepState.AWAKE:
            log.warning("SleepManager: cannot enter sleep — already in state %s", self._state)
            return None

        self._state = SleepState.ENTERING_SLEEP
        self._sleeping_event.clear()  # Block API requests
        log.info("SleepManager: entering sleep mode")

        report: DreamReport | None = None
        t0 = time.monotonic()

        try:
            # Execute dream with timeout
            self._state = SleepState.SLEEPING
            log.info("SleepManager: sleeping — dream cycle starting")

            # Build harvest from wake-cycle buffers (v2.3).
            harvest = self._build_harvest() if self._engine is not None else None

            report = await asyncio.wait_for(
                self._dream_cycle.run(harvest=harvest),
                timeout=self._max_dream_duration,
            )

            duration = time.monotonic() - t0
            self._dream_count += 1
            self._last_dream_at = datetime.now(timezone.utc).isoformat()
            self._last_dream_duration = duration
            self._total_dream_time += duration

            log.info(
                "SleepManager: dream completed in %.2fs (dream #%d)",
                duration,
                self._dream_count,
            )

            # Process awakening
            if report is not None and self._awakening is not None:
                try:
                    awakening_report = self._awakening.process(report)
                    log.info(
                        "SleepManager: awakening processed (drift=%.4f, creative=%d)",
                        awakening_report.drift_from_psi0,
                        awakening_report.creative_connections,
                    )
                except Exception as exc:
                    log.warning("SleepManager: awakening failed — %s", exc)

        except asyncio.TimeoutError:
            duration = time.monotonic() - t0
            log.warning(
                "SleepManager: dream timed out after %.2fs (max: %.2fs)",
                duration,
                self._max_dream_duration,
            )

        except Exception as exc:
            duration = time.monotonic() - t0
            log.error(
                "SleepManager: dream crashed after %.2fs — %s",
                duration,
                exc,
            )

        finally:
            # Always wake up, even if dream failed
            self._state = SleepState.WAKING_UP
            self._sleeping_event.set()  # Unblock API requests
            self._state = SleepState.AWAKE
            log.info("SleepManager: awake")

        return report

    def get_status(self) -> SleepStatus:
        """Return current sleep manager status."""
        return SleepStatus(
            state=self._state,
            dream_count=self._dream_count,
            last_dream_at=self._last_dream_at,
            last_dream_duration=self._last_dream_duration,
            total_dream_time=self._total_dream_time,
        )
