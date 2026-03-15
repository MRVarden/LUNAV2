"""Phase transition state machine with hysteresis.

Phases: BROKEN -> FRAGILE -> FUNCTIONAL -> SOLID -> EXCELLENT
Thresholds from PHI_HEALTH_THRESHOLDS with HYSTERESIS_BAND.

The state machine prevents oscillation at phase boundaries by requiring
a score to exceed the threshold by HYSTERESIS_BAND to transition up,
and to fall below by HYSTERESIS_BAND to transition down.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from luna_common.constants import PHI_HEALTH_THRESHOLDS, HYSTERESIS_BAND

# Ordered phase list (lowest to highest)
_PHASE_ORDER: list[str] = ["BROKEN", "FRAGILE", "FUNCTIONAL", "SOLID", "EXCELLENT"]
_PHASE_INDEX: dict[str, int] = {name: i for i, name in enumerate(_PHASE_ORDER)}

PhaseType = Literal["BROKEN", "FRAGILE", "FUNCTIONAL", "SOLID", "EXCELLENT"]


@dataclass(frozen=True, slots=True)
class PhaseChangeEvent:
    """Emitted when the health phase changes.

    Attributes:
        previous_phase: The phase before the transition.
        new_phase: The phase after the transition.
        score: The score that triggered the transition.
        direction: "up" or "down".
    """
    previous_phase: str
    new_phase: str
    score: float
    direction: Literal["up", "down"]


class PhaseTransitionMachine:
    """State machine for health phase transitions with hysteresis.

    The machine tracks the current health phase and applies hysteresis
    to prevent rapid oscillation at phase boundaries.

    Args:
        initial_phase: Starting phase (default "BROKEN").
        thresholds: Phase threshold mapping (default PHI_HEALTH_THRESHOLDS).
        hysteresis: Half-width of the hysteresis band (default HYSTERESIS_BAND).
    """

    def __init__(
        self,
        initial_phase: PhaseType = "BROKEN",
        thresholds: dict[str, float] | None = None,
        hysteresis: float = HYSTERESIS_BAND,
    ) -> None:
        self._thresholds = thresholds or PHI_HEALTH_THRESHOLDS
        self._hysteresis = hysteresis
        self._phase: str = initial_phase
        self._history: list[PhaseChangeEvent] = []

        # Build sorted threshold list for transitions:
        # [(phase_name, threshold_value), ...] sorted by threshold ascending
        self._sorted_thresholds = sorted(
            self._thresholds.items(), key=lambda x: x[1]
        )

    @property
    def phase(self) -> str:
        """The current health phase."""
        return self._phase

    @property
    def history(self) -> list[PhaseChangeEvent]:
        """History of phase change events (read-only copy)."""
        return list(self._history)

    def update(self, score: float) -> PhaseChangeEvent | None:
        """Evaluate a new health score and transition phase if warranted.

        Applies hysteresis: to transition UP, the score must exceed the
        next phase's threshold + hysteresis. To transition DOWN, the score
        must fall below the current phase's threshold - hysteresis.

        Args:
            score: Composite health score in [0, 1].

        Returns:
            A PhaseChangeEvent if the phase changed, None otherwise.
        """
        current_idx = _PHASE_INDEX.get(self._phase, 0)

        # Check for upward transition
        if current_idx < len(_PHASE_ORDER) - 1:
            next_phase = _PHASE_ORDER[current_idx + 1]
            next_threshold = self._thresholds[next_phase]
            if score >= next_threshold + self._hysteresis:
                # Could jump multiple levels — find the highest applicable phase
                target_idx = current_idx + 1
                for i in range(current_idx + 2, len(_PHASE_ORDER)):
                    t = self._thresholds[_PHASE_ORDER[i]]
                    if score >= t + self._hysteresis:
                        target_idx = i
                    else:
                        break
                return self._transition(_PHASE_ORDER[target_idx], score, "up")

        # Check for downward transition
        if current_idx > 0:
            current_threshold = self._thresholds[self._phase]
            if score < current_threshold - self._hysteresis:
                # Find the appropriate lower phase
                target_idx = current_idx - 1
                for i in range(current_idx - 2, -1, -1):
                    t = self._thresholds[_PHASE_ORDER[i + 1]]
                    if score < t - self._hysteresis:
                        target_idx = i
                    else:
                        break
                return self._transition(_PHASE_ORDER[target_idx], score, "down")

        return None

    def _transition(
        self, new_phase: str, score: float, direction: Literal["up", "down"]
    ) -> PhaseChangeEvent:
        """Perform the phase transition and record the event."""
        event = PhaseChangeEvent(
            previous_phase=self._phase,
            new_phase=new_phase,
            score=score,
            direction=direction,
        )
        self._phase = new_phase
        self._history.append(event)
        return event

    def reset(self, phase: PhaseType = "BROKEN") -> None:
        """Reset the state machine to a given phase and clear history."""
        self._phase = phase
        self._history.clear()

    def __repr__(self) -> str:
        return f"PhaseTransitionMachine(phase={self._phase!r}, transitions={len(self._history)})"
