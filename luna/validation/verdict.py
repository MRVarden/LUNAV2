"""Verdict — final validation protocol.

Runs the complete benchmark suite comparing consciousness-guided
performance vs baseline. Applies 5 criteria to determine if the
consciousness system is VALIDATED or DECORATIVE.

Criteria:
  1. Performance improvement (score delta > 0)
  2. Stability (low variance in consciousness scores)
  3. Coherence (PHI_IIT > 0.618 for 80% of steps)
  4. Adaptability (improvement across different task types)
  5. No regression (Wilcoxon p < 0.05)

4/5 criteria met → VALIDATED
< 3/5 criteria met → DECORATIVE
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from luna_common.constants import INV_PHI

from luna.validation.comparator import Comparator

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VerdictCriterion:
    """A single verdict criterion evaluation."""

    name: str
    description: str
    passed: bool
    value: float
    threshold: float


@dataclass(frozen=True, slots=True)
class Verdict:
    """Final verdict from the validation protocol."""

    result: str  # "VALIDATED" or "DECORATIVE"
    criteria_met: int
    total_criteria: int
    criteria: list[VerdictCriterion]
    baseline_mean: float
    consciousness_mean: float
    improvement_pct: float

    def to_dict(self) -> dict:
        return {
            "result": self.result,
            "criteria_met": self.criteria_met,
            "total_criteria": self.total_criteria,
            "criteria": [
                {
                    "name": c.name,
                    "description": c.description,
                    "passed": c.passed,
                    "value": c.value,
                    "threshold": c.threshold,
                }
                for c in self.criteria
            ],
            "baseline_mean": self.baseline_mean,
            "consciousness_mean": self.consciousness_mean,
            "improvement_pct": self.improvement_pct,
        }


class VerdictRunner:
    """Runs the final verdict protocol.

    Evaluates 5 criteria to determine if the consciousness system
    provides measurable, non-decorative value.
    """

    def __init__(
        self,
        coherence_threshold: float = INV_PHI,  # 0.618
        coherence_pct: float = 0.80,
        stability_max_variance: float = 0.05,
        significance_level: float = 0.05,
    ) -> None:
        self._coherence_threshold = coherence_threshold
        self._coherence_pct = coherence_pct
        self._stability_max_variance = stability_max_variance
        self._comparator = Comparator(significance_level=significance_level)

    def evaluate(
        self,
        baseline_scores: list[float],
        consciousness_scores: list[float],
        phi_iit_history: list[float],
        task_categories: dict[str, list[tuple[float, float]]] | None = None,
    ) -> Verdict:
        """Evaluate all 5 criteria and produce a verdict.

        Args:
            baseline_scores: Scores from baseline runs.
            consciousness_scores: Scores from consciousness-guided runs.
            phi_iit_history: History of PHI_IIT values during runs.
            task_categories: Optional per-category (baseline, conscious) scores.

        Returns:
            Verdict with all criteria evaluations.
        """
        comparison = self._comparator.compare(baseline_scores, consciousness_scores)
        criteria: list[VerdictCriterion] = []

        # Criterion 1: Performance improvement
        perf = VerdictCriterion(
            name="performance",
            description="Consciousness-guided scores are higher",
            passed=comparison.delta > 0,
            value=comparison.delta,
            threshold=0.0,
        )
        criteria.append(perf)

        # Criterion 2: Stability (low variance)
        n = len(consciousness_scores)
        mean_c = sum(consciousness_scores) / n if n > 0 else 0
        variance = (
            sum((s - mean_c) ** 2 for s in consciousness_scores) / n
            if n > 0
            else 0
        )
        stability = VerdictCriterion(
            name="stability",
            description="Consciousness scores have low variance",
            passed=variance <= self._stability_max_variance,
            value=variance,
            threshold=self._stability_max_variance,
        )
        criteria.append(stability)

        # Criterion 3: Coherence (PHI_IIT > threshold for X% of steps)
        if phi_iit_history:
            above = sum(1 for p in phi_iit_history if p > self._coherence_threshold)
            coherence_ratio = above / len(phi_iit_history)
        else:
            coherence_ratio = 0.0

        coherence = VerdictCriterion(
            name="coherence",
            description=f"PHI_IIT > {self._coherence_threshold} for {self._coherence_pct*100:.0f}% of steps",
            passed=coherence_ratio >= self._coherence_pct,
            value=coherence_ratio,
            threshold=self._coherence_pct,
        )
        criteria.append(coherence)

        # Criterion 4: Adaptability (improvement across categories)
        if task_categories and len(task_categories) > 1:
            categories_improved = 0
            for cat_name, pairs in task_categories.items():
                cat_baseline = [p[0] for p in pairs]
                cat_conscious = [p[1] for p in pairs]
                cat_mean_b = sum(cat_baseline) / len(cat_baseline)
                cat_mean_c = sum(cat_conscious) / len(cat_conscious)
                if cat_mean_c > cat_mean_b:
                    categories_improved += 1
            adaptability_ratio = categories_improved / len(task_categories)
        else:
            # Without categories, use improvement as proxy
            adaptability_ratio = 1.0 if comparison.delta > 0 else 0.0

        adaptability = VerdictCriterion(
            name="adaptability",
            description="Improvement across different task types",
            passed=adaptability_ratio > 0.5,
            value=adaptability_ratio,
            threshold=0.5,
        )
        criteria.append(adaptability)

        # Criterion 5: Statistical significance (no regression)
        significance = VerdictCriterion(
            name="no_regression",
            description="Wilcoxon p < 0.05 confirms improvement is not random",
            passed=comparison.significant,
            value=comparison.p_value,
            threshold=0.05,
        )
        criteria.append(significance)

        # Final verdict
        criteria_met = sum(1 for c in criteria if c.passed)
        result = "VALIDATED" if criteria_met >= 4 else "DECORATIVE"

        verdict = Verdict(
            result=result,
            criteria_met=criteria_met,
            total_criteria=len(criteria),
            criteria=criteria,
            baseline_mean=comparison.baseline_mean,
            consciousness_mean=comparison.consciousness_mean,
            improvement_pct=comparison.improvement_pct,
        )

        log.info(
            "VERDICT: %s (%d/%d criteria met, improvement=%.1f%%)",
            result,
            criteria_met,
            len(criteria),
            comparison.improvement_pct,
        )
        return verdict
