"""Pipeline I/O — filesystem bus between Luna and the 3 agents.

Reads/writes JSON files in pipeline_root/ to connect
LunaEngine with SayOhMy, SENTINEL, and Test-Engineer.

File layout:
    pipeline_root/
        current_task.json         <- Luna writes
        sayohmy_manifest.json     <- SayOhMy writes
        sentinel_report.json      <- SENTINEL writes
        integration_check.json    <- Test-Engineer writes
        decision.json             <- Luna writes (after processing)
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from luna_common.schemas import (
    CurrentTask,
    Decision,
    IntegrationCheck,
    SayOhmyManifest,
    SentinelReport,
)

log = logging.getLogger(__name__)

# Canonical filenames — no user-controlled path components.
_CURRENT_TASK_FILE = "current_task.json"
_MANIFEST_FILE = "sayohmy_manifest.json"
_SENTINEL_FILE = "sentinel_report.json"
_INTEGRATION_FILE = "integration_check.json"
_DECISION_FILE = "decision.json"


class PipelineWriter:
    """Writes current_task.json and decision.json into pipeline_root."""

    def __init__(self, pipeline_root: Path) -> None:
        self._root = Path(pipeline_root)

    def write_current_task(self, task: CurrentTask) -> Path:
        """Serialize and write a CurrentTask to JSON. Returns the file path."""
        return self._write(task, _CURRENT_TASK_FILE)

    def write_decision(self, decision: Decision) -> Path:
        """Serialize and write a Decision to JSON. Returns the file path."""
        return self._write(decision, _DECISION_FILE)

    def _write(self, model: CurrentTask | Decision, filename: str) -> Path:
        """Atomic-ish write: write to .tmp then rename."""
        self._root.mkdir(parents=True, exist_ok=True)
        target = self._root / filename
        tmp = target.with_suffix(".json.tmp")
        data = model.model_dump_json(indent=2)
        tmp.write_text(data, encoding="utf-8")
        tmp.rename(target)
        log.debug("Wrote %s (%d bytes)", target, len(data))
        return target


class PipelineReader:
    """Reads JSON files from the 3 agents and parses them into Pydantic models."""

    def __init__(self, pipeline_root: Path) -> None:
        self._root = Path(pipeline_root)

    def read_manifest(self) -> SayOhmyManifest | None:
        """Read and parse sayohmy_manifest.json, or None if missing."""
        return self._read(SayOhmyManifest, _MANIFEST_FILE)

    def read_sentinel_report(self) -> SentinelReport | None:
        """Read and parse sentinel_report.json, or None if missing."""
        return self._read(SentinelReport, _SENTINEL_FILE)

    def read_integration_check(self) -> IntegrationCheck | None:
        """Read and parse integration_check.json, or None if missing."""
        return self._read(IntegrationCheck, _INTEGRATION_FILE)

    def _read(self, model_cls: type, filename: str):
        """Read a JSON file and parse it into the given Pydantic model.

        Returns None if the file does not exist.
        Raises ValueError on malformed JSON.
        Raises pydantic.ValidationError on schema mismatch.
        """
        path = self._root / filename
        if not path.exists():
            return None
        raw = path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Malformed JSON in {path}: {exc}"
            ) from exc
        return model_cls.model_validate(data)


class PipelinePoller:
    """Synchronous polling loop — waits for the 3 agent reports then calls LunaEngine.

    Follows the strict sequential order: ψ₄(manifest) → ψ₁(sentinel) → ψ₃(integration).
    """

    def __init__(
        self,
        reader: PipelineReader,
        writer: PipelineWriter,
        engine: "LunaEngine",  # noqa: F821 — forward ref
        poll_interval: float = 1.0,
        timeout: float = 300.0,
    ) -> None:
        self.reader = reader
        self.writer = writer
        self.engine = engine
        self.poll_interval = poll_interval
        self.timeout = timeout

    def poll_cycle(self) -> Decision:
        """Wait for all 3 reports in sequential order, process, and write Decision.

        Raises TimeoutError if any report is not available within self.timeout.
        """
        manifest = self._wait_for("manifest", self.reader.read_manifest)
        sentinel = self._wait_for("sentinel_report", self.reader.read_sentinel_report)
        integration = self._wait_for(
            "integration_check", self.reader.read_integration_check
        )

        log.info(
            "All 3 reports received for task=%s — processing",
            manifest.task_id,
        )

        decision = self.engine.process_pipeline_result(
            manifest=manifest,
            sentinel_report=sentinel,
            integration_check=integration,
        )

        self.writer.write_decision(decision)
        log.info("Decision written: approved=%s", decision.approved)
        return decision

    def run(self, max_cycles: int | None = None) -> None:
        """Run poll_cycle repeatedly. Stops after max_cycles (None = infinite)."""
        cycle = 0
        while max_cycles is None or cycle < max_cycles:
            log.info("Starting poll cycle %d", cycle)
            self.poll_cycle()
            cycle += 1

    def _wait_for(self, name: str, read_fn) -> object:
        """Poll until read_fn() returns a non-None value, or timeout."""
        deadline = time.monotonic() + self.timeout
        while True:
            result = read_fn()
            if result is not None:
                log.debug("Received %s", name)
                return result
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Timed out waiting for {name} "
                    f"after {self.timeout:.1f}s"
                )
            time.sleep(self.poll_interval)
