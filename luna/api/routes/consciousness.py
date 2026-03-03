"""Consciousness endpoints -- Psi state, evolution, phi_iit."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from luna.api.dependencies import get_engine, get_orchestrator

router = APIRouter()


@router.get("/state")
async def get_state(orch: object = Depends(get_orchestrator)) -> dict:
    """Get current consciousness state."""
    engine = getattr(orch, "engine", None)
    if engine is None:
        raise HTTPException(status_code=503, detail="engine not available")

    cs = getattr(engine, "consciousness", None)
    if cs is None:
        raise HTTPException(status_code=503, detail="consciousness not initialized")

    return {
        "psi": cs.psi.tolist() if hasattr(cs.psi, "tolist") else list(cs.psi),
        "psi0": cs.psi0.tolist() if hasattr(cs.psi0, "tolist") else list(cs.psi0),
        "step_count": cs.step_count,
        "agent_name": cs.agent_name,
    }


@router.get("/phi")
async def get_phi(engine: object = Depends(get_engine)) -> dict:
    """Get current PHI IIT value."""
    status = engine.get_status()
    return {
        "phi_iit": status.get("phi_iit", 0.0),
        "health_phase": status.get("health_phase", "unknown"),
        "health_score": status.get("health_score", 0.0),
    }
