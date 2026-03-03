"""Tests for watchdog — consecutive degradation detection."""

from __future__ import annotations

import pytest

from luna.safety.kill_switch import KillSwitch
from luna.safety.watchdog import Watchdog


@pytest.fixture
def kill_switch():
    return KillSwitch()


@pytest.fixture
def watchdog(kill_switch):
    return Watchdog(kill_switch, threshold=3)


class TestWatchdog:
    """Tests for Watchdog."""

    def test_initial_state(self, watchdog):
        """Watchdog starts with zero degradations."""
        assert watchdog.consecutive_degradations == 0
        assert watchdog.threshold == 3

    def test_no_degradation_on_improvement(self, watchdog):
        """Improving phase does not count as degradation."""
        watchdog.report("FRAGILE")
        watchdog.report("FUNCTIONAL")
        watchdog.report("SOLID")
        assert watchdog.consecutive_degradations == 0

    def test_no_degradation_on_same_phase(self, watchdog):
        """Same phase does not count as degradation."""
        watchdog.report("FUNCTIONAL")
        watchdog.report("FUNCTIONAL")
        watchdog.report("FUNCTIONAL")
        assert watchdog.consecutive_degradations == 0

    def test_single_degradation(self, watchdog):
        """Single degradation increments counter."""
        watchdog.report("SOLID")
        watchdog.report("FUNCTIONAL")
        assert watchdog.consecutive_degradations == 1

    def test_consecutive_degradations_trigger_kill(self, watchdog, kill_switch):
        """Three consecutive degradations trigger kill switch."""
        watchdog.report("EXCELLENT")
        triggered = watchdog.report("SOLID")
        assert not triggered
        triggered = watchdog.report("FUNCTIONAL")
        assert not triggered
        triggered = watchdog.report("FRAGILE")
        assert triggered
        assert kill_switch.is_killed

    def test_improvement_resets_counter(self, watchdog, kill_switch):
        """Improvement resets consecutive degradation counter."""
        watchdog.report("EXCELLENT")
        watchdog.report("SOLID")     # 1 degradation
        watchdog.report("FRAGILE")   # 2 degradations
        watchdog.report("FUNCTIONAL")  # improvement — reset!
        assert watchdog.consecutive_degradations == 0
        assert not kill_switch.is_killed

    def test_reset(self, watchdog):
        """reset() clears the counter."""
        watchdog.report("SOLID")
        watchdog.report("FUNCTIONAL")
        assert watchdog.consecutive_degradations == 1
        watchdog.reset()
        assert watchdog.consecutive_degradations == 0

    def test_custom_threshold(self, kill_switch):
        """Custom threshold works correctly."""
        wd = Watchdog(kill_switch, threshold=1)
        wd.report("SOLID")
        triggered = wd.report("FRAGILE")
        assert triggered
        assert kill_switch.is_killed

    def test_first_report_no_degradation(self, watchdog):
        """First report never counts as degradation (no previous phase)."""
        watchdog.report("BROKEN")
        assert watchdog.consecutive_degradations == 0

    def test_get_status(self, watchdog):
        """get_status returns expected structure."""
        watchdog.report("SOLID")
        watchdog.report("FUNCTIONAL")
        status = watchdog.get_status()
        assert status["consecutive_degradations"] == 1
        assert status["threshold"] == 3
        assert status["last_phase"] == "FUNCTIONAL"
        assert status["total_reports"] == 2
        assert status["total_degradations"] == 1
        assert status["kill_switch_active"] is False

    def test_kill_reason_includes_count(self, kill_switch):
        """Kill reason mentions the degradation count."""
        wd = Watchdog(kill_switch, threshold=2)
        wd.report("EXCELLENT")
        wd.report("SOLID")
        wd.report("FRAGILE")
        status = kill_switch.get_status()
        assert "2 consecutive" in status["killed_reason"]

    def test_disabled_kill_switch(self):
        """Watchdog with disabled kill switch does not kill."""
        ks = KillSwitch(enabled=False)
        wd = Watchdog(ks, threshold=1)
        wd.report("SOLID")
        triggered = wd.report("FRAGILE")
        assert not triggered
        assert not ks.is_killed

    def test_multiple_cycles(self, watchdog, kill_switch):
        """Multiple degradation/improvement cycles work correctly."""
        # First cycle — 2 degradations then improvement
        watchdog.report("EXCELLENT")
        watchdog.report("SOLID")
        watchdog.report("EXCELLENT")  # reset
        assert watchdog.consecutive_degradations == 0

        # Second cycle — 2 degradations then improvement
        watchdog.report("FUNCTIONAL")
        watchdog.report("EXCELLENT")  # reset
        assert watchdog.consecutive_degradations == 0

        # Third cycle — reach threshold
        watchdog.report("SOLID")
        watchdog.report("FUNCTIONAL")
        watchdog.report("FRAGILE")
        assert kill_switch.is_killed
