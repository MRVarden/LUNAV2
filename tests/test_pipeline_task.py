"""Tests for pipeline task data models (v2.4.0 Session 1).

Validates the frozen dataclass contracts, enum values, factory methods,
and defaults for TaskType, AutonomyLevel, TaskStatus, TaskIntent,
PipelineTask, StepResult, and PipelineResult.

CRITICAL INVARIANTS:
  - All enums are str subclasses (JSON-serializable without custom encoder)
  - TaskIntent and PipelineTask are frozen (immutable after creation)
  - PipelineTask.from_intent() maps fields correctly
  - Auto-generated task_id is a 12-char hex string
  - Default values are sensible and do not share mutable state
"""

from __future__ import annotations

import re
from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from luna.pipeline.task import (
    AutonomyLevel,
    PipelineResult,
    PipelineTask,
    StepResult,
    TaskIntent,
    TaskStatus,
    TaskType,
)


# ---------------------------------------------------------------------------
# Enum value tests
# ---------------------------------------------------------------------------

class TestTaskTypeEnum:
    """TaskType enum completeness and values."""

    def test_all_seven_values_exist(self):
        """TaskType must have exactly 7 members."""
        expected = {"generate", "improve", "fix", "refactor", "measure", "test", "audit"}
        actual = {e.value for e in TaskType}
        assert actual == expected, f"TaskType values: {actual}"

    def test_is_str_subclass(self):
        """TaskType members are str instances (JSON-serializable)."""
        for member in TaskType:
            assert isinstance(member, str), f"{member} is not str"


class TestAutonomyLevelEnum:
    """AutonomyLevel enum completeness and values."""

    def test_all_three_values_exist(self):
        """AutonomyLevel must have exactly 3 members."""
        expected = {"supervised", "semi_autonomous", "autonomous"}
        actual = {e.value for e in AutonomyLevel}
        assert actual == expected, f"AutonomyLevel values: {actual}"

    def test_is_str_subclass(self):
        """AutonomyLevel members are str instances."""
        for member in AutonomyLevel:
            assert isinstance(member, str), f"{member} is not str"


class TestTaskStatusEnum:
    """TaskStatus enum completeness and values."""

    def test_all_five_values_exist(self):
        """TaskStatus must have exactly 5 members."""
        expected = {"pending", "running", "completed", "failed", "vetoed"}
        actual = {e.value for e in TaskStatus}
        assert actual == expected, f"TaskStatus values: {actual}"

    def test_is_str_subclass(self):
        """TaskStatus members are str instances."""
        for member in TaskStatus:
            assert isinstance(member, str), f"{member} is not str"


# ---------------------------------------------------------------------------
# Frozen dataclass tests
# ---------------------------------------------------------------------------

class TestTaskIntent:
    """TaskIntent is a frozen dataclass with correct fields."""

    def test_fields_accessible(self):
        """All declared fields are accessible after construction."""
        intent = TaskIntent(
            task_type=TaskType.FIX,
            description="Fix the flaky test",
            target_path="tests/test_example.py",
            language="python",
            confidence=0.85,
            signals=("error_in_log", "test_failure"),
        )
        assert intent.task_type == TaskType.FIX
        assert intent.description == "Fix the flaky test"
        assert intent.target_path == "tests/test_example.py"
        assert intent.language == "python"
        assert intent.confidence == 0.85
        assert intent.signals == ("error_in_log", "test_failure")

    def test_frozen_raises_on_mutation(self):
        """Attempting to modify a field raises FrozenInstanceError."""
        intent = TaskIntent(task_type=TaskType.MEASURE, description="measure it")
        with pytest.raises(FrozenInstanceError):
            intent.description = "changed"  # type: ignore[misc]

    def test_defaults(self):
        """Default values are correct when only required fields given."""
        intent = TaskIntent(task_type=TaskType.AUDIT, description="audit code")
        assert intent.target_path == ""
        assert intent.language == "python"
        assert intent.confidence == 0.0
        assert intent.signals == ()


class TestPipelineTask:
    """PipelineTask is a frozen dataclass with auto-generated ID."""

    def test_frozen_raises_on_mutation(self):
        """Attempting to modify a field raises FrozenInstanceError."""
        task = PipelineTask()
        with pytest.raises(FrozenInstanceError):
            task.description = "changed"  # type: ignore[misc]

    def test_default_task_id_is_12_char_hex(self):
        """Auto-generated task_id is a 12-character hex string."""
        task = PipelineTask()
        assert len(task.task_id) == 12, (
            f"Expected 12-char ID, got {len(task.task_id)}: {task.task_id!r}"
        )
        assert re.fullmatch(r"[0-9a-f]{12}", task.task_id), (
            f"task_id is not hex: {task.task_id!r}"
        )

    def test_default_ids_are_unique(self):
        """Each PipelineTask gets a distinct auto-generated ID."""
        ids = {PipelineTask().task_id for _ in range(50)}
        assert len(ids) == 50, "Auto-generated IDs must be unique"

    def test_defaults(self):
        """Default values are sensible."""
        task = PipelineTask()
        assert task.task_type == TaskType.MEASURE
        assert task.description == ""
        assert task.priority == 0.5
        assert task.source == "chat"

    def test_from_intent_maps_fields(self):
        """from_intent() correctly maps TaskIntent fields to PipelineTask."""
        intent = TaskIntent(
            task_type=TaskType.REFACTOR,
            description="Refactor the module",
            target_path="src/module.py",
            confidence=0.9,
        )
        task = PipelineTask.from_intent(intent, source="need")

        assert task.task_type == TaskType.REFACTOR
        assert task.description == "Refactor the module"
        assert task.priority == 0.9  # maps from intent.confidence
        assert task.source == "need"
        assert len(task.task_id) == 12  # still auto-generated

    def test_from_intent_default_source(self):
        """from_intent() defaults source to 'chat'."""
        intent = TaskIntent(task_type=TaskType.TEST, description="test it")
        task = PipelineTask.from_intent(intent)
        assert task.source == "chat"


# ---------------------------------------------------------------------------
# Mutable dataclass tests
# ---------------------------------------------------------------------------

class TestStepResult:
    """StepResult is a mutable dataclass with sensible defaults."""

    def test_defaults(self):
        """Default values for optional fields."""
        step = StepResult(agent="sayohmy", success=True)
        assert step.duration_seconds == 0.0
        assert step.return_code == 0
        assert step.stdout == ""
        assert step.stderr == ""

    def test_all_fields_writable(self):
        """StepResult is mutable -- fields can be updated."""
        step = StepResult(agent="sentinel", success=False)
        step.success = True
        step.duration_seconds = 1.5
        assert step.success is True
        assert step.duration_seconds == 1.5


class TestPipelineResult:
    """PipelineResult is a mutable dataclass with list/dict defaults."""

    def test_defaults(self):
        """Default values for optional fields."""
        result = PipelineResult(task_id="abc123")
        assert result.status == TaskStatus.COMPLETED
        assert result.reason == ""
        assert result.steps == []
        assert result.metrics == {}
        assert result.duration_seconds == 0.0
        assert isinstance(result.timestamp, datetime)

    def test_default_lists_not_shared(self):
        """Each instance gets its own mutable list/dict (no aliasing)."""
        r1 = PipelineResult(task_id="a")
        r2 = PipelineResult(task_id="b")
        r1.steps.append(StepResult(agent="x", success=True))
        assert len(r2.steps) == 0, "Mutable default must not be shared"

    def test_with_steps(self):
        """Steps list populated correctly."""
        step1 = StepResult(agent="sayohmy", success=True, duration_seconds=1.2)
        step2 = StepResult(agent="sentinel", success=True, duration_seconds=0.5)
        result = PipelineResult(
            task_id="test-001",
            status=TaskStatus.COMPLETED,
            steps=[step1, step2],
            metrics={"coverage_pct": 0.85},
            duration_seconds=1.7,
        )
        assert len(result.steps) == 2
        assert result.steps[0].agent == "sayohmy"
        assert result.steps[1].agent == "sentinel"
        assert result.metrics["coverage_pct"] == 0.85
