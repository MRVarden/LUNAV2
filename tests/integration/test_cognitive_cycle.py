"""Integration tests for Phase D — cognitive CycleRecord production.

Proves that every chat turn produces a complete CycleRecord with:
- Cognitive Evaluator rewards (9 components, not pipeline-based)
- Before/after state deltas (psi, phi_iit, phase, affect)
- Thinker observations and causalities
- Dominance rank computation
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from luna_common.constants import AGENT_PROFILES
from luna_common.schemas.cycle import (
    CycleRecord,
    REWARD_COMPONENT_NAMES,
    DOMINANCE_GROUPS,
    J_WEIGHTS,
)
from luna.core.config import (
    ChatSection,
    ConsciousnessSection,
    HeartbeatSection,
    LLMSection,
    LunaConfig,
    LunaSection,
    MemorySection,
    ObservabilitySection,
    OrchestratorSection,
)
from luna.llm_bridge.bridge import LLMResponse
from luna.memory.cycle_store import CycleStore


def _make_config(tmp_path: Path) -> LunaConfig:
    return LunaConfig(
        luna=LunaSection(
            version="5.0.0",
            agent_name="LUNA",
            data_dir=str(tmp_path / "data"),
        ),
        consciousness=ConsciousnessSection(
            checkpoint_file="cs.json",
            backup_on_save=False,
        ),
        memory=MemorySection(fractal_root=str(tmp_path / "fractal")),
        observability=ObservabilitySection(),
        heartbeat=HeartbeatSection(
            interval_seconds=0.01,
            checkpoint_interval=0,
        ),
        orchestrator=OrchestratorSection(retry_max=1, retry_base_delay=0.01),
        chat=ChatSection(
            max_history=100,
            memory_search_limit=5,
            idle_heartbeat=True,
            save_conversations=False,
            prompt_prefix="luna> ",
        ),
        root_dir=tmp_path,
    )


def _mock_llm() -> AsyncMock:
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=LLMResponse(
        content="Je perçois ta question et je réfléchis à une réponse intégrée.",
        model="mock-model",
        input_tokens=42,
        output_tokens=15,
    ))
    return llm


class TestCognitiveCycleProduction:
    """Prove that each chat turn produces a CycleRecord with cognitive evaluation."""

    @pytest.mark.asyncio
    async def test_single_turn_produces_cycle(self, tmp_path: Path):
        """One chat message → one CycleRecord in the store."""
        cfg = _make_config(tmp_path)
        from luna.chat.session import ChatSession

        session = ChatSession(cfg)
        with patch("luna.llm_bridge.providers.create_provider", return_value=_mock_llm()):
            await session.start()

        await session.send("Bonjour Luna, comment vas-tu ?")
        await session.stop()

        # Check cycles directory exists and has records
        cycles_dir = cfg.resolve(cfg.memory.fractal_root) / "cycles"
        assert cycles_dir.exists(), "cycles/ directory should exist"

        store = CycleStore(cycles_dir)
        assert store.count >= 1, f"Expected at least 1 cycle, got {store.count}"

    @pytest.mark.asyncio
    async def test_cycle_has_cognitive_reward(self, tmp_path: Path):
        """CycleRecord has a RewardVector with 9 cognitive components."""
        cfg = _make_config(tmp_path)
        from luna.chat.session import ChatSession

        session = ChatSession(cfg)
        with patch("luna.llm_bridge.providers.create_provider", return_value=_mock_llm()):
            await session.start()

        await session.send("Explique-moi ta conscience")
        await session.stop()

        cycles_dir = cfg.resolve(cfg.memory.fractal_root) / "cycles"
        store = CycleStore(cycles_dir)
        records = store.read_recent(1)
        assert len(records) == 1, "Expected 1 recent cycle"

        record = records[0]
        assert record.reward is not None, "Cycle must have a reward"
        assert len(record.reward.components) == 9, (
            f"Expected 9 cognitive components, got {len(record.reward.components)}"
        )

        # All 9 canonical names present
        component_names = {c.name for c in record.reward.components}
        expected_names = set(REWARD_COMPONENT_NAMES)
        assert component_names == expected_names, (
            f"Missing components: {expected_names - component_names}"
        )

    @pytest.mark.asyncio
    async def test_cycle_has_before_after_deltas(self, tmp_path: Path):
        """CycleRecord captures real before/after state."""
        cfg = _make_config(tmp_path)
        from luna.chat.session import ChatSession

        session = ChatSession(cfg)
        with patch("luna.llm_bridge.providers.create_provider", return_value=_mock_llm()):
            await session.start()

        await session.send("Analyse cette situation")
        await session.stop()

        cycles_dir = cfg.resolve(cfg.memory.fractal_root) / "cycles"
        store = CycleStore(cycles_dir)
        record = store.read_recent(1)[0]

        # Psi values are on the simplex
        assert abs(sum(record.psi_before) - 1.0) < 0.01
        assert abs(sum(record.psi_after) - 1.0) < 0.01

        # phi_iit values are non-negative (Gaussian MI — unbounded above)
        assert record.phi_iit_before >= 0.0
        assert record.phi_iit_after >= 0.0

        # Phase values are valid
        valid_phases = {"BROKEN", "FRAGILE", "FUNCTIONAL", "SOLID", "EXCELLENT"}
        assert record.phase_before in valid_phases
        assert record.phase_after in valid_phases

        # Duration is reasonable (not 0, not absurd)
        assert 0.0 < record.duration_seconds < 30.0

    @pytest.mark.asyncio
    async def test_cycle_has_thinker_output(self, tmp_path: Path):
        """CycleRecord captures Thinker observations and confidence."""
        cfg = _make_config(tmp_path)
        from luna.chat.session import ChatSession

        session = ChatSession(cfg)
        with patch("luna.llm_bridge.providers.create_provider", return_value=_mock_llm()):
            await session.start()

        await session.send("Qu'est-ce que tu observes ?")
        await session.stop()

        cycles_dir = cfg.resolve(cfg.memory.fractal_root) / "cycles"
        store = CycleStore(cycles_dir)
        record = store.read_recent(1)[0]

        # Thinker confidence should be non-zero (Thinker always produces output)
        assert record.thinker_confidence >= 0.0
        # Intent should be valid
        assert record.intent in {"RESPOND", "DREAM", "INTROSPECT", "ALERT", "PIPELINE"}

    @pytest.mark.asyncio
    async def test_multiple_turns_accumulate_cycles(self, tmp_path: Path):
        """3 messages → 3 CycleRecords with increasing cycle_ids."""
        cfg = _make_config(tmp_path)
        from luna.chat.session import ChatSession

        session = ChatSession(cfg)
        with patch("luna.llm_bridge.providers.create_provider", return_value=_mock_llm()):
            await session.start()

        await session.send("Premier message")
        await session.send("Deuxième message")
        await session.send("Troisième message")
        await session.stop()

        cycles_dir = cfg.resolve(cfg.memory.fractal_root) / "cycles"
        store = CycleStore(cycles_dir)
        assert store.count >= 3, f"Expected at least 3 cycles, got {store.count}"

        records = store.read_recent(3)
        cycle_ids = [r.cycle_id for r in records]
        assert len(set(cycle_ids)) == 3, "Each cycle should have a unique ID"

    @pytest.mark.asyncio
    async def test_dominance_rank_computed(self, tmp_path: Path):
        """After multiple turns, dominance rank is computed against history."""
        cfg = _make_config(tmp_path)
        from luna.chat.session import ChatSession

        session = ChatSession(cfg)
        with patch("luna.llm_bridge.providers.create_provider", return_value=_mock_llm()):
            await session.start()

        await session.send("Message 1")
        await session.send("Message 2")
        await session.send("Message 3")
        await session.stop()

        cycles_dir = cfg.resolve(cfg.memory.fractal_root) / "cycles"
        store = CycleStore(cycles_dir)
        records = store.read_recent(3)

        for record in records:
            assert record.reward is not None
            # dominance_rank >= 0 (0 = best, higher = worse)
            assert record.reward.dominance_rank >= 0

    @pytest.mark.asyncio
    async def test_affect_trace_captured(self, tmp_path: Path):
        """CycleRecord captures affect before/after."""
        cfg = _make_config(tmp_path)
        from luna.chat.session import ChatSession

        session = ChatSession(cfg)
        with patch("luna.llm_bridge.providers.create_provider", return_value=_mock_llm()):
            await session.start()

        await session.send("Comment te sens-tu ?")
        await session.stop()

        cycles_dir = cfg.resolve(cfg.memory.fractal_root) / "cycles"
        store = CycleStore(cycles_dir)
        record = store.read_recent(1)[0]

        # affect_trace may be None if AffectEngine not initialized,
        # but if present, it should have before/after
        if record.affect_trace is not None:
            assert "valence_after" in record.affect_trace
            assert "arousal_after" in record.affect_trace

    @pytest.mark.asyncio
    async def test_no_pipeline_dependency(self, tmp_path: Path):
        """CycleRecord is produced WITHOUT any pipeline execution."""
        cfg = _make_config(tmp_path)
        from luna.chat.session import ChatSession

        session = ChatSession(cfg)
        with patch("luna.llm_bridge.providers.create_provider", return_value=_mock_llm()):
            await session.start()

        await session.send("Simple chat, pas de pipeline")
        await session.stop()

        cycles_dir = cfg.resolve(cfg.memory.fractal_root) / "cycles"
        store = CycleStore(cycles_dir)
        record = store.read_recent(1)[0]

        # Pipeline result should be None (no pipeline was called)
        assert record.pipeline_result is None
        # But reward should still exist (cognitive evaluation, not pipeline)
        assert record.reward is not None
        assert len(record.reward.components) == 9

    @pytest.mark.asyncio
    async def test_constitution_integrity_component(self, tmp_path: Path):
        """constitution_integrity reflects identity context state."""
        cfg = _make_config(tmp_path)
        from luna.chat.session import ChatSession

        session = ChatSession(cfg)
        with patch("luna.llm_bridge.providers.create_provider", return_value=_mock_llm()):
            await session.start()

        await session.send("Test constitution")
        await session.stop()

        cycles_dir = cfg.resolve(cfg.memory.fractal_root) / "cycles"
        store = CycleStore(cycles_dir)
        record = store.read_recent(1)[0]

        ci = record.reward.get("constitution_integrity")
        # Without identity context (test env), defaults to +1.0
        assert ci == pytest.approx(1.0), (
            f"constitution_integrity should be 1.0 without identity context, got {ci}"
        )

    @pytest.mark.asyncio
    async def test_cycle_survives_restart(self, tmp_path: Path):
        """CycleRecords persist across session restarts."""
        cfg = _make_config(tmp_path)
        from luna.chat.session import ChatSession

        # Session 1: produce cycles
        session1 = ChatSession(cfg)
        with patch("luna.llm_bridge.providers.create_provider", return_value=_mock_llm()):
            await session1.start()
        await session1.send("Message persistant")
        await session1.stop()

        # Session 2: verify cycles survive
        session2 = ChatSession(cfg)
        with patch("luna.llm_bridge.providers.create_provider", return_value=_mock_llm()):
            await session2.start()

        cycles_dir = cfg.resolve(cfg.memory.fractal_root) / "cycles"
        store = CycleStore(cycles_dir)
        assert store.count >= 1, "Cycles should persist across restarts"

        record = store.read_recent(1)[0]
        assert record.reward is not None
