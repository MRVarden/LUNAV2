"""Sandbox — isolated execution environment.

Provides temporary directory isolation for benchmark tasks.
Cleans up after execution.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)


class Sandbox:
    """Temporary isolated execution environment.

    Creates a temporary directory for isolated task execution.
    Supports context manager protocol for automatic cleanup.
    """

    def __init__(self, prefix: str = "luna_sandbox_") -> None:
        self._prefix = prefix
        self._path: Path | None = None

    @property
    def path(self) -> Path | None:
        """Path to the sandbox directory (None if not created)."""
        return self._path

    def create(self) -> Path:
        """Create the sandbox directory.

        Returns:
            Path to the sandbox directory.
        """
        self._path = Path(tempfile.mkdtemp(prefix=self._prefix))
        log.debug("Sandbox created: %s", self._path)
        return self._path

    def destroy(self) -> None:
        """Destroy the sandbox directory."""
        if self._path is not None and self._path.exists():
            shutil.rmtree(self._path, ignore_errors=True)
            log.debug("Sandbox destroyed: %s", self._path)
            self._path = None

    def __enter__(self) -> Path:
        return self.create()

    def __exit__(self, *args: object) -> None:
        self.destroy()

    @property
    def exists(self) -> bool:
        """Whether the sandbox directory exists."""
        return self._path is not None and self._path.exists()
