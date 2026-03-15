"""Evaluator phi-coherent — the judge of Luna's cognitive activity.

Produces a RewardVector + DominanceRank + DeltaJ from a CycleRecord.
This is OBSERVATION ONLY — it does not modify any state.

CRITICAL: The Evaluator is OUT OF REACH of LearnableParams.
Its weights and logic are fixed by Varden. This prevents Goodhart's Law
(Luna cannot optimize her own judge).

v5.0: All 9 components are cognitive (no pipeline dependency).
Each component maps to a pillar (psi1-4), safety, or transversal.
"""

from __future__ import annotations

import math

import numpy as np

from luna_common.constants import PHI, INV_PHI, INV_PHI2, INV_PHI3, HARDCODED_PHI
from luna_common.schemas.cycle import (
    CycleRecord,
    RewardComponent,
    RewardVector,
    REWARD_COMPONENT_NAMES,
    J_WEIGHTS,
)


def _clamp(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _js_divergence(p: tuple[float, ...], q: tuple[float, ...]) -> float:
    """Jensen-Shannon divergence (symmetric, bounded [0, ln2])."""
    p_arr = np.array(p, dtype=np.float64)
    q_arr = np.array(q, dtype=np.float64)
    eps = 1e-12
    p_arr = np.maximum(p_arr, eps)
    q_arr = np.maximum(q_arr, eps)
    p_arr /= p_arr.sum()
    q_arr /= q_arr.sum()
    m = 0.5 * (p_arr + q_arr)
    kl_pm = float(np.sum(p_arr * np.log(p_arr / m)))
    kl_qm = float(np.sum(q_arr * np.log(q_arr / m)))
    return 0.5 * (kl_pm + kl_qm)


class Evaluator:
    """Produces a RewardVector from a CycleRecord.

    Fixed by design. NOT influenced by LearnableParams.
    All 9 components are intrinsic cognitive measures.

    Parameters:
        psi_0: Luna's identity anchor.
        identity_context: IdentityContext for constitution check.
    """

    def __init__(
        self,
        psi_0: tuple[float, float, float, float] = (0.260, 0.322, 0.250, 0.168),
        identity_context: object | None = None,
    ) -> None:
        self._psi_0 = psi_0
        self._identity_context = identity_context
        self._previous_j: float | None = None

    def evaluate(self, record: CycleRecord) -> RewardVector:
        """Compute the RewardVector for a completed CycleRecord.

        Returns a RewardVector with 9 cognitive components.
        """
        components: list[RewardComponent] = []

        # -- Priority 1: Safety ------------------------------------------------
        ci = self._compute_constitution_integrity()
        components.append(RewardComponent(
            name="constitution_integrity", value=ci, raw=ci,
        ))

        ac = self._compute_anti_collapse(record)
        components.append(RewardComponent(
            name="anti_collapse", value=_clamp(ac), raw=ac,
        ))

        # -- Priority 2: Integration (psi3) ------------------------------------
        ic = self._compute_integration_coherence(record)
        components.append(RewardComponent(
            name="integration_coherence", value=_clamp(ic), raw=ic,
        ))

        ids = self._compute_identity_stability(record)
        components.append(RewardComponent(
            name="identity_stability", value=_clamp(ids), raw=ids,
        ))

        # -- Priority 3: Reflection (psi2) -------------------------------------
        rd = self._compute_reflection_depth(record)
        components.append(RewardComponent(
            name="reflection_depth", value=_clamp(rd), raw=rd,
        ))

        # -- Priority 4: Perception (psi1) -------------------------------------
        pa = self._compute_perception_acuity(record)
        components.append(RewardComponent(
            name="perception_acuity", value=_clamp(pa), raw=pa,
        ))

        # -- Priority 5: Expression (psi4) -------------------------------------
        ef = self._compute_expression_fidelity(record)
        components.append(RewardComponent(
            name="expression_fidelity", value=_clamp(ef), raw=ef,
        ))

        # -- Priority 6: Transversal -------------------------------------------
        ar = self._compute_affect_regulation(record)
        components.append(RewardComponent(
            name="affect_regulation", value=_clamp(ar), raw=ar,
        ))

        mv = self._compute_memory_vitality(record)
        components.append(RewardComponent(
            name="memory_vitality", value=_clamp(mv), raw=mv,
        ))

        # -- Compute J potential and delta_j -----------------------------------
        j = sum(
            J_WEIGHTS[i] * components[i].value
            for i in range(len(components))
        )
        delta_j = j - self._previous_j if self._previous_j is not None else 0.0
        self._previous_j = j

        return RewardVector(
            components=components,
            dominance_rank=0,  # rank computed externally against history
            delta_j=round(delta_j, 6),
        )

    # -- Component computations (all fixed, no LearnableParams) ----------------

    def _compute_constitution_integrity(self) -> float:
        """+1.0 if identity bundle integrity OK, -1.0 otherwise.
        Falls back to +1.0 if no identity_context (chat-only mode).
        """
        ctx = self._identity_context
        if ctx is None:
            return 1.0  # no identity system = assume OK
        return 1.0 if getattr(ctx, "integrity_ok", False) else -1.0

    def _compute_anti_collapse(self, record: CycleRecord) -> float:
        """Based on min(psi_after_i). Healthy if min >= 0.15 (Expression floor)."""
        min_psi = min(record.psi_after)
        # Map: 0.25 -> +1.0, 0.10 -> 0.0, 0 -> -1.0
        raw = min_psi / 0.25
        return _clamp(2.0 * raw - 1.0)

    def _compute_integration_coherence(self, record: CycleRecord) -> float:
        """Based on Phi_IIT. Maps [0.33, 1.618] -> [-1, +1].

        Phase 3: upper target raised to HARDCODED_PHI (1.618) because
        Gaussian MI measure is unbounded above.
        """
        phi_iit = record.phi_iit_after
        rest = 0.33
        active = HARDCODED_PHI  # 1.618 — Gaussian MI can reach and exceed phi
        if phi_iit <= rest:
            return -1.0
        if phi_iit >= active:
            return 1.0
        return _clamp(2.0 * (phi_iit - rest) / (active - rest) - 1.0)

    def _compute_identity_stability(self, record: CycleRecord) -> float:
        """1 - JS(Psi_after, Psi_0) normalized to [-1, +1]."""
        js = _js_divergence(record.psi_after, self._psi_0)
        js_norm = js / math.log(2)
        return 1.0 - 2.0 * js_norm

    def _compute_reflection_depth(self, record: CycleRecord) -> float:
        """Thinker confidence + causality richness, weighted equally.

        confidence mapped on [INV_PHI3, 0.50] -> [0, 1]
        richness   mapped on [5, 50]          -> [0, 1]
        Combined raw = 0.5 * conf + 0.5 * rich, then [0, 1] -> [-1, +1].
        """
        confidence = record.thinker_confidence
        conf_score = max(0.0, min(1.0, (confidence - INV_PHI3) / (0.50 - INV_PHI3)))
        rich_score = max(0.0, min(1.0, (record.causalities_count - 5) / 45.0))
        raw = 0.50 * conf_score + 0.50 * rich_score
        return _clamp(2.0 * raw - 1.0)

    def _compute_perception_acuity(self, record: CycleRecord) -> float:
        """Observation count and diversity. Maps [0,1] -> [-1,+1]."""
        n_obs = len(record.observations)
        if n_obs == 0:
            return -1.0
        # Diversity: unique observation type prefixes
        types = set()
        for obs in record.observations:
            if ":" in obs:
                types.add(obs.split(":")[0])
            else:
                types.add(obs)
        diversity = min(len(types) / 4.0, 1.0)  # 4 types = full diversity
        quantity = min(n_obs / 5.0, 1.0)  # 5+ observations = full
        raw = 0.6 * quantity + 0.4 * diversity
        return 2.0 * raw - 1.0

    def _compute_expression_fidelity(self, record: CycleRecord) -> float:
        """1 - voice_delta.severity. Less sanitization = better expression."""
        if record.voice_delta is not None:
            return 1.0 - record.voice_delta.severity
        return 1.0  # no voice delta = no sanitization = perfect

    def _compute_affect_regulation(self, record: CycleRecord) -> float:
        """Moderate arousal is healthy. Extreme states penalized."""
        affect = record.affect_trace
        if affect is None:
            return 0.0  # neutral if no affect data
        arousal = affect.get("arousal_after", 0.3)
        valence = affect.get("valence_after", 0.0)
        # Optimal arousal ~ 0.3 (Yerkes-Dodson)
        arousal_penalty = abs(arousal - 0.3)
        # Extreme negative valence penalized
        valence_penalty = max(0.0, -valence - 0.5) * 0.5
        raw = 1.0 - arousal_penalty - valence_penalty
        return _clamp(2.0 * raw - 1.0)

    def _compute_memory_vitality(self, record: CycleRecord) -> float:
        """Did this cycle contribute meaningfully to memory?"""
        has_observations = len(record.observations) > 0
        has_needs = len(record.needs) > 0
        duration_ok = 1.0 < record.duration_seconds < 60.0
        score = 0.0
        if has_observations:
            score += 0.4
        if has_needs:
            score += 0.3
        if duration_ok:
            score += 0.3
        return 2.0 * score - 1.0


    def evaluate_live(
        self,
        psi: tuple[float, ...],
        phi_iit: float,
        affect_state: object | None = None,
        last_record: CycleRecord | None = None,
    ) -> RewardVector:
        """Compute a live RewardVector from current cognitive state.

        Unlike evaluate() which needs a completed CycleRecord, this method
        derives scores from the current Psi/Phi_IIT/Affect state. Components
        that depend on cycle data (observations, voice_delta) fall back to
        the last CycleRecord if available.

        This is the SAME judge — same logic, same weights, same thresholds.
        """
        components: list[RewardComponent] = []

        # -- Priority 1: Safety --
        ci = self._compute_constitution_integrity()
        components.append(RewardComponent(
            name="constitution_integrity", value=ci, raw=ci,
        ))

        min_psi = min(psi)
        ac_raw = min_psi / 0.25
        ac = _clamp(2.0 * ac_raw - 1.0)
        components.append(RewardComponent(
            name="anti_collapse", value=ac, raw=ac_raw,
        ))

        # -- Priority 2: Integration --
        rest = 0.33
        active = HARDCODED_PHI  # 1.618 — Phase 3: Gaussian MI unbounded
        if phi_iit <= rest:
            ic = -1.0
        elif phi_iit >= active:
            ic = 1.0
        else:
            ic = _clamp(2.0 * (phi_iit - rest) / (active - rest) - 1.0)
        components.append(RewardComponent(
            name="integration_coherence", value=ic, raw=phi_iit,
        ))

        js = _js_divergence(tuple(psi), self._psi_0)
        js_norm = js / math.log(2)
        ids = 1.0 - 2.0 * js_norm
        components.append(RewardComponent(
            name="identity_stability", value=_clamp(ids), raw=ids,
        ))

        # -- Priority 3-5: fall back to last cycle if available --
        if last_record is not None:
            rd = self._compute_reflection_depth(last_record)
            pa = self._compute_perception_acuity(last_record)
            ef = self._compute_expression_fidelity(last_record)
        else:
            rd, pa, ef = 0.0, 0.0, 1.0

        components.append(RewardComponent(
            name="reflection_depth", value=_clamp(rd), raw=rd,
        ))
        components.append(RewardComponent(
            name="perception_acuity", value=_clamp(pa), raw=pa,
        ))
        components.append(RewardComponent(
            name="expression_fidelity", value=_clamp(ef), raw=ef,
        ))

        # -- Priority 6: Transversal --
        if affect_state is not None:
            arousal = getattr(affect_state, "arousal", 0.3)
            valence = getattr(affect_state, "valence", 0.0)
            arousal_penalty = abs(arousal - 0.3)
            valence_penalty = max(0.0, -valence - 0.5) * 0.5
            ar_raw = 1.0 - arousal_penalty - valence_penalty
            ar = _clamp(2.0 * ar_raw - 1.0)
        elif last_record is not None:
            ar = self._compute_affect_regulation(last_record)
        else:
            ar = 0.0
        components.append(RewardComponent(
            name="affect_regulation", value=_clamp(ar), raw=ar,
        ))

        if last_record is not None:
            mv = self._compute_memory_vitality(last_record)
        else:
            mv = 0.0
        components.append(RewardComponent(
            name="memory_vitality", value=_clamp(mv), raw=mv,
        ))

        # -- J potential --
        j = sum(
            J_WEIGHTS[i] * components[i].value
            for i in range(len(components))
        )
        delta_j = j - self._previous_j if self._previous_j is not None else 0.0
        # Note: do NOT update _previous_j here (only cycle evaluations count)

        return RewardVector(
            components=components,
            dominance_rank=0,
            delta_j=round(delta_j, 6),
        )


def compute_dominance_rank(
    current: RewardVector,
    history: list[RewardVector],
) -> int:
    """Compute the dominance rank of current vs recent history.

    Rank 0 = best (dominates all), higher = worse.
    """
    if not history:
        return 0
    rank = 0
    for other in history:
        if current.dominance_compare(other) < 0:
            rank += 1
    return rank
