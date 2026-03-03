"""Heartbeat endpoints -- vital signs and rhythm."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from luna.api.dependencies import get_orchestrator

router = APIRouter()


@router.get("/status")
async def get_heartbeat(orch: object = Depends(get_orchestrator)) -> dict:
    """Get current heartbeat status."""
    hb = getattr(orch, "heartbeat", None)
    if hb is None:
        raise HTTPException(status_code=503, detail="heartbeat not available")

    status = hb.get_status()
    return {
        "is_running": status.is_running,
        "idle_steps": status.idle_steps,
        "identity_ok": status.identity_ok,
        "last_beat": status.last_beat.isoformat() if status.last_beat else None,
    }


@router.get("/vitals")
async def get_vitals(orch: object = Depends(get_orchestrator)) -> dict:
    """Get current vital signs from the heartbeat loop."""
    hb = getattr(orch, "_heartbeat", None) or getattr(orch, "heartbeat", None)
    if hb is None:
        raise HTTPException(status_code=503, detail="heartbeat not available")
    vitals = getattr(hb, "_last_vitals", None)
    if vitals is None:
        raise HTTPException(status_code=503, detail="no vitals measured yet")
    return vitals
