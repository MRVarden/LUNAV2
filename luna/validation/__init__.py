"""Validation module — benchmark harness, sandbox, comparator.

Provides isolated benchmark execution, statistical comparison,
canary rollouts, and proof-of-performance export.
"""

from __future__ import annotations

from luna.validation.benchmark_harness import BenchmarkHarness, BenchmarkResult
from luna.validation.comparator import Comparator, ComparisonResult
from luna.validation.sandbox import Sandbox
from luna.validation.verdict import Verdict, VerdictCriterion, VerdictRunner
from luna.validation.verdict_tasks import (
    BenchmarkTask,
    get_all_tasks,
    get_categories,
    register_all_tasks,
)

__all__ = [
    "BenchmarkHarness",
    "BenchmarkResult",
    "BenchmarkTask",
    "Comparator",
    "ComparisonResult",
    "Sandbox",
    "Verdict",
    "VerdictCriterion",
    "VerdictRunner",
    "get_all_tasks",
    "get_categories",
    "register_all_tasks",
]
