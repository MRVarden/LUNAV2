"""AST runner — Python AST analysis for structure and entity metrics.

Uses Python's built-in ast module (no external tool needed).
Maps to 'abstraction_ratio', 'function_size_score', and 'test_ratio'.
"""

from __future__ import annotations

import ast
import asyncio
import logging
from pathlib import Path

from luna_common.phi_engine.soft_constraint import function_size_score

from luna.metrics.base_runner import BaseRunner, RawMetrics

log = logging.getLogger(__name__)


class AstRunner(BaseRunner):
    """Python AST analysis using stdlib ast module.

    Extracts structural metrics: entity counts, function sizes,
    abstraction ratio, and test file detection.
    No external tool required.
    """

    @property
    def name(self) -> str:
        return "ast"

    @property
    def language(self) -> str:
        return "python"

    @property
    def _tool_binary(self) -> str | None:
        return None  # stdlib-based

    async def run(self, path: Path) -> RawMetrics:
        """Analyze Python files at the given path using ast module.

        Returns RawMetrics with data keys:
            total_files: Number of Python files analyzed.
            test_files: Number of test files (test_*.py or *_test.py).
            source_files: Number of non-test Python files.
            total_classes: Total class definitions.
            total_functions: Total function/method definitions.
            total_entities: total_classes + total_functions.
            abstraction_ratio: classes / total_entities (0 if no entities).
            avg_function_lines: Average function body size in lines.
            function_size_quality: Score from function_size_score().
            test_ratio: test_files / source_files (0 if no source files).
        """
        if not path.exists():
            return self._make_error(path, f"Path does not exist: {path}")

        try:
            data = await asyncio.to_thread(self._analyze_path, path)
            return RawMetrics(
                runner_name=self.name,
                language=self.language,
                path=str(path),
                data=data,
                errors=[],
                success=True,
            )
        except Exception as exc:
            return self._make_error(path, f"AST analysis error: {exc}")

    def _analyze_path(self, path: Path) -> dict:
        """Synchronous AST analysis (run via to_thread)."""
        py_files = self._collect_python_files(path)
        if not py_files:
            return self._empty_data()

        total_classes = 0
        total_functions = 0
        function_sizes: list[int] = []
        test_files = 0
        source_files = 0

        for py_file in py_files:
            is_test = self._is_test_file(py_file)
            if is_test:
                test_files += 1
            else:
                source_files += 1

            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    total_classes += 1
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    total_functions += 1
                    size = self._function_body_lines(node)
                    function_sizes.append(size)

        total_entities = total_classes + total_functions
        avg_lines = sum(function_sizes) / len(function_sizes) if function_sizes else 0.0

        return {
            "total_files": len(py_files),
            "test_files": test_files,
            "source_files": source_files,
            "total_classes": total_classes,
            "total_functions": total_functions,
            "total_entities": total_entities,
            "abstraction_ratio": total_classes / total_entities if total_entities > 0 else 0.0,
            "avg_function_lines": avg_lines,
            "function_size_quality": function_size_score(avg_lines),
            "test_ratio": test_files / source_files if source_files > 0 else 0.0,
        }

    def _collect_python_files(self, path: Path) -> list[Path]:
        """Collect all .py files from a path (file or directory)."""
        if path.is_file() and path.suffix == ".py":
            return [path]
        if path.is_dir():
            return sorted(path.rglob("*.py"))
        return []

    def _is_test_file(self, path: Path) -> bool:
        """Check if a file is a test file by name convention."""
        name = path.stem
        return name.startswith("test_") or name.endswith("_test") or "conftest" in name

    def _function_body_lines(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
        """Count lines in a function body."""
        if not node.body:
            return 0
        first_line = node.body[0].lineno
        last_line = max(
            getattr(child, "end_lineno", child.lineno)
            for child in ast.walk(node)
            if hasattr(child, "lineno")
        )
        return max(1, last_line - first_line + 1)

    def _empty_data(self) -> dict:
        """Return empty metrics when no Python files are found."""
        return {
            "total_files": 0,
            "test_files": 0,
            "source_files": 0,
            "total_classes": 0,
            "total_functions": 0,
            "total_entities": 0,
            "abstraction_ratio": 0.0,
            "avg_function_lines": 0.0,
            "function_size_quality": 0.0,
            "test_ratio": 0.0,
        }
