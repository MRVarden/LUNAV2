"""Status command — show engine state."""

from __future__ import annotations

import json

import typer

from luna.core.config import LunaConfig
from luna.core.luna import LunaEngine


def status(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    config: str = typer.Option("luna.toml", help="Path to config file"),
) -> None:
    """Show the current Luna engine status."""
    try:
        cfg = LunaConfig.load(config)
    except FileNotFoundError:
        typer.echo("Error: luna.toml not found. Run 'luna start' first.")
        raise typer.Exit(1)

    engine = LunaEngine(cfg)
    engine.initialize()
    status_data = engine.get_status()

    if json_output:
        typer.echo(json.dumps(status_data, indent=2, default=str))
    else:
        typer.echo(f"Agent: {status_data.get('agent_name', '?')}")
        typer.echo(f"Phase: {status_data.get('phase', '?')}")
        typer.echo(f"Step count: {status_data.get('step_count', 0)}")
        typer.echo(f"Health phase: {status_data.get('health_phase', '?')}")
        typer.echo(f"Quality score: {status_data.get('quality_score', 0):.4f}")
        typer.echo(f"PHI IIT: {status_data.get('phi_iit', 0):.4f}")
        dom = status_data.get('dominant_component', '?')
        preserved = status_data.get('identity_preserved', False)
        typer.echo(f"Dominant: {dom} (identity {'OK' if preserved else 'DRIFTED'})")
