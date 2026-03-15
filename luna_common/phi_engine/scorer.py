"""Phi scorer — EMA-based composite quality scoring with 7 Fibonacci-weighted metrics.

MetricEMA tracks a single metric's exponential moving average.
PhiScorer combines all 7 EMAs into a weighted composite health score.

All values are bounded [0, 1]. Partial data is handled gracefully:
metrics that have never been updated are excluded from the weighted sum,
and the remaining weights are renormalized.
"""

from __future__ import annotations

import logging
import math
from collections import deque

log = logging.getLogger(__name__)

from luna_common.constants import METRIC_NAMES, PHI_WEIGHTS, PHI_EMA_ALPHAS


class MetricEMA:
    """Exponential Moving Average tracker for a single metric.

    From LUNA_CONSCIOUSNESS_FRAMEWORK.md §III: value starts at None,
    first raw becomes initial value; history deque(maxlen=100).

    Attributes:
        name: Metric name (one of METRIC_NAMES).
        alpha: Smoothing factor in (0, 1]. Higher = faster response.
        value: Current EMA value, or None if never updated.
        history: Rolling history of raw measurements (maxlen=100).
    """

    __slots__ = ("name", "alpha", "value", "history")

    def __init__(self, name: str, alpha: float) -> None:
        if not 0 < alpha <= 1:
            raise ValueError(f"alpha must be in (0, 1], got {alpha}")
        self.name = name
        self.alpha = alpha
        self.value: float | None = None
        self.history: deque[float] = deque(maxlen=100)

    def update(self, raw: float) -> float:
        """Feed a new raw measurement and return the updated EMA.

        Args:
            raw: Raw metric value, clamped to [0, 1]. NaN/Inf ignored.

        Returns:
            The new EMA value after incorporating *raw*.
        """
        if not math.isfinite(raw):
            return self.value if self.value is not None else 0.0
        clamped = max(0.0, min(1.0, raw))
        self.history.append(clamped)
        if self.value is None:
            self.value = clamped
        else:
            self.value = self.alpha * clamped + (1.0 - self.alpha) * self.value
        return self.value

    def reset(self) -> None:
        """Reset EMA to uninitialized state."""
        self.value = None
        self.history.clear()

    def __repr__(self) -> str:
        v = f"{self.value:.4f}" if self.value is not None else "None"
        return f"MetricEMA({self.name!r}, alpha={self.alpha}, value={v})"


class PhiScorer:
    """Composite health scorer using 7 Fibonacci-weighted EMA metrics.

    The scorer maintains one MetricEMA per canonical metric. On each
    ``score()`` call, it combines all initialized EMAs into a weighted
    average (renormalizing weights to exclude uninitialized metrics).

    Typical usage::

        scorer = PhiScorer()
        scorer.update("integration_coherence", 0.95)
        scorer.update("identity_anchoring", 0.72)
        composite = scorer.score()  # weighted average of available metrics
    """

    def __init__(
        self,
        metric_names: tuple[str, ...] = METRIC_NAMES,
        weights: tuple[float, ...] = PHI_WEIGHTS,
        alphas: tuple[float, ...] = PHI_EMA_ALPHAS,
    ) -> None:
        if len(metric_names) != len(weights) or len(metric_names) != len(alphas):
            raise ValueError(
                f"metric_names ({len(metric_names)}), weights ({len(weights)}), "
                f"and alphas ({len(alphas)}) must have the same length"
            )
        self._names = metric_names
        self._weights = weights
        self._emas: dict[str, MetricEMA] = {
            name: MetricEMA(name, alpha)
            for name, alpha in zip(metric_names, alphas)
        }
        self._weight_map: dict[str, float] = dict(zip(metric_names, weights))

    def update(self, metric_name: str, raw_value: float) -> float:
        """Update a single metric's EMA and return the new smoothed value.

        Args:
            metric_name: Must be one of the canonical metric names.
            raw_value: Raw measurement, clamped to [0, 1].

        Returns:
            The updated EMA value for this metric.

        Raises:
            KeyError: If *metric_name* is not a recognized metric.
        """
        if metric_name not in self._emas:
            raise KeyError(
                f"Unknown metric {metric_name!r}. "
                f"Valid names: {list(self._emas.keys())}"
            )
        return self._emas[metric_name].update(raw_value)

    def score(self) -> float:
        """Compute the weighted composite health score.

        Only metrics that have been updated at least once contribute.
        Weights of uninitialized metrics are redistributed proportionally
        among initialized ones. If no metrics are initialized, returns 0.0.

        Returns:
            Composite score in [0, 1].
        """
        numerator = 0.0
        denominator = 0.0
        for name, ema in self._emas.items():
            if ema.value is not None:
                w = self._weight_map[name]
                numerator += w * ema.value
                denominator += w
        if denominator == 0.0:
            return 0.0
        return max(0.0, min(1.0, numerator / denominator))

    def get_metric(self, metric_name: str) -> float | None:
        """Return the current EMA value for a metric, or None if uninitialized."""
        if metric_name not in self._emas:
            raise KeyError(f"Unknown metric: {metric_name!r}")
        return self._emas[metric_name].value

    def get_all_metrics(self) -> dict[str, float | None]:
        """Return a dict of all metric names to their current EMA values."""
        return {name: ema.value for name, ema in self._emas.items()}

    def initialized_count(self) -> int:
        """Return the number of metrics that have been updated at least once."""
        return sum(1 for ema in self._emas.values() if ema.value is not None)

    def snapshot(self) -> dict[str, dict]:
        """Return a serializable snapshot of all metric EMA values.

        Only includes metrics that have been initialized (value is not None).
        Used for checkpoint persistence so metrics survive restarts.

        Returns:
            Dict mapping metric name to {"value": float, "source": str}.
            Source defaults to "measured" — callers may override before saving.
        """
        result: dict[str, dict] = {}
        for name, ema in self._emas.items():
            if ema.value is not None:
                result[name] = {"value": ema.value}
        return result

    def restore(self, snapshot: dict[str, dict]) -> int:
        """Restore EMA values from a checkpoint snapshot.

        Sets each metric's EMA value directly (skipping the smoothing step).
        Unknown metric names are logged at WARNING level and skipped.

        Args:
            snapshot: Dict mapping metric name to {"value": float, ...}.

        Returns:
            Number of metrics successfully restored.
        """
        count = 0
        for name, entry in snapshot.items():
            if name not in self._emas:
                log.warning("PhiScorer.restore: skipping unknown metric %r", name)
                continue
            if "value" not in entry:
                log.warning("PhiScorer.restore: skipping metric %r (no 'value' key)", name)
                continue
            value = entry["value"]
            if isinstance(value, (int, float)) and math.isfinite(value):
                clamped = max(0.0, min(1.0, float(value)))
                self._emas[name].value = clamped
                count += 1
        return count

    def reset(self) -> None:
        """Reset all EMAs to uninitialized state."""
        for ema in self._emas.values():
            ema.reset()

    def __repr__(self) -> str:
        init = self.initialized_count()
        total = len(self._emas)
        return f"PhiScorer(score={self.score():.4f}, initialized={init}/{total})"
