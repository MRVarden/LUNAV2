"""Soft constraints — Fibonacci zone classification and penalty functions.

SoftConstraint classifies a metric value into one of four Fibonacci zones
(comfort, acceptable, warning, critical) and applies a graduated penalty.

FibonacciZone is the result of classification, containing the zone name
and the penalty factor.

function_size_score is a convenience function that converts a raw function
line count into a [0, 1] score using the Fibonacci zone system.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from luna_common.constants import FIBONACCI_ZONES, FUNCTION_SIZE_TARGET

ZoneType = Literal["comfort", "acceptable", "warning", "critical"]

# Penalty factors for each zone (from plan spec)
_ZONE_PENALTIES: dict[str, float] = {
    "comfort":    1.0,    # No penalty
    "acceptable": 0.85,   # Mild penalty (15% reduction)
    "warning":    0.50,   # Moderate penalty (50% reduction)
    "critical":   0.10,   # Severe penalty (90% reduction)
}


@dataclass(frozen=True, slots=True)
class FibonacciZone:
    """Result of classifying a value into a Fibonacci zone.

    Attributes:
        zone: Zone name (comfort, acceptable, warning, critical).
        value: The original value that was classified.
        penalty: Penalty multiplier for this zone (1.0 = no penalty).
        penalized_value: value * penalty.
    """
    zone: str
    value: float
    penalty: float
    penalized_value: float


class SoftConstraint:
    """Fibonacci zone classifier for a single metric.

    Classifies values in [0, 1] into four zones based on the golden ratio
    derived boundaries from FIBONACCI_ZONES constants.

    Args:
        zones: Zone boundary mapping (default FIBONACCI_ZONES).
        penalties: Penalty factor per zone (default _ZONE_PENALTIES).
    """

    def __init__(
        self,
        zones: dict[str, tuple[float, float]] | None = None,
        penalties: dict[str, float] | None = None,
    ) -> None:
        self._zones = zones or FIBONACCI_ZONES
        self._penalties = penalties or _ZONE_PENALTIES
        # Sort zones by lower bound descending for classification
        self._sorted_zones = sorted(
            self._zones.items(),
            key=lambda x: x[1][0],
            reverse=True,
        )

    def classify(self, value: float) -> FibonacciZone:
        """Classify a value into its Fibonacci zone.

        Args:
            value: A metric value, typically in [0, 1].

        Returns:
            FibonacciZone with the classification result.
        """
        clamped = max(0.0, min(1.0, value))

        for zone_name, (lower, upper) in self._sorted_zones:
            if clamped >= lower:
                penalty = self._penalties.get(zone_name, 1.0)
                return FibonacciZone(
                    zone=zone_name,
                    value=clamped,
                    penalty=penalty,
                    penalized_value=clamped * penalty,
                )

        # Fallback: critical zone
        penalty = self._penalties.get("critical", 0.30)
        return FibonacciZone(
            zone="critical",
            value=clamped,
            penalty=penalty,
            penalized_value=clamped * penalty,
        )

    def __repr__(self) -> str:
        return f"SoftConstraint(zones={list(self._zones.keys())})"


def function_size_score(avg_lines: float, target: int = FUNCTION_SIZE_TARGET) -> float:
    """Convert an average function line count to a [0, 1] quality score.

    From LUNA_CONSCIOUSNESS_FRAMEWORK.md §II (Métrique 5):
        deviation = |avg_lines - target| / target
        score = max(0, 1 - deviation)

    Symmetric: penalizes both too-long AND too-short functions.
    At target (17): score = 1.0
    At 2*target (34): score = 0.0
    At 0: score = 0.0

    Args:
        avg_lines: Average function size in lines.
        target: Target function size (default FUNCTION_SIZE_TARGET = 17).

    Returns:
        A score in [0, 1] where 1.0 is ideal.
    """
    if target <= 0:
        return 0.0
    deviation = abs(avg_lines - target) / target
    return max(0.0, 1.0 - deviation)
