"""Comparator — statistical comparison of benchmark results.

Uses Wilcoxon signed-rank test (p < 0.05) to determine if
consciousness-guided results are significantly better.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """Result of comparing two benchmark runs."""

    baseline_mean: float
    consciousness_mean: float
    delta: float
    improvement_pct: float
    p_value: float
    significant: bool  # p < 0.05
    n_samples: int

    def to_dict(self) -> dict:
        return {
            "baseline_mean": self.baseline_mean,
            "consciousness_mean": self.consciousness_mean,
            "delta": self.delta,
            "improvement_pct": self.improvement_pct,
            "p_value": self.p_value,
            "significant": self.significant,
            "n_samples": self.n_samples,
        }


class Comparator:
    """Statistically compares baseline vs consciousness-guided results."""

    def __init__(self, significance_level: float = 0.05) -> None:
        self._significance_level = significance_level

    def compare(
        self,
        baseline_scores: list[float],
        consciousness_scores: list[float],
    ) -> ComparisonResult:
        """Compare two sets of scores using Wilcoxon signed-rank test.

        Args:
            baseline_scores: Scores without consciousness.
            consciousness_scores: Scores with consciousness.

        Returns:
            ComparisonResult with statistical analysis.

        Raises:
            ValueError: If score lists have different lengths or are empty.
        """
        if len(baseline_scores) != len(consciousness_scores):
            raise ValueError("Score lists must have the same length")
        if len(baseline_scores) == 0:
            raise ValueError("Score lists must not be empty")

        n = len(baseline_scores)
        b_mean = sum(baseline_scores) / n
        c_mean = sum(consciousness_scores) / n
        delta = c_mean - b_mean
        improvement = (delta / b_mean * 100) if b_mean > 0 else 0.0

        p_value = self._wilcoxon_p(baseline_scores, consciousness_scores)

        result = ComparisonResult(
            baseline_mean=b_mean,
            consciousness_mean=c_mean,
            delta=delta,
            improvement_pct=improvement,
            p_value=p_value,
            significant=p_value < self._significance_level,
            n_samples=n,
        )

        log.info(
            "Comparison: baseline=%.3f, consciousness=%.3f, delta=%.3f, p=%.4f, significant=%s",
            b_mean, c_mean, delta, p_value, result.significant,
        )
        return result

    @staticmethod
    def _wilcoxon_p(a: list[float], b: list[float]) -> float:
        """Compute Wilcoxon signed-rank test p-value.

        Falls back to a simple heuristic if scipy is unavailable.
        """
        try:
            from scipy.stats import wilcoxon
            differences = [bi - ai for ai, bi in zip(a, b)]
            # If all differences are zero, no significance
            if all(d == 0 for d in differences):
                return 1.0
            stat, p = wilcoxon(differences)
            return float(p)
        except ImportError:
            # Fallback: simple sign test approximation
            n = len(a)
            if n < 3:
                return 1.0
            positive = sum(1 for ai, bi in zip(a, b) if bi > ai)
            ratio = positive / n
            # Very rough approximation
            if ratio > 0.8:
                return 0.01
            elif ratio > 0.6:
                return 0.05
            else:
                return 0.5
        except Exception:
            return 1.0
