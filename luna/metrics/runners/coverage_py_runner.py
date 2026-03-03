"""Coverage.py runner — Python branch coverage analysis.

Calls `coverage json` and parses the JSON report.
Maps to the 'coverage_pct' canonical metric.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import tempfile
from pathlib import Path

from luna.metrics.base_runner import BaseRunner, RawMetrics

log = logging.getLogger(__name__)


class CoveragePyRunner(BaseRunner):
    """Python branch coverage analysis via coverage.py.

    Reads existing coverage data if available, or reports unavailable.
    Requires 'coverage' to be installed: pip install coverage.
    """

    def __init__(self, timeout: float = 60.0) -> None:
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "coverage_py"

    @property
    def language(self) -> str:
        return "python"

    @property
    def _tool_binary(self) -> str | None:
        return "coverage"

    async def run(self, path: Path) -> RawMetrics:
        """Extract coverage data from existing coverage report.

        Looks for .coverage data file in the project directory and
        generates a JSON report from it. Does NOT run tests — only reads
        existing coverage data.

        Returns RawMetrics with data keys:
            covered_lines: Total lines covered.
            total_lines: Total executable lines.
            coverage_pct: Coverage percentage [0, 100].
            covered_branches: Total branches covered (if branch coverage).
            total_branches: Total branches.
            branch_coverage_pct: Branch coverage percentage [0, 100].
            files_covered: Number of files with coverage data.
        """
        if not path.exists():
            return self._make_error(path, f"Path does not exist: {path}")

        # Find the .coverage file
        coverage_file = self._find_coverage_file(path)
        if coverage_file is None:
            return RawMetrics(
                runner_name=self.name,
                language=self.language,
                path=str(path),
                data={"coverage_pct": 0.0, "note": "No .coverage data file found"},
                errors=[],
                success=True,
            )

        try:
            data = await self._extract_coverage(coverage_file, path)
            return RawMetrics(
                runner_name=self.name,
                language=self.language,
                path=str(path),
                data=data,
                errors=[],
                success=True,
            )
        except Exception as exc:
            return self._make_error(path, f"Coverage extraction error: {exc}")

    def _find_coverage_file(self, path: Path) -> Path | None:
        """Find .coverage data file in the project tree."""
        # Check path itself, then parent directories
        search = path if path.is_dir() else path.parent
        for directory in [search] + list(search.parents):
            candidate = directory / ".coverage"
            if candidate.exists():
                return candidate
            # Stop at home directory
            if directory == directory.parent:
                break
        return None

    async def _extract_coverage(self, coverage_file: Path, project_path: Path) -> dict:
        """Generate JSON report from .coverage and parse it."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            json_path = tmp.name

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [
                    "coverage", "json",
                    f"--data-file={coverage_file}",
                    f"-o", json_path,
                ],
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=str(project_path if project_path.is_dir() else project_path.parent),
            )

            if result.returncode != 0:
                return {
                    "coverage_pct": 0.0,
                    "error": f"coverage json exit {result.returncode}: {result.stderr.strip()}",
                }

            report_path = Path(json_path)
            if not report_path.exists():
                return {"coverage_pct": 0.0, "error": "No JSON report generated"}

            report = json.loads(report_path.read_text(encoding="utf-8"))
            totals = report.get("totals", {})

            return {
                "covered_lines": totals.get("covered_lines", 0),
                "total_lines": totals.get("num_statements", 0),
                "coverage_pct": totals.get("percent_covered", 0.0),
                "covered_branches": totals.get("covered_branches", 0),
                "total_branches": totals.get("num_branches", 0),
                "branch_coverage_pct": totals.get("percent_covered_branches", 0.0),
                "files_covered": len(report.get("files", {})),
            }
        finally:
            Path(json_path).unlink(missing_ok=True)
