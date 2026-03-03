"""Integration tests for Luna v2.4.0 persistence gaps.

Proves that Luna's memory survives restarts:
- Gap 1: PhiScorer metrics in consciousness checkpoint
- Gap 2: Agent profiles from dream consolidation
- Gap 3: Chat history persistence

Each gap is tested for:
1. Roundtrip (save -> load -> values match)
2. Backward compatibility (old format -> graceful defaults)
3. Corruption recovery (bad file -> fallback, no crash)
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from luna_common.constants import AGENT_PROFILES, METRIC_NAMES
from luna_common.phi_engine.scorer import PhiScorer
from luna.consciousness.state import ConsciousnessState
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
    PipelineSection,
)
from luna.dream.consolidation import load_profiles, save_profiles
from luna.llm_bridge.bridge import LLMResponse


# ---------------------------------------------------------------------------
#  Shared helpers
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Path, **chat_overrides) -> LunaConfig:
    """Build a minimal LunaConfig rooted in tmp_path."""
    chat_kw = {
        "max_history": 100,
        "memory_search_limit": 5,
        "idle_heartbeat": True,
        "save_conversations": False,  # avoid writing seeds in tests
        "prompt_prefix": "luna> ",
    }
    chat_kw.update(chat_overrides)
    return LunaConfig(
        luna=LunaSection(
            version="2.4.0",
            agent_name="LUNA",
            data_dir=str(tmp_path / "data"),
            pipeline_dir=str(tmp_path / "pipeline"),
        ),
        consciousness=ConsciousnessSection(
            checkpoint_file="cs.json",
            backup_on_save=False,
        ),
        memory=MemorySection(fractal_root=str(tmp_path / "fractal")),
        pipeline=PipelineSection(root=str(tmp_path / "pipeline")),
        observability=ObservabilitySection(),
        heartbeat=HeartbeatSection(
            interval_seconds=0.01,
            checkpoint_interval=0,  # disable periodic checkpoint in tests
        ),
        orchestrator=OrchestratorSection(retry_max=1, retry_base_delay=0.01),
        chat=ChatSection(**chat_kw),
        root_dir=tmp_path,
    )


def _mock_llm() -> AsyncMock:
    """Mock LLMBridge returning a fixed response."""
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=LLMResponse(
        content="Bonjour, je suis Luna.",
        model="mock-model",
        input_tokens=42,
        output_tokens=10,
    ))
    return llm


def _make_phi_snapshot() -> dict:
    """Build a realistic phi_metrics snapshot with all 7 metrics."""
    ts = datetime.now(timezone.utc).isoformat()
    return {
        "security_integrity":  {"value": 0.95, "source": "measured", "timestamp": ts},
        "coverage_pct":        {"value": 0.72, "source": "measured", "timestamp": ts},
        "complexity_score":    {"value": 0.80, "source": "bootstrap", "timestamp": ts},
        "test_ratio":          {"value": 0.65, "source": "measured", "timestamp": ts},
        "abstraction_ratio":   {"value": 0.58, "source": "bootstrap", "timestamp": ts},
        "function_size_score": {"value": 0.88, "source": "measured", "timestamp": ts},
        "performance_score":   {"value": 0.91, "source": "measured", "timestamp": ts},
    }


# ═══════════════════════════════════════════════════════════════════════════
#  GAP 1 — PhiScorer metrics in consciousness checkpoint
# ═══════════════════════════════════════════════════════════════════════════


class TestGap1PhiMetricsPersistence:
    """Prove that PhiScorer metrics survive a checkpoint roundtrip."""

    def test_roundtrip_save_load(self, tmp_path: Path):
        """Save checkpoint with phi_metrics, load it back, all fields match."""
        ckpt = tmp_path / "cs_gap1.json"
        phi_snap = _make_phi_snapshot()

        # Save
        state = ConsciousnessState("LUNA")
        state.save_checkpoint(ckpt, phi_metrics=phi_snap)

        # Load
        loaded = ConsciousnessState.load_checkpoint(ckpt, agent_name="LUNA")
        assert loaded.phi_metrics_snapshot is not None, (
            "phi_metrics_snapshot should not be None after loading v2.4 checkpoint"
        )

        # Every metric name present with correct value
        for name in METRIC_NAMES:
            assert name in loaded.phi_metrics_snapshot, (
                f"Metric '{name}' missing from loaded snapshot"
            )
            expected_val = phi_snap[name]["value"]
            actual_val = loaded.phi_metrics_snapshot[name]["value"]
            assert actual_val == pytest.approx(expected_val, abs=1e-12), (
                f"Metric '{name}' value mismatch: expected {expected_val}, got {actual_val}"
            )

        # Source and timestamp preserved
        for name in METRIC_NAMES:
            assert loaded.phi_metrics_snapshot[name]["source"] == phi_snap[name]["source"]
            assert loaded.phi_metrics_snapshot[name]["timestamp"] == phi_snap[name]["timestamp"]

    def test_backward_compat_v22_no_phi_metrics(self, tmp_path: Path):
        """v2.2 checkpoint (no phi_metrics key) loads without crash; snapshot is None."""
        ckpt = tmp_path / "cs_v22.json"
        data = {
            "version": "2.2.0",
            "type": "consciousness_state",
            "agent_name": "LUNA",
            "psi": [0.25, 0.35, 0.25, 0.15],
            "psi0": [0.25, 0.35, 0.25, 0.15],
            "step_count": 42,
            "phase": "FUNCTIONAL",
            "phi_iit": 0.0,
            "history_tail": [],
        }
        ckpt.write_text(json.dumps(data))

        loaded = ConsciousnessState.load_checkpoint(ckpt, agent_name="LUNA")
        assert loaded.phi_metrics_snapshot is None, (
            "v2.2 checkpoint without phi_metrics should give None snapshot"
        )
        assert loaded.step_count == 42
        np.testing.assert_allclose(
            loaded.psi, [0.25, 0.35, 0.25, 0.15], atol=1e-10,
        )

    def test_backward_compat_v20_legacy(self, tmp_path: Path):
        """v2.0 checkpoint (no psi at all) loads as fresh state with defaults."""
        ckpt = tmp_path / "cs_v20.json"
        data = {"version": "2.0.0", "type": "consciousness_state"}
        ckpt.write_text(json.dumps(data))

        loaded = ConsciousnessState.load_checkpoint(ckpt, agent_name="LUNA")
        assert loaded.phi_metrics_snapshot is None
        # Should get the default LUNA profile
        np.testing.assert_allclose(
            loaded.psi0, list(AGENT_PROFILES["LUNA"]), atol=1e-10,
        )

    def test_corruption_invalid_json(self, tmp_path: Path):
        """Garbage file raises (not silent corruption)."""
        ckpt = tmp_path / "cs_garbage.json"
        ckpt.write_text("NOT VALID JSON {{{{")

        with pytest.raises((json.JSONDecodeError, ValueError)):
            ConsciousnessState.load_checkpoint(ckpt, agent_name="LUNA")

    def test_corruption_missing_psi(self, tmp_path: Path):
        """Valid JSON v2.4 but missing 'psi' key raises ValueError."""
        ckpt = tmp_path / "cs_no_psi.json"
        data = {
            "version": "2.4.0",
            "type": "consciousness_state",
            "agent_name": "LUNA",
            # no "psi" key!
            "step_count": 10,
        }
        ckpt.write_text(json.dumps(data))

        with pytest.raises(KeyError):
            ConsciousnessState.load_checkpoint(ckpt, agent_name="LUNA")

    def test_corruption_file_not_found(self, tmp_path: Path):
        """Missing checkpoint file raises FileNotFoundError."""
        missing = tmp_path / "nonexistent.json"
        with pytest.raises(FileNotFoundError):
            ConsciousnessState.load_checkpoint(missing, agent_name="LUNA")

    def test_phi_metrics_partial_restore(self, tmp_path: Path):
        """Only 3 of 7 metrics in checkpoint -- those 3 restored, others remain None."""
        ckpt = tmp_path / "cs_partial.json"
        partial_snap = {
            "security_integrity": {"value": 0.95},
            "coverage_pct": {"value": 0.72},
            "test_ratio": {"value": 0.60},
        }
        state = ConsciousnessState("LUNA")
        state.save_checkpoint(ckpt, phi_metrics=partial_snap)

        loaded = ConsciousnessState.load_checkpoint(ckpt, agent_name="LUNA")
        assert loaded.phi_metrics_snapshot is not None

        # Feed into PhiScorer
        scorer = PhiScorer()
        count = scorer.restore(loaded.phi_metrics_snapshot)
        assert count == 3, f"Expected 3 metrics restored, got {count}"

        # Restored metrics have correct values
        assert scorer.get_metric("security_integrity") == pytest.approx(0.95)
        assert scorer.get_metric("coverage_pct") == pytest.approx(0.72)
        assert scorer.get_metric("test_ratio") == pytest.approx(0.60)

        # Unrestored metrics are None
        assert scorer.get_metric("complexity_score") is None
        assert scorer.get_metric("abstraction_ratio") is None
        assert scorer.get_metric("function_size_score") is None
        assert scorer.get_metric("performance_score") is None

    def test_phi_metrics_with_nan_ignored(self, tmp_path: Path):
        """NaN value in phi_metrics is skipped during PhiScorer.restore()."""
        ckpt = tmp_path / "cs_nan.json"
        snap = {
            "security_integrity": {"value": 0.95},
            "coverage_pct": {"value": float("nan")},  # Will serialize as NaN
        }
        state = ConsciousnessState("LUNA")
        state.save_checkpoint(ckpt, phi_metrics=snap)

        loaded = ConsciousnessState.load_checkpoint(ckpt, agent_name="LUNA")
        scorer = PhiScorer()
        count = scorer.restore(loaded.phi_metrics_snapshot)

        # NaN should be skipped by PhiScorer.restore (isfinite check)
        assert count == 1, (
            f"Expected 1 metric restored (NaN skipped), got {count}"
        )
        assert scorer.get_metric("security_integrity") == pytest.approx(0.95)
        assert scorer.get_metric("coverage_pct") is None

    def test_scorer_snapshot_restore_roundtrip(self):
        """PhiScorer: update -> snapshot -> restore into new scorer -> score matches."""
        scorer1 = PhiScorer()
        for name in METRIC_NAMES:
            scorer1.update(name, 0.75)
        score1 = scorer1.score()
        snap = scorer1.snapshot()

        scorer2 = PhiScorer()
        count = scorer2.restore(snap)
        assert count == 7, f"Expected 7 metrics restored, got {count}"
        score2 = scorer2.score()

        assert score2 == pytest.approx(score1, abs=1e-10), (
            f"Score mismatch after restore: {score1} vs {score2}"
        )

    def test_scorer_restore_unknown_metrics_ignored(self):
        """Unknown metric names in snapshot are silently ignored (forward compat)."""
        scorer = PhiScorer()
        snap = {
            "security_integrity": {"value": 0.90},
            "future_metric_v3": {"value": 0.50},  # Unknown -- should be skipped
        }
        count = scorer.restore(snap)
        assert count == 1
        assert scorer.get_metric("security_integrity") == pytest.approx(0.90)

    def test_checkpoint_contains_version_and_structure(self, tmp_path: Path):
        """Saved checkpoint has required top-level keys for forward readers."""
        ckpt = tmp_path / "cs_structure.json"
        state = ConsciousnessState("LUNA")
        state.save_checkpoint(ckpt, phi_metrics=_make_phi_snapshot())

        with open(ckpt) as f:
            data = json.load(f)

        required_keys = {
            "version", "type", "agent_name", "psi", "psi0",
            "step_count", "phase", "phi_iit", "history_tail", "phi_metrics",
        }
        assert required_keys.issubset(data.keys()), (
            f"Missing keys: {required_keys - data.keys()}"
        )
        assert data["version"] == "2.4.0"
        assert data["type"] == "consciousness_state"

    def test_atomic_write_no_tmp_left(self, tmp_path: Path):
        """After save_checkpoint, no .tmp file remains."""
        ckpt = tmp_path / "cs_atomic.json"
        state = ConsciousnessState("LUNA")
        state.save_checkpoint(ckpt)

        assert ckpt.exists()
        tmp_file = ckpt.with_suffix(".tmp")
        assert not tmp_file.exists(), (
            f"Temporary file should not remain: {tmp_file}"
        )


# ═══════════════════════════════════════════════════════════════════════════
#  GAP 2 — Agent profiles from dream consolidation
# ═══════════════════════════════════════════════════════════════════════════


class TestGap2AgentProfiles:
    """Prove that agent profiles survive save/load through dream consolidation."""

    def test_roundtrip_save_load(self, tmp_path: Path):
        """save_profiles -> load_profiles -> identical profiles."""
        path = tmp_path / "agent_profiles.json"
        profiles = {
            "LUNA":         (0.25, 0.35, 0.25, 0.15),
            "SAYOHMY":      (0.15, 0.15, 0.20, 0.50),
            "SENTINEL":     (0.50, 0.20, 0.20, 0.10),
            "TESTENGINEER": (0.15, 0.20, 0.50, 0.15),
        }
        save_profiles(path, profiles)
        loaded = load_profiles(path)

        for agent_id, expected in profiles.items():
            assert agent_id in loaded, f"Agent '{agent_id}' missing after roundtrip"
            np.testing.assert_allclose(
                loaded[agent_id], expected, atol=1e-12,
                err_msg=f"Profile mismatch for {agent_id}",
            )

    def test_roundtrip_preserves_tuple_type(self, tmp_path: Path):
        """Loaded profile values are tuples (matching the type contract)."""
        path = tmp_path / "agent_profiles.json"
        save_profiles(path, dict(AGENT_PROFILES))
        loaded = load_profiles(path)

        for agent_id, profile in loaded.items():
            assert isinstance(profile, tuple), (
                f"{agent_id} profile should be tuple, got {type(profile).__name__}"
            )

    def test_missing_file_uses_defaults(self, tmp_path: Path):
        """load_profiles on nonexistent file returns AGENT_PROFILES defaults."""
        path = tmp_path / "does_not_exist.json"
        loaded = load_profiles(path)

        for agent_id in AGENT_PROFILES:
            assert agent_id in loaded, (
                f"Default agent '{agent_id}' missing from fallback"
            )
            np.testing.assert_allclose(
                loaded[agent_id], AGENT_PROFILES[agent_id], atol=1e-12,
            )

    def test_corruption_invalid_json(self, tmp_path: Path):
        """Garbage file -> load_profiles returns AGENT_PROFILES (not crash)."""
        path = tmp_path / "corrupted.json"
        path.write_text("THIS IS NOT JSON !!!")

        loaded = load_profiles(path)
        assert loaded == dict(AGENT_PROFILES), (
            "Corrupted profile file should fall back to AGENT_PROFILES"
        )

    def test_corruption_wrong_type(self, tmp_path: Path):
        """File with a JSON string instead of object -> fallback to defaults."""
        path = tmp_path / "wrong_type.json"
        path.write_text(json.dumps("just a string"))

        # json.loads returns str, iterating .items() on a str raises
        # load_profiles catches all exceptions and falls back
        loaded = load_profiles(path)
        assert loaded == dict(AGENT_PROFILES)

    def test_corruption_missing_agent(self, tmp_path: Path):
        """Valid JSON with only 2 agents -> returns those 2 (no crash)."""
        path = tmp_path / "partial.json"
        partial = {
            "LUNA": [0.25, 0.35, 0.25, 0.15],
            "SAYOHMY": [0.15, 0.15, 0.20, 0.50],
        }
        path.write_text(json.dumps(partial))

        loaded = load_profiles(path)
        assert "LUNA" in loaded
        assert "SAYOHMY" in loaded
        assert "SENTINEL" not in loaded, (
            "Missing agent should not be invented -- only return what's in the file"
        )

    def test_atomic_write_no_tmp_left(self, tmp_path: Path):
        """After save_profiles, no .tmp file remains."""
        path = tmp_path / "agent_profiles.json"
        save_profiles(path, dict(AGENT_PROFILES))

        assert path.exists()
        tmp_file = path.with_suffix(".tmp")
        assert not tmp_file.exists(), (
            f"Temporary file should not remain: {tmp_file}"
        )

    def test_save_creates_valid_json(self, tmp_path: Path):
        """Saved file is valid JSON with lists (not tuples, which are not JSON)."""
        path = tmp_path / "agent_profiles.json"
        save_profiles(path, dict(AGENT_PROFILES))

        with open(path) as f:
            data = json.load(f)

        for agent_id, profile in data.items():
            assert isinstance(profile, list), (
                f"{agent_id} should be serialized as JSON list, got {type(profile).__name__}"
            )
            assert len(profile) == 4, (
                f"{agent_id} profile should have 4 components, got {len(profile)}"
            )

    def test_simplex_preserved_in_saved_profiles(self, tmp_path: Path):
        """Every saved profile sums to ~1.0 (simplex constraint)."""
        path = tmp_path / "agent_profiles.json"
        save_profiles(path, dict(AGENT_PROFILES))

        with open(path) as f:
            data = json.load(f)

        for agent_id, profile in data.items():
            total = sum(profile)
            assert abs(total - 1.0) < 1e-10, (
                f"{agent_id} profile sum = {total}, expected ~1.0"
            )


# ═══════════════════════════════════════════════════════════════════════════
#  GAP 3 — Chat history persistence
# ═══════════════════════════════════════════════════════════════════════════


class TestGap3ChatHistory:
    """Prove that chat history survives session stop/restart."""

    def _history_path(self, cfg: LunaConfig) -> Path:
        """Compute where chat history is stored for the given config."""
        return cfg.resolve(cfg.memory.fractal_root) / "chat_history.json"

    def _write_history(self, cfg: LunaConfig, entries: list[dict]) -> Path:
        """Write raw entries to the chat history file."""
        path = self._history_path(cfg)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(entries, f)
        return path

    @pytest.mark.asyncio
    async def test_roundtrip_save_load(self, tmp_path: Path):
        """Save history via stop(), load it in a fresh session, content matches."""
        cfg = _make_config(tmp_path)
        from luna.chat.session import ChatSession

        # Session 1: start, send a message, stop (saves history)
        session1 = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session1.start()
        await session1.send("Hello Luna")
        await session1.stop()

        hist_path = self._history_path(cfg)
        assert hist_path.exists(), "Chat history file should exist after stop()"

        # Session 2: start (loads history), verify
        session2 = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session2.start()

        assert len(session2.history) >= 2, (
            f"Expected at least 2 history entries (user + assistant), got {len(session2.history)}"
        )
        assert session2.history[0].role == "user"
        assert session2.history[0].content == "Hello Luna"
        assert session2.history[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_missing_file_loads_empty(self, tmp_path: Path):
        """No history file -> session starts with empty history (no crash)."""
        cfg = _make_config(tmp_path)
        from luna.chat.session import ChatSession

        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()

        assert session.history == [], (
            "Fresh session without history file should have empty history"
        )

    @pytest.mark.asyncio
    async def test_corruption_invalid_json(self, tmp_path: Path):
        """Garbage history file -> session starts with empty history (not crash)."""
        cfg = _make_config(tmp_path)
        self._write_history(cfg, [])  # Create the parent dir
        # Overwrite with garbage
        hist_path = self._history_path(cfg)
        hist_path.write_text("NOT JSON {{{")

        from luna.chat.session import ChatSession

        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()

        assert session.history == [], (
            "Corrupted history file should result in empty history"
        )

    @pytest.mark.asyncio
    async def test_corruption_not_a_list(self, tmp_path: Path):
        """Valid JSON but object instead of list -> empty history (not crash)."""
        cfg = _make_config(tmp_path)
        self._write_history(cfg, [])  # creates dir
        hist_path = self._history_path(cfg)
        hist_path.write_text(json.dumps({"not": "a list"}))

        from luna.chat.session import ChatSession

        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()

        assert session.history == [], (
            "History file with object (not list) should result in empty history"
        )

    @pytest.mark.asyncio
    async def test_corruption_missing_fields(self, tmp_path: Path):
        """Entries without 'role' or 'content' are skipped, valid ones loaded."""
        cfg = _make_config(tmp_path)
        entries = [
            {"role": "user", "content": "valid entry", "timestamp": "2026-03-01T00:00:00+00:00"},
            {"role": "user"},                   # missing content
            {"content": "orphan content"},       # missing role
            {},                                  # empty
            {"role": "assistant", "content": "also valid", "timestamp": "2026-03-01T00:01:00+00:00"},
        ]
        self._write_history(cfg, entries)

        from luna.chat.session import ChatSession

        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()

        assert len(session.history) == 2, (
            f"Expected 2 valid entries loaded, got {len(session.history)}"
        )
        assert session.history[0].content == "valid entry"
        assert session.history[1].content == "also valid"

    @pytest.mark.asyncio
    async def test_max_history_respected_on_save(self, tmp_path: Path):
        """Saving respects max_history: 200 entries with max=50 -> only 50 saved."""
        cfg = _make_config(tmp_path, max_history=50)
        from luna.chat.session import ChatSession

        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()

        # Simulate many turns by injecting history directly
        from luna.chat.session import ChatMessage

        for i in range(100):
            session._history.append(
                ChatMessage(role="user", content=f"msg {i}")
            )
            session._history.append(
                ChatMessage(role="assistant", content=f"reply {i}")
            )
        assert len(session._history) == 200

        await session.stop()

        # Load the file and check it has at most 50 entries
        hist_path = self._history_path(cfg)
        with open(hist_path) as f:
            saved = json.load(f)
        assert len(saved) == 50, (
            f"Expected 50 entries saved (max_history), got {len(saved)}"
        )

    @pytest.mark.asyncio
    async def test_max_history_respected_on_load(self, tmp_path: Path):
        """Loading with max_history=10 loads only the last 10 entries."""
        cfg = _make_config(tmp_path, max_history=10)
        ts = "2026-03-01T00:00:00+00:00"
        entries = [
            {"role": "user", "content": f"msg {i}", "timestamp": ts}
            for i in range(30)
        ]
        self._write_history(cfg, entries)

        from luna.chat.session import ChatSession

        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()

        assert len(session.history) == 10, (
            f"Expected 10 entries loaded (max_history), got {len(session.history)}"
        )
        # Should be the LAST 10 entries
        assert session.history[0].content == "msg 20"
        assert session.history[-1].content == "msg 29"

    @pytest.mark.asyncio
    async def test_timestamps_preserved(self, tmp_path: Path):
        """Saved timestamps are restored correctly with timezone info."""
        cfg = _make_config(tmp_path)
        ts = "2026-03-01T12:34:56+00:00"
        entries = [
            {"role": "user", "content": "hello", "timestamp": ts},
        ]
        self._write_history(cfg, entries)

        from luna.chat.session import ChatSession

        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()

        assert len(session.history) == 1
        loaded_ts = session.history[0].timestamp
        assert loaded_ts.tzinfo is not None, "Loaded timestamp must have timezone"
        expected_ts = datetime.fromisoformat(ts)
        assert loaded_ts == expected_ts, (
            f"Timestamp mismatch: loaded={loaded_ts}, expected={expected_ts}"
        )

    @pytest.mark.asyncio
    async def test_atomic_write_no_tmp_left(self, tmp_path: Path):
        """After _save_history, no .tmp file remains."""
        cfg = _make_config(tmp_path)
        from luna.chat.session import ChatSession, ChatMessage

        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()

        session._history.append(ChatMessage(role="user", content="test"))
        await session.stop()

        hist_path = self._history_path(cfg)
        tmp_file = hist_path.with_suffix(".tmp")
        assert not tmp_file.exists(), (
            f"Temporary file should not remain: {tmp_file}"
        )

    @pytest.mark.asyncio
    async def test_empty_history_not_saved(self, tmp_path: Path):
        """Session with no messages does not create a history file."""
        cfg = _make_config(tmp_path)
        from luna.chat.session import ChatSession

        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()
        await session.stop()

        hist_path = self._history_path(cfg)
        assert not hist_path.exists(), (
            "Empty history should not create a file"
        )


# ═══════════════════════════════════════════════════════════════════════════
#  END-TO-END — All 3 gaps together
# ═══════════════════════════════════════════════════════════════════════════


class TestEndToEndPersistence:
    """Prove that a full session lifecycle persists all 3 gaps."""

    @pytest.mark.asyncio
    async def test_session_stop_creates_checkpoint_with_phi_metrics(self, tmp_path: Path):
        """Start session -> send -> stop -> checkpoint has phi_metrics."""
        cfg = _make_config(tmp_path)
        from luna.chat.session import ChatSession

        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()
        await session.send("Hello persistence")
        await session.stop()

        # Verify checkpoint
        ckpt = cfg.resolve(cfg.consciousness.checkpoint_file)
        assert ckpt.exists(), "Checkpoint should exist after stop()"
        with open(ckpt) as f:
            data = json.load(f)
        assert "phi_metrics" in data, (
            "Checkpoint must contain phi_metrics after a chat turn"
        )
        # PhiScorer was fed during _chat_evolve, so at least some metrics present
        assert len(data["phi_metrics"]) > 0, (
            "phi_metrics should have at least one metric after chat"
        )

    @pytest.mark.asyncio
    async def test_session_stop_creates_chat_history(self, tmp_path: Path):
        """Start session -> send -> stop -> chat_history.json exists."""
        cfg = _make_config(tmp_path)
        from luna.chat.session import ChatSession

        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()
        await session.send("Hello history")
        await session.stop()

        hist_path = cfg.resolve(cfg.memory.fractal_root) / "chat_history.json"
        assert hist_path.exists(), "Chat history file should exist after stop()"
        with open(hist_path) as f:
            entries = json.load(f)
        assert len(entries) >= 2, "Should have at least user + assistant entries"
        assert entries[0]["role"] == "user"
        assert entries[0]["content"] == "Hello history"

    @pytest.mark.asyncio
    async def test_session_restart_preserves_phi_metrics(self, tmp_path: Path):
        """Start -> send -> stop -> start again -> PhiScorer values restored."""
        cfg = _make_config(tmp_path)
        from luna.chat.session import ChatSession

        # Session 1: interact and stop
        session1 = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session1.start()
        await session1.send("Measure something")
        score_before = session1.engine.phi_scorer.score()
        all_metrics_before = session1.engine.phi_scorer.get_all_metrics()
        await session1.stop()

        # Session 2: restart and verify
        session2 = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session2.start()

        assert session2.engine.phi_metrics_restored is True, (
            "phi_metrics_restored should be True after reloading checkpoint"
        )
        score_after = session2.engine.phi_scorer.score()
        assert score_after == pytest.approx(score_before, abs=1e-6), (
            f"PhiScorer score mismatch after restart: {score_before} vs {score_after}"
        )

        # Verify each metric individually
        all_metrics_after = session2.engine.phi_scorer.get_all_metrics()
        for name in METRIC_NAMES:
            before_val = all_metrics_before[name]
            after_val = all_metrics_after[name]
            if before_val is not None:
                assert after_val == pytest.approx(before_val, abs=1e-6), (
                    f"Metric '{name}' mismatch: {before_val} vs {after_val}"
                )

    @pytest.mark.asyncio
    async def test_session_restart_preserves_history(self, tmp_path: Path):
        """Start -> send -> stop -> start again -> history restored."""
        cfg = _make_config(tmp_path)
        from luna.chat.session import ChatSession

        # Session 1
        session1 = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session1.start()
        await session1.send("Remember this")
        history_len = len(session1.history)
        await session1.stop()

        # Session 2
        session2 = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session2.start()

        assert len(session2.history) == history_len, (
            f"History length mismatch: {history_len} vs {len(session2.history)}"
        )
        assert session2.history[0].content == "Remember this"

    @pytest.mark.asyncio
    async def test_session_restart_preserves_consciousness_step(self, tmp_path: Path):
        """Start -> send -> stop -> start again -> step_count preserved."""
        cfg = _make_config(tmp_path)
        from luna.chat.session import ChatSession

        session1 = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session1.start()
        await session1.send("Tick tock")
        step_count = session1.engine.consciousness.step_count
        assert step_count > 0, "step_count should be > 0 after a chat turn"
        await session1.stop()

        session2 = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session2.start()

        assert session2.engine.consciousness.step_count == step_count, (
            f"step_count mismatch: {step_count} vs {session2.engine.consciousness.step_count}"
        )

    @pytest.mark.asyncio
    async def test_dream_profiles_applied_on_restart(self, tmp_path: Path):
        """Save dream-consolidated profiles -> next init applies them to Psi0."""
        cfg = _make_config(tmp_path)
        from luna.chat.session import ChatSession

        # Session 1: normal start, save checkpoint
        session1 = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session1.start()
        psi0_original = session1.engine.consciousness.psi0.copy()
        await session1.stop()

        # Simulate dream consolidation: save slightly drifted profiles
        data_dir = cfg.resolve(cfg.luna.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        drifted_profiles = {
            "LUNA":         (0.24, 0.36, 0.25, 0.15),
            "SAYOHMY":      (0.15, 0.15, 0.20, 0.50),
            "SENTINEL":     (0.50, 0.20, 0.20, 0.10),
            "TESTENGINEER": (0.15, 0.20, 0.50, 0.15),
        }
        save_profiles(data_dir / "agent_profiles.json", drifted_profiles)

        # Session 2: should pick up the drifted profiles
        session2 = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session2.start()

        psi0_after = session2.engine.consciousness.psi0
        # Psi0 should have been updated (project_simplex may adjust values slightly)
        assert not np.allclose(psi0_after, psi0_original, atol=1e-6), (
            "Psi0 should have changed after dream consolidation profiles applied"
        )
        # Dominant component should still be Reflexion (index 1) for LUNA
        assert np.argmax(psi0_after) == 1, (
            f"LUNA dominant should remain Reflexion (index 1), got {np.argmax(psi0_after)}"
        )

    @pytest.mark.asyncio
    async def test_all_three_gaps_survive_restart(self, tmp_path: Path):
        """The definitive test: all 3 persistence mechanisms survive a restart."""
        cfg = _make_config(tmp_path)
        from luna.chat.session import ChatSession

        # --- Session 1: create state across all 3 gaps ---
        session1 = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session1.start()

        # Gap 3: create chat history
        await session1.send("First message for persistence test")
        await session1.send("Second message for persistence test")

        # Gap 1: capture phi scorer state
        phi_score_1 = session1.engine.phi_scorer.score()
        assert phi_score_1 > 0, "PhiScorer should have a nonzero score after chat"

        # Capture consciousness state
        step_count_1 = session1.engine.consciousness.step_count
        history_len_1 = len(session1.history)

        await session1.stop()

        # Gap 2: write dream profiles
        data_dir = cfg.resolve(cfg.luna.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        dream_profiles = dict(AGENT_PROFILES)
        save_profiles(data_dir / "agent_profiles.json", dream_profiles)

        # Verify all files exist
        ckpt_path = cfg.resolve(cfg.consciousness.checkpoint_file)
        hist_path = cfg.resolve(cfg.memory.fractal_root) / "chat_history.json"
        prof_path = data_dir / "agent_profiles.json"
        assert ckpt_path.exists(), "Gap 1: checkpoint file must exist"
        assert hist_path.exists(), "Gap 3: history file must exist"
        assert prof_path.exists(), "Gap 2: profiles file must exist"

        # --- Session 2: verify all 3 gaps ---
        session2 = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session2.start()

        # Gap 1: PhiScorer restored
        assert session2.engine.phi_metrics_restored is True, (
            "Gap 1 FAILED: phi_metrics not restored"
        )
        phi_score_2 = session2.engine.phi_scorer.score()
        assert phi_score_2 == pytest.approx(phi_score_1, abs=1e-6), (
            f"Gap 1 FAILED: score mismatch {phi_score_1} vs {phi_score_2}"
        )

        # Gap 2: profiles loaded (even if same as defaults -- the file was read)
        loaded_profiles = load_profiles(prof_path)
        for agent in AGENT_PROFILES:
            assert agent in loaded_profiles, (
                f"Gap 2 FAILED: agent '{agent}' missing from loaded profiles"
            )

        # Gap 3: chat history restored
        assert len(session2.history) == history_len_1, (
            f"Gap 3 FAILED: history length {history_len_1} vs {len(session2.history)}"
        )
        assert session2.history[0].content == "First message for persistence test"

        # Consciousness: step count preserved
        assert session2.engine.consciousness.step_count == step_count_1, (
            f"Consciousness step_count not preserved: {step_count_1} vs "
            f"{session2.engine.consciousness.step_count}"
        )
