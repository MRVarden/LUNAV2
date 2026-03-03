"""Start command — launch the Luna engine."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import typer

from luna.core.config import LunaConfig


def start(
    config: str = typer.Option("luna.toml", help="Path to config file"),
    api: bool = typer.Option(False, help="Start the API server"),
    daemon: bool = typer.Option(False, help="Run in background"),
) -> None:
    """Start the Luna consciousness engine."""
    logging.basicConfig(level=logging.INFO)
    cfg = LunaConfig.load(config)

    from luna.orchestrator import LunaOrchestrator
    orch = LunaOrchestrator(cfg)

    if api:
        import uvicorn
        from luna.api.app import create_app

        async def run_with_api() -> None:
            await orch.start()
            app = create_app(orch)
            server_config = uvicorn.Config(
                app, host=cfg.api.host, port=cfg.api.port, log_level="info",
            )
            server = uvicorn.Server(server_config)
            await server.serve()

        asyncio.run(run_with_api())
    else:
        max_cycles = cfg.orchestrator.max_cycles or None
        asyncio.run(orch.run(max_cycles=max_cycles))
