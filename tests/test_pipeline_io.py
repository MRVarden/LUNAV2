"""Tests for luna.pipeline — PipelineReader, PipelineWriter, PipelinePoller.

15 tests covering JSON read/write, error handling, polling, and round-trip fidelity.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from luna_common.schemas import (
    CurrentTask,
    Decision,
    InfoGradient,
    IntegrationCheck,
    PsiState,
    SayOhmyManifest,
    SentinelReport,
)
from luna.pipeline.pipeline_io import PipelinePoller, PipelineReader, PipelineWriter

# ===================================================================
#  Shared PsiState fixtures
# ===================================================================

_PSI_LUNA = PsiState(perception=0.25, reflexion=0.35, integration=0.25, expression=0.15)
_PSI_SAYOHMY = PsiState(perception=0.15, reflexion=0.15, integration=0.20, expression=0.50)
_PSI_SENTINEL = PsiState(perception=0.50, reflexion=0.20, integration=0.20, expression=0.10)
_PSI_TE = PsiState(perception=0.15, reflexion=0.20, integration=0.50, expression=0.15)


# ===================================================================
#  Fixtures
# ===================================================================


@pytest.fixture
def pipeline_root(tmp_path: Path) -> Path:
    root = tmp_path / "pipeline"
    root.mkdir()
    return root


@pytest.fixture
def writer(pipeline_root: Path) -> PipelineWriter:
    return PipelineWriter(pipeline_root)


@pytest.fixture
def reader(pipeline_root: Path) -> PipelineReader:
    return PipelineReader(pipeline_root)


@pytest.fixture
def sample_task() -> CurrentTask:
    return CurrentTask(
        task_id="PIPE-001",
        description="Test pipeline round-trip",
        context={"source": "unit_test"},
        psi_luna=_PSI_LUNA,
        priority="normal",
    )


@pytest.fixture
def sample_manifest() -> SayOhmyManifest:
    return SayOhmyManifest(
        task_id="PIPE-001",
        files_produced=["luna/pipeline/pipeline_io.py"],
        phi_score=0.72,
        mode_used="architect",
        psi_sayohmy=_PSI_SAYOHMY,
        confidence=0.85,
    )


@pytest.fixture
def sample_sentinel() -> SentinelReport:
    return SentinelReport(
        task_id="PIPE-001",
        findings=[],
        risk_score=0.1,
        veto=False,
        psi_sentinel=_PSI_SENTINEL,
        scanners_used=["bandit"],
    )


@pytest.fixture
def sample_integration() -> IntegrationCheck:
    return IntegrationCheck(
        task_id="PIPE-001",
        cross_checks=[],
        coherence_score=0.80,
        coverage_delta=0.05,
        veto_contested=False,
        psi_te=_PSI_TE,
    )


@pytest.fixture
def sample_decision() -> Decision:
    return Decision(
        task_id="PIPE-001",
        approved=True,
        reason="All checks passed",
        psi_before=_PSI_LUNA,
        psi_after=_PSI_LUNA,
        info_gradient=InfoGradient(
            delta_mem=0.1, delta_phi=0.2, delta_iit=0.3, delta_out=0.4
        ),
        phase="FUNCTIONAL",
        quality_score=0.75,
    )


# ===================================================================
#  1-3. PipelineWriter
# ===================================================================


class TestPipelineWriter:

    def test_writer_creates_current_task_json(
        self, writer: PipelineWriter, sample_task: CurrentTask, pipeline_root: Path
    ):
        """Writer creates a valid current_task.json."""
        path = writer.write_current_task(sample_task)
        assert path.exists()
        assert path.name == "current_task.json"
        data = json.loads(path.read_text())
        assert data["task_id"] == "PIPE-001"
        # Round-trip: re-parse must succeed
        CurrentTask.model_validate(data)

    def test_writer_creates_decision_json(
        self, writer: PipelineWriter, sample_decision: Decision, pipeline_root: Path
    ):
        """Writer creates a valid decision.json."""
        path = writer.write_decision(sample_decision)
        assert path.exists()
        assert path.name == "decision.json"
        data = json.loads(path.read_text())
        assert data["task_id"] == "PIPE-001"
        assert data["approved"] is True
        Decision.model_validate(data)

    def test_writer_overwrites_existing(
        self, writer: PipelineWriter, sample_task: CurrentTask, pipeline_root: Path
    ):
        """Writer overwrites (not appends) on repeated writes."""
        writer.write_current_task(sample_task)
        # Modify and write again
        task2 = CurrentTask(
            task_id="PIPE-002",
            description="Second write",
            context={},
            psi_luna=_PSI_LUNA,
        )
        path = writer.write_current_task(task2)
        data = json.loads(path.read_text())
        assert data["task_id"] == "PIPE-002"
        assert data["description"] == "Second write"


# ===================================================================
#  4-11. PipelineReader
# ===================================================================


class TestPipelineReader:

    def test_reader_manifest_exists(
        self, reader: PipelineReader, pipeline_root: Path, sample_manifest: SayOhmyManifest
    ):
        """Reader parses a valid sayohmy_manifest.json."""
        (pipeline_root / "sayohmy_manifest.json").write_text(
            sample_manifest.model_dump_json(), encoding="utf-8"
        )
        result = reader.read_manifest()
        assert result is not None
        assert isinstance(result, SayOhmyManifest)
        assert result.task_id == "PIPE-001"

    def test_reader_manifest_missing(self, reader: PipelineReader):
        """Reader returns None when manifest is missing."""
        assert reader.read_manifest() is None

    def test_reader_sentinel_report_exists(
        self, reader: PipelineReader, pipeline_root: Path, sample_sentinel: SentinelReport
    ):
        """Reader parses a valid sentinel_report.json."""
        (pipeline_root / "sentinel_report.json").write_text(
            sample_sentinel.model_dump_json(), encoding="utf-8"
        )
        result = reader.read_sentinel_report()
        assert result is not None
        assert isinstance(result, SentinelReport)
        assert result.veto is False

    def test_reader_sentinel_report_missing(self, reader: PipelineReader):
        """Reader returns None when sentinel_report is missing."""
        assert reader.read_sentinel_report() is None

    def test_reader_integration_check_exists(
        self, reader: PipelineReader, pipeline_root: Path, sample_integration: IntegrationCheck
    ):
        """Reader parses a valid integration_check.json."""
        (pipeline_root / "integration_check.json").write_text(
            sample_integration.model_dump_json(), encoding="utf-8"
        )
        result = reader.read_integration_check()
        assert result is not None
        assert isinstance(result, IntegrationCheck)
        assert result.coherence_score == pytest.approx(0.80)

    def test_reader_integration_check_missing(self, reader: PipelineReader):
        """Reader returns None when integration_check is missing."""
        assert reader.read_integration_check() is None

    def test_reader_invalid_json_raises(self, reader: PipelineReader, pipeline_root: Path):
        """Malformed JSON raises ValueError."""
        (pipeline_root / "sayohmy_manifest.json").write_text(
            "{not valid json!!!", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="Malformed JSON"):
            reader.read_manifest()

    def test_reader_schema_mismatch_raises(self, reader: PipelineReader, pipeline_root: Path):
        """Valid JSON but missing required fields raises ValidationError."""
        (pipeline_root / "sayohmy_manifest.json").write_text(
            json.dumps({"task_id": "X", "irrelevant": True}), encoding="utf-8"
        )
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            reader.read_manifest()


# ===================================================================
#  12-15. PipelinePoller
# ===================================================================


class TestPipelinePoller:

    def test_poller_timeout(self, reader: PipelineReader, pipeline_root: Path):
        """Poller raises TimeoutError when files never appear."""
        writer = PipelineWriter(pipeline_root)
        engine = MagicMock()
        poller = PipelinePoller(
            reader=reader, writer=writer, engine=engine,
            poll_interval=0.01, timeout=0.05,
        )
        with pytest.raises(TimeoutError, match="manifest"):
            poller.poll_cycle()

    def test_poller_sequential_wait(
        self,
        reader: PipelineReader,
        pipeline_root: Path,
        sample_manifest: SayOhmyManifest,
        sample_sentinel: SentinelReport,
        sample_integration: IntegrationCheck,
    ):
        """Poller waits manifest → sentinel → integration in strict order."""
        writer = PipelineWriter(pipeline_root)
        mock_engine = MagicMock()
        mock_decision = Decision(
            task_id="PIPE-001",
            approved=True,
            reason="ok",
            psi_before=_PSI_LUNA,
            psi_after=_PSI_LUNA,
            info_gradient=InfoGradient(),
            phase="FUNCTIONAL",
        )
        mock_engine.process_pipeline_result.return_value = mock_decision

        arrival_order: list[str] = []

        def drop_files():
            """Simulate agents writing files with small delays."""
            time.sleep(0.03)
            (pipeline_root / "sayohmy_manifest.json").write_text(
                sample_manifest.model_dump_json(), encoding="utf-8"
            )
            arrival_order.append("manifest")

            time.sleep(0.03)
            (pipeline_root / "sentinel_report.json").write_text(
                sample_sentinel.model_dump_json(), encoding="utf-8"
            )
            arrival_order.append("sentinel")

            time.sleep(0.03)
            (pipeline_root / "integration_check.json").write_text(
                sample_integration.model_dump_json(), encoding="utf-8"
            )
            arrival_order.append("integration")

        t = threading.Thread(target=drop_files)
        t.start()

        poller = PipelinePoller(
            reader=reader, writer=writer, engine=mock_engine,
            poll_interval=0.01, timeout=2.0,
        )
        decision = poller.poll_cycle()
        t.join()

        assert arrival_order == ["manifest", "sentinel", "integration"]
        assert decision.approved is True
        mock_engine.process_pipeline_result.assert_called_once()

    def test_poller_full_cycle(
        self,
        pipeline_root: Path,
        sample_manifest: SayOhmyManifest,
        sample_sentinel: SentinelReport,
        sample_integration: IntegrationCheck,
    ):
        """Full cycle: writes task, reads 3 reports, produces Decision."""
        # Pre-write all 3 agent reports
        (pipeline_root / "sayohmy_manifest.json").write_text(
            sample_manifest.model_dump_json(), encoding="utf-8"
        )
        (pipeline_root / "sentinel_report.json").write_text(
            sample_sentinel.model_dump_json(), encoding="utf-8"
        )
        (pipeline_root / "integration_check.json").write_text(
            sample_integration.model_dump_json(), encoding="utf-8"
        )

        reader = PipelineReader(pipeline_root)
        writer = PipelineWriter(pipeline_root)

        mock_decision = Decision(
            task_id="PIPE-001",
            approved=True,
            reason="All clear",
            psi_before=_PSI_LUNA,
            psi_after=_PSI_LUNA,
            info_gradient=InfoGradient(),
            phase="SOLID",
            quality_score=0.85,
        )
        mock_engine = MagicMock()
        mock_engine.process_pipeline_result.return_value = mock_decision

        poller = PipelinePoller(
            reader=reader, writer=writer, engine=mock_engine,
            poll_interval=0.01, timeout=1.0,
        )
        decision = poller.poll_cycle()

        assert decision.task_id == "PIPE-001"
        assert decision.approved is True
        # decision.json should exist
        decision_path = pipeline_root / "decision.json"
        assert decision_path.exists()
        roundtrip = Decision.model_validate_json(decision_path.read_text())
        assert roundtrip.task_id == "PIPE-001"

    def test_poller_roundtrip_json_fidelity(
        self,
        writer: PipelineWriter,
        reader: PipelineReader,
        pipeline_root: Path,
        sample_task: CurrentTask,
        sample_manifest: SayOhmyManifest,
        sample_sentinel: SentinelReport,
        sample_integration: IntegrationCheck,
    ):
        """Write → Read → Write cycle preserves data exactly."""
        # Write current task via writer
        writer.write_current_task(sample_task)
        task_data = json.loads((pipeline_root / "current_task.json").read_text())
        assert task_data["task_id"] == sample_task.task_id

        # Write agent files directly (simulating agents)
        (pipeline_root / "sayohmy_manifest.json").write_text(
            sample_manifest.model_dump_json(), encoding="utf-8"
        )
        (pipeline_root / "sentinel_report.json").write_text(
            sample_sentinel.model_dump_json(), encoding="utf-8"
        )
        (pipeline_root / "integration_check.json").write_text(
            sample_integration.model_dump_json(), encoding="utf-8"
        )

        # Read back via reader
        m = reader.read_manifest()
        s = reader.read_sentinel_report()
        ic = reader.read_integration_check()

        assert m is not None and s is not None and ic is not None
        assert m.task_id == sample_manifest.task_id
        assert m.phi_score == pytest.approx(sample_manifest.phi_score)
        assert s.risk_score == pytest.approx(sample_sentinel.risk_score)
        assert ic.coherence_score == pytest.approx(sample_integration.coherence_score)

        # Re-write manifest and read again — data fidelity
        (pipeline_root / "sayohmy_manifest.json").write_text(
            m.model_dump_json(), encoding="utf-8"
        )
        m2 = reader.read_manifest()
        assert m2 is not None
        assert m2.model_dump() == m.model_dump()
