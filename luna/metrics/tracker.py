"""MetricTracker — provenance tracking for PhiScorer metrics.

Tracks the source (bootstrap/measured/dream) and history of each metric
value fed to the PhiScorer. Enables bootstrap_ratio computation to
measure how much of Luna's self-assessment is real vs synthetic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from luna_common.constants import METRIC_NAMES

log = logging.getLogger(__name__)


class MetricSource(str, Enum):
    """Origin of a metric measurement."""
    BOOTSTRAP = "bootstrap"
    MEASURED = "measured"
    DREAM = "dream"


@dataclass(slots=True)
class MetricEntry:
    """A single metric observation with provenance."""
    value: float
    source: MetricSource
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    pipeline_id: str | None = None


class MetricTracker:
    """Tracks provenance for each of the 7 canonical metrics.

    Maintains latest entry per metric + counts per source.
    Thread-safe: single-writer assumption (Luna engine is single-threaded).
    """

    def __init__(self) -> None:
        self._latest: dict[str, MetricEntry] = {}
        self._counts: dict[str, dict[str, int]] = {
            name: {s.value: 0 for s in MetricSource}
            for name in METRIC_NAMES
        }

    def record(
        self,
        name: str,
        value: float,
        source: MetricSource,
        pipeline_id: str | None = None,
    ) -> MetricEntry:
        """Record a metric value with its source.

        Raises KeyError if name is not a canonical metric.
        """
        if name not in self._counts:
            raise KeyError(f"Unknown metric: {name!r}. Valid: {list(METRIC_NAMES)}")
        entry = MetricEntry(value=value, source=source, pipeline_id=pipeline_id)
        self._latest[name] = entry
        self._counts[name][source.value] += 1
        return entry

    def get(self, name: str) -> MetricEntry | None:
        """Get the latest entry for a metric, or None if never recorded."""
        return self._latest.get(name)

    def bootstrap_ratio(self) -> float:
        """Fraction of metrics whose latest value is BOOTSTRAP.

        Returns 1.0 when all metrics are bootstrap (fresh start).
        Returns 0.0 when all metrics have been measured/dream-replaced.
        Returns 0.0 if no metrics recorded at all.
        """
        if not self._latest:
            return 0.0
        bootstrap_count = sum(
            1 for e in self._latest.values()
            if e.source == MetricSource.BOOTSTRAP
        )
        return bootstrap_count / len(METRIC_NAMES)

    def measured_count(self) -> int:
        """Total number of MEASURED recordings across all metrics."""
        return sum(
            counts[MetricSource.MEASURED.value]
            for counts in self._counts.values()
        )

    def get_status(self) -> dict:
        """Summary for observability."""
        return {
            "bootstrap_ratio": self.bootstrap_ratio(),
            "measured_count": self.measured_count(),
            "latest": {
                name: {
                    "value": e.value,
                    "source": e.source.value,
                    "pipeline_id": e.pipeline_id,
                }
                for name, e in self._latest.items()
            },
        }

    def snapshot_sources(self) -> dict[str, str]:
        """Return metric name -> source string for checkpoint augmentation.

        Used by ChatSession/LunaEngine to enrich PhiScorer.snapshot()
        with source info before saving to checkpoint.
        """
        return {
            name: entry.source.value
            for name, entry in self._latest.items()
        }
