"""Structured veto module -- replaces inline veto logic in luna.py.

The veto mechanism short-circuits the scoring pipeline. An external review
(security audit) may raise a veto; Luna adjudicates contestation.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone


class Severity(str, enum.Enum):
    """Severity levels for veto events."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class VetoEvent:
    """Structured veto event.

    Produced by an external review, read by Luna.
    Non-contestable when severity=CRITICAL and confidence > 0.95.
    """

    source: str                               # origin of the veto
    severity: Severity                        # CRITICAL / HIGH / MEDIUM / LOW
    confidence: float                         # 0.0 - 1.0
    finding: str                              # Description of the issue
    contestable: bool = True                  # may be contested?
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass(frozen=True, slots=True)
class VetoRule:
    """Rule that triggers a veto.

    Framework: veto short-circuits scoring (no EMA, no weighting).
    """

    metric: str                     # "security_integrity"
    threshold: float                # 0.0 for universal, 0.3 for critical_system
    severity: Severity = Severity.CRITICAL
    action_blocked: str = "ALL"     # "ALL" or "merge_to_main"


# --- Default rules (framework veto rules) ---

DEFAULT_VETO_RULES: tuple[VetoRule, ...] = (
    VetoRule(
        metric="security_integrity",
        threshold=0.0,
        severity=Severity.CRITICAL,
        action_blocked="ALL",
    ),
)

CRITICAL_SYSTEM_RULES: tuple[VetoRule, ...] = DEFAULT_VETO_RULES + (
    VetoRule(
        metric="security_integrity",
        threshold=0.3,
        severity=Severity.HIGH,
        action_blocked="ALL",
    ),
)


@dataclass(frozen=True, slots=True)
class VetoResolution:
    """Result of Luna's adjudication.

    Luna reads: veto + contestation + manifest -> decision.
    """

    vetoed: bool                        # Final decision
    event: VetoEvent | None             # The veto event (None if no veto)
    contested: bool                     # Was the veto contested?
    contest_evidence: str | None        # Justification for contestation
    reason: str                         # Explanation of the decision


def _get(obj, key, default=None):
    """Access a field by key (dict) or attribute (object)."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def build_veto_event(
    sentinel_report,   # dict or object with veto, risk_score, veto_reason
) -> VetoEvent | None:
    """Convert a security report into a structured VetoEvent.

    Accepts both plain dicts and objects with attribute access.
    Returns None if sentinel_report.veto is False.
    """
    if not _get(sentinel_report, "veto", False):
        return None

    risk_score = _get(sentinel_report, "risk_score", 0.0)

    # Infer severity from risk_score.
    if risk_score >= 0.8:
        severity = Severity.CRITICAL
    elif risk_score >= 0.5:
        severity = Severity.HIGH
    else:
        severity = Severity.MEDIUM

    confidence = risk_score
    veto_reason = _get(sentinel_report, "veto_reason")

    return VetoEvent(
        source="security_review",
        severity=severity,
        confidence=confidence,
        finding=veto_reason or "unspecified",
        contestable=not (severity == Severity.CRITICAL and confidence > 0.95),
    )


def resolve_veto(
    event: VetoEvent | None,
    integration_check,  # IntegrationCheck
    phase: str,
) -> VetoResolution:
    """Luna adjudication: veto + contestation + phase -> decision.

    Rules:
    1. No veto and phase != BROKEN -> approved
    2. Non-contestable veto -> blocked (CRITICAL + high confidence)
    3. Contestable veto + contested with evidence -> approved (contestation wins)
    4. Contestable veto + not contested -> blocked
    5. Phase BROKEN -> blocked (independent of veto)
    """
    # Case 5: Phase BROKEN blocks independently.
    if phase == "BROKEN":
        return VetoResolution(
            vetoed=True,
            event=event,
            contested=False,
            contest_evidence=None,
            reason="Phase BROKEN — cognitive integrity compromised",
        )

    # Case 1: No veto.
    if event is None:
        return VetoResolution(
            vetoed=False,
            event=None,
            contested=False,
            contest_evidence=None,
            reason=f"No veto, phase={phase}",
        )

    contested = integration_check.veto_contested
    evidence = integration_check.contest_evidence

    # Case 2: Non-contestable.
    if not event.contestable:
        return VetoResolution(
            vetoed=True,
            event=event,
            contested=contested,
            contest_evidence=evidence,
            reason=(
                f"Veto non-contestable: {event.finding} "
                f"(severity={event.severity.value}, confidence={event.confidence:.2f})"
            ),
        )

    # Case 3: Contestable + contested with evidence.
    if contested and evidence:
        return VetoResolution(
            vetoed=False,
            event=event,
            contested=True,
            contest_evidence=evidence,
            reason=(
                f"Veto contested: {evidence} "
                f"(original: {event.finding})"
            ),
        )

    # Case 4: Contestable but not contested (or without evidence).
    return VetoResolution(
        vetoed=True,
        event=event,
        contested=contested,
        contest_evidence=evidence,
        reason=f"Veto: {event.finding}",
    )
