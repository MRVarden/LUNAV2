"""Kill command — emergency stop."""

from __future__ import annotations

from pathlib import Path

import typer

from luna.core.config import LunaConfig
from luna.safety.kill_switch import KillSwitch


def kill(
    reason: str = typer.Option("manual CLI", help="Reason for emergency stop"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    config: str = typer.Option("luna.toml", help="Path to config file"),
) -> None:
    """Activate the kill switch — emergency stop via sentinel file."""
    if not force:
        confirm = typer.confirm("Activate kill switch?")
        if not confirm:
            typer.echo("Cancelled.")
            raise typer.Exit()

    try:
        cfg = LunaConfig.load(config)
        data_dir = cfg.resolve(cfg.luna.data_dir)
    except FileNotFoundError:
        data_dir = Path.cwd() / "data"

    ks = KillSwitch()
    sentinel_path = ks.write_sentinel(data_dir, reason)
    typer.echo(f"Kill sentinel written: {sentinel_path}")
    typer.echo(f"Reason: {reason}")
    typer.echo("The running orchestrator will detect this on next heartbeat cycle.")
