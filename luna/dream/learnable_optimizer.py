"""Learnable Optimizer — CEM-based param tuning during Dream.

Cross-Entropy Method (CEM) optimizes LearnableParams by replaying
recent CycleRecords with counterfactual param vectors, evaluating
each with the Evaluator, and selecting the elite performers.

This runs ONLY during Dream (offline). Never during interactive mode.

CEM config (all phi-derived where possible):
  - Population: 30
  - Elite fraction: 1/PHI^2 ~ 0.382 -> top 11
  - Generations: 10
  - Replay cycles per candidate: 5
  - Noise decay: 0.95 per generation
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import numpy as np

from luna.consciousness.evaluator import Evaluator, compute_dominance_rank
from luna.consciousness.learnable_params import (
    PARAM_COUNT,
    PARAM_SPECS,
    LearnableParams,
)
from luna_common.constants import INV_PHI2, INV_PHI3, PHI
from luna_common.schemas.cycle import CycleRecord, RewardComponent, RewardVector

log = logging.getLogger(__name__)

# ── CEM hyperparameters (phi-derived) ────────────────────────────────────────

_POPULATION: int = 30
_ELITE_FRACTION: float = INV_PHI2  # ~0.382 -> top 11
_ELITE_COUNT: int = max(2, int(_POPULATION * _ELITE_FRACTION))
_GENERATIONS: int = 10
_REPLAY_K: int = 5          # cycles to replay per candidate
_NOISE_INIT: float = 0.1    # initial std dev (relative to param range)
_NOISE_DECAY: float = 0.95  # decay per generation
_PSI0_MAX_DELTA: float = 0.02  # max Psi_0 shift per dream session


# ══════════════════════════════════════════════════════════════════════════════
#  DATA MODEL
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class LearningTrace:
    """Records what the CEM learned during a dream session."""

    generations_run: int = 0
    best_j_by_generation: list[float] = field(default_factory=list)
    initial_j: float = 0.0
    final_j: float = 0.0
    params_before: dict[str, float] = field(default_factory=dict)
    params_after: dict[str, float] = field(default_factory=dict)
    params_delta: dict[str, float] = field(default_factory=dict)
    psi0_delta: tuple[float, ...] = ()
    cycles_replayed: int = 0
    duration_seconds: float = 0.0

    def summary(self) -> str:
        """Human-readable summary of what was learned."""
        if not self.params_delta:
            return "CEM: no improvement found"
        changed = {k: v for k, v in self.params_delta.items() if abs(v) > 1e-6}
        if not changed:
            return "CEM: params unchanged (already optimal for recent history)"
        top = sorted(changed.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
        parts = [f"{k}: {v:+.4f}" for k, v in top]
        return f"CEM: J {self.initial_j:.4f} -> {self.final_j:.4f} | {', '.join(parts)}"


# ══════════════════════════════════════════════════════════════════════════════
#  COUNTERFACTUAL REPLAY
# ══════════════════════════════════════════════════════════════════════════════

def counterfactual_replay(
    record: CycleRecord,
    params: LearnableParams,
    evaluator: Evaluator,
) -> RewardVector:
    """Replay a CycleRecord with different params, return estimated reward.

    Modifies param-dependent fields in the record:
    - scope_budget from max_scope_files / max_scope_lines
    - mode from mode_prior_* (estimated)

    Then evaluates with the Evaluator and applies a behavioral alignment
    bonus that estimates how the params would have affected the outcome.
    The Evaluator itself is NOT modified (anti-Goodhart preserved).
    """
    # Build modified record with new param-dependent fields
    new_scope = {
        "max_files": params.get("max_scope_files"),
        "max_lines": params.get("max_scope_lines"),
    }

    # Estimate duration adjustment from scope change
    old_max_lines = record.scope_budget.get("max_lines", 500.0)
    new_max_lines = params.get("max_scope_lines")
    scope_ratio = new_max_lines / max(old_max_lines, 1.0)
    adjusted_duration = record.duration_seconds * scope_ratio

    # Build counterfactual record
    cf_record = CycleRecord(
        cycle_id=record.cycle_id,
        timestamp=record.timestamp,
        context_digest=record.context_digest,
        psi_before=record.psi_before,
        psi_after=record.psi_after,
        phi_before=record.phi_before,
        phi_after=record.phi_after,
        phi_iit_before=record.phi_iit_before,
        phi_iit_after=record.phi_iit_after,
        emergent_phi=record.emergent_phi,
        phase_before=record.phase_before,
        phase_after=record.phase_after,
        observations=record.observations,
        causalities_count=record.causalities_count,
        needs=record.needs,
        thinker_confidence=record.thinker_confidence,
        intent=record.intent,
        mode=record.mode,
        focus=record.focus,
        depth=record.depth,
        scope_budget=new_scope,
        initiative_flags=record.initiative_flags,
        alternatives_considered=record.alternatives_considered,
        telemetry_timeline=[],  # stripped for performance
        telemetry_summary=record.telemetry_summary,
        pipeline_result=record.pipeline_result,
        voice_delta=record.voice_delta,
        reward=None,  # will be recomputed
        learnable_params_before=record.learnable_params_before,
        learnable_params_after=params.snapshot(),
        autonomy_level=record.autonomy_level,
        rollback_occurred=record.rollback_occurred,
        duration_seconds=max(0.1, adjusted_duration),
    )

    rv = evaluator.evaluate(cf_record)

    # ── Behavioral alignment bonus ──────────────────────────────────
    # Estimate how this param set would have performed given observed
    # conditions. This creates an optimization landscape for CEM without
    # modifying the Evaluator (anti-Goodhart preserved).
    bonus = _param_alignment_bonus(record, params)

    if abs(bonus) > 1e-9:
        modulated = []
        for comp in rv.components:
            modulated.append(RewardComponent(
                name=comp.name,
                value=max(-1.0, min(1.0, comp.value + bonus)),
                raw=comp.raw,
            ))
        rv = RewardVector(
            components=modulated,
            dominance_rank=rv.dominance_rank,
            delta_j=rv.delta_j,
        )

    return rv


def _param_alignment_bonus(record: CycleRecord, params: LearnableParams) -> float:
    """Compute a small bonus/penalty based on param-to-situation alignment.

    This estimates how well the candidate params would have BEHAVIORALLY
    matched the situation observed in this cycle. It does NOT modify the
    Evaluator's judgment --- it adds a BEHAVIORAL signal to the CF replay.

    Bounded to [-0.05, +0.05] to keep the base evaluation dominant.
    """
    bonus = 0.0
    obs_set = set(record.observations)

    # 1. Regression aversion: reward high aversion when phi dropped
    phi_dropped = record.phi_iit_after < record.phi_iit_before
    reg_aversion = params.get("regression_aversion")
    if phi_dropped:
        bonus += reg_aversion * 0.02  # high aversion = good when phi drops
    else:
        bonus += (1.0 - reg_aversion) * 0.01  # low aversion OK when stable

    # 2. Exploration rate: reward exploration when novel observations present
    has_factory = any(o.startswith("factory:") for o in obs_set)
    expl_rate = params.get("exploration_rate")
    if has_factory:
        bonus += expl_rate * 0.03  # novel observation = exploration paid off
    else:
        bonus -= expl_rate * 0.01  # no novelty = exploration cost

    # 3. Need weight expression: reward when weak_Expression is present
    if "weak_Expression" in obs_set:
        expr_weight = params.get("need_weight_expression")
        bonus += expr_weight * 0.02  # prioritizing expression when needed

    # 4. Mode prior alignment: reward matching mode prior to actual mode
    actual_mode = record.mode
    if actual_mode:
        mode_key = f"mode_prior_{actual_mode}"
        try:
            prior = params.get(mode_key)
            bonus += prior * 0.02  # high prior for actual mode = good alignment
        except KeyError:
            pass

    # 5. Veto aversion: penalize low veto aversion when phi is critical
    if "phi_critical" in obs_set:
        veto_av = params.get("veto_aversion")
        bonus += veto_av * 0.02  # high caution in critical state

    # Clamp to prevent dominating the base evaluation
    return max(-0.05, min(0.05, bonus))


# ══════════════════════════════════════════════════════════════════════════════
#  CEM OPTIMIZER
# ══════════════════════════════════════════════════════════════════════════════

class CEMOptimizer:
    """Cross-Entropy Method for LearnableParams optimization.

    Runs during Dream only. Uses counterfactual replay of recent
    CycleRecords to estimate reward for different param vectors.
    """

    def __init__(
        self,
        evaluator: Evaluator,
        *,
        population: int = _POPULATION,
        elite_count: int = _ELITE_COUNT,
        generations: int = _GENERATIONS,
        replay_k: int = _REPLAY_K,
        noise_init: float = _NOISE_INIT,
        noise_decay: float = _NOISE_DECAY,
    ) -> None:
        self._evaluator = evaluator
        self._population = population
        self._elite_count = min(elite_count, population)
        self._generations = generations
        self._replay_k = replay_k
        self._noise_init = noise_init
        self._noise_decay = noise_decay

    def optimize(
        self,
        current_params: LearnableParams,
        recent_cycles: list[CycleRecord],
    ) -> tuple[LearnableParams, LearningTrace]:
        """Run CEM optimization on recent_cycles.

        Args:
            current_params: Starting params (center of initial distribution).
            recent_cycles: Recent CycleRecords to replay (max replay_k used).

        Returns:
            (optimized_params, learning_trace)
        """
        start = time.monotonic()
        trace = LearningTrace(
            params_before=current_params.snapshot(),
        )

        if not recent_cycles:
            log.info("CEM: no cycles to replay, skipping")
            trace.params_after = current_params.snapshot()
            return current_params, trace

        # Select replay cycles (most recent K)
        replay_cycles = recent_cycles[-self._replay_k:]
        trace.cycles_replayed = len(replay_cycles)

        # Initialize distribution: mean = current params, std = noise * range
        mean = np.array(current_params.as_vector(), dtype=np.float64)
        ranges = np.array(
            [spec.hi - spec.lo for spec in PARAM_SPECS], dtype=np.float64,
        )
        std = ranges * self._noise_init

        # Evaluate current params as baseline
        trace.initial_j = self._evaluate_candidate(current_params, replay_cycles)

        best_j = trace.initial_j
        best_vector = mean.copy()

        for gen in range(self._generations):
            # Generate population
            candidates = self._sample_population(mean, std)

            # Evaluate each candidate
            scores: list[tuple[float, np.ndarray]] = []
            for vec in candidates:
                params = self._vector_to_params(vec)
                j = self._evaluate_candidate(params, replay_cycles)
                scores.append((j, vec))

            # Sort by J descending (higher is better)
            scores.sort(key=lambda x: x[0], reverse=True)

            # Select elite
            elite = scores[:self._elite_count]
            elite_vectors = np.array([v for _, v in elite])
            elite_j = elite[0][0]

            # Track best
            if elite_j > best_j:
                best_j = elite_j
                best_vector = elite[0][1].copy()

            trace.best_j_by_generation.append(elite_j)

            # Update distribution from elite
            mean = np.mean(elite_vectors, axis=0)
            std = np.std(elite_vectors, axis=0) + 1e-8  # prevent collapse

            # Decay noise
            std *= self._noise_decay

            log.debug(
                "CEM gen %d/%d: elite_j=%.4f best_j=%.4f",
                gen + 1, self._generations, elite_j, best_j,
            )

        # Build optimized params
        optimized = self._vector_to_params(best_vector)
        trace.generations_run = self._generations
        trace.final_j = best_j
        trace.params_after = optimized.snapshot()
        trace.params_delta = optimized.delta(current_params)
        trace.duration_seconds = time.monotonic() - start

        log.info("CEM: %s", trace.summary())

        return optimized, trace

    def _sample_population(
        self, mean: np.ndarray, std: np.ndarray,
    ) -> list[np.ndarray]:
        """Sample population vectors, clamped to param bounds."""
        candidates: list[np.ndarray] = []
        rng = np.random.default_rng()

        for _ in range(self._population):
            vec = rng.normal(mean, std)
            # Clamp to bounds
            for i, spec in enumerate(PARAM_SPECS):
                vec[i] = max(spec.lo, min(spec.hi, vec[i]))
            candidates.append(vec)

        return candidates

    def _vector_to_params(self, vec: np.ndarray) -> LearnableParams:
        """Convert a vector to LearnableParams."""
        params = LearnableParams()
        params.from_vector(vec.tolist())
        return params

    def _evaluate_candidate(
        self,
        params: LearnableParams,
        cycles: list[CycleRecord],
    ) -> float:
        """Evaluate a param candidate against replay cycles.

        Returns the mean J potential across replayed cycles.
        Each replay uses a fresh Evaluator to avoid state leaks.
        """
        if not cycles:
            return 0.0

        total_j = 0.0
        evaluator = Evaluator(psi_0=self._evaluator._psi_0)

        for record in cycles:
            rv = counterfactual_replay(record, params, evaluator)
            # J is the weighted sum of components
            j = sum(
                w * c.value
                for w, c in zip(
                    _j_weights_list(), rv.components,
                )
            )
            total_j += j

        return total_j / len(cycles)


def _j_weights_list() -> list[float]:
    """Get J_WEIGHTS as a list (indexed by component position)."""
    from luna_common.schemas.cycle import J_WEIGHTS
    return list(J_WEIGHTS)


# ══════════════════════════════════════════════════════════════════════════════
#  PSI_0 CONSOLIDATION (protected)
# ══════════════════════════════════════════════════════════════════════════════

def consolidate_psi0(
    current_psi0: tuple[float, float, float, float],
    recent_cycles: list[CycleRecord],
    max_delta: float = _PSI0_MAX_DELTA,
    psi0_delta_history: list[tuple[float, ...]] | None = None,
) -> tuple[tuple[float, float, float, float], tuple[float, ...]]:
    """Adjust Psi_0 based on lived experience (CycleRecords).

    Rules:
    - Movement capped at max_delta per component per dream
    - Cumulative cap: ±INV_PHI3 (0.236) per component over sliding window
    - Soft floor: resistance increases as a component approaches INV_PHI3
    - Based on mean psi_after across cycles (what Luna naturally tends toward)
    - Result re-normalized to simplex (sum=1)
    - Returns (new_psi0, delta_applied)

    This is OUT OF REACH of LearnableParams. The judge (Evaluator)
    and the identity anchor (Psi_0) are both protected.
    """
    if not recent_cycles:
        return current_psi0, (0.0, 0.0, 0.0, 0.0)

    # Mean psi_after across recent cycles = natural tendency
    psi_sum = np.zeros(4, dtype=np.float64)
    for record in recent_cycles:
        psi_sum += np.array(record.psi_after, dtype=np.float64)
    psi_mean = psi_sum / len(recent_cycles)

    current = np.array(current_psi0, dtype=np.float64)

    # Compute desired delta (toward natural tendency)
    raw_delta = psi_mean - current

    # Clamp each component to max_delta (per-dream cap)
    clamped_delta = np.clip(raw_delta, -max_delta, max_delta)

    # ── Cumulative cap (sliding window) ──────────────────────────────
    # Prevent monotone drift: total cumulative shift per component
    # cannot exceed ±INV_PHI3 over the history window.
    if psi0_delta_history:
        cumulative = np.zeros(4, dtype=np.float64)
        for past_delta in psi0_delta_history:
            cumulative += np.array(past_delta[:4], dtype=np.float64)
        # Warn if any component exceeds 50% of budget
        from luna_common.constants import COMP_NAMES
        for i in range(4):
            if abs(cumulative[i]) > INV_PHI3 * 0.5:
                log.warning(
                    "Psi0 drift alert: %s cumulative=%.3f (budget=±%.3f, %.0f%% used)",
                    COMP_NAMES[i], cumulative[i], INV_PHI3,
                    abs(cumulative[i]) / INV_PHI3 * 100,
                )
        # Available budget = INV_PHI3 - |cumulative|, signed
        for i in range(4):
            headroom_pos = max(0.0, INV_PHI3 - cumulative[i])
            headroom_neg = max(0.0, INV_PHI3 + cumulative[i])
            clamped_delta[i] = np.clip(
                clamped_delta[i], -headroom_neg, headroom_pos,
            )

    # ── Soft floor (resistance) ──────────────────────────────────────
    # When a component approaches INV_PHI3 from above, apply increasing
    # resistance to prevent extinction. Resistance = exp(-k*(value - floor))
    # when value < floor + margin. k=PHI (golden ratio) for smooth curve.
    _FLOOR = INV_PHI3        # 0.236 — minimum healthy component
    _MARGIN = INV_PHI2       # 0.382 — resistance starts here
    _K = PHI                 # 1.618 — steepness
    projected = current + clamped_delta
    for i in range(4):
        if clamped_delta[i] < 0 and projected[i] < _FLOOR + _MARGIN:
            # How far into the danger zone?
            depth = max(0.0, (_FLOOR + _MARGIN) - projected[i]) / _MARGIN
            resistance = float(np.exp(-_K * depth))
            clamped_delta[i] *= resistance

    # Apply
    new_psi0 = current + clamped_delta

    # Re-normalize to simplex (sum=1, all >= 0)
    new_psi0 = np.maximum(new_psi0, 0.01)  # floor to avoid zero
    new_psi0 /= new_psi0.sum()

    result = tuple(float(x) for x in new_psi0)
    delta = tuple(float(x) for x in (np.array(result) - current))

    return result, delta  # type: ignore[return-value]
