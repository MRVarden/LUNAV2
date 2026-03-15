"""CycleRecord and related schemas — the unit of lived experience for Luna.

A CycleRecord captures one complete sensorimotor cycle:
  state -> decision -> action -> consequences -> evaluation -> learning

All schemas follow the same conventions as pipeline.py / signals.py:
Pydantic BaseModel, bounded fields, size-limited dicts, UTC timestamps.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# ── Constants ────────────────────────────────────────────────────────────────

_MAX_OBSERVATIONS: int = 64
_MAX_NEEDS: int = 32
_MAX_TELEMETRY_EVENTS: int = 512
_MAX_CATEGORIES: int = 16
_MAX_ALTERNATIVES: int = 10
_MAX_STR_LEN: int = 4096
_MAX_EVENT_DATA_BYTES: int = 4096  # 4KB per event payload
_MAX_DICT_BYTES: int = 65536  # 64KB for generic dicts
_MAX_RECORD_BYTES: int = 51200  # 50KB hard limit per CycleRecord

# Valid event types for telemetry
TELEMETRY_EVENT_TYPES: frozenset[str] = frozenset({
    "AGENT_START", "AGENT_END",
    "STDERR_CHUNK", "MANIFEST_PARSED", "METRICS_FED",
    "VETO_EMITTED", "DIFF_STATS", "TESTS_PROGRESS",
    "RETRY_TRIGGERED", "RESOURCE",
})

# Valid intents
VALID_INTENTS: frozenset[str] = frozenset({
    "RESPOND", "PIPELINE", "DREAM", "INTROSPECT", "ALERT",
})

# Valid modes
VALID_MODES: frozenset[str] = frozenset({
    "virtuoso", "architect", "mentor", "reviewer", "debugger",
})

# Valid focus targets (Psi components)
VALID_FOCUS: frozenset[str] = frozenset({
    "PERCEPTION", "REFLECTION", "INTEGRATION", "EXPRESSION",
})

# Valid depth levels
VALID_DEPTHS: frozenset[str] = frozenset({
    "MINIMAL", "CONCISE", "DETAILED", "PROFOUND",
})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_dict_size(v: dict, max_bytes: int = _MAX_DICT_BYTES) -> dict:
    if len(json.dumps(v, default=str)) > max_bytes:
        raise ValueError(f"Dict serialized size exceeds {max_bytes} bytes")
    return v


# ── Telemetry ────────────────────────────────────────────────────────────────


class TelemetryEvent(BaseModel):
    """A single instrumentation event from the pipeline execution."""

    model_config = {"frozen": True}

    event_type: str = Field(max_length=64)
    agent: str | None = Field(default=None, max_length=64)
    timestamp: datetime = Field(default_factory=_utc_now)
    data: dict = Field(default_factory=dict)

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        if v not in TELEMETRY_EVENT_TYPES:
            raise ValueError(
                f"Unknown event_type {v!r}. "
                f"Allowed: {sorted(TELEMETRY_EVENT_TYPES)}"
            )
        return v

    @field_validator("data")
    @classmethod
    def validate_data(cls, v: dict) -> dict:
        return _validate_dict_size(v, _MAX_EVENT_DATA_BYTES)


# ── VoiceDelta ───────────────────────────────────────────────────────────────

# Categories of voice validator corrections
VOICE_CATEGORIES: frozenset[str] = frozenset({
    "UNVERIFIED", "TOO_ASSERTIVE", "STYLE", "SECURITY",
    "HALLUCINATION", "FORMAT",
})


class VoiceDelta(BaseModel):
    """Signal produced by VoiceValidator: what was sanitized and how much."""

    model_config = {"frozen": True}

    violations_count: int = Field(ge=0, le=100)
    categories: list[str] = Field(default_factory=list, max_length=_MAX_CATEGORIES)
    severity: float = Field(ge=0.0, le=1.0)
    ratio_modified_chars: float = Field(ge=0.0, le=1.0)

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, v: list[str]) -> list[str]:
        unknown = set(v) - VOICE_CATEGORIES
        if unknown:
            raise ValueError(
                f"Unknown voice categories: {sorted(unknown)}. "
                f"Allowed: {sorted(VOICE_CATEGORIES)}"
            )
        return sorted(set(v))  # deduplicate + sort for determinism


# ── Reward ───────────────────────────────────────────────────────────────────

# Canonical reward component names — 9 cognitive components (v5.0)
# Mapped to 4 pillars: Safety, Integration(psi3), Reflection(psi2),
# Perception(psi1), Expression(psi4), Transversal
REWARD_COMPONENT_NAMES: tuple[str, ...] = (
    "constitution_integrity",   # Priority 1 — Safety: bundle intact
    "anti_collapse",            # Priority 1 — Safety: no dimension dies
    "integration_coherence",    # Priority 2 — psi3: phi_iit level
    "identity_stability",       # Priority 2 — psi3: fidelity to Psi0
    "reflection_depth",         # Priority 3 — psi2: confidence * causalities
    "perception_acuity",        # Priority 4 — psi1: observation quality
    "expression_fidelity",      # Priority 5 — psi4: voice compliance
    "affect_regulation",        # Priority 6 — Transversal: emotional balance
    "memory_vitality",          # Priority 6 — Transversal: episode production
)

# Legacy names for backward compatibility with existing CycleRecords
LEGACY_REWARD_NAMES: frozenset[str] = frozenset({
    "world_validity", "world_regression", "integration",
    "cost_time", "cost_scope", "expression", "novelty",
})

# Dominance priority groups — each pillar has its own group
DOMINANCE_GROUPS: dict[int, list[int]] = {
    1: [0, 1],    # Safety: constitution + anti_collapse
    2: [2, 3],    # Integration (psi3): coherence + identity
    3: [4],       # Reflection (psi2): depth
    4: [5],       # Perception (psi1): acuity
    5: [6],       # Expression (psi4): fidelity
    6: [7, 8],    # Transversal: affect + memory
}

# Fixed weights for J potential (Fibonacci-like, NOT learnable, sum = 1.00)
J_WEIGHTS: tuple[float, ...] = (
    0.21,  # constitution_integrity  (Safety)
    0.17,  # anti_collapse           (Safety)
    0.16,  # integration_coherence   (psi3)
    0.13,  # identity_stability      (psi3)
    0.12,  # reflection_depth        (psi2)
    0.08,  # perception_acuity       (psi1)
    0.06,  # expression_fidelity     (psi4)
    0.04,  # affect_regulation       (Transversal)
    0.03,  # memory_vitality         (Transversal)
)


class RewardComponent(BaseModel):
    """One dimension of the reward vector."""

    model_config = {"frozen": True}

    name: str = Field(max_length=64)
    value: float = Field(ge=-1.0, le=1.0)
    raw: float = Field(description="Raw value before normalization")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if v not in REWARD_COMPONENT_NAMES and v not in LEGACY_REWARD_NAMES:
            raise ValueError(
                f"Unknown reward component {v!r}. "
                f"Allowed: {list(REWARD_COMPONENT_NAMES)}"
            )
        return v


class RewardVector(BaseModel):
    """Complete evaluation output: components + dominance rank + potential delta."""

    model_config = {"frozen": True}

    components: list[RewardComponent] = Field(max_length=len(REWARD_COMPONENT_NAMES))
    dominance_rank: int = Field(
        ge=0,
        description="Lexicographic rank vs recent history (0 = best)",
    )
    delta_j: float = Field(
        description="J(t) - J(t-1) potential variation (tie-break)",
    )

    @model_validator(mode="after")
    def validate_components(self) -> RewardVector:
        names = [c.name for c in self.components]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate component names in RewardVector")
        return self

    def get(self, name: str) -> float:
        """Return value for a named component, or 0.0 if absent."""
        for c in self.components:
            if c.name == name:
                return c.value
        return 0.0

    def compute_j(self) -> float:
        """Compute the J potential from components using fixed weights."""
        j = 0.0
        for comp in self.components:
            idx = REWARD_COMPONENT_NAMES.index(comp.name)
            j += J_WEIGHTS[idx] * comp.value
        return j

    def dominance_compare(self, other: RewardVector) -> int:
        """Lexicographic comparison by priority groups.

        Returns:
            +1 if self dominates other,
            -1 if other dominates self,
             0 if tied (use delta_j as tie-break).
        """
        for _priority, indices in sorted(DOMINANCE_GROUPS.items()):
            self_sum = sum(
                self.get(REWARD_COMPONENT_NAMES[i]) for i in indices
            )
            other_sum = sum(
                other.get(REWARD_COMPONENT_NAMES[i]) for i in indices
            )
            if self_sum > other_sum:
                return 1
            if self_sum < other_sum:
                return -1
        return 0


# ── TelemetrySummary ─────────────────────────────────────────────────────────


class TelemetrySummary(BaseModel):
    """Digested signals from raw telemetry — what the Thinker actually reads."""

    model_config = {"frozen": True}

    pipeline_latency_bucket: str = Field(
        default="normal", max_length=32,
        description="fast / normal / slow / outlier",
    )
    agent_latency_outliers: list[str] = Field(
        default_factory=list, max_length=4,
        description="Agents whose duration > 2 sigma",
    )
    stderr_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    veto_frequency: float = Field(default=0.0, ge=0.0, le=1.0)
    veto_top_reasons: list[str] = Field(
        default_factory=list, max_length=3,
    )
    diff_scope_ratio: float = Field(
        default=0.0, ge=0.0,
        description="lines_changed / scope_budget",
    )
    metric_coverage: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="measured / total metrics",
    )
    test_pass_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    manifest_parse_health: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="ok_count / total_manifests",
    )
    flakiness_score: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="variance(test_pass_rate) over recent cycles",
    )


# ── CycleRecord ──────────────────────────────────────────────────────────────


class CycleRecord(BaseModel):
    """The unit of lived experience — one complete sensorimotor cycle.

    Persistent, serializable, replayable. This is Luna's life.
    """

    # -- Identity --
    cycle_id: str = Field(max_length=64, description="Short UUID")
    timestamp: datetime = Field(default_factory=_utc_now)
    context_digest: str = Field(
        max_length=128,
        description="hash(chat_history[-5:] + state_summary)",
    )

    # -- Internal state --
    psi_before: tuple[float, float, float, float]
    psi_after: tuple[float, float, float, float]
    phi_before: float = Field(ge=0.0, le=2.0)
    phi_after: float = Field(ge=0.0, le=2.0)
    phi_iit_before: float = Field(ge=0.0)  # Gaussian MI — unbounded above
    phi_iit_after: float = Field(ge=0.0)   # Gaussian MI — unbounded above
    emergent_phi: float | None = Field(
        default=None, ge=0.0, le=5.0,
        description="Emergent phi from coupling dynamics (self-discovered golden ratio)",
    )
    phase_before: Literal["BROKEN", "FRAGILE", "FUNCTIONAL", "SOLID", "EXCELLENT"]
    phase_after: Literal["BROKEN", "FRAGILE", "FUNCTIONAL", "SOLID", "EXCELLENT"]

    # -- Thinker output --
    observations: list[str] = Field(default_factory=list, max_length=_MAX_OBSERVATIONS)
    causalities_count: int = Field(ge=0)
    needs: list[str] = Field(default_factory=list, max_length=_MAX_NEEDS)
    thinker_confidence: float = Field(ge=0.0, le=1.0)

    # -- Decision --
    intent: str = Field(max_length=32)
    mode: str | None = Field(default=None, max_length=32)
    focus: str = Field(max_length=32)
    depth: str = Field(max_length=32)
    scope_budget: dict = Field(
        default_factory=lambda: {"max_files": 10, "max_lines": 500},
    )
    initiative_flags: dict = Field(
        default_factory=dict,
        description="source, urgency, reason",
    )
    alternatives_considered: list[dict] = Field(
        default_factory=list, max_length=_MAX_ALTERNATIVES,
        description="[{intent, mode, reason_rejected}]",
    )

    # -- Execution --
    telemetry_timeline: list[TelemetryEvent] = Field(
        default_factory=list, max_length=_MAX_TELEMETRY_EVENTS,
    )
    telemetry_summary: TelemetrySummary | None = Field(default=None)
    pipeline_result: dict | None = Field(default=None)

    # -- Expression --
    voice_delta: VoiceDelta | None = Field(default=None)

    # -- Affect --
    affect_trace: dict | None = Field(
        default=None,
        description="PAD before/after: {valence_before, arousal_before, dominance_before, "
                    "valence_after, arousal_after, dominance_after}",
    )

    # -- Evaluation --
    reward: RewardVector | None = Field(default=None)
    learnable_params_before: dict[str, float] = Field(default_factory=dict)
    learnable_params_after: dict[str, float] = Field(default_factory=dict)

    # -- LLM health (v6.0) --
    llm_failed: bool = Field(default=False)
    llm_latency_ms: float = Field(default=0.0, ge=0.0)
    llm_circuit_state: str = Field(default="closed", max_length=16)

    # -- Meta --
    autonomy_level: int = Field(default=0, ge=0, le=10, description="W (0=supervised)")
    rollback_occurred: bool = Field(default=False)
    duration_seconds: float = Field(ge=0.0)
    dream_priors_active: int = Field(default=0, ge=0, description="dream obs injected this cycle")

    # -- Ghost (Phase A — shadow auto-apply evaluation) --
    auto_apply_candidate: bool = Field(default=False)
    ghost_reason: str = Field(default="", max_length=512)
    ghost_expected_rank: int | None = Field(default=None)
    ghost_planned_scope: dict | None = Field(default=None)

    # -- Auto-apply (Phase B — W=1 real apply with snapshot physics) --
    auto_applied: bool = Field(default=False)
    auto_rolled_back: bool = Field(default=False)
    auto_post_tests: bool | None = Field(default=None, description="smoke tests passed?")
    auto_diff_stats: dict | None = Field(default=None, description="{files, lines}")
    auto_delta_rank: int | None = Field(
        default=None,
        description="dominance rank change after apply (positive=better)",
    )

    # -- Validators --

    @field_validator("intent")
    @classmethod
    def validate_intent(cls, v: str) -> str:
        if v not in VALID_INTENTS:
            raise ValueError(
                f"Unknown intent {v!r}. Allowed: {sorted(VALID_INTENTS)}"
            )
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_MODES:
            raise ValueError(
                f"Unknown mode {v!r}. Allowed: {sorted(VALID_MODES)}"
            )
        return v

    @field_validator("focus")
    @classmethod
    def validate_focus(cls, v: str) -> str:
        if v not in VALID_FOCUS:
            raise ValueError(
                f"Unknown focus {v!r}. Allowed: {sorted(VALID_FOCUS)}"
            )
        return v

    @field_validator("depth")
    @classmethod
    def validate_depth(cls, v: str) -> str:
        if v not in VALID_DEPTHS:
            raise ValueError(
                f"Unknown depth {v!r}. Allowed: {sorted(VALID_DEPTHS)}"
            )
        return v

    @model_validator(mode="after")
    def validate_psi_simplex(self) -> CycleRecord:
        """Validate that psi_before and psi_after are on the simplex."""
        for label, psi in [("psi_before", self.psi_before), ("psi_after", self.psi_after)]:
            s = sum(psi)
            if abs(s - 1.0) > 0.01:
                raise ValueError(
                    f"{label} must sum to ~1.0 (got {s:.6f}): {psi}"
                )
            if any(v < 0.0 for v in psi):
                raise ValueError(f"{label} components must be >= 0: {psi}")
        return self

    @field_validator("scope_budget")
    @classmethod
    def validate_scope_budget(cls, v: dict) -> dict:
        return _validate_dict_size(v, 1024)

    @field_validator("initiative_flags")
    @classmethod
    def validate_initiative_flags(cls, v: dict) -> dict:
        return _validate_dict_size(v, 1024)

    @field_validator("alternatives_considered")
    @classmethod
    def validate_alternatives(cls, v: list[dict]) -> list[dict]:
        for alt in v:
            _validate_dict_size(alt, 1024)
        return v

    @field_validator("pipeline_result")
    @classmethod
    def validate_pipeline_result(cls, v: dict | None) -> dict | None:
        if v is not None:
            _validate_dict_size(v, _MAX_DICT_BYTES)
        return v

    @field_validator("ghost_planned_scope")
    @classmethod
    def validate_ghost_planned_scope(cls, v: dict | None) -> dict | None:
        if v is not None:
            _validate_dict_size(v, 1024)
        return v

    @field_validator("auto_diff_stats")
    @classmethod
    def validate_auto_diff_stats(cls, v: dict | None) -> dict | None:
        if v is not None:
            _validate_dict_size(v, 1024)
        return v

    @field_validator("observations")
    @classmethod
    def validate_observations(cls, v: list[str]) -> list[str]:
        for obs in v:
            if len(obs) > _MAX_STR_LEN:
                raise ValueError(f"Observation too long: {len(obs)} > {_MAX_STR_LEN}")
        return v

    @field_validator("needs")
    @classmethod
    def validate_needs(cls, v: list[str]) -> list[str]:
        for need in v:
            if len(need) > _MAX_STR_LEN:
                raise ValueError(f"Need too long: {len(need)} > {_MAX_STR_LEN}")
        return v


# ── Exports ──────────────────────────────────────────────────────────────────

__all__ = [
    "TelemetryEvent",
    "VoiceDelta",
    "TelemetrySummary",
    "RewardComponent",
    "RewardVector",
    "CycleRecord",
    # Constants
    "TELEMETRY_EVENT_TYPES",
    "VOICE_CATEGORIES",
    "REWARD_COMPONENT_NAMES",
    "DOMINANCE_GROUPS",
    "J_WEIGHTS",
    "VALID_INTENTS",
    "VALID_MODES",
    "VALID_FOCUS",
    "VALID_DEPTHS",
]
