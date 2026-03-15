"""Pipeline schemas — legacy inter-agent JSON protocol.

.. deprecated::
    These schemas were used by the multi-agent pipeline
    (SAYOHMY/SENTINEL/TESTENGINEER). Luna now operates autonomously.
    Kept for backward compatibility (checkpoint loading, veto module).
"""

import json
import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Bounds for string fields to prevent memory exhaustion
_MAX_TASK_ID_LEN: int = 128
_MAX_STR_LEN: int = 4096
_MAX_LIST_LEN: int = 256
_MAX_CONTEXT_KEYS: int = 64
_MAX_CONTENT_LEN: int = 65536  # 64K — sufficient for generated code blocks

# task_id must be alphanumeric with hyphens/underscores/dots only (no path traversal)
_TASK_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")


class PsiState(BaseModel):
    """A Psi state vector on the simplex Delta^3."""
    perception: float = Field(ge=0, le=1)
    reflexion: float = Field(ge=0, le=1)
    integration: float = Field(ge=0, le=1)
    expression: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def check_simplex(self) -> "PsiState":
        """Validate that the vector is approximately on the simplex (sum ~= 1.0)."""
        s = self.perception + self.reflexion + self.integration + self.expression
        if abs(s - 1.0) > 0.01:
            raise ValueError(
                f"PsiState must sum to ~1.0 (got {s:.6f}). "
                f"Components: P={self.perception}, R={self.reflexion}, "
                f"I={self.integration}, E={self.expression}"
            )
        return self

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.perception, self.reflexion, self.integration, self.expression)

    def sum(self) -> float:
        return self.perception + self.reflexion + self.integration + self.expression


def _validate_task_id(v: str) -> str:
    """Validate task_id against path traversal and length."""
    if not _TASK_ID_PATTERN.match(v):
        raise ValueError(
            f"task_id must be alphanumeric with .-_ only, 1-128 chars (got: {v!r:.80})"
        )
    return v


def _validate_bounded_str(v: str, max_len: int = _MAX_STR_LEN) -> str:
    """Validate string length."""
    if len(v) > max_len:
        raise ValueError(f"String too long: {len(v)} > {max_len}")
    return v


_MAX_DICT_SERIALIZED_BYTES: int = 65536  # 64 KiB


def _validate_dict_size(v: dict, max_bytes: int = _MAX_DICT_SERIALIZED_BYTES) -> dict:
    """Reject dicts whose JSON serialization exceeds *max_bytes*.

    Prevents memory/CPU exhaustion from deeply nested or oversized payloads
    injected via inter-agent protocol messages.
    """
    if len(json.dumps(v, default=str)) > max_bytes:
        raise ValueError(
            f"Dict serialized size exceeds {max_bytes} bytes"
        )
    return v


class InfoGradient(BaseModel):
    """The d_c informational gradient — concrete mapping from pipeline reports."""
    delta_mem: float = Field(default=0.0, ge=-10.0, le=10.0, description="Memory change magnitude")
    delta_phi: float = Field(default=0.0, ge=-10.0, le=10.0, description="Quality score delta")
    delta_iit: float = Field(default=0.0, ge=-10.0, le=10.0, description="Integrated information delta")
    delta_out: float = Field(default=0.0, ge=-10.0, le=10.0, description="Output quality metric")

    def as_list(self) -> list[float]:
        return [self.delta_mem, self.delta_phi, self.delta_iit, self.delta_out]


class CurrentTask(BaseModel):
    """Written by Luna to ~/pipeline/current_task.json."""
    task_id: str = Field(max_length=_MAX_TASK_ID_LEN)
    description: str = Field(max_length=_MAX_STR_LEN)
    context: dict = Field(default_factory=dict)
    psi_luna: PsiState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    priority: Literal["low", "normal", "high", "critical"] = "normal"

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, v: str) -> str:
        return _validate_task_id(v)

    @field_validator("context")
    @classmethod
    def validate_context(cls, v: dict) -> dict:
        if len(v) > _MAX_CONTEXT_KEYS:
            raise ValueError(f"context has too many keys: {len(v)} > {_MAX_CONTEXT_KEYS}")
        _validate_dict_size(v)
        return v


class IntegrationCheck(BaseModel):
    """Integration validation check (legacy pipeline schema)."""
    task_id: str = Field(max_length=_MAX_TASK_ID_LEN)
    cross_checks: list[dict] = Field(default_factory=list, max_length=_MAX_LIST_LEN)
    coherence_score: float = Field(ge=0, le=1)
    coverage_delta: float = Field(default=0.0, ge=-10.0, le=10.0)
    veto_contested: bool = False
    contest_evidence: str | None = Field(default=None, max_length=_MAX_STR_LEN)
    psi_te: PsiState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, v: str) -> str:
        return _validate_task_id(v)

    @field_validator("cross_checks")
    @classmethod
    def validate_cross_checks(cls, v: list[dict]) -> list[dict]:
        for entry in v:
            _validate_dict_size(entry)
        return v


class Decision(BaseModel):
    """Written by Luna to ~/pipeline/decision.json — final pipeline output.

    Contains full traceability: Psi_before, Psi_after, d_c gradient.
    """
    task_id: str = Field(max_length=_MAX_TASK_ID_LEN)
    approved: bool
    reason: str = Field(max_length=_MAX_STR_LEN)
    psi_before: PsiState
    psi_after: PsiState
    info_gradient: InfoGradient
    phase: Literal["BROKEN", "FRAGILE", "FUNCTIONAL", "SOLID", "EXCELLENT"]
    quality_score: float | None = Field(default=None, ge=0, le=1)
    illusion_status: str | None = Field(
        default=None, max_length=32,
        description="IllusionDetector result: healthy/caution/illusion/harmful",
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # v0.2.0 — audit trail cross-reference
    audit_trail_id: str | None = Field(default=None, max_length=_MAX_TASK_ID_LEN)

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, v: str) -> str:
        return _validate_task_id(v)
