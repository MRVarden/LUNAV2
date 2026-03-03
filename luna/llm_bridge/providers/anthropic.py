"""Anthropic provider — Claude API via the anthropic SDK."""

from __future__ import annotations

import os

from luna.llm_bridge.bridge import LLMBridge, LLMBridgeError, LLMResponse


class AnthropicProvider(LLMBridge):
    """Claude API provider using ``anthropic.AsyncAnthropic``."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
    ) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise LLMBridgeError(
                "No Anthropic API key: set api_key or ANTHROPIC_API_KEY env var.",
                provider="anthropic",
            )
        # Lazy import — graceful if anthropic not installed.
        try:
            import anthropic  # noqa: F811
        except ImportError as exc:
            raise LLMBridgeError(
                "anthropic package not installed: pip install anthropic",
                provider="anthropic",
                original=exc,
            ) from exc
        self._client = anthropic.AsyncAnthropic(api_key=self._api_key)

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        system_prompt: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        try:
            kwargs: dict = {
                "model": self._model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if system_prompt:
                kwargs["system"] = system_prompt
            response = await self._client.messages.create(**kwargs)
        except Exception as exc:
            raise LLMBridgeError(
                f"Anthropic API error: {exc}",
                provider="anthropic",
                original=exc,
            ) from exc

        return LLMResponse(
            content=response.content[0].text,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
