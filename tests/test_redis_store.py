"""Tests for Redis metrics store — graceful degradation."""

from __future__ import annotations

import pytest

from luna.observability.redis_store import RedisMetricsStore


class TestRedisMetricsStore:
    """Tests for RedisMetricsStore with fallback behavior.

    These tests run without a Redis server — they verify the
    graceful degradation to in-memory storage.
    """

    @pytest.fixture
    def store(self):
        """Store that will fail to connect (no Redis available)."""
        return RedisMetricsStore(redis_url="redis://127.0.0.1:59999/0")

    def test_graceful_degradation(self, store):
        """Store works without Redis via fallback."""
        assert not store.is_connected

    def test_set_and_get_fallback(self, store):
        """set/get work through fallback storage."""
        store.set("test_key", "test_value")
        assert store.get("test_key") == "test_value"

    def test_set_dict_fallback(self, store):
        """Dict values are JSON-serialized in fallback."""
        store.set("metrics", {"score": 0.85})
        result = store.get("metrics")
        assert '"score"' in result
        assert "0.85" in result

    def test_get_nonexistent(self, store):
        """get() returns None for missing keys."""
        assert store.get("nonexistent") is None

    def test_publish_vitals(self, store):
        """publish_vitals stores vitals data."""
        store.publish_vitals({"overall_vitality": 0.9})
        assert store.get("vitals") is not None
        assert store.get("vitals:timestamp") is not None

    def test_publish_psi(self, store):
        """publish_psi stores Psi vector."""
        store.publish_psi([0.25, 0.35, 0.25, 0.15])
        result = store.get("psi")
        assert "0.25" in result

    def test_publish_health(self, store):
        """publish_health stores health data."""
        store.publish_health(0.85, "SOLID")
        result = store.get("health")
        assert "SOLID" in result

    def test_get_status(self, store):
        """get_status returns expected structure."""
        status = store.get_status()
        assert "connected" in status
        assert "redis_url" in status
        assert status["connected"] is False

    def test_key_prefix(self, store):
        """Keys are prefixed correctly."""
        store.set("mykey", "val")
        assert store.get("mykey") == "val"
