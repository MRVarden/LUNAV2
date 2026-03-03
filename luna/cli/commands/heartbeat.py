"""Heartbeat command — vital signs display."""

from __future__ import annotations

import json
import time
from dataclasses import asdict

import typer

from luna.core.config import LunaConfig
from luna.core.luna import LunaEngine
from luna.heartbeat.vitals import measure_vitals


def heartbeat(
    watch: bool = typer.Option(False, "--watch", "-w", help="Continuous display"),
    config: str = typer.Option("luna.toml", help="Path to config file"),
) -> None:
    """Show heartbeat vital signs."""
    cfg = LunaConfig.load(config)
    engine = LunaEngine(cfg)
    engine.initialize()

    start_time = time.monotonic()

    if watch:
        typer.echo("Heartbeat watch mode — Ctrl+C to stop.\n")
        try:
            while True:
                engine.idle_step()
                uptime = time.monotonic() - start_time
                vitals = measure_vitals(engine, uptime, 0)
                v = asdict(vitals)
                typer.echo(f"Step {engine._idle_steps}: vitality={v['overall_vitality']:.4f} "
                          f"drift={v['identity_drift']:.4f} phi={v['phi_iit']:.4f}")
                time.sleep(cfg.heartbeat.interval_seconds)
        except KeyboardInterrupt:
            typer.echo("\nStopped.")
    else:
        engine.idle_step()
        uptime = time.monotonic() - start_time
        vitals = measure_vitals(engine, uptime, 0)
        typer.echo(json.dumps(asdict(vitals), indent=2))
