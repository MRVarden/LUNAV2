"""Session 2 -- TaskDetector: 18 tests for intent detection from chat messages.

Validates strong/weak signal matching, confidence scoring, target path
extraction, and TaskIntent field correctness. No I/O, no mocks needed --
TaskDetector is a pure function from string to TaskIntent|None.
"""

from __future__ import annotations

import pytest

from luna.pipeline.detector import (
    TaskDetector,
    _DETECTION_THRESHOLD,
    _EXTRA_STRONG_SCORE,
    _FIRST_STRONG_SCORE,
    _WEAK_SCORE,
)
from luna.pipeline.task import TaskIntent, TaskType


@pytest.fixture
def detector() -> TaskDetector:
    """Fresh TaskDetector for each test -- stateless, so sharing is safe."""
    return TaskDetector()


# =====================================================================
#  I. STRONG SIGNAL DETECTION
# =====================================================================


class TestDetectStrong:
    """Verify that strong action verbs map to the correct TaskType.

    Each test uses a full sentence to exercise whole-word matching and
    case-insensitive tokenization.  The message must have enough strong
    signals (>= 2) or weak bonus to cross the 0.5 threshold.
    """

    def test_detect_generate_fr(self, detector: TaskDetector) -> None:
        """FR 'genere' + weak 'module' pushes past threshold -> GENERATE."""
        intent = detector.detect("genere un module de test")
        assert intent is not None, "Expected GENERATE intent for 'genere un module de test'"
        assert intent.task_type == TaskType.GENERATE

    def test_detect_generate_en(self, detector: TaskDetector) -> None:
        """EN 'create' + 'write' (two strong) -> GENERATE."""
        intent = detector.detect("create and write a new parser module")
        assert intent is not None, "Expected GENERATE intent"
        assert intent.task_type == TaskType.GENERATE

    def test_detect_improve_fr(self, detector: TaskDetector) -> None:
        """FR 'ameliore' + weak 'performance' + 'code' -> IMPROVE."""
        intent = detector.detect("ameliore la performance du code heartbeat")
        assert intent is not None, "Expected IMPROVE intent"
        assert intent.task_type == TaskType.IMPROVE

    def test_detect_improve_en(self, detector: TaskDetector) -> None:
        """EN 'optimize' + weak 'performance' -> IMPROVE."""
        intent = detector.detect("optimize the performance of the pipeline")
        assert intent is not None, "Expected IMPROVE intent"
        assert intent.task_type == TaskType.IMPROVE

    def test_detect_fix_fr(self, detector: TaskDetector) -> None:
        """FR 'corrige' + weak 'module' + 'code' -> FIX."""
        intent = detector.detect("corrige le bug dans le module code session")
        assert intent is not None, "Expected FIX intent"
        assert intent.task_type == TaskType.FIX

    def test_detect_fix_en(self, detector: TaskDetector) -> None:
        """EN 'fix' + 'debug' (two strong) -> FIX."""
        intent = detector.detect("fix and debug the crash in pipeline")
        assert intent is not None, "Expected FIX intent"
        assert intent.task_type == TaskType.FIX

    def test_detect_refactor(self, detector: TaskDetector) -> None:
        """EN 'refactor' + weak 'module' + 'code' -> REFACTOR."""
        intent = detector.detect("refactor the config module code")
        assert intent is not None, "Expected REFACTOR intent"
        assert intent.task_type == TaskType.REFACTOR

    def test_detect_measure(self, detector: TaskDetector) -> None:
        """FR 'mesure' + weak 'qualite' + 'code' -> MEASURE."""
        intent = detector.detect("mesure la qualite du code")
        assert intent is not None, "Expected MEASURE intent"
        assert intent.task_type == TaskType.MEASURE

    def test_detect_test(self, detector: TaskDetector) -> None:
        """FR 'teste' + weak 'module' + 'code' -> TEST."""
        intent = detector.detect("teste le module code du chat")
        assert intent is not None, "Expected TEST intent"
        assert intent.task_type == TaskType.TEST

    def test_detect_audit(self, detector: TaskDetector) -> None:
        """FR 'audite' + weak 'securite' + 'code' -> AUDIT."""
        intent = detector.detect("audite la securite du code systeme")
        assert intent is not None, "Expected AUDIT intent"
        assert intent.task_type == TaskType.AUDIT


# =====================================================================
#  II. NO MATCH CASES
# =====================================================================


class TestDetectNoMatch:
    """Verify that non-task messages return None (false-negative is OK)."""

    def test_no_match_greeting(self, detector: TaskDetector) -> None:
        """Simple greeting -- no strong signal at all -> None."""
        assert detector.detect("bonjour Luna") is None

    def test_no_match_question(self, detector: TaskDetector) -> None:
        """Casual question with no action verb -> None."""
        assert detector.detect("comment vas-tu aujourd'hui?") is None

    def test_no_match_short(self, detector: TaskDetector) -> None:
        """Very short input with no signal -> None."""
        assert detector.detect("ok") is None


# =====================================================================
#  III. CONFIDENCE SCORING
# =====================================================================


class TestConfidence:
    """Verify the confidence formula: 0.4 first + 0.1/extra + 0.05/weak."""

    def test_multiple_strong_increases_confidence(self, detector: TaskDetector) -> None:
        """Two strong signals score higher than one strong + one weak."""
        intent_two_strong = detector.detect("create and write a new module")
        assert intent_two_strong is not None
        # 0.4 (first 'create') + 0.1 ('write') + 0.05 ('module') = 0.55
        assert intent_two_strong.confidence >= _FIRST_STRONG_SCORE + _EXTRA_STRONG_SCORE

    def test_weak_signals_add_bonus(self, detector: TaskDetector) -> None:
        """Weak nouns (code, module, performance) increase confidence."""
        intent = detector.detect("ameliore le code du module pour la performance")
        assert intent is not None
        # 0.4 (ameliore) + 0.05*3 (code, module, performance) = 0.55
        expected_min = _FIRST_STRONG_SCORE + 3 * _WEAK_SCORE
        assert intent.confidence >= expected_min, (
            f"Expected confidence >= {expected_min}, got {intent.confidence}"
        )

    def test_below_threshold_returns_none(self, detector: TaskDetector) -> None:
        """A single strong signal alone (0.4) is below threshold (0.5) -> None.

        NOTE: Whether this returns None depends on whether the sentence
        also contains weak signals. We use a minimal sentence.
        """
        # 'analyse' is a strong signal (MEASURE) worth 0.4.
        # No weak nouns in the rest -> 0.4 < 0.5 -> None.
        result = detector.detect("analyse bien tout")
        # 0.4 for 'analyse', no weak -> 0.4 < 0.5 -> None
        assert result is None, (
            f"Expected None for single strong signal without weak bonus, "
            f"got confidence={getattr(result, 'confidence', '?')}"
        )


# =====================================================================
#  IV. TARGET PATH EXTRACTION
# =====================================================================


class TestTargetExtraction:
    """Verify _extract_target regex finds Python-ish file paths."""

    def test_extracts_python_path(self, detector: TaskDetector) -> None:
        """A Python file path in the message is extracted."""
        intent = detector.detect("ameliore le code du module luna/chat/session.py")
        assert intent is not None
        assert intent.target_path == "luna/chat/session.py"

    def test_no_path_returns_empty(self, detector: TaskDetector) -> None:
        """When no file path is present, target_path is empty string."""
        intent = detector.detect("ameliore le code du module chat")
        assert intent is not None
        assert intent.target_path == ""


# =====================================================================
#  V. TASKINTENT FIELDS
# =====================================================================


class TestTaskIntentFields:
    """Verify the TaskIntent dataclass structure."""

    def test_intent_has_correct_fields(self, detector: TaskDetector) -> None:
        """TaskIntent carries all expected fields from detection."""
        intent = detector.detect("genere un nouveau module de code")
        assert intent is not None

        # task_type
        assert isinstance(intent.task_type, TaskType)
        # description is the original message, stripped
        assert intent.description == "genere un nouveau module de code"
        # language defaults to python
        assert intent.language == "python"
        # confidence is a float in (0, 1]
        assert 0.0 < intent.confidence <= 1.0
        # signals is a tuple of matched strong signal tokens
        assert isinstance(intent.signals, tuple)
        assert len(intent.signals) >= 1
        # target_path is a string (possibly empty)
        assert isinstance(intent.target_path, str)

    def test_intent_is_frozen(self) -> None:
        """TaskIntent is immutable (frozen=True)."""
        intent = TaskIntent(
            task_type=TaskType.FIX,
            description="test",
            confidence=0.5,
            signals=("fix",),
        )
        with pytest.raises(AttributeError):
            intent.task_type = TaskType.AUDIT  # type: ignore[misc]
