"""Prometheus exporter — text format metrics for scraping.

Generates Prometheus-compatible text output for /metrics endpoint.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class PrometheusExporter:
    """Generates Prometheus text-format metrics.

    Collects metrics from various Luna subsystems and formats them
    for Prometheus scraping.
    """

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._metrics: dict[str, tuple[str, str, float]] = {}  # name -> (help, type, value)

    def gauge(self, name: str, value: float, help_text: str = "") -> None:
        """Set a gauge metric.

        Args:
            name: Metric name (will be prefixed with luna_).
            value: Current value.
            help_text: Description for the metric.
        """
        full_name = f"luna_{name}"
        self._metrics[full_name] = (help_text, "gauge", value)

    def counter(self, name: str, value: float, help_text: str = "") -> None:
        """Set a counter metric.

        Args:
            name: Metric name (will be prefixed with luna_).
            value: Current value (monotonically increasing).
            help_text: Description for the metric.
        """
        full_name = f"luna_{name}"
        self._metrics[full_name] = (help_text, "counter", value)

    def export(self) -> str:
        """Export all metrics in Prometheus text format.

        Returns:
            Prometheus-compatible text output.
        """
        if not self._enabled:
            return ""

        lines: list[str] = []
        for name, (help_text, metric_type, value) in sorted(self._metrics.items()):
            if help_text:
                lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} {metric_type}")
            lines.append(f"{name} {value}")

        return "\n".join(lines) + "\n" if lines else ""

    def update_from_vitals(self, vitals: dict) -> None:
        """Update metrics from a VitalSigns-like dict.

        Args:
            vitals: Dictionary with vital signs data.
        """
        if "overall_vitality" in vitals:
            self.gauge("vitality", vitals["overall_vitality"], "Overall vitality score")
        if "identity_drift" in vitals:
            self.gauge("identity_drift", vitals["identity_drift"], "Identity drift from psi0")
        if "quality_score" in vitals:
            self.gauge("quality_score", vitals["quality_score"], "Code quality score")
        if "phi_iit" in vitals:
            self.gauge("phi_iit", vitals["phi_iit"], "PHI IIT consciousness measure")
        if "idle_steps" in vitals:
            self.counter("idle_steps_total", vitals["idle_steps"], "Total idle steps")

    def update_from_health(self, health_score: float) -> None:
        """Update metrics from health data.

        Args:
            health_score: Current health score.
        """
        self.gauge("health_score", health_score, "PHI-weighted health score")

    def clear(self) -> None:
        """Clear all metrics."""
        self._metrics.clear()

    def get_status(self) -> dict:
        """Return current exporter status."""
        return {
            "enabled": self._enabled,
            "metric_count": len(self._metrics),
        }
