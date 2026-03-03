"""Tests for heartbeat vitals — VitalSigns and measure_vitals."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from luna.heartbeat.vitals import VitalSigns, measure_vitals, _default_vitals


def _make_engine(psi=None, psi0=None, phi_iit=0.7, quality=0.6, phase="SOLID"):
    """Create a mock engine for vitals measurement."""
    engine = MagicMock()

    cs = MagicMock()
    cs.psi = np.array(psi or [0.25, 0.35, 0.25, 0.15])
    cs.psi0 = np.array(psi0 or [0.25, 0.35, 0.25, 0.15])
    cs.compute_phi_iit.return_value = phi_iit
    engine.consciousness = cs

    engine.phi_scorer.score.return_value = quality
    engine.health_phase_machine.phase = phase
    engine._idle_steps = 42

    return engine


class TestVitalSigns:
    """Tests for the VitalSigns frozen dataclass."""

    def test_frozen(self):
        """VitalSigns is immutable."""
        vitals = _default_vitals()
        with pytest.raises(AttributeError):
            vitals.phi_iit = 1.0  # type: ignore[misc]

    def test_default_vitals(self):
        """Default vitals have sensible initial values."""
        vitals = _default_vitals()
        assert vitals.psi == (0.25, 0.25, 0.25, 0.25)
        assert vitals.identity_drift == 0.0
        assert vitals.overall_vitality == 0.0
        assert vitals.health_phase == "BROKEN"


class TestMeasureVitals:
    """Tests for the measure_vitals function."""

    def test_basic_measurement(self):
        """measure_vitals produces valid VitalSigns."""
        engine = _make_engine()
        vitals = measure_vitals(engine, uptime_seconds=100.0)

        assert isinstance(vitals, VitalSigns)
        assert vitals.idle_steps == 42
        assert vitals.uptime_seconds == 100.0
        assert vitals.phi_iit == 0.7
        assert vitals.quality_score == 0.6
        assert vitals.health_phase == "SOLID"

    def test_identity_preserved(self):
        """Identity is preserved when argmax(psi) == argmax(psi0)."""
        engine = _make_engine(
            psi=[0.15, 0.50, 0.20, 0.15],
            psi0=[0.15, 0.45, 0.25, 0.15],
        )
        vitals = measure_vitals(engine)
        assert vitals.identity_preserved is True
        assert vitals.dominant_component == "Reflexion"

    def test_identity_drifted(self):
        """Identity drift detected when dominant shifts."""
        engine = _make_engine(
            psi=[0.50, 0.20, 0.15, 0.15],
            psi0=[0.15, 0.45, 0.25, 0.15],
        )
        vitals = measure_vitals(engine)
        assert vitals.identity_preserved is False
        assert vitals.dominant_component == "Perception"

    def test_identity_drift_value(self):
        """Identity drift is L2 norm of (psi - psi0)."""
        engine = _make_engine(
            psi=[0.25, 0.35, 0.25, 0.15],
            psi0=[0.25, 0.35, 0.25, 0.15],
        )
        vitals = measure_vitals(engine)
        assert abs(vitals.identity_drift) < 1e-10

    def test_emotional_state_reflexion(self):
        """Reflexion dominant -> contemplatif."""
        engine = _make_engine(psi=[0.15, 0.50, 0.20, 0.15])
        vitals = measure_vitals(engine)
        assert vitals.emotional_state == "contemplatif"

    def test_emotional_state_expression(self):
        """Expression dominant -> creatif."""
        engine = _make_engine(psi=[0.10, 0.15, 0.20, 0.55])
        vitals = measure_vitals(engine)
        assert vitals.emotional_state == "creatif"

    def test_overall_vitality_range(self):
        """Overall vitality is in [0, 1]."""
        engine = _make_engine()
        vitals = measure_vitals(engine)
        assert 0.0 <= vitals.overall_vitality <= 1.0

    def test_uninitialized_engine(self):
        """measure_vitals handles uninitialized engine."""
        engine = MagicMock()
        engine.consciousness = None
        vitals = measure_vitals(engine)
        assert vitals.health_phase == "BROKEN"
        assert vitals.overall_vitality == 0.0

    def test_psi_tuple_format(self):
        """Psi values are stored as tuples of floats."""
        engine = _make_engine()
        vitals = measure_vitals(engine)
        assert isinstance(vitals.psi, tuple)
        assert len(vitals.psi) == 4
        assert all(isinstance(x, float) for x in vitals.psi)
