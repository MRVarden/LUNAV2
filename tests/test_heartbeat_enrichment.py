"""Tests for heartbeat enrichment — Session 2 integration.

Validates that the Heartbeat class correctly wires:
  - AdaptiveRhythm (Phi-modulated intervals)
  - HeartbeatMonitor (anomaly detection over vital signs)
  - measure_vitals() (comprehensive health snapshot)

Tests prove the BEHAVIOUR is correct — the enriched heartbeat loop
measures vitals, detects anomalies, and adapts its rhythm.
No network calls, no LLM, no Docker.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from luna.core.config import (
    ConsciousnessSection,
    DreamSection,
    HeartbeatSection,
    LunaConfig,
    LunaSection,
    MemorySection,
    ObservabilitySection,
    PipelineSection,
)
from luna.core.luna import LunaEngine
from luna.heartbeat.heartbeat import Heartbeat
from luna.heartbeat.monitor import HeartbeatMonitor
from luna.heartbeat.rhythm import AdaptiveRhythm
from luna.heartbeat.vitals import VitalSigns


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Path) -> LunaConfig:
    """Build a minimal LunaConfig for heartbeat enrichment tests."""
    return LunaConfig(
        luna=LunaSection(
            version="test",
            agent_name="LUNA",
            data_dir=str(tmp_path),
            pipeline_dir=str(tmp_path / "pipeline"),
        ),
        consciousness=ConsciousnessSection(
            checkpoint_file="cs.json",
            backup_on_save=False,
        ),
        memory=MemorySection(fractal_root=str(tmp_path / "fractal")),
        pipeline=PipelineSection(root=str(tmp_path / "pipeline")),
        observability=ObservabilitySection(),
        heartbeat=HeartbeatSection(
            interval_seconds=0.01,  # Fast for tests.
            fingerprint_enabled=False,
            checkpoint_interval=0,  # Disable periodic checkpoints.
        ),
        dream=DreamSection(enabled=False),
        root_dir=tmp_path,
    )


def _make_engine(tmp_path: Path) -> LunaEngine:
    """Create and initialize a LunaEngine for testing."""
    cfg = _make_config(tmp_path)
    engine = LunaEngine(cfg)
    engine.initialize()
    return engine


def _make_extreme_vitals() -> VitalSigns:
    """Return a VitalSigns with extreme values that trigger anomalies."""
    return VitalSigns(
        psi=(0.05, 0.05, 0.85, 0.05),
        psi0=(0.25, 0.35, 0.25, 0.15),
        identity_drift=0.9,           # Critical drift
        dominant_component="Integration",
        identity_preserved=False,      # Identity shifted
        phi_iit=0.1,                   # Below warning threshold
        quality_score=0.1,
        health_phase="BROKEN",
        total_memories=0,
        idle_steps=1,
        uptime_seconds=1.0,
        overall_vitality=0.1,
        emotional_state="harmonieux",
    )


# ===========================================================================
# Test 7: Heartbeat has AdaptiveRhythm
# ===========================================================================


class TestHeartbeatRhythmWiring:
    """Heartbeat.__init__ creates an AdaptiveRhythm by default."""

    def test_heartbeat_has_adaptive_rhythm(self, tmp_path: Path):
        """A newly created Heartbeat has an AdaptiveRhythm instance."""
        engine = _make_engine(tmp_path)
        cfg = engine.config
        hb = Heartbeat(engine, cfg)
        assert isinstance(hb._rhythm, AdaptiveRhythm), (
            f"Expected AdaptiveRhythm, got {type(hb._rhythm).__name__}"
        )


# ===========================================================================
# Test 8: Heartbeat has HeartbeatMonitor
# ===========================================================================


class TestHeartbeatMonitorWiring:
    """Heartbeat.__init__ creates a HeartbeatMonitor by default."""

    def test_heartbeat_has_monitor(self, tmp_path: Path):
        """A newly created Heartbeat has a HeartbeatMonitor instance."""
        engine = _make_engine(tmp_path)
        cfg = engine.config
        hb = Heartbeat(engine, cfg)
        assert isinstance(hb._monitor, HeartbeatMonitor), (
            f"Expected HeartbeatMonitor, got {type(hb._monitor).__name__}"
        )


# ===========================================================================
# Test 9: Heartbeat stores last_vitals after one beat
# ===========================================================================


class TestHeartbeatStoresVitals:
    """After at least one iteration, _last_vitals is populated."""

    @pytest.mark.asyncio
    async def test_heartbeat_stores_last_vitals_after_beat(self, tmp_path: Path):
        """After running one iteration, _last_vitals contains overall_vitality."""
        engine = _make_engine(tmp_path)
        cfg = engine.config
        hb = Heartbeat(engine, cfg)
        hb.start()
        # Let it tick at least once (interval=0.01s).
        await asyncio.sleep(0.08)
        await hb.stop()

        assert hb._last_vitals is not None, (
            "_last_vitals must be populated after at least one heartbeat iteration"
        )
        assert "overall_vitality" in hb._last_vitals, (
            "_last_vitals dict must contain 'overall_vitality' key"
        )


# ===========================================================================
# Test 10: Rhythm responds to anomaly detection
# ===========================================================================


class TestRhythmRespondsToAnomaly:
    """When monitor detects anomalies, rhythm.set_anomaly(True) is called."""

    @pytest.mark.asyncio
    async def test_heartbeat_rhythm_responds_to_anomaly(self, tmp_path: Path):
        """When measure_vitals returns extreme values that trigger anomalies,
        the rhythm transitions to alert mode (set_anomaly(True) is called)."""
        engine = _make_engine(tmp_path)
        cfg = engine.config

        # Use a real AdaptiveRhythm but spy on set_anomaly.
        rhythm = AdaptiveRhythm(base_seconds=0.01)
        original_set_anomaly = rhythm.set_anomaly
        anomaly_calls: list[bool] = []

        def tracking_set_anomaly(value: bool) -> None:
            anomaly_calls.append(value)
            original_set_anomaly(value)

        rhythm.set_anomaly = tracking_set_anomaly  # type: ignore[assignment]

        # Use a monitor that will detect anomalies in the extreme vitals.
        monitor = HeartbeatMonitor()

        hb = Heartbeat(engine, cfg, rhythm=rhythm, monitor=monitor)

        # Patch measure_vitals to return extreme values that trigger anomalies.
        extreme = _make_extreme_vitals()
        with patch("luna.heartbeat.heartbeat.measure_vitals", return_value=extreme):
            hb.start()
            await asyncio.sleep(0.08)
            await hb.stop()

        # set_anomaly should have been called with True at least once.
        assert any(v is True for v in anomaly_calls), (
            "set_anomaly(True) should have been called when monitor detects anomalies. "
            f"Calls recorded: {anomaly_calls}"
        )


# ===========================================================================
# Test 11: Rhythm responds to dreaming
# ===========================================================================


class TestRhythmRespondsToDreaming:
    """When dream cycle triggers, rhythm.set_dreaming(True) is called before
    and set_dreaming(False) after."""

    @pytest.mark.asyncio
    async def test_heartbeat_rhythm_responds_to_dreaming(self, tmp_path: Path):
        """set_dreaming(True) is called before dream, False after."""
        engine = _make_engine(tmp_path)
        cfg = engine.config

        # Spy on AdaptiveRhythm.set_dreaming.
        rhythm = AdaptiveRhythm(base_seconds=0.01)
        original_set_dreaming = rhythm.set_dreaming
        dreaming_calls: list[bool] = []

        def tracking_set_dreaming(value: bool) -> None:
            dreaming_calls.append(value)
            original_set_dreaming(value)

        rhythm.set_dreaming = tracking_set_dreaming  # type: ignore[assignment]

        # Create a mock dream cycle that claims it should dream.
        mock_dream = MagicMock()
        mock_dream.should_dream.return_value = True
        mock_dream.run = AsyncMock(return_value=None)

        hb = Heartbeat(engine, cfg, dream_cycle=mock_dream, rhythm=rhythm)
        hb.start()
        # Let it tick enough to trigger the dream path.
        await asyncio.sleep(0.08)
        await hb.stop()

        # Dream cycle should have been invoked.
        mock_dream.run.assert_awaited(
        ), "Dream cycle's run() should have been awaited"

        # set_dreaming should have been called with True and then False.
        assert True in dreaming_calls, (
            "set_dreaming(True) must be called before the dream cycle"
        )
        assert False in dreaming_calls, (
            "set_dreaming(False) must be called after the dream cycle"
        )

        # Verify ordering: True appears before False.
        first_true = dreaming_calls.index(True)
        # Find the False that comes after the first True.
        found_false_after_true = any(
            dreaming_calls[i] is False
            for i in range(first_true + 1, len(dreaming_calls))
        )
        assert found_false_after_true, (
            "set_dreaming(False) must be called AFTER set_dreaming(True). "
            f"Call sequence: {dreaming_calls}"
        )
