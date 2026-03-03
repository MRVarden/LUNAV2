"""Safety endpoints -- kill switch, snapshots, watchdog."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from luna.api.dependencies import get_orchestrator

router = APIRouter()


@router.get("/status")
async def safety_status(orch: object = Depends(get_orchestrator)) -> dict:
    """Get overall safety status."""
    result: dict = {}

    ks = getattr(orch, "kill_switch", None)
    if ks is not None:
        result["kill_switch"] = ks.get_status()

    wd = getattr(orch, "watchdog", None)
    if wd is not None:
        result["watchdog"] = wd.get_status()

    rl = getattr(orch, "rate_limiter", None)
    if rl is not None:
        result["rate_limiter"] = rl.get_status()

    if not result:
        raise HTTPException(status_code=503, detail="safety subsystems not available")

    return result


@router.post("/kill")
async def kill(orch: object = Depends(get_orchestrator)) -> dict:
    """Activate the kill switch."""
    ks = getattr(orch, "kill_switch", None)
    if ks is None:
        raise HTTPException(status_code=503, detail="kill switch not available")

    cancelled = ks.kill(reason="API request")
    return {"killed": True, "tasks_cancelled": cancelled}


@router.get("/snapshots")
async def list_snapshots(orch: object = Depends(get_orchestrator)) -> dict:
    """List available snapshots."""
    sm = getattr(orch, "snapshot_manager", None)
    if sm is None:
        raise HTTPException(status_code=503, detail="snapshot manager not available")

    snapshots = await sm.list_snapshots()
    return {"snapshots": [s.to_dict() for s in snapshots]}
