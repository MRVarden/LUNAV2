"""TaskDetector — detect pipeline intent from chat messages.

Scans French + English chat messages for strong signals (action verbs)
and weak signals (contextual nouns) to determine if the user is requesting
a pipeline action. Conservative: prefers false negatives over false positives.
"""

from __future__ import annotations

import logging
import re

from luna.pipeline.task import TaskIntent, TaskType

log = logging.getLogger(__name__)

# Strong signals: action verbs that map directly to a TaskType.
# Match is case-insensitive, must be whole word.
_STRONG_SIGNALS: dict[str, TaskType] = {
    # GENERATE
    "genere": TaskType.GENERATE,
    "génère": TaskType.GENERATE,
    "generer": TaskType.GENERATE,
    "générer": TaskType.GENERATE,
    "cree": TaskType.GENERATE,
    "crée": TaskType.GENERATE,
    "créer": TaskType.GENERATE,
    "generate": TaskType.GENERATE,
    "create": TaskType.GENERATE,
    "write": TaskType.GENERATE,
    "ecris": TaskType.GENERATE,
    "écris": TaskType.GENERATE,
    # IMPROVE
    "ameliore": TaskType.IMPROVE,
    "améliore": TaskType.IMPROVE,
    "ameliorer": TaskType.IMPROVE,
    "améliorer": TaskType.IMPROVE,
    "improve": TaskType.IMPROVE,
    "optimize": TaskType.IMPROVE,
    "optimise": TaskType.IMPROVE,
    "enhance": TaskType.IMPROVE,
    # FIX
    "corrige": TaskType.FIX,
    "corriger": TaskType.FIX,
    "repare": TaskType.FIX,
    "répare": TaskType.FIX,
    "fix": TaskType.FIX,
    "repair": TaskType.FIX,
    "debug": TaskType.FIX,
    # REFACTOR
    "refactor": TaskType.REFACTOR,
    "refactorise": TaskType.REFACTOR,
    "restructure": TaskType.REFACTOR,
    "reorganise": TaskType.REFACTOR,
    "reorganize": TaskType.REFACTOR,
    # MEASURE
    "mesure": TaskType.MEASURE,
    "mesurer": TaskType.MEASURE,
    "measure": TaskType.MEASURE,
    "analyse": TaskType.MEASURE,
    "analyze": TaskType.MEASURE,
    "scan": TaskType.MEASURE,
    # TEST
    "teste": TaskType.TEST,
    "tester": TaskType.TEST,
    "test": TaskType.TEST,
    "validate": TaskType.TEST,
    "valide": TaskType.TEST,
    "valider": TaskType.TEST,
    # AUDIT
    "audite": TaskType.AUDIT,
    "auditer": TaskType.AUDIT,
    "audit": TaskType.AUDIT,
    "verifie": TaskType.AUDIT,
    "vérifie": TaskType.AUDIT,
    "verify": TaskType.AUDIT,
    "securise": TaskType.AUDIT,
    "sécurise": TaskType.AUDIT,
}

# Weak signals: contextual nouns that increase confidence but don't
# determine task type alone.
_WEAK_SIGNALS: frozenset[str] = frozenset({
    "code", "module", "fonction", "function", "classe", "class",
    "fichier", "file", "pipeline", "agent", "performance",
    "securite", "sécurité", "security", "couverture", "coverage",
    "complexite", "complexité", "complexity", "qualite", "qualité",
    "quality",
})

# Confidence scoring thresholds.
_DETECTION_THRESHOLD = 0.5
_FIRST_STRONG_SCORE = 0.4
_EXTRA_STRONG_SCORE = 0.1
_WEAK_SCORE = 0.05

# Target path extraction: matches Python-ish file paths.
_PATH_RE = re.compile(
    r'(?:^|\s)((?:[\w./~-]+/)*[\w-]+\.(?:py|toml|json|yaml|yml|cfg|ini))\b'
)


class TaskDetector:
    """Detect pipeline task intent from a chat message.

    Conservative: threshold is 0.5, prefers false negatives.
    Only the FIRST strong signal determines the task type.
    """

    def detect(self, message: str) -> TaskIntent | None:
        """Analyze a message and return a TaskIntent if confident enough.

        Returns None if confidence is below threshold (0.5).
        """
        lower = message.lower()
        tokens = set(re.findall(r'[a-zA-ZÀ-ÿ]{2,}', lower))

        # Find strong signals.
        strong_matches: list[tuple[str, TaskType]] = []
        for signal, task_type in _STRONG_SIGNALS.items():
            if signal in tokens:
                strong_matches.append((signal, task_type))

        if not strong_matches:
            return None

        # First strong signal determines task type.
        task_type = strong_matches[0][1]

        # Confidence scoring.
        confidence = _FIRST_STRONG_SCORE
        confidence += (len(strong_matches) - 1) * _EXTRA_STRONG_SCORE

        # Weak signal bonus.
        weak_count = sum(1 for s in _WEAK_SIGNALS if s in tokens)
        confidence += weak_count * _WEAK_SCORE

        # Cap at 1.0.
        confidence = min(1.0, confidence)

        if confidence < _DETECTION_THRESHOLD:
            return None

        # Extract target path if present.
        target_path = self._extract_target(message)

        # Collect signal names for traceability.
        signals = tuple(s for s, _ in strong_matches)

        return TaskIntent(
            task_type=task_type,
            description=message.strip(),
            target_path=target_path,
            language="python",
            confidence=confidence,
            signals=signals,
        )

    @staticmethod
    def _extract_target(message: str) -> str:
        """Extract a file path from the message, or empty string."""
        match = _PATH_RE.search(message)
        return match.group(1) if match else ""
