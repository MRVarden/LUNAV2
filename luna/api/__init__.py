"""API module — FastAPI REST interface on 127.0.0.1:8618.

Provides endpoints for health, consciousness, metrics, heartbeat,
dream, safety, fingerprint, and memory subsystems.
"""

from __future__ import annotations

from luna.api.app import create_app

__all__ = ["create_app"]
