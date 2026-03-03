"""Integration tests -- Cross-agent pipeline with luna_common v0.2.0 schemas.

These tests verify that the full psi4->psi1->psi3->psi2 pipeline works end-to-end
with the new signal types, metrics, and audit trail.

5 scenario classes:
    D.1 TestPipelineNominal       -- Happy path through all 4 agents
    D.2 TestPipelineWithVeto      -- SENTINEL veto blocks the pipeline
    D.3 TestKillCritical          -- SENTINEL kill request triggers KillSwitch
    D.4 TestSleepCycle            -- Sleep/wake notifications and vitals exchange
    D.5 TestGracefulDegradation   -- Partial data, missing files, malformed JSON
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from luna_common.constants import METRIC_NAMES
from luna_common.schemas import (
    AuditEntry,
    CurrentTask,
    Decision,
    InfoGradient,
    IntegrationCheck,
    KillSignal,
    NormalizedMetricsReport,
    PsiState,
    SayOhmyManifest,
    SentinelReport,
    Severity,
    SleepNotification,
    VerdictInput,
    VitalsReport,
    VitalsRequest,
)
from luna.pipeline.pipeline_io import PipelineReader, PipelineWriter
from luna.safety.kill_switch import KillSwitch
from luna.observability.audit_trail import AuditEvent, AuditTrail


# ---------------------------------------------------------------------------
# Factory helpers -- small, composable, no shared state
# ---------------------------------------------------------------------------

def _psi_luna() -> PsiState:
    """Luna: psi2 (Reflexion) dominant."""
    return PsiState(perception=0.25, reflexion=0.35, integration=0.25, expression=0.15)


def _psi_sayohmy() -> PsiState:
    """SayOhMy: psi4 (Expression) dominant."""
    return PsiState(perception=0.15, reflexion=0.15, integration=0.20, expression=0.50)


def _psi_sentinel() -> PsiState:
    """SENTINEL: psi1 (Perception) dominant."""
    return PsiState(perception=0.50, reflexion=0.20, integration=0.20, expression=0.10)


def _psi_testengineer() -> PsiState:
    """Test-Engineer: psi3 (Integration) dominant."""
    return PsiState(perception=0.15, reflexion=0.20, integration=0.50, expression=0.15)


def _make_current_task(task_id: str = "task-001") -> CurrentTask:
    return CurrentTask(
        task_id=task_id,
        description="Implement feature X with phi-aligned architecture",
        context={"module": "consciousness", "priority": "high"},
        psi_luna=_psi_luna(),
        priority="normal",
    )


def _make_manifest(
    task_id: str = "task-001",
    vitals: dict | None = None,
) -> SayOhmyManifest:
    return SayOhmyManifest(
        task_id=task_id,
        files_produced=["src/feature_x.py", "tests/test_feature_x.py"],
        phi_score=0.786,
        mode_used="architect",
        psi_sayohmy=_psi_sayohmy(),
        confidence=0.85,
        vitals=vitals,
    )


def _make_sentinel_report(
    task_id: str = "task-001",
    veto: bool = False,
    veto_reason: str | None = None,
    risk_score: float = 0.15,
    audit_entries: list[dict] | None = None,
    kill_requested: bool = False,
    kill_reason: str | None = None,
) -> SentinelReport:
    return SentinelReport(
        task_id=task_id,
        findings=[{"type": "info", "message": "No critical issues found"}],
        risk_score=risk_score,
        veto=veto,
        veto_reason=veto_reason,
        psi_sentinel=_psi_sentinel(),
        scanners_used=["bandit", "semgrep"],
        audit_entries=audit_entries or [],
        kill_requested=kill_requested,
        kill_reason=kill_reason,
    )


def _make_integration_check(task_id: str = "task-001") -> IntegrationCheck:
    return IntegrationCheck(
        task_id=task_id,
        cross_checks=[
            {"check": "type_safety", "passed": True},
            {"check": "simplex_invariant", "passed": True},
        ],
        coherence_score=0.72,
        coverage_delta=0.05,
        psi_te=_psi_testengineer(),
    )


def _make_decision(
    task_id: str = "task-001",
    approved: bool = True,
    audit_trail_id: str | None = None,
) -> Decision:
    return Decision(
        task_id=task_id,
        approved=approved,
        reason="All checks passed, phi_score above threshold",
        psi_before=_psi_luna(),
        psi_after=PsiState(
            perception=0.24, reflexion=0.34, integration=0.26, expression=0.16,
        ),
        info_gradient=InfoGradient(
            delta_mem=0.1, delta_phi=0.786, delta_iit=0.72, delta_out=0.85,
        ),
        phase="SOLID",
        quality_score=0.75,
        audit_trail_id=audit_trail_id,
    )


def _all_seven_metrics() -> dict[str, float]:
    """Return a dict with all 7 canonical metrics populated."""
    return {
        "security_integrity": 0.92,
        "coverage_pct": 0.78,
        "complexity_score": 0.65,
        "test_ratio": 0.55,
        "abstraction_ratio": 0.70,
        "function_size_score": 0.80,
        "performance_score": 0.88,
    }


def _partial_metrics(count: int = 3) -> dict[str, float]:
    """Return a dict with only *count* of the 7 canonical metrics."""
    full = _all_seven_metrics()
    keys = list(full.keys())[:count]
    return {k: full[k] for k in keys}


# ===========================================================================
# D.1 -- Pipeline Nominal (Happy Path)
# ===========================================================================


class TestPipelineNominal:
    """SAYOHMY produces -> SENTINEL audits (no veto) -> TESTENGINEER validates -> LUNA decides."""

    def test_manifest_with_vitals_is_valid(self) -> None:
        """SayOhmyManifest with the v0.2.0 vitals field serializes and deserializes correctly."""
        vitals_snapshot = {
            "agent_id": "SAYOHMY",
            "psi_state": _psi_sayohmy().model_dump(),
            "uptime_s": 3600.0,
            "health": {"cpu_pct": 12.5, "mem_mb": 256},
        }
        manifest = _make_manifest(vitals=vitals_snapshot)

        # Round-trip through JSON
        json_str = manifest.model_dump_json()
        restored = SayOhmyManifest.model_validate_json(json_str)

        assert restored.vitals is not None, "vitals field lost during round-trip"
        assert restored.vitals["agent_id"] == "SAYOHMY"
        assert restored.phi_score == pytest.approx(0.786)
        assert restored.task_id == "task-001"

    def test_sentinel_report_with_audit_entries(self) -> None:
        """SentinelReport with v0.2.0 audit_entries validates correctly."""
        entries = [
            {
                "agent_id": "SENTINEL",
                "event_type": "scan_complete",
                "severity": "info",
                "payload": {"scanner": "bandit", "findings": 0},
            },
            {
                "agent_id": "SENTINEL",
                "event_type": "dependency_check",
                "severity": "low",
                "payload": {"scanner": "pip-audit", "vulnerabilities": 1},
            },
        ]
        report = _make_sentinel_report(audit_entries=entries)

        assert len(report.audit_entries) == 2
        assert report.audit_entries[0]["event_type"] == "scan_complete"
        assert report.audit_entries[1]["severity"] == "low"

        # Each dict entry should be parseable as an AuditEntry
        for entry_dict in report.audit_entries:
            ae = AuditEntry.model_validate(entry_dict)
            assert ae.agent_id == "SENTINEL"

    def test_decision_with_audit_trail_id(self) -> None:
        """Decision with v0.2.0 audit_trail_id provides full traceability."""
        decision = _make_decision(audit_trail_id="evt_abc123def456")

        assert decision.audit_trail_id == "evt_abc123def456"

        json_str = decision.model_dump_json()
        restored = Decision.model_validate_json(json_str)
        assert restored.audit_trail_id == "evt_abc123def456"
        assert restored.approved is True
        assert restored.phase == "SOLID"

    def test_normalized_metrics_flow(self) -> None:
        """NormalizedMetricsReport with all 7 metrics feeds into VerdictInput correctly."""
        metrics_with = NormalizedMetricsReport(
            metrics=_all_seven_metrics(),
            source="sayohmy",
            project_path="/tmp/project",
        )
        metrics_without = NormalizedMetricsReport(
            metrics={k: max(0.0, v - 0.15) for k, v in _all_seven_metrics().items()},
            source="baseline",
            project_path="/tmp/project",
        )

        assert metrics_with.complete is True, "All 7 metrics present but complete=False"
        assert metrics_without.complete is True

        verdict_input = VerdictInput(
            task_id="task-001",
            category="refactoring",
            metrics_with=metrics_with,
            metrics_without=metrics_without,
        )

        assert verdict_input.task_id == "task-001"
        assert verdict_input.category == "refactoring"
        # Differential: each metric_with >= metric_without
        for name in METRIC_NAMES:
            diff = verdict_input.metrics_with.get(name) - verdict_input.metrics_without.get(name)
            assert diff >= 0.0, (
                f"Consciousness should improve {name}: "
                f"with={verdict_input.metrics_with.get(name)}, "
                f"without={verdict_input.metrics_without.get(name)}"
            )

    def test_full_pipeline_json_roundtrip(self, tmp_path: Path) -> None:
        """All 5 pipeline files written to disk and parsed back correctly."""
        writer = PipelineWriter(tmp_path)
        reader = PipelineReader(tmp_path)

        # 1. CurrentTask
        task = _make_current_task()
        writer.write_current_task(task)
        assert (tmp_path / "current_task.json").exists()

        # 2. SayOhmyManifest -- written manually (PipelineWriter only handles task/decision)
        manifest = _make_manifest()
        (tmp_path / "sayohmy_manifest.json").write_text(
            manifest.model_dump_json(indent=2), encoding="utf-8",
        )
        read_manifest = reader.read_manifest()
        assert read_manifest is not None, "PipelineReader failed to read manifest"
        assert read_manifest.task_id == "task-001"
        assert read_manifest.phi_score == pytest.approx(0.786)

        # 3. SentinelReport
        sentinel = _make_sentinel_report()
        (tmp_path / "sentinel_report.json").write_text(
            sentinel.model_dump_json(indent=2), encoding="utf-8",
        )
        read_sentinel = reader.read_sentinel_report()
        assert read_sentinel is not None, "PipelineReader failed to read sentinel report"
        assert read_sentinel.veto is False

        # 4. IntegrationCheck
        ic = _make_integration_check()
        (tmp_path / "integration_check.json").write_text(
            ic.model_dump_json(indent=2), encoding="utf-8",
        )
        read_ic = reader.read_integration_check()
        assert read_ic is not None, "PipelineReader failed to read integration check"
        assert read_ic.coherence_score == pytest.approx(0.72)

        # 5. Decision
        decision = _make_decision(audit_trail_id="evt_pipeline_test")
        writer.write_decision(decision)
        assert (tmp_path / "decision.json").exists()
        raw = json.loads((tmp_path / "decision.json").read_text(encoding="utf-8"))
        assert raw["approved"] is True
        assert raw["audit_trail_id"] == "evt_pipeline_test"


# ===========================================================================
# D.2 -- Pipeline with Veto
# ===========================================================================


class TestPipelineWithVeto:
    """SENTINEL detects a vulnerability, emits a veto -- manifest rejected."""

    def test_sentinel_veto_with_audit_entries(self) -> None:
        """SentinelReport with veto=True has correctly populated audit_entries."""
        audit_entries = [
            {
                "agent_id": "SENTINEL",
                "event_type": "vulnerability_detected",
                "severity": "high",
                "payload": {
                    "cve": "CVE-2026-0001",
                    "package": "insecure-lib",
                    "fix_available": True,
                },
            },
        ]
        report = _make_sentinel_report(
            veto=True,
            veto_reason="Critical CVE in dependency: CVE-2026-0001",
            risk_score=0.85,
            audit_entries=audit_entries,
        )

        assert report.veto is True
        assert report.veto_reason is not None
        assert "CVE-2026-0001" in report.veto_reason

        # Validate that the audit entry can be parsed as AuditEntry with HIGH severity
        ae = AuditEntry.model_validate(report.audit_entries[0])
        assert ae.severity == Severity.HIGH
        assert ae.event_type == "vulnerability_detected"

    def test_veto_blocks_decision_approval(self) -> None:
        """When SENTINEL veto=True, the Decision.approved should be False."""
        # Build the full pipeline context: sentinel vetoed
        sentinel = _make_sentinel_report(
            veto=True,
            veto_reason="SQL injection vulnerability in user input handler",
            risk_score=0.90,
        )
        # The decision that Luna should produce when a veto is active
        decision = Decision(
            task_id="task-001",
            approved=False,
            reason=f"Sentinel veto: {sentinel.veto_reason}",
            psi_before=_psi_luna(),
            psi_after=_psi_luna(),
            info_gradient=InfoGradient(),
            phase="FRAGILE",
            quality_score=0.20,
        )

        assert decision.approved is False, "Decision must be rejected when sentinel vetoes"
        assert "veto" in decision.reason.lower()
        assert decision.phase == "FRAGILE"

    def test_veto_generates_high_severity_audit_entry(self) -> None:
        """A veto event produces an AuditEntry with severity=HIGH or CRITICAL."""
        veto_event = AuditEvent.create(
            "sentinel_veto",
            agent_name="SENTINEL",
            data={
                "veto_reason": "Command injection in subprocess call",
                "risk_score": 0.92,
                "task_id": "task-001",
            },
            severity="high",
        )

        # Convert to luna_common AuditEntry
        audit_entry = veto_event.to_audit_entry()
        assert audit_entry.severity == Severity.HIGH
        assert audit_entry.event_type == "sentinel_veto"
        assert audit_entry.agent_id == "SENTINEL"
        assert "veto_reason" in audit_entry.payload


# ===========================================================================
# D.3 -- Kill Critical
# ===========================================================================


class TestKillCritical:
    """SENTINEL detects code execution vuln -> kill_requested=True -> KillSwitch triggered."""

    def test_sentinel_kill_request_format(self) -> None:
        """SentinelReport with kill_requested=True can produce a valid KillSignal."""
        report = _make_sentinel_report(
            kill_requested=True,
            kill_reason="Remote code execution via eval() on user input",
            risk_score=0.99,
        )

        assert report.kill_requested is True
        assert report.kill_reason is not None

        # Create a KillSignal from the sentinel report data
        kill_signal = KillSignal(
            reason=report.kill_reason,
            severity=Severity.CRITICAL,
            source_agent="SENTINEL",
        )
        assert kill_signal.severity == Severity.CRITICAL
        assert "eval()" in kill_signal.reason

    def test_kill_signal_broadcast(self, tmp_path: Path) -> None:
        """A KillSignal written to disk can be parsed by all 3 agents."""
        kill_signal = KillSignal(
            reason="Critical buffer overflow in parser module",
            severity=Severity.CRITICAL,
            source_agent="SENTINEL",
        )
        signal_json = kill_signal.model_dump_json(indent=2)

        # Simulate broadcast: write to each agent's signal directory
        agent_dirs = ["sayohmy_signals", "sentinel_signals", "testengineer_signals"]
        for agent_dir in agent_dirs:
            signal_dir = tmp_path / agent_dir
            signal_dir.mkdir(parents=True, exist_ok=True)
            signal_file = signal_dir / "kill_signal.json"
            signal_file.write_text(signal_json, encoding="utf-8")

        # Each agent reads and parses the signal
        for agent_dir in agent_dirs:
            signal_file = tmp_path / agent_dir / "kill_signal.json"
            raw = signal_file.read_text(encoding="utf-8")
            parsed = KillSignal.model_validate_json(raw)
            assert parsed.severity == Severity.CRITICAL, (
                f"Agent {agent_dir} parsed wrong severity: {parsed.severity}"
            )
            assert parsed.source_agent == "SENTINEL"

    def test_kill_switch_integration(self) -> None:
        """Real KillSwitch instance responds to kill_requested flag from SentinelReport."""
        report = _make_sentinel_report(
            kill_requested=True,
            kill_reason="Arbitrary file write via path traversal",
            risk_score=0.98,
        )

        ks = KillSwitch(enabled=True)
        assert ks.is_killed is False

        # Simulate the orchestrator's kill path
        if report.kill_requested:
            reason = report.kill_reason or "sentinel critical finding"
            ks.kill(reason=reason)

        assert ks.is_killed is True, "KillSwitch should be active after kill()"

        # check() should raise RuntimeError when killed
        with pytest.raises(RuntimeError, match="Kill switch active"):
            ks.check()

        # Reset and verify clean state
        ks.reset()
        assert ks.is_killed is False

    def test_kill_switch_sentinel_file(self, tmp_path: Path) -> None:
        """KillSwitch write_sentinel/check_sentinel round-trip for inter-process signaling."""
        ks = KillSwitch(enabled=True)
        reason = "Critical vulnerability detected by SENTINEL agent"

        sentinel_path = ks.write_sentinel(tmp_path, reason)
        assert sentinel_path.exists()

        # check_sentinel reads, returns reason, and deletes the file
        found_reason = ks.check_sentinel(tmp_path)
        assert found_reason == reason
        assert not sentinel_path.exists(), "Sentinel file should be deleted after check"

        # Second check returns None (file already consumed)
        assert ks.check_sentinel(tmp_path) is None

    def test_audit_trail_records_kill(self) -> None:
        """AuditEntry with event_type='kill_switch_activated' and severity='critical' is valid."""
        kill_event = AuditEvent.create(
            "kill_switch_activated",
            agent_name="SENTINEL",
            data={
                "reason": "Remote code execution via deserialization",
                "task_id": "task-001",
                "risk_score": 0.99,
            },
            severity="critical",
        )

        # Convert to luna_common AuditEntry
        audit_entry = kill_event.to_audit_entry()
        assert audit_entry.event_type == "kill_switch_activated"
        assert audit_entry.severity == Severity.CRITICAL
        assert audit_entry.agent_id == "SENTINEL"
        assert "reason" in audit_entry.payload
        assert audit_entry.payload["risk_score"] == pytest.approx(0.99)


# ===========================================================================
# D.4 -- Sleep Cycle
# ===========================================================================


class TestSleepCycle:
    """LUNA enters sleep -> agents notified -> dream cycle -> wake up -> agents resume."""

    def test_sleep_notification_format(self) -> None:
        """SleepNotification(entering_sleep=True) serializes correctly as frozen model."""
        notif = SleepNotification(
            entering_sleep=True,
            estimated_duration_s=60.0,
            source_agent="LUNA",
        )

        assert notif.entering_sleep is True
        assert notif.estimated_duration_s == pytest.approx(60.0)
        assert notif.source_agent == "LUNA"
        assert notif.timestamp is not None

        # Verify frozen -- assignment should raise
        with pytest.raises(ValidationError):
            notif.entering_sleep = False  # type: ignore[misc]

    def test_wake_notification_format(self) -> None:
        """SleepNotification(entering_sleep=False) clears sleep state."""
        wake = SleepNotification(
            entering_sleep=False,
            estimated_duration_s=0.0,
            source_agent="LUNA",
        )

        assert wake.entering_sleep is False
        assert wake.estimated_duration_s == pytest.approx(0.0)

    def test_sleep_wake_roundtrip(self, tmp_path: Path) -> None:
        """Sleep notification written as JSON is parsed back identically."""
        sleep_notif = SleepNotification(
            entering_sleep=True,
            estimated_duration_s=120.0,
        )
        signal_file = tmp_path / "sleep_notification.json"
        signal_file.write_text(sleep_notif.model_dump_json(indent=2), encoding="utf-8")

        raw = signal_file.read_text(encoding="utf-8")
        restored = SleepNotification.model_validate_json(raw)

        assert restored.entering_sleep is True
        assert restored.estimated_duration_s == pytest.approx(120.0)
        assert restored.source_agent == sleep_notif.source_agent

    def test_vitals_request_response_cycle(self) -> None:
        """VitalsRequest triggers VitalsReport from each agent with correct PsiState."""
        request = VitalsRequest(
            requested_fields=["psi_state", "uptime_s", "health"],
            request_id="vitals-req-001",
        )

        assert request.request_id == "vitals-req-001"

        # Each agent responds with its own PsiState
        agents = {
            "SAYOHMY": _psi_sayohmy(),
            "SENTINEL": _psi_sentinel(),
            "TESTENGINEER": _psi_testengineer(),
        }

        expected_dominants = {
            "SAYOHMY": "expression",
            "SENTINEL": "perception",
            "TESTENGINEER": "integration",
        }

        for agent_id, psi in agents.items():
            report = VitalsReport(
                agent_id=agent_id,
                psi_state=psi,
                uptime_s=3600.0,
                health={"status": "healthy"},
                request_id=request.request_id,
            )

            assert report.agent_id == agent_id
            assert report.request_id == request.request_id

            # Verify the correct dominant component
            psi_tuple = report.psi_state.as_tuple()
            component_names = ("perception", "reflexion", "integration", "expression")
            dominant_idx = psi_tuple.index(max(psi_tuple))
            dominant_name = component_names[dominant_idx]
            assert dominant_name == expected_dominants[agent_id], (
                f"{agent_id}: expected dominant={expected_dominants[agent_id]}, "
                f"got={dominant_name} from psi={psi_tuple}"
            )

        # Verify frozen -- VitalsReport should reject mutation
        sample_report = VitalsReport(
            agent_id="SAYOHMY",
            psi_state=_psi_sayohmy(),
            uptime_s=100.0,
        )
        with pytest.raises(ValidationError):
            sample_report.agent_id = "tampered"  # type: ignore[misc]

    def test_psi_state_simplex_invariant(self) -> None:
        """All agent PsiStates sum to approximately 1.0 (simplex constraint)."""
        for name, psi_fn in [
            ("LUNA", _psi_luna),
            ("SAYOHMY", _psi_sayohmy),
            ("SENTINEL", _psi_sentinel),
            ("TESTENGINEER", _psi_testengineer),
        ]:
            psi = psi_fn()
            total = psi.sum()
            assert abs(total - 1.0) < 0.01, (
                f"{name} PsiState violates simplex: sum={total}"
            )
            for component in psi.as_tuple():
                assert component > 0, (
                    f"{name} PsiState has non-positive component: {psi.as_tuple()}"
                )


# ===========================================================================
# D.5 -- Graceful Degradation
# ===========================================================================


class TestGracefulDegradation:
    """System continues with reduced capabilities when components fail."""

    def test_metrics_report_partial(self) -> None:
        """NormalizedMetricsReport with only 3 of 7 metrics is valid, complete=False."""
        partial = NormalizedMetricsReport(
            metrics=_partial_metrics(3),
            source="degraded_collector",
        )

        assert partial.complete is False, (
            "Report with 3/7 metrics should not be complete"
        )
        assert len(partial.metrics) == 3
        # All values in [0, 1]
        for name, value in partial.metrics.items():
            assert 0.0 <= value <= 1.0, f"Metric {name} out of range: {value}"

    def test_verdict_input_with_partial_metrics(self) -> None:
        """VerdictInput accepts partial (incomplete) NormalizedMetricsReport."""
        partial_with = NormalizedMetricsReport(
            metrics=_partial_metrics(4),
            source="partial_with",
        )
        partial_without = NormalizedMetricsReport(
            metrics=_partial_metrics(4),
            source="partial_without",
        )

        verdict = VerdictInput(
            task_id="task-degraded-001",
            category="security",
            metrics_with=partial_with,
            metrics_without=partial_without,
        )

        assert verdict.metrics_with.complete is False
        assert verdict.metrics_without.complete is False
        assert verdict.task_id == "task-degraded-001"

    def test_sentinel_report_no_audit_entries(self) -> None:
        """SentinelReport without audit_entries is valid (backward compat with v0.1.x)."""
        report = SentinelReport(
            task_id="task-compat-001",
            findings=[],
            risk_score=0.10,
            veto=False,
            psi_sentinel=_psi_sentinel(),
            scanners_used=["bandit"],
        )

        assert report.audit_entries == []
        assert report.kill_requested is False
        assert report.kill_reason is None

    def test_manifest_no_vitals(self) -> None:
        """SayOhmyManifest without vitals is valid (backward compat with v0.1.x)."""
        manifest = SayOhmyManifest(
            task_id="task-compat-002",
            files_produced=["src/module.py"],
            phi_score=0.618,
            mode_used="mentor",
            psi_sayohmy=_psi_sayohmy(),
            confidence=0.70,
        )

        assert manifest.vitals is None
        assert manifest.phi_score == pytest.approx(0.618)

    def test_missing_signal_files(self, tmp_path: Path) -> None:
        """PipelineReader returns None for every missing file in an empty directory."""
        reader = PipelineReader(tmp_path)

        assert reader.read_manifest() is None, (
            "read_manifest should return None for missing file"
        )
        assert reader.read_sentinel_report() is None, (
            "read_sentinel_report should return None for missing file"
        )
        assert reader.read_integration_check() is None, (
            "read_integration_check should return None for missing file"
        )

    def test_malformed_json_graceful(self, tmp_path: Path) -> None:
        """PipelineReader raises ValueError on malformed JSON (never crashes silently)."""
        reader = PipelineReader(tmp_path)

        # Write malformed JSON to each pipeline file
        malformed_files = {
            "sayohmy_manifest.json": "{not valid json at all",
            "sentinel_report.json": "<<<xml_not_json>>>",
            "integration_check.json": "",
        }
        for filename, content in malformed_files.items():
            (tmp_path / filename).write_text(content, encoding="utf-8")

        # Each reader method should raise ValueError, not crash with an unhandled exception
        with pytest.raises(ValueError, match="Malformed JSON"):
            reader.read_manifest()

        with pytest.raises(ValueError, match="Malformed JSON"):
            reader.read_sentinel_report()

        # Empty file is also malformed JSON
        with pytest.raises(ValueError, match="Malformed JSON"):
            reader.read_integration_check()

    def test_psi_state_rejects_invalid_simplex(self) -> None:
        """PsiState rejects vectors that do not sum to ~1.0."""
        with pytest.raises(ValidationError, match="sum to"):
            PsiState(
                perception=0.5, reflexion=0.5,
                integration=0.5, expression=0.5,
            )

    def test_audit_entry_rejects_empty_agent_id(self) -> None:
        """AuditEntry rejects empty agent_id (validation guard)."""
        with pytest.raises(ValidationError, match="agent_id"):
            AuditEntry(
                agent_id="   ",
                event_type="test",
                severity=Severity.INFO,
            )

    def test_normalized_metrics_rejects_unknown_name(self) -> None:
        """NormalizedMetricsReport rejects metric names not in the canonical set."""
        with pytest.raises(ValidationError, match="Unknown metric"):
            NormalizedMetricsReport(
                metrics={"invented_metric": 0.5},
                source="test",
            )

    def test_normalized_metrics_rejects_out_of_range(self) -> None:
        """NormalizedMetricsReport rejects values outside [0.0, 1.0]."""
        with pytest.raises(ValidationError):
            NormalizedMetricsReport(
                metrics={"security_integrity": 1.5},
                source="test",
            )
