"""Redis metrics store — graceful degradation if unavailable.

Stores real-time metrics in Redis for dashboard consumption.
Falls back gracefully to in-memory storage when Redis is not available.
"""

from __future__ import annotations

import json
import logging
import time

log = logging.getLogger(__name__)


class RedisMetricsStore:
    """Metrics store with Redis backend and graceful degradation.

    When Redis is unavailable, stores metrics in memory only.
    Reconnection is attempted on each write operation.
    """

    def __init__(
        self,
        redis_url: str = "redis://127.0.0.1:6379/0",
        key_prefix: str = "luna:",
        ttl_seconds: int = 3600,
    ) -> None:
        self._redis_url = redis_url
        self._key_prefix = key_prefix
        self._ttl_seconds = ttl_seconds
        self._client = None
        self._connected = False
        self._fallback: dict[str, str] = {}
        self._connect()

    def _connect(self) -> None:
        """Attempt to connect to Redis."""
        try:
            import redis
            self._client = redis.from_url(self._redis_url, decode_responses=True)
            self._client.ping()
            self._connected = True
            log.info("RedisMetricsStore: connected to %s", self._redis_url)
        except Exception as exc:
            self._connected = False
            self._client = None
            log.debug("RedisMetricsStore: Redis unavailable — using fallback (%s)", exc)

    @property
    def is_connected(self) -> bool:
        """Whether Redis is currently connected."""
        return self._connected

    def set(self, key: str, value: dict | str | float) -> None:
        """Store a metric value.

        Args:
            key: Metric key (prefix is added automatically).
            value: Value to store (dicts are JSON-serialized).
        """
        full_key = f"{self._key_prefix}{key}"

        if isinstance(value, dict):
            serialized = json.dumps(value)
        else:
            serialized = str(value)

        if self._connected and self._client is not None:
            try:
                self._client.setex(full_key, self._ttl_seconds, serialized)
                return
            except Exception as exc:
                log.warning("RedisMetricsStore: write failed — %s", exc)
                self._connected = False

        # Fallback to in-memory
        self._fallback[full_key] = serialized

    def get(self, key: str) -> str | None:
        """Retrieve a metric value.

        Args:
            key: Metric key.

        Returns:
            The stored value as string, or None if not found.
        """
        full_key = f"{self._key_prefix}{key}"

        if self._connected and self._client is not None:
            try:
                return self._client.get(full_key)
            except Exception as exc:
                log.warning("RedisMetricsStore: read failed — %s", exc)
                self._connected = False

        return self._fallback.get(full_key)

    def publish_vitals(self, vitals: dict) -> None:
        """Publish vital signs to Redis.

        Args:
            vitals: Dictionary of vital sign metrics.
        """
        self.set("vitals", vitals)
        self.set("vitals:timestamp", str(time.time()))

    def publish_psi(self, psi: list[float]) -> None:
        """Publish Psi state vector.

        Args:
            psi: The 4-component Psi vector.
        """
        self.set("psi", {"components": psi})

    def publish_health(self, health_score: float, phase: str) -> None:
        """Publish health score and phase.

        Args:
            health_score: Current health score [0,1].
            phase: Current health phase name.
        """
        self.set("health", {"score": health_score, "phase": phase})

    def get_status(self) -> dict:
        """Return current store status."""
        return {
            "connected": self._connected,
            "redis_url": self._redis_url,
            "key_prefix": self._key_prefix,
            "ttl_seconds": self._ttl_seconds,
            "fallback_keys": len(self._fallback),
        }
