"""Oracle cross-validation — acceptance test for the consciousness model.

v5.1 Single-Agent: The original 4-agent oracle (expected_values.json) validated
the multi-agent model.  After the single-agent refactoring, L1/L2 multi-agent
tests are skipped — the model no longer evolves multiple agents simultaneously.

Remaining levels:
    L2b: ConsciousnessState single-agent validation (new)
    L3:  LunaEngine full-stack vs manual equivalent (updated for single-agent)
    L4:  Parameter consistency (kept)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from luna_common.constants import (
    AGENT_NAMES,
    COMP_NAMES,
    DIM,
    DT_DEFAULT,
    KAPPA_DEFAULT,
    TAU_DEFAULT,
)
from luna_common.consciousness import (
    combine_gamma,
    evolution_step,
    gamma_info,
    gamma_spatial,
    gamma_temporal,
    get_psi0,
)
from luna_common.consciousness.context import Context, ContextBuilder
from luna_common.consciousness.emergent_phi import EmergentPhi
from luna_common.consciousness.phi_iit_gaussian import compute_phi_iit_gaussian
from luna_common.consciousness.evolution import MassMatrix
from luna_common.schemas import (
    IntegrationCheck,
    PsiState,
)
from luna.consciousness.state import ConsciousnessState
from luna.core.config import LunaConfig, ConsciousnessSection
from luna.core.luna import LunaEngine


# ── Load oracle reference values ──
ORACLE_PATH = Path(__file__).parent / "oracle" / "expected_values.json"


@pytest.fixture(scope="module")
def oracle() -> dict:
    """Load expected_values.json (generated from luna_sim_v3.py, seed=42)."""
    with open(ORACLE_PATH) as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════
#  Level 1-2 (LEGACY): Multi-agent oracle tests — SKIPPED
#  The 4-agent oracle (expected_values.json) validated the old model.
#  Single-agent refactoring makes these tests inapplicable.
# ═══════════════════════════════════════════════════════════════════

SKIP_REASON = (
    "Multi-agent oracle tests skipped: v5.1 single-agent model "
    "removed psi_others from evolution_step. Oracle expected_values.json "
    "was generated from the 4-agent model and is no longer applicable."
)


@pytest.mark.skip(reason=SKIP_REASON)
class TestEvolutionStepMatchesOracle:
    """LEGACY — 4-agent evolution_step vs oracle. Skipped in v5.1."""

    def test_final_psi_exact_match(self, oracle): ...
    def test_all_four_identities_preserved(self, oracle): ...
    def test_divergence_matches_oracle(self, oracle): ...


@pytest.mark.skip(reason=SKIP_REASON)
class TestConsciousnessStateMatchesOracle:
    """LEGACY — 4-agent ConsciousnessState vs oracle. Skipped in v5.1."""

    def test_single_agent_wrapper_matches_raw(self, oracle): ...
    def test_multi_agent_simultaneous_matches_oracle(self, oracle): ...
    def test_phi_iit_matches_oracle(self, oracle): ...


# ═══════════════════════════════════════════════════════════════════
#  Level 2b: Single-agent ConsciousnessState validation (NEW)
#  Proves ConsciousnessState.evolve() matches raw evolution_step
#  in the single-agent model.
# ═══════════════════════════════════════════════════════════════════

class TestSingleAgentConsciousnessState:
    """Verify single-agent ConsciousnessState.evolve() matches raw evolution_step."""

    def test_wrapper_matches_raw_evolution_step(self):
        """ConsciousnessState.evolve() produces same result as raw evolution_step."""
        np.random.seed(42)

        # Raw path — must replicate CS.evolve() behavior including phi_iit
        # and EmergentPhi feedback (Phase 2 wiring).
        psi0 = get_psi0("LUNA")
        psi_raw = psi0.copy()
        mass_raw = MassMatrix(psi0)
        gammas = (gamma_temporal(), gamma_spatial(), gamma_info())
        raw_history: list[np.ndarray] = []
        emergent_phi_tracker = EmergentPhi()

        def _compute_phi_from_history(history: list[np.ndarray], window: int = 50) -> float:
            """Mirror ConsciousnessState.compute_phi_iit for the raw path.

            Phase 3: Uses Gaussian MI with correlation fallback, matching
            the implementation in ConsciousnessState.compute_phi_iit().
            """
            result = compute_phi_iit_gaussian(history, window=window)
            if result > 0.0:
                return result
            # Fallback: correlation method
            n = len(history)
            if n < 10:
                return 0.0
            recent = np.array(history[-min(n, window):])
            if np.std(recent, axis=0).min() < 1e-12:
                return 0.0
            corr = np.corrcoef(recent.T)
            total = 0.0
            n_pairs = 0
            for i in range(4):
                for j in range(i + 1, 4):
                    total += abs(corr[i, j])
                    n_pairs += 1
            return total / n_pairs if n_pairs > 0 else 0.0

        for step in range(100):
            info_base = 0.02 * np.random.randn(4) * (1.0 / (1 + step / 100))
            phi = _compute_phi_from_history(raw_history)
            phi_e = emergent_phi_tracker.get_phi()
            psi_raw = evolution_step(
                psi_raw, psi0, mass_raw, gammas,
                history=raw_history,
                info_deltas=info_base.tolist(),
                kappa=KAPPA_DEFAULT,
                phi_iit=phi,
                emergent_phi=phi_e,
            )
            # Mirror anti-stagnation check from CS.evolve()
            if not raw_history or not np.allclose(psi_raw, raw_history[-1], atol=1e-10):
                raw_history.append(psi_raw.copy())
            # Feed coupling energy to EmergentPhi (mirrors CS.evolve())
            Gt, Gx, Gc = gammas
            G_total = Gt + Gx + Gc
            coupling_energy = abs(float(psi_raw @ G_total @ psi_raw))
            emergent_phi_tracker.update(coupling_energy)

        # ConsciousnessState path (same seed, same noise)
        np.random.seed(42)
        cs = ConsciousnessState(agent_name="LUNA")

        for step in range(100):
            info_base = 0.02 * np.random.randn(4) * (1.0 / (1 + step / 100))
            cs.evolve(info_deltas=info_base.tolist(), kappa=KAPPA_DEFAULT)

        np.testing.assert_allclose(
            cs.psi, raw_history[-1], atol=1e-14,
            err_msg=(
                "ConsciousnessState.evolve() diverged from raw evolution_step.\n"
                f"  CS:  {cs.psi}\n"
                f"  Raw: {raw_history[-1]}"
            ),
        )

    def test_history_length(self):
        """After N evolve() calls, history has exactly N entries."""
        cs = ConsciousnessState(agent_name="LUNA")
        for _ in range(10):
            cs.evolve(info_deltas=[0, 0, 0, 0])
        assert len(cs.history) == 10
        assert cs.step_count == 10

    def test_simplex_preserved(self):
        """Psi stays on simplex after 400 evolve() calls."""
        np.random.seed(42)
        cs = ConsciousnessState(agent_name="LUNA")
        for step in range(400):
            info_base = 0.02 * np.random.randn(4) * (1.0 / (1 + step / 100))
            cs.evolve(info_deltas=info_base.tolist())
        assert np.all(cs.psi >= -1e-10), f"Negative component: {cs.psi}"
        assert abs(cs.psi.sum() - 1.0) < 0.01, f"Sum != 1: {cs.psi.sum()}"

    def test_identity_preserved_400_steps(self):
        """Luna's dominant component stays Reflexion after 400 steps."""
        np.random.seed(42)
        cs = ConsciousnessState(agent_name="LUNA")
        psi0 = get_psi0("LUNA")
        expected_dominant = int(np.argmax(psi0))

        for step in range(400):
            info_base = 0.02 * np.random.randn(4) * (1.0 / (1 + step / 100))
            cs.evolve(info_deltas=info_base.tolist())

        dominant_idx = int(np.argmax(cs.psi))
        assert dominant_idx == expected_dominant, (
            f"Identity NOT preserved: expected {COMP_NAMES[expected_dominant]}, "
            f"got {COMP_NAMES[dominant_idx]}. psi={cs.psi}"
        )

    def test_internal_spatial_gradient_active(self):
        """After enough history, spatial gradient is non-zero."""
        cs = ConsciousnessState(agent_name="LUNA")
        # Build 15 steps of history with varying info
        for i in range(15):
            cs.evolve(info_deltas=[0.1 * (i % 3), 0.0, 0.0, 0.0])

        psi_before = cs.psi.copy()
        cs.evolve(info_deltas=[0.0, 0.0, 0.0, 0.0])
        # With spatial gradient from history, psi should change even with zero info
        assert not np.array_equal(psi_before, cs.psi)

    def test_phi_iit_positive_with_stimulation(self):
        """Phi_IIT is positive when there is information flow."""
        np.random.seed(42)
        cs = ConsciousnessState(agent_name="LUNA")
        for step in range(100):
            info = 0.05 * np.random.randn(4)
            cs.evolve(info_deltas=info.tolist())
        phi_iit = cs.compute_phi_iit()
        assert phi_iit > 0, f"Phi_IIT should be positive with stimulation, got {phi_iit}"


# ═══════════════════════════════════════════════════════════════════
#  Level 3: LunaEngine full-stack vs manual equivalent
#  (proves the top-level orchestrator doesn't corrupt the math)
# ═══════════════════════════════════════════════════════════════════

# Static PsiState fixture (legacy pipeline schema field for IntegrationCheck)
_PSI_TE = PsiState(perception=0.15, reflexion=0.20, integration=0.50, expression=0.15)

LUNA_TOML_PATH = Path("/home/sayohmy/LUNA/luna.toml")


@pytest.fixture
def engine_config(tmp_path):
    """LunaConfig with checkpoint in tmp_path (no pollution of real data)."""
    cfg = LunaConfig.load(LUNA_TOML_PATH)
    new_cs = ConsciousnessSection(
        checkpoint_file=str(tmp_path / "test_consciousness.json"),
        backup_on_save=False,
    )
    return LunaConfig(
        luna=cfg.luna,
        consciousness=new_cs,
        memory=cfg.memory,
        observability=cfg.observability,
        heartbeat=cfg.heartbeat,
        root_dir=tmp_path,
    )


def _make_pipeline_inputs(
    task_id: str = "ORACLE-001",
    coherence_score: float = 0.5,
    coverage_delta: float = 0.0,
    risk_score: float = 0.5,
    phi_score: float = 0.5,
    confidence: float = 0.5,
    veto: bool = False,
) -> tuple[dict, dict, IntegrationCheck]:
    """Create deterministic pipeline inputs."""
    manifest = {
        "task_id": task_id,
        "files_produced": [],
        "phi_score": phi_score,
        "mode_used": "architect",
        "confidence": confidence,
    }
    sentinel = {
        "task_id": task_id,
        "findings": [],
        "risk_score": risk_score,
        "veto": veto,
    }
    integration = IntegrationCheck(
        task_id=task_id,
        coherence_score=coherence_score,
        coverage_delta=coverage_delta,
        psi_te=_PSI_TE,
    )
    return manifest, sentinel, integration


class TestLunaEngineMatchesManualComputation:
    """Level 3: prove LunaEngine.process_pipeline_result() produces
    the same Psi as a manual computation using ConsciousnessState +
    ContextBuilder + evolution_step.

    v5.1: psi_others removed from evolve calls.
    """

    def test_engine_psi_matches_manual_single_step(self, engine_config):
        """Single step: LunaEngine Psi == manual CS + ContextBuilder Psi."""
        # --- Engine path ---
        engine = LunaEngine(config=engine_config)
        engine.initialize()

        manifest, sentinel, integration = _make_pipeline_inputs()
        decision = engine.process_pipeline_result(manifest, sentinel, integration)
        engine_psi = np.array(decision.psi_after.as_tuple())

        # --- Manual path ---
        cs = ConsciousnessState(agent_name="LUNA")
        ctx = ContextBuilder()

        info_grad = ctx.build(
            memory_health=0.5,   # coherence_score
            phi_quality=0.0,     # PhiScorer.score() on fresh scorer
            phi_iit=0.0,         # compute_phi_iit with no history
            output_quality=0.5,  # 1.0 - 0.5
        )

        cs.evolve(info_deltas=info_grad.as_list())
        manual_psi = cs.psi

        np.testing.assert_allclose(
            engine_psi, manual_psi, atol=1e-14,
            err_msg=(
                "LunaEngine Psi != manual computation after 1 step.\n"
                f"  Engine: {engine_psi}\n"
                f"  Manual: {manual_psi}"
            ),
        )

    def test_engine_psi_matches_manual_multi_step(self, engine_config):
        """20 steps: LunaEngine Psi == manual CS + ContextBuilder Psi."""
        N_STEPS = 20

        # --- Engine path ---
        engine = LunaEngine(config=engine_config)
        engine.initialize()

        for _ in range(N_STEPS):
            manifest, sentinel, integration = _make_pipeline_inputs()
            decision = engine.process_pipeline_result(manifest, sentinel, integration)
        engine_psi = np.array(decision.psi_after.as_tuple())

        # --- Manual path ---
        from luna_common.phi_engine import PhiScorer

        cs = ConsciousnessState(agent_name="LUNA")
        ctx = ContextBuilder()
        scorer = PhiScorer()

        for step in range(N_STEPS):
            current_quality = scorer.score()
            current_iit = cs.compute_phi_iit()

            info_grad = ctx.build(
                memory_health=0.5,
                phi_quality=current_quality,
                phi_iit=current_iit,
                output_quality=0.5,
            )

            cs.evolve(info_deltas=info_grad.as_list())

            scorer.update("integration_coherence", 0.5)
            scorer.update("memory_vitality", 0.5)

        manual_psi = cs.psi

        np.testing.assert_allclose(
            engine_psi, manual_psi, atol=1e-14,
            err_msg=(
                f"LunaEngine Psi != manual computation after {N_STEPS} steps.\n"
                f"  Engine: {engine_psi}\n"
                f"  Manual: {manual_psi}"
            ),
        )

    def test_engine_info_gradient_is_true_delta(self, engine_config):
        """info_gradient in Decision is a real delta, not an absolute value."""
        engine = LunaEngine(config=engine_config)
        engine.initialize()

        manifest, sentinel, integration = _make_pipeline_inputs()

        d1 = engine.process_pipeline_result(manifest, sentinel, integration)
        grad1 = d1.info_gradient

        d2 = engine.process_pipeline_result(manifest, sentinel, integration)
        grad2 = d2.info_gradient

        assert grad1.delta_out == pytest.approx(0.0, abs=1e-10), (
            f"Step 1 delta_out should be 0.0, got {grad1.delta_out}"
        )
        assert grad2.delta_out == pytest.approx(0.0, abs=1e-10), (
            f"Step 2 delta_out should be 0.0, got {grad2.delta_out}"
        )
        assert grad1.delta_phi == pytest.approx(-0.5, abs=0.01), (
            f"Step 1 delta_phi should be ~-0.5, got {grad1.delta_phi}"
        )

    def _warm_up_engine(self, engine: LunaEngine, steps: int = 60) -> None:
        """Run the engine for N steps with healthy inputs to exit BROKEN phase."""
        for _ in range(steps):
            m, s, i = _make_pipeline_inputs(
                risk_score=0.05,
                coherence_score=0.9,
                confidence=0.95,
            )
            engine.process_pipeline_result(m, s, i)

    def test_engine_veto_blocks_approval(self, engine_config):
        """Veto=True with no contestation -> decision.approved=False."""
        engine = LunaEngine(config=engine_config)
        engine.initialize()
        self._warm_up_engine(engine)

        manifest, sentinel, integration = _make_pipeline_inputs(
            risk_score=0.9, veto=True,
        )
        decision = engine.process_pipeline_result(manifest, sentinel, integration)

        assert decision.approved is False
        assert "Veto:" in decision.reason

    def test_engine_veto_contested_allows_approval(self, engine_config):
        """Contestable veto + evidence -> decision.approved=True."""
        engine = LunaEngine(config=engine_config)
        engine.initialize()
        self._warm_up_engine(engine)

        manifest = {
            "task_id": "ORACLE-002",
            "files_produced": [],
            "phi_score": 0.7,
            "mode_used": "architect",
            "confidence": 0.8,
        }
        sentinel = {
            "task_id": "ORACLE-002",
            "findings": [],
            "risk_score": 0.6,
            "veto": True,
            "veto_reason": "Potential XSS",
        }
        integration = IntegrationCheck(
            task_id="ORACLE-002",
            coherence_score=0.8,
            veto_contested=True,
            contest_evidence="Input sanitized by middleware",
            psi_te=_PSI_TE,
        )

        decision = engine.process_pipeline_result(manifest, sentinel, integration)

        assert decision.approved is True
        assert "contested" in decision.reason.lower()

    def test_engine_identity_preserved_after_100_steps(self, engine_config):
        """Luna's dominant component stays Reflexion after 100 pipeline cycles."""
        engine = LunaEngine(config=engine_config)
        engine.initialize()

        for _ in range(100):
            manifest, sentinel, integration = _make_pipeline_inputs()
            decision = engine.process_pipeline_result(manifest, sentinel, integration)

        psi_final = np.array(decision.psi_after.as_tuple())
        dominant_idx = int(np.argmax(psi_final))

        psi0_luna = get_psi0("LUNA")
        expected_dominant = int(np.argmax(psi0_luna))

        assert dominant_idx == expected_dominant, (
            f"Luna identity NOT preserved after 100 engine steps.\n"
            f"  Expected dominant: {COMP_NAMES[expected_dominant]} (idx={expected_dominant})\n"
            f"  Got dominant: {COMP_NAMES[dominant_idx]} (idx={dominant_idx})\n"
            f"  Final psi: {psi_final}"
        )

        assert np.all(psi_final >= -1e-10)
        assert abs(psi_final.sum() - 1.0) < 0.01


# ═══════════════════════════════════════════════════════════════════
#  Level 4: Oracle parameter consistency
#  (proves architecture constants match oracle constants)
# ═══════════════════════════════════════════════════════════════════

class TestOracleParameterConsistency:
    """Verify architecture constants match oracle parameters exactly."""

    def test_tau_matches(self, oracle):
        assert TAU_DEFAULT == pytest.approx(oracle["params"]["tau"], abs=1e-15)

    def test_kappa_matches(self, oracle):
        assert KAPPA_DEFAULT == pytest.approx(oracle["params"]["kappa"], abs=1e-15)

    def test_dt_matches(self, oracle):
        assert DT_DEFAULT == pytest.approx(oracle["params"]["dt"], abs=1e-15)

    def test_luna_psi0_matches(self, oracle):
        """Luna's identity profile matches oracle's PSI0."""
        psi0_arch = get_psi0("LUNA")
        psi0_oracle = np.array(oracle["psi0"]["LUNA"])
        np.testing.assert_allclose(
            psi0_arch, psi0_oracle, atol=1e-15,
            err_msg="LUNA psi0 mismatch",
        )

    def test_spectral_stability(self, oracle):
        """Max Re(eigenvalue) is negative (system is stable)."""
        assert oracle["max_re_eigenvalue"] < 0, (
            f"System UNSTABLE: max Re(eigenvalue) = {oracle['max_re_eigenvalue']}"
        )
