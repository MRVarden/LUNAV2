"""Phase D — Integration tests: Initiative + Self-Reflection through ChatSession.send().

Verifies the full chain:
  user message -> _input_evolve -> _build_session_context -> ConsciousnessDecider.decide()
  -> ConsciousDecision with initiative/self_reflection -> build_voice_prompt() -> LLM prompt

15 tests across 4 categories:
  I.   Initiative integration (5 rules through send)
  II.  Self-reflection integration (5 rules through send)
  III. Stop-word filtering (_extract_keywords)
  IV.  SessionContext correctness (phi_history, dream_insight clearing)

No network calls — all LLM interactions are mocked.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from luna.chat.session import ChatSession, _extract_keywords
from luna.consciousness.decider import SessionContext
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
from luna.llm_bridge.prompt_builder import build_voice_prompt
from luna.metrics.tracker import MetricSource


# ===================================================================
#  HELPERS
# ===================================================================


def _cfg(tmp_path: Path) -> LunaConfig:
    """Build a minimal LunaConfig for testing."""
    return LunaConfig(
        luna=LunaSection(
            version="test",
            agent_name="LUNA",
            data_dir=str(tmp_path),
        ),
        consciousness=ConsciousnessSection(
            checkpoint_file="cs.json",
            backup_on_save=False,
        ),
        memory=MemorySection(fractal_root=str(tmp_path / "fractal")),
        observability=ObservabilitySection(),
        heartbeat=HeartbeatSection(interval_seconds=0.01),
        orchestrator=OrchestratorSection(retry_max=1, retry_base_delay=0.01),
        chat=ChatSection(
            max_history=100,
            memory_search_limit=5,
            idle_heartbeat=True,
            save_conversations=True,
            prompt_prefix="luna> ",
        ),
        root_dir=tmp_path,
    )


def _mock_llm() -> AsyncMock:
    """Create a mock LLMBridge returning a fixed response."""
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=LLMResponse(
        content="Bonjour, je suis Luna.",
        model="mock-model",
        input_tokens=42,
        output_tokens=10,
    ))
    return llm


def _warm_up(session: ChatSession, n: int = 55) -> None:
    """Pre-evolve consciousness so the phase leaves BROKEN (avoids ALERT path).

    55 iterations with uniform deltas reaches FRAGILE (phi ~ 0.33).
    """
    cs = session.engine.consciousness
    if cs is None:
        return
    rng = np.random.default_rng(42)
    for _ in range(n):
        deltas = rng.uniform(0.05, 0.15, size=4).tolist()
        cs.evolve(info_deltas=deltas)


def _warm_up_to_functional(session: ChatSession) -> float:
    """Pre-evolve consciousness to reach phi >= 0.5 (FUNCTIONAL phase).

    First does the standard warm-up (55 iters), then continues
    with larger deltas until phi crosses 0.5.

    Returns the phi value achieved.
    """
    cs = session.engine.consciousness
    if cs is None:
        return 0.0
    _warm_up(session)
    phi = cs.compute_phi_iit()
    if phi >= 0.5:
        return phi

    # Push harder with a different seed and larger deltas.
    rng = np.random.default_rng(99)
    for _ in range(200):
        deltas = rng.uniform(0.10, 0.25, size=4).tolist()
        cs.evolve(info_deltas=deltas)
        phi = cs.compute_phi_iit()
        if phi >= 0.5:
            return phi
    return phi


def _seed_all_bootstrap(session: ChatSession) -> None:
    """Seed MetricTracker with BOOTSTRAP entries for all 7 canonical metrics.

    This makes bootstrap_ratio() return 1.0 (all bootstrap).
    Without this, bootstrap_ratio() returns 0.0 (empty _latest).
    """
    from luna_common.constants import METRIC_NAMES
    for name in METRIC_NAMES:
        session._metric_tracker.record(name, 0.5, source=MetricSource.BOOTSTRAP)


def _seed_all_measured(session: ChatSession) -> None:
    """Seed MetricTracker with MEASURED entries for all 7 canonical metrics.

    This makes bootstrap_ratio() return 0.0 (all measured).
    """
    from luna_common.constants import METRIC_NAMES
    for name in METRIC_NAMES:
        session._metric_tracker.record(name, 0.5, source=MetricSource.MEASURED)


# ===================================================================
#  I. INITIATIVE INTEGRATION -- 5 rules through send()
# ===================================================================


class TestInitiativeIntegration:
    """Each test triggers one initiative rule by manipulating session
    internals, then calls send() and verifies the initiative appears
    in the voice prompt passed to the LLM."""

    @pytest.mark.asyncio
    async def test_initiative_phi_declining(self, tmp_path: Path) -> None:
        """Rule 1: Phi declining monotonically over _PHI_DECLINE_WINDOW turns.

        Setup: inject 6 monotonically decreasing phi values (delta > 0.05)
        into _phi_iit_history.
        Expect: initiative contains "instabilite".
        """
        session = ChatSession(_cfg(tmp_path))
        await session.start()
        _warm_up(session)
        session._llm = _mock_llm()

        # Inject 6 monotonically decreasing phi values (window = 5).
        # Needs recent[0] - recent[-1] > 0.05 (significant change).
        session._phi_iit_history = [0.70, 0.65, 0.60, 0.55, 0.50, 0.44]

        with patch(
            "luna.chat.session.build_voice_prompt",
            wraps=build_voice_prompt,
        ) as mock_bvp:
            await session.send("Comment vas-tu ?")

        mock_bvp.assert_called_once()
        decision = mock_bvp.call_args[0][0]
        assert decision.initiative is not None
        assert "instabilite" in decision.initiative.lower()

    @pytest.mark.asyncio
    async def test_initiative_no_dream_for_long(self, tmp_path: Path) -> None:
        """Rule 2: No dream for >= _DREAM_GAP (50) turns.

        Setup: set _turn_count >= 50 and _last_dream_turn = -1 (never dreamed).
        Expect: initiative contains "/dream".
        """
        session = ChatSession(_cfg(tmp_path))
        await session.start()
        _warm_up(session)
        session._llm = _mock_llm()

        # Simulate 50+ turns without any dream.
        session._turn_count = 55
        session._last_dream_turn = -1

        # Suppress earlier initiative rules.
        # Clear phi_history so rule 1 doesn't fire.
        session._phi_iit_history = []
        # bootstrap_ratio() is already 0.0 (empty tracker) < 0.7, so rule 2 won't fire.

        with patch(
            "luna.chat.session.build_voice_prompt",
            wraps=build_voice_prompt,
        ) as mock_bvp:
            await session.send("Quoi de neuf ?")

        mock_bvp.assert_called_once()
        decision = mock_bvp.call_args[0][0]
        assert decision.initiative is not None
        assert "/dream" in decision.initiative.lower()

    @pytest.mark.asyncio
    async def test_initiative_topic_repeating(self, tmp_path: Path) -> None:
        """Rule 3: Same topic repeated >= _TOPIC_REPEAT_THRESHOLD (3) times.

        Setup: inject 3 identical keywords into _recent_topics.
        Expect: initiative contains "meme sujet".
        """
        session = ChatSession(_cfg(tmp_path))
        await session.start()
        _warm_up(session)
        session._llm = _mock_llm()

        # Inject repeated topic.
        session._recent_topics = ["securite", "securite", "securite"]

        # Suppress earlier rules.
        session._phi_iit_history = []
        # bootstrap_ratio() is already 0.0 < 0.7 (empty tracker), rule 2 won't fire.
        session._turn_count = 5
        session._last_dream_turn = 3

        with patch(
            "luna.chat.session.build_voice_prompt",
            wraps=build_voice_prompt,
        ) as mock_bvp:
            # Message where the ONLY extractable keyword is "securite".
            # "et" and "la" are stopwords, so _extract_keywords returns ["securite"].
            # This appends one "securite" to _recent_topics, keeping last 3 identical.
            await session.send("Et la securite ?")

        mock_bvp.assert_called_once()
        decision = mock_bvp.call_args[0][0]
        assert decision.initiative is not None
        assert "meme sujet" in decision.initiative.lower()


# ===================================================================
#  II. SELF-REFLECTION INTEGRATION -- 5 rules through send()
# ===================================================================


class TestSelfReflectionIntegration:
    """Each test triggers one self-reflection rule and verifies it flows
    through to build_voice_prompt."""

    @pytest.mark.asyncio
    async def test_reflection_phi_rose(self, tmp_path: Path) -> None:
        """Rule 1: Phi just rose significantly (delta > 0.05).

        Setup: inject phi_history where last value is much lower than current phi.
        Expect: self_reflection contains "metriques montent".
        """
        session = ChatSession(_cfg(tmp_path))
        await session.start()
        _warm_up(session)
        session._llm = _mock_llm()

        # Current phi after warm-up.
        cs = session.engine.consciousness
        current_phi = cs.compute_phi_iit()

        # Set previous phi to be significantly lower.
        session._phi_iit_history = [current_phi - 0.15, current_phi - 0.10]

        with patch(
            "luna.chat.session.build_voice_prompt",
            wraps=build_voice_prompt,
        ) as mock_bvp:
            await session.send("Bonjour")

        mock_bvp.assert_called_once()
        decision = mock_bvp.call_args[0][0]
        assert decision.self_reflection is not None
        assert "metriques montent" in decision.self_reflection.lower()

    @pytest.mark.asyncio
    async def test_reflection_phi_dropped(self, tmp_path: Path) -> None:
        """Rule 2: Phi just dropped significantly (delta < -0.05).

        Setup: inject phi_history where last value is much higher than current phi.
        Expect: self_reflection contains "destabilise".
        """
        session = ChatSession(_cfg(tmp_path))
        await session.start()
        _warm_up(session)
        session._llm = _mock_llm()

        cs = session.engine.consciousness
        current_phi = cs.compute_phi_iit()

        # Set previous phi much higher — must survive Reactor evolution shifting phi.
        # After v3.5.1, _input_evolve runs the Thinker+Reactor which evolves Ψ,
        # potentially changing compute_phi_iit(). Phase 3: Gaussian MI can produce
        # values >> 1.0, so the gap must be large enough (2.0) to ensure the Decider
        # still sees a significant drop after evolution.
        session._phi_iit_history = [current_phi + 2.0, current_phi + 2.0]

        with patch(
            "luna.chat.session.build_voice_prompt",
            wraps=build_voice_prompt,
        ) as mock_bvp:
            await session.send("Bonjour")

        mock_bvp.assert_called_once()
        decision = mock_bvp.call_args[0][0]
        assert decision.self_reflection is not None
        assert "destabilise" in decision.self_reflection.lower()

    @pytest.mark.asyncio
    async def test_reflection_phase_changed_up(self, tmp_path: Path) -> None:
        """Rule 3: Phase changed upward (prev phi < 0.5 <= current phi).

        Setup: warm up enough for valid phi computation, then patch
        compute_phi_iit to return a precise value (0.505) so we can
        set prev_phi=0.499 with delta=0.006 (rules 1-2 don't fire)
        while prev < 0.5 <= current (rule 3 fires).
        Expect: self_reflection contains "plus solide".
        """
        session = ChatSession(_cfg(tmp_path))
        await session.start()
        _warm_up(session)
        session._llm = _mock_llm()

        cs = session.engine.consciousness

        # Set prev_phi just below 0.5 threshold.
        prev_phi = 0.499
        session._phi_iit_history = [prev_phi - 0.02, prev_phi]

        # Patch compute_phi_iit to return a controlled value just above 0.5.
        # This ensures:
        # - delta = 0.505 - 0.499 = 0.006 < 0.05 -> rules 1-2 don't fire
        # - prev (0.499) < 0.5 <= current (0.505) -> rule 3 fires
        # Without the patch, _warm_up_to_functional can overshoot (phi ~0.62),
        # making delta > 0.05 and triggering rule 1 before rule 3.
        with patch.object(
            cs, "compute_phi_iit", return_value=0.505,
        ), patch(
            "luna.chat.session.build_voice_prompt",
            wraps=build_voice_prompt,
        ) as mock_bvp:
            await session.send("Bonjour")

        mock_bvp.assert_called_once()
        decision = mock_bvp.call_args[0][0]
        assert decision.self_reflection is not None
        assert "plus solide" in decision.self_reflection.lower()

    @pytest.mark.asyncio
    async def test_reflection_convergence(self, tmp_path: Path) -> None:
        """Rule 4: Psi history converged (variance < 0.0005 over 10 steps).

        Setup: keep >= 50 history entries (required for compute_phi_iit),
        then replace the last 10 with near-identical vectors.
        Expect: self_reflection contains "converge".
        """
        session = ChatSession(_cfg(tmp_path))
        await session.start()
        _warm_up(session)
        session._llm = _mock_llm()

        cs = session.engine.consciousness

        # Clear phi_history so rules 1-3 don't fire.
        session._phi_iit_history = []

        # CRITICAL: Do NOT clear cs.history -- compute_phi_iit() needs >= 50
        # entries. If history drops below 50, phi = 0.0, phase drops to
        # BROKEN via hysteresis, and ALERT intent fires (skips build_voice_prompt).
        #
        # Instead, keep the first ~45 entries from warm-up and replace
        # the last 10 with near-identical vectors (variance < 0.0005).
        assert len(cs.history) >= 50, (
            f"Expected >= 50 history entries after warm-up, got {len(cs.history)}"
        )

        # Keep first entries, replace last 10 with convergent vectors.
        stable_psi = cs.psi.copy()
        base_entries = cs.history[:-10]  # Keep bulk of history
        convergent_tail = []
        for i in range(10):
            # Tiny noise: variance << 0.0005
            noise = np.array([
                0.00001 * (i % 3),
                -0.00001 * (i % 2),
                0.000005 * (i % 4),
                -0.000005 * (i % 3),
            ])
            convergent_tail.append(stable_psi + noise)

        cs.history = list(base_entries) + convergent_tail

        with patch(
            "luna.chat.session.build_voice_prompt",
            wraps=build_voice_prompt,
        ) as mock_bvp:
            await session.send("Bonjour")

        mock_bvp.assert_called_once()
        decision = mock_bvp.call_args[0][0]
        assert decision.self_reflection is not None
        assert "converge" in decision.self_reflection.lower()

    @pytest.mark.asyncio
    async def test_reflection_dream_insight(self, tmp_path: Path) -> None:
        """Rule 5: Recent dream insight available.

        Setup: set _last_dream_insight to a string.
        Expect: self_reflection contains "dernier reve".
        """
        session = ChatSession(_cfg(tmp_path))
        await session.start()
        _warm_up(session)
        session._llm = _mock_llm()

        # Clear phi_history so rules 1-3 don't fire.
        session._phi_iit_history = []

        # Ensure rule 4 (convergence) doesn't fire by replacing the last 10
        # history entries with VARIED vectors (variance >> 0.0005).
        # Do NOT clear cs.history -- need >= 50 entries for compute_phi_iit().
        cs = session.engine.consciousness
        assert len(cs.history) >= 50, (
            f"Expected >= 50 history entries after warm-up, got {len(cs.history)}"
        )

        # Replace last 10 with intentionally varied vectors on the simplex.
        rng = np.random.default_rng(77)
        base_entries = cs.history[:-10]
        varied_tail = []
        for _ in range(10):
            v = rng.uniform(0.1, 0.9, size=4)
            v = v / v.sum()  # Project onto simplex
            varied_tail.append(v)
        cs.history = list(base_entries) + varied_tail

        # Verify the tail has enough variance to suppress rule 4.
        recent = np.array(cs.history[-10:])
        variance = float(np.sum(np.var(recent, axis=0)))
        assert variance >= 0.0005, (
            f"History variance too low ({variance}), rule 4 would fire before rule 5"
        )

        # Set dream insight.
        session._last_dream_insight = "pattern de stabilisation observe"

        with patch(
            "luna.chat.session.build_voice_prompt",
            wraps=build_voice_prompt,
        ) as mock_bvp:
            await session.send("Bonjour")

        mock_bvp.assert_called_once()
        decision = mock_bvp.call_args[0][0]
        assert decision.self_reflection is not None
        assert "dernier reve" in decision.self_reflection.lower()
        assert "pattern de stabilisation observe" in decision.self_reflection


# ===================================================================
#  III. STOP-WORD FILTERING
# ===================================================================


class TestStopWordFiltering:
    """Verify _extract_keywords correctly filters Luna ecosystem terms
    while keeping meaningful words."""

    def test_filters_luna_ecosystem_terms(self) -> None:
        """Luna ecosystem terms (luna, pipeline, conscience, etc.) are filtered."""
        text = "Luna pipeline conscience psi phi phase sentinel sayohmy"
        keywords = _extract_keywords(text)
        assert len(keywords) == 0, (
            f"Expected all ecosystem terms filtered, got: {keywords}"
        )

    def test_keeps_meaningful_words(self) -> None:
        """Meaningful domain words survive the stopword filter."""
        text = "securite performance architecture deploiement"
        keywords = _extract_keywords(text)
        assert "securite" in keywords
        assert "performance" in keywords
        assert "architecture" in keywords
        assert "deploiement" in keywords

    @pytest.mark.asyncio
    async def test_topic_tracking_across_turns(self, tmp_path: Path) -> None:
        """Keywords extracted per turn accumulate in _recent_topics.

        send() extracts keywords from user message and appends to
        _recent_topics (first 3 per turn, capped at 30).
        """
        session = ChatSession(_cfg(tmp_path))
        await session.start()
        _warm_up(session)
        session._llm = _mock_llm()

        # Verify initial state.
        assert session._recent_topics == []

        # Send a message with extractable keywords.
        await session.send("Analyse la securite du serveur")

        # _extract_keywords("analyse la securite du serveur") should yield
        # "analyse", "securite", "serveur" (la, du are stopwords).
        # First 3 are appended to _recent_topics.
        assert len(session._recent_topics) >= 1
        # "securite" should be among the extracted keywords.
        assert "securite" in session._recent_topics or "analyse" in session._recent_topics

        topics_after_first = list(session._recent_topics)

        # Send another message -- topics accumulate.
        await session.send("Verifie la couverture des tests")

        assert len(session._recent_topics) > len(topics_after_first)


# ===================================================================
#  IV. SESSIONCONTEXT CORRECTNESS
# ===================================================================


class TestSessionContextCorrectness:
    """Verify that _build_session_context correctly maps session internals
    into SessionContext fields consumed by the Decider."""

    @pytest.mark.asyncio
    async def test_phi_history_values(self, tmp_path: Path) -> None:
        """phi_history in SessionContext mirrors _phi_iit_history (last 10).

        After send(), _chat_evolve appends phi to _phi_iit_history.
        The next call to _build_session_context should include it.
        """
        session = ChatSession(_cfg(tmp_path))
        await session.start()
        _warm_up(session)
        session._llm = _mock_llm()

        # Inject known phi values.
        session._phi_iit_history = [0.30, 0.35, 0.40]

        # Capture the SessionContext built during send().
        captured_contexts: list[SessionContext] = []
        original_decide = session._decider.decide

        def spy_decide(message, state, context, **kwargs):
            captured_contexts.append(context)
            return original_decide(message, state, context, **kwargs)

        session._decider.decide = spy_decide

        await session.send("Test phi history")

        assert len(captured_contexts) == 1
        ctx = captured_contexts[0]

        # phi_history should contain our injected values (last 10).
        assert ctx.phi_history[:3] == [0.30, 0.35, 0.40]

    @pytest.mark.asyncio
    async def test_dream_insight_clears_after_consumed(self, tmp_path: Path) -> None:
        """_last_dream_insight is cleared to None after being consumed by decide().

        This ensures the dream insight is a one-shot signal: it appears in
        the ConsciousDecision once, then is cleared so it doesn't repeat.
        """
        session = ChatSession(_cfg(tmp_path))
        await session.start()
        _warm_up(session)
        session._llm = _mock_llm()

        # Set dream insight.
        session._last_dream_insight = "consolidation reussie"

        # First send consumes the insight.
        await session.send("Premier message")
        assert session._last_dream_insight is None, (
            "Dream insight should be cleared after first send()"
        )

        # Second send -- no dream insight in decision.
        with patch(
            "luna.chat.session.build_voice_prompt",
            wraps=build_voice_prompt,
        ) as mock_bvp:
            await session.send("Deuxieme message")

        mock_bvp.assert_called_once()
        decision = mock_bvp.call_args[0][0]
        # self_reflection might be None or set by other rules, but NOT by dream insight.
        if decision.self_reflection is not None:
            assert "dernier reve" not in decision.self_reflection.lower(), (
                "Dream insight should not re-appear on second send()"
            )
