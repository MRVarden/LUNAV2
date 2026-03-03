"""Watermark — subtle marking in generated code.

Stub implementation for Phase 4.2. Will be expanded to embed
identity markers in code comments, variable names, or formatting
choices in a way that is detectable but not intrusive.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class Watermark:
    """Subtle identity marker embedded in generated code.

    Currently a stub — returns content unchanged.
    Future implementation will embed Phi-derived patterns.
    """

    def __init__(self, enabled: bool = False) -> None:
        self._enabled = enabled

    def apply(self, content: str, agent_name: str = "LUNA") -> str:
        """Apply watermark to generated content.

        Args:
            content: The code or text to watermark.
            agent_name: Name of the generating agent.

        Returns:
            Watermarked content (currently unchanged).
        """
        if not self._enabled:
            return content

        log.debug("Watermark: stub — returning content unchanged")
        return content

    def detect(self, content: str) -> bool:
        """Detect if content contains a Luna watermark.

        Args:
            content: The code or text to check.

        Returns:
            True if watermark detected (currently always False).
        """
        return False
