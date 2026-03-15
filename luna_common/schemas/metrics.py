"""Metric exchange types for the Luna phi-engine scoring pipeline.

NormalizedMetricsReport carries a standardized [0,1] metric vector whose keys
must belong to the canonical METRIC_NAMES defined in luna_common.constants.

VerdictInput bundles a *with-cognition* and *without-cognition* metrics
pair so that VerdictRunner can compute the differential impact of cognition.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator, model_validator

from luna_common.constants import METRIC_NAMES
from luna_common.schemas.pipeline import _validate_task_id

__all__ = [
    "NormalizedMetricsReport",
    "VerdictInput",
]

# ── private helpers ──────────────────────────────────────────────────────────

_METRIC_NAMES_SET: frozenset[str] = frozenset(METRIC_NAMES)


# ── schemas ──────────────────────────────────────────────────────────────────


class NormalizedMetricsReport(BaseModel):
    """Standardized metrics report with all values normalized to [0, 1].

    Keys in *metrics* must be a subset of the 7 canonical METRIC_NAMES.
    A report is *complete* when all 7 metrics are present.
    """

    model_config = {"frozen": True}

    metrics: dict[str, float] = Field(
        description="Metric name -> value in [0.0, 1.0]. Keys must be from METRIC_NAMES.",
    )
    source: str = Field(
        default="luna",
        max_length=64,
        description="Identifier of the agent or tool that produced these metrics.",
    )
    project_path: str | None = Field(
        default=None,
        max_length=512,
        description="Filesystem path of the project that was analyzed.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @model_validator(mode="after")
    def _validate_metrics(self) -> NormalizedMetricsReport:
        unknown = set(self.metrics.keys()) - _METRIC_NAMES_SET
        if unknown:
            raise ValueError(
                f"Unknown metric names: {sorted(unknown)}. "
                f"Allowed: {sorted(_METRIC_NAMES_SET)}"
            )
        for name, value in self.metrics.items():
            if not (0.0 <= value <= 1.0):
                raise ValueError(
                    f"Metric {name!r} value must be in [0.0, 1.0] (got {value})"
                )
        return self

    # -- convenience helpers --------------------------------------------------

    def get(self, name: str, default: float = 0.0) -> float:
        """Return the value for *name*, or *default* if absent."""
        return self.metrics.get(name, default)

    @property
    def complete(self) -> bool:
        """True when all 7 canonical metrics are present."""
        return _METRIC_NAMES_SET <= self.metrics.keys()


class VerdictInput(BaseModel):
    """Input payload for VerdictRunner.

    Pairs a *with-cognition* metrics report against a *without-cognition*
    baseline so the verdict can quantify the differential contribution of
    cognition to code quality.
    """

    model_config = {"frozen": True}

    task_id: str = Field(max_length=128)
    category: str = Field(
        max_length=64,
        description="Benchmark category (e.g. 'security', 'refactoring').",
    )
    metrics_with: NormalizedMetricsReport = Field(
        description="Metrics collected WITH cognitive system active.",
    )
    metrics_without: NormalizedMetricsReport = Field(
        description="Metrics collected WITHOUT cognitive system (baseline).",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, v: str) -> str:
        return _validate_task_id(v)
