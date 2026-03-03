"""Validate command — run validation benchmarks."""

from __future__ import annotations

import asyncio
import json

import typer

from luna.core.config import LunaConfig
from luna.core.luna import LunaEngine
from luna.validation import BenchmarkHarness, VerdictRunner
from luna.validation.verdict_tasks import register_all_tasks


def validate(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    config: str = typer.Option("luna.toml", help="Path to config file"),
) -> None:
    """Run the validation benchmark suite."""
    cfg = LunaConfig.load(config)

    # Baseline run (no consciousness — fresh engine, no checkpoint)
    typer.echo("Running baseline benchmarks...")
    baseline_engine = LunaEngine(cfg)
    baseline_engine.initialize()
    baseline_harness = BenchmarkHarness(timeout_seconds=30.0)
    register_all_tasks(baseline_harness, baseline_engine)
    baseline_report = asyncio.run(baseline_harness.run_all())

    baseline_scores = [r.score for r in baseline_report.results]

    # Consciousness run (same engine, already initialized)
    typer.echo("Running consciousness benchmarks...")
    conscious_engine = LunaEngine(cfg)
    conscious_engine.initialize()
    # Pre-warm with idle steps to let consciousness stabilize
    for _ in range(20):
        conscious_engine.idle_step()

    conscious_harness = BenchmarkHarness(timeout_seconds=30.0)
    register_all_tasks(conscious_harness, conscious_engine)
    conscious_report = asyncio.run(conscious_harness.run_all())

    conscious_scores = [r.score for r in conscious_report.results]

    # Collect phi_iit history from the conscious engine
    phi_history = [conscious_engine.consciousness.compute_phi_iit()]

    # Run verdict
    runner = VerdictRunner()
    verdict = runner.evaluate(baseline_scores, conscious_scores, phi_history)

    typer.echo(f"\n{'='*50}")
    typer.echo(f"VERDICT: {verdict.result}")
    typer.echo(f"Criteria met: {verdict.criteria_met}/{verdict.total_criteria}")
    typer.echo(f"Improvement: {verdict.improvement_pct:.1f}%")
    typer.echo(f"{'='*50}")

    if verbose:
        for c in verdict.criteria:
            status_str = "PASS" if c.passed else "FAIL"
            typer.echo(f"  [{status_str}] {c.name}: {c.value:.4f} (threshold: {c.threshold})")
        typer.echo(json.dumps(verdict.to_dict(), indent=2, default=str))
