"""Phase 5 — Heartbeat: idle evolution, fingerprint, checkpoint, async loop.

16 tests covering:
  - idle_step() on LunaEngine (7 tests)
  - Heartbeat class async behavior (7 tests)
  - HeartbeatSection config (2 tests)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from luna.consciousness.state import ConsciousnessState
from luna.core.config import HeartbeatSection, LunaConfig
from luna.core.luna import LunaEngine
from luna.heartbeat.heartbeat import Heartbeat, HeartbeatStatus
from luna_common.consciousness import get_psi0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Path) -> LunaConfig:
    """Build a minimal LunaConfig for testing."""
    from luna.core.config import (
        ConsciousnessSection,
        LunaSection,
        MemorySection,
        ObservabilitySection,
        PipelineSection,
    )

    return LunaConfig(
        luna=LunaSection(
            version="2.2.0-test",
            agent_name="LUNA",
            data_dir=str(tmp_path),
            pipeline_dir=str(tmp_path / "pipeline"),
        ),
        consciousness=ConsciousnessSection(
            checkpoint_file="cs.json", backup_on_save=False,
        ),
        memory=MemorySection(fractal_root=str(tmp_path / "fractal")),
        pipeline=PipelineSection(root=str(tmp_path / "pipeline")),
        observability=ObservabilitySection(),
        heartbeat=HeartbeatSection(
            interval_seconds=0.01,  # Fast for tests.
            fingerprint_enabled=True,
            checkpoint_interval=5,
        ),
        root_dir=tmp_path,
    )


def _make_engine(tmp_path: Path) -> LunaEngine:
    """Create and initialize a LunaEngine for testing."""
    cfg = _make_config(tmp_path)
    engine = LunaEngine(cfg)
    engine.initialize()
    return engine


# ---------------------------------------------------------------------------
# 1-7: idle_step() on LunaEngine
# ---------------------------------------------------------------------------


def test_idle_step_raises_if_not_initialized(tmp_path: Path):
    cfg = _make_config(tmp_path)
    engine = LunaEngine(cfg)
    # NOT initialized — should raise.
    with pytest.raises(RuntimeError, match="initialize"):
        engine.idle_step()


def test_idle_step_evolves_psi(tmp_path: Path):
    engine = _make_engine(tmp_path)
    psi_before = engine.consciousness.psi.copy()
    engine.idle_step()
    # Psi should have changed (zero deltas still cause coupling + anchoring).
    assert not np.array_equal(psi_before, engine.consciousness.psi)


def test_idle_step_uses_identity_profiles_when_no_cache(tmp_path: Path):
    engine = _make_engine(tmp_path)
    assert engine._cached_psi_others is None
    engine.idle_step()
    # Should not crash — uses default identity profiles.
    assert engine._idle_steps == 1


def test_idle_step_uses_cached_psi_others(tmp_path: Path):
    engine = _make_engine(tmp_path)

    # Manually set cached psi_others.
    fake_others = [
        np.array([0.25, 0.25, 0.25, 0.25]),
        np.array([0.25, 0.25, 0.25, 0.25]),
        np.array([0.25, 0.25, 0.25, 0.25]),
    ]
    engine._cached_psi_others = fake_others

    psi_before = engine.consciousness.psi.copy()
    engine.idle_step()
    # Should use the cached others — psi evolves differently.
    assert not np.array_equal(psi_before, engine.consciousness.psi)


def test_idle_step_increments_counter(tmp_path: Path):
    engine = _make_engine(tmp_path)
    assert engine._idle_steps == 0
    engine.idle_step()
    engine.idle_step()
    engine.idle_step()
    assert engine._idle_steps == 3


def test_idle_step_preserves_simplex(tmp_path: Path):
    engine = _make_engine(tmp_path)
    for _ in range(20):
        engine.idle_step()
    psi = engine.consciousness.psi
    assert abs(psi.sum() - 1.0) < 1e-10
    assert np.all(psi >= 0)


def test_idle_step_identity_drift_minimal(tmp_path: Path):
    engine = _make_engine(tmp_path)
    psi0 = engine.consciousness.psi0.copy()

    # Run many idle steps — with zero info and kappa anchoring,
    # psi should stay close to psi0.
    for _ in range(50):
        engine.idle_step()

    psi = engine.consciousness.psi
    drift = np.linalg.norm(psi - psi0)
    # Drift should be small (< 0.15 after 50 idle steps).
    assert drift < 0.15, f"Excessive identity drift: {drift:.4f}"


# ---------------------------------------------------------------------------
# 8-14: Heartbeat async class
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heartbeat_init(tmp_path: Path):
    engine = _make_engine(tmp_path)
    cfg = engine.config
    hb = Heartbeat(engine, cfg)
    assert not hb.is_running
    assert hb.get_status().idle_steps == 0


@pytest.mark.asyncio
async def test_heartbeat_start_creates_task(tmp_path: Path):
    engine = _make_engine(tmp_path)
    cfg = engine.config
    hb = Heartbeat(engine, cfg)
    task = hb.start()
    assert isinstance(task, asyncio.Task)
    assert hb.is_running
    await hb.stop()


@pytest.mark.asyncio
async def test_heartbeat_stop(tmp_path: Path):
    engine = _make_engine(tmp_path)
    cfg = engine.config
    hb = Heartbeat(engine, cfg)
    hb.start()
    await hb.stop()
    assert not hb.is_running


@pytest.mark.asyncio
async def test_heartbeat_runs_idle_steps(tmp_path: Path):
    engine = _make_engine(tmp_path)
    cfg = engine.config
    hb = Heartbeat(engine, cfg)
    hb.start()
    # Let it tick a few times (interval=0.01s).
    await asyncio.sleep(0.1)
    await hb.stop()
    assert engine._idle_steps >= 2


@pytest.mark.asyncio
async def test_heartbeat_checkpoint_save(tmp_path: Path):
    engine = _make_engine(tmp_path)
    cfg = engine.config
    # checkpoint_interval=5 with fast ticking.
    hb = Heartbeat(engine, cfg)
    hb.start()
    await asyncio.sleep(0.15)
    await hb.stop()
    # Should have saved at least one checkpoint.
    status = hb.get_status()
    assert status.checkpoints_saved >= 1
    assert (tmp_path / "cs.json").exists()


@pytest.mark.asyncio
async def test_heartbeat_fingerprint_check(tmp_path: Path):
    engine = _make_engine(tmp_path)
    cfg = engine.config
    hb = Heartbeat(engine, cfg)
    hb.start()
    await asyncio.sleep(0.05)
    await hb.stop()
    # Luna's psi should still match psi0 dominant component.
    status = hb.get_status()
    assert status.identity_ok is True


@pytest.mark.asyncio
async def test_heartbeat_status(tmp_path: Path):
    engine = _make_engine(tmp_path)
    cfg = engine.config
    hb = Heartbeat(engine, cfg)
    status = hb.get_status()
    assert isinstance(status, HeartbeatStatus)
    assert status.is_running is False
    assert status.idle_steps == 0

    hb.start()
    await asyncio.sleep(0.05)
    status = hb.get_status()
    assert status.is_running is True
    assert status.last_beat is not None
    await hb.stop()


# ---------------------------------------------------------------------------
# 15-16: HeartbeatSection config
# ---------------------------------------------------------------------------


def test_heartbeat_section_defaults():
    hs = HeartbeatSection()
    assert hs.interval_seconds == 30.0
    assert hs.fingerprint_enabled is True
    assert hs.checkpoint_interval == 100


def test_heartbeat_section_checkpoint_interval_from_toml(tmp_path: Path):
    """Verify that checkpoint_interval is loaded from luna.toml."""
    toml_content = """\
[luna]
version = "test"
agent_name = "LUNA"
data_dir = "data"
pipeline_dir = "pipeline"

[consciousness]
checkpoint_file = "cs.json"

[memory]
fractal_root = "fractal"

[pipeline]
root = "pipeline"

[heartbeat]
interval_seconds = 15
fingerprint_enabled = false
checkpoint_interval = 42
"""
    toml_path = tmp_path / "luna.toml"
    toml_path.write_text(toml_content)

    cfg = LunaConfig.load(toml_path)
    assert cfg.heartbeat.checkpoint_interval == 42
    assert cfg.heartbeat.interval_seconds == 15.0
    assert cfg.heartbeat.fingerprint_enabled is False
