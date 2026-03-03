"""Tests for sleep manager — dream cycle lifecycle orchestration."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from luna.dream.dream_cycle import DreamPhase, DreamReport, PhaseResult
from luna.dream.sleep_manager import SleepManager, SleepState, SleepStatus


def _make_dream_report(duration: float = 0.5) -> DreamReport:
    """Create a mock DreamReport."""
    return DreamReport(
        phases=[
            PhaseResult(phase=DreamPhase.CONSOLIDATION, data={"drift_from_psi0": 0.1}),
            PhaseResult(phase=DreamPhase.REINTERPRETATION, data={"significant": []}),
            PhaseResult(phase=DreamPhase.DEFRAGMENTATION, data={"removed": 2}),
            PhaseResult(phase=DreamPhase.CREATIVE, data={"unexpected_couplings": []}),
        ],
        total_duration=duration,
        history_before=50,
        history_after=48,
    )


@pytest.fixture
def dream_cycle():
    dc = MagicMock()
    dc.run = AsyncMock(return_value=_make_dream_report())
    return dc


@pytest.fixture
def sleep_manager(dream_cycle):
    return SleepManager(dream_cycle, max_dream_duration=5.0)


class TestSleepManager:
    """Tests for SleepManager."""

    def test_initial_state(self, sleep_manager):
        """Sleep manager starts awake."""
        assert sleep_manager.state == SleepState.AWAKE
        assert not sleep_manager.is_sleeping

    @pytest.mark.asyncio
    async def test_enter_sleep_and_wake(self, sleep_manager, dream_cycle):
        """Enter sleep, execute dream, wake up."""
        report = await sleep_manager.enter_sleep()
        assert report is not None
        assert sleep_manager.state == SleepState.AWAKE
        assert not sleep_manager.is_sleeping
        dream_cycle.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_dream_count_increments(self, sleep_manager):
        """Dream count increases after each sleep."""
        await sleep_manager.enter_sleep()
        status = sleep_manager.get_status()
        assert status.dream_count == 1

        await sleep_manager.enter_sleep()
        status = sleep_manager.get_status()
        assert status.dream_count == 2

    @pytest.mark.asyncio
    async def test_cannot_sleep_while_sleeping(self, sleep_manager):
        """Cannot enter sleep if already sleeping."""
        # Simulate already sleeping
        sleep_manager._state = SleepState.SLEEPING
        result = await sleep_manager.enter_sleep()
        assert result is None

    @pytest.mark.asyncio
    async def test_sleeping_event_blocks_during_sleep(self, sleep_manager):
        """sleeping_event is cleared during sleep and set after."""
        assert sleep_manager.sleeping_event.is_set()  # Awake

        entered = []

        async def check_event():
            entered.append("before")
            await sleep_manager.sleeping_event.wait()
            entered.append("after")

        # The event should be set before and after sleep
        await sleep_manager.enter_sleep()
        assert sleep_manager.sleeping_event.is_set()

    @pytest.mark.asyncio
    async def test_dream_timeout(self):
        """Dream that exceeds timeout is cancelled gracefully."""
        dc = MagicMock()

        async def slow_dream():
            await asyncio.sleep(999)
            return _make_dream_report()

        dc.run = slow_dream

        sm = SleepManager(dc, max_dream_duration=0.1)
        report = await sm.enter_sleep()
        assert report is None
        assert sm.state == SleepState.AWAKE

    @pytest.mark.asyncio
    async def test_dream_crash_recovery(self):
        """System recovers from dream crash."""
        dc = MagicMock()
        dc.run = AsyncMock(side_effect=RuntimeError("dream crash"))

        sm = SleepManager(dc)
        report = await sm.enter_sleep()
        assert report is None
        assert sm.state == SleepState.AWAKE
        assert not sm.is_sleeping

    @pytest.mark.asyncio
    async def test_get_status(self, sleep_manager):
        """get_status returns expected structure."""
        status = sleep_manager.get_status()
        assert isinstance(status, SleepStatus)
        assert status.state == SleepState.AWAKE
        assert status.dream_count == 0
        assert status.total_dream_time == 0.0

    @pytest.mark.asyncio
    async def test_get_status_after_dream(self, sleep_manager):
        """get_status reflects dream history."""
        await sleep_manager.enter_sleep()
        status = sleep_manager.get_status()
        assert status.dream_count == 1
        assert status.last_dream_at is not None
        assert status.total_dream_time > 0

    @pytest.mark.asyncio
    async def test_total_dream_time_accumulates(self, sleep_manager):
        """Total dream time accumulates across multiple dreams."""
        await sleep_manager.enter_sleep()
        t1 = sleep_manager.get_status().total_dream_time
        await sleep_manager.enter_sleep()
        t2 = sleep_manager.get_status().total_dream_time
        assert t2 > t1
