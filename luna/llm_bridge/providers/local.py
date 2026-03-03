"""Local provider — Ollama, llama.cpp, vLLM via OpenAI-compatible API."""

from __future__ import annotations

from luna.llm_bridge.bridge import LLMBridge, LLMBridgeError, LLMResponse


class LocalProvider(LLMBridge):
    """Local LLM provider using OpenAI-compatible API (Ollama default)."""

    def __init__(
        self,
        model: str = "llama3",
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "ollama",
    ) -> None:
        self._model = model
        try:
            import openai  # noqa: F811
        except ImportError as exc:
            raise LLMBridgeError(
                "openai package not installed: pip install openai",
                provider="local",
                original=exc,
            ) from exc
        self._client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )

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
                f"Local LLM error: {exc}",
                provider="local",
                original=exc,
            ) from exc

        choice = response.choices[0]
        usage = response.usage
        return LLMResponse(
            content=choice.message.content or "",
            model=response.model or self._model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )
