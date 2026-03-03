"""Metrics collector — orchestrates runners by detected language.

Detects the language of a project path, dispatches to appropriate runners,
collects RawMetrics, normalizes, and optionally feeds PhiScorer.
"""

from __future__ import annotations

import logging
from pathlib import Path

from luna.metrics.base_runner import BaseRunner, RawMetrics
from luna.metrics.cache import CacheKey, MetricsCache
from luna.metrics.normalizer import NormalizedMetrics, normalize
from luna.metrics.runners.ast_runner import AstRunner
from luna.metrics.runners.coverage_py_runner import CoveragePyRunner
from luna.metrics.runners.radon_runner import RadonRunner

log = logging.getLogger(__name__)

# File extension -> language mapping
_EXTENSION_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".rs": "rust",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".java": "java",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
}


class MetricsCollector:
    """Orchestrate runners by detected language, normalize, cache results.

    Usage:
        collector = MetricsCollector(cache_dir=Path("data/metrics_cache"))
        metrics = await collector.collect(Path("/path/to/project"))
        # metrics.values has the 7 canonical metrics in [0, 1]
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        cache_enabled: bool = True,
        timeout: float = 60.0,
    ) -> None:
        self._timeout = timeout

        # Initialize cache
        self._cache = MetricsCache(
            cache_dir=cache_dir or Path("data/metrics_cache"),
            enabled=cache_enabled,
        )

        # Register runners by language
        self._runners: dict[str, list[BaseRunner]] = {
            "python": [
                RadonRunner(timeout=timeout),
                AstRunner(),
                CoveragePyRunner(timeout=timeout),
            ],
        }

    async def collect(self, path: Path) -> NormalizedMetrics:
        """Run all applicable runners on path, normalize results.

        1. Detect languages present in the path.
        2. Check cache — return cached result if valid.
        3. Run all runners for detected languages.
        4. Normalize raw metrics to [0, 1].
        5. Cache and return the result.

        Args:
            path: File or directory to analyze.

        Returns:
            NormalizedMetrics with available metrics in [0, 1].
        """
        if not path.exists():
            log.warning("Path does not exist: %s", path)
            return NormalizedMetrics()

        # Check cache
        cache_key = CacheKey.from_path(path)
        cached = self._cache.get(cache_key)
        if cached is not None:
            log.debug("Cache hit for %s", path)
            return cached

        # Detect languages
        languages = self._detect_languages(path)
        if not languages:
            log.debug("No recognized languages at %s", path)
            return NormalizedMetrics()

        # Collect runners for all detected languages
        runners: list[BaseRunner] = []
        for lang in languages:
            runners.extend(self._runners.get(lang, []))

        if not runners:
            log.debug("No runners available for languages: %s", languages)
            return NormalizedMetrics()

        # Run all applicable runners
        raw_results: list[RawMetrics] = []
        for runner in runners:
            if not await runner.is_available():
                log.debug("Runner '%s' not available, skipping", runner.name)
                continue

            log.debug("Running '%s' on %s", runner.name, path)
            result = await runner.run(path)
            raw_results.append(result)

            if not result.success:
                log.debug(
                    "Runner '%s' failed on %s: %s",
                    runner.name, path, result.errors,
                )

        # Normalize
        metrics = normalize(raw_results)

        # Cache the result
        self._cache.put(cache_key, metrics)

        log.info(
            "Collected %d metrics from %s (%d runners): %s",
            len(metrics.values),
            path,
            len(raw_results),
            list(metrics.values.keys()),
        )

        return metrics

    def register_runner(self, language: str, runner: BaseRunner) -> None:
        """Register an additional runner for a language."""
        if language not in self._runners:
            self._runners[language] = []
        self._runners[language].append(runner)

    def get_status(self) -> dict:
        """Metrics subsystem status."""
        return {
            "registered_languages": list(self._runners.keys()),
            "runners_per_language": {
                lang: [r.name for r in runners]
                for lang, runners in self._runners.items()
            },
            "cache_enabled": self._cache.enabled,
        }

    def _detect_languages(self, path: Path) -> set[str]:
        """Detect programming languages present at the given path."""
        languages: set[str] = set()

        if path.is_file():
            lang = _EXTENSION_LANGUAGE.get(path.suffix)
            if lang:
                languages.add(lang)
        elif path.is_dir():
            for child in path.rglob("*"):
                if child.is_file():
                    lang = _EXTENSION_LANGUAGE.get(child.suffix)
                    if lang:
                        languages.add(lang)

        return languages
