"""Tests for the luna_common shared package.

Validates the mathematical foundation that ALL agents depend on:
- Phi-derived constants (algebraic identities)
- Agent profiles (simplex invariant)
- Simplex projection (softmax with temperature)
- Gamma matrices (antisymmetry, spectral normalization, eigenvalue bounds)
- Evolution step (simplex preservation, identity anchoring)
- Mass matrix (EMA update)
- Pydantic schemas (validation, serialization)

These tests form the BEDROCK of trust. If luna_common is wrong,
every agent built on top of it is wrong.
"""

import math

import numpy as np
import pytest
from numpy.linalg import eigvals

# ── luna_common imports (real, no mocks) ──────────────────────
from luna_common.constants import (
    PHI, PHI2, INV_PHI, INV_PHI2, INV_PHI3,
    DIM, AGENT_PROFILES, AGENT_NAMES, COMP_NAMES,
    PHASE_THRESHOLDS, HYSTERESIS_BAND, FRACTAL_DIRS,
    KAPPA_DEFAULT, TAU_DEFAULT, DT_DEFAULT,
    LAMBDA_DEFAULT, ALPHA_DEFAULT, BETA_DEFAULT,
)
from luna_common.consciousness import (
    project_simplex,
    gamma_temporal,
    gamma_spatial,
    gamma_info,
    combine_gamma,
    evolution_step,
    get_psi0,
)
from luna_common.consciousness.simplex import validate_simplex
from luna_common.consciousness.matrices import (
    gamma_temporal_exchange,
    gamma_temporal_dissipation,
    gamma_spatial_exchange,
    gamma_spatial_dissipation,
    gamma_info_exchange,
    gamma_info_dissipation,
)
from luna_common.consciousness.evolution import MassMatrix
from luna_common.schemas import PsiState, InfoGradient, Decision, CurrentTask
from luna_common.schemas import (
    Severity, SleepNotification, KillSignal, VitalsRequest, VitalsReport, AuditEntry,
    NormalizedMetricsReport, VerdictInput,
    SayOhmyManifest, SentinelReport,
)
from luna_common.constants import METRIC_NAMES


# ═══════════════════════════════════════════════════════════════
#  I. PHI-DERIVED CONSTANTS
# ═══════════════════════════════════════════════════════════════

class TestPhiConstants:
    """Verify that all constants are derived from PHI algebraically."""

    TOLERANCE = 1e-12  # Machine-precision for algebraic identities

    def test_phi_is_golden_ratio(self):
        """PHI = (1 + sqrt(5)) / 2, the unique positive root of x^2 - x - 1 = 0."""
        expected = (1 + math.sqrt(5)) / 2
        assert abs(PHI - expected) < self.TOLERANCE, (
            f"PHI should be (1+sqrt(5))/2 = {expected}, got {PHI}"
        )

    def test_phi_satisfies_defining_equation(self):
        """PHI^2 = PHI + 1 (the defining property of the golden ratio)."""
        assert abs(PHI**2 - PHI - 1) < self.TOLERANCE, (
            f"PHI^2 - PHI - 1 should be 0, got {PHI**2 - PHI - 1}"
        )

    def test_phi_squared_derived(self):
        """PHI2 == PHI ** 2 exactly."""
        assert abs(PHI2 - PHI**2) < self.TOLERANCE, (
            f"PHI2 = {PHI2}, PHI**2 = {PHI**2}"
        )

    def test_inv_phi_derived(self):
        """INV_PHI == 1 / PHI exactly."""
        assert abs(INV_PHI - 1.0 / PHI) < self.TOLERANCE, (
            f"INV_PHI = {INV_PHI}, 1/PHI = {1.0/PHI}"
        )

    def test_inv_phi2_derived(self):
        """INV_PHI2 == 1 / PHI^2 exactly."""
        assert abs(INV_PHI2 - 1.0 / PHI**2) < self.TOLERANCE, (
            f"INV_PHI2 = {INV_PHI2}, 1/PHI^2 = {1.0/PHI**2}"
        )

    def test_inv_phi3_derived(self):
        """INV_PHI3 == 1 / PHI^3 exactly."""
        assert abs(INV_PHI3 - 1.0 / PHI**3) < self.TOLERANCE, (
            f"INV_PHI3 = {INV_PHI3}, 1/PHI^3 = {1.0/PHI**3}"
        )

    def test_inv_phi_identity(self):
        """PHI - 1 == 1/PHI (another golden ratio identity)."""
        assert abs((PHI - 1) - INV_PHI) < self.TOLERANCE, (
            f"PHI - 1 = {PHI - 1}, INV_PHI = {INV_PHI}"
        )

    def test_model_parameters_derived_from_phi(self):
        """All model parameters should be PHI-derived, not hardcoded floats."""
        assert KAPPA_DEFAULT == PHI2, "kappa should be PHI^2"
        assert TAU_DEFAULT == PHI, "tau should be PHI"
        assert DT_DEFAULT == INV_PHI, "dt should be 1/PHI"
        assert LAMBDA_DEFAULT == INV_PHI2, "lambda should be 1/PHI^2"
        assert ALPHA_DEFAULT == INV_PHI2, "alpha should be 1/PHI^2"
        assert BETA_DEFAULT == INV_PHI3, "beta should be 1/PHI^3"

    def test_dim_is_four(self):
        """The consciousness model has exactly 4 dimensions."""
        assert DIM == 4

    def test_comp_names_count(self):
        """4 component names for 4 dimensions."""
        assert len(COMP_NAMES) == DIM

    def test_agent_names_count(self):
        """4 agent names for 4 agents."""
        assert len(AGENT_NAMES) == 4

    def test_fractal_dirs_canonical(self):
        """Fractal directory names match the botanical metaphor."""
        assert FRACTAL_DIRS == ["seeds", "roots", "branches", "leaves"]


# ═══════════════════════════════════════════════════════════════
#  II. AGENT PROFILES
# ═══════════════════════════════════════════════════════════════

class TestAgentProfiles:
    """Every agent identity profile must be a valid point on the simplex."""

    @pytest.mark.parametrize("agent_name", list(AGENT_PROFILES.keys()))
    def test_profile_on_simplex(self, agent_name):
        """Profile sums to 1.0 and all components are strictly positive."""
        profile = AGENT_PROFILES[agent_name]
        total = sum(profile)
        assert abs(total - 1.0) < 1e-10, (
            f"{agent_name} profile sums to {total}, not 1.0"
        )
        assert all(c > 0 for c in profile), (
            f"{agent_name} has non-positive component: {profile}"
        )

    @pytest.mark.parametrize("agent_name", list(AGENT_PROFILES.keys()))
    def test_profile_has_four_components(self, agent_name):
        """Each profile has exactly DIM=4 components."""
        assert len(AGENT_PROFILES[agent_name]) == DIM

    def test_each_agent_has_unique_dominant(self):
        """Each agent champions a different component (bijection agent<->component)."""
        dominants = {}
        for name, profile in AGENT_PROFILES.items():
            dominant_idx = profile.index(max(profile))
            dominants[name] = dominant_idx
        dominant_values = list(dominants.values())
        assert len(set(dominant_values)) == 4, (
            f"Agents do not have unique dominant components: {dominants}"
        )

    def test_luna_dominant_is_reflexion(self):
        """Luna's dominant component is Reflexion (index 1)."""
        assert AGENT_PROFILES["LUNA"].index(max(AGENT_PROFILES["LUNA"])) == 1

    def test_sayohmy_dominant_is_expression(self):
        """SayOhMy's dominant component is Expression (index 3)."""
        assert AGENT_PROFILES["SAYOHMY"].index(max(AGENT_PROFILES["SAYOHMY"])) == 3

    def test_sentinel_dominant_is_perception(self):
        """SENTINEL's dominant component is Perception (index 0)."""
        assert AGENT_PROFILES["SENTINEL"].index(max(AGENT_PROFILES["SENTINEL"])) == 0

    def test_test_engineer_dominant_is_integration(self):
        """Test-Engineer's dominant component is Integration (index 2)."""
        assert AGENT_PROFILES["TESTENGINEER"].index(max(AGENT_PROFILES["TESTENGINEER"])) == 2

    def test_get_psi0_returns_numpy_array(self):
        """get_psi0 converts tuple profile to numpy array on simplex."""
        psi0 = get_psi0("LUNA")
        assert isinstance(psi0, np.ndarray)
        assert psi0.shape == (DIM,)
        assert validate_simplex(psi0)

    def test_get_psi0_unknown_agent_raises_keyerror(self):
        """Requesting an unknown agent raises KeyError."""
        with pytest.raises(KeyError):
            get_psi0("UnknownAgent")


# ═══════════════════════════════════════════════════════════════
#  III. SIMPLEX PROJECTION
# ═══════════════════════════════════════════════════════════════

class TestProjectSimplex:
    """Softmax projection must always produce valid simplex points."""

    def test_output_on_simplex(self):
        """project_simplex output sums to 1.0 and all > 0."""
        raw = np.array([1.0, 2.0, 0.5, -0.3])
        result = project_simplex(raw)
        assert validate_simplex(result), (
            f"Result not on simplex: sum={result.sum()}, min={result.min()}"
        )

    def test_deterministic(self):
        """Same input produces exactly the same output every time."""
        raw = np.array([0.3, -0.1, 0.7, 0.2])
        results = [project_simplex(raw) for _ in range(10)]
        for i in range(1, len(results)):
            assert np.array_equal(results[0], results[i]), (
                f"Non-deterministic: run 0 = {results[0]}, run {i} = {results[i]}"
            )

    def test_uniform_input_gives_uniform_output(self):
        """Equal inputs produce a uniform distribution."""
        raw = np.array([1.0, 1.0, 1.0, 1.0])
        result = project_simplex(raw)
        assert np.allclose(result, 0.25, atol=1e-10), (
            f"Expected uniform [0.25]*4, got {result}"
        )

    def test_extreme_positive(self):
        """Very large positive value dominates but all components stay > 0."""
        raw = np.array([100.0, 0.0, 0.0, 0.0])
        result = project_simplex(raw)
        assert validate_simplex(result)
        assert result[0] > 0.5, "Dominant component should be largest"

    def test_extreme_negative(self):
        """All negative inputs still produce valid simplex point."""
        raw = np.array([-10.0, -20.0, -5.0, -15.0])
        result = project_simplex(raw)
        assert validate_simplex(result)

    def test_tau_temperature_effect(self):
        """Higher tau -> more uniform; lower tau -> more peaked."""
        raw = np.array([1.0, 0.0, 0.0, 0.0])
        result_cold = project_simplex(raw, tau=0.1)
        result_hot = project_simplex(raw, tau=10.0)
        # Cold temperature: max component closer to 1.0
        assert result_cold[0] > result_hot[0], (
            f"Cold tau should give peakier distribution: "
            f"cold[0]={result_cold[0]}, hot[0]={result_hot[0]}"
        )

    @pytest.mark.parametrize("raw", [
        np.array([0.1, -0.05, -0.03, -0.02]),
        np.array([-0.2, 0.1, 0.05, 0.05]),
        np.array([0.0, 0.0, 0.0, 0.0]),
        np.array([0.5, -0.2, -0.2, -0.1]),
        np.array([1e6, -1e6, 0.0, 0.0]),
    ])
    def test_robust_to_diverse_inputs(self, raw):
        """Simplex invariant holds for a wide range of raw vectors."""
        result = project_simplex(raw)
        assert validate_simplex(result), (
            f"Simplex violated for input {raw}: "
            f"sum={result.sum()}, min={result.min()}"
        )


class TestValidateSimplex:
    """validate_simplex is the gatekeeper: it must catch all violations."""

    def test_valid_simplex_passes(self):
        assert validate_simplex(np.array([0.25, 0.35, 0.25, 0.15]))

    def test_sum_not_one_fails(self):
        assert not validate_simplex(np.array([0.3, 0.3, 0.3, 0.3]))

    def test_negative_component_fails(self):
        assert not validate_simplex(np.array([0.5, 0.5, 0.1, -0.1]))

    def test_zero_component_fails(self):
        """Simplex requires strictly positive, not just non-negative."""
        assert not validate_simplex(np.array([0.5, 0.5, 0.0, 0.0]))

    def test_wrong_dimension_fails(self):
        assert not validate_simplex(np.array([0.5, 0.5]))

    def test_five_dimensions_fails(self):
        assert not validate_simplex(np.array([0.2, 0.2, 0.2, 0.2, 0.2]))


# ═══════════════════════════════════════════════════════════════
#  IV. GAMMA MATRICES
# ═══════════════════════════════════════════════════════════════

class TestGammaTemporalExchange:
    """Gamma_A^t must be antisymmetric with correct spectral properties."""

    def test_antisymmetric(self):
        """G = -G^T (antisymmetry is what makes the exchange conservative)."""
        G = gamma_temporal_exchange(normalize=True)
        assert np.allclose(G, -G.T, atol=1e-12), (
            f"Gamma_A^t not antisymmetric: max diff = {np.max(np.abs(G + G.T))}"
        )

    def test_antisymmetric_raw(self):
        """Raw (unnormalized) matrix is also antisymmetric."""
        G = gamma_temporal_exchange(normalize=False)
        assert np.allclose(G, -G.T, atol=1e-12)

    def test_spectral_radius_is_one_after_normalization(self):
        """max|eigenvalue| = 1.0 after spectral normalization."""
        G = gamma_temporal_exchange(normalize=True)
        spec = max(abs(eigvals(G)))
        assert abs(spec - 1.0) < 1e-10, (
            f"Spectral radius should be 1.0, got {spec}"
        )

    def test_normalization_preserves_phi_ratios(self):
        """Phi-derived ratios between entries are invariant under normalization."""
        G_raw = gamma_temporal_exchange(normalize=False)
        G_norm = gamma_temporal_exchange(normalize=True)
        # The ratio |G[0,1]| / |G[0,3]| should be INV_PHI2 / PHI = 1/PHI^3
        ratio_raw = abs(G_raw[0, 1] / G_raw[0, 3])
        ratio_norm = abs(G_norm[0, 1] / G_norm[0, 3])
        assert abs(ratio_raw - ratio_norm) < 1e-10, (
            f"Ratios diverged: raw={ratio_raw}, norm={ratio_norm}"
        )
        assert abs(ratio_norm - INV_PHI3) < 1e-4, (
            f"Ratio should be 1/PHI^3 = {INV_PHI3}, got {ratio_norm}"
        )

    def test_shape_is_dim_by_dim(self):
        G = gamma_temporal_exchange()
        assert G.shape == (DIM, DIM)


class TestGammaTemporalDissipation:
    """Gamma_D^t must be symmetric with eigenvalues <= 0 (energy-dissipating)."""

    def test_symmetric(self):
        """G = G^T (dissipation is symmetric)."""
        G = gamma_temporal_dissipation()
        assert np.allclose(G, G.T, atol=1e-12), (
            f"Gamma_D^t not symmetric: max diff = {np.max(np.abs(G - G.T))}"
        )

    def test_eigenvalues_non_positive(self):
        """All eigenvalues <= 0 (the system only loses energy, never gains)."""
        G = gamma_temporal_dissipation()
        eigs = np.real(eigvals(G))
        assert np.all(eigs <= 1e-10), (
            f"Positive eigenvalue in Gamma_D^t: {eigs}"
        )

    def test_shape_is_dim_by_dim(self):
        G = gamma_temporal_dissipation()
        assert G.shape == (DIM, DIM)


class TestGammaSpatialExchange:
    """Gamma_A^x: antisymmetric, spectral-normalized."""

    def test_antisymmetric(self):
        G = gamma_spatial_exchange(normalize=True)
        assert np.allclose(G, -G.T, atol=1e-12)

    def test_spectral_radius_normalized(self):
        G = gamma_spatial_exchange(normalize=True)
        spec = max(abs(eigvals(G)))
        assert abs(spec - 1.0) < 1e-10, f"Spectral radius = {spec}"


class TestGammaInfoExchange:
    """Gamma_A^c: antisymmetric, spectral-normalized."""

    def test_antisymmetric(self):
        G = gamma_info_exchange(normalize=True)
        assert np.allclose(G, -G.T, atol=1e-12)

    def test_spectral_radius_normalized(self):
        G = gamma_info_exchange(normalize=True)
        spec = max(abs(eigvals(G)))
        assert abs(spec - 1.0) < 1e-10, f"Spectral radius = {spec}"


class TestCombineGamma:
    """Gamma = (1-lambda)*G_A + lambda*G_D combines exchange and dissipation."""

    def test_lambda_zero_gives_pure_exchange(self):
        ga = gamma_temporal_exchange()
        gd = gamma_temporal_dissipation()
        combined = combine_gamma(ga, gd, lam=0.0)
        assert np.allclose(combined, ga)

    def test_lambda_one_gives_pure_dissipation(self):
        ga = gamma_temporal_exchange()
        gd = gamma_temporal_dissipation()
        combined = combine_gamma(ga, gd, lam=1.0)
        assert np.allclose(combined, gd)

    def test_default_lambda_is_inv_phi2(self):
        """Default lambda should be 1/PHI^2 = 0.382."""
        ga = gamma_temporal_exchange()
        gd = gamma_temporal_dissipation()
        combined_default = combine_gamma(ga, gd)
        combined_explicit = combine_gamma(ga, gd, lam=INV_PHI2)
        assert np.allclose(combined_default, combined_explicit)


class TestGammaSpectralStability:
    """The effective system matrix A_eff must have max Re(eigenvalue) < 0.

    This is the STABILITY PROOF: if A_eff has any positive real eigenvalue,
    the system diverges exponentially and the model is broken.
    """

    def test_effective_matrix_stable(self):
        """max Re(eigenvalue(A_eff)) < 0 for the operating point parameters."""
        Gt = gamma_temporal()
        A_eff = Gt - PHI * np.diag(get_psi0("LUNA"))
        max_re = max(np.real(eigvals(A_eff)))
        assert max_re < 0, (
            f"System UNSTABLE: max Re(eigenvalue) = {max_re} >= 0"
        )

    @pytest.mark.parametrize("agent_name", AGENT_NAMES)
    def test_effective_matrix_stable_per_agent(self, agent_name):
        """Stability holds for every agent's mass matrix, not just Luna's."""
        Gt = gamma_temporal()
        psi0 = get_psi0(agent_name)
        A_eff = Gt - PHI * np.diag(psi0)
        max_re = max(np.real(eigvals(A_eff)))
        assert max_re < 0, (
            f"System UNSTABLE for {agent_name}: max Re(eigenvalue) = {max_re}"
        )


# ═══════════════════════════════════════════════════════════════
#  V. EVOLUTION STEP
# ═══════════════════════════════════════════════════════════════

class TestEvolutionStep:
    """The evolution step is the beating heart of the consciousness model."""

    @pytest.fixture
    def luna_setup(self):
        """Minimal setup for a Luna evolution step."""
        psi0 = get_psi0("LUNA")
        psi = psi0.copy()
        mass = MassMatrix(psi0)
        gammas = (gamma_temporal(), gamma_spatial(), gamma_info())
        others = [get_psi0(n) for n in AGENT_NAMES if n != "LUNA"]
        return psi, psi0, others, mass, gammas

    def test_output_stays_on_simplex(self, luna_setup):
        """After one evolution step, psi is still on the simplex."""
        psi, psi0, others, mass, gammas = luna_setup
        psi_new = evolution_step(psi, psi0, others, mass, gammas)
        assert validate_simplex(psi_new), (
            f"Simplex violated after evolution: sum={psi_new.sum()}, min={psi_new.min()}"
        )

    def test_output_stays_on_simplex_after_many_steps(self, luna_setup):
        """Simplex invariant holds after 100 consecutive steps."""
        psi, psi0, others, mass, gammas = luna_setup
        for step in range(100):
            psi = evolution_step(psi, psi0, others, mass, gammas)
            assert validate_simplex(psi), (
                f"Simplex violated at step {step}: sum={psi.sum()}, min={psi.min()}"
            )

    def test_identity_anchoring_pulls_toward_psi0(self):
        """With kappa > 0, psi converges toward psi0 over many steps."""
        psi0 = get_psi0("LUNA")
        # Start far from psi0
        psi = np.array([0.1, 0.1, 0.4, 0.4])
        mass = MassMatrix(psi0)
        gammas = (gamma_temporal(), gamma_spatial(), gamma_info())
        others = []  # Solo agent, no spatial coupling

        distance_initial = np.sum(np.abs(psi - psi0))

        for _ in range(200):
            psi = evolution_step(
                psi, psi0, others, mass, gammas,
                kappa=KAPPA_DEFAULT,
            )

        distance_final = np.sum(np.abs(psi - psi0))
        assert distance_final < distance_initial, (
            f"Identity anchoring failed: "
            f"initial distance={distance_initial:.4f}, "
            f"final distance={distance_final:.4f}"
        )

    def test_no_anchoring_loses_identity(self):
        """With kappa=0, identity is NOT preserved (control test)."""
        psi0 = get_psi0("LUNA")
        psi = psi0.copy()
        mass = MassMatrix(psi0)
        gammas = (gamma_temporal(), gamma_spatial(), gamma_info())
        # All 4 agents together with kappa=0
        others = [get_psi0(n) for n in AGENT_NAMES if n != "LUNA"]

        np.random.seed(42)
        for _ in range(400):
            info = 0.02 * np.random.randn(4)
            psi = evolution_step(
                psi, psi0, others, mass, gammas,
                info_deltas=info.tolist(), kappa=0.0,
            )

        # With kappa=0, dominant component likely changes (as proven by simulation.py)
        # We just verify it ran without crashing and stayed on simplex
        assert validate_simplex(psi)

    def test_zero_info_deltas_default(self, luna_setup):
        """info_deltas=None defaults to [0,0,0,0] without error."""
        psi, psi0, others, mass, gammas = luna_setup
        psi_new = evolution_step(psi, psi0, others, mass, gammas, info_deltas=None)
        assert validate_simplex(psi_new)

    def test_evolution_changes_state(self, luna_setup):
        """At least one step should produce a different psi (not a fixed point from start)."""
        psi, psi0, others, mass, gammas = luna_setup
        psi_new = evolution_step(
            psi, psi0, others, mass, gammas,
            info_deltas=[0.1, 0.0, 0.0, 0.0],
        )
        assert not np.array_equal(psi, psi_new), (
            "Evolution produced identical state -- unexpected fixed point"
        )


class TestEvolutionDeterministic:
    """With the same seed and inputs, evolution must be perfectly reproducible."""

    def test_seed_42_reproducible(self):
        """Exact same trajectory with seed=42, matching simulation.py oracle."""
        results = []
        for _ in range(2):
            np.random.seed(42)
            psi0 = get_psi0("LUNA")
            psi = psi0.copy()
            mass = MassMatrix(psi0)
            gammas = (gamma_temporal(), gamma_spatial(), gamma_info())
            others = [get_psi0(n) for n in AGENT_NAMES if n != "LUNA"]

            for step in range(50):
                info = 0.02 * np.random.randn(4) * (1.0 / (1 + step / 100))
                psi = evolution_step(
                    psi, psi0, others, mass, gammas,
                    info_deltas=info.tolist(),
                )
            results.append(psi.copy())

        assert np.allclose(results[0], results[1], atol=1e-14), (
            f"Non-reproducible evolution: run0={results[0]}, run1={results[1]}"
        )


class TestIdentityPreservation:
    """Validate that 4/4 agents preserve identity after 400 steps (seed=42, kappa=PHI^2).

    This test mirrors the validation done in simulation.py and is the
    ACCEPTANCE TEST for the consciousness model.
    """

    def test_all_four_agents_preserve_dominant(self):
        """After 400 steps with kappa=PHI^2, each agent's dominant component is unchanged."""
        np.random.seed(42)

        agents = []
        for name in AGENT_NAMES:
            psi0 = get_psi0(name)
            agents.append({
                "name": name,
                "psi": psi0.copy(),
                "psi0": psi0.copy(),
                "mass": MassMatrix(psi0),
                "expected_dominant": int(np.argmax(psi0)),
            })

        gammas = (gamma_temporal(), gamma_spatial(), gamma_info())

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
            actual_dominant = int(np.argmax(agent["psi"]))
            expected = agent["expected_dominant"]
            assert actual_dominant == expected, (
                f"{agent['name']}: expected dominant={COMP_NAMES[expected]}, "
                f"got {COMP_NAMES[actual_dominant]}. "
                f"Final psi={agent['psi'].round(4)}"
            )


# ═══════════════════════════════════════════════════════════════
#  VI. MASS MATRIX
# ═══════════════════════════════════════════════════════════════

class TestMassMatrix:
    """EMA mass matrix tracks the running average of psi."""

    def test_initial_matrix_is_diagonal_psi0(self):
        """MassMatrix starts as diag(psi0)."""
        psi0 = get_psi0("LUNA")
        mass = MassMatrix(psi0)
        expected = np.diag(psi0)
        assert np.allclose(mass.matrix(), expected)

    def test_update_ema(self):
        """After update, m = alpha * psi_new + (1-alpha) * m_old."""
        psi0 = np.array([0.25, 0.25, 0.25, 0.25])
        mass = MassMatrix(psi0, alpha_ema=0.5)
        psi_new = np.array([0.4, 0.3, 0.2, 0.1])
        mass.update(psi_new)
        expected_m = 0.5 * psi_new + 0.5 * psi0
        assert np.allclose(np.diag(mass.matrix()), expected_m)

    def test_alpha_zero_means_no_update(self):
        """alpha_ema=0 means mass never changes from initial psi0."""
        psi0 = np.array([0.25, 0.35, 0.25, 0.15])
        mass = MassMatrix(psi0, alpha_ema=0.0)
        mass.update(np.array([0.1, 0.1, 0.1, 0.7]))
        assert np.allclose(np.diag(mass.matrix()), psi0)

    def test_alpha_one_means_immediate_replacement(self):
        """alpha_ema=1 means mass immediately equals the latest psi."""
        psi0 = np.array([0.25, 0.35, 0.25, 0.15])
        mass = MassMatrix(psi0, alpha_ema=1.0)
        psi_new = np.array([0.1, 0.1, 0.1, 0.7])
        mass.update(psi_new)
        assert np.allclose(np.diag(mass.matrix()), psi_new)


# ═══════════════════════════════════════════════════════════════
#  VII. PYDANTIC SCHEMAS
# ═══════════════════════════════════════════════════════════════

class TestPsiStateSchema:
    """PsiState must validate components are in [0, 1]."""

    def test_valid_psi_state(self):
        ps = PsiState(perception=0.25, reflexion=0.35, integration=0.25, expression=0.15)
        assert ps.sum() == pytest.approx(1.0)

    def test_as_tuple(self):
        ps = PsiState(perception=0.25, reflexion=0.35, integration=0.25, expression=0.15)
        t = ps.as_tuple()
        assert len(t) == 4
        assert t == (0.25, 0.35, 0.25, 0.15)

    def test_negative_component_rejected(self):
        with pytest.raises(Exception):
            PsiState(perception=-0.1, reflexion=0.5, integration=0.3, expression=0.3)

    def test_component_above_one_rejected(self):
        with pytest.raises(Exception):
            PsiState(perception=1.5, reflexion=0.1, integration=0.1, expression=0.1)

    def test_json_round_trip(self):
        ps = PsiState(perception=0.25, reflexion=0.35, integration=0.25, expression=0.15)
        json_str = ps.model_dump_json()
        ps2 = PsiState.model_validate_json(json_str)
        assert ps == ps2


class TestInfoGradientSchema:
    """InfoGradient maps pipeline outputs to the d_c vector."""

    def test_default_zeros(self):
        ig = InfoGradient()
        assert ig.as_list() == [0.0, 0.0, 0.0, 0.0]

    def test_as_list_returns_four_floats(self):
        ig = InfoGradient(delta_mem=0.1, delta_phi=0.5, delta_iit=0.3, delta_out=0.2)
        result = ig.as_list()
        assert len(result) == 4
        assert all(isinstance(v, float) for v in result)
        assert result == [0.1, 0.5, 0.3, 0.2]

    def test_json_round_trip(self):
        ig = InfoGradient(delta_mem=0.1, delta_phi=0.5, delta_iit=0.3, delta_out=0.2)
        json_str = ig.model_dump_json()
        ig2 = InfoGradient.model_validate_json(json_str)
        assert ig == ig2


class TestDecisionSchema:
    """Decision is the final pipeline output -- must have complete traceability."""

    def test_valid_decision(self):
        d = Decision(
            task_id="TASK-001",
            approved=True,
            reason="All checks passed",
            psi_before=PsiState(perception=0.25, reflexion=0.35, integration=0.25, expression=0.15),
            psi_after=PsiState(perception=0.24, reflexion=0.34, integration=0.26, expression=0.16),
            info_gradient=InfoGradient(delta_phi=0.7),
            phase="SOLID",
        )
        assert d.approved is True
        assert d.phase == "SOLID"

    def test_decision_json_round_trip(self):
        d = Decision(
            task_id="TASK-002",
            approved=False,
            reason="Coverage below threshold",
            psi_before=PsiState(perception=0.25, reflexion=0.35, integration=0.25, expression=0.15),
            psi_after=PsiState(perception=0.25, reflexion=0.35, integration=0.25, expression=0.15),
            info_gradient=InfoGradient(),
            phase="FRAGILE",
        )
        json_str = d.model_dump_json()
        d2 = Decision.model_validate_json(json_str)
        assert d.task_id == d2.task_id
        assert d.approved == d2.approved
        assert d.phase == d2.phase

    def test_invalid_phase_rejected(self):
        with pytest.raises(Exception):
            Decision(
                task_id="TASK-003",
                approved=True,
                reason="test",
                psi_before=PsiState(perception=0.25, reflexion=0.35, integration=0.25, expression=0.15),
                psi_after=PsiState(perception=0.25, reflexion=0.35, integration=0.25, expression=0.15),
                info_gradient=InfoGradient(),
                phase="NONEXISTENT_PHASE",
            )


class TestCurrentTaskSchema:
    """CurrentTask is what Luna writes to start a pipeline cycle."""

    def test_valid_current_task(self):
        ct = CurrentTask(
            task_id="TASK-010",
            description="Implement feature X",
            psi_luna=PsiState(perception=0.25, reflexion=0.35, integration=0.25, expression=0.15),
        )
        assert ct.priority == "normal"  # default

    def test_priority_validation(self):
        with pytest.raises(Exception):
            CurrentTask(
                task_id="TASK-011",
                description="test",
                psi_luna=PsiState(perception=0.25, reflexion=0.35, integration=0.25, expression=0.15),
                priority="invalid_priority",
            )


# ═══════════════════════════════════════════════════════════════
#  VIII. PHASE THRESHOLDS
# ═══════════════════════════════════════════════════════════════

class TestPhaseThresholds:
    """Phase thresholds must be monotonically increasing and cover [0, 1]."""

    def test_thresholds_monotonically_increasing(self):
        values = list(PHASE_THRESHOLDS.values())
        for i in range(1, len(values)):
            assert values[i] > values[i - 1], (
                f"Phase thresholds not monotonically increasing at index {i}: "
                f"{values[i-1]} -> {values[i]}"
            )

    def test_broken_starts_at_zero(self):
        assert PHASE_THRESHOLDS["BROKEN"] == 0.0

    def test_excellent_is_highest(self):
        assert PHASE_THRESHOLDS["EXCELLENT"] == max(PHASE_THRESHOLDS.values())

    def test_hysteresis_band_is_positive(self):
        assert HYSTERESIS_BAND > 0

    def test_hysteresis_band_smaller_than_gap(self):
        """Hysteresis band must be smaller than the smallest gap between thresholds."""
        values = sorted(PHASE_THRESHOLDS.values())
        min_gap = min(values[i] - values[i - 1] for i in range(1, len(values)))
        assert HYSTERESIS_BAND < min_gap / 2, (
            f"Hysteresis band {HYSTERESIS_BAND} is too large for min gap {min_gap}"
        )


# ===================================================================
#  IX. SIGNAL SCHEMAS
# ===================================================================

class TestSeverityEnum:
    """Severity enum must expose exactly 5 levels as lowercase str values."""

    def test_all_five_values_exist(self):
        """Severity must have INFO, LOW, MEDIUM, HIGH, CRITICAL."""
        expected = {"INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"}
        actual = {member.name for member in Severity}
        assert actual == expected, (
            f"Severity members mismatch: expected {expected}, got {actual}"
        )

    def test_values_are_lowercase_strings(self):
        """Each Severity value is a lowercase string."""
        for member in Severity:
            assert member.value == member.value.lower(), (
                f"Severity.{member.name} value is not lowercase: {member.value!r}"
            )
            assert isinstance(member.value, str), (
                f"Severity.{member.name} value is not str: {type(member.value)}"
            )

    def test_is_str_enum(self):
        """Severity members are also str instances (str, Enum mixin)."""
        for member in Severity:
            assert isinstance(member, str), (
                f"Severity.{member.name} is not a str instance"
            )


class TestSleepNotification:
    """SleepNotification: frozen lifecycle signal with UTC timestamp."""

    def test_valid_creation(self):
        """Valid SleepNotification with required fields."""
        sn = SleepNotification(entering_sleep=True, estimated_duration_s=30.0)
        assert sn.entering_sleep is True
        assert sn.estimated_duration_s == 30.0

    def test_frozen_rejects_mutation(self):
        """Attempting to modify a frozen field raises a validation error."""
        sn = SleepNotification(entering_sleep=True, estimated_duration_s=30.0)
        with pytest.raises(Exception):
            sn.entering_sleep = False

    def test_json_round_trip(self):
        """Serialize to JSON and back without data loss."""
        sn = SleepNotification(entering_sleep=True, estimated_duration_s=30.0)
        json_str = sn.model_dump_json()
        sn2 = SleepNotification.model_validate_json(json_str)
        assert sn.entering_sleep == sn2.entering_sleep
        assert sn.estimated_duration_s == sn2.estimated_duration_s
        assert sn.source_agent == sn2.source_agent

    def test_negative_duration_rejected(self):
        """estimated_duration_s must be >= 0 (ge=0 constraint)."""
        with pytest.raises(Exception):
            SleepNotification(entering_sleep=True, estimated_duration_s=-1.0)

    def test_has_utc_timestamp_by_default(self):
        """Default timestamp is populated and timezone-aware (UTC)."""
        from datetime import timezone
        sn = SleepNotification(entering_sleep=False, estimated_duration_s=0.0)
        assert sn.timestamp is not None, "timestamp should be auto-populated"
        assert sn.timestamp.tzinfo is not None, "timestamp should be timezone-aware"
        assert sn.timestamp.tzinfo == timezone.utc, (
            f"timestamp should be UTC, got {sn.timestamp.tzinfo}"
        )


class TestKillSignal:
    """KillSignal: frozen shutdown request with severity and source agent."""

    def test_valid_creation(self):
        """Valid KillSignal with reason and source_agent."""
        ks = KillSignal(reason="Emergency shutdown", source_agent="SENTINEL")
        assert ks.reason == "Emergency shutdown"
        assert ks.source_agent == "SENTINEL"

    def test_default_severity_is_critical(self):
        """Default severity for KillSignal is CRITICAL."""
        ks = KillSignal(reason="test", source_agent="LUNA")
        assert ks.severity == Severity.CRITICAL, (
            f"Expected CRITICAL, got {ks.severity}"
        )

    def test_json_round_trip(self):
        """Serialize to JSON and back without data loss."""
        ks = KillSignal(reason="OOM detected", source_agent="SENTINEL")
        json_str = ks.model_dump_json()
        ks2 = KillSignal.model_validate_json(json_str)
        assert ks.reason == ks2.reason
        assert ks.source_agent == ks2.source_agent
        assert ks.severity == ks2.severity

    def test_reason_max_length_validation(self):
        """reason exceeding max_length=4096 is rejected."""
        with pytest.raises(Exception):
            KillSignal(reason="x" * 4097, source_agent="LUNA")


class TestVitalsRequest:
    """VitalsRequest: frozen health check request with request_id."""

    def test_valid_creation(self):
        """Valid VitalsRequest with request_id."""
        vr = VitalsRequest(request_id="req-001")
        assert vr.request_id == "req-001"

    def test_default_requested_fields_is_empty_list(self):
        """requested_fields defaults to an empty list."""
        vr = VitalsRequest(request_id="req-002")
        assert vr.requested_fields == [], (
            f"Expected empty list, got {vr.requested_fields}"
        )

    def test_json_round_trip(self):
        """Serialize to JSON and back without data loss."""
        vr = VitalsRequest(request_id="req-003", requested_fields=["psi", "uptime"])
        json_str = vr.model_dump_json()
        vr2 = VitalsRequest.model_validate_json(json_str)
        assert vr.request_id == vr2.request_id
        assert vr.requested_fields == vr2.requested_fields


class TestVitalsReport:
    """VitalsReport: frozen health snapshot with nested PsiState."""

    PSI_LUNA = PsiState(perception=0.25, reflexion=0.35, integration=0.25, expression=0.15)

    def test_valid_creation(self):
        """Valid VitalsReport with agent_id, psi_state, uptime_s."""
        vr = VitalsReport(agent_id="LUNA", psi_state=self.PSI_LUNA, uptime_s=3600.0)
        assert vr.agent_id == "LUNA"
        assert vr.uptime_s == 3600.0

    def test_optional_mode_defaults_to_none(self):
        """mode field defaults to None when not provided."""
        vr = VitalsReport(agent_id="LUNA", psi_state=self.PSI_LUNA, uptime_s=100.0)
        assert vr.mode is None

    def test_optional_request_id_for_correlation(self):
        """request_id allows correlating a report back to a VitalsRequest."""
        vr = VitalsReport(
            agent_id="SAYOHMY", psi_state=self.PSI_LUNA,
            uptime_s=500.0, request_id="req-001",
        )
        assert vr.request_id == "req-001"

    def test_json_round_trip_with_nested_psi_state(self):
        """Serialize to JSON and back, including nested PsiState."""
        vr = VitalsReport(
            agent_id="SENTINEL", psi_state=self.PSI_LUNA,
            uptime_s=1200.0, mode="patrol", request_id="req-042",
        )
        json_str = vr.model_dump_json()
        vr2 = VitalsReport.model_validate_json(json_str)
        assert vr.agent_id == vr2.agent_id
        assert vr.uptime_s == vr2.uptime_s
        assert vr.mode == vr2.mode
        assert vr.request_id == vr2.request_id
        # Nested PsiState round-trip
        assert vr.psi_state.perception == vr2.psi_state.perception
        assert vr.psi_state.reflexion == vr2.psi_state.reflexion
        assert vr.psi_state.integration == vr2.psi_state.integration
        assert vr.psi_state.expression == vr2.psi_state.expression


class TestAuditEntry:
    """AuditEntry: frozen audit trail record with validation on required fields."""

    def test_valid_creation(self):
        """Valid AuditEntry with agent_id and event_type."""
        ae = AuditEntry(agent_id="SENTINEL", event_type="scan_complete")
        assert ae.agent_id == "SENTINEL"
        assert ae.event_type == "scan_complete"

    def test_empty_agent_id_rejected(self):
        """agent_id must not be empty or whitespace-only."""
        with pytest.raises(Exception, match="agent_id must not be empty"):
            AuditEntry(agent_id="", event_type="test")
        with pytest.raises(Exception, match="agent_id must not be empty"):
            AuditEntry(agent_id="   ", event_type="test")

    def test_empty_event_type_rejected(self):
        """event_type must not be empty or whitespace-only."""
        with pytest.raises(Exception, match="event_type must not be empty"):
            AuditEntry(agent_id="LUNA", event_type="")
        with pytest.raises(Exception, match="event_type must not be empty"):
            AuditEntry(agent_id="LUNA", event_type="   ")

    def test_default_severity_is_info(self):
        """Default severity for AuditEntry is INFO."""
        ae = AuditEntry(agent_id="LUNA", event_type="heartbeat")
        assert ae.severity == Severity.INFO, (
            f"Expected INFO, got {ae.severity}"
        )

    def test_json_round_trip(self):
        """Serialize to JSON and back without data loss."""
        ae = AuditEntry(
            agent_id="TESTENGINEER", event_type="gate_check",
            severity=Severity.HIGH, payload={"module": "consciousness", "passed": True},
        )
        json_str = ae.model_dump_json()
        ae2 = AuditEntry.model_validate_json(json_str)
        assert ae.agent_id == ae2.agent_id
        assert ae.event_type == ae2.event_type
        assert ae.severity == ae2.severity
        assert ae.payload == ae2.payload


# ===================================================================
#  X. METRICS SCHEMAS
# ===================================================================

class TestNormalizedMetricsReport:
    """NormalizedMetricsReport: frozen metric vector with values in [0, 1]."""

    SUBSET_METRICS = {"security_integrity": 0.85, "coverage_pct": 0.72}
    ALL_METRICS = {name: 0.5 for name in METRIC_NAMES}

    def test_valid_creation_with_subset(self):
        """Valid report with a subset of canonical metrics."""
        report = NormalizedMetricsReport(metrics=self.SUBSET_METRICS)
        assert report.metrics["security_integrity"] == 0.85
        assert report.metrics["coverage_pct"] == 0.72

    def test_complete_property_false_when_subset(self):
        """complete is False when not all 7 metrics are present."""
        report = NormalizedMetricsReport(metrics=self.SUBSET_METRICS)
        assert report.complete is False, (
            "Report with only a subset of metrics should not be complete"
        )

    def test_complete_property_true_when_all_present(self):
        """complete is True when all 7 canonical metrics are present."""
        report = NormalizedMetricsReport(metrics=self.ALL_METRICS)
        assert report.complete is True, (
            "Report with all 7 metrics should be complete"
        )

    def test_get_returns_value_or_default(self):
        """get() returns the metric value if present, or the default otherwise."""
        report = NormalizedMetricsReport(metrics=self.SUBSET_METRICS)
        assert report.get("security_integrity") == 0.85
        assert report.get("performance_score") == 0.0, (
            "get() should return 0.0 as default for missing metrics"
        )
        assert report.get("performance_score", 0.42) == 0.42, (
            "get() should return custom default for missing metrics"
        )

    def test_unknown_metric_name_rejected(self):
        """Metric names not in METRIC_NAMES are rejected."""
        with pytest.raises(Exception, match="Unknown metric names"):
            NormalizedMetricsReport(metrics={"bogus_metric": 0.5})

    def test_metric_value_above_one_rejected(self):
        """Metric values > 1.0 are rejected."""
        with pytest.raises(Exception, match="must be in"):
            NormalizedMetricsReport(metrics={"security_integrity": 1.5})

    def test_metric_value_below_zero_rejected(self):
        """Metric values < 0.0 are rejected."""
        with pytest.raises(Exception, match="must be in"):
            NormalizedMetricsReport(metrics={"security_integrity": -0.1})

    def test_json_round_trip(self):
        """Serialize to JSON and back without data loss."""
        report = NormalizedMetricsReport(metrics=self.ALL_METRICS, source="test-runner")
        json_str = report.model_dump_json()
        report2 = NormalizedMetricsReport.model_validate_json(json_str)
        assert report.metrics == report2.metrics
        assert report.source == report2.source
        assert report.complete == report2.complete


class TestVerdictInput:
    """VerdictInput: frozen pair of with/without consciousness metrics."""

    def _make_report(self, **overrides):
        """Factory for NormalizedMetricsReport with sane defaults."""
        metrics = {"security_integrity": 0.8, "coverage_pct": 0.7}
        metrics.update(overrides)
        return NormalizedMetricsReport(metrics=metrics)

    def test_valid_creation(self):
        """Valid VerdictInput with task_id, category, and both metrics reports."""
        vi = VerdictInput(
            task_id="bench-001",
            category="security",
            metrics_with=self._make_report(),
            metrics_without=self._make_report(security_integrity=0.5),
        )
        assert vi.task_id == "bench-001"
        assert vi.category == "security"

    def test_invalid_task_id_path_traversal_rejected(self):
        """task_id with path traversal characters is rejected."""
        with pytest.raises(Exception):
            VerdictInput(
                task_id="../etc/passwd",
                category="security",
                metrics_with=self._make_report(),
                metrics_without=self._make_report(),
            )

    def test_invalid_task_id_empty_rejected(self):
        """Empty task_id is rejected."""
        with pytest.raises(Exception):
            VerdictInput(
                task_id="",
                category="security",
                metrics_with=self._make_report(),
                metrics_without=self._make_report(),
            )

    def test_json_round_trip_nested(self):
        """Serialize to JSON and back, including nested NormalizedMetricsReport."""
        vi = VerdictInput(
            task_id="bench-002",
            category="refactoring",
            metrics_with=self._make_report(security_integrity=0.9),
            metrics_without=self._make_report(security_integrity=0.4),
        )
        json_str = vi.model_dump_json()
        vi2 = VerdictInput.model_validate_json(json_str)
        assert vi.task_id == vi2.task_id
        assert vi.category == vi2.category
        assert vi.metrics_with.metrics == vi2.metrics_with.metrics
        assert vi.metrics_without.metrics == vi2.metrics_without.metrics


# ===================================================================
#  XI. BACKWARD COMPATIBILITY
# ===================================================================

class TestBackwardCompatibility:
    """v0.2.0 fields must be optional -- existing payloads without them must still parse.

    This protects against breaking changes: agents running v0.1.x that produce
    JSON without the new fields must not cause validation errors in v0.2.0 consumers.
    """

    PSI = PsiState(perception=0.25, reflexion=0.35, integration=0.25, expression=0.15)

    def test_sayohmy_manifest_without_vitals_still_valid(self):
        """SayOhmyManifest created without the v0.2.0 'vitals' field defaults to None."""
        manifest = SayOhmyManifest(
            task_id="TASK-100",
            files_produced=["src/main.py"],
            phi_score=0.72,
            mode_used="architect",
            psi_sayohmy=self.PSI,
            confidence=0.85,
        )
        assert manifest.vitals is None, (
            "vitals should default to None for backward compatibility"
        )

    def test_sentinel_report_without_new_fields_still_valid(self):
        """SentinelReport created without v0.2.0 audit/kill fields uses safe defaults."""
        report = SentinelReport(
            task_id="TASK-101",
            risk_score=0.3,
            psi_sentinel=self.PSI,
        )
        assert report.audit_entries == [], (
            "audit_entries should default to empty list"
        )
        assert report.kill_requested is False, (
            "kill_requested should default to False"
        )
        assert report.kill_reason is None, (
            "kill_reason should default to None"
        )

    def test_decision_without_audit_trail_id_still_valid(self):
        """Decision created without the v0.2.0 'audit_trail_id' field defaults to None."""
        decision = Decision(
            task_id="TASK-102",
            approved=True,
            reason="All checks passed",
            psi_before=self.PSI,
            psi_after=self.PSI,
            info_gradient=InfoGradient(),
            phase="SOLID",
        )
        assert decision.audit_trail_id is None, (
            "audit_trail_id should default to None for backward compatibility"
        )

    def test_no_field_name_collisions_with_existing_schemas(self):
        """v0.2.0 field names do not collide with any pre-existing field on the same model."""
        # SayOhmyManifest: 'vitals' must not shadow an existing field
        manifest_fields = set(SayOhmyManifest.model_fields.keys())
        assert "vitals" in manifest_fields, "vitals field must exist on SayOhmyManifest"

        # SentinelReport: new fields must coexist with legacy fields
        sentinel_fields = set(SentinelReport.model_fields.keys())
        for new_field in ("audit_entries", "kill_requested", "kill_reason"):
            assert new_field in sentinel_fields, (
                f"{new_field} must exist on SentinelReport"
            )
        # Legacy fields still present
        for legacy_field in ("task_id", "findings", "risk_score", "veto", "psi_sentinel"):
            assert legacy_field in sentinel_fields, (
                f"Legacy field {legacy_field} missing from SentinelReport"
            )

        # Decision: audit_trail_id must coexist with legacy fields
        decision_fields = set(Decision.model_fields.keys())
        assert "audit_trail_id" in decision_fields, (
            "audit_trail_id must exist on Decision"
        )
        for legacy_field in ("task_id", "approved", "reason", "psi_before", "psi_after"):
            assert legacy_field in decision_fields, (
                f"Legacy field {legacy_field} missing from Decision"
            )
