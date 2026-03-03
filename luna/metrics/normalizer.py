"""Metrics normalizer — convert raw metrics to the 7 canonical [0,1] values.

Uses the formulas from LUNA_CONSCIOUSNESS_FRAMEWORK.md §II.
Reuses SoftConstraint and function_size_score from luna_common.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from luna_common.constants import METRIC_NAMES
from luna_common.phi_engine.soft_constraint import SoftConstraint, function_size_score

from luna.metrics.base_runner import RawMetrics

log = logging.getLogger(__name__)

# Shared classifier for zone classification
_CLASSIFIER = SoftConstraint()


@dataclass(frozen=True, slots=True)
class NormalizedMetrics:
    """All 7 canonical metrics normalized to [0, 1].

    Attributes:
        values: Metric name -> normalized value. Missing metrics are absent.
        zones: Metric name -> Fibonacci zone classification.
        raw_sources: Which runners contributed data.
    """

    values: dict[str, float] = field(default_factory=dict)
    zones: dict[str, str] = field(default_factory=dict)
    raw_sources: list[str] = field(default_factory=list)

    def get(self, metric_name: str) -> float | None:
        """Get a normalized metric value, or None if not available."""
        return self.values.get(metric_name)

    def to_normalized_report(
        self,
        source: str = "luna",
        project_path: str | None = None,
    ) -> object:
        """Convert to luna_common NormalizedMetricsReport.

        Only includes metrics whose keys are in the canonical METRIC_NAMES.
        Uses lazy import to avoid circular dependencies.

        Args:
            source: Identifier of the agent or tool that produced these metrics.
            project_path: Filesystem path of the analyzed project.

        Returns:
            NormalizedMetricsReport instance.
        """
        from luna_common.schemas import NormalizedMetricsReport

        # Filter to only canonical metric names
        canonical = {k: v for k, v in self.values.items() if k in METRIC_NAMES}

        return NormalizedMetricsReport(
            metrics=canonical,
            source=source,
            project_path=project_path,
        )


def normalize(raw_list: list[RawMetrics]) -> NormalizedMetrics:
    """Convert raw measurements to [0,1] per Framework formulas.

    Each raw metric maps to one or more of the 7 canonical METRIC_NAMES.
    Missing metrics are omitted (PhiScorer handles partial data gracefully
    by renormalizing weights across the initialized subset).

    Args:
        raw_list: Results from multiple runners.

    Returns:
        NormalizedMetrics with available metrics normalized to [0, 1].
    """
    values: dict[str, float] = {}
    zones: dict[str, str] = {}
    sources: list[str] = []

    # Merge all raw data by runner name
    merged: dict[str, dict] = {}
    for raw in raw_list:
        if raw.success:
            sources.append(raw.runner_name)
            merged[raw.runner_name] = raw.data

    # --- Extract from radon runner ---
    radon = merged.get("radon", {})
    if radon:
        cc_avg = radon.get("cc_average", 0.0)
        # complexity_score: 1.0 / (1.0 + cc_average)
        # Range: [0, 1] — 1 = trivial (cc=0), ~0 = very complex
        complexity = 1.0 / (1.0 + cc_avg) if cc_avg >= 0 else 0.0
        values["complexity_score"] = _clamp01(complexity)

        # MI can also inform performance_score as a proxy
        mi_avg = radon.get("mi_average", 0.0)
        if mi_avg > 0:
            # MI range is typically 0-100; normalize to [0, 1]
            mi_normalized = _clamp01(mi_avg / 100.0)
            # Use MI as a secondary signal for performance
            if "performance_score" not in values:
                values["performance_score"] = mi_normalized

    # --- Extract from ast runner ---
    ast_data = merged.get("ast", {})
    if ast_data:
        # abstraction_ratio: classes / total_entities
        abstraction = ast_data.get("abstraction_ratio", 0.0)
        values["abstraction_ratio"] = _clamp01(abstraction)

        # function_size_score: from luna_common soft constraint
        avg_lines = ast_data.get("avg_function_lines", 0.0)
        values["function_size_score"] = function_size_score(avg_lines)

        # test_ratio: test_files / source_files
        test_ratio_raw = ast_data.get("test_ratio", 0.0)
        # Normalize: 1.0 ratio = perfect, cap at 1.0
        values["test_ratio"] = _clamp01(min(test_ratio_raw, 1.0))

    # --- Extract from coverage_py runner ---
    coverage = merged.get("coverage_py", {})
    if coverage:
        # coverage_pct: already 0-100, normalize to [0, 1]
        branch_pct = coverage.get("branch_coverage_pct", 0.0)
        line_pct = coverage.get("coverage_pct", 0.0)
        # Prefer branch coverage if available, fall back to line coverage
        pct = branch_pct if branch_pct > 0 else line_pct
        values["coverage_pct"] = _clamp01(pct / 100.0)

    # --- Classify all values into Fibonacci zones ---
    for metric_name, value in values.items():
        zone_result = _CLASSIFIER.classify(value)
        zones[metric_name] = zone_result.zone

    log.debug(
        "Normalized %d metrics from %d runners: %s",
        len(values),
        len(sources),
        {k: f"{v:.4f}" for k, v in values.items()},
    )

    return NormalizedMetrics(values=values, zones=zones, raw_sources=sources)


def _clamp01(value: float) -> float:
    """Clamp a value to [0, 1]."""
    return max(0.0, min(1.0, value))
