"""Dream command — sleep cycle control."""

from __future__ import annotations

import asyncio
import json

import typer

from luna.core.config import LunaConfig
from luna.core.luna import LunaEngine
from luna.dream import DreamCycle
from luna.memory import MemoryManager


def dream(
    trigger: bool = typer.Option(False, help="Manually trigger a dream cycle"),
    status_only: bool = typer.Option(False, "--status", help="Show dream status only"),
    config: str = typer.Option("luna.toml", help="Path to config file"),
) -> None:
    """Show dream status or trigger a dream cycle."""
    cfg = LunaConfig.load(config)
    engine = LunaEngine(cfg)
    engine.initialize()
    memory = MemoryManager(cfg)
    dc = DreamCycle(engine, cfg, memory=memory)

    if status_only:
        typer.echo(json.dumps(dc.get_status(), indent=2, default=str))
    elif trigger:
        typer.echo("Triggering dream cycle...")
        report = asyncio.run(dc.run())
        if report is not None:
            typer.echo(f"Dream completed: {report.total_duration:.2f}s")
            typer.echo(f"History: {report.history_before} -> {report.history_after}")
        else:
            typer.echo("Dream cycle returned no report.")
    else:
        typer.echo(json.dumps(dc.get_status(), indent=2, default=str))
