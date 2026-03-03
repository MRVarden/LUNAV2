"""PipelineRunner -- async subprocess orchestration of the 4-agent cycle.

Invokes SAYOHMY -> SENTINEL -> TESTENGINEER as subprocesses, reads their
outputs via the filesystem JSON protocol, and produces a PipelineResult.

Security: NEVER uses shell=True. All command arguments are passed as lists
to asyncio.create_subprocess_exec.  Timeouts prevent hung agents from
blocking the system.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

from luna_common.schemas import (
    CurrentTask,
    IntegrationCheck,
    PsiState,
    SayOhmyManifest,
    SentinelReport,
)

from luna.pipeline.pipeline_io import PipelineReader, PipelineWriter
from luna.pipeline.task import PipelineResult, PipelineTask, StepResult, TaskStatus

log = logging.getLogger(__name__)

# Default Psi profile for synthetic fallbacks.
# Components must sum to 1.0 to satisfy the PsiState simplex validator.
_DEFAULT_PSI = PsiState(
    perception=0.25,
    reflexion=0.25,
    integration=0.25,
    expression=0.25,
)

# Luna's identity profile from constants (reflexion-dominant).
_LUNA_PSI = PsiState(
    perception=0.25,
    reflexion=0.35,
    integration=0.25,
    expression=0.15,
)


class PipelineRunner:
    """Orchestrate the 4-agent pipeline cycle via subprocess invocation.

    Each agent is invoked as a subprocess with strict argument lists (no shell).
    Results are read from the filesystem JSON protocol managed by
    PipelineWriter/PipelineReader.

    Parameters
    ----------
    pipeline_root : Path
        Directory where JSON files are exchanged between agents.
    sayohmy_cwd : Path
        Working directory for the SAYOHMY subprocess.
    sentinel_cwd : Path
        Working directory for the SENTINEL subprocess.
    testengineer_cwd : Path
        Working directory for the TESTENGINEER subprocess.
    agent_timeout : float
        Maximum seconds to wait for any single agent subprocess.
    """

    def __init__(
        self,
        pipeline_root: Path,
        sayohmy_cwd: Path,
        sentinel_cwd: Path,
        testengineer_cwd: Path,
        agent_timeout: float = 120.0,
        project_root: Path | None = None,
        env_extras: dict[str, str] | None = None,
    ) -> None:
        self._root = Path(pipeline_root).resolve()
        self._sayohmy_cwd = Path(sayohmy_cwd)
        self._sentinel_cwd = Path(sentinel_cwd)
        self._testengineer_cwd = Path(testengineer_cwd)
        self._timeout = agent_timeout
        self._writer = PipelineWriter(self._root)
        self._reader = PipelineReader(self._root)

        # Load .env from project root (injects into os.environ).
        self._load_dotenv(project_root or pipeline_root.parent)

        # Config-derived env vars (e.g., api_key from luna.toml).
        if env_extras:
            os.environ.update(env_extras)

    # ------------------------------------------------------------------
    # Environment bootstrap
    # ------------------------------------------------------------------

    @staticmethod
    def _load_dotenv(project_root: Path) -> None:
        """Load ``.env`` from *project_root* into ``os.environ``.

        Uses ``python-dotenv`` if available, otherwise falls back to a
        minimal KEY=VALUE parser.  Existing env vars are NOT overridden
        (``override=False``) so explicit exports (e.g. from .bashrc) win.
        """
        env_path = project_root / ".env"
        if not env_path.is_file():
            return
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path, override=False)
            log.info("Loaded .env from %s", env_path)
        except ImportError:
            # Fallback: read KEY=VALUE lines manually.
            with open(env_path) as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()
                    if key and key not in os.environ:
                        os.environ[key] = value
            log.info("Loaded .env (fallback parser) from %s", env_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, task: PipelineTask) -> PipelineResult:
        """Execute the full pipeline cycle for a task.

        Steps:
            1. Write current_task.json via PipelineWriter.
            2. Invoke SAYOHMY -> read manifest.
            3. Invoke SENTINEL -> read report; check veto.
            4. Invoke TESTENGINEER -> read integration check.
            5. Extract metrics from reports.
            6. Return PipelineResult.
        """
        t0 = time.monotonic()
        steps: list[StepResult] = []

        # 1. Write current_task.json.
        current = CurrentTask(
            task_id=task.task_id,
            description=task.description,
            context={"task_type": task.task_type.value, "source": task.source},
            psi_luna=_LUNA_PSI,
        )
        self._writer.write_current_task(current)

        # 2. SAYOHMY -- code generation.
        sayohmy_step = await self._invoke_sayohmy(task)
        steps.append(sayohmy_step)

        if not sayohmy_step.success:
            return PipelineResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                reason=f"SAYOHMY failed: {sayohmy_step.stderr[:200]}",
                steps=steps,
                duration_seconds=time.monotonic() - t0,
            )

        manifest = self._read_manifest(task.task_id)

        # 3. SENTINEL -- security audit.
        sentinel_step = await self._invoke_sentinel(task)
        steps.append(sentinel_step)

        report = self._read_sentinel_report(task.task_id)

        # Check veto.
        if report.veto:
            return PipelineResult(
                task_id=task.task_id,
                status=TaskStatus.VETOED,
                reason=f"SENTINEL veto: {report.veto_reason or 'no reason given'}",
                steps=steps,
                duration_seconds=time.monotonic() - t0,
            )

        # 4. TESTENGINEER -- integration validation.
        te_step = await self._invoke_testengineer(task)
        steps.append(te_step)

        integration = self._read_integration_check(task.task_id)

        # 5. Extract metrics.
        metrics = self._extract_metrics(manifest, report, integration)

        return PipelineResult(
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            reason="Pipeline completed successfully",
            steps=steps,
            metrics=metrics,
            duration_seconds=time.monotonic() - t0,
        )

    # ------------------------------------------------------------------
    # Agent invocations
    # ------------------------------------------------------------------

    async def _invoke_sayohmy(self, task: PipelineTask) -> StepResult:
        """Invoke SAYOHMY via ``python3 -m sayohmy generate``.

        Reads current_task.json (already written by run()), writes
        sayohmy_manifest.json to the pipeline root.
        """
        task_path = self._root / "current_task.json"
        manifest_path = self._root / "sayohmy_manifest.json"
        cmd = [
            sys.executable, "-m", "sayohmy",
            "generate",
            "--task", str(task_path),
            "--output", str(manifest_path),
        ]
        return await self._run_subprocess("SAYOHMY", cmd, self._sayohmy_cwd)

    async def _invoke_sentinel(self, task: PipelineTask) -> StepResult:
        """Invoke SENTINEL via ``python3 -m sentinel report``.

        Passes --task-id so SENTINEL's JSON output includes the pipeline
        task identifier, making the output parseable as a SentinelReport.
        """
        report_path = self._root / "sentinel_report.json"
        cmd = [
            sys.executable, "-m", "sentinel",
            "report",
            "-f", "json",
            "--task-id", task.task_id,
            "-o", str(report_path),
        ]
        return await self._run_subprocess("SENTINEL", cmd, self._sentinel_cwd)

    async def _invoke_testengineer(self, task: PipelineTask) -> StepResult:
        """Invoke TESTENGINEER via ``python3 -m testengineer validate``.

        Reads the manifest and sentinel report already produced by the
        previous agents, writes integration_check.json.
        """
        manifest_path = self._root / "sayohmy_manifest.json"
        report_path = self._root / "sentinel_report.json"
        output_path = self._root / "integration_check.json"
        cmd = [
            sys.executable, "-m", "testengineer",
            "validate",
            "--manifest", str(manifest_path),
            "--report", str(report_path),
            "--output", str(output_path),
        ]
        return await self._run_subprocess(
            "TESTENGINEER", cmd, self._testengineer_cwd
        )

    async def _run_subprocess(
        self,
        agent: str,
        cmd: list[str],
        cwd: Path,
    ) -> StepResult:
        """Run a subprocess with timeout.  NEVER uses shell=True.

        All arguments are passed as a list to create_subprocess_exec.
        stdout/stderr are captured and truncated to 10 000 chars to prevent
        memory exhaustion from chatty agents.
        """
        t0 = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._timeout,
            )
            duration = time.monotonic() - t0
            return_code = proc.returncode or 0
            return StepResult(
                agent=agent,
                success=return_code == 0,
                duration_seconds=duration,
                return_code=return_code,
                stdout=stdout_bytes.decode(errors="replace")[:10_000],
                stderr=stderr_bytes.decode(errors="replace")[:10_000],
            )
        except asyncio.TimeoutError:
            log.warning("%s timed out after %.1fs", agent, self._timeout)
            # Kill the hung process and reap to avoid zombie subprocesses.
            try:
                proc.kill()  # type: ignore[possibly-undefined]
                await proc.wait()  # S07-002: reap to prevent zombie
            except (ProcessLookupError, OSError):
                pass
            return StepResult(
                agent=agent,
                success=False,
                duration_seconds=time.monotonic() - t0,
                return_code=-1,
                stderr=f"Timeout after {self._timeout}s",
            )
        except FileNotFoundError:
            log.error("%s command not found: %s", agent, cmd[0])
            return StepResult(
                agent=agent,
                success=False,
                duration_seconds=time.monotonic() - t0,
                return_code=-2,
                stderr=f"Command not found: {cmd[0]}",
            )
        except OSError as exc:
            log.error("%s OS error: %s", agent, exc)
            return StepResult(
                agent=agent,
                success=False,
                duration_seconds=time.monotonic() - t0,
                return_code=-3,
                stderr=str(exc),
            )

    # ------------------------------------------------------------------
    # Report reading with synthetic fallbacks
    # ------------------------------------------------------------------

    def _read_manifest(self, task_id: str) -> SayOhmyManifest:
        """Read SAYOHMY manifest, falling back to synthetic if missing/invalid."""
        try:
            result = self._reader.read_manifest()
            if result is not None:
                return result
        except Exception:
            log.warning("Failed to parse SAYOHMY manifest", exc_info=True)
        log.warning("SAYOHMY manifest unavailable -- using synthetic fallback")
        return self._build_synthetic_manifest(task_id)

    def _read_sentinel_report(self, task_id: str) -> SentinelReport:
        """Read SENTINEL report, falling back to synthetic if missing/invalid."""
        try:
            result = self._reader.read_sentinel_report()
            if result is not None:
                return result
        except Exception:
            log.warning("Failed to parse SENTINEL report", exc_info=True)
        log.warning("SENTINEL report unavailable -- using synthetic fallback")
        return self._build_synthetic_sentinel_report(task_id)

    def _read_integration_check(self, task_id: str) -> IntegrationCheck:
        """Read integration check, falling back to synthetic if missing/invalid."""
        try:
            result = self._reader.read_integration_check()
            if result is not None:
                return result
        except Exception:
            log.warning("Failed to parse integration check", exc_info=True)
        log.warning("Integration check unavailable -- using synthetic fallback")
        return self._build_synthetic_integration(task_id)

    # ------------------------------------------------------------------
    # Synthetic report builders (safe defaults, Pydantic-valid)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_synthetic_manifest(task_id: str) -> SayOhmyManifest:
        """Build a minimal valid manifest for fallback.

        Uses 'reviewer' mode as the most conservative synthetic default.
        """
        return SayOhmyManifest(
            task_id=task_id,
            files_produced=[],
            phi_score=0.5,
            mode_used="reviewer",
            psi_sayohmy=_DEFAULT_PSI,
            confidence=0.5,
        )

    @staticmethod
    def _build_synthetic_sentinel_report(task_id: str) -> SentinelReport:
        """Build a fail-closed sentinel report for fallback.

        S07-004: When SENTINEL is unavailable, default to veto=True
        (fail-closed) rather than allowing unaudited code through.
        """
        return SentinelReport(
            task_id=task_id,
            findings=[],
            risk_score=1.0,
            veto=True,
            veto_reason="SENTINEL unavailable -- fail-closed fallback",
            psi_sentinel=_DEFAULT_PSI,
            kill_requested=False,
        )

    @staticmethod
    def _build_synthetic_integration(task_id: str) -> IntegrationCheck:
        """Build a minimal valid integration check for fallback."""
        return IntegrationCheck(
            task_id=task_id,
            cross_checks=[],
            coherence_score=0.5,
            coverage_delta=0.0,
            veto_contested=False,
            psi_te=_DEFAULT_PSI,
        )

    # ------------------------------------------------------------------
    # Metrics extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_metrics(
        manifest: SayOhmyManifest,
        report: SentinelReport,
        integration: IntegrationCheck,
    ) -> dict[str, float]:
        """Extract canonical metrics from pipeline reports.

        Maps report fields to the 7 canonical METRIC_NAMES.  Missing metrics
        are omitted rather than guessed -- PhiScorer handles partial data via
        weight renormalization.

        Mapping:
            security_integrity  <- 1 - report.risk_score
            performance_score   <- manifest.confidence
            coverage_pct        <- integration.coverage_delta (clamped to [0,1])
            complexity_score    <- manifest.phi_score (clamped to [0,1])
            test_ratio          <- integration.coherence_score
        """
        metrics: dict[str, float] = {}

        # security_integrity: inverse of risk score (high risk -> low integrity).
        metrics["security_integrity"] = _clamp01(1.0 - report.risk_score)

        # performance_score: SAYOHMY confidence as proxy.
        metrics["performance_score"] = _clamp01(manifest.confidence)

        # coverage_pct: from integration coverage_delta (only if non-negative).
        if integration.coverage_delta >= 0:
            metrics["coverage_pct"] = _clamp01(integration.coverage_delta)

        # complexity_score: from manifest phi_score (capped at 1.0 since
        # phi_score range is [0, 2.0]).
        metrics["complexity_score"] = _clamp01(manifest.phi_score)

        # test_ratio: from integration coherence_score.
        metrics["test_ratio"] = _clamp01(integration.coherence_score)

        return metrics


def _clamp01(value: float) -> float:
    """Clamp a value to [0.0, 1.0]."""
    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return value
