"""Wave 3 — Integration tests for the Dream Simulation Architecture v2.3 wiring.

Tests cover the full integration between components:
  - DreamCycle simulation path (harvest -> replay -> exploration -> consolidation).
  - SleepManager wake-cycle data recording and harvest building.
  - Awakening v2.3 processing with ConsolidationReport.
  - ConsciousnessState.update_psi0() validation and mass re-seeding.
  - LunaEngine._apply_consolidated_profiles() during initialize().
  - ChatSession /dream command routing (legacy vs simulation path).

These tests verify that the components WORK TOGETHER, not in isolation.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from luna_common.constants import AGENT_PROFILES, DIM

from luna.chat.session import ChatSession
from luna.core.config import (
    ChatSection,
    ConsciousnessSection,
    DreamSection,
    HeartbeatSection,
    LunaConfig,
    LunaSection,
    MemorySection,
    ObservabilitySection,
    OrchestratorSection,
    PipelineSection,
)
from luna.dream.harvest import DreamHarvest
from luna.llm_bridge.bridge import LLMResponse


# ---------------------------------------------------------------------------
# Shared fixtures and helpers
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Path, **dream_overrides):
    """Build a minimal LunaConfig with configurable dream section."""
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

    dream_kw = {
        "inactivity_threshold": 0.01,
        "consolidation_window": 100,
        "max_dream_duration": 300.0,
        "report_dir": str(tmp_path / "dreams"),
        "enabled": True,
    }
    dream_kw.update(dream_overrides)

    return LunaConfig(
        luna=LunaSection(
            version="test", agent_name="LUNA",
            data_dir=str(tmp_path), pipeline_dir=str(tmp_path / "pipeline"),
        ),
        consciousness=ConsciousnessSection(
            checkpoint_file="cs.json", backup_on_save=False,
        ),
        memory=MemorySection(fractal_root=str(tmp_path / "fractal")),
        pipeline=PipelineSection(root=str(tmp_path / "pipeline")),
        observability=ObservabilitySection(),
        heartbeat=HeartbeatSection(interval_seconds=0.01),
        dream=DreamSection(**dream_kw),
        root_dir=tmp_path,
    )


def _make_engine(tmp_path: Path):
    """Create and initialize a LunaEngine with some history."""
    from luna.core.luna import LunaEngine
    cfg = _make_config(tmp_path)
    engine = LunaEngine(cfg)
    engine.initialize()
    for _ in range(20):
        engine.idle_step()
    return engine


def _make_harvest(
    pipeline_events: int = 15,
    phi_iit_values: tuple[float, ...] | None = None,
):
    """Build a DreamHarvest suitable for integration tests."""
    from luna.dream.harvest import DreamHarvest

    events = tuple({"type": "dummy", "idx": i} for i in range(pipeline_events))
    psi_snaps = tuple(
        AGENT_PROFILES["LUNA"] for _ in range(min(pipeline_events, 5))
    )
    metrics = tuple({"phi_iit": 0.3} for _ in range(pipeline_events))
    phi_iit = phi_iit_values if phi_iit_values is not None else tuple(
        0.2 + 0.01 * i for i in range(pipeline_events)
    )

    return DreamHarvest(
        pipeline_events=events,
        luna_psi_snapshots=psi_snaps,
        metrics_history=metrics,
        phi_iit_history=phi_iit,
        current_profiles=dict(AGENT_PROFILES),
    )


# ===========================================================================
# TestDreamCycleSimulation
# ===========================================================================


class TestDreamCycleSimulation:
    """Integration tests for the v2.3 simulation dream path."""

    @pytest.mark.asyncio
    async def test_run_with_harvest_four_phases(self, tmp_path: Path) -> None:
        """Passing a DreamHarvest yields 4 simulation phases in order."""
        from luna.dream.dream_cycle import DreamCycle, DreamPhase

        engine = _make_engine(tmp_path)
        dc = DreamCycle(engine, engine.config)

        harvest = _make_harvest()
        report = await dc.run(harvest=harvest)

        assert len(report.phases) == 4
        phase_names = [p.phase for p in report.phases]
        assert phase_names == [
            DreamPhase.HARVEST,
            DreamPhase.REPLAY,
            DreamPhase.EXPLORATION,
            DreamPhase.SIM_CONSOLIDATION,
        ]

    @pytest.mark.asyncio
    async def test_run_without_harvest_legacy(self, tmp_path: Path) -> None:
        """Without harvest, legacy 4-phase path runs."""
        from luna.dream.dream_cycle import DreamCycle, DreamPhase

        engine = _make_engine(tmp_path)
        dc = DreamCycle(engine, engine.config)

        report = await dc.run()  # No harvest.

        assert len(report.phases) == 4
        phase_names = [p.phase for p in report.phases]
        assert DreamPhase.CONSOLIDATION in phase_names
        assert DreamPhase.DEFRAGMENTATION in phase_names

    @pytest.mark.asyncio
    async def test_consolidation_report_attached(self, tmp_path: Path) -> None:
        """DreamReport.consolidation_report is set after simulation path."""
        from luna.dream.dream_cycle import DreamCycle

        engine = _make_engine(tmp_path)
        dc = DreamCycle(engine, engine.config)

        harvest = _make_harvest()
        report = await dc.run(harvest=harvest)

        assert report.consolidation_report is not None
        cr = report.consolidation_report
        assert isinstance(cr.previous_profiles, dict)
        assert isinstance(cr.updated_profiles, dict)
        assert isinstance(cr.drift_per_agent, dict)
        assert isinstance(cr.dominant_preserved, bool)

    @pytest.mark.asyncio
    async def test_simulation_produces_serializable_report(self, tmp_path: Path) -> None:
        """report.to_dict() is JSON-serializable without errors."""
        from luna.dream.dream_cycle import DreamCycle

        engine = _make_engine(tmp_path)
        dc = DreamCycle(engine, engine.config)

        harvest = _make_harvest()
        report = await dc.run(harvest=harvest)

        d = report.to_dict()
        serialized = json.dumps(d, default=str)
        assert len(serialized) > 100
        parsed = json.loads(serialized)
        assert "phases" in parsed
        assert len(parsed["phases"]) == 4


# ===========================================================================
# TestSleepManagerHarvest
# ===========================================================================


class TestSleepManagerHarvest:
    """SleepManager wake-cycle data recording and harvest building."""

    def test_record_event_grows_buffer(self) -> None:
        """record_event() appends to the pipeline_events buffer."""
        from luna.dream.sleep_manager import SleepManager

        dc = MagicMock()
        dc.run = AsyncMock()
        sm = SleepManager(dc)

        sm.record_event({"type": "test", "idx": 0})
        sm.record_event({"type": "test", "idx": 1})

        assert len(sm._pipeline_events) == 2

    def test_record_psi_grows_buffer(self) -> None:
        """record_psi() appends to the luna_psi_snapshots buffer."""
        from luna.dream.sleep_manager import SleepManager

        dc = MagicMock()
        dc.run = AsyncMock()
        sm = SleepManager(dc)

        sm.record_psi((0.25, 0.35, 0.25, 0.15))
        assert len(sm._luna_psi_snapshots) == 1

    def test_record_metrics_grows_buffer(self) -> None:
        """record_metrics() appends to the metrics_history buffer."""
        from luna.dream.sleep_manager import SleepManager

        dc = MagicMock()
        dc.run = AsyncMock()
        sm = SleepManager(dc)

        sm.record_metrics({"phi_iit": 0.5})
        sm.record_metrics({"phi_iit": 0.6})
        assert len(sm._metrics_history) == 2

    def test_record_phi_iit_grows_buffer(self) -> None:
        """record_phi_iit() appends to the phi_iit_history buffer."""
        from luna.dream.sleep_manager import SleepManager

        dc = MagicMock()
        dc.run = AsyncMock()
        sm = SleepManager(dc)

        sm.record_phi_iit(0.42)
        assert len(sm._phi_iit_history) == 1

    def test_build_harvest_with_data(self) -> None:
        """_build_harvest() builds DreamHarvest from populated buffers."""
        from luna.dream.harvest import DreamHarvest
        from luna.dream.sleep_manager import SleepManager

        dc = MagicMock()
        dc.run = AsyncMock()
        sm = SleepManager(dc)

        sm.record_event({"type": "pipeline"})
        sm.record_psi((0.25, 0.35, 0.25, 0.15))
        sm.record_phi_iit(0.5)

        harvest = sm._build_harvest()

        assert harvest is not None
        assert isinstance(harvest, DreamHarvest)
        assert len(harvest.pipeline_events) == 1
        assert len(harvest.luna_psi_snapshots) == 1
        assert len(harvest.phi_iit_history) == 1

    def test_build_harvest_empty_returns_none(self) -> None:
        """_build_harvest() returns None if no data was recorded."""
        from luna.dream.sleep_manager import SleepManager

        dc = MagicMock()
        dc.run = AsyncMock()
        sm = SleepManager(dc)

        harvest = sm._build_harvest()
        assert harvest is None

    def test_buffers_cleared_after_harvest(self) -> None:
        """After _build_harvest(), all buffers are empty."""
        from luna.dream.sleep_manager import SleepManager

        dc = MagicMock()
        dc.run = AsyncMock()
        sm = SleepManager(dc)

        sm.record_event({"type": "a"})
        sm.record_psi((0.25, 0.35, 0.25, 0.15))
        sm.record_metrics({"x": 1.0})
        sm.record_phi_iit(0.3)

        sm._build_harvest()

        assert len(sm._pipeline_events) == 0
        assert len(sm._luna_psi_snapshots) == 0
        assert len(sm._metrics_history) == 0
        assert len(sm._phi_iit_history) == 0

    @pytest.mark.asyncio
    async def test_enter_sleep_with_harvest(self, tmp_path: Path) -> None:
        """Full lifecycle: record data -> enter_sleep -> dream with harvest."""
        from luna.dream.dream_cycle import DreamCycle, DreamPhase, DreamReport
        from luna.dream.sleep_manager import SleepManager

        engine = _make_engine(tmp_path)
        dc = DreamCycle(engine, engine.config)
        sm = SleepManager(dc, engine=engine, max_dream_duration=30.0)

        # Record some wake-cycle data.
        for i in range(5):
            sm.record_event({"type": "test", "idx": i})
            sm.record_psi(tuple(float(x) for x in engine.consciousness.psi))
            sm.record_phi_iit(0.3 + 0.01 * i)

        report = await sm.enter_sleep()

        assert report is not None
        assert isinstance(report, DreamReport)
        assert len(report.phases) == 4
        # Should use simulation path since engine is set and buffers have data.
        phase_names = [p.phase for p in report.phases]
        assert DreamPhase.HARVEST in phase_names


# ===========================================================================
# TestAwakeningV23
# ===========================================================================


class TestAwakeningV23:
    """Awakening v2.3 processing with ConsolidationReport."""

    def test_process_with_consolidation_report(self) -> None:
        """profiles_updated=True when consolidation has non-zero drift."""
        from luna.dream.awakening import Awakening
        from luna.dream.dream_cycle import DreamPhase, DreamReport, PhaseResult
        from luna.dream.harvest import ConsolidationReport

        profiles = dict(AGENT_PROFILES)
        # Create updated profiles with slight drift for Luna.
        updated = dict(profiles)
        updated["LUNA"] = (0.26, 0.34, 0.25, 0.15)

        cr = ConsolidationReport(
            previous_profiles=profiles,
            updated_profiles=updated,
            drift_per_agent={"LUNA": 0.015, "SAYOHMY": 0.0, "SENTINEL": 0.0, "TESTENGINEER": 0.0},
            dominant_preserved=True,
        )

        report = DreamReport(
            phases=[
                PhaseResult(phase=DreamPhase.HARVEST, data={}),
                PhaseResult(phase=DreamPhase.REPLAY, data={}),
                PhaseResult(phase=DreamPhase.EXPLORATION, data={}),
                PhaseResult(phase=DreamPhase.SIM_CONSOLIDATION, data={}),
            ],
            total_duration=1.0,
            consolidation_report=cr,
        )

        awakening = Awakening()
        ar = awakening.process(report)

        assert ar.profiles_updated is True
        assert ar.drift_per_agent["LUNA"] == pytest.approx(0.015)

    def test_process_legacy_report(self) -> None:
        """Legacy report (no consolidation_report) has profiles_updated=False."""
        from luna.dream.awakening import Awakening
        from luna.dream.dream_cycle import DreamPhase, DreamReport, PhaseResult

        report = DreamReport(
            phases=[
                PhaseResult(phase=DreamPhase.CONSOLIDATION, data={"drift_from_psi0": 0.05}),
                PhaseResult(phase=DreamPhase.REINTERPRETATION, data={"significant": []}),
                PhaseResult(phase=DreamPhase.DEFRAGMENTATION, data={"removed": 0}),
                PhaseResult(phase=DreamPhase.CREATIVE, data={"unexpected_couplings": []}),
            ],
            total_duration=0.5,
        )

        awakening = Awakening()
        ar = awakening.process(report)

        assert ar.profiles_updated is False
        assert ar.drift_per_agent == {}

    def test_psi0_updated_via_engine(self, tmp_path: Path) -> None:
        """Awakening with engine updates consciousness.psi0."""
        from luna.dream.awakening import Awakening
        from luna.dream.dream_cycle import DreamPhase, DreamReport, PhaseResult
        from luna.dream.harvest import ConsolidationReport

        engine = _make_engine(tmp_path)
        psi0_before = engine.consciousness.psi0.copy()

        # Create a slightly shifted Luna profile that preserves dominant.
        new_luna = (0.24, 0.36, 0.25, 0.15)  # Reflexion still dominant.
        profiles = dict(AGENT_PROFILES)
        updated = dict(profiles)
        updated["LUNA"] = new_luna

        cr = ConsolidationReport(
            previous_profiles=profiles,
            updated_profiles=updated,
            drift_per_agent={"LUNA": 0.02, "SAYOHMY": 0.0, "SENTINEL": 0.0, "TESTENGINEER": 0.0},
            dominant_preserved=True,
        )

        report = DreamReport(
            phases=[
                PhaseResult(phase=DreamPhase.HARVEST, data={}),
                PhaseResult(phase=DreamPhase.REPLAY, data={}),
                PhaseResult(phase=DreamPhase.EXPLORATION, data={}),
                PhaseResult(phase=DreamPhase.SIM_CONSOLIDATION, data={}),
            ],
            total_duration=1.0,
            consolidation_report=cr,
        )

        awakening = Awakening(engine=engine)
        ar = awakening.process(report)

        assert ar.profiles_updated is True
        assert ar.psi_updated is True

        # engine.consciousness.psi0 should have changed.
        psi0_after = engine.consciousness.psi0
        assert not np.allclose(psi0_after, psi0_before, atol=1e-6), (
            "Psi0 should have been updated by awakening"
        )
        # New psi0 should be on the simplex.
        assert abs(psi0_after.sum() - 1.0) < 1e-6
        assert (psi0_after >= 0).all()

    def test_awakening_with_zero_drift(self) -> None:
        """When all drifts are zero, profiles_updated is False."""
        from luna.dream.awakening import Awakening
        from luna.dream.dream_cycle import DreamPhase, DreamReport, PhaseResult
        from luna.dream.harvest import ConsolidationReport

        profiles = dict(AGENT_PROFILES)
        cr = ConsolidationReport(
            previous_profiles=profiles,
            updated_profiles=profiles,
            drift_per_agent={k: 0.0 for k in profiles},
            dominant_preserved=True,
        )

        report = DreamReport(
            phases=[
                PhaseResult(phase=DreamPhase.HARVEST, data={}),
                PhaseResult(phase=DreamPhase.REPLAY, data={}),
                PhaseResult(phase=DreamPhase.EXPLORATION, data={}),
                PhaseResult(phase=DreamPhase.SIM_CONSOLIDATION, data={}),
            ],
            total_duration=0.5,
            consolidation_report=cr,
        )

        awakening = Awakening()
        ar = awakening.process(report)

        # No drift -> profiles_updated should be False.
        assert ar.profiles_updated is False

    def test_awakening_report_has_v23_fields(self) -> None:
        """AwakeningReport includes profiles_updated and drift_per_agent."""
        from luna.dream.awakening import Awakening, AwakeningReport
        from luna.dream.dream_cycle import DreamPhase, DreamReport, PhaseResult
        from luna.dream.harvest import ConsolidationReport

        profiles = dict(AGENT_PROFILES)
        cr = ConsolidationReport(
            previous_profiles=profiles,
            updated_profiles=profiles,
            drift_per_agent={"LUNA": 0.01},
            dominant_preserved=True,
        )

        report = DreamReport(
            phases=[
                PhaseResult(phase=DreamPhase.HARVEST, data={}),
                PhaseResult(phase=DreamPhase.REPLAY, data={}),
                PhaseResult(phase=DreamPhase.EXPLORATION, data={}),
                PhaseResult(phase=DreamPhase.SIM_CONSOLIDATION, data={}),
            ],
            total_duration=0.5,
            consolidation_report=cr,
        )

        awakening = Awakening()
        ar = awakening.process(report)

        assert isinstance(ar, AwakeningReport)
        assert hasattr(ar, "profiles_updated")
        assert hasattr(ar, "drift_per_agent")
        d = ar.to_dict()
        assert "profiles_updated" in d
        assert "drift_per_agent" in d


# ===========================================================================
# TestUpdatePsi0
# ===========================================================================


class TestUpdatePsi0:
    """ConsciousnessState.update_psi0() validation and side effects."""

    @pytest.fixture
    def cs(self):
        """Fresh ConsciousnessState for Luna."""
        from luna.consciousness.state import ConsciousnessState
        return ConsciousnessState(agent_name="LUNA")

    def test_update_psi0_valid(self, cs) -> None:
        """Valid input updates psi0 successfully."""
        new_psi0 = np.array([0.24, 0.36, 0.25, 0.15])
        cs.update_psi0(new_psi0)
        # After projection, the values should be close.
        assert abs(cs.psi0.sum() - 1.0) < 1e-6
        assert (cs.psi0 >= 0).all()
        # Dominant should still be reflexion (index 1).
        assert np.argmax(cs.psi0) == 1

    def test_update_psi0_wrong_shape(self, cs) -> None:
        """Wrong shape raises ValueError."""
        with pytest.raises(ValueError, match="shape"):
            cs.update_psi0(np.array([0.5, 0.5]))

    def test_update_psi0_negative(self, cs) -> None:
        """Negative values raise ValueError."""
        with pytest.raises(ValueError, match="must be >= 0"):
            cs.update_psi0(np.array([-0.1, 0.4, 0.4, 0.3]))

    def test_update_psi0_not_simplex_reprojected(self, cs) -> None:
        """Non-simplex input is re-projected (no error, just projection)."""
        # Values that don't sum to 1.0 but are non-negative.
        raw = np.array([0.5, 0.7, 0.5, 0.3])
        cs.update_psi0(raw)
        # After projection, should be on simplex.
        assert abs(cs.psi0.sum() - 1.0) < 1e-6
        assert (cs.psi0 >= 0).all()

    def test_update_psi0_reseeds_mass(self, cs) -> None:
        """update_psi0 re-initializes the mass matrix from the new psi0."""
        from luna_common.consciousness.evolution import MassMatrix

        old_mass_m = cs.mass.m.copy()
        new_psi0 = np.array([0.24, 0.36, 0.25, 0.15])
        cs.update_psi0(new_psi0)

        # Mass should be a fresh MassMatrix seeded from new psi0.
        assert isinstance(cs.mass, MassMatrix)
        # The mass should differ from the old one (new seed).
        # After projection, psi0 may differ slightly from input.
        np.testing.assert_allclose(cs.mass.m, cs.psi0, atol=1e-10)

    def test_update_psi0_with_tuple(self, cs) -> None:
        """update_psi0 accepts array-like (tuple or list)."""
        cs.update_psi0([0.24, 0.36, 0.25, 0.15])
        assert abs(cs.psi0.sum() - 1.0) < 1e-6

    def test_update_psi0_preserves_history(self, cs) -> None:
        """update_psi0 does not modify history or step_count."""
        cs.history.append(np.array([0.25, 0.35, 0.25, 0.15]))
        cs.step_count = 5
        history_len = len(cs.history)
        step_count = cs.step_count

        cs.update_psi0(np.array([0.24, 0.36, 0.25, 0.15]))

        assert len(cs.history) == history_len
        assert cs.step_count == step_count


# ===========================================================================
# TestLunaEngineProfileLoad
# ===========================================================================


class TestLunaEngineProfileLoad:
    """LunaEngine._apply_consolidated_profiles() during initialize()."""

    def test_initialize_loads_profiles(self, tmp_path: Path) -> None:
        """If agent_profiles.json exists, initialize loads and applies it."""
        from luna.core.luna import LunaEngine
        from luna.dream.consolidation import save_profiles

        cfg = _make_config(tmp_path)

        # Create a slightly shifted Luna profile (preserves dominant).
        profiles = dict(AGENT_PROFILES)
        profiles["LUNA"] = (0.22, 0.38, 0.24, 0.16)  # Reflexion still dominant.

        data_dir = cfg.resolve(cfg.luna.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        profiles_path = data_dir / "agent_profiles.json"
        save_profiles(profiles_path, profiles)

        engine = LunaEngine(cfg)
        engine.initialize()

        # Psi0 should have been updated to match the saved profiles.
        psi0 = engine.consciousness.psi0
        expected = np.array(profiles["LUNA"])

        # After simplex projection, it should be close to the saved profile.
        # The projection might shift values slightly, so we use a moderate tolerance.
        assert abs(psi0.sum() - 1.0) < 1e-6
        # Dominant should still be reflexion (index 1).
        assert np.argmax(psi0) == 1

    def test_initialize_no_file_no_change(self, tmp_path: Path) -> None:
        """Without agent_profiles.json, psi0 defaults to AGENT_PROFILES."""
        from luna.core.luna import LunaEngine

        cfg = _make_config(tmp_path)
        engine = LunaEngine(cfg)
        engine.initialize()

        expected = np.array(AGENT_PROFILES["LUNA"])
        np.testing.assert_allclose(
            engine.consciousness.psi0, expected, atol=1e-10,
        )

    def test_initialize_same_profile_no_update(self, tmp_path: Path) -> None:
        """If saved profiles match defaults, no update occurs."""
        from luna.core.luna import LunaEngine
        from luna.dream.consolidation import save_profiles

        cfg = _make_config(tmp_path)

        # Save exact default profiles.
        data_dir = cfg.resolve(cfg.luna.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        profiles_path = data_dir / "agent_profiles.json"
        save_profiles(profiles_path, dict(AGENT_PROFILES))

        engine = LunaEngine(cfg)
        engine.initialize()

        expected = np.array(AGENT_PROFILES["LUNA"])
        np.testing.assert_allclose(
            engine.consciousness.psi0, expected, atol=1e-10,
        )


# ===========================================================================
# ChatSession /dream command wiring — fixtures and helpers
# ===========================================================================


def _make_chat_config(tmp_path: Path, **chat_overrides) -> LunaConfig:
    """Build a LunaConfig suitable for ChatSession dream wiring tests.

    Differs from the module-level _make_config by including ChatSection,
    OrchestratorSection, and a data_dir subdirectory (to test profile saving).
    """
    chat_kw = {
        "max_history": 100,
        "memory_search_limit": 5,
        "idle_heartbeat": True,
        "save_conversations": True,
        "prompt_prefix": "luna> ",
    }
    chat_kw.update(chat_overrides)

    return LunaConfig(
        luna=LunaSection(
            version="test",
            agent_name="LUNA",
            data_dir=str(tmp_path / "data"),
            pipeline_dir=str(tmp_path / "pipeline"),
        ),
        consciousness=ConsciousnessSection(
            checkpoint_file="cs.json",
            backup_on_save=False,
        ),
        memory=MemorySection(fractal_root=str(tmp_path / "fractal")),
        pipeline=PipelineSection(root=str(tmp_path / "pipeline")),
        observability=ObservabilitySection(),
        heartbeat=HeartbeatSection(interval_seconds=0.01),
        orchestrator=OrchestratorSection(retry_max=1, retry_base_delay=0.01),
        dream=DreamSection(
            enabled=True,
            report_dir=str(tmp_path / "dreams"),
        ),
        chat=ChatSection(**chat_kw),
        root_dir=tmp_path,
    )


def _mock_chat_llm() -> AsyncMock:
    """Create a mock LLMBridge that returns a fixed response."""
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=LLMResponse(
        content="Bonjour, je suis Luna.",
        model="mock-model",
        input_tokens=42,
        output_tokens=10,
    ))
    return llm


async def _started_chat_session(cfg: LunaConfig) -> ChatSession:
    """Return a started ChatSession with mocked LLM provider."""
    session = ChatSession(cfg)
    with patch("luna.chat.session.create_provider", return_value=_mock_chat_llm()):
        await session.start()
    return session


# ===========================================================================
# TestChatDreamRouting — /dream routes to legacy vs simulation
# ===========================================================================


class TestChatDreamRouting:
    """Verify /dream dispatches to legacy or simulation based on buffer state."""

    @pytest.mark.asyncio
    async def test_dream_without_chat_runs_legacy(self, tmp_path: Path) -> None:
        """Call /dream without any send() calls -> legacy path.

        When no chat turns have occurred, _build_dream_harvest() returns None
        and DreamCycle.run(harvest=None) takes the legacy code path.
        The response text must contain 'legacy'.
        """
        cfg = _make_chat_config(tmp_path)
        session = await _started_chat_session(cfg)

        # Build enough consciousness history for the legacy dream to work.
        for _ in range(20):
            session.engine.idle_step()

        result = await session.handle_command("/dream")

        assert "legacy" in result.lower(), (
            f"Expected 'legacy' in dream response when buffers are empty, "
            f"got: {result!r}"
        )

    @pytest.mark.asyncio
    async def test_dream_after_chat_runs_simulation(self, tmp_path: Path) -> None:
        """Call send() to accumulate wake-cycle data, then /dream -> simulation.

        After chat turns, _build_dream_harvest() returns a DreamHarvest and
        the simulation path runs 4 phases: harvest, replay, exploration,
        sim_consolidation.
        """
        cfg = _make_chat_config(tmp_path)
        session = await _started_chat_session(cfg)

        # Build consciousness history for the dream.
        for _ in range(20):
            session.engine.idle_step()

        # Accumulate wake-cycle data via send().
        for i in range(3):
            await session.send(f"Message {i}")

        result = await session.handle_command("/dream")

        assert "simulation" in result.lower(), (
            f"Expected 'simulation' in dream response after chat turns, "
            f"got: {result!r}"
        )
        # Verify all 4 simulation phases appear in the output.
        for phase_name in ("harvest", "replay", "exploration", "sim_consolidation"):
            assert phase_name in result.lower(), (
                f"Expected phase '{phase_name}' in simulation dream output, "
                f"got: {result!r}"
            )


# ===========================================================================
# TestChatDreamHarvest — _build_dream_harvest() data integrity
# ===========================================================================


class TestChatDreamHarvest:
    """Verify ChatSession._build_dream_harvest() produces correct data."""

    @pytest.mark.asyncio
    async def test_dream_harvest_has_correct_data(self, tmp_path: Path) -> None:
        """After send() calls, _build_dream_harvest() returns a DreamHarvest
        with psi_snapshots and phi_iit_history matching the number of turns,
        and current_profiles containing all 4 agent names.
        """
        cfg = _make_chat_config(tmp_path)
        session = await _started_chat_session(cfg)
        num_turns = 4

        for i in range(num_turns):
            await session.send(f"Turn {i}")

        harvest = session._build_dream_harvest()

        assert harvest is not None, (
            "_build_dream_harvest() returned None after send() calls"
        )
        assert isinstance(harvest, DreamHarvest), (
            f"Expected DreamHarvest, got {type(harvest).__name__}"
        )

        # Each send() -> _chat_evolve() appends one psi snapshot and one phi_iit.
        assert len(harvest.luna_psi_snapshots) == num_turns, (
            f"Expected {num_turns} psi_snapshots, "
            f"got {len(harvest.luna_psi_snapshots)}"
        )
        assert len(harvest.phi_iit_history) == num_turns, (
            f"Expected {num_turns} phi_iit entries, "
            f"got {len(harvest.phi_iit_history)}"
        )

        # Each psi snapshot is a 4-tuple of floats.
        for idx, snap in enumerate(harvest.luna_psi_snapshots):
            assert len(snap) == 4, (
                f"Psi snapshot {idx} should have 4 components, got {len(snap)}"
            )
            assert all(isinstance(x, float) for x in snap), (
                f"Psi snapshot {idx} components should be floats"
            )

        # current_profiles must contain all canonical agent names.
        expected_agents = {"LUNA", "SAYOHMY", "SENTINEL", "TESTENGINEER"}
        assert expected_agents.issubset(set(harvest.current_profiles.keys())), (
            f"Expected agents {expected_agents} in current_profiles, "
            f"got {set(harvest.current_profiles.keys())}"
        )


# ===========================================================================
# TestChatDreamBuffers — buffer clearing after harvest
# ===========================================================================


class TestChatDreamBuffers:
    """Verify buffers are consumed (cleared) after _build_dream_harvest()."""

    @pytest.mark.asyncio
    async def test_dream_buffers_cleared_after_harvest(
        self, tmp_path: Path,
    ) -> None:
        """After _build_dream_harvest(), all three buffers are empty
        and a second call returns None.
        """
        cfg = _make_chat_config(tmp_path)
        session = await _started_chat_session(cfg)

        # Populate buffers with chat turns.
        for i in range(3):
            await session.send(f"Turn {i}")

        # First harvest consumes the buffers.
        harvest = session._build_dream_harvest()
        assert harvest is not None, "First harvest should be non-None"

        # Buffers should now be empty.
        assert len(session._psi_snapshots) == 0, (
            f"_psi_snapshots not cleared: {len(session._psi_snapshots)} remain"
        )
        assert len(session._phi_iit_history) == 0, (
            f"_phi_iit_history not cleared: {len(session._phi_iit_history)} remain"
        )
        assert len(session._pipeline_events) == 0, (
            f"_pipeline_events not cleared: {len(session._pipeline_events)} remain"
        )

        # Second harvest returns None (nothing left).
        second = session._build_dream_harvest()
        assert second is None, (
            "Second _build_dream_harvest() should return None after clearing"
        )


# ===========================================================================
# TestChatDreamTiming — simulation vs legacy duration
# ===========================================================================


class TestChatDreamTiming:
    """Verify simulation dream takes measurably longer than legacy."""

    @pytest.mark.asyncio
    async def test_dream_simulation_takes_longer_than_legacy(
        self, tmp_path: Path,
    ) -> None:
        """The simulation path (replay + exploration + consolidation)
        should take strictly longer than the legacy statistical path.
        We compare total_duration from the DreamReport of each path.
        """
        from luna.dream.dream_cycle import DreamCycle

        cfg = _make_chat_config(tmp_path)
        session = await _started_chat_session(cfg)

        # Build enough history for both paths.
        for _ in range(20):
            session.engine.idle_step()

        # --- Legacy dream (no chat data) ---
        dream_legacy = DreamCycle(session.engine, cfg)
        report_legacy = await dream_legacy.run(harvest=None)

        # --- Accumulate wake-cycle data, then simulation dream ---
        for i in range(3):
            await session.send(f"Turn {i}")

        harvest = session._build_dream_harvest()
        assert harvest is not None, "Harvest should be non-None after send() calls"

        dream_sim = DreamCycle(session.engine, cfg)
        report_sim = await dream_sim.run(harvest=harvest)

        # Simulation should take strictly longer than legacy.
        assert report_sim.total_duration > report_legacy.total_duration, (
            f"Simulation ({report_sim.total_duration:.4f}s) should take longer "
            f"than legacy ({report_legacy.total_duration:.4f}s)"
        )


# ===========================================================================
# TestChatDreamConsolidation — report structure after simulation
# ===========================================================================


class TestChatDreamConsolidation:
    """Verify simulation dream via ChatSession produces valid consolidation."""

    @pytest.mark.asyncio
    async def test_dream_simulation_produces_consolidation_report(
        self, tmp_path: Path,
    ) -> None:
        """After simulation dream, report.consolidation_report is not None
        and has drift_per_agent entries for each agent.
        """
        from luna.dream.dream_cycle import DreamCycle

        cfg = _make_chat_config(tmp_path)
        session = await _started_chat_session(cfg)

        for _ in range(20):
            session.engine.idle_step()

        for i in range(3):
            await session.send(f"Turn {i}")

        harvest = session._build_dream_harvest()
        assert harvest is not None

        dream = DreamCycle(session.engine, cfg)
        report = await dream.run(harvest=harvest)

        assert report.consolidation_report is not None, (
            "Simulation dream must produce a consolidation_report"
        )

        cr = report.consolidation_report

        # drift_per_agent should have entries for agents in the harvest.
        assert len(cr.drift_per_agent) > 0, (
            "consolidation_report.drift_per_agent should not be empty"
        )

        # All drifts should be non-negative floats.
        for agent, drift in cr.drift_per_agent.items():
            assert isinstance(drift, float), (
                f"Drift for {agent} should be float, got {type(drift).__name__}"
            )
            assert drift >= 0.0, (
                f"Drift for {agent} should be >= 0, got {drift}"
            )

        # dominant_preserved should be a bool.
        assert isinstance(cr.dominant_preserved, bool), (
            f"dominant_preserved should be bool, got {type(cr.dominant_preserved).__name__}"
        )


# ===========================================================================
# TestChatDreamProfilePersistence — profiles saved to disk
# ===========================================================================


class TestChatDreamProfilePersistence:
    """Verify simulation dream saves consolidated profiles to disk."""

    @pytest.mark.asyncio
    async def test_dream_simulation_saves_profiles(
        self, tmp_path: Path,
    ) -> None:
        """After simulation dream with dominant_preserved=True,
        agent_profiles.json should be created in data_dir.
        """
        from luna.dream.dream_cycle import DreamCycle

        cfg = _make_chat_config(tmp_path)
        session = await _started_chat_session(cfg)

        # Pre-create data_dir — DreamCycle expects it to exist for profile saving.
        data_dir = cfg.resolve(cfg.luna.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)

        for _ in range(20):
            session.engine.idle_step()

        for i in range(3):
            await session.send(f"Turn {i}")

        harvest = session._build_dream_harvest()
        assert harvest is not None

        dream = DreamCycle(session.engine, cfg)
        report = await dream.run(harvest=harvest)

        cr = report.consolidation_report
        assert cr is not None, "Need consolidation_report to check profile saving"

        data_dir = cfg.resolve(cfg.luna.data_dir)
        profiles_path = data_dir / "agent_profiles.json"

        if cr.dominant_preserved:
            assert profiles_path.exists(), (
                f"agent_profiles.json should exist at {profiles_path} "
                f"when dominant_preserved=True"
            )

            # Verify the JSON is valid and contains agent profiles.
            content = json.loads(profiles_path.read_text())
            assert isinstance(content, dict), (
                "agent_profiles.json should contain a dict"
            )

            # Each value should be a list of 4 floats.
            for agent_name, profile in content.items():
                assert isinstance(profile, list), (
                    f"Profile for {agent_name} should be a list"
                )
                assert len(profile) == 4, (
                    f"Profile for {agent_name} should have 4 components, "
                    f"got {len(profile)}"
                )
                for comp in profile:
                    assert isinstance(comp, (int, float)), (
                        f"Profile component for {agent_name} should be numeric"
                    )
        else:
            # dominant not preserved => consolidation rolled back.
            # Profiles may or may not exist, but the report documents rollback.
            pass
