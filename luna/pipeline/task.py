"""Pipeline task models for Luna's self-evolution loop.

TaskType/AutonomyLevel enums, TaskIntent (detection output),
PipelineTask (pipeline input), StepResult/PipelineResult (pipeline output).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

# S07-001: task_id must be hex-only to prevent injection in python -c scripts.
_TASK_ID_RE = re.compile(r"^[a-f0-9]{8,16}$")


class TaskType(str, Enum):
    """Type of pipeline task Luna can trigger."""
    GENERATE = "generate"
    IMPROVE = "improve"
    FIX = "fix"
    REFACTOR = "refactor"
    MEASURE = "measure"
    TEST = "test"
    AUDIT = "audit"


class AutonomyLevel(str, Enum):
    """How much human oversight is required."""
    SUPERVISED = "supervised"          # Human must approve before execution
    SEMI_AUTONOMOUS = "semi_autonomous"  # Human notified, can veto
    AUTONOMOUS = "autonomous"          # Fully autonomous (future)


class TaskStatus(str, Enum):
    """Pipeline task lifecycle."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    VETOED = "vetoed"


@dataclass(frozen=True, slots=True)
class TaskIntent:
    """Output of TaskDetector — a detected intent to run the pipeline.

    Immutable: once detected, the intent doesn't change.
    """
    task_type: TaskType
    description: str
    target_path: str = ""
    language: str = "python"
    confidence: float = 0.0
    signals: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PipelineTask:
    """A concrete task to be executed by the pipeline.

    Created from a TaskIntent or from NeedIdentifier.
    """
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    task_type: TaskType = TaskType.MEASURE
    description: str = ""
    priority: float = 0.5
    source: str = "chat"  # "chat" | "need" | "dream"

    def __post_init__(self) -> None:
        """Validate task_id format (hex-only, 8-16 chars).

        S07-001: Prevents injection when task_id is interpolated into
        the TESTENGINEER python -c script in runner.py.
        """
        if not _TASK_ID_RE.match(self.task_id):
            # Frozen dataclass — must use object.__setattr__.
            object.__setattr__(self, "task_id", uuid.uuid4().hex[:12])

    @classmethod
    def from_intent(cls, intent: TaskIntent, source: str = "chat") -> PipelineTask:
        """Create a PipelineTask from a detected TaskIntent."""
        return cls(
            task_type=intent.task_type,
            description=intent.description,
            priority=intent.confidence,
            source=source,
        )


@dataclass(slots=True)
class StepResult:
    """Result of a single agent invocation within the pipeline."""
    agent: str
    success: bool
    duration_seconds: float = 0.0
    return_code: int = 0
    stdout: str = ""
    stderr: str = ""


@dataclass(slots=True)
class PipelineResult:
    """Complete result of a pipeline run."""
    task_id: str
    status: TaskStatus = TaskStatus.COMPLETED
    reason: str = ""
    steps: list[StepResult] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    duration_seconds: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
