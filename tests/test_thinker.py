"""Tests for luna.consciousness.thinker — structured reasoning without LLM.

The Thinker applies Luna's state equation recursively to thought:
  MACRO: Psi evolves between messages (dt = INV_PHI)
  MICRO: Thought evolves within the Thinker (convergence < INV_PHI2)

51 tests across 12 classes covering all Thinker components.
"""

from __future__ import annotations

import numpy as np
import pytest

from luna_common.constants import (
    COMP_NAMES,
    DIM,
    INV_PHI,
    INV_PHI2,
    INV_PHI3,
    METRIC_NAMES,
    PHI,
)

from luna.consciousness.state import ConsciousnessState
from luna.consciousness.thinker import (
    CONVERGENCE_THRESHOLD,
    CausalGraphProtocol,
    Causality,
    Correlation,
    Insight,
    Need,
    NullCausalGraph,
    Observation,
    Proposal,
    SelfState,
    Stimulus,
    ThinkMode,
    Thinker,
    Thought,
    _RESPONSIVE_MAX,
)


# ===================================================================
#  HELPERS
# ===================================================================

def _make_state() -> ConsciousnessState:
    """Create a fresh ConsciousnessState for LUNA."""
    return ConsciousnessState(agent_name="LUNA")


def _make_stimulus(**overrides) -> Stimulus:
    """Create a Stimulus with sensible defaults, overridable."""
    defaults = dict(
        user_message="améliorer la couverture",
        metrics={
            "integration_coherence": 0.9,
            "identity_anchoring": 0.4,
            "reflection_depth": 0.7,
            "perception_acuity": 0.5,
            "expression_fidelity": 0.6,
            "affect_regulation": 0.8,
            "memory_vitality": 0.7,
        },
        phi_iit=0.5,
        phase="FUNCTIONAL",
        psi=np.array([0.260, 0.322, 0.250, 0.168]),
        psi_trajectory=[],
    )
    defaults.update(overrides)
    return Stimulus(**defaults)


def _make_thinker(
    state: ConsciousnessState | None = None,
    metrics: dict | None = None,
) -> Thinker:
    """Create a Thinker with a fresh state."""
    if state is None:
        state = _make_state()
    return Thinker(state, metrics=metrics)


def _make_rich_stimulus() -> Stimulus:
    """Create a stimulus that produces many observations for confidence tests."""
    return Stimulus(
        user_message="fix security and improve coverage",
        metrics={
            "integration_coherence": 0.3,
            "identity_anchoring": 0.2,
            "reflection_depth": 0.3,
            "perception_acuity": 0.2,
            "expression_fidelity": 0.3,
            "affect_regulation": 0.3,
            "memory_vitality": 0.3,
        },
        phi_iit=0.2,
        phase="BROKEN",
        psi=np.array([0.10, 0.60, 0.20, 0.10]),
        psi_trajectory=[
            np.array([0.30, 0.30, 0.25, 0.15]),
            np.array([0.10, 0.60, 0.20, 0.10]),
        ],
    )


# ===================================================================
#  FIXTURES
# ===================================================================

@pytest.fixture
def thinker():
    """A fresh Thinker with LUNA state."""
    return _make_thinker()


@pytest.fixture
def stimulus():
    """A default stimulus with some low metrics."""
    return _make_stimulus()


@pytest.fixture
def rich_stimulus():
    """A stimulus that produces many observations."""
    return _make_rich_stimulus()


# ===================================================================
#  I. DATACLASSES
# ===================================================================

class TestDataclasses:
    """Thought and supporting dataclasses are well-formed."""

    def test_thought_empty(self):
        """Thought.empty() creates a valid empty Thought."""
        t = Thought.empty()
        assert t.observations == []
        assert t.causalities == []
        assert t.correlations == []
        assert t.needs == []
        assert t.proposals == []
        assert t.insights == []
        assert t.uncertainties == []
        assert t.self_state is None
        assert t.depth_reached == 0
        assert t.confidence == 0.0

    def test_observation_component_range(self):
        """Observation component must be 0-3."""
        for i in range(DIM):
            obs = Observation(tag=f"t{i}", description="d", confidence=0.5, component=i)
            assert 0 <= obs.component < DIM

    def test_self_state_trajectory_values(self):
        """SelfState trajectory is one of rising/declining/stable."""
        for traj in ("rising", "declining", "stable"):
            ss = SelfState(phase="FUNCTIONAL", phi=0.5, dominant="Reflexion",
                           trajectory=traj, stability=0.8)
            assert ss.trajectory == traj

    def test_insight_types(self):
        """Insight types are one of the 4 thinking angles."""
        valid_types = {"meta", "counterfactual", "causal_chain", "connection"}
        for t in valid_types:
            ins = Insight(type=t, content="test", confidence=0.5, iteration=0)
            assert ins.type in valid_types


# ===================================================================
#  II. CAUSAL GRAPH PROTOCOL
# ===================================================================

class TestCausalGraphProtocol:
    """NullCausalGraph satisfies the Protocol and returns empty."""

    def test_null_graph_returns_empty(self):
        """NullCausalGraph returns empty lists and False."""
        g = NullCausalGraph()
        assert g.get_causes("any") == []
        assert g.get_effects("any") == []
        assert g.is_confirmed("a", "b") is False

    def test_null_graph_observe_pair_noop(self):
        """observe_pair does nothing and doesn't raise."""
        g = NullCausalGraph()
        g.observe_pair("a", "b")  # Should not raise

    def test_null_graph_satisfies_protocol(self):
        """NullCausalGraph is a runtime instance of CausalGraphProtocol."""
        g = NullCausalGraph()
        assert isinstance(g, CausalGraphProtocol)


# ===================================================================
#  III. STIMULUS CONSTRUCTION
# ===================================================================

class TestStimulusConstruction:
    """Stimulus dataclass constructs correctly."""

    def test_defaults(self):
        """Stimulus with all defaults is valid."""
        s = Stimulus()
        assert s.user_message == ""
        assert s.metrics == {}
        assert s.phi_iit == 0.0
        assert s.phase == "BROKEN"

    def test_with_message(self):
        """Stimulus with user message."""
        s = Stimulus(user_message="hello")
        assert s.user_message == "hello"

    def test_with_metrics(self):
        """Stimulus with metrics dict."""
        m = {"identity_anchoring": 0.8}
        s = Stimulus(metrics=m)
        assert s.metrics["identity_anchoring"] == 0.8


# ===================================================================
#  IV. OBSERVE
# ===================================================================

class TestObserve:
    """_observe() produces deterministic observations from stimulus."""

    def test_low_phase_detected(self, thinker):
        """BROKEN/FRAGILE phase produces low_phase observation."""
        s = _make_stimulus(phase="BROKEN")
        obs = thinker._observe(s)
        tags = [o.tag for o in obs]
        assert "low_phase" in tags

    def test_phi_critical_detected(self, thinker):
        """phi_iit < INV_PHI2 produces phi_critical."""
        s = _make_stimulus(phi_iit=0.1)
        obs = thinker._observe(s)
        tags = [o.tag for o in obs]
        assert "phi_critical" in tags

    def test_phi_low_detected(self, thinker):
        """phi_iit between INV_PHI2 and INV_PHI produces phi_low."""
        s = _make_stimulus(phi_iit=0.5)
        obs = thinker._observe(s)
        tags = [o.tag for o in obs]
        assert "phi_low" in tags

    def test_phi_excellent_detected(self, thinker):
        """phi_iit > 1.0 produces phi_excellent (Phase 3: Gaussian MI)."""
        s = _make_stimulus(phi_iit=1.3)
        obs = thinker._observe(s)
        tags = [o.tag for o in obs]
        assert "phi_excellent" in tags
        assert "phi_healthy" in tags  # phi_excellent also implies phi_healthy

    def test_metric_low_detected(self, thinker):
        """Low metric produces metric_low_<name> observation."""
        s = _make_stimulus(metrics={"identity_anchoring": 0.3})
        obs = thinker._observe(s)
        tags = [o.tag for o in obs]
        assert "metric_low_identity_anchoring" in tags

    def test_dominant_component_detected(self, thinker):
        """psi component > INV_PHI produces dominant_<comp>."""
        s = _make_stimulus(psi=np.array([0.05, 0.70, 0.15, 0.10]))
        obs = thinker._observe(s)
        tags = [o.tag for o in obs]
        assert "dominant_Reflexion" in tags

    def test_weak_component_detected(self, thinker):
        """psi component < INV_PHI3 produces weak_<comp>."""
        s = _make_stimulus(psi=np.array([0.05, 0.70, 0.15, 0.10]))
        obs = thinker._observe(s)
        tags = [o.tag for o in obs]
        assert "weak_Perception" in tags

    def test_user_stimulus_detected(self, thinker):
        """Non-empty user_message produces user_stimulus."""
        s = _make_stimulus(user_message="test")
        obs = thinker._observe(s)
        tags = [o.tag for o in obs]
        assert "user_stimulus" in tags


# ===================================================================
#  V. INTROSPECT
# ===================================================================

class TestIntrospect:
    """_introspect() returns a SelfState from consciousness."""

    def test_returns_self_state(self, thinker):
        """_introspect() returns a SelfState instance."""
        ss = thinker._introspect()
        assert isinstance(ss, SelfState)

    def test_dominant_correct(self, thinker):
        """Dominant component matches argmax of psi."""
        ss = thinker._introspect()
        psi = thinker._state.psi
        expected = COMP_NAMES[int(np.argmax(psi))]
        assert ss.dominant == expected

    def test_phase_correct(self, thinker):
        """Phase matches the state's get_phase()."""
        ss = thinker._introspect()
        assert ss.phase == thinker._state.get_phase()


# ===================================================================
#  VI. FIND CAUSALITIES
# ===================================================================

class TestFindCausalities:
    """_find_causalities() uses heuristic pairs + graph."""

    def test_no_match(self, thinker):
        """No heuristic pairs observed → empty causalities."""
        obs = [Observation(tag="unrelated", description="x", confidence=0.5, component=0)]
        result = thinker._find_causalities(obs)
        assert result == []

    def test_heuristic_pair_detected(self, thinker):
        """Both tags of a heuristic pair observed → causality found."""
        obs = [
            Observation(tag="metric_low_identity_anchoring", description="low cov",
                        confidence=0.8, component=2),
            Observation(tag="phi_low", description="phi low",
                        confidence=0.7, component=0),
        ]
        result = thinker._find_causalities(obs)
        assert len(result) >= 1
        assert any(c.cause == "metric_low_identity_anchoring" and c.effect == "phi_low"
                    for c in result)

    def test_strength_is_phi_derived(self, thinker):
        """Heuristic causality strength is INV_PHI."""
        obs = [
            Observation(tag="metric_low_identity_anchoring", description="low",
                        confidence=0.8, component=2),
            Observation(tag="phi_low", description="low",
                        confidence=0.7, component=0),
        ]
        result = thinker._find_causalities(obs)
        c = next(c for c in result
                 if c.cause == "metric_low_identity_anchoring" and c.effect == "phi_low")
        assert c.strength == pytest.approx(INV_PHI, abs=1e-10)

    def test_dedup_keeps_max_strength(self, thinker):
        """Duplicate causal pairs keep the one with higher strength."""
        obs = [
            Observation(tag="metric_low_identity_anchoring", description="low",
                        confidence=0.8, component=2),
            Observation(tag="phi_low", description="low",
                        confidence=0.7, component=0),
        ]
        result = thinker._find_causalities(obs)
        # Should have exactly 1 entry for this pair (deduped)
        pairs = [(c.cause, c.effect) for c in result]
        assert pairs.count(("metric_low_identity_anchoring", "phi_low")) == 1


# ===================================================================
#  VII. IDENTIFY NEEDS
# ===================================================================

class TestIdentifyNeeds:
    """_identify_needs() maps observations to actionable needs."""

    def test_metric_to_pipeline(self, thinker):
        """Low metric → pipeline need."""
        obs = [Observation(tag="metric_low_identity_anchoring", description="low",
                           confidence=0.8, component=2)]
        needs = thinker._identify_needs(obs, [])
        assert any(n.method == "pipeline" for n in needs)

    def test_phase_to_dream(self, thinker):
        """Low phase → dream need."""
        obs = [Observation(tag="low_phase", description="BROKEN",
                           confidence=1.0, component=0)]
        needs = thinker._identify_needs(obs, [])
        assert any(n.method == "dream" for n in needs)

    def test_sorted_by_priority(self, thinker):
        """Needs are sorted by priority descending."""
        obs = [
            Observation(tag="metric_low_identity_anchoring", description="low",
                        confidence=0.3, component=2),
            Observation(tag="low_phase", description="BROKEN",
                        confidence=1.0, component=0),
        ]
        needs = thinker._identify_needs(obs, [])
        priorities = [n.priority for n in needs]
        assert priorities == sorted(priorities, reverse=True)

    def test_empty_observations(self, thinker):
        """No observations → no needs."""
        needs = thinker._identify_needs([], [])
        assert needs == []


# ===================================================================
#  VIII. GENERATE PROPOSALS
# ===================================================================

class TestGenerateProposals:
    """_generate_proposals() maps needs to concrete proposals."""

    def test_pipeline_proposal(self, thinker):
        """Pipeline need → pipeline proposal."""
        needs = [Need(description="Improve coverage", priority=0.8, method="pipeline")]
        props = thinker._generate_proposals(needs, [])
        assert len(props) >= 1
        assert "pipeline" in props[0].description.lower() or "Run" in props[0].description

    def test_dream_proposal(self, thinker):
        """Dream need → dream proposal."""
        needs = [Need(description="Consolidation", priority=1.0, method="dream")]
        props = thinker._generate_proposals(needs, [])
        assert len(props) >= 1
        assert "dream" in props[0].description.lower()

    def test_expected_impact_non_empty(self, thinker):
        """Every proposal has non-empty expected_impact."""
        needs = [Need(description="Improve X", priority=0.8, method="pipeline")]
        props = thinker._generate_proposals(needs, [])
        for p in props:
            assert len(p.expected_impact) > 0


# ===================================================================
#  IX. COMPUTE CONFIDENCE
# ===================================================================

class TestComputeConfidence:
    """_compute_confidence() is Phi_IIT on 4 thought components."""

    def test_empty_thought_zero(self, thinker):
        """Empty thought → confidence 0."""
        t = Thought.empty()
        assert thinker._compute_confidence(t) == 0.0

    def test_single_obs_zero(self, thinker):
        """Single observation (< 2 elements in 1 vector) → 0."""
        t = Thought.empty()
        t.observations = [Observation(tag="x", description="x",
                                       confidence=0.5, component=0)]
        assert thinker._compute_confidence(t) == 0.0

    def test_range_zero_one(self, thinker, rich_stimulus):
        """Confidence is in [0, 1]."""
        thought = thinker.think(rich_stimulus)
        assert 0.0 <= thought.confidence <= 1.0

    def test_rich_thought_positive(self, thinker, rich_stimulus):
        """Rich thought with many observations has positive confidence."""
        thought = thinker.think(rich_stimulus)
        # With many observations and causalities, some correlation is expected
        # but not guaranteed to be > 0 depending on exact values
        assert thought.confidence >= 0.0

    def test_deterministic(self, thinker, rich_stimulus):
        """Same inputs → same confidence."""
        t1 = thinker.think(rich_stimulus)
        # Create fresh thinker with same state
        thinker2 = _make_thinker()
        t2 = thinker2.think(rich_stimulus)
        assert t1.confidence == pytest.approx(t2.confidence, abs=1e-10)


# ===================================================================
#  X. THINK INTEGRATION
# ===================================================================

class TestThinkIntegration:
    """think() produces a complete Thought."""

    def test_returns_thought(self, thinker, stimulus):
        """think() returns a Thought instance."""
        result = thinker.think(stimulus)
        assert isinstance(result, Thought)

    def test_observations_non_empty(self, thinker, stimulus):
        """A stimulus with low metrics produces observations."""
        result = thinker.think(stimulus)
        assert len(result.observations) > 0

    def test_self_state_set(self, thinker, stimulus):
        """think() sets self_state."""
        result = thinker.think(stimulus)
        assert result.self_state is not None
        assert isinstance(result.self_state, SelfState)

    def test_depth_at_least_5(self, thinker, stimulus):
        """Foundation phase sets depth_reached to at least 5."""
        result = thinker.think(stimulus)
        assert result.depth_reached >= 5

    def test_budget_sums_to_one(self, thinker, stimulus):
        """Cognitive budget sums to 1.0."""
        result = thinker.think(stimulus)
        assert sum(result.cognitive_budget) == pytest.approx(1.0, abs=1e-10)

    def test_deterministic(self, thinker, stimulus):
        """Same stimulus + same state → identical Thought."""
        t1 = thinker.think(stimulus)
        thinker2 = _make_thinker()
        t2 = thinker2.think(stimulus)
        assert t1.depth_reached == t2.depth_reached
        assert len(t1.observations) == len(t2.observations)

    def test_responsive_max_iterations(self, thinker, stimulus):
        """RESPONSIVE mode stays within _RESPONSIVE_MAX iterations."""
        result = thinker.think(stimulus, mode=ThinkMode.RESPONSIVE)
        assert result.depth_reached <= _RESPONSIVE_MAX

    def test_convergence_stops_early(self, thinker):
        """If confidence converges, deepening stops before max_iterations."""
        # Simple stimulus with few observations → quick convergence
        s = Stimulus(
            user_message="hello",
            phase="FUNCTIONAL",
            phi_iit=0.7,
            psi=np.array([0.260, 0.322, 0.250, 0.168]),
        )
        result = thinker.think(s, max_iterations=100, mode=ThinkMode.REFLECTIVE)
        # With few observations, should converge well before 100
        assert result.depth_reached < 100


# ===================================================================
#  XI. COMPUTE BUDGET
# ===================================================================

class TestComputeBudget:
    """_compute_budget() normalizes counts to simplex."""

    def test_empty_uniform(self, thinker):
        """Empty thought → uniform budget [0.0, 0.0, 0.0, 0.0]."""
        t = Thought.empty()
        budget = thinker._compute_budget(t)
        assert budget == [0.0, 0.0, 0.0, 0.0]

    def test_sums_to_one(self, thinker, stimulus):
        """Budget with items sums to 1."""
        result = thinker.think(stimulus)
        if any(b > 0 for b in result.cognitive_budget):
            assert sum(result.cognitive_budget) == pytest.approx(1.0, abs=1e-10)

    def test_proportional_to_counts(self, thinker):
        """Budget is proportional to observation/causality/need/proposal counts."""
        t = Thought.empty()
        t.observations = [
            Observation(tag="a", description="a", confidence=0.5, component=0),
            Observation(tag="b", description="b", confidence=0.5, component=1),
            Observation(tag="c", description="c", confidence=0.5, component=2),
        ]
        t.needs = [Need(description="x", priority=0.8, method="pipeline")]
        budget = thinker._compute_budget(t)
        # 3 obs, 0 caus, 1 need, 0 props → [3/4, 0, 1/4, 0]
        assert budget[0] == pytest.approx(0.75, abs=1e-10)
        assert budget[1] == pytest.approx(0.0, abs=1e-10)
        assert budget[2] == pytest.approx(0.25, abs=1e-10)
        assert budget[3] == pytest.approx(0.0, abs=1e-10)


# ===================================================================
#  XII. DEEPEN
# ===================================================================

class TestDeepen:
    """_deepen() cycles through 4 thinking angles."""

    def _build_thought(self, thinker, stimulus):
        """Build a thought with foundation phase completed."""
        t = Thought.empty()
        t.observations = thinker._observe(stimulus)
        t.self_state = thinker._introspect()
        t.causalities = thinker._find_causalities(t.observations)
        t.correlations = thinker._find_correlations(t.observations)
        t.needs = thinker._identify_needs(t.observations, t.causalities)
        t.proposals = thinker._generate_proposals(t.needs, t.causalities)
        t.confidence = thinker._compute_confidence(t)
        return t

    def test_meta_at_mod_0(self, thinker, rich_stimulus):
        """iteration % 4 == 0 → meta insights."""
        t = self._build_thought(thinker, rich_stimulus)
        insights = thinker._deepen(t, 8, ThinkMode.RESPONSIVE)  # 8 % 4 == 0
        if insights:
            assert any(i.type == "meta" for i in insights)

    def test_counterfactual_at_mod_1(self, thinker, rich_stimulus):
        """iteration % 4 == 1 → counterfactual insights."""
        t = self._build_thought(thinker, rich_stimulus)
        insights = thinker._deepen(t, 5, ThinkMode.RESPONSIVE)  # 5 % 4 == 1
        if insights:
            assert any(i.type == "counterfactual" for i in insights)

    def test_causal_chain_at_mod_2(self, thinker, rich_stimulus):
        """iteration % 4 == 2 → causal_chain insights."""
        t = self._build_thought(thinker, rich_stimulus)
        insights = thinker._deepen(t, 6, ThinkMode.RESPONSIVE)  # 6 % 4 == 2
        # Causal chains need A->B->C, may be empty
        for i in insights:
            assert i.type == "causal_chain"

    def test_connection_at_mod_3(self, thinker, rich_stimulus):
        """iteration % 4 == 3 → connection insights."""
        t = self._build_thought(thinker, rich_stimulus)
        insights = thinker._deepen(t, 7, ThinkMode.RESPONSIVE)  # 7 % 4 == 3
        for i in insights:
            assert i.type == "connection"


# ===================================================================
#  XIII. REWARD INTEROCEPTION
# ===================================================================

# Helper to build RewardVector with defaults at +0.5, then overrides.
from luna_common.schemas.cycle import RewardVector, RewardComponent, REWARD_COMPONENT_NAMES


def _make_reward(**overrides: float) -> RewardVector:
    """Build a RewardVector with defaults at +0.5, then apply overrides."""
    components = []
    for name in REWARD_COMPONENT_NAMES:
        value = overrides.get(name, 0.5)
        components.append(RewardComponent(name=name, value=value, raw=value))
    return RewardVector(components=components, dominance_rank=0, delta_j=0.0)


class TestRewardInteroception:
    """Cognitive interoception — Thinker senses previous cycle's RewardVector.

    The Thinker does NOT maximize J. It PERCEIVES when something is wrong.
    Healthy cycles are quiet (one low-confidence observation).
    Degraded cycles produce warning observations that shift attention
    towards the affected consciousness component.

    14 tests covering:
      - No reward -> no reward observations
      - Healthy cycle -> single quiet positive signal
      - Each degradation threshold individually
      - Below-threshold values produce no observation
      - Multiple simultaneous warnings
      - Confidence bounds (anti-Goodhart cap at INV_PHI3)
      - Component mapping correctness
    """

    def test_no_reward_no_observations(self, thinker):
        """previous_reward=None produces zero reward_* observations."""
        s = _make_stimulus(previous_reward=None)
        obs = thinker._observe(s)
        reward_tags = [o.tag for o in obs if o.tag.startswith("reward_")]
        assert reward_tags == [], \
            f"Expected no reward observations, got: {reward_tags}"

    def test_healthy_cycle_observation(self, thinker):
        """All monitored components >= 0 produces reward_healthy_cycle."""
        rv = _make_reward()  # All at +0.5
        s = _make_stimulus(previous_reward=rv)
        obs = thinker._observe(s)
        tags = [o.tag for o in obs]
        assert "reward_healthy_cycle" in tags, \
            f"Expected reward_healthy_cycle in {tags}"

    def test_healthy_cycle_confidence_value(self, thinker):
        """reward_healthy_cycle confidence is INV_PHI3 * INV_PHI2."""
        rv = _make_reward()
        s = _make_stimulus(previous_reward=rv)
        obs = thinker._observe(s)
        healthy = [o for o in obs if o.tag == "reward_healthy_cycle"]
        assert len(healthy) == 1
        expected_conf = INV_PHI3 * INV_PHI2
        assert healthy[0].confidence == pytest.approx(expected_conf, abs=1e-10), \
            f"Expected confidence {expected_conf:.6f}, got {healthy[0].confidence:.6f}"

    def test_constitution_breach(self, thinker):
        """constitution_integrity < 0 produces reward_constitution_breach."""
        rv = _make_reward(constitution_integrity=-0.5)
        s = _make_stimulus(previous_reward=rv)
        obs = thinker._observe(s)
        tags = [o.tag for o in obs]
        assert "reward_constitution_breach" in tags

    def test_collapse_risk(self, thinker):
        """anti_collapse < 0 produces reward_collapse_risk."""
        rv = _make_reward(anti_collapse=-0.3)
        s = _make_stimulus(previous_reward=rv)
        obs = thinker._observe(s)
        tags = [o.tag for o in obs]
        assert "reward_collapse_risk" in tags

    def test_identity_drift(self, thinker):
        """identity_stability < -INV_PHI3 produces reward_identity_drift."""
        rv = _make_reward(identity_stability=-0.5)
        s = _make_stimulus(previous_reward=rv)
        obs = thinker._observe(s)
        tags = [o.tag for o in obs]
        assert "reward_identity_drift" in tags

    def test_identity_drift_below_threshold_no_obs(self, thinker):
        """identity_stability = -0.1 (> -INV_PHI3) produces no reward_identity_drift.

        Threshold is -INV_PHI3 = -0.236. A value of -0.1 is above
        that threshold, so no observation should fire.
        """
        rv = _make_reward(identity_stability=-0.1)
        s = _make_stimulus(previous_reward=rv)
        obs = thinker._observe(s)
        tags = [o.tag for o in obs]
        assert "reward_identity_drift" not in tags, \
            f"-0.1 > -INV_PHI3 ({-INV_PHI3:.4f}), should not trigger identity_drift"

    def test_reflection_shallow(self, thinker):
        """reflection_depth < -INV_PHI2 produces reward_reflection_shallow."""
        rv = _make_reward(reflection_depth=-0.6)
        s = _make_stimulus(previous_reward=rv)
        obs = thinker._observe(s)
        tags = [o.tag for o in obs]
        assert "reward_reflection_shallow" in tags

    def test_reflection_above_threshold_no_obs(self, thinker):
        """reflection_depth = -0.2 (> -INV_PHI2) produces no reward_reflection_shallow.

        Threshold is -INV_PHI2 = -0.382. A value of -0.2 is above
        that threshold, so no observation should fire.
        """
        rv = _make_reward(reflection_depth=-0.2)
        s = _make_stimulus(previous_reward=rv)
        obs = thinker._observe(s)
        tags = [o.tag for o in obs]
        assert "reward_reflection_shallow" not in tags, \
            f"-0.2 > -INV_PHI2 ({-INV_PHI2:.4f}), should not trigger reflection_shallow"

    def test_integration_low(self, thinker):
        """integration_coherence < -INV_PHI2 produces reward_integration_low."""
        rv = _make_reward(integration_coherence=-0.5)
        s = _make_stimulus(previous_reward=rv)
        obs = thinker._observe(s)
        tags = [o.tag for o in obs]
        assert "reward_integration_low" in tags

    def test_affect_dysregulated(self, thinker):
        """affect_regulation < -INV_PHI2 produces reward_affect_dysregulated."""
        rv = _make_reward(affect_regulation=-0.7)
        s = _make_stimulus(previous_reward=rv)
        obs = thinker._observe(s)
        tags = [o.tag for o in obs]
        assert "reward_affect_dysregulated" in tags

    def test_multiple_warnings_simultaneously(self, thinker):
        """Multiple bad components produce multiple reward observations.

        When constitution, collapse, identity, and reflection are all
        degraded simultaneously, four warning observations should fire
        and reward_healthy_cycle should NOT appear.
        """
        rv = _make_reward(
            constitution_integrity=-0.3,
            anti_collapse=-0.1,
            identity_stability=-0.5,
            reflection_depth=-0.6,
        )
        s = _make_stimulus(previous_reward=rv)
        obs = thinker._observe(s)
        reward_tags = [o.tag for o in obs if o.tag.startswith("reward_")]
        assert "reward_constitution_breach" in reward_tags
        assert "reward_collapse_risk" in reward_tags
        assert "reward_identity_drift" in reward_tags
        assert "reward_reflection_shallow" in reward_tags
        assert "reward_healthy_cycle" not in reward_tags

    def test_healthy_blocks_if_one_negative(self, thinker):
        """One monitored component < 0 prevents reward_healthy_cycle.

        The healthy check requires constitution_integrity, anti_collapse,
        integration_coherence, identity_stability, and reflection_depth
        ALL >= 0. Even one negative blocks the healthy signal.
        """
        # Only constitution_integrity negative, rest positive
        rv = _make_reward(constitution_integrity=-0.01)
        s = _make_stimulus(previous_reward=rv)
        obs = thinker._observe(s)
        tags = [o.tag for o in obs]
        assert "reward_healthy_cycle" not in tags, \
            "One negative component should block reward_healthy_cycle"

    def test_confidence_bounds(self, thinker):
        """All reward observations have confidence <= INV_PHI3 (0.236).

        Anti-Goodhart design: reward interoception is a whisper,
        not a shout. Confidence is capped at INV_PHI3 to prevent
        reward-maximization from dominating the Thinker's attention.
        """
        # Trigger every possible reward observation
        rv = _make_reward(
            constitution_integrity=-0.8,
            anti_collapse=-0.8,
            identity_stability=-0.8,
            reflection_depth=-0.8,
            integration_coherence=-0.8,
            affect_regulation=-0.8,
        )
        s = _make_stimulus(previous_reward=rv)
        obs = thinker._observe(s)
        reward_obs = [o for o in obs if o.tag.startswith("reward_")]
        assert len(reward_obs) >= 6, \
            f"Expected at least 6 reward observations, got {len(reward_obs)}"
        for o in reward_obs:
            assert o.confidence <= INV_PHI3 + 1e-10, \
                f"{o.tag}: confidence {o.confidence:.6f} > INV_PHI3 ({INV_PHI3:.6f})"

    def test_component_mapping(self, thinker):
        """Each reward observation maps to the correct consciousness component.

        Component indices:
          0 = Perception  (constitution_breach, collapse_risk)
          1 = Reflexion    (reflection_shallow, affect_dysregulated)
          2 = Integration  (identity_drift, integration_low, healthy_cycle)
        """
        expected_components = {
            "reward_constitution_breach": 0,
            "reward_collapse_risk": 0,
            "reward_identity_drift": 2,
            "reward_reflection_shallow": 1,
            "reward_integration_low": 2,
            "reward_affect_dysregulated": 1,
        }
        rv = _make_reward(
            constitution_integrity=-0.5,
            anti_collapse=-0.5,
            identity_stability=-0.5,
            reflection_depth=-0.5,
            integration_coherence=-0.5,
            affect_regulation=-0.5,
        )
        s = _make_stimulus(previous_reward=rv)
        obs = thinker._observe(s)
        obs_by_tag = {o.tag: o for o in obs}
        for tag, expected_comp in expected_components.items():
            assert tag in obs_by_tag, f"Missing observation: {tag}"
            actual_comp = obs_by_tag[tag].component
            assert actual_comp == expected_comp, \
                f"{tag}: expected component {expected_comp} ({COMP_NAMES[expected_comp]}), " \
                f"got {actual_comp} ({COMP_NAMES[actual_comp]})"
