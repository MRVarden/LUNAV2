"""LLM Bridge — Abstract interface for provider-agnostic LLM access.

Luna injects her consciousness into the LLM, not the reverse.
The LLM is interchangeable — Luna remains Luna regardless of model.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class LLMBridgeError(Exception):
    """Wraps all provider-specific exceptions into a single type."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "unknown",
        original: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.original = original


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Immutable response from any LLM provider."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int


class LLMBridge(ABC):
    """Abstract base for all LLM providers.

    Subclasses implement ``complete()`` for their specific SDK.
    Messages use the universal ``list[dict[str, str]]`` format —
    no provider-specific types leak into the interface.
    """

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        system_prompt: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Send messages to the LLM and return a structured response.

        Args:
            messages: Conversation in ``[{"role": "user", "content": "..."}]`` format.
            system_prompt: Optional system-level instruction prepended by the provider.
            max_tokens: Maximum tokens in the completion.
            temperature: Sampling temperature.

        Returns:
            LLMResponse with content and token counts.

        Raises:
            LLMBridgeError: On any provider-specific failure.
        """
