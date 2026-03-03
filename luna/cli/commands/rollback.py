"""Rollback command — restore from snapshot."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from luna.core.config import LunaConfig
from luna.safety.snapshot_manager import SnapshotManager


def rollback(
    snapshot_id: str = typer.Argument(..., help="Snapshot ID to restore"),
    target: str = typer.Option(".", help="Target directory for restoration"),
    config: str = typer.Option("luna.toml", help="Path to config file"),
) -> None:
    """Restore a snapshot by ID."""
    cfg = LunaConfig.load(config)
    snapshot_dir = cfg.resolve(cfg.safety.snapshot_dir)
    sm = SnapshotManager(
        snapshot_dir=snapshot_dir,
        max_snapshots=cfg.safety.max_snapshots,
        retention_days=cfg.safety.retention_days,
    )

    target_path = Path(target).resolve()
    typer.echo(f"Restoring snapshot {snapshot_id} to {target_path}...")

    try:
        asyncio.run(sm.restore(snapshot_id, target_path))
        typer.echo("Restore complete.")
    except FileNotFoundError:
        typer.echo(f"Error: snapshot not found: {snapshot_id}")
        raise typer.Exit(1)
    except ValueError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1)
