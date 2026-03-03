"""Health check endpoint.

Health MUST always respond (no ``Depends`` on orchestrator) so that
load-balancers and liveness probes work even when the engine is down.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict:
    """Health check -- returns system status."""
    orch = getattr(request.app.state, "orchestrator", None)

    status = "healthy"
    details: dict = {"api": True}

    if orch is not None:
        engine = getattr(orch, "engine", None)
        if engine is not None:
            try:
                engine_status = engine.get_status()
                details["engine"] = True
                details["phase"] = engine_status.get("health_phase", "unknown")
            except Exception:
                details["engine"] = False
                status = "degraded"
    else:
        details["engine"] = False
        status = "standalone"

    return {"status": status, "details": details}
