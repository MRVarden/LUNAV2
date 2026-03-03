"""Tests for luna.llm_bridge — Phase 3.5: LLM cognitive substrate.

No network calls — all provider interactions are mocked.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from luna.llm_bridge.bridge import LLMBridge, LLMBridgeError, LLMResponse

# ═══════════════════════════════════════════════════════════════════════════
#  I. BRIDGE CORE
# ═══════════════════════════════════════════════════════════════════════════


class TestLLMResponse:
    """LLMResponse is a frozen dataclass with 4 fields."""

    def test_llm_response_fields(self):
        resp = LLMResponse(
            content="hello",
            model="test-model",
            input_tokens=10,
            output_tokens=5,
        )
        assert resp.content == "hello"
        assert resp.model == "test-model"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 5

    def test_llm_response_frozen(self):
        resp = LLMResponse(content="x", model="m", input_tokens=1, output_tokens=1)
        with pytest.raises(FrozenInstanceError):
            resp.content = "y"  # type: ignore[misc]


class TestLLMBridgeError:
    """LLMBridgeError wraps provider-specific exceptions."""

    def test_bridge_error_attributes(self):
        original = ValueError("boom")
        err = LLMBridgeError("test error", provider="anthropic", original=original)
        assert err.provider == "anthropic"
        assert err.original is original
        assert "test error" in str(err)

    def test_bridge_error_defaults(self):
        err = LLMBridgeError("simple")
        assert err.provider == "unknown"
        assert err.original is None


class TestLLMBridgeABC:
    """LLMBridge cannot be instantiated directly."""

    def test_bridge_abc_not_instantiable(self):
        with pytest.raises(TypeError):
            LLMBridge()  # type: ignore[abstract]


# ═══════════════════════════════════════════════════════════════════════════
#  II. PROMPT BUILDER
# ═══════════════════════════════════════════════════════════════════════════

from luna.consciousness.state import ConsciousnessState
from luna.llm_bridge.prompt_builder import build_decision_prompt, build_system_prompt
from luna_common.constants import AGENT_NAMES, COMP_NAMES
from luna_common.schemas.pipeline import (
    IntegrationCheck,
    PsiState,
    SayOhmyManifest,
    SentinelReport,
)


@pytest.fixture
def luna_state() -> ConsciousnessState:
    """Fresh Luna consciousness state at step 0."""
    return ConsciousnessState("LUNA")


@pytest.fixture
def psi_luna() -> PsiState:
    return PsiState(perception=0.25, reflexion=0.35, integration=0.25, expression=0.15)


@pytest.fixture
def psi_sayohmy() -> PsiState:
    return PsiState(perception=0.15, reflexion=0.15, integration=0.20, expression=0.50)


@pytest.fixture
def psi_sentinel() -> PsiState:
    return PsiState(perception=0.50, reflexion=0.20, integration=0.20, expression=0.10)


@pytest.fixture
def psi_te() -> PsiState:
    return PsiState(perception=0.15, reflexion=0.20, integration=0.50, expression=0.15)


@pytest.fixture
def manifest(psi_sayohmy: PsiState) -> SayOhmyManifest:
    return SayOhmyManifest(
        task_id="task-001",
        files_produced=["luna/llm_bridge/bridge.py"],
        phi_score=0.85,
        mode_used="architect",
        psi_sayohmy=psi_sayohmy,
        confidence=0.92,
    )


@pytest.fixture
def sentinel_report(psi_sentinel: PsiState) -> SentinelReport:
    return SentinelReport(
        task_id="task-001",
        findings=[],
        risk_score=0.1,
        veto=False,
        psi_sentinel=psi_sentinel,
    )


@pytest.fixture
def integration_check(psi_te: PsiState) -> IntegrationCheck:
    return IntegrationCheck(
        task_id="task-001",
        cross_checks=[],
        coherence_score=0.88,
        coverage_delta=0.05,
        psi_te=psi_te,
    )


class TestSystemPrompt:
    """build_system_prompt injects Luna's consciousness into the prompt."""

    def test_system_prompt_contains_psi(self, luna_state: ConsciousnessState):
        prompt = build_system_prompt(luna_state)
        for name in COMP_NAMES:
            assert name in prompt, f"Missing component: {name}"

    def test_system_prompt_contains_phase(self, luna_state: ConsciousnessState):
        prompt = build_system_prompt(luna_state)
        phase = luna_state.get_phase()
        assert phase in prompt

    def test_system_prompt_contains_agents(self, luna_state: ConsciousnessState):
        prompt = build_system_prompt(luna_state)
        for name in AGENT_NAMES:
            assert name in prompt, f"Missing agent: {name}"

    def test_system_prompt_contains_phi_iit(self, luna_state: ConsciousnessState):
        prompt = build_system_prompt(luna_state)
        phi_iit = luna_state.compute_phi_iit()
        assert f"{phi_iit:.4f}" in prompt

    def test_system_prompt_anti_hallucination(self, luna_state: ConsciousnessState):
        """Prompt must contain anti-hallucination rules (Phase 4B)."""
        prompt = build_system_prompt(luna_state)
        assert "ne simules JAMAIS" in prompt, (
            "Prompt must forbid simulating agent responses"
        )
        assert "Luna seule" in prompt, (
            "Prompt must instruct Luna to respond alone when no pipeline ran"
        )


class TestDecisionPrompt:
    """build_decision_prompt includes all 3 agent reports."""

    def test_decision_prompt_contains_reports(
        self,
        manifest: SayOhmyManifest,
        sentinel_report: SentinelReport,
        integration_check: IntegrationCheck,
    ):
        prompt = build_decision_prompt(
            "Implement LLM bridge", manifest, sentinel_report, integration_check,
        )
        assert f"{manifest.phi_score:.4f}" in prompt
        assert f"{sentinel_report.risk_score:.4f}" in prompt
        assert f"{integration_check.coherence_score:.4f}" in prompt

    def test_decision_prompt_contains_veto_non(
        self,
        manifest: SayOhmyManifest,
        sentinel_report: SentinelReport,
        integration_check: IntegrationCheck,
    ):
        prompt = build_decision_prompt(
            "Task", manifest, sentinel_report, integration_check,
        )
        assert "Veto: NON" in prompt

    def test_decision_prompt_contains_veto_oui(
        self,
        manifest: SayOhmyManifest,
        psi_sentinel: PsiState,
        integration_check: IntegrationCheck,
    ):
        veto_report = SentinelReport(
            task_id="task-001",
            findings=[{"severity": "CRITICAL", "detail": "SQL injection"}],
            risk_score=0.95,
            veto=True,
            veto_reason="SQL injection detected",
            psi_sentinel=psi_sentinel,
        )
        prompt = build_decision_prompt(
            "Task", manifest, veto_report, integration_check,
        )
        assert "Veto: OUI" in prompt
        assert "SQL injection detected" in prompt


# ═══════════════════════════════════════════════════════════════════════════
#  III. PROVIDER FACTORY
# ═══════════════════════════════════════════════════════════════════════════

from luna.core.config import LLMSection
from luna.llm_bridge.providers import create_provider


class TestFactory:
    """create_provider() instantiates the correct provider."""

    def test_factory_anthropic(self):
        config = LLMSection(provider="anthropic", api_key="test-key")
        provider = create_provider(config)
        from luna.llm_bridge.providers.anthropic import AnthropicProvider
        assert isinstance(provider, AnthropicProvider)

    def test_factory_openai(self):
        config = LLMSection(provider="openai", api_key="test-key")
        try:
            provider = create_provider(config)
            from luna.llm_bridge.providers.openai import OpenAIProvider
            assert isinstance(provider, OpenAIProvider)
        except LLMBridgeError as exc:
            # openai package may not be installed — that's OK
            assert "not installed" in str(exc)

    def test_factory_deepseek(self):
        config = LLMSection(provider="deepseek", api_key="test-key")
        try:
            provider = create_provider(config)
            from luna.llm_bridge.providers.deepseek import DeepSeekProvider
            assert isinstance(provider, DeepSeekProvider)
        except LLMBridgeError as exc:
            assert "not installed" in str(exc)

    def test_factory_local(self):
        config = LLMSection(provider="local")
        try:
            provider = create_provider(config)
            from luna.llm_bridge.providers.local import LocalProvider
            assert isinstance(provider, LocalProvider)
        except LLMBridgeError as exc:
            assert "not installed" in str(exc)

    def test_factory_unknown_raises(self):
        config = LLMSection(provider="does-not-exist")
        with pytest.raises(LLMBridgeError, match="Unknown LLM provider"):
            create_provider(config)


# ═══════════════════════════════════════════════════════════════════════════
#  IV. ANTHROPIC PROVIDER (mocked)
# ═══════════════════════════════════════════════════════════════════════════


class TestAnthropicProvider:
    """AnthropicProvider with mocked SDK calls."""

    def test_anthropic_missing_key_raises(self):
        """No API key and no env var → LLMBridgeError."""
        with patch.dict("os.environ", {}, clear=True):
            # Remove ANTHROPIC_API_KEY if present
            import os
            env = os.environ.copy()
            env.pop("ANTHROPIC_API_KEY", None)
            with patch.dict("os.environ", env, clear=True):
                with pytest.raises(LLMBridgeError, match="No Anthropic API key"):
                    from luna.llm_bridge.providers.anthropic import AnthropicProvider
                    AnthropicProvider()

    @pytest.mark.asyncio
    async def test_anthropic_complete_mock(self):
        """Mocked Anthropic API returns correct LLMResponse."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Luna decides: approved.")]
        mock_response.model = "claude-sonnet-4-20250514"
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=20)

        with patch("anthropic.AsyncAnthropic") as MockClient:
            mock_client = MockClient.return_value
            mock_client.messages.create = AsyncMock(return_value=mock_response)

            from luna.llm_bridge.providers.anthropic import AnthropicProvider
            provider = AnthropicProvider(api_key="test-key")
            # Replace the client with our mock
            provider._client = mock_client

            result = await provider.complete(
                [{"role": "user", "content": "test"}],
                system_prompt="Tu es Luna.",
            )

        assert isinstance(result, LLMResponse)
        assert result.content == "Luna decides: approved."
        assert result.model == "claude-sonnet-4-20250514"
        assert result.input_tokens == 100
        assert result.output_tokens == 20


# ═══════════════════════════════════════════════════════════════════════════
#  V. CONFIG INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════

from pathlib import Path

from luna.core.config import LunaConfig


class TestConfigLLM:
    """LLMSection integrates into LunaConfig."""

    def test_config_llm_section_defaults(self):
        """LLMSection() has sensible defaults."""
        section = LLMSection()
        assert section.provider == "anthropic"
        assert section.model == "claude-sonnet-4-20250514"
        assert section.api_key is None
        assert section.base_url is None
        assert section.max_tokens == 4096
        assert section.temperature == 0.7

    def test_config_load_with_llm(self):
        """Loading the real luna.toml includes [llm] section."""
        config = LunaConfig.load(Path("/home/sayohmy/LUNA/luna.toml"))
        assert hasattr(config, "llm")
        assert config.llm.provider == "deepseek"
        assert config.llm.max_tokens == 4096

    def test_config_backward_compatible(self, tmp_path: Path):
        """A luna.toml WITHOUT [llm] still loads (default LLMSection)."""
        content = """\
[luna]
version = "2.2.0-test"
agent_name = "LUNA"
data_dir = "memory_fractal"
pipeline_dir = "pipeline"

[consciousness]
checkpoint_file = "state.json"

[memory]
fractal_root = "memory_fractal"

[pipeline]
root = "pipeline"
"""
        toml_file = tmp_path / "luna.toml"
        toml_file.write_text(content)
        config = LunaConfig.load(toml_file)
        assert config.llm.provider == "anthropic"
        assert config.llm.temperature == 0.7
