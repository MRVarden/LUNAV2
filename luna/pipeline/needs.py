"""NeedIdentifier — identify improvement needs from metric state.

Analyzes MetricTracker to find bootstrap metrics (need MEASURE),
weak metrics (need IMPROVE), and proposes prioritized tasks.
"""

from __future__ import annotations

import logging

from luna_common.constants import INV_PHI, METRIC_NAMES

from luna.metrics.tracker import MetricSource, MetricTracker
from luna.pipeline.task import PipelineTask, TaskType

log = logging.getLogger(__name__)

# Mapping: metric name → which TaskType addresses it.
_METRIC_TASK_MAP: dict[str, TaskType] = {
    "security_integrity": TaskType.AUDIT,
    "coverage_pct": TaskType.TEST,
    "complexity_score": TaskType.REFACTOR,
    "test_ratio": TaskType.TEST,
    "abstraction_ratio": TaskType.REFACTOR,
    "function_size_score": TaskType.REFACTOR,
    "performance_score": TaskType.IMPROVE,
}

# Priority weights: higher = more urgent when metric is weak.
_PRIORITY_WEIGHTS: dict[str, float] = {
    "security_integrity": 1.0,
    "coverage_pct": 0.9,
    "complexity_score": 0.7,
    "test_ratio": 0.8,
    "abstraction_ratio": 0.5,
    "function_size_score": 0.6,
    "performance_score": 0.85,
}


class NeedIdentifier:
    """Identify improvement needs from metric provenance and values.

    Two categories:
    1. BOOTSTRAP metrics → need MEASURE (we don't have real data)
    2. Weak metrics (value < INV_PHI) → need the corresponding TaskType
    """

    def identify(self, tracker: MetricTracker) -> list[PipelineTask]:
        """Return a prioritized list of needed pipeline tasks.

        Higher priority tasks come first.
        """
        needs: list[PipelineTask] = []

        for name in METRIC_NAMES:
            entry = tracker.get(name)

            if entry is None or entry.source == MetricSource.BOOTSTRAP:
                # No real measurement — need to MEASURE first.
                needs.append(PipelineTask(
                    task_type=TaskType.MEASURE,
                    description=f"Mesurer {name} — valeur actuelle: bootstrap",
                    priority=_PRIORITY_WEIGHTS.get(name, 0.5),
                    source="need",
                ))
            elif entry.value < INV_PHI:
                # Weak metric — needs improvement.
                task_type = _METRIC_TASK_MAP.get(name, TaskType.IMPROVE)
                needs.append(PipelineTask(
                    task_type=task_type,
                    description=(
                        f"Ameliorer {name} — valeur: {entry.value:.3f} "
                        f"(seuil: {INV_PHI:.3f})"
                    ),
                    priority=_PRIORITY_WEIGHTS.get(name, 0.5) * (1.0 - entry.value),
                    source="need",
                ))

        # Sort by priority descending.
        needs.sort(key=lambda t: t.priority, reverse=True)
        return needs

    def propose_to_human(self, needs: list[PipelineTask]) -> str:
        """Format needs as a readable French proposal for the chat.

        Returns empty string if no needs.
        """
        if not needs:
            return ""

        lines = ["## Besoins identifies\n"]
        for i, task in enumerate(needs, 1):
            emoji = {
                TaskType.MEASURE: "📏",
                TaskType.TEST: "🧪",
                TaskType.AUDIT: "🛡️",
                TaskType.REFACTOR: "🔧",
                TaskType.IMPROVE: "⚡",
            }.get(task.task_type, "📋")
            lines.append(
                f"{i}. {emoji} [{task.task_type.value.upper()}] "
                f"{task.description} (priorite: {task.priority:.2f})"
            )

        bootstrap_count = sum(1 for t in needs if t.task_type == TaskType.MEASURE)
        if bootstrap_count > 0:
            lines.append(
                f"\n⚠️ {bootstrap_count} metrique(s) encore en bootstrap "
                f"— une mesure reelle est necessaire."
            )

        return "\n".join(lines)
