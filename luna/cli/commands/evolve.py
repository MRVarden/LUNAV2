"""Evolve command — run consciousness evolution steps."""

from __future__ import annotations

import typer

from luna.core.config import LunaConfig
from luna.core.luna import LunaEngine


def evolve(
    steps: int = typer.Argument(1, help="Number of evolution steps"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    config: str = typer.Option("luna.toml", help="Path to config file"),
) -> None:
    """Run N consciousness evolution steps (idle steps)."""
    cfg = LunaConfig.load(config)
    engine = LunaEngine(cfg)
    engine.initialize()

    for i in range(steps):
        engine.idle_step()
        if verbose:
            cs = engine.consciousness
            typer.echo(f"Step {i + 1}/{steps}: phi_iit={cs.compute_phi_iit():.4f}, phase={cs.get_phase()}")

    cs = engine.consciousness
    typer.echo(f"Evolved {steps} step(s). Phase: {cs.get_phase()}, PHI_IIT: {cs.compute_phi_iit():.4f}")

    # Save checkpoint
    ckpt = cfg.resolve(cfg.consciousness.checkpoint_file)
    ckpt.parent.mkdir(parents=True, exist_ok=True)
    cs.save_checkpoint(ckpt, backup=cfg.consciousness.backup_on_save)
    typer.echo(f"Checkpoint saved: {ckpt}")
