"""Memory command — fractal memory access."""

from __future__ import annotations

import asyncio
import json

import typer

from luna.core.config import LunaConfig
from luna.memory import MemoryManager


def memory(
    search: str = typer.Option("", help="Search memories by keyword"),
    stats: bool = typer.Option(False, "--stats", help="Show memory statistics"),
    config: str = typer.Option("luna.toml", help="Path to config file"),
) -> None:
    """Access fractal memory system."""
    cfg = LunaConfig.load(config)
    mm = MemoryManager(cfg)

    if stats:
        status_data = asyncio.run(mm.get_status())
        typer.echo(json.dumps(status_data, indent=2, default=str))
    elif search:
        keywords = search.split(",")
        results = asyncio.run(mm.search(keywords))
        if not results:
            typer.echo("No memories found.")
        else:
            typer.echo(f"Found {len(results)} memories:")
            for entry in results:
                content = str(entry.content)[:80]
                typer.echo(f"  [{entry.memory_type}] {entry.id}: {content}...")
    else:
        # Show recent memories
        recent = asyncio.run(mm.read_recent(limit=10))
        if not recent:
            typer.echo("No memories stored yet.")
        else:
            typer.echo(f"Recent memories ({len(recent)}):")
            for entry in recent:
                content = str(entry.content)[:80]
                typer.echo(f"  [{entry.memory_type}] {entry.id}: {content}")
