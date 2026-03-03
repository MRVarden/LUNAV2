"""Tests for heartbeat monitor — anomaly detection."""

from __future__ import annotations

import pytest

from luna.heartbeat.monitor import AnomalyAlert, HeartbeatMonitor
from luna.heartbeat.vitals import VitalSigns


def _make_vitals(**overrides) -> VitalSigns:
    """Create a VitalSigns with defaults and optional overrides."""
    defaults = dict(
        psi=(0.25, 0.35, 0.25, 0.15),
        psi0=(0.25, 0.35, 0.25, 0.15),
        identity_drift=0.1,
        dominant_component="Reflexion",
        identity_preserved=True,
        phi_iit=0.7,
        quality_score=0.65,
        health_phase="SOLID",
        total_memories=100,
        idle_steps=42,
        uptime_seconds=300.0,
        overall_vitality=0.75,
        emotional_state="contemplatif",
    )
    defaults.update(overrides)
    return VitalSigns(**defaults)


class TestAnomalyAlert:
    """Tests for AnomalyAlert dataclass."""

    def test_frozen(self):
        """AnomalyAlert is immutable."""
        alert = AnomalyAlert(
            alert_type="test", severity="warning",
            details="test", timestamp="2026-01-01",
        )
        with pytest.raises(AttributeError):
            alert.severity = "critical"  # type: ignore[misc]


class TestHeartbeatMonitor:
    """Tests for HeartbeatMonitor anomaly detection."""

    def test_no_anomalies(self):
        """Healthy vitals produce no alerts."""
        monitor = HeartbeatMonitor()
        vitals = _make_vitals()
        alerts = monitor.check(vitals)
        assert len(alerts) == 0

    def test_identity_drift_warning(self):
        """Identity drift above warning threshold triggers alert."""
        monitor = HeartbeatMonitor(drift_warning=0.3)
        vitals = _make_vitals(identity_drift=0.35)
        alerts = monitor.check(vitals)
        drift_alerts = [a for a in alerts if a.alert_type == "identity_drift"]
        assert len(drift_alerts) == 1
        assert drift_alerts[0].severity == "warning"

    def test_identity_drift_critical(self):
        """Identity drift above critical threshold triggers critical alert."""
        monitor = HeartbeatMonitor(drift_critical=0.5)
        vitals = _make_vitals(identity_drift=0.6)
        alerts = monitor.check(vitals)
        drift_alerts = [a for a in alerts if a.alert_type == "identity_drift"]
        assert len(drift_alerts) == 1
        assert drift_alerts[0].severity == "critical"

    def test_identity_shift(self):
        """Identity not preserved triggers identity_shift alert."""
        monitor = HeartbeatMonitor()
        vitals = _make_vitals(identity_preserved=False, identity_drift=0.1)
        alerts = monitor.check(vitals)
        shift_alerts = [a for a in alerts if a.alert_type == "identity_shift"]
        assert len(shift_alerts) == 1

    def test_score_crash(self):
        """Large quality score drop triggers score_crash alert."""
        monitor = HeartbeatMonitor(score_drop_threshold=0.2)

        # First check (no previous -> no crash detection)
        good = _make_vitals(quality_score=0.8)
        alerts1 = monitor.check(good)

        # Second check with big drop
        bad = _make_vitals(quality_score=0.5)
        alerts2 = monitor.check(bad)
        crash_alerts = [a for a in alerts2 if a.alert_type == "score_crash"]
        assert len(crash_alerts) == 1
        assert crash_alerts[0].severity == "critical"

    def test_phase_degradation(self):
        """Health phase degradation triggers alert."""
        monitor = HeartbeatMonitor()

        solid = _make_vitals(health_phase="SOLID")
        monitor.check(solid)

        fragile = _make_vitals(health_phase="FRAGILE")
        alerts = monitor.check(fragile)
        phase_alerts = [a for a in alerts if a.alert_type == "phase_degradation"]
        assert len(phase_alerts) == 1

    def test_no_phase_degradation_on_improvement(self):
        """Phase improvement does not trigger degradation alert."""
        monitor = HeartbeatMonitor()

        fragile = _make_vitals(health_phase="FRAGILE")
        monitor.check(fragile)

        solid = _make_vitals(health_phase="SOLID")
        alerts = monitor.check(solid)
        phase_alerts = [a for a in alerts if a.alert_type == "phase_degradation"]
        assert len(phase_alerts) == 0

    def test_low_phi_iit(self):
        """Low Phi_IIT triggers warning."""
        monitor = HeartbeatMonitor(phi_iit_warning=0.5)
        vitals = _make_vitals(phi_iit=0.3)
        alerts = monitor.check(vitals)
        phi_alerts = [a for a in alerts if a.alert_type == "low_phi_iit"]
        assert len(phi_alerts) == 1

    def test_first_check_no_crash(self):
        """First check never triggers score_crash (no previous)."""
        monitor = HeartbeatMonitor()
        vitals = _make_vitals(quality_score=0.1)
        alerts = monitor.check(vitals)
        crash_alerts = [a for a in alerts if a.alert_type == "score_crash"]
        assert len(crash_alerts) == 0

    def test_multiple_anomalies(self):
        """Multiple anomalies are reported simultaneously."""
        monitor = HeartbeatMonitor(
            drift_critical=0.5,
            phi_iit_warning=0.5,
        )
        vitals = _make_vitals(
            identity_drift=0.7,
            identity_preserved=False,
            phi_iit=0.2,
        )
        alerts = monitor.check(vitals)
        assert len(alerts) >= 3  # drift, shift, phi_iit
