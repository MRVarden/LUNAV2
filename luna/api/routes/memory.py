"""Memory endpoints -- fractal memory access."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from luna.api.dependencies import get_orchestrator

router = APIRouter()


@router.get("/status")
async def memory_status(orch: object = Depends(get_orchestrator)) -> dict:
    """Get memory subsystem status."""
    memory = getattr(orch, "memory", None)
    if memory is None:
        raise HTTPException(status_code=503, detail="memory not available")

    if hasattr(memory, "get_status"):
        return memory.get_status()

    return {"status": "available"}


@router.get("/search")
async def search_memory(
    orch: object = Depends(get_orchestrator),
    query: str = "",
    limit: int = Query(default=5, ge=1, le=50),
) -> dict:
    """Search memories by keywords."""
    memory = getattr(orch, "memory", None)
    if memory is None:
        raise HTTPException(status_code=503, detail="memory not available")

    if not hasattr(memory, "search"):
        raise HTTPException(status_code=503, detail="search not implemented")

    results = await memory.search(query, limit=limit)
    return {"results": results, "count": len(results)}
