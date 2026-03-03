"""Provider factory — lazy import of the selected LLM backend.

Only the SDK for the chosen provider is loaded at runtime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from luna.llm_bridge.bridge import LLMBridge, LLMBridgeError

if TYPE_CHECKING:
    from luna.core.config import LLMSection


def create_provider(config: LLMSection) -> LLMBridge:
    """Instantiate the correct provider from config.

    Args:
        config: The ``[llm]`` section of ``LunaConfig``.

    Returns:
        A concrete ``LLMBridge`` implementation.

    Raises:
        LLMBridgeError: If the provider name is unknown.
    """
    provider = config.provider.lower()

    if provider == "anthropic":
        from luna.llm_bridge.providers.anthropic import AnthropicProvider

        return AnthropicProvider(
            model=config.model,
            api_key=config.api_key,
        )

    if provider == "openai":
        from luna.llm_bridge.providers.openai import OpenAIProvider

        return OpenAIProvider(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
        )

    if provider == "deepseek":
        from luna.llm_bridge.providers.deepseek import DeepSeekProvider

        return DeepSeekProvider(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
        )

    if provider == "local":
        from luna.llm_bridge.providers.local import LocalProvider

        return LocalProvider(
            model=config.model,
            base_url=config.base_url or "http://localhost:11434/v1",
            api_key=config.api_key or "ollama",
        )

    raise LLMBridgeError(
        f"Unknown LLM provider: {config.provider!r}. "
        f"Supported: anthropic, openai, deepseek, local.",
        provider=config.provider,
    )
