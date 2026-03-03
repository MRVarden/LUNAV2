"""Retry policy — exponential backoff with Phi-derived factor.

Used exclusively for LLM calls (network = flaky).
Does NOT catch logic errors — only LLMBridgeError.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from luna_common.constants import PHI
from luna.llm_bridge.bridge import LLMBridgeError

log = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Immutable retry configuration with Phi-derived backoff."""

    max_retries: int = 3
    base_delay: float = 1.0      # seconds
    max_delay: float = 30.0      # ceiling
    backoff_factor: float = PHI   # 1.618 — thematic


async def retry_async(
    fn: Callable[..., Awaitable[T]],
    *args: object,
    policy: RetryPolicy = RetryPolicy(),
    on_retry: Callable[[int, Exception], None] | None = None,
    **kwargs: object,
) -> T:
    """Execute *fn* with retry + exponential backoff.

    Only catches ``LLMBridgeError``. Raises the last exception
    if all retries are exhausted.

    Args:
        fn: Async callable to execute.
        *args: Positional arguments forwarded to *fn*.
        policy: Retry configuration.
        on_retry: Optional callback ``(attempt, exception)`` called before each retry.
        **kwargs: Keyword arguments forwarded to *fn*.

    Returns:
        The result of *fn*.

    Raises:
        LLMBridgeError: If all retries fail.
    """
    last_exc: LLMBridgeError | None = None
    delay = policy.base_delay

    for attempt in range(1 + policy.max_retries):
        try:
            return await fn(*args, **kwargs)
        except LLMBridgeError as exc:
            last_exc = exc
            if attempt == policy.max_retries:
                break
            if on_retry is not None:
                on_retry(attempt + 1, exc)
            log.debug(
                "Retry %d/%d after %.2fs: %s",
                attempt + 1,
                policy.max_retries,
                delay,
                exc,
            )
            await asyncio.sleep(delay)
            delay = min(delay * policy.backoff_factor, policy.max_delay)

    assert last_exc is not None  # noqa: S101
    raise last_exc
