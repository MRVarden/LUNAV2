"""Awakening — post-dream processing and reporting.

Generates a complete awakening report from a DreamReport,
restores normal operational state, and optionally updates
Psi if metrics have changed during sleep.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from luna.dream.dream_cycle import DreamPhase, DreamReport

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AwakeningReport:
    """Summary of what happened during sleep and what changed on wake."""

    timestamp: str
    dream_duration: float
    history_before: int
    history_after: int
    entries_removed: int
    significant_correlations: int
    creative_connections: int
    drift_from_psi0: float
    psi_updated: bool
    # v2.3 fields — defaults preserve backward compatibility.
    profiles_updated: bool = False
    drift_per_agent: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        d = {
            "timestamp": self.timestamp,
            "dream_duration": self.dream_duration,
            "history_before": self.history_before,
            "history_after": self.history_after,
            "entries_removed": self.entries_removed,
            "significant_correlations": self.significant_correlations,
            "creative_connections": self.creative_connections,
            "drift_from_psi0": self.drift_from_psi0,
            "psi_updated": self.psi_updated,
            "profiles_updated": self.profiles_updated,
            "drift_per_agent": self.drift_per_agent,
        }
        return d


class Awakening:
    """Post-dream processing — report generation and state restoration.

    Extracts insights from the DreamReport, generates a compact
    AwakeningReport, and optionally nudges Psi if significant
    drift was detected during dreaming.
    """

    def __init__(self, engine: object | None = None) -> None:
        self._engine = engine

    def process(self, dream_report: DreamReport) -> AwakeningReport:
        """Process a dream report into an awakening report.

        Args:
            dream_report: The completed DreamReport.

        Returns:
            AwakeningReport summarizing the dream and any state changes.
        """
        drift = 0.0
        significant_count = 0
        creative_count = 0
        entries_removed = 0

        for pr in dream_report.phases:
            if pr.phase == DreamPhase.CONSOLIDATION:
                drift = pr.data.get("drift_from_psi0", 0.0)

            elif pr.phase == DreamPhase.REINTERPRETATION:
                significant_count = len(pr.data.get("significant", []))

            elif pr.phase == DreamPhase.DEFRAGMENTATION:
                entries_removed = pr.data.get("removed", 0)

            elif pr.phase == DreamPhase.CREATIVE:
                creative_count = len(pr.data.get("unexpected_couplings", []))

        psi_updated = False
        profiles_updated = False
        agent_drift: dict[str, float] = {}

        # v2.3 — handle SIM_CONSOLIDATION results if present.
        cr = dream_report.consolidation_report
        if cr is not None:
            profiles_updated = cr.dominant_preserved and any(
                d > 0.0 for d in cr.drift_per_agent.values()
            )
            agent_drift = dict(cr.drift_per_agent)

            # Apply Luna's updated profile to the live consciousness state.
            if profiles_updated and self._engine is not None:
                luna_profile = cr.updated_profiles.get("LUNA")
                if luna_profile is not None:
                    try:
                        import numpy as np

                        self._engine.consciousness.update_psi0(
                            np.array(luna_profile, dtype=np.float64),
                        )
                        psi_updated = True
                        log.info(
                            "Awakening: Luna Psi0 updated to %s",
                            luna_profile,
                        )
                    except Exception as exc:
                        log.warning("Awakening: failed to update Psi0 — %s", exc)
                        psi_updated = False

        report = AwakeningReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            dream_duration=dream_report.total_duration,
            history_before=dream_report.history_before,
            history_after=dream_report.history_after,
            entries_removed=entries_removed,
            significant_correlations=significant_count,
            creative_connections=creative_count,
            drift_from_psi0=drift,
            psi_updated=psi_updated,
            profiles_updated=profiles_updated,
            drift_per_agent=agent_drift,
        )

        log.info(
            "Awakening: drift=%.4f, correlations=%d, creative=%d, removed=%d, "
            "profiles_updated=%s",
            drift,
            significant_count,
            creative_count,
            entries_removed,
            profiles_updated,
        )

        return report
