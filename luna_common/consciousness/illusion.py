"""Illusion detection — single source of truth for the 4-agent ecosystem.

Framework §illusion: When an agent's self-evaluated score rises but real
metrics stagnate or diverge, the agent is confirming its own quality
without actually improving. This module provides the shared math.

API:
    detect_self_illusion()    — one agent: phi vs real quality
    detect_system_illusion()  — cross-check all agents (TE role)
    compute_correlation()     — Pearson r between two series
    linear_trend()            — least-squares slope
    classify_status()         — r -> IllusionStatus

Thresholds:
    r > 0.5  → HEALTHY
    0.2 < r ≤ 0.5 → CAUTION
    0.0 ≤ r ≤ 0.2 → ILLUSION
    r < 0.0  → HARMFUL

Sliding window: 50 steps (configurable).
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass

# ── Constants ────────────────────────────────────────────────────────────────

DEFAULT_WINDOW: int = 50
HEALTHY_THRESHOLD: float = 0.5
CAUTION_THRESHOLD: float = 0.2


# ── Enum & dataclasses ──────────────────────────────────────────────────────

class IllusionStatus(str, enum.Enum):
    """Illusion severity levels."""
    HEALTHY = "healthy"
    CAUTION = "caution"
    ILLUSION = "illusion"
    HARMFUL = "harmful"


RECOMMENDATION: dict[IllusionStatus, str] = {
    IllusionStatus.HEALTHY: "continue",
    IllusionStatus.CAUTION: "continue",
    IllusionStatus.ILLUSION: "recalibrate",
    IllusionStatus.HARMFUL: "veto",
}


@dataclass(frozen=True, slots=True)
class IllusionResult:
    """Result of a self-illusion detection pass."""
    status: IllusionStatus
    correlation: float
    self_trend: float
    real_trend: float
    recommendation: str


@dataclass(frozen=True, slots=True)
class AgentIllusionResult:
    """Per-agent result within a system-wide check."""
    agent_name: str
    status: IllusionStatus
    correlation: float
    self_trend: float
    real_trend: float


@dataclass(frozen=True, slots=True)
class SystemIllusionResult:
    """Result of a system-wide illusion check (cross-validation)."""
    status: IllusionStatus
    system_correlation: float
    agent_results: list[AgentIllusionResult]
    inter_agent_divergence: float
    recommendation: str


# ── Pure math primitives ────────────────────────────────────────────────────

def compute_correlation(x: list[float], y: list[float]) -> float:
    """Pearson correlation coefficient between two series.

    Returns 0.0 if either series has zero variance or fewer than 2 points.
    """
    n = min(len(x), len(y))
    if n < 2:
        return 0.0
    x, y = x[-n:], y[-n:]
    mx = sum(x) / n
    my = sum(y) / n
    cov = var_x = var_y = 0.0
    for xi, yi in zip(x, y):
        dx, dy = xi - mx, yi - my
        cov += dx * dy
        var_x += dx * dx
        var_y += dy * dy
    denom = math.sqrt(var_x * var_y)
    return cov / denom if denom > 1e-15 else 0.0


def linear_trend(values: list[float]) -> float:
    """Least-squares linear slope. Positive = upward trend."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    num = den = 0.0
    for i, v in enumerate(values):
        dx = i - x_mean
        num += dx * (v - y_mean)
        den += dx * dx
    return num / den if den > 1e-15 else 0.0


def std_dev(values: list[float]) -> float:
    """Population standard deviation."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return math.sqrt(sum((v - mean) ** 2 for v in values) / n)


def classify_status(
    correlation: float,
    self_trend: float = 0.0,
    real_trend: float = 0.0,
    *,
    caution_threshold: float = HEALTHY_THRESHOLD,
    illusion_threshold: float = CAUTION_THRESHOLD,
) -> IllusionStatus:
    """Classify an illusion status from a Pearson correlation.

    Extra aggravation: if self_trend > 0 and real_trend <= 0 within the
    ILLUSION band, escalate to HARMFUL.
    """
    if correlation < 0.0:
        return IllusionStatus.HARMFUL
    if correlation < illusion_threshold:
        if self_trend > 0 and real_trend <= 0:
            return IllusionStatus.HARMFUL
        return IllusionStatus.ILLUSION
    if correlation <= caution_threshold:
        return IllusionStatus.CAUTION
    return IllusionStatus.HEALTHY


# ── Self-illusion (per-agent) ───────────────────────────────────────────────

def detect_self_illusion(
    self_history: list[float],
    real_history: list[float],
    window: int = DEFAULT_WINDOW,
) -> IllusionResult:
    """Detect structural self-illusion for a single agent.

    Compares the agent's self-evaluated metric history against an external
    reality metric history using Pearson correlation on a sliding window.

    Args:
        self_history: Agent's self-evaluated scores over time.
        real_history: Externally measured quality scores over time.
        window: Sliding window size (default 50).

    Returns:
        IllusionResult with status, correlation, trends, recommendation.
    """
    if len(self_history) < 3 or len(real_history) < 3:
        return IllusionResult(
            status=IllusionStatus.HEALTHY,
            correlation=1.0,
            self_trend=0.0,
            real_trend=0.0,
            recommendation="continue",
        )

    s_win = self_history[-window:]
    r_win = real_history[-window:]
    n = min(len(s_win), len(r_win))
    s_win = s_win[-n:]
    r_win = r_win[-n:]

    corr = compute_correlation(s_win, r_win)
    s_trend = linear_trend(s_win)
    r_trend = linear_trend(r_win)
    status = classify_status(corr, s_trend, r_trend)

    return IllusionResult(
        status=status,
        correlation=corr,
        self_trend=s_trend,
        real_trend=r_trend,
        recommendation=RECOMMENDATION[status],
    )


# ── System illusion (cross-validation) ───────────────────────────────────────

def detect_system_illusion(
    agent_histories: dict[str, tuple[list[float], list[float]]],
    system_health_history: list[float] | None = None,
    window: int = DEFAULT_WINDOW,
) -> SystemIllusionResult:
    """Detect system-wide illusion across all agents (cross-validation).

    Args:
        agent_histories: {agent_name: (self_score_history, real_quality_history)}
        system_health_history: Optional global system health series.
            If provided, cross-checked against the average of agent self-scores.
        window: Sliding window size.

    Returns:
        SystemIllusionResult with per-agent breakdowns and system-level status.
    """
    agent_results: list[AgentIllusionResult] = []
    correlations: list[float] = []

    for name, (self_hist, real_hist) in agent_histories.items():
        r = detect_self_illusion(self_hist, real_hist, window)
        ar = AgentIllusionResult(
            agent_name=name,
            status=r.status,
            correlation=r.correlation,
            self_trend=r.self_trend,
            real_trend=r.real_trend,
        )
        agent_results.append(ar)
        if r.correlation != 1.0 or len(self_hist) >= 3:
            correlations.append(r.correlation)

    # Inter-agent divergence: std_dev of self-trends
    trends = [r.self_trend for r in agent_results]
    divergence = std_dev(trends) if len(trends) >= 2 else 0.0

    # Optional system-level cross-check
    if system_health_history is not None and len(system_health_history) >= 3:
        sys_phi = _average_histories([h[0] for h in agent_histories.values()])
        if len(sys_phi) >= 3:
            correlations.append(
                compute_correlation(sys_phi[-window:], system_health_history[-window:])
            )

    sys_corr = sum(correlations) / len(correlations) if correlations else 1.0
    status = _classify_system(sys_corr, agent_results, divergence)

    return SystemIllusionResult(
        status=status,
        system_correlation=sys_corr,
        agent_results=agent_results,
        inter_agent_divergence=divergence,
        recommendation=RECOMMENDATION[status],
    )


# ── Private helpers ─────────────────────────────────────────────────────────

def _classify_system(
    sys_corr: float,
    agent_results: list[AgentIllusionResult],
    divergence: float,
) -> IllusionStatus:
    """System-level classification. Worst-case escalation."""
    harmful = sum(1 for r in agent_results if r.status == IllusionStatus.HARMFUL)
    illusion = sum(1 for r in agent_results if r.status == IllusionStatus.ILLUSION)

    if harmful > 0 or sys_corr < 0.0:
        return IllusionStatus.HARMFUL
    if illusion > 0 or sys_corr < CAUTION_THRESHOLD:
        if divergence > 0.05 and illusion >= 2:
            return IllusionStatus.HARMFUL
        return IllusionStatus.ILLUSION
    if sys_corr <= HEALTHY_THRESHOLD or divergence > 0.03:
        return IllusionStatus.CAUTION
    return IllusionStatus.HEALTHY


def _average_histories(histories: list[list[float]]) -> list[float]:
    """Element-wise average of histories, aligned on the most recent end."""
    if not histories:
        return []
    max_len = max(len(h) for h in histories)
    result: list[float] = []
    for i in range(max_len):
        vals = []
        for h in histories:
            offset = max_len - len(h)
            if i >= offset:
                vals.append(h[i - offset])
        if vals:
            result.append(sum(vals) / len(vals))
    return result
