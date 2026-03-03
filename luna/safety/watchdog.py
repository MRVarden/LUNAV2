"""Watchdog — automatic stop after consecutive degradations.

Monitors health phase transitions and triggers the kill switch
after a configurable number of consecutive degradations.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from luna.safety.kill_switch import KillSwitch

log = logging.getLogger(__name__)

# Phase ordering (higher index = better)
_PHASE_ORDER = {
    "BROKEN": 0,
    "FRAGILE": 1,
    "FUNCTIONAL": 2,
    "SOLID": 3,
    "EXCELLENT": 4,
}


class Watchdog:
    """Monitors consecutive degradations and triggers kill switch.

    A degradation occurs when the health phase drops to a lower level.
    After `threshold` consecutive degradations, the kill switch is activated.
    """

    def __init__(
        self,
        kill_switch: KillSwitch,
        threshold: int = 3,
    ) -> None:
        self._kill_switch = kill_switch
        self._threshold = threshold
        self._consecutive_degradations = 0
        self._last_phase: str | None = None
        self._last_report_at: str | None = None
        self._total_reports = 0
        self._total_degradations = 0

    def report(self, health_phase: str) -> bool:
        """Report the current health phase.

        Args:
            health_phase: Current phase (BROKEN/FRAGILE/FUNCTIONAL/SOLID/EXCELLENT).

        Returns:
            True if the kill switch was triggered by this report.
        """
        self._total_reports += 1
        self._last_report_at = datetime.now(timezone.utc).isoformat()

        current_order = _PHASE_ORDER.get(health_phase, -1)
        triggered = False

        if self._last_phase is not None:
            last_order = _PHASE_ORDER.get(self._last_phase, -1)
            if current_order < last_order:
                self._consecutive_degradations += 1
                self._total_degradations += 1
                log.warning(
                    "Watchdog: degradation %d/%d (%s → %s)",
                    self._consecutive_degradations,
                    self._threshold,
                    self._last_phase,
                    health_phase,
                )

                if self._consecutive_degradations >= self._threshold:
                    log.critical(
                        "Watchdog: %d consecutive degradations — triggering kill switch",
                        self._consecutive_degradations,
                    )
                    self._kill_switch.kill(
                        reason=f"watchdog: {self._consecutive_degradations} consecutive degradations"
                    )
                    triggered = self._kill_switch.is_killed
            else:
                # Phase improved or stayed the same — reset counter
                if self._consecutive_degradations > 0:
                    log.info(
                        "Watchdog: degradation streak reset (phase: %s)",
                        health_phase,
                    )
                self._consecutive_degradations = 0

        self._last_phase = health_phase
        return triggered

    def reset(self) -> None:
        """Reset the degradation counter."""
        self._consecutive_degradations = 0
        self._last_phase = None
        log.info("Watchdog: degradation counter reset")

    @property
    def consecutive_degradations(self) -> int:
        """Number of consecutive degradations observed."""
        return self._consecutive_degradations

    @property
    def threshold(self) -> int:
        """Number of consecutive degradations before kill."""
        return self._threshold

    def get_status(self) -> dict:
        """Return current watchdog status."""
        return {
            "consecutive_degradations": self._consecutive_degradations,
            "threshold": self._threshold,
            "last_phase": self._last_phase,
            "last_report_at": self._last_report_at,
            "total_reports": self._total_reports,
            "total_degradations": self._total_degradations,
            "kill_switch_active": self._kill_switch.is_killed,
        }
