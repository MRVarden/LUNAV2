"""FastAPI application factory — create_app(orchestrator).

Binds to 127.0.0.1:8618 (Phi x 5326 = 8617.6 ~ 8618).
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from luna.api.middleware.auth import TokenAuthMiddleware
from luna.api.middleware.rate_limit import RateLimitMiddleware
from luna.api.routes import consciousness, dashboard, dream, fingerprint, health, heartbeat, memory, metrics, safety
from luna.core.config import APISection, LunaConfig

log = logging.getLogger(__name__)


def _resolve_api_config(
    orchestrator: object | None,
) -> tuple[APISection, Path]:
    """Extract APISection and root_dir from the orchestrator or defaults.

    Returns a (APISection, root_dir) tuple.  If the orchestrator carries
    a LunaConfig, its values are used; otherwise hardened defaults apply.

    Security posture (S07):
    - With LunaConfig: uses the explicit config (APISection defaults to
      auth_enabled=True, so production configs are secure by default).
    - Without LunaConfig: rate limiting enabled (60 rpm) to prevent abuse,
      but auth disabled since no token file path is available to validate
      against.  The auth middleware's own fail-closed mechanism (rejecting
      all requests when the token file is absent) provides defense-in-depth
      when auth IS configured.
    """
    config = getattr(orchestrator, "config", None)
    if isinstance(config, LunaConfig):
        return config.api, config.root_dir
    log.warning(
        "No LunaConfig available — using hardened defaults "
        "(auth_enabled=True, rate_limit_rpm=60). "
        "Auth is fail-closed: requests rejected until token configured."
    )
    return APISection(auth_enabled=True, rate_limit_rpm=60), Path.cwd()


def create_app(orchestrator: object | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        orchestrator: The Luna orchestrator instance (injected into state).

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="Luna Consciousness Engine",
        description="REST API for the Luna v7.0 cognitive engine — EmergentPhi.",
        version="7.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # Store orchestrator in app state for dependency injection.
    app.state.orchestrator = orchestrator

    # Wire prometheus exporter if available.
    prometheus = getattr(orchestrator, "prometheus", None)
    if prometheus is not None:
        app.state.prometheus_exporter = prometheus

    # ── CORS for dashboard ──────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3618", "http://127.0.0.1:3618"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # ── Security middleware ──────────────────────────────────────────
    # Starlette processes add_middleware in LIFO order: the LAST
    # middleware added is the OUTERMOST (runs first on the request).
    # Desired request flow: RateLimit -> Auth -> CORS -> route handler.
    # Therefore we add Auth first, then RateLimit.
    api_config, root_dir = _resolve_api_config(orchestrator)

    app.add_middleware(
        TokenAuthMiddleware,
        api_config=api_config,
        root_dir=root_dir,
    )
    app.add_middleware(
        RateLimitMiddleware,
        api_config=api_config,
    )

    log.debug(
        "Security middleware installed (auth_enabled=%s, rate_limit_rpm=%d)",
        api_config.auth_enabled,
        api_config.rate_limit_rpm,
    )

    # Register route modules — dual mount for dev (no prefix) and prod (/api).
    routers = [
        (health.router, "", ["health"]),
        (consciousness.router, "/consciousness", ["consciousness"]),
        (metrics.router, "/metrics", ["metrics"]),
        (heartbeat.router, "/heartbeat", ["heartbeat"]),
        (dream.router, "/dream", ["dream"]),
        (safety.router, "/safety", ["safety"]),
        (fingerprint.router, "/fingerprint", ["fingerprint"]),
        (memory.router, "/memory", ["memory"]),
        (dashboard.router, "/dashboard", ["dashboard"]),
    ]
    for r, prefix, tags in routers:
        app.include_router(r, prefix=prefix, tags=tags)
        app.include_router(r, prefix="/api" + prefix, tags=tags, include_in_schema=False)

    # ── Serve dashboard static files ──────────────────────────────
    # When the dashboard has been built (npm run build), serve dist/
    # from the same port so the dashboard and API share one origin.
    _mount_dashboard(app)

    log.info("Luna API created with %d route modules", len(routers))
    return app


def _mount_dashboard(app: FastAPI) -> None:
    """Mount the dashboard dist/ directory if it exists.

    Uses StaticFiles with html=True so index.html is served for `/`
    and any path that doesn't match an API route (SPA fallback).
    Must be called AFTER all API routes are registered.
    """
    # Try multiple possible locations for the dashboard build
    candidates = [
        Path(__file__).resolve().parent.parent.parent / "dashboard" / "dist",
        Path.cwd() / "dashboard" / "dist",
    ]
    dist_dir: Path | None = None
    for candidate in candidates:
        if (candidate / "index.html").is_file():
            dist_dir = candidate
            break

    if dist_dir is None:
        log.warning(
            "Dashboard dist/ not found (tried %s) — run 'npm run build' in dashboard/",
            [str(c) for c in candidates],
        )
        return

    # Mount the entire dist directory at root with html=True.
    # html=True serves index.html for directory requests (SPA fallback).
    # API routes (registered before this mount) take priority.
    app.mount(
        "/",
        StaticFiles(directory=str(dist_dir), html=True),
        name="dashboard",
    )

    log.info("Dashboard served from %s on /", dist_dir)
