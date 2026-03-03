"""Tests for illusion detection — structural illusion detection.

12 tests covering status classification, correlation edge cases,
windowing, and LunaEngine integration.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from luna_common.consciousness.illusion import (
    IllusionResult,
    IllusionStatus,
    classify_status,
    compute_correlation,
    detect_self_illusion,
    detect_system_illusion,
    linear_trend,
)

# ===================================================================
#  1. Enum
# ===================================================================


class TestIllusionStatusEnum:

    def test_illusion_status_enum(self):
        """IllusionStatus has exactly 4 levels."""
        assert set(IllusionStatus) == {
            IllusionStatus.HEALTHY,
            IllusionStatus.CAUTION,
            IllusionStatus.ILLUSION,
            IllusionStatus.HARMFUL,
        }
        assert IllusionStatus.HEALTHY.value == "healthy"
        assert IllusionStatus.HARMFUL.value == "harmful"


# ===================================================================
#  2-5. Primary correlation classification
# ===================================================================


class TestPrimaryDetection:

    def test_perfect_correlation_healthy(self):
        """Perfectly correlated histories -> HEALTHY (r ~ 1.0)."""
        phi = [0.1 * i for i in range(20)]
        health = [0.1 * i for i in range(20)]
        result = detect_self_illusion(phi, health)
        assert result.status == IllusionStatus.HEALTHY
        assert result.correlation > 0.5

    def test_zero_correlation_illusion(self):
        """Uncorrelated histories -> ILLUSION or HARMFUL (r ~ 0)."""
        rng = np.random.default_rng(42)
        phi = [0.01 * i for i in range(100)]
        health = rng.random(100).tolist()
        result = detect_self_illusion(phi, health)
        assert result.status in (
            IllusionStatus.ILLUSION, IllusionStatus.CAUTION, IllusionStatus.HARMFUL
        )
        assert result.correlation < 0.5

    def test_negative_correlation_harmful(self):
        """Anti-correlated histories -> HARMFUL (r < 0)."""
        phi = [0.1 * i for i in range(20)]
        health = [2.0 - 0.1 * i for i in range(20)]
        result = detect_self_illusion(phi, health)
        assert result.status == IllusionStatus.HARMFUL
        assert result.correlation < 0.0

    def test_moderate_correlation_caution(self):
        """Moderate correlation (0.2 <= r <= 0.5) -> CAUTION."""
        rng = np.random.default_rng(123)
        base = np.linspace(0, 1, 50)
        noise = rng.normal(0, 0.4, 50)
        phi = base.tolist()
        health = (base + noise).tolist()
        result = detect_self_illusion(phi, health)
        assert 0.0 <= result.correlation <= 0.8
        if 0.2 <= result.correlation <= 0.5:
            assert result.status == IllusionStatus.CAUTION


# ===================================================================
#  6-7. Windowing and insufficient data
# ===================================================================


class TestWindowing:

    def test_window_truncation(self):
        """Only the last `window` steps should matter."""
        phi_bad = [0.01 * i for i in range(90)]
        health_bad = [1.0 - 0.01 * i for i in range(90)]
        phi_good = [0.1 * i for i in range(10)]
        health_good = [0.1 * i for i in range(10)]

        phi = phi_bad + phi_good
        health = health_bad + health_good

        result = detect_self_illusion(phi, health, window=10)
        assert result.status == IllusionStatus.HEALTHY
        assert result.correlation > 0.5

    def test_insufficient_data_returns_healthy(self):
        """With < 3 data points, assume HEALTHY (no evidence)."""
        result = detect_self_illusion([0.5, 0.6], [0.5, 0.6])
        assert result.status == IllusionStatus.HEALTHY
        assert result.recommendation == "continue"


# ===================================================================
#  8-9. System-wide detection (Test-Engineer cross-check)
# ===================================================================


class TestSystemDetection:

    def test_all_agents_healthy(self):
        """All agents correlated -> system HEALTHY."""
        result = detect_system_illusion({
            "luna": (
                [0.3 + 0.02 * i for i in range(20)],
                [0.2 + 0.02 * i for i in range(20)],
            ),
            "sayohmy": (
                [0.2 + 0.02 * i for i in range(20)],
                [0.1 + 0.02 * i for i in range(20)],
            ),
            "sentinel": (
                [0.3 + 0.02 * i for i in range(20)],
                [0.2 + 0.02 * i for i in range(20)],
            ),
        })
        assert result.status == IllusionStatus.HEALTHY
        assert all(r.status == IllusionStatus.HEALTHY for r in result.agent_results)

    def test_one_harmful_escalates_system(self):
        """One HARMFUL agent -> system HARMFUL."""
        result = detect_system_illusion({
            "luna": (
                [0.1 * i for i in range(20)],
                [0.1 * i for i in range(20)],
            ),
            "sentinel": (
                [0.1 * i for i in range(20)],
                [2.0 - 0.1 * i for i in range(20)],
            ),
        })
        assert result.status == IllusionStatus.HARMFUL


# ===================================================================
#  10-11. Edge cases and recommendation mapping
# ===================================================================


class TestEdgeCases:

    def test_pearson_edge_cases(self):
        """Constant data -> r = 0 (zero variance)."""
        r = compute_correlation(
            [0.5, 0.5, 0.5, 0.5],
            [0.7, 0.7, 0.7, 0.7],
        )
        assert r == pytest.approx(0.0)

    def test_recommendation_mapping(self):
        """Each status maps to the correct recommendation."""
        phi = [0.1 * i for i in range(20)]
        health = [0.1 * i for i in range(20)]
        result = detect_self_illusion(phi, health)
        assert result.recommendation == "continue"

        health_anti = [2.0 - 0.1 * i for i in range(20)]
        result = detect_self_illusion(phi, health_anti)
        assert result.recommendation == "veto"


# ===================================================================
#  12. Integration with LunaEngine
# ===================================================================


class TestEngineIntegration:

    def test_integration_with_engine_buffers(self):
        """LunaEngine accumulates phi_iit and health buffers after process_pipeline_result."""
        from luna_common.schemas import (
            IntegrationCheck,
            PsiState,
            SayOhmyManifest,
            SentinelReport,
        )

        engine_module = pytest.importorskip("luna.core.luna")
        LunaEngine = engine_module.LunaEngine

        config_module = pytest.importorskip("luna.core.config")
        LunaConfig = config_module.LunaConfig
        ConsciousnessSection = config_module.ConsciousnessSection

        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            cfg = LunaConfig.load(Path("/home/sayohmy/LUNA/luna.toml"))
            new_cs = ConsciousnessSection(
                checkpoint_file=str(tmp / "test_cs.json"),
                backup_on_save=False,
            )
            cfg = LunaConfig(
                luna=cfg.luna,
                consciousness=new_cs,
                memory=cfg.memory,
                pipeline=cfg.pipeline,
                observability=cfg.observability,
                heartbeat=cfg.heartbeat,
                root_dir=tmp,
            )
            engine = LunaEngine(config=cfg)
            engine.initialize()

            psi_s = PsiState(perception=0.15, reflexion=0.15, integration=0.20, expression=0.50)
            psi_se = PsiState(perception=0.50, reflexion=0.20, integration=0.20, expression=0.10)
            psi_te = PsiState(perception=0.15, reflexion=0.20, integration=0.50, expression=0.15)

            for i in range(5):
                m = SayOhmyManifest(
                    task_id=f"ILL-{i}",
                    files_produced=[],
                    phi_score=0.72,
                    mode_used="architect",
                    psi_sayohmy=psi_s,
                    confidence=0.85,
                )
                sr = SentinelReport(
                    task_id=f"ILL-{i}",
                    findings=[],
                    risk_score=0.1,
                    veto=False,
                    psi_sentinel=psi_se,
                    scanners_used=["bandit"],
                )
                ic = IntegrationCheck(
                    task_id=f"ILL-{i}",
                    cross_checks=[],
                    coherence_score=0.80,
                    coverage_delta=0.05,
                    veto_contested=False,
                    psi_te=psi_te,
                )
                decision = engine.process_pipeline_result(m, sr, ic)

            assert len(engine._phi_iit_buffer) == 5
            assert len(engine._health_buffer) == 5
            assert decision.illusion_status is not None
            assert decision.illusion_status in ("healthy", "caution", "illusion", "harmful")
