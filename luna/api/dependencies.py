"""Dependency injection -- extract subsystems from app state.

FastAPI dependencies that provide access to Luna subsystems
via the orchestrator stored in app.state.  Each dependency raises
``HTTPException(503)`` when the required subsystem is unavailable,
so route handlers never need to check for *None*.
"""

from __future__ import annotations

from fastapi import HTTPException, Request


def get_orchestrator(request: Request) -> object:
    """Return the orchestrator from *app.state* or raise 503."""
    orch = getattr(request.app.state, "orchestrator", None)
    if orch is None:
        raise HTTPException(status_code=503, detail="orchestrator not available")
    return orch


def get_engine(request: Request) -> object:
    """Return the Luna engine from the orchestrator or raise 503."""
    orch = get_orchestrator(request)
    engine = getattr(orch, "engine", None)
    if engine is None:
        raise HTTPException(status_code=503, detail="engine not available")
    return engine
