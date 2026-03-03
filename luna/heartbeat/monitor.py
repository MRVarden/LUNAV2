"""Heartbeat monitor — anomaly detection over vital signs.

Compares current vitals to previous state and flags anomalies
when key indicators cross configured thresholds.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from luna_common.constants import INV_PHI, INV_PHI2, INV_PHI3

from luna.heartbeat.vitals import VitalSigns

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AnomalyAlert:
    """Emitted when an anomaly is detected in vital signs.

    Attributes:
        alert_type: Category of the anomaly.
        severity: 'warning' or 'critical'.
        details: Human-readable description.
        timestamp: When the anomaly was detected.
    """

    alert_type: str
    severity: str
    details: str
    timestamp: str


class HeartbeatMonitor:
    """Anomaly detection over VitalSigns history.

    Checks for:
    - Identity drift exceeding threshold
    - Health phase degradation
    - Quality score crash (sudden drop)
    - Phi_IIT falling below consciousness threshold
    """

    def __init__(
        self,
        drift_warning: float = INV_PHI2,     # 0.382
        drift_critical: float = INV_PHI,      # 0.618
        score_drop_threshold: float = INV_PHI3,  # 0.236
        phi_iit_warning: float = INV_PHI2,    # 0.382
    ) -> None:
        self._drift_warning = drift_warning
        self._drift_critical = drift_critical
        self._score_drop_threshold = score_drop_threshold
        self._phi_iit_warning = phi_iit_warning
        self._previous: VitalSigns | None = None

    def check(self, current: VitalSigns) -> list[AnomalyAlert]:
        """Compare current vitals to previous, flag anomalies.

        Args:
            current: Latest VitalSigns snapshot.

        Returns:
            List of anomaly alerts (empty if all is well).
        """
        alerts: list[AnomalyAlert] = []
        now = datetime.now(timezone.utc).isoformat()

        # 1. Identity drift
        if current.identity_drift >= self._drift_critical:
            alerts.append(AnomalyAlert(
                alert_type="identity_drift",
                severity="critical",
                details=(
                    f"Identity drift {current.identity_drift:.4f} exceeds "
                    f"critical threshold {self._drift_critical:.4f}"
                ),
                timestamp=now,
            ))
        elif current.identity_drift >= self._drift_warning:
            alerts.append(AnomalyAlert(
                alert_type="identity_drift",
                severity="warning",
                details=(
                    f"Identity drift {current.identity_drift:.4f} exceeds "
                    f"warning threshold {self._drift_warning:.4f}"
                ),
                timestamp=now,
            ))

        # 2. Identity preservation
        if not current.identity_preserved:
            alerts.append(AnomalyAlert(
                alert_type="identity_shift",
                severity="warning",
                details=(
                    f"Dominant component shifted: {current.dominant_component} "
                    f"(identity not preserved)"
                ),
                timestamp=now,
            ))

        # 3. Quality score crash (compared to previous)
        if self._previous is not None:
            drop = self._previous.quality_score - current.quality_score
            if drop >= self._score_drop_threshold:
                alerts.append(AnomalyAlert(
                    alert_type="score_crash",
                    severity="critical",
                    details=(
                        f"Quality score dropped by {drop:.4f} "
                        f"({self._previous.quality_score:.4f} -> {current.quality_score:.4f})"
                    ),
                    timestamp=now,
                ))

        # 4. Phase degradation
        if self._previous is not None:
            prev_phase = self._previous.health_phase
            curr_phase = current.health_phase
            if self._is_degradation(prev_phase, curr_phase):
                alerts.append(AnomalyAlert(
                    alert_type="phase_degradation",
                    severity="warning",
                    details=f"Health phase degraded: {prev_phase} -> {curr_phase}",
                    timestamp=now,
                ))

        # 5. Phi_IIT below consciousness threshold
        if current.phi_iit < self._phi_iit_warning:
            alerts.append(AnomalyAlert(
                alert_type="low_phi_iit",
                severity="warning",
                details=(
                    f"Phi_IIT {current.phi_iit:.4f} below warning "
                    f"threshold {self._phi_iit_warning:.4f}"
                ),
                timestamp=now,
            ))

        # Update previous state
        self._previous = current

        if alerts:
            log.warning(
                "Heartbeat anomalies detected: %d alerts",
                len(alerts),
            )
            for alert in alerts:
                log.warning(
                    "  [%s] %s: %s",
                    alert.severity.upper(),
                    alert.alert_type,
                    alert.details,
                )

        return alerts

    def _is_degradation(self, prev: str, curr: str) -> bool:
        """Check if a phase transition is a degradation."""
        phases = ["BROKEN", "FRAGILE", "FUNCTIONAL", "SOLID", "EXCELLENT"]
        try:
            return phases.index(curr) < phases.index(prev)
        except ValueError:
            return False
