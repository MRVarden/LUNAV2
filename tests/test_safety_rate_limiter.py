"""Tests for rate limiter — token bucket algorithm."""

from __future__ import annotations

import pytest

from luna.safety.rate_limiter import RateLimiter


class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_initial_tokens(self):
        """Buckets start with full tokens."""
        rl = RateLimiter(max_generations_per_hour=10, max_commits_per_hour=5)
        assert rl.remaining("generation") == 10.0
        assert rl.remaining("commit") == 5.0

    def test_acquire_consumes_tokens(self):
        """acquire() reduces available tokens."""
        rl = RateLimiter(max_generations_per_hour=10, max_commits_per_hour=5)
        assert rl.acquire("generation") is True
        assert rl.remaining("generation") < 10.0

    def test_acquire_denied_when_empty(self):
        """acquire() returns False when tokens exhausted."""
        rl = RateLimiter(max_generations_per_hour=3, max_commits_per_hour=1)
        for _ in range(3):
            assert rl.acquire("generation") is True
        assert rl.acquire("generation") is False

    def test_unknown_operation_blocked(self):
        """Unknown operation types are blocked (fail-closed)."""
        rl = RateLimiter()
        assert rl.acquire("unknown_op") is False

    def test_remaining_unknown_operation(self):
        """Unknown operation returns infinite remaining."""
        rl = RateLimiter()
        assert rl.remaining("unknown") == float("inf")

    def test_reset_single_bucket(self):
        """Reset refills a single bucket."""
        rl = RateLimiter(max_generations_per_hour=5, max_commits_per_hour=3)
        for _ in range(5):
            rl.acquire("generation")
        for _ in range(3):
            rl.acquire("commit")

        rl.reset("generation")
        assert rl.remaining("generation") == 5.0
        assert rl.remaining("commit") < 3.0  # commit not reset

    def test_reset_all_buckets(self):
        """Reset with no argument refills all buckets."""
        rl = RateLimiter(max_generations_per_hour=5, max_commits_per_hour=3)
        for _ in range(5):
            rl.acquire("generation")
        for _ in range(3):
            rl.acquire("commit")

        rl.reset()
        assert rl.remaining("generation") == 5.0
        assert rl.remaining("commit") == 3.0

    def test_add_custom_bucket(self):
        """Custom operation types can be added."""
        rl = RateLimiter()
        rl.add_bucket("deploy", max_per_hour=2)

        assert rl.acquire("deploy") is True
        assert rl.acquire("deploy") is True
        assert rl.acquire("deploy") is False

    def test_acquire_with_cost(self):
        """acquire() supports custom cost."""
        rl = RateLimiter(max_generations_per_hour=10, max_commits_per_hour=5)
        assert rl.acquire("generation", cost=8) is True
        assert rl.acquire("generation", cost=3) is False
        assert rl.acquire("generation", cost=2) is True

    def test_get_status(self):
        """get_status returns bucket information."""
        rl = RateLimiter(max_generations_per_hour=100, max_commits_per_hour=20)
        status = rl.get_status()
        assert "buckets" in status
        assert "generation" in status["buckets"]
        assert "commit" in status["buckets"]
        assert status["buckets"]["generation"]["max"] == 100

    def test_commit_rate_limit(self):
        """Commit bucket works independently."""
        rl = RateLimiter(max_generations_per_hour=100, max_commits_per_hour=2)
        assert rl.acquire("commit") is True
        assert rl.acquire("commit") is True
        assert rl.acquire("commit") is False
        # Generation bucket should still work
        assert rl.acquire("generation") is True
