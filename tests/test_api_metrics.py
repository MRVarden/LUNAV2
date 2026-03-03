"""Tests for API metrics endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from luna.api.app import create_app
from luna.observability.prometheus_exporter import PrometheusExporter


@pytest.fixture
def client():
    """TestClient with mock metrics."""
    orch = MagicMock()
    orch.engine.get_status.return_value = {
        "health_score": 0.85,
        "health_phase": "SOLID",
        "ema_values": {"security": 0.9, "coverage": 0.8},
    }
    app = create_app(orchestrator=orch)

    # Attach prometheus exporter
    exporter = PrometheusExporter()
    exporter.gauge("test", 1.0, "Test metric")
    app.state.prometheus_exporter = exporter

    return TestClient(app)


class TestMetricsEndpoints:
    """Tests for /metrics endpoints."""

    def test_get_current_metrics(self, client):
        """Get current metrics values."""
        response = client.get("/metrics/current")
        assert response.status_code == 200
        data = response.json()
        assert data["health_score"] == 0.85
        assert data["health_phase"] == "SOLID"

    def test_prometheus_export(self, client):
        """Prometheus endpoint returns text format."""
        response = client.get("/metrics/prometheus")
        assert response.status_code == 200
        assert "luna_test 1.0" in response.text

    def test_prometheus_no_exporter(self):
        """Prometheus endpoint returns empty without exporter."""
        app = create_app(orchestrator=None)
        client = TestClient(app)
        response = client.get("/metrics/prometheus")
        assert response.status_code == 200
        assert response.text == ""
