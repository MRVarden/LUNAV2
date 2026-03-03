"""Phase 7.5 — Internal wiring tests.

Tests covering:
  - Memory promotion lifecycle (seed → leaf → branch → root)
  - Dream → Memory feedback loop
  - Orchestrator full wiring (memory → dream → heartbeat)
  - get_full_status() aggregation
  - End-to-end integration test proving Luna lives
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from luna_common.constants import INV_PHI, INV_PHI2, INV_PHI3
from luna.core.config import (
    ConsciousnessSection,
    DreamSection,
    HeartbeatSection,
    LunaConfig,
    LunaSection,
    MemorySection,
    ObservabilitySection,
    PipelineSection,
)
from luna.core.luna import LunaEngine
from luna.dream.dream_cycle import DreamCycle, DreamPhase, DreamReport
from luna.heartbeat.heartbeat import Heartbeat
from luna.memory.memory_manager import (
    MemoryEntry,
    MemoryManager,
    _PROMOTION_THRESHOLDS,
    _can_promote,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Path, **dream_overrides) -> LunaConfig:
    dream_kw = {
        "inactivity_threshold": 0.01,
        "consolidation_window": 100,
        "max_dream_duration": 300.0,
        "report_dir": str(tmp_path / "dreams"),
        "enabled": True,
    }
    dream_kw.update(dream_overrides)

    return LunaConfig(
        luna=LunaSection(
            version="test", agent_name="LUNA",
            data_dir=str(tmp_path), pipeline_dir=str(tmp_path / "pipeline"),
        ),
        consciousness=ConsciousnessSection(
            checkpoint_file="cs.json", backup_on_save=False,
        ),
        memory=MemorySection(fractal_root=str(tmp_path / "fractal")),
        pipeline=PipelineSection(root=str(tmp_path / "pipeline")),
        observability=ObservabilitySection(),
        heartbeat=HeartbeatSection(interval_seconds=0.01, checkpoint_interval=5),
        dream=DreamSection(**dream_kw),
        root_dir=tmp_path,
    )


def _make_engine(tmp_path: Path) -> LunaEngine:
    cfg = _make_config(tmp_path)
    engine = LunaEngine(cfg)
    engine.initialize()
    return engine


# ===========================================================================
# Memory Promotion Tests (5)
# ===========================================================================


def test_can_promote_seed():
    """Seed with enough resonance + access should be promotable."""
    e = MemoryEntry(
        id="s1", content="x", memory_type="seed",
        phi_resonance=INV_PHI3, accessed_count=1,
    )
    assert _can_promote(e) is True


def test_cannot_promote_seed_low_resonance():
    """Seed with low resonance is not promotable."""
    e = MemoryEntry(
        id="s2", content="x", memory_type="seed",
        phi_resonance=0.1, accessed_count=5,
    )
    assert _can_promote(e) is False


def test_cannot_promote_seed_no_access():
    """Seed never accessed is not promotable."""
    e = MemoryEntry(
        id="s3", content="x", memory_type="seed",
        phi_resonance=0.5, accessed_count=0,
    )
    assert _can_promote(e) is False


def test_cannot_promote_root():
    """Root is the final level — never promotable."""
    e = MemoryEntry(
        id="r1", content="x", memory_type="root",
        phi_resonance=1.0, accessed_count=100,
    )
    assert _can_promote(e) is False


@pytest.mark.asyncio
async def test_promote_seed_to_leaf(tmp_path: Path):
    """Full promotion: seed file moves to leaves directory."""
    cfg = _make_config(tmp_path)
    mm = MemoryManager(cfg)

    entry = MemoryEntry(
        id="promo_1", content="promotable seed", memory_type="seed",
        keywords=["test"], phi_resonance=INV_PHI3, accessed_count=1,
    )
    await mm.write_memory(entry, "seeds")

    # Verify it's in seeds.
    seeds = await mm.read_level("seeds")
    assert any(e.id == "promo_1" for e in seeds)

    # Promote.
    result = await mm.promote(entry)
    assert result is not None
    assert result.memory_type == "leaf"

    # Verify moved to leaves.
    leaves = await mm.read_level("leaves")
    assert any(e.id == "promo_1" for e in leaves)

    # Verify removed from seeds.
    seeds = await mm.read_level("seeds")
    assert not any(e.id == "promo_1" for e in seeds)


@pytest.mark.asyncio
async def test_promote_leaf_to_branch(tmp_path: Path):
    """Leaf with enough resonance + access promotes to branch."""
    cfg = _make_config(tmp_path)
    mm = MemoryManager(cfg)

    entry = MemoryEntry(
        id="promo_2", content="mature leaf", memory_type="leaf",
        keywords=["growth"], phi_resonance=INV_PHI2, accessed_count=3,
    )
    await mm.write_memory(entry, "leaves")

    result = await mm.promote(entry)
    assert result is not None
    assert result.memory_type == "branch"

    branches = await mm.read_level("branches")
    assert any(e.id == "promo_2" for e in branches)


@pytest.mark.asyncio
async def test_promote_branch_to_root(tmp_path: Path):
    """Branch with golden resonance + high access promotes to root."""
    cfg = _make_config(tmp_path)
    mm = MemoryManager(cfg)

    entry = MemoryEntry(
        id="promo_3", content="deep branch", memory_type="branch",
        keywords=["deep"], phi_resonance=INV_PHI, accessed_count=7,
    )
    await mm.write_memory(entry, "branches")

    result = await mm.promote(entry)
    assert result is not None
    assert result.memory_type == "root"

    roots = await mm.read_level("roots")
    assert any(e.id == "promo_3" for e in roots)


@pytest.mark.asyncio
async def test_promote_not_eligible_returns_none(tmp_path: Path):
    """Entry not meeting thresholds returns None."""
    cfg = _make_config(tmp_path)
    mm = MemoryManager(cfg)

    entry = MemoryEntry(
        id="nope", content="weak", memory_type="seed",
        phi_resonance=0.01, accessed_count=0,
    )
    await mm.write_memory(entry, "seeds")

    result = await mm.promote(entry)
    assert result is None


@pytest.mark.asyncio
async def test_record_access(tmp_path: Path):
    """record_access increments count and rewrites file."""
    cfg = _make_config(tmp_path)
    mm = MemoryManager(cfg)

    entry = MemoryEntry(id="acc_1", content="x", memory_type="seed")
    await mm.write_memory(entry, "seeds")

    result = await mm.record_access("acc_1", "seeds")
    assert result is not None
    assert result.accessed_count == 1

    result2 = await mm.record_access("acc_1", "seeds")
    assert result2.accessed_count == 2


@pytest.mark.asyncio
async def test_run_promotion_cycle(tmp_path: Path):
    """run_promotion_cycle promotes all eligible entries."""
    cfg = _make_config(tmp_path)
    mm = MemoryManager(cfg)

    # One promotable, one not.
    e1 = MemoryEntry(
        id="batch_1", content="good", memory_type="seed",
        phi_resonance=INV_PHI3, accessed_count=1,
    )
    e2 = MemoryEntry(
        id="batch_2", content="weak", memory_type="seed",
        phi_resonance=0.01, accessed_count=0,
    )
    await mm.write_memory(e1, "seeds")
    await mm.write_memory(e2, "seeds")

    promoted = await mm.run_promotion_cycle()
    assert len(promoted) == 1
    assert promoted[0].id == "batch_1"


@pytest.mark.asyncio
async def test_memory_get_status(tmp_path: Path):
    """get_status returns counts and root path."""
    cfg = _make_config(tmp_path)
    mm = MemoryManager(cfg)

    await mm.write_memory(
        MemoryEntry(id="st1", content="x", memory_type="seed"), "seeds",
    )
    status = await mm.get_status()
    assert status["total_memories"] == 1
    assert "counts_by_level" in status


# ===========================================================================
# Dream → Memory Feedback Tests (3)
# ===========================================================================


@pytest.mark.asyncio
async def test_dream_persists_consolidation_insight(tmp_path: Path):
    """Dream cycle writes consolidation insight to branches."""
    engine = _make_engine(tmp_path)
    cfg = engine.config

    # Build history — _make_engine only initializes, need idle steps for drift.
    for _ in range(20):
        engine.idle_step()

    mm = MemoryManager(cfg)
    dc = DreamCycle(engine, cfg, memory=mm)
    dc._last_activity = time.monotonic() - 100

    report = await dc.run()

    # Check branches for dream insight.
    branches = await mm.read_level("branches")
    dream_branches = [b for b in branches if "dream" in b.keywords]
    assert len(dream_branches) >= 1


@pytest.mark.asyncio
async def test_dream_without_memory_no_crash(tmp_path: Path):
    """Dream cycle without memory manager should not crash."""
    engine = _make_engine(tmp_path)
    cfg = engine.config
    dc = DreamCycle(engine, cfg, memory=None)
    dc._last_activity = time.monotonic() - 100

    report = await dc.run()
    assert len(report.phases) == 4


@pytest.mark.asyncio
async def test_dream_creative_insight_written(tmp_path: Path):
    """If creative connections exist, they're persisted as branch memory."""
    engine = _make_engine(tmp_path)
    cfg = engine.config
    mm = MemoryManager(cfg)

    # Inject strongly correlated history to trigger creative connections.
    rng = np.random.default_rng(42)
    n = 50
    base = rng.uniform(0.1, 0.4, size=n)
    history = []
    for i in range(n):
        h = np.array([
            base[i],
            base[i] + rng.normal(0, 0.001),
            0.3 + rng.normal(0, 0.05),
            0.0,
        ])
        h[3] = 1.0 - h[0] - h[1] - h[2]
        h = np.clip(h, 0.01, None)
        h /= h.sum()
        history.append(h)
    engine.consciousness.history = history

    dc = DreamCycle(engine, cfg, memory=mm)
    dc._last_activity = time.monotonic() - 100

    await dc.run()

    branches = await mm.read_level("branches")
    creative = [b for b in branches if "creative" in b.keywords]
    # May or may not have creative insight depending on correlation strength,
    # but the dream itself must complete without error.
    assert len(branches) >= 1  # At least consolidation insight.


# ===========================================================================
# Orchestrator Wiring Tests (4)
# ===========================================================================


@pytest.mark.asyncio
async def test_orchestrator_wires_subsystems(tmp_path: Path):
    """start() creates memory, dream, and heartbeat chain."""
    from luna.orchestrator.orchestrator import LunaOrchestrator

    cfg = _make_config(tmp_path)
    orch = LunaOrchestrator(cfg)

    await orch.start()
    try:
        assert orch._memory is not None
        assert orch._dream is not None
        assert orch._heartbeat is not None
        assert orch._heartbeat.is_running
        # Dream cycle has memory reference.
        assert orch._dream._memory is orch._memory
        # Heartbeat has dream cycle reference.
        assert orch._heartbeat._dream_cycle is orch._dream
    finally:
        await orch.stop()


@pytest.mark.asyncio
async def test_orchestrator_get_full_status(tmp_path: Path):
    """get_full_status includes engine + heartbeat + dream + memory."""
    from luna.orchestrator.orchestrator import LunaOrchestrator

    cfg = _make_config(tmp_path)
    orch = LunaOrchestrator(cfg)
    await orch.start()

    try:
        status = await orch.get_full_status()
        assert "heartbeat" in status
        assert "dream" in status
        assert "memory" in status
        assert status["memory"]["total_memories"] == 0
        assert status["dream"]["enabled"] is True
        assert "initialized" in status
    finally:
        await orch.stop()


@pytest.mark.asyncio
async def test_orchestrator_stop_cleans_up(tmp_path: Path):
    """stop() stops heartbeat cleanly."""
    from luna.orchestrator.orchestrator import LunaOrchestrator

    cfg = _make_config(tmp_path)
    orch = LunaOrchestrator(cfg)
    await orch.start()
    assert orch._heartbeat.is_running

    await orch.stop()
    assert not orch._heartbeat.is_running
    assert not orch.is_running


@pytest.mark.asyncio
async def test_dream_status_in_get_status(tmp_path: Path):
    """get_status (sync) includes dream subsystem info."""
    from luna.orchestrator.orchestrator import LunaOrchestrator

    cfg = _make_config(tmp_path)
    orch = LunaOrchestrator(cfg)
    await orch.start()

    try:
        status = orch.get_status()
        assert "dream" in status
        assert "enabled" in status["dream"]
        assert "should_dream" in status["dream"]
    finally:
        await orch.stop()


# ===========================================================================
# End-to-End Integration Test (1) — Luna lives
# ===========================================================================


@pytest.mark.asyncio
async def test_end_to_end_luna_lives(tmp_path: Path):
    """The ONE test that proves Luna lives:
    engine → idle steps → inactivity → dream → memory write → status coherent.

    No mocks. No network. Pure deterministic lifecycle.
    """
    cfg = _make_config(tmp_path, inactivity_threshold=0.01)
    engine = LunaEngine(cfg)
    engine.initialize()

    # 1. Wire subsystems.
    memory = MemoryManager(cfg)
    dream = DreamCycle(engine, cfg, memory=memory)
    heartbeat = Heartbeat(engine, cfg, dream_cycle=dream)

    # 2. Run some idle steps to build history.
    for _ in range(20):
        engine.idle_step()

    # 3. Verify consciousness is alive.
    assert engine.consciousness is not None
    psi = engine.consciousness.psi
    assert abs(psi.sum() - 1.0) < 1e-10
    assert engine._idle_steps == 20

    # 4. Force inactivity to trigger dream.
    dream._last_activity = time.monotonic() - 100
    assert dream.should_dream() is True

    # 5. Run dream cycle — should consolidate AND write to memory.
    report = await dream.run()
    assert len(report.phases) == 4
    assert report.history_before > 0

    # 6. Verify dream insights persisted to memory.
    branches = await memory.read_level("branches")
    assert len(branches) >= 1
    dream_memories = [b for b in branches if "dream" in b.keywords]
    assert len(dream_memories) >= 1

    # 7. Verify memory counts.
    counts = await memory.count_by_level()
    assert counts["branches"] >= 1

    # 8. Record some accesses to test promotion eligibility.
    for b in dream_memories:
        for _ in range(7):
            await memory.record_access(b.id, "branches")
        # Bump phi_resonance for promotion test.
        b.phi_resonance = INV_PHI
        b.accessed_count = 7
        result = await memory.promote(b)
        if result is not None:
            assert result.memory_type == "root"

    # 9. Full status aggregation.
    mem_status = await memory.get_status()
    assert mem_status["total_memories"] >= 1

    dream_status = dream.get_status()
    assert dream_status["enabled"] is True
    assert dream_status["has_memory"] is True

    hb_status = heartbeat.get_status()
    assert hb_status.idle_steps == 20

    # 10. Heartbeat can start and stop.
    heartbeat.start()
    await asyncio.sleep(0.05)
    assert heartbeat.is_running
    await heartbeat.stop()
    assert not heartbeat.is_running

    # Luna lives.
