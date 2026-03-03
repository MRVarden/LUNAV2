"""Radon runner — Python cyclomatic + cognitive complexity analysis.

Calls `radon cc --json` and `radon mi --json` via subprocess.
Maps to the 'complexity_score' canonical metric.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from pathlib import Path

from luna.metrics.base_runner import BaseRunner, RawMetrics

log = logging.getLogger(__name__)


class RadonRunner(BaseRunner):
    """Python complexity analysis via radon.

    Measures cyclomatic complexity (CC) and maintainability index (MI).
    Requires 'radon' to be installed: pip install radon.
    """

    def __init__(self, timeout: float = 60.0) -> None:
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "radon"

    @property
    def language(self) -> str:
        return "python"

    @property
    def _tool_binary(self) -> str | None:
        return "radon"

    async def run(self, path: Path) -> RawMetrics:
        """Run radon CC and MI on the given path.

        Returns RawMetrics with data keys:
            cc_average: Average cyclomatic complexity across all functions.
            cc_max: Maximum cyclomatic complexity found.
            cc_total: Total cyclomatic complexity.
            cc_count: Number of functions/methods analyzed.
            mi_average: Average maintainability index.
            mi_scores: Dict of file -> MI score.
        """
        if not path.exists():
            return self._make_error(path, f"Path does not exist: {path}")

        cc_data = await self._run_cc(path)
        mi_data = await self._run_mi(path)

        errors = cc_data.get("errors", []) + mi_data.get("errors", [])
        success = cc_data.get("success", False) or mi_data.get("success", False)

        merged = {}
        merged.update(cc_data.get("data", {}))
        merged.update(mi_data.get("data", {}))

        return RawMetrics(
            runner_name=self.name,
            language=self.language,
            path=str(path),
            data=merged,
            errors=errors,
            success=success,
        )

    async def _run_cc(self, path: Path) -> dict:
        """Run radon cyclomatic complexity analysis."""
        try:
            target = str(path)
            args = ["radon", "cc", "--json", "--average", target]
            result = await asyncio.to_thread(
                subprocess.run,
                args,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "errors": [f"radon cc exit code {result.returncode}: {result.stderr.strip()}"],
                    "data": {},
                }

            parsed = json.loads(result.stdout) if result.stdout.strip() else {}
            cc_values = []

            for _file, blocks in parsed.items():
                if isinstance(blocks, list):
                    for block in blocks:
                        if isinstance(block, dict) and "complexity" in block:
                            cc_values.append(block["complexity"])

            data = {
                "cc_average": sum(cc_values) / len(cc_values) if cc_values else 0.0,
                "cc_max": max(cc_values) if cc_values else 0,
                "cc_total": sum(cc_values),
                "cc_count": len(cc_values),
            }

            return {"success": True, "errors": [], "data": data}

        except subprocess.TimeoutExpired:
            return {"success": False, "errors": ["radon cc timed out"], "data": {}}
        except (json.JSONDecodeError, OSError) as exc:
            return {"success": False, "errors": [f"radon cc error: {exc}"], "data": {}}

    async def _run_mi(self, path: Path) -> dict:
        """Run radon maintainability index analysis."""
        try:
            target = str(path)
            args = ["radon", "mi", "--json", target]
            result = await asyncio.to_thread(
                subprocess.run,
                args,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "errors": [f"radon mi exit code {result.returncode}: {result.stderr.strip()}"],
                    "data": {},
                }

            parsed = json.loads(result.stdout) if result.stdout.strip() else {}
            mi_scores = {}
            mi_values = []

            for file_path, score in parsed.items():
                if isinstance(score, (int, float)):
                    mi_scores[file_path] = score
                    mi_values.append(score)
                elif isinstance(score, dict) and "mi" in score:
                    mi_scores[file_path] = score["mi"]
                    mi_values.append(score["mi"])

            data = {
                "mi_average": sum(mi_values) / len(mi_values) if mi_values else 0.0,
                "mi_scores": mi_scores,
            }

            return {"success": True, "errors": [], "data": data}

        except subprocess.TimeoutExpired:
            return {"success": False, "errors": ["radon mi timed out"], "data": {}}
        except (json.JSONDecodeError, OSError) as exc:
            return {"success": False, "errors": [f"radon mi error: {exc}"], "data": {}}
