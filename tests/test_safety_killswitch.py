"""Tests for kill switch — emergency stop mechanism."""

from __future__ import annotations

import asyncio

import pytest

from luna.safety.kill_switch import KillSwitch


class TestKillSwitch:
    """Tests for KillSwitch."""

    def test_initial_state(self):
        """Kill switch starts in non-killed state."""
        ks = KillSwitch()
        assert ks.is_killed is False
        assert ks.is_enabled is True

    def test_kill(self):
        """kill() sets the killed flag."""
        ks = KillSwitch()
        ks.kill(reason="test")
        assert ks.is_killed is True

    def test_reset(self):
        """reset() clears the killed flag."""
        ks = KillSwitch()
        ks.kill(reason="test")
        ks.reset()
        assert ks.is_killed is False

    def test_check_raises_when_killed(self):
        """check() raises RuntimeError when killed."""
        ks = KillSwitch()
        ks.kill(reason="testing check")
        with pytest.raises(RuntimeError, match="Kill switch active"):
            ks.check()

    def test_check_passes_when_alive(self):
        """check() does nothing when not killed."""
        ks = KillSwitch()
        ks.check()  # Should not raise

    def test_disabled_kill_switch(self):
        """Disabled kill switch ignores kill requests."""
        ks = KillSwitch(enabled=False)
        result = ks.kill(reason="test")
        assert result == 0
        assert ks.is_killed is False

    @pytest.mark.asyncio
    async def test_cancels_registered_tasks(self):
        """kill() cancels all registered asyncio tasks."""
        ks = KillSwitch()

        async def long_task():
            await asyncio.sleep(999)

        task1 = asyncio.create_task(long_task())
        task2 = asyncio.create_task(long_task())
        ks.register_task(task1)
        ks.register_task(task2)

        cancelled = ks.kill(reason="test cancel")
        assert cancelled == 2

        # Allow event loop to process cancellations
        await asyncio.sleep(0)
        assert task1.cancelled()
        assert task2.cancelled()

    @pytest.mark.asyncio
    async def test_does_not_cancel_completed_tasks(self):
        """kill() skips already completed tasks."""
        ks = KillSwitch()

        async def quick_task():
            return 42

        task = asyncio.create_task(quick_task())
        await task  # Let it complete

        ks.register_task(task)
        cancelled = ks.kill(reason="test")
        assert cancelled == 0

    def test_get_status(self):
        """get_status returns expected structure."""
        ks = KillSwitch()
        status = ks.get_status()
        assert status["enabled"] is True
        assert status["killed"] is False
        assert status["killed_at"] is None

    def test_get_status_after_kill(self):
        """get_status reflects killed state."""
        ks = KillSwitch()
        ks.kill(reason="status test")
        status = ks.get_status()
        assert status["killed"] is True
        assert status["killed_reason"] == "status test"
        assert status["killed_at"] is not None

    def test_kill_returns_cancelled_count(self):
        """kill() returns the number of tasks cancelled."""
        ks = KillSwitch()
        result = ks.kill(reason="no tasks")
        assert result == 0
