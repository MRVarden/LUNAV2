"""Base metric runner — abstract interface for deterministic code analysis tools.

NEVER uses LLM estimation. Every runner calls a real external tool
(radon, ast, coverage.py, clippy, etc.) via subprocess or stdlib.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RawMetrics:
    """Raw output from a single metrics runner.

    Contains structured data from the tool before normalization.
    The normalizer converts these to [0, 1] per the 7 canonical METRIC_NAMES.

    Attributes:
        runner_name: Unique runner identifier (e.g. 'radon', 'ast').
        language: Language this runner targets (e.g. 'python', 'rust').
        path: The path that was analyzed.
        data: Tool-specific key/value results.
        errors: Any errors encountered during analysis.
        success: Whether the runner completed without fatal errors.
    """

    runner_name: str
    language: str
    path: str
    data: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    success: bool = True


class BaseRunner(ABC):
    """Abstract interface: run(path) -> RawMetrics.

    All runners must:
    - Be deterministic (same input -> same output).
    - Use asyncio.to_thread for subprocess calls to avoid blocking.
    - Return RawMetrics(success=False) on tool failure (never raise).
    - Implement is_available() to check if the backing tool is installed.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique runner identifier (e.g. 'radon', 'ast', 'coverage_py')."""

    @property
    @abstractmethod
    def language(self) -> str:
        """Language this runner targets (e.g. 'python', 'rust', 'java')."""

    @abstractmethod
    async def run(self, path: Path) -> RawMetrics:
        """Execute the tool on the given path and return raw metrics.

        Must be deterministic. Uses asyncio.to_thread for subprocess calls.
        Returns RawMetrics with success=False on tool failure (never raises).
        """

    async def is_available(self) -> bool:
        """Check if the backing tool is installed and accessible.

        Default implementation checks if the tool binary exists in PATH.
        Override for runners that use stdlib modules (e.g. ast_runner).
        """
        tool = self._tool_binary
        if tool is None:
            return True  # No external tool needed (stdlib-based)

        available = await asyncio.to_thread(shutil.which, tool)
        if available is None:
            log.debug("Tool '%s' not found in PATH for runner '%s'", tool, self.name)
            return False
        return True

    @property
    def _tool_binary(self) -> str | None:
        """Name of the external binary this runner needs. None for stdlib-based."""
        return None

    def _make_error(self, path: Path, error_msg: str) -> RawMetrics:
        """Convenience: create a failed RawMetrics result."""
        return RawMetrics(
            runner_name=self.name,
            language=self.language,
            path=str(path),
            data={},
            errors=[error_msg],
            success=False,
        )
