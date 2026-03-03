"""Tests for API auth middleware and rate limiting.

Validates P0 corrections: Bearer token authentication and IP-based
rate limiting applied via FastAPI middleware.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from luna.api.middleware.auth import TokenAuthMiddleware
from luna.api.middleware.rate_limit import RateLimitMiddleware
from luna.core.config import APISection


# ---------------------------------------------------------------------------
# Helpers — minimal FastAPI app wired with real middleware
# ---------------------------------------------------------------------------

def _make_app(
    *,
    auth_enabled: bool = True,
    rate_limit_rpm: int = 0,
    token_file_path: str = "api_token",
    root_dir: str | None = None,
) -> FastAPI:
    """Build a tiny FastAPI app with real auth + rate-limit middleware."""
    from pathlib import Path

    api_config = APISection(
        auth_enabled=auth_enabled,
        auth_token_file=token_file_path,
        rate_limit_rpm=rate_limit_rpm,
    )
    root = Path(root_dir) if root_dir else Path.cwd()

    app = FastAPI()

    # Route that requires auth
    @app.get("/ping")
    async def ping():
        return JSONResponse({"message": "pong"})

    # Public health route
    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok"})

    # Starlette processes middleware LIFO: add Auth first, then RateLimit.
    app.add_middleware(
        TokenAuthMiddleware,
        api_config=api_config,
        root_dir=root,
    )
    app.add_middleware(
        RateLimitMiddleware,
        api_config=api_config,
    )

    return app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SECRET_TOKEN = "test-secret-token-a1b2c3d4"


@pytest.fixture()
def token_file(tmp_path):
    """Write a known token to a temporary file and return (tmp_path, filename)."""
    token_filename = "api_token"
    token_path = tmp_path / token_filename
    token_path.write_text(SECRET_TOKEN, encoding="utf-8")
    return tmp_path, token_filename


@pytest.fixture()
def auth_client(token_file):
    """TestClient for an app with auth enabled and a valid token file."""
    root_dir, token_filename = token_file
    app = _make_app(
        auth_enabled=True,
        rate_limit_rpm=0,
        token_file_path=token_filename,
        root_dir=str(root_dir),
    )
    return TestClient(app)


@pytest.fixture()
def noauth_client():
    """TestClient with auth disabled."""
    app = _make_app(auth_enabled=False, rate_limit_rpm=0)
    return TestClient(app)


@pytest.fixture()
def rate_limited_client(token_file):
    """TestClient with rate limiting enabled at 3 rpm."""
    root_dir, token_filename = token_file
    app = _make_app(
        auth_enabled=True,
        rate_limit_rpm=3,
        token_file_path=token_filename,
        root_dir=str(root_dir),
    )
    return TestClient(app)


@pytest.fixture()
def rate_unlimited_client(token_file):
    """TestClient with rate limiting disabled (rpm=0)."""
    root_dir, token_filename = token_file
    app = _make_app(
        auth_enabled=True,
        rate_limit_rpm=0,
        token_file_path=token_filename,
        root_dir=str(root_dir),
    )
    return TestClient(app)


# ===========================================================================
# Auth middleware tests
# ===========================================================================


class TestAuthMiddleware:
    """Bearer token authentication middleware tests."""

    def test_health_accessible_without_auth(self, auth_client):
        """/health is a public path — no token required."""
        response = auth_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_requires_bearer_token(self, auth_client):
        """Non-public routes return 401 when no Authorization header."""
        response = auth_client.get("/ping")
        assert response.status_code == 401
        body = response.json()
        assert "detail" in body

    def test_valid_token_accepted(self, auth_client):
        """A valid Bearer token grants access to protected routes."""
        response = auth_client.get(
            "/ping",
            headers={"Authorization": f"Bearer {SECRET_TOKEN}"},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "pong"

    def test_invalid_token_rejected(self, auth_client):
        """An invalid Bearer token is rejected with 401."""
        response = auth_client.get(
            "/ping",
            headers={"Authorization": "Bearer wrong-token-value"},
        )
        assert response.status_code == 401

    def test_auth_disabled_bypasses_check(self, noauth_client):
        """When auth_enabled=False, no token is required on any route."""
        response = noauth_client.get("/ping")
        assert response.status_code == 200
        assert response.json()["message"] == "pong"


# ===========================================================================
# Rate limiting middleware tests
# ===========================================================================


class TestRateLimitMiddleware:
    """IP-based rate limiting middleware tests."""

    def test_rate_limit_blocks_excess(self, rate_limited_client):
        """After exceeding the RPM limit, the server returns 429."""
        headers = {"Authorization": f"Bearer {SECRET_TOKEN}"}

        # Send requests up to the limit (3 rpm)
        for _ in range(3):
            resp = rate_limited_client.get("/ping", headers=headers)
            assert resp.status_code == 200

        # The 4th request should be rate-limited
        resp = rate_limited_client.get("/ping", headers=headers)
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

    def test_rate_limit_headers(self, rate_limited_client):
        """Successful responses include X-RateLimit-Limit and X-RateLimit-Remaining."""
        headers = {"Authorization": f"Bearer {SECRET_TOKEN}"}

        resp = rate_limited_client.get("/ping", headers=headers)
        assert resp.status_code == 200
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers
        assert resp.headers["X-RateLimit-Limit"] == "3"
        # After 1 request out of 3, remaining should be 2
        assert resp.headers["X-RateLimit-Remaining"] == "2"

    def test_rate_limit_disabled_when_zero(self, rate_unlimited_client):
        """When rate_limit_rpm=0, no rate limiting is applied."""
        headers = {"Authorization": f"Bearer {SECRET_TOKEN}"}

        # Send many requests — none should be rate-limited
        for _ in range(20):
            resp = rate_unlimited_client.get("/ping", headers=headers)
            assert resp.status_code == 200
            # When disabled, rate-limit headers should NOT be present
            assert "X-RateLimit-Limit" not in resp.headers
