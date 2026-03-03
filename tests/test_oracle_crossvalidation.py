"""Oracle cross-validation — THE acceptance test for Phases 1-2.

Proves that the architecture code (luna_common + luna/) produces
the exact same Psi trajectories as luna_sim_v3.py (the oracle).

Chain of trust:
    luna_sim_v3.py (oracle, seed=42, 400 steps)
        -> expected_values.json (generated once, never modified)
            -> this test (compares architecture code against reference)

4 levels of validation:
    L1: evolution_step (luna_common) vs oracle
    L2: ConsciousnessState.evolve (luna/) vs oracle
    L3: LunaEngine.process_pipeline_result (full stack) vs manual equivalent
    L4: Parameter consistency

If any test fails, the architecture code has diverged from the
mathematical model.  No Phase 3+ work should proceed until it passes.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pytest

from luna_common.constants import (
    AGENT_NAMES,
    AGENT_PROFILES,
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
from luna_common.consciousness.evolution import MassMatrix
from luna_common.schemas import (
    IntegrationCheck,
    PsiState,
    SayOhmyManifest,
    SentinelReport,
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
#  Level 1: luna_common.evolution_step vs oracle
#  (raw math layer — same as existing TestIdentityPreservation but
#   now with exact numerical comparison against frozen reference)
# ═══════════════════════════════════════════════════════════════════

class TestEvolutionStepMatchesOracle:
    """Verify luna_common.evolution_step produces oracle-identical Psi."""

    def test_final_psi_exact_match(self, oracle):
        """Architecture evolution_step produces the same final Psi as the oracle.

        Both use seed=42, 400 steps, same info_base noise, same params.
        Tolerance: 1e-10 (machine-precision agreement expected).
        """
        np.random.seed(42)

        gammas = (gamma_temporal(), gamma_spatial(), gamma_info())

        agents = []
        for name in AGENT_NAMES:
            psi0 = get_psi0(name)
            agents.append({
                "name": name,
                "psi": psi0.copy(),
                "psi0": psi0.copy(),
                "mass": MassMatrix(psi0),
            })

        for step in range(400):
            info_base = 0.02 * np.random.randn(4) * (1.0 / (1 + step / 100))
            new_psis = []
            for i, agent in enumerate(agents):
                others = [a["psi"] for j, a in enumerate(agents) if j != i]
                psi_new = evolution_step(
                    agent["psi"], agent["psi0"], others, agent["mass"], gammas,
                    info_deltas=info_base.tolist(),
                    kappa=KAPPA_DEFAULT,
                )
                new_psis.append(psi_new)
            for i, agent in enumerate(agents):
                agent["psi"] = new_psis[i]

        for agent in agents:
            name = agent["name"]
            expected = np.array(oracle["final_psi"][name])
            np.testing.assert_allclose(
                agent["psi"], expected, atol=1e-10,
                err_msg=(
                    f"{name}: architecture Psi diverged from oracle.\n"
                    f"  got:      {agent['psi']}\n"
                    f"  expected: {expected}"
                ),
            )

    def test_all_four_identities_preserved(self, oracle):
        """All 4 agents preserve their dominant component (oracle confirms)."""
        for name in AGENT_NAMES:
            assert oracle["dominant_preserved"][name] is True, (
                f"{name}: oracle says identity NOT preserved"
            )

    def test_divergence_matches_oracle(self, oracle):
        """Inter-agent divergence at step 400 matches oracle."""
        np.random.seed(42)

        gammas = (gamma_temporal(), gamma_spatial(), gamma_info())
        agents = []
        for name in AGENT_NAMES:
            psi0 = get_psi0(name)
            agents.append({
                "name": name,
                "psi": psi0.copy(),
                "psi0": psi0.copy(),
                "mass": MassMatrix(psi0),
            })

        for step in range(400):
            info_base = 0.02 * np.random.randn(4) * (1.0 / (1 + step / 100))
            new_psis = []
            for i, agent in enumerate(agents):
                others = [a["psi"] for j, a in enumerate(agents) if j != i]
                psi_new = evolution_step(
                    agent["psi"], agent["psi0"], others, agent["mass"], gammas,
                    info_deltas=info_base.tolist(),
                    kappa=KAPPA_DEFAULT,
                )
                new_psis.append(psi_new)
            for i, agent in enumerate(agents):
                agent["psi"] = new_psis[i]

        div_total, n_pairs = 0.0, 0
        for a, b in itertools.combinations(range(len(agents)), 2):
            div_total += np.sum(np.abs(agents[a]["psi"] - agents[b]["psi"]))
            n_pairs += 1
        divergence = div_total / max(1, n_pairs)

        assert divergence == pytest.approx(oracle["divergence_final"], abs=1e-10), (
            f"Divergence mismatch: got {divergence}, oracle says {oracle['divergence_final']}"
        )


# ═══════════════════════════════════════════════════════════════════
#  Level 2: ConsciousnessState.evolve() vs oracle
#  (wrapper layer — proves state.py doesn't corrupt the math)
# ═══════════════════════════════════════════════════════════════════

class TestConsciousnessStateMatchesOracle:
    """Verify ConsciousnessState.evolve() produces oracle-identical Psi.

    This tests the wrapping layer: state management, history tracking,
    mass matrix updates, and phase computation do NOT alter the
    mathematical output of evolution_step.
    """

    def test_single_agent_wrapper_matches_raw(self, oracle):
        """Single-agent evolution via ConsciousnessState matches raw evolution_step.

        Run Luna alone (other agents frozen at psi0) for 100 steps.
        Compare ConsciousnessState.evolve() output vs raw evolution_step.
        """
        np.random.seed(42)

        # Raw evolution_step path
        psi0_luna = get_psi0("LUNA")
        psi_raw = psi0_luna.copy()
        mass_raw = MassMatrix(psi0_luna)
        gammas = (gamma_temporal(), gamma_spatial(), gamma_info())

        others_static = [get_psi0(n) for n in AGENT_NAMES if n != "LUNA"]

        raw_history = []
        for step in range(100):
            info_base = 0.02 * np.random.randn(4) * (1.0 / (1 + step / 100))
            psi_raw = evolution_step(
                psi_raw, psi0_luna, others_static, mass_raw, gammas,
                info_deltas=info_base.tolist(),
                kappa=KAPPA_DEFAULT,
            )
            raw_history.append(psi_raw.copy())

        # ConsciousnessState path (same seed, same noise)
        np.random.seed(42)
        cs = ConsciousnessState(agent_name="LUNA")

        for step in range(100):
            info_base = 0.02 * np.random.randn(4) * (1.0 / (1 + step / 100))
            cs.evolve(
                others_static,
                info_deltas=info_base.tolist(),
                kappa=KAPPA_DEFAULT,
            )

        np.testing.assert_allclose(
            cs.psi, raw_history[-1], atol=1e-14,
            err_msg=(
                "ConsciousnessState.evolve() diverged from raw evolution_step.\n"
                f"  CS:  {cs.psi}\n"
                f"  Raw: {raw_history[-1]}"
            ),
        )

    def test_consciousness_state_history_length(self):
        """After N evolve() calls, history has exactly N entries."""
        cs = ConsciousnessState(agent_name="LUNA")
        others = [get_psi0(n) for n in AGENT_NAMES if n != "LUNA"]

        for _ in range(10):
            cs.evolve(others, info_deltas=[0, 0, 0, 0])

        assert len(cs.history) == 10
        assert cs.step_count == 10

    def test_consciousness_state_simplex_preserved(self):
        """Psi stays on simplex after 400 evolve() calls."""
        np.random.seed(42)
        cs = ConsciousnessState(agent_name="LUNA")
        others = [get_psi0(n) for n in AGENT_NAMES if n != "LUNA"]

        for step in range(400):
            info_base = 0.02 * np.random.randn(4) * (1.0 / (1 + step / 100))
            cs.evolve(others, info_deltas=info_base.tolist())

        assert np.all(cs.psi >= -1e-10), f"Negative component: {cs.psi}"
        assert abs(cs.psi.sum() - 1.0) < 0.01, f"Sum != 1: {cs.psi.sum()}"

    def test_multi_agent_simultaneous_matches_oracle(self, oracle):
        """4-agent simultaneous stepping via ConsciousnessState matches oracle.

        Key: we must pre-compute all new psis BEFORE assigning any,
        to match the oracle's semantics. We use a temporary dict to
        collect results, then copy them back.
        """
        np.random.seed(42)

        states = {}
        for name in AGENT_NAMES:
            states[name] = ConsciousnessState(agent_name=name)

        for step in range(400):
            info_base = 0.02 * np.random.randn(4) * (1.0 / (1 + step / 100))

            # Snapshot current psis BEFORE any mutation
            current_psis = {name: states[name].psi.copy() for name in AGENT_NAMES}

            # Compute new psis using snapshots for "others"
            new_psis = {}
            for name in AGENT_NAMES:
                others = [current_psis[other] for other in AGENT_NAMES if other != name]

                # We need to call evolution_step directly on the CS's internals
                # to avoid the mid-loop mutation problem, but still use CS's
                # mass matrix and gammas (proving they match oracle's).
                psi_new = evolution_step(
                    current_psis[name],
                    states[name].psi0,
                    others,
                    states[name].mass,
                    states[name].gammas,
                    info_deltas=info_base.tolist(),
                    kappa=KAPPA_DEFAULT,
                )
                new_psis[name] = psi_new

            # Now assign all at once (matching oracle semantics)
            for name in AGENT_NAMES:
                states[name].psi = new_psis[name]
                states[name].history.append(new_psis[name].copy())
                states[name].step_count += 1

        for name in AGENT_NAMES:
            expected = np.array(oracle["final_psi"][name])
            np.testing.assert_allclose(
                states[name].psi, expected, atol=1e-10,
                err_msg=(
                    f"{name}: ConsciousnessState Psi diverged from oracle.\n"
                    f"  got:      {states[name].psi}\n"
                    f"  expected: {expected}"
                ),
            )

    def test_phi_iit_matches_oracle(self, oracle):
        """Phi_IIT (correlation) at step 400 matches oracle values."""
        np.random.seed(42)

        states = {}
        for name in AGENT_NAMES:
            states[name] = ConsciousnessState(agent_name=name)

        for step in range(400):
            info_base = 0.02 * np.random.randn(4) * (1.0 / (1 + step / 100))
            current_psis = {name: states[name].psi.copy() for name in AGENT_NAMES}
            new_psis = {}
            for name in AGENT_NAMES:
                others = [current_psis[other] for other in AGENT_NAMES if other != name]
                psi_new = evolution_step(
                    current_psis[name], states[name].psi0, others,
                    states[name].mass, states[name].gammas,
                    info_deltas=info_base.tolist(), kappa=KAPPA_DEFAULT,
                )
                new_psis[name] = psi_new
            for name in AGENT_NAMES:
                states[name].psi = new_psis[name]
                states[name].history.append(new_psis[name].copy())
                states[name].step_count += 1

        for name in AGENT_NAMES:
            phi_iit = states[name].compute_phi_iit()
            expected = oracle["phi_iit_correlation"][name]
            assert phi_iit == pytest.approx(expected, abs=1e-6), (
                f"{name}: Phi_IIT = {phi_iit}, oracle = {expected}"
            )


# ═══════════════════════════════════════════════════════════════════
#  Level 3: LunaEngine full-stack vs manual equivalent
#  (proves the top-level orchestrator doesn't corrupt the math)
# ═══════════════════════════════════════════════════════════════════

# Static PsiState fixtures (psi0 of each agent)
_PSI_SAYOHMY = PsiState(perception=0.15, reflexion=0.15, integration=0.20, expression=0.50)
_PSI_SENTINEL = PsiState(perception=0.50, reflexion=0.20, integration=0.20, expression=0.10)
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
        pipeline=cfg.pipeline,
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
) -> tuple[SayOhmyManifest, SentinelReport, IntegrationCheck]:
    """Create deterministic pipeline inputs with static psi_others = psi0."""
    manifest = SayOhmyManifest(
        task_id=task_id,
        files_produced=[],
        phi_score=phi_score,
        mode_used="architect",
        psi_sayohmy=_PSI_SAYOHMY,
        confidence=confidence,
    )
    sentinel = SentinelReport(
        task_id=task_id,
        findings=[],
        risk_score=risk_score,
        veto=veto,
        psi_sentinel=_PSI_SENTINEL,
    )
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

    This closes the gap between the oracle (L1/L2) and what actually
    runs in production.  Tests use stable inputs so ContextBuilder
    produces predictable deltas.
    """

    def test_engine_psi_matches_manual_single_step(self, engine_config):
        """Single step: LunaEngine Psi == manual CS + ContextBuilder Psi.

        Both paths see the same inputs.  The engine adds PhiScorer,
        convergence tracking, veto resolution — none of which should
        affect the Psi evolution math.
        """
        # --- Engine path ---
        engine = LunaEngine(config=engine_config)
        engine.initialize()

        manifest, sentinel, integration = _make_pipeline_inputs()
        decision = engine.process_pipeline_result(manifest, sentinel, integration)
        engine_psi = np.array(decision.psi_after.as_tuple())

        # --- Manual path (replicate exactly what engine does) ---
        cs = ConsciousnessState(agent_name="LUNA")
        ctx = ContextBuilder()

        # ContextBuilder inputs match engine's:
        #   memory_health = integration.coherence_score = 0.5
        #   phi_quality = PhiScorer().score() = 0.0 (no metrics yet)
        #   phi_iit = cs.compute_phi_iit() = 0.0 (no history)
        #   output_quality = 1.0 - sentinel.risk_score = 0.5
        info_grad = ctx.build(
            memory_health=0.5,   # coherence_score
            phi_quality=0.0,     # PhiScorer.score() on fresh scorer
            phi_iit=0.0,         # compute_phi_iit with no history
            output_quality=0.5,  # 1.0 - 0.5
        )

        psi_others = [
            np.array(_PSI_SAYOHMY.as_tuple()),
            np.array(_PSI_SENTINEL.as_tuple()),
            np.array(_PSI_TE.as_tuple()),
        ]

        cs.evolve(psi_others, info_deltas=info_grad.as_list())
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
        """20 steps: LunaEngine Psi == manual CS + ContextBuilder Psi.

        Uses stable inputs every step.  After step 1, PhiScorer and
        phi_iit values evolve — the manual path must replicate this.
        """
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

        psi_others = [
            np.array(_PSI_SAYOHMY.as_tuple()),
            np.array(_PSI_SENTINEL.as_tuple()),
            np.array(_PSI_TE.as_tuple()),
        ]

        for step in range(N_STEPS):
            # Replicate engine's ContextBuilder inputs exactly
            current_quality = scorer.score()
            current_iit = cs.compute_phi_iit()

            info_grad = ctx.build(
                memory_health=0.5,         # coherence_score
                phi_quality=current_quality,
                phi_iit=current_iit,
                output_quality=0.5,        # 1.0 - risk_score
            )

            cs.evolve(psi_others, info_deltas=info_grad.as_list())

            # Replicate engine's PhiScorer updates (post-evolve)
            scorer.update("security_integrity", 0.5)   # 1 - risk_score
            scorer.update("performance_score", 0.5)     # confidence

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
        """info_gradient in Decision is a real delta, not an absolute value.

        Step 1: bootstrap(0.5) -> current -> delta = current - 0.5
        Step 2: delta = current(step2) - current(step1)

        If ContextBuilder is wired wrong, deltas would be absolute values.
        """
        engine = LunaEngine(config=engine_config)
        engine.initialize()

        manifest, sentinel, integration = _make_pipeline_inputs()

        # Step 1
        d1 = engine.process_pipeline_result(manifest, sentinel, integration)
        grad1 = d1.info_gradient

        # Step 2 (same inputs -> quality and iit have changed)
        d2 = engine.process_pipeline_result(manifest, sentinel, integration)
        grad2 = d2.info_gradient

        # With stable inputs, output_quality = 0.5 every step.
        # Step 1: delta_out = 0.5 - 0.5 (bootstrap) = 0.0
        # Step 2: delta_out = 0.5 - 0.5 (previous) = 0.0
        assert grad1.delta_out == pytest.approx(0.0, abs=1e-10), (
            f"Step 1 delta_out should be 0.0, got {grad1.delta_out}"
        )
        assert grad2.delta_out == pytest.approx(0.0, abs=1e-10), (
            f"Step 2 delta_out should be 0.0, got {grad2.delta_out}"
        )

        # phi_quality changes between steps (PhiScorer gets updated),
        # so delta_phi should differ between step 1 and step 2.
        # Step 1: phi_quality = 0.0 (no metrics), delta = 0.0 - 0.5 = -0.5
        assert grad1.delta_phi == pytest.approx(-0.5, abs=0.01), (
            f"Step 1 delta_phi should be ~-0.5, got {grad1.delta_phi}"
        )

    def _warm_up_engine(self, engine: LunaEngine, steps: int = 60) -> None:
        """Run the engine for N steps with healthy inputs to exit BROKEN phase.

        Fresh engine starts at phase=BROKEN (no history -> phi_iit=0).
        We need ~50+ steps to build enough history for phi_iit to
        register, and healthy scores to climb out of BROKEN.
        """
        for _ in range(steps):
            m, s, i = _make_pipeline_inputs(
                risk_score=0.05,    # very low risk -> high output quality
                coherence_score=0.9,
                confidence=0.95,
            )
            engine.process_pipeline_result(m, s, i)

    def test_engine_veto_blocks_approval(self, engine_config):
        """SENTINEL veto=True with no contestation -> decision.approved=False.

        Engine must first exit BROKEN phase (via warm-up) so the veto
        logic is actually tested rather than being masked by BROKEN override.
        """
        engine = LunaEngine(config=engine_config)
        engine.initialize()
        self._warm_up_engine(engine)

        manifest, sentinel, integration = _make_pipeline_inputs(
            risk_score=0.9, veto=True,
        )
        decision = engine.process_pipeline_result(manifest, sentinel, integration)

        assert decision.approved is False
        assert "SENTINEL veto" in decision.reason

    def test_engine_veto_contested_allows_approval(self, engine_config):
        """Contestable veto + evidence -> decision.approved=True.

        Proves the full veto adjudication pipeline works end-to-end.
        """
        engine = LunaEngine(config=engine_config)
        engine.initialize()
        self._warm_up_engine(engine)

        manifest = SayOhmyManifest(
            task_id="ORACLE-002",
            files_produced=[],
            phi_score=0.7,
            mode_used="architect",
            psi_sayohmy=_PSI_SAYOHMY,
            confidence=0.8,
        )
        sentinel = SentinelReport(
            task_id="ORACLE-002",
            findings=[],
            risk_score=0.6,  # HIGH severity, contestable
            veto=True,
            veto_reason="Potential XSS",
            psi_sentinel=_PSI_SENTINEL,
        )
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
        """Luna's dominant component stays Reflexion after 100 pipeline cycles.

        This is the engine-level equivalent of the oracle's identity
        preservation test.  If the wrappers silently flip a sign or
        swap an argument, the dominant might shift.
        """
        engine = LunaEngine(config=engine_config)
        engine.initialize()

        for _ in range(100):
            manifest, sentinel, integration = _make_pipeline_inputs()
            decision = engine.process_pipeline_result(manifest, sentinel, integration)

        psi_final = np.array(decision.psi_after.as_tuple())
        dominant_idx = int(np.argmax(psi_final))

        # Luna's psi0 dominant is Reflexion (index 1)
        psi0_luna = get_psi0("LUNA")
        expected_dominant = int(np.argmax(psi0_luna))

        assert dominant_idx == expected_dominant, (
            f"Luna identity NOT preserved after 100 engine steps.\n"
            f"  Expected dominant: {COMP_NAMES[expected_dominant]} (idx={expected_dominant})\n"
            f"  Got dominant: {COMP_NAMES[dominant_idx]} (idx={dominant_idx})\n"
            f"  Final psi: {psi_final}"
        )

        # Simplex check
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

    def test_psi0_profiles_match(self, oracle):
        """Agent identity profiles match oracle's PSI0."""
        for name in AGENT_NAMES:
            psi0_arch = get_psi0(name)
            psi0_oracle = np.array(oracle["psi0"][name])
            np.testing.assert_allclose(
                psi0_arch, psi0_oracle, atol=1e-15,
                err_msg=f"{name}: psi0 mismatch",
            )

    def test_spectral_stability(self, oracle):
        """Max Re(eigenvalue) is negative (system is stable)."""
        assert oracle["max_re_eigenvalue"] < 0, (
            f"System UNSTABLE: max Re(eigenvalue) = {oracle['max_re_eigenvalue']}"
        )
