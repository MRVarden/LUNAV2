"""Heartbeat rhythm — Phi-modulated intervals.

The heartbeat rhythm is not fixed. It adapts to Luna's activity state:
- Active (code generation): faster (base interval)
- Idle: moderate (PHI * base)
- Dreaming: slow (PHI^3 * base)
- Alert (anomaly): very fast (base / 2)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from luna_common.constants import PHI, PHI2

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class HeartbeatRhythm:
    """Phi-modulated intervals for heartbeat timing.

    Attributes:
        base: Base interval in seconds.
        primary: PHI * base (standard idle rhythm).
        deep: PHI^2 * base (relaxed rhythm).
        sleep: PHI^3 * base (dream cycle rhythm).
        alert: base / 2 (anomaly detected rhythm).
    """

    base: float
    primary: float
    deep: float
    sleep: float
    alert: float

    @staticmethod
    def from_base(base_seconds: float) -> HeartbeatRhythm:
        """Create a full rhythm set from a base interval.

        Args:
            base_seconds: The base heartbeat interval.

        Returns:
            HeartbeatRhythm with all Phi-derived intervals.
        """
        return HeartbeatRhythm(
            base=base_seconds,
            primary=base_seconds * PHI,
            deep=base_seconds * PHI2,
            sleep=base_seconds * PHI ** 3,
            alert=base_seconds / 2.0,
        )


class AdaptiveRhythm:
    """Adjusts heartbeat interval based on activity and health phase.

    Uses HeartbeatRhythm intervals and selects the appropriate one
    based on the current system state.
    """

    def __init__(self, base_seconds: float = 1.0) -> None:
        self._rhythm = HeartbeatRhythm.from_base(base_seconds)
        self._is_dreaming = False
        self._has_anomaly = False

    @property
    def rhythm(self) -> HeartbeatRhythm:
        """Current rhythm configuration."""
        return self._rhythm

    def set_dreaming(self, dreaming: bool) -> None:
        """Transition to/from dream rhythm."""
        self._is_dreaming = dreaming
        if dreaming:
            log.debug("Rhythm: entering dream mode (interval=%.3fs)", self._rhythm.sleep)
        else:
            log.debug("Rhythm: exiting dream mode")

    def set_anomaly(self, anomaly: bool) -> None:
        """Transition to/from alert rhythm."""
        self._has_anomaly = anomaly
        if anomaly:
            log.debug("Rhythm: alert mode (interval=%.3fs)", self._rhythm.alert)

    def current_interval(self, health_phase: str = "FUNCTIONAL") -> float:
        """Return the appropriate interval for the current state.

        Priority:
        1. Alert (anomaly) -> fastest
        2. Dreaming -> slowest
        3. Phase-based:
           - BROKEN/FRAGILE: base (fast monitoring)
           - FUNCTIONAL: primary
           - SOLID/EXCELLENT: deep (relaxed)

        Args:
            health_phase: Current health phase string.

        Returns:
            Interval in seconds.
        """
        if self._has_anomaly:
            return self._rhythm.alert

        if self._is_dreaming:
            return self._rhythm.sleep

        if health_phase in ("BROKEN", "FRAGILE"):
            return self._rhythm.base
        if health_phase in ("SOLID", "EXCELLENT"):
            return self._rhythm.deep

        return self._rhythm.primary
