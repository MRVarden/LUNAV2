"""Convergence detection — sliding window analysis for health score stability.

From LUNA_CONSCIOUSNESS_FRAMEWORK.md §V:
  ConvergenceDetector(window=5, tol_relative=0.01, min_iterations=3)

Convergence is declared when:
  1. At least min_iterations samples have been collected.
  2. The relative spread (max - min) / mean < tol_relative.

Trend is computed via linear regression on the window:
  improving (slope > 0.005), degrading (slope < -0.005), plateau.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class ConvergenceResult:
    """Result of a convergence check.

    Attributes:
        converged: True if the series is stable within tolerance.
        reason: Human-readable explanation of the result.
        final_score: Last score value (if converged).
        plateau_mean: Mean of the window (if converged).
        trend: "improving", "degrading", or "plateau".
    """
    converged: bool
    reason: str
    final_score: float | None = None
    plateau_mean: float | None = None
    trend: str | None = None


# Slope threshold for trend classification (framework §V)
_SLOPE_THRESHOLD: float = 0.005


class ConvergenceDetector:
    """Sliding window convergence detector for scalar time series.

    Matches LUNA_CONSCIOUSNESS_FRAMEWORK.md §V specification.

    Args:
        window: Number of samples in the sliding window (default 5).
        tol_relative: Maximum relative spread for convergence (default 0.01).
        min_iterations: Minimum samples before convergence can be declared (default 3).
    """

    def __init__(
        self,
        window: int = 5,
        tol_relative: float = 0.01,
        min_iterations: int = 3,
    ) -> None:
        if window < 2:
            raise ValueError(f"window must be >= 2, got {window}")
        if tol_relative <= 0:
            raise ValueError(f"tol_relative must be > 0, got {tol_relative}")
        if min_iterations < 1:
            raise ValueError(f"min_iterations must be >= 1, got {min_iterations}")
        self.window = window
        self.tol_relative = tol_relative
        self.min_iterations = min_iterations
        self.scores: deque[float] = deque(maxlen=window)

    def update(self, score: float) -> ConvergenceResult:
        """Add a new score and return convergence status.

        Args:
            score: A scalar measurement (typically in [0, 1]).

        Returns:
            ConvergenceResult with current convergence analysis.
        """
        self.scores.append(score)

        if len(self.scores) < self.min_iterations:
            return ConvergenceResult(
                converged=False,
                reason="insufficient_data",
            )

        scores = list(self.scores)
        mean = sum(scores) / len(scores)
        spread = max(scores) - min(scores)
        eps = 1e-9

        relative_spread = spread / max(mean, eps)

        # Trend via linear regression
        slope = _linear_slope(scores)
        if slope > _SLOPE_THRESHOLD:
            trend = "improving"
        elif slope < -_SLOPE_THRESHOLD:
            trend = "degrading"
        else:
            trend = "plateau"

        if relative_spread < self.tol_relative:
            return ConvergenceResult(
                converged=True,
                reason=f"spread={relative_spread:.4f} < tol={self.tol_relative}",
                final_score=scores[-1],
                plateau_mean=mean,
                trend=trend,
            )

        return ConvergenceResult(
            converged=False,
            reason=f"spread={relative_spread:.4f}, trend={trend}",
            trend=trend,
        )

    # Alias for backward compatibility with push()-based code
    push = update

    def reset(self) -> None:
        """Clear all buffered values."""
        self.scores.clear()

    def __repr__(self) -> str:
        n = len(self.scores)
        return f"ConvergenceDetector(window={self.window}, samples={n})"


def _linear_slope(values: Sequence[float]) -> float:
    """Compute the slope of a simple linear regression y = a + b*x.

    Uses the closed-form solution: b = Cov(x, y) / Var(x).
    x is just the index [0, 1, ..., n-1].

    Returns 0.0 if fewer than 2 values.
    """
    n = len(values)
    if n < 2:
        return 0.0

    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n

    cov_xy = 0.0
    var_x = 0.0
    for i, y in enumerate(values):
        dx = i - x_mean
        cov_xy += dx * (y - y_mean)
        var_x += dx * dx

    if var_x < 1e-15:
        return 0.0
    return cov_xy / var_x
