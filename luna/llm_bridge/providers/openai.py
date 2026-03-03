"""OpenAI provider — GPT API via the openai SDK (optional dependency)."""

from __future__ import annotations

import os

from luna.llm_bridge.bridge import LLMBridge, LLMBridgeError, LLMResponse


class OpenAIProvider(LLMBridge):
    """GPT API provider using ``openai.AsyncOpenAI``."""

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise LLMBridgeError(
                "No OpenAI API key: set api_key or OPENAI_API_KEY env var.",
                provider="openai",
            )
        try:
            import openai  # noqa: F811
        except ImportError as exc:
            raise LLMBridgeError(
                "openai package not installed: pip install openai",
                provider="openai",
                original=exc,
            ) from exc
        kwargs: dict = {"api_key": self._api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = openai.AsyncOpenAI(**kwargs)

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

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=full_messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            raise LLMBridgeError(
                f"OpenAI API error: {exc}",
                provider="openai",
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
