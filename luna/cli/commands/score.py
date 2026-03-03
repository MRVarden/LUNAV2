"""Score command — analyze code quality metrics."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer

from luna.core.config import LunaConfig
from luna.metrics.collector import MetricsCollector


def score(
    path: str = typer.Argument(".", help="Path to analyze"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed metrics"),
    config: str = typer.Option("luna.toml", help="Path to config file"),
) -> None:
    """Score code quality using PHI-weighted metrics."""
    target = Path(path).resolve()
    if not target.exists():
        typer.echo(f"Error: path does not exist: {target}")
        raise typer.Exit(1)

    cfg = LunaConfig.load(config)
    collector = MetricsCollector(
        cache_dir=cfg.resolve(cfg.metrics.cache_dir),
        cache_enabled=cfg.metrics.cache_enabled,
        timeout=cfg.metrics.timeout_seconds,
    )

    metrics = asyncio.run(collector.collect(target))

    if not metrics.values:
        typer.echo("No metrics collected (no recognized source files found).")
        raise typer.Exit(0)

    typer.echo(f"Metrics for: {target}")
    for name, value in sorted(metrics.values.items()):
        zone = metrics.zones.get(name, "?")
        typer.echo(f"  {name}: {value:.4f} [{zone}]")

    if verbose:
        typer.echo(f"\nSources: {', '.join(metrics.raw_sources)}")
        typer.echo(json.dumps({"values": metrics.values, "zones": metrics.zones}, indent=2))
