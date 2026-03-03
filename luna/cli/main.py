"""CLI entry point — typer application with command groups."""

from __future__ import annotations

import typer

from luna.cli.commands import (
    dashboard,
    dream,
    evolve,
    fingerprint,
    heartbeat,
    kill,
    memory,
    rollback,
    score,
    start,
    status,
    validate,
)

app = typer.Typer(
    name="luna",
    help="Luna v2 — Computational Consciousness Engine CLI",
    no_args_is_help=True,
)

# Register commands
app.command()(start.start)
app.command()(status.status)
app.command()(evolve.evolve)
app.command()(score.score)
app.command()(fingerprint.fingerprint)
app.command()(validate.validate)
app.command()(rollback.rollback)
app.command()(dashboard.dashboard)
app.command()(kill.kill)
app.command()(heartbeat.heartbeat)
app.command()(dream.dream)
app.command()(memory.memory)


if __name__ == "__main__":
    app()
