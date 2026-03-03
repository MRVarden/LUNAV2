"""Phase 2.4 — Veto module test suite.

Validates the structured veto system: Severity enum, VetoEvent,
VetoRule, VetoResolution, build_veto_event(), and resolve_veto().
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from luna_common.phi_engine.veto import (
    CRITICAL_SYSTEM_RULES,
    DEFAULT_VETO_RULES,
    Severity,
    VetoEvent,
    VetoResolution,
    VetoRule,
    build_veto_event,
    resolve_veto,
)


# --- Lightweight stubs for SentinelReport and IntegrationCheck ---
# Avoid importing the full Pydantic schemas just for veto tests.

@dataclass
class _StubSentinelReport:
    veto: bool = False
    risk_score: float = 0.1
    veto_reason: str | None = None


@dataclass
class _StubIntegrationCheck:
    veto_contested: bool = False
    contest_evidence: str | None = None


class TestSeverity:
    """Validate the Severity enum."""

    def test_severity_enum(self):
        """4 levels in order: CRITICAL, HIGH, MEDIUM, LOW."""
        values = [s.value for s in Severity]
        assert values == ["critical", "high", "medium", "low"]

    def test_severity_is_str(self):
        """Severity values are usable as strings (str enum)."""
        assert Severity.CRITICAL == "critical"
        assert str(Severity.HIGH) == "Severity.HIGH" or Severity.HIGH.value == "high"


class TestVetoEvent:
    """Validate VetoEvent creation and contestability logic."""

    def test_veto_event_creation(self):
        """Required fields set correctly, defaults applied."""
        event = VetoEvent(
            source="SENTINEL",
            severity=Severity.HIGH,
            confidence=0.7,
            finding="SQL injection detected",
        )
        assert event.source == "SENTINEL"
        assert event.severity == Severity.HIGH
        assert event.confidence == 0.7
        assert event.finding == "SQL injection detected"
        assert event.contestable is True  # default
        assert event.timestamp is not None

    def test_veto_event_non_contestable(self):
        """CRITICAL + confidence > 0.95 -> contestable=False."""
        event = VetoEvent(
            source="SENTINEL",
            severity=Severity.CRITICAL,
            confidence=0.98,
            finding="RCE vulnerability",
            contestable=False,
        )
        assert event.contestable is False

    def test_veto_event_contestable(self):
        """HIGH severity -> contestable=True."""
        event = VetoEvent(
            source="SENTINEL",
            severity=Severity.HIGH,
            confidence=0.6,
            finding="Potential XSS",
            contestable=True,
        )
        assert event.contestable is True


class TestBuildVetoEvent:
    """Validate build_veto_event() from SentinelReport."""

    def test_build_veto_event_from_report(self):
        """SentinelReport(veto=True) -> VetoEvent with correct severity."""
        report = _StubSentinelReport(
            veto=True,
            risk_score=0.85,
            veto_reason="Critical vulnerability found",
        )
        event = build_veto_event(report)

        assert event is not None
        assert event.source == "SENTINEL"
        assert event.severity == Severity.CRITICAL  # risk >= 0.8
        assert event.confidence == 0.85
        assert event.finding == "Critical vulnerability found"

    def test_build_veto_event_high_severity(self):
        """risk_score in [0.5, 0.8) -> HIGH severity."""
        report = _StubSentinelReport(veto=True, risk_score=0.6, veto_reason="medium risk")
        event = build_veto_event(report)

        assert event is not None
        assert event.severity == Severity.HIGH

    def test_build_veto_event_medium_severity(self):
        """risk_score < 0.5 -> MEDIUM severity."""
        report = _StubSentinelReport(veto=True, risk_score=0.3, veto_reason="low risk")
        event = build_veto_event(report)

        assert event is not None
        assert event.severity == Severity.MEDIUM

    def test_build_veto_event_no_veto(self):
        """SentinelReport(veto=False) -> None."""
        report = _StubSentinelReport(veto=False, risk_score=0.1)
        event = build_veto_event(report)
        assert event is None

    def test_build_veto_event_contestable_critical_high_confidence(self):
        """CRITICAL + confidence > 0.95 -> non-contestable."""
        report = _StubSentinelReport(veto=True, risk_score=0.97, veto_reason="RCE")
        event = build_veto_event(report)

        assert event is not None
        assert event.severity == Severity.CRITICAL
        assert event.contestable is False  # 0.97 > 0.95

    def test_build_veto_event_unspecified_reason(self):
        """None veto_reason -> finding = 'unspecified'."""
        report = _StubSentinelReport(veto=True, risk_score=0.5, veto_reason=None)
        event = build_veto_event(report)

        assert event is not None
        assert event.finding == "unspecified"


class TestResolveVeto:
    """Validate resolve_veto() adjudication logic."""

    def test_resolve_no_veto(self):
        """No veto event -> approved."""
        check = _StubIntegrationCheck()
        resolution = resolve_veto(None, check, "FUNCTIONAL")

        assert resolution.vetoed is False
        assert resolution.event is None
        assert "No veto" in resolution.reason

    def test_resolve_veto_not_contested(self):
        """Veto without contestation -> blocked."""
        event = VetoEvent(
            source="SENTINEL",
            severity=Severity.HIGH,
            confidence=0.7,
            finding="XSS detected",
        )
        check = _StubIntegrationCheck(veto_contested=False)
        resolution = resolve_veto(event, check, "FUNCTIONAL")

        assert resolution.vetoed is True
        assert "SENTINEL veto: XSS detected" in resolution.reason

    def test_resolve_veto_contested_with_evidence(self):
        """Contestable veto + contested with evidence -> approved."""
        event = VetoEvent(
            source="SENTINEL",
            severity=Severity.HIGH,
            confidence=0.6,
            finding="Potential XSS",
            contestable=True,
        )
        check = _StubIntegrationCheck(
            veto_contested=True,
            contest_evidence="Input is sanitized by middleware",
        )
        resolution = resolve_veto(event, check, "FUNCTIONAL")

        assert resolution.vetoed is False
        assert resolution.contested is True
        assert "contested by Test-Engineer" in resolution.reason

    def test_resolve_veto_non_contestable_even_if_contested(self):
        """Non-contestable veto -> blocked even if Test-Engineer contests."""
        event = VetoEvent(
            source="SENTINEL",
            severity=Severity.CRITICAL,
            confidence=0.98,
            finding="RCE vulnerability",
            contestable=False,
        )
        check = _StubIntegrationCheck(
            veto_contested=True,
            contest_evidence="False positive",
        )
        resolution = resolve_veto(event, check, "FUNCTIONAL")

        assert resolution.vetoed is True
        assert "non-contestable" in resolution.reason

    def test_resolve_phase_broken_overrides(self):
        """Phase BROKEN -> blocked even without veto."""
        check = _StubIntegrationCheck()
        resolution = resolve_veto(None, check, "BROKEN")

        assert resolution.vetoed is True
        assert "BROKEN" in resolution.reason

    def test_resolve_phase_broken_with_veto(self):
        """Phase BROKEN + veto -> blocked (BROKEN takes priority)."""
        event = VetoEvent(
            source="SENTINEL",
            severity=Severity.HIGH,
            confidence=0.7,
            finding="issue",
        )
        check = _StubIntegrationCheck()
        resolution = resolve_veto(event, check, "BROKEN")

        assert resolution.vetoed is True
        assert "BROKEN" in resolution.reason

    def test_resolve_contested_without_evidence(self):
        """Contested but no evidence -> blocked (case 4)."""
        event = VetoEvent(
            source="SENTINEL",
            severity=Severity.MEDIUM,
            confidence=0.4,
            finding="minor issue",
        )
        check = _StubIntegrationCheck(veto_contested=True, contest_evidence=None)
        resolution = resolve_veto(event, check, "FUNCTIONAL")

        assert resolution.vetoed is True


class TestVetoRules:
    """Validate veto rule constants."""

    def test_veto_rule_defaults(self):
        """DEFAULT_VETO_RULES has the universal security_integrity rule."""
        assert len(DEFAULT_VETO_RULES) == 1
        rule = DEFAULT_VETO_RULES[0]
        assert rule.metric == "security_integrity"
        assert rule.threshold == 0.0
        assert rule.severity == Severity.CRITICAL
        assert rule.action_blocked == "ALL"

    def test_critical_system_rules_extends_default(self):
        """CRITICAL_SYSTEM_RULES includes default + threshold=0.3 rule."""
        assert len(CRITICAL_SYSTEM_RULES) == 2
        assert CRITICAL_SYSTEM_RULES[0] == DEFAULT_VETO_RULES[0]
        high_rule = CRITICAL_SYSTEM_RULES[1]
        assert high_rule.threshold == 0.3
        assert high_rule.severity == Severity.HIGH
