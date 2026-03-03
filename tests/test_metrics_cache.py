"""Tests for metrics cache — hash-based invalidation."""

from __future__ import annotations

from pathlib import Path

import pytest

from luna.metrics.cache import CacheKey, MetricsCache
from luna.metrics.normalizer import NormalizedMetrics


@pytest.fixture
def cache_dir(tmp_path):
    return tmp_path / "metrics_cache"


@pytest.fixture
def cache(cache_dir):
    return MetricsCache(cache_dir=cache_dir, enabled=True)


@pytest.fixture
def sample_metrics():
    return NormalizedMetrics(
        values={"complexity_score": 0.8, "coverage_pct": 0.75},
        zones={"complexity_score": "comfort", "coverage_pct": "comfort"},
        raw_sources=["radon", "coverage_py"],
    )


class TestCacheKey:
    """Tests for CacheKey dataclass."""

    def test_from_file(self, tmp_path):
        """CacheKey.from_path works on a file."""
        f = tmp_path / "test.py"
        f.write_text("print('hello')")
        key = CacheKey.from_path(f)
        assert key.path == str(f.resolve())
        assert key.mtime > 0
        assert key.size > 0

    def test_from_directory(self, tmp_path):
        """CacheKey.from_path works on a directory."""
        (tmp_path / "a.py").write_text("a = 1")
        (tmp_path / "b.py").write_text("b = 2")
        key = CacheKey.from_path(tmp_path)
        assert key.size > 0

    def test_hexdigest_deterministic(self, tmp_path):
        """Same path produces same hexdigest."""
        f = tmp_path / "test.py"
        f.write_text("x = 1")
        k1 = CacheKey.from_path(f)
        k2 = CacheKey.from_path(f)
        assert k1.hexdigest() == k2.hexdigest()

    def test_hexdigest_changes_on_modify(self, tmp_path):
        """Modified file produces different hexdigest."""
        f = tmp_path / "test.py"
        f.write_text("x = 1")
        k1 = CacheKey.from_path(f)

        import time
        time.sleep(0.05)  # Ensure mtime changes
        f.write_text("x = 2")
        k2 = CacheKey.from_path(f)
        assert k1.hexdigest() != k2.hexdigest()

    def test_frozen(self):
        """CacheKey is immutable."""
        key = CacheKey(path="/test", mtime=1.0, size=100)
        with pytest.raises(AttributeError):
            key.mtime = 2.0  # type: ignore[misc]


class TestMetricsCache:
    """Tests for MetricsCache."""

    def test_put_and_get(self, cache, sample_metrics):
        """Cache stores and retrieves metrics."""
        key = CacheKey(path="/test", mtime=1.0, size=100)
        cache.put(key, sample_metrics)
        result = cache.get(key)
        assert result is not None
        assert result.values == sample_metrics.values
        assert result.zones == sample_metrics.zones

    def test_cache_miss(self, cache):
        """Cache returns None on miss."""
        key = CacheKey(path="/nonexistent", mtime=1.0, size=0)
        assert cache.get(key) is None

    def test_invalidate(self, cache, sample_metrics):
        """Invalidate removes a cache entry."""
        key = CacheKey(path="/test", mtime=1.0, size=100)
        cache.put(key, sample_metrics)
        assert cache.invalidate(key) is True
        assert cache.get(key) is None

    def test_invalidate_missing(self, cache):
        """Invalidate returns False for non-existent entry."""
        key = CacheKey(path="/nope", mtime=1.0, size=0)
        assert cache.invalidate(key) is False

    def test_clear(self, cache, sample_metrics):
        """Clear removes all entries."""
        for i in range(5):
            key = CacheKey(path=f"/test/{i}", mtime=float(i), size=i * 10)
            cache.put(key, sample_metrics)
        count = cache.clear()
        assert count == 5

    def test_disabled_cache(self, cache_dir, sample_metrics):
        """Disabled cache never stores or returns."""
        cache = MetricsCache(cache_dir=cache_dir, enabled=False)
        key = CacheKey(path="/test", mtime=1.0, size=100)
        cache.put(key, sample_metrics)
        assert cache.get(key) is None

    def test_cache_dir_created(self, tmp_path):
        """Cache directory is created automatically."""
        new_dir = tmp_path / "new_cache_dir"
        assert not new_dir.exists()
        MetricsCache(cache_dir=new_dir, enabled=True)
        assert new_dir.exists()

    def test_atomic_write(self, cache, sample_metrics):
        """No .tmp files remain after successful write."""
        key = CacheKey(path="/test", mtime=1.0, size=100)
        cache.put(key, sample_metrics)
        tmp_files = list(cache._cache_dir.glob("*.tmp"))
        assert len(tmp_files) == 0
