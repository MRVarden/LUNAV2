"""DeepSeek provider — OpenAI-compatible API with different defaults."""

from __future__ import annotations

import os

from luna.llm_bridge.bridge import LLMBridge, LLMBridgeError, LLMResponse


class DeepSeekProvider(LLMBridge):
    """DeepSeek API provider using ``openai.AsyncOpenAI`` (compatible API)."""

    def __init__(
        self,
        model: str = "deepseek-chat",
        api_key: str | None = None,
        base_url: str | None = "https://api.deepseek.com/v1",
    ) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not self._api_key:
            raise LLMBridgeError(
                "No DeepSeek API key: set api_key or DEEPSEEK_API_KEY env var.",
                provider="deepseek",
            )
        try:
            import openai  # noqa: F811
        except ImportError as exc:
            raise LLMBridgeError(
                "openai package not installed: pip install openai",
                provider="deepseek",
                original=exc,
            ) from exc
        self._client = openai.AsyncOpenAI(
            api_key=self._api_key,
            base_url=base_url,
        )

    # Models that do not support the temperature parameter
    _NO_TEMPERATURE_MODELS = frozenset({"deepseek-reasoner"})

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        system_prompt: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        full_messages: list[dict[str, str]] = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        params: dict = {
            "model": self._model,
            "messages": full_messages,
            "max_tokens": max_tokens,
        }
        # deepseek-reasoner does not support temperature
        if self._model not in self._NO_TEMPERATURE_MODELS:
            params["temperature"] = temperature

        try:
            response = await self._client.chat.completions.create(**params)
        except Exception as exc:
            raise LLMBridgeError(
                f"DeepSeek API error: {exc}",
                provider="deepseek",
                original=exc,
            ) from exc

        choice = response.choices[0]
        usage = response.usage
        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )
