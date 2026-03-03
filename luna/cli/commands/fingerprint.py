"""Fingerprint command — identity verification."""

from __future__ import annotations

import asyncio
import json

import typer

from luna.core.config import LunaConfig
from luna.fingerprint.generator import FingerprintGenerator
from luna.fingerprint.ledger import FingerprintLedger


def fingerprint(
    verify: bool = typer.Option(False, help="Verify current fingerprint"),
    history: int = typer.Option(0, help="Show N recent fingerprints"),
    config: str = typer.Option("luna.toml", help="Path to config file"),
) -> None:
    """Show or verify the Luna identity fingerprint."""
    cfg = LunaConfig.load(config)
    secret_file = cfg.resolve(cfg.fingerprint.secret_file)
    ledger_file = cfg.resolve(cfg.fingerprint.ledger_file)

    gen = FingerprintGenerator(secret_path=secret_file)
    ledger = FingerprintLedger(ledger_file)

    if history > 0:
        entries = asyncio.run(ledger.read_latest(n=history))
        if not entries:
            typer.echo("No fingerprints recorded yet.")
        else:
            for e in entries:
                typer.echo(json.dumps(e.to_dict(), default=str))
        return

    # Generate a fingerprint from current state
    from luna.core.luna import LunaEngine
    engine = LunaEngine(cfg)
    engine.initialize()

    cs = engine.consciousness
    if cs is None:
        typer.echo("Error: consciousness not initialized.")
        raise typer.Exit(1)

    fp = gen.generate(cs)
    typer.echo(f"Fingerprint: {fp.composite}")

    if verify:
        matches = gen.verify(fp, cs)
        if matches:
            typer.echo("Verification: identity integrity confirmed.")
        else:
            typer.echo("Verification: identity MISMATCH.")
