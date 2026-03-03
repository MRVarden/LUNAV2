"""Tests for API consciousness endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest
from fastapi.testclient import TestClient

from luna.api.app import create_app


@pytest.fixture
def client():
    """TestClient with mock consciousness state."""
    orch = MagicMock()
    cs = MagicMock()
    cs.psi = np.array([0.25, 0.35, 0.25, 0.15])
    cs.psi0 = np.array([0.25, 0.35, 0.25, 0.15])
    cs.step_count = 42
    cs.agent_name = "LUNA"
    orch.engine.consciousness = cs
    orch.engine.get_status.return_value = {
        "phi_iit": 0.72,
        "health_phase": "SOLID",
        "health_score": 0.85,
    }
    app = create_app(orchestrator=orch)
    return TestClient(app)


@pytest.fixture
def client_no_orch():
    app = create_app(orchestrator=None)
    return TestClient(app)


class TestConsciousnessEndpoints:
    """Tests for /consciousness endpoints."""

    def test_get_state(self, client):
        """Get consciousness state."""
        response = client.get("/consciousness/state")
        assert response.status_code == 200
        data = response.json()
        assert len(data["psi"]) == 4
        assert data["step_count"] == 42
        assert data["agent_name"] == "LUNA"

    def test_get_phi(self, client):
        """Get PHI IIT value."""
        response = client.get("/consciousness/phi")
        assert response.status_code == 200
        data = response.json()
        assert data["phi_iit"] == pytest.approx(0.72)
        assert data["health_phase"] == "SOLID"

    def test_no_orchestrator(self, client_no_orch):
        """Returns 503 when orchestrator unavailable."""
        response = client_no_orch.get("/consciousness/state")
        assert response.status_code == 503
        assert "detail" in response.json()
