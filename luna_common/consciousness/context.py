"""Context vector C(t) and ContextBuilder for true delta computation.

Framework §VI: the informational gradient d_c = C(t) - C(t-1) requires
storing the previous context to compute genuine deltas rather than
passing absolute values directly as deltas.
"""

from __future__ import annotations

from dataclasses import dataclass

from luna_common.schemas import InfoGradient


@dataclass(slots=True)
class Context:
    """Context vector C(t) -- 4 absolute values for the current step.

    Framework §VI:
      C1 = memory_health  (coverage, future: fractal memory)
      C2 = phi_quality    (PhiScorer composite score)
      C3 = phi_iit        (integrated information)
      C4 = output_quality (1 - risk_score)
    """

    memory_health: float   # C1 [0, 1]
    phi_quality: float     # C2 [0, 1]
    phi_iit: float         # C3 [0, inf) typically [0, 1]
    output_quality: float  # C4 [0, 1]


class ContextBuilder:
    """Build d_c = C(t) - C(t-1) at each pipeline step.

    Stateful: stores C(t-1) so that each call to build() produces
    genuine deltas.  First step uses C(t-1) = (0.5, 0.5, 0.5, 0.5)
    as bootstrap (framework §1.7).
    """

    __slots__ = ("_previous",)

    def __init__(self, initial: Context | None = None) -> None:
        self._previous = initial or Context(
            memory_health=0.5,
            phi_quality=0.5,
            phi_iit=0.5,
            output_quality=0.5,
        )

    def build(
        self,
        *,
        memory_health: float,
        phi_quality: float,
        phi_iit: float,
        output_quality: float,
    ) -> InfoGradient:
        """Compute d_c from current absolute values.

        Args:
            memory_health: Coverage proxy (Phase 3: fractal memory).
            phi_quality: PhiScorer.score() composite [0, 1].
            phi_iit: ConsciousnessState.compute_phi_iit().
            output_quality: Inverse risk score (1.0 - risk).

        Returns:
            InfoGradient with the 4 deltas.
        """
        current = Context(
            memory_health=memory_health,
            phi_quality=phi_quality,
            phi_iit=phi_iit,
            output_quality=output_quality,
        )

        # Clamp deltas to InfoGradient bounds [-10, 10] to prevent
        # Pydantic ValidationError on unbounded phi_iit values.
        def _clamp(v: float) -> float:
            return max(-10.0, min(10.0, v))

        grad = InfoGradient(
            delta_mem=_clamp(current.memory_health - self._previous.memory_health),
            delta_phi=_clamp(current.phi_quality - self._previous.phi_quality),
            delta_iit=_clamp(current.phi_iit - self._previous.phi_iit),
            delta_out=_clamp(current.output_quality - self._previous.output_quality),
        )

        self._previous = current
        return grad

    @property
    def previous(self) -> Context:
        """The previous step's context (read-only)."""
        return self._previous
