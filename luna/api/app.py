"""FastAPI application factory — create_app(orchestrator).

Binds to 127.0.0.1:8618 (Phi x 5326 = 8617.6 ~ 8618).
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI

from luna.api.middleware.auth import TokenAuthMiddleware
from luna.api.middleware.rate_limit import RateLimitMiddleware
from luna.api.routes import consciousness, dream, fingerprint, health, heartbeat, memory, metrics, safety
from luna.core.config import APISection, LunaConfig

log = logging.getLogger(__name__)


def _resolve_api_config(
    orchestrator: object | None,
) -> tuple[APISection, Path]:
    """Extract APISection and root_dir from the orchestrator or defaults.

    Returns a (APISection, root_dir) tuple.  If the orchestrator carries
    a LunaConfig, its values are used; otherwise safe defaults apply.
    """
    config = getattr(orchestrator, "config", None)
    if isinstance(config, LunaConfig):
        return config.api, config.root_dir
    log.warning(
        "No orchestrator config available — using safe defaults "
        "(auth_enabled=False, rate_limit_rpm=0)"
    )
    return APISection(auth_enabled=False, rate_limit_rpm=0), Path.cwd()


def create_app(orchestrator: object | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        orchestrator: The Luna orchestrator instance (injected into state).

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="Luna Consciousness Engine",
        description="REST API for the Luna v2 consciousness engine.",
        version="2.0.0",
    )

    # Store orchestrator in app state for dependency injection.
    app.state.orchestrator = orchestrator

    # Wire prometheus exporter if available.
    prometheus = getattr(orchestrator, "prometheus", None)
    if prometheus is not None:
        app.state.prometheus_exporter = prometheus

    # ── Security middleware ──────────────────────────────────────────
    # Starlette processes add_middleware in LIFO order: the LAST
    # middleware added is the OUTERMOST (runs first on the request).
    # Desired request flow: RateLimit -> Auth -> route handler.
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

    log.info(
        "Security middleware installed (auth_enabled=%s, rate_limit_rpm=%d)",
        api_config.auth_enabled,
        api_config.rate_limit_rpm,
    )

    # Register route modules.
    routers = [
        (health.router, "", ["health"]),
        (consciousness.router, "/consciousness", ["consciousness"]),
        (metrics.router, "/metrics", ["metrics"]),
        (heartbeat.router, "/heartbeat", ["heartbeat"]),
        (dream.router, "/dream", ["dream"]),
        (safety.router, "/safety", ["safety"]),
        (fingerprint.router, "/fingerprint", ["fingerprint"]),
        (memory.router, "/memory", ["memory"]),
    ]
    for r, prefix, tags in routers:
        app.include_router(r, prefix=prefix, tags=tags)

    log.info("Luna API created with %d route modules", len(routers))
    return app
