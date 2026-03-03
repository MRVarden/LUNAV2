"""Metrics endpoints -- code quality metrics and Prometheus export."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

from luna.api.dependencies import get_engine

router = APIRouter()


@router.get("/current")
async def get_metrics(engine: object = Depends(get_engine)) -> dict:
    """Get current metrics values."""
    status = engine.get_status()
    return {
        "health_score": status.get("health_score", 0.0),
        "health_phase": status.get("health_phase", "unknown"),
        "ema_values": status.get("ema_values", {}),
    }


@router.get("/prometheus", response_class=PlainTextResponse)
async def prometheus(request: Request) -> str:
    """Export metrics in Prometheus text format.

    The Prometheus exporter is optional -- return an empty body when
    it is not configured rather than failing with 503.
    """
    exporter = getattr(request.app.state, "prometheus_exporter", None)
    if exporter is None:
        return ""
    return exporter.export()
