"""Tests for alerting — local webhook notifications."""

from __future__ import annotations

import pytest

from luna.observability.alerting import AlertConfig, AlertManager


@pytest.fixture
def manager():
    return AlertManager()


class TestAlertManager:
    """Tests for AlertManager."""

    def test_alert_records_history(self, manager):
        """Alerts are recorded in history."""
        manager.alert("veto", "Test veto alert")
        assert len(manager.recent_alerts) == 1
        assert manager.recent_alerts[0]["type"] == "veto"

    def test_alert_returns_true(self, manager):
        """alert() returns True when processed."""
        result = manager.alert("veto", "Test")
        assert result is True

    def test_disabled_alert_type(self):
        """Disabled alert types are not processed."""
        config = AlertConfig(on_veto=False)
        mgr = AlertManager(config)
        result = mgr.alert("veto", "Should not alert")
        assert result is False
        assert len(mgr.recent_alerts) == 0

    def test_unknown_alert_type_allowed(self, manager):
        """Unknown alert types are allowed by default."""
        result = manager.alert("custom_type", "Custom alert")
        assert result is True

    def test_multiple_alerts(self, manager):
        """Multiple alerts accumulate."""
        for i in range(5):
            manager.alert("test", f"Alert {i}")
        assert len(manager.recent_alerts) == 5

    def test_clear_history(self, manager):
        """clear_history removes all alerts."""
        manager.alert("test", "Alert")
        manager.clear_history()
        assert len(manager.recent_alerts) == 0

    def test_history_limit(self):
        """History is capped at max size."""
        mgr = AlertManager()
        mgr._max_history = 5
        for i in range(10):
            mgr.alert("test", f"Alert {i}")
        assert len(mgr.recent_alerts) == 5

    def test_alert_severity(self, manager):
        """Alert severity is recorded."""
        manager.alert("security_fail", "Critical!", severity="critical")
        assert manager.recent_alerts[0]["severity"] == "critical"

    def test_alert_data(self, manager):
        """Alert data dict is recorded."""
        manager.alert("veto", "Test", data={"metric": "security", "value": 0.0})
        assert manager.recent_alerts[0]["data"]["metric"] == "security"

    def test_get_status(self, manager):
        """get_status returns expected structure."""
        status = manager.get_status()
        assert "webhook_configured" in status
        assert status["webhook_configured"] is False
        assert status["recent_alert_count"] == 0

    def test_alert_timestamp(self, manager):
        """Alert has a timestamp."""
        manager.alert("test", "Timestamped")
        assert "timestamp" in manager.recent_alerts[0]
        assert "T" in manager.recent_alerts[0]["timestamp"]

    def test_selective_disabling(self):
        """Individual alert types can be selectively disabled."""
        config = AlertConfig(
            on_veto=False,
            on_security_fail=True,
        )
        mgr = AlertManager(config)

        assert mgr.alert("veto", "Should not alert") is False
        assert mgr.alert("security_fail", "Should alert") is True
        assert len(mgr.recent_alerts) == 1
