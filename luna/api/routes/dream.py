"""Dream endpoints -- sleep cycle status and control."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from luna.api.dependencies import get_orchestrator

router = APIRouter()


@router.get("/status")
async def dream_status(orch: object = Depends(get_orchestrator)) -> dict:
    """Get current dream/sleep status."""
    sleep_mgr = getattr(orch, "sleep_manager", None)
    if sleep_mgr is not None:
        status = sleep_mgr.get_status()
        return {
            "state": status.state.value,
            "dream_count": status.dream_count,
            "last_dream_at": status.last_dream_at,
            "last_dream_duration": status.last_dream_duration,
            "total_dream_time": status.total_dream_time,
        }

    dream = getattr(orch, "_dream", None)
    if dream is not None:
        return dream.get_status()

    raise HTTPException(status_code=503, detail="dream subsystem not available")


@router.post("/trigger")
async def trigger_dream(orch: object = Depends(get_orchestrator)) -> dict:
    """Manually trigger a dream cycle."""
    sleep_mgr = getattr(orch, "sleep_manager", None)
    if sleep_mgr is None:
        raise HTTPException(status_code=503, detail="sleep manager not available")

    report = await sleep_mgr.enter_sleep()
    if report is not None:
        return {"status": "completed", "duration": report.total_duration}
    return {"status": "failed"}
