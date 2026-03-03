"""Session 3-4 -- PipelineRunner: 15 tests for async subprocess orchestration.

All subprocess calls are mocked via unittest.mock.AsyncMock patching
asyncio.create_subprocess_exec. PipelineReader is patched to return
synthetic or controlled Pydantic models. No actual subprocesses launched.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from luna_common.schemas import (
    IntegrationCheck,
    PsiState,
    SayOhmyManifest,
    SentinelReport,
)

from luna.pipeline.runner import PipelineRunner, _clamp01
from luna.pipeline.task import (
    PipelineResult,
    PipelineTask,
    StepResult,
    TaskStatus,
    TaskType,
)


# =====================================================================
#  FIXTURES
# =====================================================================

_DEFAULT_PSI = PsiState(
    perception=0.25, reflexion=0.25, integration=0.25, expression=0.25,
)


def _make_runner(tmp_path: Path) -> PipelineRunner:
    """Build a PipelineRunner with tmp_path directories."""
    root = tmp_path / "pipeline"
    root.mkdir(parents=True, exist_ok=True)
    return PipelineRunner(
        pipeline_root=root,
        sayohmy_cwd=tmp_path / "sayohmy",
        sentinel_cwd=tmp_path / "sentinel",
        testengineer_cwd=tmp_path / "testengineer",
        agent_timeout=5.0,
    )


def _make_task(description: str = "test task") -> PipelineTask:
    """Build a minimal PipelineTask."""
    return PipelineTask(
        task_type=TaskType.IMPROVE,
        description=description,
        priority=0.7,
        source="test",
    )


def _mock_process(returncode: int = 0, stdout: bytes = b"", stderr: bytes = b"") -> AsyncMock:
    """Create a mock subprocess with controllable return code and outputs."""
    proc = AsyncMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.kill = MagicMock()
    return proc


def _make_manifest(task_id: str) -> SayOhmyManifest:
    return SayOhmyManifest(
        task_id=task_id,
        files_produced=["output.py"],
        phi_score=0.75,
        mode_used="reviewer",
        psi_sayohmy=_DEFAULT_PSI,
        confidence=0.80,
    )


def _make_sentinel_report(task_id: str, *, veto: bool = False) -> SentinelReport:
    return SentinelReport(
        task_id=task_id,
        findings=[],
        risk_score=0.1,
        veto=veto,
        veto_reason="Critical vulnerability found" if veto else None,
        psi_sentinel=_DEFAULT_PSI,
        kill_requested=False,
    )


def _make_integration(task_id: str) -> IntegrationCheck:
    return IntegrationCheck(
        task_id=task_id,
        cross_checks=[],
        coherence_score=0.70,
        coverage_delta=0.5,
        veto_contested=False,
        psi_te=_DEFAULT_PSI,
    )


# =====================================================================
#  I. _run_subprocess
# =====================================================================


class TestRunSubprocess:
    """Low-level subprocess invocation -- success, failure, timeout, not-found."""

    @pytest.mark.asyncio
    async def test_successful_command(self, tmp_path: Path) -> None:
        """Return code 0 -> success=True, stdout captured."""
        runner = _make_runner(tmp_path)
        proc = _mock_process(returncode=0, stdout=b"all good")

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await runner._run_subprocess(
                "TEST_AGENT", ["echo", "hello"], tmp_path,
            )

        assert result.success is True
        assert result.return_code == 0
        assert "all good" in result.stdout

    @pytest.mark.asyncio
    async def test_failed_command(self, tmp_path: Path) -> None:
        """Return code 1 -> success=False."""
        runner = _make_runner(tmp_path)
        proc = _mock_process(returncode=1, stderr=b"error occurred")

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await runner._run_subprocess(
                "TEST_AGENT", ["fail_cmd"], tmp_path,
            )

        assert result.success is False
        assert result.return_code == 1
        assert "error occurred" in result.stderr

    @pytest.mark.asyncio
    async def test_timeout_handling(self, tmp_path: Path) -> None:
        """asyncio.TimeoutError -> success=False, stderr mentions timeout."""
        runner = _make_runner(tmp_path)
        proc = _mock_process()
        proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            # Patch wait_for to propagate the timeout
            result = await runner._run_subprocess(
                "TEST_AGENT", ["slow_cmd"], tmp_path,
            )

        assert result.success is False
        assert result.return_code == -1
        assert "timeout" in result.stderr.lower() or "Timeout" in result.stderr

    @pytest.mark.asyncio
    async def test_command_not_found(self, tmp_path: Path) -> None:
        """FileNotFoundError -> success=False, return_code=-2."""
        runner = _make_runner(tmp_path)

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("no such binary"),
        ):
            result = await runner._run_subprocess(
                "TEST_AGENT", ["nonexistent"], tmp_path,
            )

        assert result.success is False
        assert result.return_code == -2
        assert "not found" in result.stderr.lower() or "Command not found" in result.stderr


# =====================================================================
#  II. FULL PIPELINE RUN
# =====================================================================


class TestRunPipeline:
    """Integration of the 3-agent cycle: SAYOHMY -> SENTINEL -> TESTENGINEER."""

    @pytest.mark.asyncio
    async def test_full_success_cycle(self, tmp_path: Path) -> None:
        """All 3 agents succeed, no veto -> COMPLETED with metrics."""
        runner = _make_runner(tmp_path)
        task = _make_task()
        proc = _mock_process(returncode=0, stdout=b"ok")

        with patch("asyncio.create_subprocess_exec", return_value=proc), \
             patch.object(runner, "_read_manifest", return_value=_make_manifest(task.task_id)), \
             patch.object(runner, "_read_sentinel_report", return_value=_make_sentinel_report(task.task_id)), \
             patch.object(runner, "_read_integration_check", return_value=_make_integration(task.task_id)):

            result = await runner.run(task)

        assert result.status == TaskStatus.COMPLETED
        assert result.task_id == task.task_id
        assert len(result.steps) == 3, f"Expected 3 steps, got {len(result.steps)}"
        assert result.duration_seconds > 0
        assert "Pipeline completed" in result.reason

    @pytest.mark.asyncio
    async def test_sayohmy_failure_stops(self, tmp_path: Path) -> None:
        """SAYOHMY fails -> FAILED, only 1 step recorded, no SENTINEL/TE."""
        runner = _make_runner(tmp_path)
        task = _make_task()
        proc_fail = _mock_process(returncode=1, stderr=b"compilation error")

        with patch("asyncio.create_subprocess_exec", return_value=proc_fail):
            result = await runner.run(task)

        assert result.status == TaskStatus.FAILED
        assert len(result.steps) == 1, "Only SAYOHMY step should be recorded"
        assert "SAYOHMY failed" in result.reason

    @pytest.mark.asyncio
    async def test_sentinel_veto_stops(self, tmp_path: Path) -> None:
        """SENTINEL veto=True -> VETOED, 2 steps (SAYOHMY + SENTINEL), no TE."""
        runner = _make_runner(tmp_path)
        task = _make_task()
        proc = _mock_process(returncode=0)

        with patch("asyncio.create_subprocess_exec", return_value=proc), \
             patch.object(runner, "_read_manifest", return_value=_make_manifest(task.task_id)), \
             patch.object(runner, "_read_sentinel_report", return_value=_make_sentinel_report(task.task_id, veto=True)):

            result = await runner.run(task)

        assert result.status == TaskStatus.VETOED
        assert len(result.steps) == 2, "SAYOHMY + SENTINEL steps expected"
        assert "veto" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_metrics_extracted(self, tmp_path: Path) -> None:
        """Completed pipeline extracts metrics with canonical names."""
        runner = _make_runner(tmp_path)
        task = _make_task()
        proc = _mock_process(returncode=0)

        with patch("asyncio.create_subprocess_exec", return_value=proc), \
             patch.object(runner, "_read_manifest", return_value=_make_manifest(task.task_id)), \
             patch.object(runner, "_read_sentinel_report", return_value=_make_sentinel_report(task.task_id)), \
             patch.object(runner, "_read_integration_check", return_value=_make_integration(task.task_id)):

            result = await runner.run(task)

        assert result.status == TaskStatus.COMPLETED
        assert "security_integrity" in result.metrics
        assert "performance_score" in result.metrics
        assert "complexity_score" in result.metrics
        assert "test_ratio" in result.metrics


# =====================================================================
#  III. SYNTHETIC BUILDERS
# =====================================================================


class TestSyntheticBuilders:
    """Verify that synthetic fallback reports are Pydantic-valid."""

    def test_synthetic_manifest_valid(self) -> None:
        """Synthetic manifest passes Pydantic validation."""
        manifest = PipelineRunner._build_synthetic_manifest("test123")
        assert manifest.task_id == "test123"
        assert manifest.phi_score == 0.5
        assert manifest.confidence == 0.5
        assert manifest.mode_used == "reviewer"
        assert manifest.files_produced == []
        # PsiState simplex check passes (sum ~= 1.0)
        assert abs(manifest.psi_sayohmy.sum() - 1.0) < 0.01

    def test_synthetic_sentinel_valid(self) -> None:
        """Synthetic sentinel report: fail-closed (veto=True, S07-004)."""
        report = PipelineRunner._build_synthetic_sentinel_report("test456")
        assert report.task_id == "test456"
        assert report.veto is True  # S07-004: fail-closed when unavailable
        assert report.risk_score == 1.0
        assert report.findings == []
        assert abs(report.psi_sentinel.sum() - 1.0) < 0.01

    def test_synthetic_integration_valid(self) -> None:
        """Synthetic integration check: coherence=0.5, coverage_delta=0."""
        check = PipelineRunner._build_synthetic_integration("test789")
        assert check.task_id == "test789"
        assert check.coherence_score == 0.5
        assert check.coverage_delta == 0.0
        assert check.veto_contested is False
        assert abs(check.psi_te.sum() - 1.0) < 0.01


# =====================================================================
#  IV. METRICS EXTRACTION
# =====================================================================


class TestMetricsExtraction:
    """Verify _extract_metrics maps report fields to canonical metrics."""

    def test_extracts_security_integrity(self) -> None:
        """security_integrity = 1 - risk_score."""
        manifest = _make_manifest("t1")
        report = _make_sentinel_report("t1")
        report_data = report  # risk_score=0.1
        integration = _make_integration("t1")

        metrics = PipelineRunner._extract_metrics(manifest, report_data, integration)
        expected = 1.0 - 0.1
        assert abs(metrics["security_integrity"] - expected) < 1e-9, (
            f"Expected security_integrity={expected}, got {metrics['security_integrity']}"
        )

    def test_extracts_performance_score(self) -> None:
        """performance_score = manifest.confidence."""
        manifest = _make_manifest("t2")  # confidence=0.80
        report = _make_sentinel_report("t2")
        integration = _make_integration("t2")

        metrics = PipelineRunner._extract_metrics(manifest, report, integration)
        assert abs(metrics["performance_score"] - 0.80) < 1e-9

    def test_all_values_bounded_01(self) -> None:
        """All extracted metrics are in [0.0, 1.0]."""
        manifest = _make_manifest("t3")
        report = _make_sentinel_report("t3")
        integration = _make_integration("t3")

        metrics = PipelineRunner._extract_metrics(manifest, report, integration)
        for name, value in metrics.items():
            assert 0.0 <= value <= 1.0, (
                f"Metric {name}={value} is out of [0, 1] bounds"
            )


# =====================================================================
#  V. CLAMP HELPER
# =====================================================================


class TestClamp01:
    """_clamp01 boundary verification."""

    def test_clamp_negative(self) -> None:
        assert _clamp01(-0.5) == 0.0

    def test_clamp_above_one(self) -> None:
        assert _clamp01(1.5) == 1.0

    def test_clamp_normal(self) -> None:
        assert _clamp01(0.618) == 0.618

    def test_clamp_zero(self) -> None:
        assert _clamp01(0.0) == 0.0

    def test_clamp_one(self) -> None:
        assert _clamp01(1.0) == 1.0
