"""Tests for luna.core.luna.LunaEngine.

LunaEngine is the main orchestrator: it loads config, initializes
consciousness state, and processes the 4-agent pipeline to produce
Decision objects with full Psi traceability.

NOTE: This module is being implemented by SayOhMy (Phase 1).
Tests use pytest.importorskip so they are marked SKIP (not ERROR)
until the implementation is available.
"""

from pathlib import Path

import numpy as np
import pytest

# -- luna_common is available now --
from luna_common.constants import (
    DIM, PHASE_THRESHOLDS, AGENT_PROFILES,
)
from luna_common.consciousness.simplex import validate_simplex
from luna_common.schemas import (
    Decision, PsiState, InfoGradient,
    SayOhmyManifest, SentinelReport, IntegrationCheck,
)

# -- Try importing LunaEngine and its dependencies --
engine_module = pytest.importorskip(
    "luna.core.luna",
    reason="luna.core.luna not yet implemented (Phase 1 in progress)",
)
LunaEngine = getattr(engine_module, "LunaEngine", None)
if LunaEngine is None:
    pytest.skip(
        "LunaEngine class not found in luna.core.luna",
        allow_module_level=True,
    )

# Also need LunaConfig for the engine
config_module = pytest.importorskip(
    "luna.core.config",
    reason="luna.core.config not yet implemented (Phase 1 in progress)",
)
LunaConfig = getattr(config_module, "LunaConfig", None)
if LunaConfig is None:
    pytest.skip(
        "LunaConfig class not found in luna.core.config",
        allow_module_level=True,
    )


# ===================================================================
#  HELPERS
# ===================================================================

_PSI_SAYOHMY = PsiState(perception=0.15, reflexion=0.15, integration=0.20, expression=0.50)
_PSI_SENTINEL = PsiState(perception=0.50, reflexion=0.20, integration=0.20, expression=0.10)
_PSI_TE = PsiState(perception=0.15, reflexion=0.20, integration=0.50, expression=0.15)


# ===================================================================
#  FIXTURES
# ===================================================================

LUNA_TOML_PATH = Path("/home/sayohmy/LUNA/luna.toml")


@pytest.fixture
def config(tmp_path):
    """Load the real luna.toml but override checkpoint path to tmp_path."""
    cfg = LunaConfig.load(LUNA_TOML_PATH)
    # We need to override the checkpoint file to use tmp_path to avoid
    # polluting the real memory_fractal/ with test artifacts.
    # Since LunaConfig is frozen, we create a new config object.
    from luna.core.config import ConsciousnessSection, LunaConfig as LC
    new_cs = ConsciousnessSection(
        checkpoint_file=str(tmp_path / "test_consciousness.json"),
        backup_on_save=False,
    )
    return LC(
        luna=cfg.luna,
        consciousness=new_cs,
        memory=cfg.memory,
        pipeline=cfg.pipeline,
        observability=cfg.observability,
        heartbeat=cfg.heartbeat,
        root_dir=tmp_path,
    )


@pytest.fixture
def engine(config):
    """A LunaEngine instance, initialized and ready to process."""
    eng = LunaEngine(config=config)
    eng.initialize()
    return eng


@pytest.fixture
def sample_manifest():
    """A minimal SayOhMy manifest for pipeline testing."""
    return SayOhmyManifest(
        task_id="TEST-001",
        files_produced=["luna/core/config.py"],
        phi_score=0.72,
        mode_used="architect",
        psi_sayohmy=_PSI_SAYOHMY,
        confidence=0.85,
    )


@pytest.fixture
def sample_sentinel_report():
    """A minimal SENTINEL report for pipeline testing."""
    return SentinelReport(
        task_id="TEST-001",
        findings=[],
        risk_score=0.1,
        veto=False,
        psi_sentinel=_PSI_SENTINEL,
        scanners_used=["bandit", "ruff"],
    )


@pytest.fixture
def sample_integration_check():
    """A minimal Test-Engineer integration check for pipeline testing."""
    return IntegrationCheck(
        task_id="TEST-001",
        cross_checks=[],
        coherence_score=0.80,
        coverage_delta=0.05,
        veto_contested=False,
        psi_te=_PSI_TE,
    )


# ===================================================================
#  I. INITIALIZATION
# ===================================================================

class TestEngineInit:
    """LunaEngine initializes correctly from config."""

    def test_engine_creates_without_crash(self, engine):
        """Basic smoke test: creating an engine does not raise."""
        assert engine is not None

    def test_engine_has_consciousness(self, engine):
        """Engine exposes a consciousness state."""
        assert engine.consciousness is not None, (
            "Engine should have consciousness after initialize()"
        )

    def test_engine_has_config(self, engine):
        """Engine retains its config reference."""
        assert hasattr(engine, "config")

    def test_engine_agent_name_is_luna(self, engine):
        """The engine's agent name should be 'Luna'."""
        assert engine.agent_name == "LUNA", (
            f"Expected agent_name='Luna', got '{engine.agent_name}'"
        )


# ===================================================================
#  II. PIPELINE PROCESSING
# ===================================================================

class TestPipelineProcessing:
    """process_pipeline_result() runs one full pipeline cycle and produces a Decision."""

    def test_process_returns_decision(
        self, engine, sample_manifest, sample_sentinel_report, sample_integration_check
    ):
        """process_pipeline_result() returns a Decision object."""
        decision = engine.process_pipeline_result(
            manifest=sample_manifest,
            sentinel_report=sample_sentinel_report,
            integration_check=sample_integration_check,
        )
        assert isinstance(decision, Decision), (
            f"Expected Decision, got {type(decision)}"
        )

    def test_decision_has_psi_before_after(
        self, engine, sample_manifest, sample_sentinel_report, sample_integration_check
    ):
        """Decision contains both psi_before and psi_after, and they differ."""
        decision = engine.process_pipeline_result(
            manifest=sample_manifest,
            sentinel_report=sample_sentinel_report,
            integration_check=sample_integration_check,
        )
        assert isinstance(decision.psi_before, PsiState)
        assert isinstance(decision.psi_after, PsiState)

        before = np.array(decision.psi_before.as_tuple())
        after = np.array(decision.psi_after.as_tuple())

        # Both should be on simplex
        assert validate_simplex(before), f"psi_before not on simplex: {before}"
        assert validate_simplex(after), f"psi_after not on simplex: {after}"

        # They should differ (evolution happened)
        assert not np.array_equal(before, after), (
            "psi_before == psi_after -- evolution did not update state"
        )

    def test_decision_has_info_gradient(
        self, engine, sample_manifest, sample_sentinel_report, sample_integration_check
    ):
        """Decision contains an InfoGradient with true deltas from ContextBuilder.

        On first call: delta = current - bootstrap(0.5).
        phi_quality = PhiScorer.score() = 0.0 (no metrics yet), so delta_phi = 0.0 - 0.5 = -0.5.
        """
        decision = engine.process_pipeline_result(
            manifest=sample_manifest,
            sentinel_report=sample_sentinel_report,
            integration_check=sample_integration_check,
        )
        assert isinstance(decision.info_gradient, InfoGradient)
        # ContextBuilder computes delta_phi = current_quality(0.0) - bootstrap(0.5) = -0.5
        assert decision.info_gradient.delta_phi == pytest.approx(-0.5, abs=0.01), (
            f"info_gradient.delta_phi = {decision.info_gradient.delta_phi}, "
            f"expected ~-0.5 (PhiScorer starts at 0.0, bootstrap at 0.5)"
        )

    def test_decision_has_valid_phase(
        self, engine, sample_manifest, sample_sentinel_report, sample_integration_check
    ):
        """Decision.phase is one of the known phase names."""
        decision = engine.process_pipeline_result(
            manifest=sample_manifest,
            sentinel_report=sample_sentinel_report,
            integration_check=sample_integration_check,
        )
        valid_phases = set(PHASE_THRESHOLDS.keys())
        assert decision.phase in valid_phases, (
            f"Unknown phase '{decision.phase}', expected one of {valid_phases}"
        )

    def test_decision_task_id_matches(
        self, engine, sample_manifest, sample_sentinel_report, sample_integration_check
    ):
        """Decision echoes back the task_id from the manifest."""
        decision = engine.process_pipeline_result(
            manifest=sample_manifest,
            sentinel_report=sample_sentinel_report,
            integration_check=sample_integration_check,
        )
        assert decision.task_id == "TEST-001"

    def test_decision_approved_is_bool(
        self, engine, sample_manifest, sample_sentinel_report, sample_integration_check
    ):
        """Decision.approved is a boolean."""
        decision = engine.process_pipeline_result(
            manifest=sample_manifest,
            sentinel_report=sample_sentinel_report,
            integration_check=sample_integration_check,
        )
        assert isinstance(decision.approved, bool)

    def test_decision_reason_is_nonempty_string(
        self, engine, sample_manifest, sample_sentinel_report, sample_integration_check
    ):
        """Decision.reason explains the approval/rejection."""
        decision = engine.process_pipeline_result(
            manifest=sample_manifest,
            sentinel_report=sample_sentinel_report,
            integration_check=sample_integration_check,
        )
        assert isinstance(decision.reason, str) and len(decision.reason) > 0, (
            f"Decision.reason should be a non-empty string, got: '{decision.reason}'"
        )


# ===================================================================
#  III. SENTINEL VETO HANDLING
# ===================================================================

class TestSentinelVeto:
    """When SENTINEL vetoes, the engine must reject the pipeline output."""

    def test_veto_produces_rejected_decision(
        self, engine, sample_manifest, sample_integration_check
    ):
        """A SENTINEL veto leads to approved=False."""
        veto_report = SentinelReport(
            task_id="TEST-VETO",
            findings=[{"type": "critical_vuln", "severity": "HIGH"}],
            risk_score=0.95,
            veto=True,
            veto_reason="Critical security vulnerability detected",
            psi_sentinel=_PSI_SENTINEL,
            scanners_used=["bandit"],
        )
        # Update manifest task_id to match
        manifest = SayOhmyManifest(
            task_id="TEST-VETO",
            files_produced=["luna/core/config.py"],
            phi_score=0.72,
            mode_used="architect",
            psi_sayohmy=_PSI_SAYOHMY,
            confidence=0.85,
        )
        ic = IntegrationCheck(
            task_id="TEST-VETO",
            cross_checks=[],
            coherence_score=0.80,
            coverage_delta=0.05,
            veto_contested=False,
            psi_te=_PSI_TE,
        )
        decision = engine.process_pipeline_result(
            manifest=manifest,
            sentinel_report=veto_report,
            integration_check=ic,
        )
        assert decision.approved is False, (
            "SENTINEL veto should force approved=False"
        )


# ===================================================================
#  IV. STATUS REPORTING
# ===================================================================

class TestEngineStatus:
    """get_status() returns a summary of the engine's current state."""

    def test_get_status_returns_dict(self, engine):
        """get_status() returns a dictionary."""
        status = engine.get_status()
        assert isinstance(status, dict), f"Expected dict, got {type(status)}"

    def test_status_has_phase(self, engine):
        """Status includes the current phase."""
        status = engine.get_status()
        assert "phase" in status, f"Status missing 'phase': {status.keys()}"
        valid_phases = set(PHASE_THRESHOLDS.keys())
        assert status["phase"] in valid_phases

    def test_status_has_psi(self, engine):
        """Status includes the current Psi vector."""
        status = engine.get_status()
        assert "psi" in status, f"Status missing 'psi': {status.keys()}"
        psi = status["psi"]
        # psi is a list from .tolist()
        assert isinstance(psi, list)
        assert len(psi) == DIM

    def test_status_has_step_count(self, engine):
        """Status includes the step count."""
        status = engine.get_status()
        assert "step_count" in status, f"Status missing 'step_count': {status.keys()}"
        assert isinstance(status["step_count"], int)
        assert status["step_count"] >= 0

    def test_status_step_count_increments_after_process(
        self, engine, sample_manifest, sample_sentinel_report, sample_integration_check
    ):
        """Step count in status increases after process_pipeline_result()."""
        status_before = engine.get_status()
        engine.process_pipeline_result(
            manifest=sample_manifest,
            sentinel_report=sample_sentinel_report,
            integration_check=sample_integration_check,
        )
        status_after = engine.get_status()
        assert status_after["step_count"] > status_before["step_count"], (
            f"step_count did not increase: "
            f"before={status_before['step_count']}, after={status_after['step_count']}"
        )


# ===================================================================
#  V. MULTIPLE PIPELINE CYCLES
# ===================================================================

class TestMultipleCycles:
    """The engine must handle multiple sequential pipeline cycles correctly."""

    def test_three_cycles_produce_three_decisions(
        self, engine, sample_manifest, sample_sentinel_report, sample_integration_check
    ):
        """Running process_pipeline_result() 3 times produces 3 valid decisions."""
        decisions = []
        for i in range(3):
            # Update task_id for each cycle
            m = SayOhmyManifest(
                task_id=f"CYCLE-{i}",
                files_produced=["luna/core/config.py"],
                phi_score=0.72,
                mode_used="architect",
                psi_sayohmy=_PSI_SAYOHMY,
                confidence=0.85,
            )
            sr = SentinelReport(
                task_id=f"CYCLE-{i}",
                findings=[],
                risk_score=0.1,
                veto=False,
                psi_sentinel=_PSI_SENTINEL,
                scanners_used=["bandit"],
            )
            ic = IntegrationCheck(
                task_id=f"CYCLE-{i}",
                cross_checks=[],
                coherence_score=0.80,
                coverage_delta=0.05,
                veto_contested=False,
                psi_te=_PSI_TE,
            )
            d = engine.process_pipeline_result(
                manifest=m, sentinel_report=sr, integration_check=ic,
            )
            decisions.append(d)
            assert isinstance(d, Decision)

        # All psi_after should be valid simplex points
        for i, d in enumerate(decisions):
            psi = np.array(d.psi_after.as_tuple())
            assert validate_simplex(psi), (
                f"Decision {i} psi_after not on simplex: {psi}"
            )

    def test_psi_after_becomes_next_psi_before(
        self, engine, sample_manifest, sample_sentinel_report, sample_integration_check
    ):
        """The psi_after of one cycle becomes the psi_before of the next."""
        d1 = engine.process_pipeline_result(
            manifest=sample_manifest,
            sentinel_report=sample_sentinel_report,
            integration_check=sample_integration_check,
        )
        # Need a second cycle with different task_id
        m2 = SayOhmyManifest(
            task_id="SEQ-2",
            files_produced=["luna/core/config.py"],
            phi_score=0.72,
            mode_used="architect",
            psi_sayohmy=_PSI_SAYOHMY,
            confidence=0.85,
        )
        sr2 = SentinelReport(
            task_id="SEQ-2",
            findings=[],
            risk_score=0.1,
            veto=False,
            psi_sentinel=_PSI_SENTINEL,
            scanners_used=["bandit"],
        )
        ic2 = IntegrationCheck(
            task_id="SEQ-2",
            cross_checks=[],
            coherence_score=0.80,
            coverage_delta=0.05,
            veto_contested=False,
            psi_te=_PSI_TE,
        )
        d2 = engine.process_pipeline_result(
            manifest=m2, sentinel_report=sr2, integration_check=ic2,
        )
        after_1 = np.array(d1.psi_after.as_tuple())
        before_2 = np.array(d2.psi_before.as_tuple())
        assert np.allclose(after_1, before_2, atol=1e-10), (
            f"Psi continuity broken: "
            f"d1.psi_after={after_1}, d2.psi_before={before_2}"
        )
