"""Phase 8 — Chat Interface: 18 tests for ChatSession, ChatMessage, ChatResponse.

No network calls — all LLM interactions are mocked.
Fixtures use tmp_path for memory/checkpoints.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from luna.chat.session import (
    ChatMessage,
    ChatResponse,
    ChatSession,
    _extract_keywords,
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
    PipelineSection,
)
from luna.llm_bridge.bridge import LLMBridgeError, LLMResponse


# ═══════════════════════════════════════════════════════════════════════════
#  FIXTURES
# ═══════════════════════════════════════════════════════════════════════════


def _make_config(tmp_path: Path, **chat_overrides) -> LunaConfig:
    """Build a minimal LunaConfig with configurable chat section."""
    chat_kw = {
        "max_history": 100,
        "memory_search_limit": 5,
        "idle_heartbeat": True,
        "save_conversations": True,
        "prompt_prefix": "luna> ",
    }
    chat_kw.update(chat_overrides)

    return LunaConfig(
        luna=LunaSection(
            version="test",
            agent_name="LUNA",
            data_dir=str(tmp_path),
            pipeline_dir=str(tmp_path / "pipeline"),
        ),
        consciousness=ConsciousnessSection(
            checkpoint_file="cs.json",
            backup_on_save=False,
        ),
        memory=MemorySection(fractal_root=str(tmp_path / "fractal")),
        pipeline=PipelineSection(root=str(tmp_path / "pipeline")),
        observability=ObservabilitySection(),
        heartbeat=HeartbeatSection(interval_seconds=0.01),
        orchestrator=OrchestratorSection(retry_max=1, retry_base_delay=0.01),
        chat=ChatSection(**chat_kw),
        root_dir=tmp_path,
    )


def _mock_llm() -> AsyncMock:
    """Create a mock LLMBridge that returns a fixed response."""
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=LLMResponse(
        content="Bonjour, je suis Luna.",
        model="mock-model",
        input_tokens=42,
        output_tokens=10,
    ))
    return llm


@pytest.fixture
def cfg(tmp_path: Path) -> LunaConfig:
    return _make_config(tmp_path)


@pytest.fixture
def session(cfg: LunaConfig) -> ChatSession:
    return ChatSession(cfg)


# ═══════════════════════════════════════════════════════════════════════════
#  I. DATACLASSES
# ═══════════════════════════════════════════════════════════════════════════


class TestChatMessage:
    """Test 1: ChatMessage fields."""

    def test_chat_message_fields(self):
        now = datetime.now(timezone.utc)
        msg = ChatMessage(role="user", content="hello", timestamp=now)
        assert msg.role == "user"
        assert msg.content == "hello"
        assert msg.timestamp == now

    def test_chat_message_frozen(self):
        msg = ChatMessage(role="user", content="hello")
        with pytest.raises(FrozenInstanceError):
            msg.role = "assistant"  # type: ignore[misc]


class TestChatResponse:
    """Test 2: ChatResponse defaults."""

    def test_chat_response_defaults(self):
        resp = ChatResponse(content="ok")
        assert resp.content == "ok"
        assert resp.input_tokens == 0
        assert resp.output_tokens == 0
        assert resp.phase == ""
        assert resp.phi_iit == 0.0

    def test_chat_response_full(self):
        resp = ChatResponse(
            content="hello",
            input_tokens=10,
            output_tokens=5,
            phase="FUNCTIONAL",
            phi_iit=0.7823,
        )
        assert resp.input_tokens == 10
        assert resp.phase == "FUNCTIONAL"


# ═══════════════════════════════════════════════════════════════════════════
#  II. CONFIG
# ═══════════════════════════════════════════════════════════════════════════


class TestChatSectionConfig:
    """Tests 3-4: ChatSection defaults and TOML loading."""

    def test_chat_section_defaults(self):
        """Test 3: Default values."""
        cs = ChatSection()
        assert cs.max_history == 100
        assert cs.memory_search_limit == 5
        assert cs.idle_heartbeat is True
        assert cs.save_conversations is True
        assert cs.prompt_prefix == "luna> "

    def test_chat_section_from_toml(self, tmp_path: Path):
        """Test 4: Load from a real TOML file."""
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

[chat]
max_history = 50
memory_search_limit = 3
idle_heartbeat = false
save_conversations = false
prompt_prefix = "test> "
"""
        toml_path = tmp_path / "luna.toml"
        toml_path.write_text(toml_content)
        config = LunaConfig.load(toml_path)
        assert config.chat.max_history == 50
        assert config.chat.memory_search_limit == 3
        assert config.chat.idle_heartbeat is False
        assert config.chat.save_conversations is False
        assert config.chat.prompt_prefix == "test> "


# ═══════════════════════════════════════════════════════════════════════════
#  III. LIFECYCLE
# ═══════════════════════════════════════════════════════════════════════════


class TestSessionLifecycle:
    """Tests 5-7: start/stop behavior."""

    @pytest.mark.asyncio
    async def test_session_start_initializes(self, cfg: LunaConfig):
        """Test 5: Start initializes engine and sets _started."""
        session = ChatSession(cfg)
        # Patch create_provider to return a mock LLM.
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()
        assert session.engine.consciousness is not None
        assert session.has_llm is True
        assert session.has_memory is True

    @pytest.mark.asyncio
    async def test_session_start_no_llm(self, cfg: LunaConfig):
        """Test 6: Start with failing LLM degrades gracefully."""
        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", side_effect=RuntimeError("no SDK")):
            await session.start()
        assert session.has_llm is False
        assert session.engine.consciousness is not None

    @pytest.mark.asyncio
    async def test_session_stop_saves_checkpoint(self, cfg: LunaConfig):
        """Test 7: Stop saves a consciousness checkpoint."""
        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()

        ckpt_path = cfg.resolve(cfg.consciousness.checkpoint_file)
        # Remove any existing checkpoint.
        if ckpt_path.exists():
            ckpt_path.unlink()

        await session.stop()
        assert ckpt_path.exists()


# ═══════════════════════════════════════════════════════════════════════════
#  IV. SEND
# ═══════════════════════════════════════════════════════════════════════════


class TestSend:
    """Tests 8-12: send() behavior."""

    @pytest.mark.asyncio
    async def test_send_with_mock_llm(self, cfg: LunaConfig):
        """Test 8: Send returns LLM content and tokens."""
        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()
        resp = await session.send("Bonjour Luna")
        assert resp.content == "Bonjour, je suis Luna."
        assert resp.input_tokens == 42
        assert resp.output_tokens == 10
        assert resp.phase != ""
        assert resp.phi_iit >= 0.0  # Fresh engine starts at 0.0

    @pytest.mark.asyncio
    async def test_send_without_llm_status_only(self, cfg: LunaConfig):
        """Test 9: Send without LLM returns a status-only response."""
        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", side_effect=RuntimeError("no SDK")):
            await session.start()
        resp = await session.send("Hello")
        assert "[Mode sans LLM]" in resp.content
        assert "Phase:" in resp.content
        assert resp.input_tokens == 0

    @pytest.mark.asyncio
    async def test_send_evolves_consciousness(self, cfg: LunaConfig):
        """Test 10: Send runs idle_step (breath) then chat_evolve (real deltas)."""
        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()

        step_before = session.engine.consciousness.step_count
        idle_before = session.engine._idle_steps
        await session.send("test evolution")
        # idle_step increments _idle_steps (the heartbeat breath).
        assert session.engine._idle_steps == idle_before + 1
        # chat_evolve adds a second evolve step (+2 total).
        assert session.engine.consciousness.step_count == step_before + 2

    @pytest.mark.asyncio
    async def test_send_records_history(self, cfg: LunaConfig):
        """Test 11: Send records user + assistant messages in history."""
        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()
        await session.send("Question 1")
        assert len(session.history) == 2  # user + assistant
        assert session.history[0].role == "user"
        assert session.history[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_send_trims_history(self, tmp_path: Path):
        """Test 12: History is trimmed to max_history."""
        cfg = _make_config(tmp_path, max_history=4)
        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()

        # Send 3 messages → 6 history entries → trimmed to 4.
        for i in range(3):
            await session.send(f"Message {i}")

        assert len(session.history) <= 4


# ═══════════════════════════════════════════════════════════════════════════
#  V. COMMANDS
# ═══════════════════════════════════════════════════════════════════════════


class TestCommands:
    """Tests 13-16: slash command handling."""

    @pytest.mark.asyncio
    async def test_command_status(self, cfg: LunaConfig):
        """Test 13: /status returns engine status."""
        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()
        result = await session.handle_command("/status")
        assert "Etat Luna" in result
        assert "phase" in result

    @pytest.mark.asyncio
    async def test_command_help(self, cfg: LunaConfig):
        """Test 14: /help returns the help text."""
        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()
        result = await session.handle_command("/help")
        assert "/status" in result
        assert "/dream" in result
        assert "/quit" in result

    @pytest.mark.asyncio
    async def test_command_dream(self, cfg: LunaConfig):
        """Test 15: /dream triggers a dream cycle."""
        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()

        # Build enough history for the dream cycle.
        for _ in range(20):
            session.engine.idle_step()

        result = await session.handle_command("/dream")
        assert "Cycle de reve" in result

    @pytest.mark.asyncio
    async def test_command_unknown(self, cfg: LunaConfig):
        """Test 16: Unknown command returns a helpful message."""
        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()
        result = await session.handle_command("/foobar")
        assert "Commande inconnue" in result
        assert "/help" in result


# ═══════════════════════════════════════════════════════════════════════════
#  VI. MEMORY
# ═══════════════════════════════════════════════════════════════════════════


class TestMemoryIntegration:
    """Test 17: send() searches memory for context."""

    @pytest.mark.asyncio
    async def test_send_searches_memory(self, cfg: LunaConfig):
        """Test 17: When memory is available, send() calls search()."""
        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()

        # Replace memory with a mock.
        mock_memory = AsyncMock()
        mock_memory.search = AsyncMock(return_value=[])
        mock_memory.write_memory = AsyncMock()
        session._memory = mock_memory

        await session.send("consciousness evolution fractal")
        mock_memory.search.assert_called_once()
        # Keywords should have been extracted from the input.
        call_args = mock_memory.search.call_args
        keywords = call_args[0][0]
        assert isinstance(keywords, list)
        assert len(keywords) > 0


# ═══════════════════════════════════════════════════════════════════════════
#  VII. HELPERS
# ═══════════════════════════════════════════════════════════════════════════


class TestExtractKeywords:
    """Test 18: _extract_keywords helper."""

    def test_extract_keywords(self):
        """Test 18: Extracts meaningful keywords, skips stopwords."""
        text = "la conscience fractale de Luna evolue dans le systeme"
        kw = _extract_keywords(text)
        assert "conscience" in kw
        assert "fractale" in kw
        assert "luna" in kw
        assert "evolue" in kw
        # Stopwords removed.
        assert "la" not in kw
        assert "de" not in kw
        assert "dans" not in kw
        assert "le" not in kw

    def test_extract_keywords_limit(self):
        """Keywords are capped at the limit."""
        text = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
        kw = _extract_keywords(text, limit=3)
        assert len(kw) == 3

    def test_extract_keywords_dedup(self):
        """Duplicate tokens are not repeated."""
        text = "Luna Luna Luna consciousness consciousness"
        kw = _extract_keywords(text)
        assert kw.count("luna") == 1
        assert kw.count("consciousness") == 1


# =====================================================================
#  VIII. PIPELINE INTEGRATION (v2.4.0)
# =====================================================================


class TestPipelineIntegration:
    """Tests 19-21: Chat + Pipeline self-evolution loop integration."""

    @pytest.mark.asyncio
    async def test_pipeline_disabled_by_default(self, cfg: LunaConfig) -> None:
        """Test 19: runner_enabled=false -> _pipeline_runner is None."""
        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()
        assert session._pipeline_runner is None, (
            "Pipeline runner should be None when runner_enabled=false"
        )

    @pytest.mark.asyncio
    async def test_send_without_runner_unchanged(self, cfg: LunaConfig) -> None:
        """Test 20: send() works normally when pipeline runner is disabled.

        Even when the message contains a detectable task intent,
        the pipeline does NOT run because _pipeline_runner is None.
        """
        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()

        # This message has a strong signal ('ameliore') + weak ('performance')
        # but pipeline_runner is None, so it goes through normal LLM path.
        resp = await session.send("ameliore la performance du code")
        assert resp.content == "Bonjour, je suis Luna."
        assert resp.input_tokens == 42

    @pytest.mark.asyncio
    async def test_needs_command_returns_needs(self, cfg: LunaConfig) -> None:
        """Test 21: /needs command formats bootstrap needs via NeedIdentifier.

        After start(), all 7 metrics are BOOTSTRAP, so /needs should
        return a list of 7 MEASURE needs.
        """
        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()

        result = await session.handle_command("/needs")
        assert "Besoins identifies" in result, (
            "Expected /needs to return identified needs header"
        )
        assert "MEASURE" in result.upper(), (
            "Expected MEASURE tasks for bootstrap metrics"
        )
        assert "bootstrap" in result.lower(), (
            "Expected bootstrap warning in /needs output"
        )


# =====================================================================
#  IX. INACTIVITY DREAM WATCHER (v2.4.1 — Phase 3)
# =====================================================================


class TestInactivityWatcher:
    """Tests for the background inactivity dream trigger."""

    @pytest.mark.asyncio
    async def test_inactivity_task_created_on_start(self, cfg: LunaConfig):
        """start() creates the _inactivity_task when dream is enabled."""
        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()
        assert session._inactivity_task is not None, (
            "Inactivity watcher task should be created on start()"
        )
        assert not session._inactivity_task.done()
        await session.stop()

    @pytest.mark.asyncio
    async def test_inactivity_task_cancelled_on_stop(self, cfg: LunaConfig):
        """stop() cancels the _inactivity_task cleanly."""
        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()
        task = session._inactivity_task
        assert task is not None
        await session.stop()
        assert session._inactivity_task is None
        assert task.done()

    @pytest.mark.asyncio
    async def test_send_resets_last_activity(self, cfg: LunaConfig):
        """send() updates _last_activity to the current time."""
        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()
        old_activity = session._last_activity
        # Small sleep to ensure time.monotonic() changes.
        await asyncio.sleep(0.01)
        await session.send("hello")
        assert session._last_activity > old_activity, (
            "send() should reset _last_activity to a more recent time"
        )
        await session.stop()

    @pytest.mark.asyncio
    async def test_dream_disabled_no_task(self, tmp_path: Path):
        """When dream.enabled=false, no inactivity task is created."""
        from luna.core.config import DreamSection

        cfg = _make_config(tmp_path)
        # Override dream section to disabled.
        object.__setattr__(cfg, "dream", DreamSection(enabled=False))
        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()
        assert session._inactivity_task is None, (
            "No inactivity task when dream is disabled"
        )
        await session.stop()


# =====================================================================
#  X. /DREAM GUARD (v2.4.1 — Phase 3)
# =====================================================================


class TestDreamCommandGuard:
    """Tests for the /dream empty-buffer guard."""

    @pytest.mark.asyncio
    async def test_dream_refused_no_data(self, cfg: LunaConfig):
        """Test: /dream before any send() with no history -> refused."""
        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()
        # No send() -> empty buffers AND empty history (<10).
        result = await session.handle_command("/dream")
        assert "Pas assez de donnees" in result, (
            "Expected refusal message when no data for dream"
        )
        await session.stop()

    @pytest.mark.asyncio
    async def test_dream_allowed_with_history(self, cfg: LunaConfig):
        """Test: /dream after enough idle_steps (history >= 10) -> legacy runs."""
        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()
        # Build consciousness history via idle steps (no send needed).
        for _ in range(20):
            session.engine.idle_step()
        result = await session.handle_command("/dream")
        assert "Cycle de reve" in result, (
            "Expected dream to run with enough consciousness history"
        )
        await session.stop()

    @pytest.mark.asyncio
    async def test_dream_allowed_with_buffers(self, cfg: LunaConfig):
        """Test: /dream after send() messages -> simulation runs."""
        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()
        # Send enough messages to fill buffers.
        for i in range(5):
            await session.send(f"Message {i}")
        assert len(session._psi_snapshots) > 0 or len(session._pipeline_events) > 0
        result = await session.handle_command("/dream")
        assert "Cycle de reve" in result, (
            "Expected dream to run after chat messages"
        )
        await session.stop()


# =====================================================================
#  XI. VIVID INFO_DELTAS (v2.4.1 — Phase 4C)
# =====================================================================


class TestVividInfoDeltas:
    """Test that info_deltas vary with message length and token count."""

    @pytest.mark.asyncio
    async def test_different_messages_produce_different_psi(self, cfg: LunaConfig):
        """Varying message lengths produce different Psi trajectories."""
        session = ChatSession(cfg)
        with patch("luna.chat.session.create_provider", return_value=_mock_llm()):
            await session.start()

        # Short message.
        await session.send("hi")
        psi_short = session.engine.consciousness.psi.copy()

        # Long message.
        await session.send("a" * 400)
        psi_long = session.engine.consciousness.psi.copy()

        # The two Psi vectors should differ (different info_deltas).
        import numpy as np
        assert not np.array_equal(psi_short, psi_long), (
            "Short and long messages should produce different Psi evolution"
        )
        await session.stop()
