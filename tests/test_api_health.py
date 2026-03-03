"""Tests for API health endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from luna.api.app import create_app


@pytest.fixture
def client():
    """TestClient with no orchestrator."""
    app = create_app(orchestrator=None)
    return TestClient(app)


@pytest.fixture
def client_with_engine():
    """TestClient with a mock orchestrator and engine."""
    orch = MagicMock()
    orch.engine.get_status.return_value = {
        "health_phase": "SOLID",
        "health_score": 0.85,
    }
    app = create_app(orchestrator=orch)
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_standalone(self, client):
        """Health check works without orchestrator."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "standalone"
        assert data["details"]["api"] is True

    def test_health_with_engine(self, client_with_engine):
        """Health check with running engine."""
        response = client_with_engine.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["details"]["engine"] is True
        assert data["details"]["phase"] == "SOLID"
