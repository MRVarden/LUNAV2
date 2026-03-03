"""Tests for Prometheus exporter — text format metrics."""

from __future__ import annotations

import pytest

from luna.observability.prometheus_exporter import PrometheusExporter


class TestPrometheusExporter:
    """Tests for PrometheusExporter."""

    @pytest.fixture
    def exporter(self):
        return PrometheusExporter()

    def test_gauge(self, exporter):
        """Gauge metrics appear in output."""
        exporter.gauge("test_metric", 0.85, "A test metric")
        output = exporter.export()
        assert "# HELP luna_test_metric A test metric" in output
        assert "# TYPE luna_test_metric gauge" in output
        assert "luna_test_metric 0.85" in output

    def test_counter(self, exporter):
        """Counter metrics appear in output."""
        exporter.counter("events_total", 42, "Total events")
        output = exporter.export()
        assert "# TYPE luna_events_total counter" in output
        assert "luna_events_total 42" in output

    def test_multiple_metrics(self, exporter):
        """Multiple metrics are exported."""
        exporter.gauge("metric_a", 1.0)
        exporter.gauge("metric_b", 2.0)
        output = exporter.export()
        assert "luna_metric_a 1.0" in output
        assert "luna_metric_b 2.0" in output

    def test_empty_export(self, exporter):
        """Empty exporter returns empty string."""
        output = exporter.export()
        assert output == ""

    def test_disabled_exporter(self):
        """Disabled exporter returns empty string."""
        exporter = PrometheusExporter(enabled=False)
        exporter.gauge("test", 1.0)
        assert exporter.export() == ""

    def test_update_from_vitals(self, exporter):
        """update_from_vitals populates metrics."""
        exporter.update_from_vitals({
            "overall_vitality": 0.9,
            "identity_drift": 0.05,
            "quality_score": 0.85,
            "phi_iit": 0.7,
            "idle_steps": 100,
        })
        output = exporter.export()
        assert "luna_vitality 0.9" in output
        assert "luna_identity_drift 0.05" in output
        assert "luna_quality_score 0.85" in output
        assert "luna_phi_iit 0.7" in output
        assert "luna_idle_steps_total 100" in output

    def test_update_from_health(self, exporter):
        """update_from_health populates health metric."""
        exporter.update_from_health(0.85)
        output = exporter.export()
        assert "luna_health_score 0.85" in output

    def test_clear(self, exporter):
        """clear() removes all metrics."""
        exporter.gauge("test", 1.0)
        exporter.clear()
        assert exporter.export() == ""

    def test_get_status(self, exporter):
        """get_status returns expected structure."""
        exporter.gauge("test", 1.0)
        status = exporter.get_status()
        assert status["enabled"] is True
        assert status["metric_count"] == 1

    def test_output_ends_with_newline(self, exporter):
        """Output ends with newline for proper scraping."""
        exporter.gauge("test", 1.0)
        output = exporter.export()
        assert output.endswith("\n")

    def test_metrics_sorted(self, exporter):
        """Metrics are exported in sorted order."""
        exporter.gauge("zebra", 1.0)
        exporter.gauge("alpha", 2.0)
        output = exporter.export()
        alpha_pos = output.index("luna_alpha")
        zebra_pos = output.index("luna_zebra")
        assert alpha_pos < zebra_pos
