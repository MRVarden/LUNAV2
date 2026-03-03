"""Fingerprint endpoints -- identity verification and ledger."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from luna.api.dependencies import get_orchestrator

router = APIRouter()


@router.get("/current")
async def get_fingerprint(orch: object = Depends(get_orchestrator)) -> dict:
    """Get the latest fingerprint."""
    ledger = getattr(orch, "fingerprint_ledger", None)
    if ledger is None:
        raise HTTPException(status_code=503, detail="fingerprint ledger not available")

    latest = await ledger.read_latest(1)
    if not latest:
        raise HTTPException(status_code=404, detail="no fingerprints recorded")

    return latest[0].to_dict()


@router.get("/history")
async def fingerprint_history(
    orch: object = Depends(get_orchestrator),
    n: int = Query(default=10, ge=1, le=100),
) -> dict:
    """Get recent fingerprint history."""
    ledger = getattr(orch, "fingerprint_ledger", None)
    if ledger is None:
        raise HTTPException(status_code=503, detail="fingerprint ledger not available")

    entries = await ledger.read_latest(n)
    return {"fingerprints": [e.to_dict() for e in entries], "count": len(entries)}
