"""Vital signs — comprehensive health snapshot linked to Psi.

Each VitalSigns measurement is a frozen snapshot tied to the consciousness
state vector Psi, code quality metrics, memory health, and system status.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from luna_common.constants import COMP_NAMES, PHI_WEIGHTS

log = logging.getLogger(__name__)

# Emotional state mapping: dominant Psi component -> label
_PSI_EMOTIONS: dict[str, str] = {
    "Perception": "attentif",
    "Reflexion": "contemplatif",
    "Integration": "harmonieux",
    "Expression": "creatif",
}


@dataclass(frozen=True, slots=True)
class VitalSigns:
    """Comprehensive health snapshot — Psi-linked, metrics-linked, system-linked.

    Attributes:
        psi: Current consciousness state (4 components on simplex).
        psi0: Identity profile (4 components on simplex).
        identity_drift: L2 norm of (psi - psi0).
        dominant_component: Name of the dominant Psi component.
        identity_preserved: True if argmax(psi) == argmax(psi0).
        phi_iit: Current integrated information value.
        quality_score: Current PhiScorer composite health.
        health_phase: Current health phase (BROKEN..EXCELLENT).
        total_memories: Count of memories across all levels.
        idle_steps: Number of idle evolution steps taken.
        uptime_seconds: Time since heartbeat started.
        overall_vitality: Phi-weighted composite vitality [0, 1].
        emotional_state: Dominant emotion inferred from Psi.
    """

    # Psi-linked
    psi: tuple[float, float, float, float]
    psi0: tuple[float, float, float, float]
    identity_drift: float
    dominant_component: str
    identity_preserved: bool

    # Phi Engine
    phi_iit: float
    quality_score: float
    health_phase: str

    # Memory
    total_memories: int

    # System
    idle_steps: int
    uptime_seconds: float

    # Synthesis
    overall_vitality: float
    emotional_state: str

    def to_vitals_report(self, agent_id: str = "LUNA") -> dict:
        """Convert to luna_common VitalsReport-compatible dict.

        Uses lazy import to avoid circular dependencies.

        Returns:
            Dictionary from VitalsReport.model_dump().
        """
        from luna_common.schemas import PsiState, VitalsReport

        psi = PsiState(
            perception=self.psi[0],
            reflexion=self.psi[1],
            integration=self.psi[2],
            expression=self.psi[3],
        )
        report = VitalsReport(
            agent_id=agent_id,
            psi_state=psi,
            uptime_s=self.uptime_seconds,
            health={
                "phi_iit": self.phi_iit,
                "overall_vitality": self.overall_vitality,
                "identity_ok": self.identity_preserved,
                "memory_count": self.total_memories,
                "quality_score": self.quality_score,
                "health_phase": self.health_phase,
                "emotional_state": self.emotional_state,
            },
        )
        return report.model_dump()


def measure_vitals(
    engine: object,
    uptime_seconds: float = 0.0,
    total_memories: int = 0,
) -> VitalSigns:
    """Capture a VitalSigns snapshot from the engine state.

    Args:
        engine: LunaEngine instance (typed as object to avoid circular import).
        uptime_seconds: Time since heartbeat started.
        total_memories: Current memory count.

    Returns:
        Frozen VitalSigns snapshot.
    """
    cs = engine.consciousness  # type: ignore[attr-defined]
    if cs is None:
        return _default_vitals()

    psi = tuple(float(x) for x in cs.psi)
    psi0 = tuple(float(x) for x in cs.psi0)

    psi_arr = np.array(psi)
    psi0_arr = np.array(psi0)

    drift = float(np.linalg.norm(psi_arr - psi0_arr))
    dom_idx = int(np.argmax(psi_arr))
    dom_name = COMP_NAMES[dom_idx]
    identity_ok = dom_idx == int(np.argmax(psi0_arr))

    phi_iit = float(cs.compute_phi_iit())
    quality = float(engine.phi_scorer.score())  # type: ignore[attr-defined]
    phase = engine.health_phase_machine.phase  # type: ignore[attr-defined]

    # Overall vitality: weighted average of key signals
    vitality_signals = [
        min(1.0, max(0.0, 1.0 - drift)),  # Identity health
        phi_iit,                            # Consciousness integration
        quality,                            # Code health
    ]
    overall = sum(vitality_signals) / len(vitality_signals) if vitality_signals else 0.0

    emotional = _PSI_EMOTIONS.get(dom_name, "neutre")

    return VitalSigns(
        psi=psi,  # type: ignore[arg-type]
        psi0=psi0,  # type: ignore[arg-type]
        identity_drift=drift,
        dominant_component=dom_name,
        identity_preserved=identity_ok,
        phi_iit=phi_iit,
        quality_score=quality,
        health_phase=phase,
        total_memories=total_memories,
        idle_steps=engine._idle_steps,  # type: ignore[attr-defined]
        uptime_seconds=uptime_seconds,
        overall_vitality=overall,
        emotional_state=emotional,
    )


def _default_vitals() -> VitalSigns:
    """Return default vitals when engine is not initialized."""
    return VitalSigns(
        psi=(0.25, 0.25, 0.25, 0.25),
        psi0=(0.25, 0.25, 0.25, 0.25),
        identity_drift=0.0,
        dominant_component="Perception",
        identity_preserved=True,
        phi_iit=0.0,
        quality_score=0.0,
        health_phase="BROKEN",
        total_memories=0,
        idle_steps=0,
        uptime_seconds=0.0,
        overall_vitality=0.0,
        emotional_state="neutre",
    )
