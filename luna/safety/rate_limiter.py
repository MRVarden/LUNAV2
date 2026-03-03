"""Rate limiter — token bucket with configurable limits.

Prevents excessive operations by limiting the rate at which actions
can be performed, measured per hour.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(slots=True)
class _Bucket:
    """Internal token bucket for a single operation type."""

    max_tokens: int
    tokens: float
    last_refill: float
    refill_rate: float  # tokens per second

    def refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def try_acquire(self, cost: int = 1) -> bool:
        """Try to acquire tokens. Returns True if allowed."""
        self.refill()
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False


class RateLimiter:
    """Token-bucket rate limiter with per-operation-type limits.

    Each operation type gets its own bucket. Limits are specified
    as operations per hour.
    """

    def __init__(
        self,
        max_generations_per_hour: int = 100,
        max_commits_per_hour: int = 20,
    ) -> None:
        now = time.monotonic()
        self._buckets: dict[str, _Bucket] = {
            "generation": _Bucket(
                max_tokens=max_generations_per_hour,
                tokens=float(max_generations_per_hour),
                last_refill=now,
                refill_rate=max_generations_per_hour / 3600.0,
            ),
            "commit": _Bucket(
                max_tokens=max_commits_per_hour,
                tokens=float(max_commits_per_hour),
                last_refill=now,
                refill_rate=max_commits_per_hour / 3600.0,
            ),
        }

    def add_bucket(self, name: str, max_per_hour: int) -> None:
        """Add a custom operation type bucket.

        Args:
            name: Operation type name.
            max_per_hour: Maximum operations per hour.
        """
        self._buckets[name] = _Bucket(
            max_tokens=max_per_hour,
            tokens=float(max_per_hour),
            last_refill=time.monotonic(),
            refill_rate=max_per_hour / 3600.0,
        )

    def acquire(self, operation: str, cost: int = 1) -> bool:
        """Try to acquire permission for an operation.

        Args:
            operation: The operation type (e.g. "generation", "commit").
            cost: How many tokens to consume (default 1).

        Returns:
            True if the operation is allowed, False if rate limited.
        """
        bucket = self._buckets.get(operation)
        if bucket is None:
            log.warning("RateLimiter: unknown operation %r blocked", operation)
            return False

        allowed = bucket.try_acquire(cost)
        if not allowed:
            log.warning(
                "RateLimiter: %s rate limited (%.1f/%.0f tokens available)",
                operation,
                bucket.tokens,
                bucket.max_tokens,
            )
        return allowed

    def remaining(self, operation: str) -> float:
        """Get remaining tokens for an operation type.

        Args:
            operation: The operation type.

        Returns:
            Number of remaining tokens (may be fractional).
        """
        bucket = self._buckets.get(operation)
        if bucket is None:
            return float("inf")
        bucket.refill()
        return bucket.tokens

    def reset(self, operation: str | None = None) -> None:
        """Reset one or all buckets to full capacity.

        Args:
            operation: If specified, reset only this bucket.
                       If None, reset all buckets.
        """
        if operation is not None:
            bucket = self._buckets.get(operation)
            if bucket is not None:
                bucket.tokens = float(bucket.max_tokens)
                bucket.last_refill = time.monotonic()
        else:
            for bucket in self._buckets.values():
                bucket.tokens = float(bucket.max_tokens)
                bucket.last_refill = time.monotonic()

    def get_status(self) -> dict:
        """Return current rate limiter status."""
        status: dict[str, dict] = {}
        for name, bucket in self._buckets.items():
            bucket.refill()
            status[name] = {
                "remaining": round(bucket.tokens, 1),
                "max": bucket.max_tokens,
                "refill_rate_per_hour": round(bucket.refill_rate * 3600, 1),
            }
        return {"buckets": status}
