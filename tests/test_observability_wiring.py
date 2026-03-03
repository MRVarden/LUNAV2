"""Tests for observability wiring in the orchestrator — Session 1 integration.

Validates that orchestrator.start() correctly instantiates and wires:
  - AuditTrail (append-only JSONL event log)
  - RedisMetricsStore (graceful degradation)
  - PrometheusExporter (text format metrics)
  - AlertManager (local webhook notifications)

Tests prove the WIRING is correct — components actually communicate.
No network calls, no LLM, no Docker.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from luna.core.config import (
    ConsciousnessSection,
    HeartbeatSection,
    LunaConfig,
    LunaSection,
    MemorySection,
    ObservabilitySection,
    PipelineSection,
)
from luna.observability.audit_trail import AuditTrail
from luna.observability.prometheus_exporter import PrometheusExporter
from luna.observability.redis_store import RedisMetricsStore
from luna.orchestrator.orchestrator import LunaOrchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Path, **obs_overrides) -> LunaConfig:
    """Build a minimal LunaConfig for observability wiring tests."""
    obs_kw = {
        "audit_trail_file": "data/audit.jsonl",
        "prometheus_enabled": True,
        "redis_url": "",
        "alert_webhook_url": "",
    }
    obs_kw.update(obs_overrides)

    return LunaConfig(
        luna=LunaSection(
            version="test",
            agent_name="LUNA",
            data_dir=str(tmp_path),
            pipeline_dir=str(tmp_path / "pipeline"),
        ),
        consciousness=ConsciousnessSection(
            checkpoint_file="cs.json",
            backup_on_save=False,
        ),
        memory=MemorySection(fractal_root=str(tmp_path / "fractal")),
        pipeline=PipelineSection(root=str(tmp_path / "pipeline")),
        observability=ObservabilitySection(**obs_kw),
        heartbeat=HeartbeatSection(
            interval_seconds=0.01,
            checkpoint_interval=0,
            fingerprint_enabled=False,
        ),
        root_dir=tmp_path,
    )


async def _start_orchestrator(tmp_path: Path, **obs_overrides) -> LunaOrchestrator:
    """Create, start, and return an orchestrator with mocked LLM."""
    cfg = _make_config(tmp_path, **obs_overrides)
    orch = LunaOrchestrator(cfg)
    # Mock LLM creation so no API key is needed.
    with patch(
        "luna.orchestrator.orchestrator.create_provider",
        return_value=None,
    ):
        await orch.start()
    return orch


# ===========================================================================
# Test 1: AuditTrail is wired
# ===========================================================================


class TestAuditTrailWiring:
    """Orchestrator.start() creates and wires an AuditTrail instance."""

    @pytest.mark.asyncio
    async def test_orchestrator_start_wires_audit_trail(self, tmp_path: Path):
        """After start(), orchestrator._audit is a live AuditTrail."""
        orch = await _start_orchestrator(tmp_path)
        try:
            assert orch._audit is not None, (
                "AuditTrail must be instantiated after start()"
            )
            assert isinstance(orch._audit, AuditTrail), (
                f"Expected AuditTrail, got {type(orch._audit).__name__}"
            )
        finally:
            await orch.stop()


# ===========================================================================
# Test 2: PrometheusExporter is wired
# ===========================================================================


class TestPrometheusWiring:
    """Orchestrator.start() creates and wires a PrometheusExporter."""

    @pytest.mark.asyncio
    async def test_orchestrator_start_wires_prometheus(self, tmp_path: Path):
        """After start(), orchestrator._prometheus is a live PrometheusExporter."""
        orch = await _start_orchestrator(tmp_path)
        try:
            assert orch._prometheus is not None, (
                "PrometheusExporter must be instantiated after start()"
            )
            assert isinstance(orch._prometheus, PrometheusExporter), (
                f"Expected PrometheusExporter, got {type(orch._prometheus).__name__}"
            )
        finally:
            await orch.stop()


# ===========================================================================
# Test 3: RedisMetricsStore is wired
# ===========================================================================


class TestRedisStoreWiring:
    """Orchestrator.start() creates a RedisMetricsStore (with graceful degradation)."""

    @pytest.mark.asyncio
    async def test_orchestrator_start_wires_redis_store(self, tmp_path: Path):
        """After start(), orchestrator._redis_store is not None."""
        orch = await _start_orchestrator(tmp_path)
        try:
            assert orch._redis_store is not None, (
                "RedisMetricsStore must be instantiated after start() "
                "(even without Redis — it degrades gracefully)"
            )
            assert isinstance(orch._redis_store, RedisMetricsStore), (
                f"Expected RedisMetricsStore, got {type(orch._redis_store).__name__}"
            )
        finally:
            await orch.stop()


# ===========================================================================
# Test 4: PrometheusExporter exposed via property
# ===========================================================================


class TestPrometheusProperty:
    """The prometheus property delegates to _prometheus."""

    @pytest.mark.asyncio
    async def test_orchestrator_prometheus_exposed_via_property(self, tmp_path: Path):
        """orchestrator.prometheus is the same object as orchestrator._prometheus."""
        orch = await _start_orchestrator(tmp_path)
        try:
            assert orch.prometheus is orch._prometheus, (
                "The 'prometheus' property must return the exact same object "
                "as '_prometheus' — no copy, no wrapper"
            )
        finally:
            await orch.stop()


# ===========================================================================
# Test 5: stop() records a shutdown audit event
# ===========================================================================


class TestShutdownAuditEvent:
    """stop() writes a 'shutdown' event to the audit trail."""

    @pytest.mark.asyncio
    async def test_orchestrator_stop_records_shutdown_audit_event(self, tmp_path: Path):
        """After stop(), the audit file contains a 'shutdown' event."""
        orch = await _start_orchestrator(tmp_path)
        # Resolve the audit file path the same way the orchestrator does.
        audit_path = orch.config.resolve(
            orch.config.observability.audit_trail_file,
        )

        await orch.stop()

        # The audit file must exist.
        assert audit_path.exists(), (
            f"Audit trail file not found at {audit_path}"
        )

        # Read the last JSONL line and verify it is a shutdown event.
        lines = audit_path.read_text().strip().splitlines()
        assert len(lines) >= 1, "Audit trail must contain at least one event"

        last_event = json.loads(lines[-1])
        assert last_event["event_type"] == "shutdown", (
            f"Last audit event should be 'shutdown', got '{last_event['event_type']}'"
        )
        assert "cycles_completed" in last_event.get("data", {}), (
            "Shutdown event must include 'cycles_completed' in data"
        )


# ===========================================================================
# Test 6: AlertManager is None when no webhook URL is configured
# ===========================================================================


class TestAlertManagerNone:
    """AlertManager is only created when a webhook URL is provided."""

    @pytest.mark.asyncio
    async def test_orchestrator_alert_manager_none_without_webhook(self, tmp_path: Path):
        """When alert_webhook_url is empty, _alert_manager stays None."""
        orch = await _start_orchestrator(tmp_path, alert_webhook_url="")
        try:
            assert orch._alert_manager is None, (
                "AlertManager should be None when no webhook URL is configured"
            )
        finally:
            await orch.stop()
