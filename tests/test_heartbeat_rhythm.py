"""Tests for heartbeat rhythm — Phi-modulated intervals."""

from __future__ import annotations

import pytest

from luna_common.constants import PHI, PHI2
from luna.heartbeat.rhythm import AdaptiveRhythm, HeartbeatRhythm


class TestHeartbeatRhythm:
    """Tests for HeartbeatRhythm frozen dataclass."""

    def test_from_base(self):
        """from_base creates correct Phi-derived intervals."""
        rhythm = HeartbeatRhythm.from_base(1.0)
        assert abs(rhythm.base - 1.0) < 1e-10
        assert abs(rhythm.primary - PHI) < 1e-10
        assert abs(rhythm.deep - PHI2) < 1e-10
        assert abs(rhythm.sleep - PHI ** 3) < 1e-10
        assert abs(rhythm.alert - 0.5) < 1e-10

    def test_from_base_scaling(self):
        """Intervals scale linearly with base."""
        rhythm = HeartbeatRhythm.from_base(2.0)
        assert abs(rhythm.primary - 2.0 * PHI) < 1e-10
        assert abs(rhythm.alert - 1.0) < 1e-10

    def test_frozen(self):
        """HeartbeatRhythm is immutable."""
        rhythm = HeartbeatRhythm.from_base(1.0)
        with pytest.raises(AttributeError):
            rhythm.base = 5.0  # type: ignore[misc]

    def test_interval_ordering(self):
        """Intervals are ordered: alert < base < primary < deep < sleep."""
        rhythm = HeartbeatRhythm.from_base(1.0)
        assert rhythm.alert < rhythm.base < rhythm.primary < rhythm.deep < rhythm.sleep


class TestAdaptiveRhythm:
    """Tests for AdaptiveRhythm."""

    def test_default_functional(self):
        """FUNCTIONAL phase uses primary interval."""
        ar = AdaptiveRhythm(base_seconds=1.0)
        interval = ar.current_interval("FUNCTIONAL")
        assert abs(interval - PHI) < 1e-10

    def test_broken_phase_fast(self):
        """BROKEN phase uses base interval (fast monitoring)."""
        ar = AdaptiveRhythm(base_seconds=1.0)
        interval = ar.current_interval("BROKEN")
        assert abs(interval - 1.0) < 1e-10

    def test_solid_phase_relaxed(self):
        """SOLID phase uses deep interval (relaxed)."""
        ar = AdaptiveRhythm(base_seconds=1.0)
        interval = ar.current_interval("SOLID")
        assert abs(interval - PHI2) < 1e-10

    def test_excellent_phase_relaxed(self):
        """EXCELLENT phase uses deep interval."""
        ar = AdaptiveRhythm(base_seconds=1.0)
        interval = ar.current_interval("EXCELLENT")
        assert abs(interval - PHI2) < 1e-10

    def test_dream_mode(self):
        """Dreaming overrides to sleep interval."""
        ar = AdaptiveRhythm(base_seconds=1.0)
        ar.set_dreaming(True)
        interval = ar.current_interval("SOLID")
        assert abs(interval - PHI ** 3) < 1e-10

    def test_exit_dream_mode(self):
        """Exiting dream restores phase-based interval."""
        ar = AdaptiveRhythm(base_seconds=1.0)
        ar.set_dreaming(True)
        ar.set_dreaming(False)
        interval = ar.current_interval("SOLID")
        assert abs(interval - PHI2) < 1e-10

    def test_anomaly_priority(self):
        """Anomaly overrides all other modes (highest priority)."""
        ar = AdaptiveRhythm(base_seconds=1.0)
        ar.set_dreaming(True)
        ar.set_anomaly(True)
        interval = ar.current_interval("EXCELLENT")
        assert abs(interval - 0.5) < 1e-10

    def test_clear_anomaly(self):
        """Clearing anomaly restores normal interval."""
        ar = AdaptiveRhythm(base_seconds=1.0)
        ar.set_anomaly(True)
        ar.set_anomaly(False)
        interval = ar.current_interval("FUNCTIONAL")
        assert abs(interval - PHI) < 1e-10

    def test_rhythm_property(self):
        """rhythm property exposes the HeartbeatRhythm."""
        ar = AdaptiveRhythm(base_seconds=2.0)
        assert isinstance(ar.rhythm, HeartbeatRhythm)
        assert ar.rhythm.base == 2.0
