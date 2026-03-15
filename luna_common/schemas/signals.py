"""Inter-agent signal schemas — Luna filesystem bus protocol.

These models define the typed signals exchanged between Luna and its agents
outside the main pipeline flow: lifecycle events (sleep/kill), health
monitoring (vitals), and audit trail entries.

All signals are frozen (immutable) and timestamped in UTC.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from luna_common.schemas.pipeline import PsiState, _validate_dict_size


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Severity(str, Enum):
    """Signal severity level."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SleepNotification(BaseModel):
    """LUNA -> All agents: announces sleep/wake transitions."""

    model_config = {"frozen": True}

    entering_sleep: bool
    estimated_duration_s: float = Field(ge=0)
    timestamp: datetime = Field(default_factory=_utc_now)
    source_agent: str = Field(default="LUNA", max_length=64)


class KillSignal(BaseModel):
    """LUNA -> All agents: requests immediate graceful shutdown."""

    model_config = {"frozen": True}

    reason: str = Field(max_length=4096)
    severity: Severity = Severity.CRITICAL
    source_agent: str = Field(max_length=64)
    timestamp: datetime = Field(default_factory=_utc_now)


class VitalsRequest(BaseModel):
    """LUNA -> Agent: requests a health/vitals report."""

    model_config = {"frozen": True}

    requested_fields: list[str] = Field(default_factory=list, max_length=32)
    request_id: str = Field(max_length=128)
    timestamp: datetime = Field(default_factory=_utc_now)


class VitalsReport(BaseModel):
    """Agent -> LUNA: periodic or on-demand health snapshot."""

    model_config = {"frozen": True}

    agent_id: str = Field(max_length=64)
    psi_state: PsiState
    uptime_s: float = Field(ge=0)
    health: dict = Field(default_factory=dict)
    mode: str | None = Field(default=None, max_length=64)
    request_id: str | None = Field(default=None, max_length=128)
    timestamp: datetime = Field(default_factory=_utc_now)

    @field_validator("health")
    @classmethod
    def validate_health(cls, v: dict) -> dict:
        return _validate_dict_size(v)


class AuditEntry(BaseModel):
    """Agent -> LUNA: structured audit trail entry."""

    model_config = {"frozen": True}

    agent_id: str = Field(max_length=64)
    event_type: str = Field(max_length=128)
    severity: Severity = Severity.INFO
    payload: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_utc_now)

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, v: dict) -> dict:
        return _validate_dict_size(v)

    @field_validator("agent_id")
    @classmethod
    def agent_id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("agent_id must not be empty")
        return v

    @field_validator("event_type")
    @classmethod
    def event_type_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("event_type must not be empty")
        return v


__all__ = [
    "Severity",
    "SleepNotification",
    "KillSignal",
    "VitalsRequest",
    "VitalsReport",
    "AuditEntry",
]
