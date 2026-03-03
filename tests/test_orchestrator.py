"""Tests for luna.orchestrator — Phase 4: Async autonomous loop.

No network calls — all LLM and pipeline interactions are mocked.
"""

from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from luna_common.constants import PHI
from luna_common.schemas import (
    CurrentTask,
    Decision,
    InfoGradient,
    IntegrationCheck,
    PsiState,
    SayOhmyManifest,
    SentinelReport,
)

from luna.core.config import LunaConfig, OrchestratorSection
from luna.llm_bridge.bridge import LLMBridgeError, LLMResponse
from luna.orchestrator.orchestrator import CycleResult, LunaOrchestrator
from luna.orchestrator.retry import RetryPolicy, retry_async

# ═══════════════════════════════════════════════════════════════════════════
#  FIXTURES
# ═══════════════════════════════════════════════════════════════════════════

LUNA_TOML_PATH = Path("/home/sayohmy/LUNA/luna.toml")


def _psi_luna() -> PsiState:
    return PsiState(perception=0.25, reflexion=0.35, integration=0.25, expression=0.15)


def _psi_sayohmy() -> PsiState:
    return PsiState(perception=0.15, reflexion=0.15, integration=0.20, expression=0.50)


def _psi_sentinel() -> PsiState:
    return PsiState(perception=0.50, reflexion=0.20, integration=0.20, expression=0.10)


def _psi_te() -> PsiState:
    return PsiState(perception=0.15, reflexion=0.20, integration=0.50, expression=0.15)


def _make_task() -> CurrentTask:
    return CurrentTask(
        task_id="test-task-001",
        description="Test task for orchestrator",
        psi_luna=_psi_luna(),
    )


def _make_manifest() -> SayOhmyManifest:
    return SayOhmyManifest(
        task_id="test-task-001",
        files_produced=["foo.py"],
        phi_score=0.85,
        mode_used="architect",
        psi_sayohmy=_psi_sayohmy(),
        confidence=0.9,
    )


def _make_sentinel_report() -> SentinelReport:
    return SentinelReport(
        task_id="test-task-001",
        risk_score=0.1,
        veto=False,
        psi_sentinel=_psi_sentinel(),
    )


def _make_integration_check() -> IntegrationCheck:
    return IntegrationCheck(
        task_id="test-task-001",
        coherence_score=0.95,
        coverage_delta=0.02,
        psi_te=_psi_te(),
    )


@pytest.fixture
def config() -> LunaConfig:
    return LunaConfig.load(LUNA_TOML_PATH)


@pytest.fixture
def orchestrator(config: LunaConfig, tmp_path: Path) -> LunaOrchestrator:
    """Orchestrator with pipeline root pointing to tmp_path."""
    from dataclasses import replace
    from luna.core.config import PipelineSection

    cfg = replace(
        config,
        pipeline=replace(config.pipeline, root=str(tmp_path)),
        root_dir=tmp_path,
    )
    return LunaOrchestrator(cfg)


# ═══════════════════════════════════════════════════════════════════════════
#  I. RETRY POLICY
# ═══════════════════════════════════════════════════════════════════════════


class TestRetryPolicy:
    """RetryPolicy is frozen with PHI-derived defaults."""

    def test_retry_policy_defaults(self):
        policy = RetryPolicy()
        assert policy.max_retries == 3
        assert policy.base_delay == 1.0
        assert policy.max_delay == 30.0
        assert policy.backoff_factor == PHI

    def test_retry_policy_frozen(self):
        policy = RetryPolicy()
        with pytest.raises(FrozenInstanceError):
            policy.max_retries = 5  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════════════
#  II. RETRY ASYNC
# ═══════════════════════════════════════════════════════════════════════════


class TestRetryAsync:
    """retry_async executes a callable with exponential backoff."""

    @pytest.mark.asyncio
    async def test_retry_async_success_first_try(self):
        fn = AsyncMock(return_value=42)
        result = await retry_async(fn)
        assert result == 42
        fn.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_retry_async_success_after_retries(self):
        fn = AsyncMock(
            side_effect=[
                LLMBridgeError("fail1"),
                42,
            ]
        )
        policy = RetryPolicy(base_delay=0.0)  # No delay in tests
        result = await retry_async(fn, policy=policy)
        assert result == 42
        assert fn.await_count == 2

    @pytest.mark.asyncio
    async def test_retry_async_all_fail(self):
        fn = AsyncMock(side_effect=LLMBridgeError("always fails"))
        policy = RetryPolicy(max_retries=2, base_delay=0.0)
        with pytest.raises(LLMBridgeError, match="always fails"):
            await retry_async(fn, policy=policy)
        assert fn.await_count == 3  # 1 initial + 2 retries

    @pytest.mark.asyncio
    async def test_retry_async_calls_on_retry(self):
        fn = AsyncMock(
            side_effect=[
                LLMBridgeError("fail1"),
                LLMBridgeError("fail2"),
                99,
            ]
        )
        on_retry = MagicMock()
        policy = RetryPolicy(base_delay=0.0)
        result = await retry_async(fn, policy=policy, on_retry=on_retry)
        assert result == 99
        assert on_retry.call_count == 2
        # First retry callback: attempt=1
        assert on_retry.call_args_list[0][0][0] == 1
        # Second retry callback: attempt=2
        assert on_retry.call_args_list[1][0][0] == 2

    @pytest.mark.asyncio
    async def test_retry_async_does_not_catch_non_llm_errors(self):
        """Only LLMBridgeError is retried — other exceptions propagate immediately."""
        fn = AsyncMock(side_effect=ValueError("logic error"))
        policy = RetryPolicy(base_delay=0.0)
        with pytest.raises(ValueError, match="logic error"):
            await retry_async(fn, policy=policy)
        fn.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_retry_async_forwards_args_kwargs(self):
        fn = AsyncMock(return_value="ok")
        await retry_async(fn, "arg1", "arg2", policy=RetryPolicy(), key="val")
        fn.assert_awaited_once_with("arg1", "arg2", key="val")


# ═══════════════════════════════════════════════════════════════════════════
#  III. CYCLE RESULT
# ═══════════════════════════════════════════════════════════════════════════


class TestCycleResult:
    """CycleResult contains all traceability fields."""

    def test_cycle_result_fields(self):
        decision = Decision(
            task_id="t1",
            approved=True,
            reason="ok",
            psi_before=_psi_luna(),
            psi_after=_psi_luna(),
            info_gradient=InfoGradient(),
            phase="FUNCTIONAL",
            quality_score=0.75,
        )
        cr = CycleResult(
            decision=decision,
            llm_reasoning="Luna approves",
            llm_tokens=(100, 50),
            cycle_number=3,
            duration_seconds=1.5,
        )
        assert cr.decision is decision
        assert cr.llm_reasoning == "Luna approves"
        assert cr.llm_tokens == (100, 50)
        assert cr.cycle_number == 3
        assert cr.duration_seconds == 1.5

    def test_cycle_result_defaults(self):
        decision = Decision(
            task_id="t1",
            approved=True,
            reason="ok",
            psi_before=_psi_luna(),
            psi_after=_psi_luna(),
            info_gradient=InfoGradient(),
            phase="FUNCTIONAL",
        )
        cr = CycleResult(decision=decision)
        assert cr.llm_reasoning is None
        assert cr.llm_tokens is None
        assert cr.cycle_number == 0
        assert cr.duration_seconds == 0.0


# ═══════════════════════════════════════════════════════════════════════════
#  IV. ORCHESTRATOR INIT & LIFECYCLE
# ═══════════════════════════════════════════════════════════════════════════


class TestOrchestratorInit:
    """Orchestrator initialization and lifecycle."""

    def test_orchestrator_init(self, orchestrator: LunaOrchestrator):
        assert orchestrator.engine is not None
        assert orchestrator.reader is not None
        assert orchestrator.writer is not None
        assert not orchestrator.is_running

    @pytest.mark.asyncio
    async def test_orchestrator_start_initializes_engine(
        self, orchestrator: LunaOrchestrator,
    ):
        with patch.object(orchestrator.engine, "initialize") as mock_init:
            # Mock create_provider to avoid real LLM creation
            with patch(
                "luna.orchestrator.orchestrator.create_provider",
                side_effect=LLMBridgeError("no key"),
            ):
                await orchestrator.start()
        mock_init.assert_called_once()
        assert orchestrator.is_running

    @pytest.mark.asyncio
    async def test_orchestrator_start_creates_llm(
        self, orchestrator: LunaOrchestrator,
    ):
        mock_llm = MagicMock()
        with patch.object(orchestrator.engine, "initialize"):
            with patch(
                "luna.orchestrator.orchestrator.create_provider",
                return_value=mock_llm,
            ):
                await orchestrator.start()
        assert orchestrator._llm is mock_llm

    @pytest.mark.asyncio
    async def test_orchestrator_start_no_llm_when_no_key(
        self, orchestrator: LunaOrchestrator,
    ):
        with patch.object(orchestrator.engine, "initialize"):
            with patch(
                "luna.orchestrator.orchestrator.create_provider",
                side_effect=LLMBridgeError("No API key"),
            ):
                await orchestrator.start()
        assert orchestrator._llm is None
        assert orchestrator.is_running  # Still runs without LLM

    @pytest.mark.asyncio
    async def test_stop_saves_checkpoint(
        self, orchestrator: LunaOrchestrator,
    ):
        mock_cs = MagicMock()
        orchestrator.engine.consciousness = mock_cs
        orchestrator._running = True

        await orchestrator.stop()

        mock_cs.save_checkpoint.assert_called_once()
        assert not orchestrator.is_running


# ═══════════════════════════════════════════════════════════════════════════
#  V. RUN_CYCLE
# ═══════════════════════════════════════════════════════════════════════════


class TestRunCycle:
    """run_cycle dispatches task, polls reports, processes, and writes decision."""

    @pytest.fixture
    def started_orchestrator(self, orchestrator: LunaOrchestrator) -> LunaOrchestrator:
        """Orchestrator with mocked engine (already initialized)."""
        mock_cs = MagicMock()
        mock_cs.psi = [0.25, 0.35, 0.25, 0.15]
        mock_cs.psi0 = [0.25, 0.35, 0.25, 0.15]
        mock_cs.step_count = 0
        mock_cs.get_phase.return_value = "FUNCTIONAL"
        mock_cs.compute_phi_iit.return_value = 0.7
        mock_cs.to_psi_state.return_value = _psi_luna()
        orchestrator.engine.consciousness = mock_cs
        orchestrator._running = True
        return orchestrator

    def _mock_decision(self) -> Decision:
        return Decision(
            task_id="test-task-001",
            approved=True,
            reason="Approved by engine",
            psi_before=_psi_luna(),
            psi_after=_psi_luna(),
            info_gradient=InfoGradient(),
            phase="FUNCTIONAL",
            quality_score=0.75,
        )

    @pytest.mark.asyncio
    async def test_run_cycle_dispatches_task(
        self, started_orchestrator: LunaOrchestrator,
    ):
        orch = started_orchestrator
        task = _make_task()
        decision = self._mock_decision()

        with patch.object(orch.writer, "write_current_task") as mock_write_task, \
             patch.object(orch.writer, "write_decision"), \
             patch.object(orch.reader, "read_manifest", return_value=_make_manifest()), \
             patch.object(orch.reader, "read_sentinel_report", return_value=_make_sentinel_report()), \
             patch.object(orch.reader, "read_integration_check", return_value=_make_integration_check()), \
             patch.object(orch.engine, "process_pipeline_result", return_value=decision):
            await orch.run_cycle(task)

        mock_write_task.assert_called_once_with(task)

    @pytest.mark.asyncio
    async def test_run_cycle_processes_pipeline(
        self, started_orchestrator: LunaOrchestrator,
    ):
        orch = started_orchestrator
        task = _make_task()
        decision = self._mock_decision()

        with patch.object(orch.writer, "write_current_task"), \
             patch.object(orch.writer, "write_decision"), \
             patch.object(orch.reader, "read_manifest", return_value=_make_manifest()), \
             patch.object(orch.reader, "read_sentinel_report", return_value=_make_sentinel_report()), \
             patch.object(orch.reader, "read_integration_check", return_value=_make_integration_check()), \
             patch.object(orch.engine, "process_pipeline_result", return_value=decision):
            result = await orch.run_cycle(task)

        assert isinstance(result, CycleResult)
        assert result.decision is decision
        assert result.cycle_number == 1
        assert result.duration_seconds > 0

    @pytest.mark.asyncio
    async def test_run_cycle_augments_with_llm(
        self, started_orchestrator: LunaOrchestrator,
    ):
        orch = started_orchestrator
        task = _make_task()
        decision = self._mock_decision()

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content="Luna approves this task",
            model="test-model",
            input_tokens=100,
            output_tokens=50,
        )
        orch._llm = mock_llm

        with patch.object(orch.writer, "write_current_task"), \
             patch.object(orch.writer, "write_decision"), \
             patch.object(orch.reader, "read_manifest", return_value=_make_manifest()), \
             patch.object(orch.reader, "read_sentinel_report", return_value=_make_sentinel_report()), \
             patch.object(orch.reader, "read_integration_check", return_value=_make_integration_check()), \
             patch.object(orch.engine, "process_pipeline_result", return_value=decision), \
             patch(
                 "luna.orchestrator.orchestrator.build_system_prompt",
                 return_value="system prompt",
             ), \
             patch(
                 "luna.orchestrator.orchestrator.build_decision_prompt",
                 return_value="decision prompt",
             ):
            result = await orch.run_cycle(task)

        assert result.llm_reasoning == "Luna approves this task"
        assert result.llm_tokens == (100, 50)
        mock_llm.complete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_cycle_works_without_llm(
        self, started_orchestrator: LunaOrchestrator,
    ):
        orch = started_orchestrator
        orch._llm = None  # No LLM
        task = _make_task()
        decision = self._mock_decision()

        with patch.object(orch.writer, "write_current_task"), \
             patch.object(orch.writer, "write_decision"), \
             patch.object(orch.reader, "read_manifest", return_value=_make_manifest()), \
             patch.object(orch.reader, "read_sentinel_report", return_value=_make_sentinel_report()), \
             patch.object(orch.reader, "read_integration_check", return_value=_make_integration_check()), \
             patch.object(orch.engine, "process_pipeline_result", return_value=decision):
            result = await orch.run_cycle(task)

        assert result.decision is decision
        assert result.llm_reasoning is None
        assert result.llm_tokens is None

    @pytest.mark.asyncio
    async def test_run_cycle_llm_error_recoverable(
        self, started_orchestrator: LunaOrchestrator,
    ):
        """LLMBridgeError during augmentation does not kill the cycle."""
        orch = started_orchestrator
        task = _make_task()
        decision = self._mock_decision()

        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = LLMBridgeError("network error")
        orch._llm = mock_llm

        with patch.object(orch.writer, "write_current_task"), \
             patch.object(orch.writer, "write_decision") as mock_write_dec, \
             patch.object(orch.reader, "read_manifest", return_value=_make_manifest()), \
             patch.object(orch.reader, "read_sentinel_report", return_value=_make_sentinel_report()), \
             patch.object(orch.reader, "read_integration_check", return_value=_make_integration_check()), \
             patch.object(orch.engine, "process_pipeline_result", return_value=decision), \
             patch(
                 "luna.orchestrator.orchestrator.build_system_prompt",
                 return_value="sys",
             ), \
             patch(
                 "luna.orchestrator.orchestrator.build_decision_prompt",
                 return_value="dec",
             ):
            result = await orch.run_cycle(task)

        # Decision still written (deterministic engine succeeded)
        mock_write_dec.assert_called_once_with(decision)
        assert result.decision is decision
        assert result.llm_reasoning is None


# ═══════════════════════════════════════════════════════════════════════════
#  VI. RUN (MAIN LOOP)
# ═══════════════════════════════════════════════════════════════════════════


class TestRun:
    """run() orchestrates multiple cycles with error resilience."""

    @pytest.mark.asyncio
    async def test_run_max_cycles(self, orchestrator: LunaOrchestrator):
        """run(max_cycles=3) executes exactly 3 cycles."""
        decision = Decision(
            task_id="t1",
            approved=True,
            reason="ok",
            psi_before=_psi_luna(),
            psi_after=_psi_luna(),
            info_gradient=InfoGradient(),
            phase="FUNCTIONAL",
            quality_score=0.75,
        )

        with patch.object(orchestrator.engine, "initialize"), \
             patch(
                 "luna.orchestrator.orchestrator.create_provider",
                 side_effect=LLMBridgeError("no key"),
             ), \
             patch.object(orchestrator.reader, "read_manifest", return_value=_make_manifest()), \
             patch.object(orchestrator.reader, "read_sentinel_report", return_value=_make_sentinel_report()), \
             patch.object(orchestrator.reader, "read_integration_check", return_value=_make_integration_check()), \
             patch.object(orchestrator.engine, "process_pipeline_result", return_value=decision), \
             patch.object(orchestrator.writer, "write_decision"), \
             patch.object(orchestrator.engine, "consciousness", create=True) as mock_cs:
            mock_cs.save_checkpoint = MagicMock()
            await orchestrator.run(max_cycles=3)

        assert orchestrator._cycle_count == 3

    @pytest.mark.asyncio
    async def test_run_cycle_timeout_recoverable(self, orchestrator: LunaOrchestrator):
        """TimeoutError in a cycle does not kill the loop."""
        call_count = 0

        def read_manifest_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return None  # Will trigger timeout
            return _make_manifest()

        decision = Decision(
            task_id="t1",
            approved=True,
            reason="ok",
            psi_before=_psi_luna(),
            psi_after=_psi_luna(),
            info_gradient=InfoGradient(),
            phase="FUNCTIONAL",
            quality_score=0.75,
        )

        from dataclasses import replace
        cfg = replace(
            orchestrator.config,
            orchestrator=replace(
                orchestrator.config.orchestrator,
                cycle_timeout=0.01,  # Very short timeout
            ),
            pipeline=replace(
                orchestrator.config.pipeline,
                poll_interval_seconds=0.005,
            ),
        )
        orchestrator.config = cfg

        with patch.object(orchestrator.engine, "initialize"), \
             patch(
                 "luna.orchestrator.orchestrator.create_provider",
                 side_effect=LLMBridgeError("no key"),
             ), \
             patch.object(orchestrator.reader, "read_manifest", side_effect=read_manifest_side_effect), \
             patch.object(orchestrator.reader, "read_sentinel_report", return_value=_make_sentinel_report()), \
             patch.object(orchestrator.reader, "read_integration_check", return_value=_make_integration_check()), \
             patch.object(orchestrator.engine, "process_pipeline_result", return_value=decision), \
             patch.object(orchestrator.writer, "write_decision"), \
             patch.object(orchestrator.engine, "consciousness", create=True) as mock_cs:
            mock_cs.save_checkpoint = MagicMock()
            await orchestrator.run(max_cycles=2)

        # At least 1 cycle completed (first timed out, second succeeded)
        assert orchestrator._cycle_count >= 1


# ═══════════════════════════════════════════════════════════════════════════
#  VII. STATUS
# ═══════════════════════════════════════════════════════════════════════════


class TestOrchestratorStatus:
    """get_status() merges engine status with orchestrator metrics."""

    def test_get_status_includes_orchestrator_fields(
        self, orchestrator: LunaOrchestrator,
    ):
        with patch.object(orchestrator.engine, "get_status", return_value={"initialized": False}):
            status = orchestrator.get_status()
        assert "orchestrator_running" in status
        assert "cycles_completed" in status
        assert "llm_available" in status
        assert "llm_augment" in status
        assert status["orchestrator_running"] is False
        assert status["cycles_completed"] == 0


# ═══════════════════════════════════════════════════════════════════════════
#  VIII. CONFIG
# ═══════════════════════════════════════════════════════════════════════════


class TestOrchestratorConfig:
    """OrchestratorSection defaults and TOML loading."""

    def test_config_orchestrator_defaults(self):
        section = OrchestratorSection()
        assert section.llm_augment is True
        assert section.max_cycles == 0
        assert section.checkpoint_interval == 1
        assert section.cycle_timeout == 600.0
        assert section.retry_max == 3
        assert section.retry_base_delay == 1.0

    def test_config_orchestrator_frozen(self):
        section = OrchestratorSection()
        with pytest.raises(FrozenInstanceError):
            section.llm_augment = False  # type: ignore[misc]

    def test_config_load_with_orchestrator(self, config: LunaConfig):
        """luna.toml includes [orchestrator] section."""
        assert hasattr(config, "orchestrator")
        assert isinstance(config.orchestrator, OrchestratorSection)
        assert config.orchestrator.llm_augment is True
        assert config.orchestrator.max_cycles == 0

    def test_config_load_without_orchestrator_section(self, tmp_path: Path):
        """Config loads with defaults if [orchestrator] is missing from TOML."""
        toml_content = """\
[luna]
version = "2.2.0-test"
agent_name = "LUNA"
data_dir = "data"
pipeline_dir = "pipeline"

[consciousness]
checkpoint_file = "ckpt.json"

[memory]
fractal_root = "memory"

[pipeline]
root = "pipeline"
"""
        toml_file = tmp_path / "luna.toml"
        toml_file.write_text(toml_content)
        cfg = LunaConfig.load(toml_file)
        assert cfg.orchestrator.llm_augment is True
        assert cfg.orchestrator.max_cycles == 0
