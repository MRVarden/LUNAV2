"""Thinker — structured reasoning without LLM (Luna v3.5).

The Thinker applies Luna's state equation RECURSIVELY to thought itself:
  MACRO: Psi evolves between messages (dt = INV_PHI = 0.618)
  MICRO: Thought evolves within the Thinker (same dt, convergence < INV_PHI2 = 0.382)

This is phi = 1 + 1/phi — self-referent. The system contains its own model.

The 4 thinking modes ARE the 4 cognitive faculties:
  _observe()            -> Perception  (psi_1)
  _find_causalities()   -> Reflexion   (psi_2)
  _identify_needs()     -> Integration (psi_3)
  _generate_proposals() -> Expression  (psi_4)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable

import numpy as np

from luna.consciousness.learnable_params import LearnableParams
from luna.consciousness.state import ConsciousnessState
from luna_common.constants import (
    COMP_NAMES,
    DIM,
    INV_PHI,
    INV_PHI2,
    INV_PHI3,
    METRIC_NAMES,
    PHI,
)

# ═══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS — all phi-derived
# ═══════════════════════════════════════════════════════════════════════════════

CONVERGENCE_THRESHOLD: float = INV_PHI2   # 0.382 — stop deepening
THINK_DT: float = INV_PHI                 # 0.618 — thought time step
INSIGHT_WEIGHT: float = INV_PHI2           # 0.382 — weight of new insight
_RESPONSIVE_MAX: int = 10
_REFLECTIVE_MAX: int = 100

# Component index → need weight param name.
_COMP_NEED_WEIGHT: dict[int, str] = {
    0: "need_weight_stability",      # Perception
    1: "need_weight_coherence",      # Reflexion
    2: "need_weight_integration",    # Integration
    3: "need_weight_expression",     # Expression
}


# ═══════════════════════════════════════════════════════════════════════════════
#  CAUSAL GRAPH PROTOCOL (Phase G stub)
# ═══════════════════════════════════════════════════════════════════════════════

@runtime_checkable
class CausalGraphProtocol(Protocol):
    """Interface for the causal graph (Phase G)."""

    def get_causes(self, tag: str) -> list[str]: ...

    def get_effects(self, tag: str) -> list[str]: ...

    def is_confirmed(self, cause: str, effect: str) -> bool: ...

    def observe_pair(self, cause: str, effect: str) -> None: ...


class NullCausalGraph:
    """Phase F stub — returns empty results for all queries."""

    def get_causes(self, tag: str) -> list[str]:
        return []

    def get_effects(self, tag: str) -> list[str]:
        return []

    def is_confirmed(self, cause: str, effect: str) -> bool:
        return False

    def observe_pair(self, cause: str, effect: str) -> None:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
#  DATA MODEL
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(slots=True)
class Stimulus:
    """Input to the Thinker — what happened."""

    user_message: str = ""
    metrics: dict[str, float] = field(default_factory=dict)
    phi_iit: float = 0.0
    phase: str = "BROKEN"
    psi: np.ndarray = field(default_factory=lambda: np.array([0.25] * DIM))
    psi_trajectory: list[np.ndarray] = field(default_factory=list)
    affect_state: tuple[float, float, float] | None = None  # PAD (valence, arousal, dominance)
    recalled_episodes: list = field(default_factory=list)  # EpisodicRecall objects
    # Self-knowledge: factual subsystem status (no descriptions, only measures)
    self_knowledge: dict[str, object] = field(default_factory=dict)
    # Dream priors — weak signals from nocturnal consolidation.
    dream_skill_priors: list = field(default_factory=list)       # SkillPrior objects
    dream_simulation_priors: list = field(default_factory=list)  # SimulationPrior objects
    dream_reflection_prior: object | None = None                 # ReflectionPrior or None
    # Dream journal — cumulative insights from previous dream cycles.
    # Injected by DreamReflection/DreamSimulation when journal context exists.
    dream_journal_context: str = ""
    # Cognitive interoception — previous cycle's RewardVector (9 components).
    previous_reward: object | None = None                        # RewardVector or None


@dataclass(slots=True)
class Observation:
    """A perceptual observation (psi_1)."""

    tag: str
    description: str
    confidence: float
    component: int  # 0=Perception, 1=Reflexion, 2=Integration, 3=Expression


@dataclass(slots=True)
class Causality:
    """A causal link between observations (psi_2)."""

    cause: str
    effect: str
    strength: float
    evidence_count: int


@dataclass(slots=True)
class Correlation:
    """A statistical correlation between observation tags (psi_2)."""

    tag_a: str
    tag_b: str
    frequency: float


@dataclass(slots=True)
class Need:
    """An identified need (psi_3)."""

    description: str
    priority: float
    method: str  # "pipeline", "dream", "introspect"
    source_tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Proposal:
    """A proposed action (psi_4)."""

    description: str
    rationale: str
    expected_impact: dict[str, float]
    source_needs: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Insight:
    """A deeper insight from the deepen phase."""

    type: str  # "meta", "counterfactual", "causal_chain", "connection"
    content: str
    confidence: float
    iteration: int


@dataclass(slots=True)
class SelfState:
    """Thinker's introspective view of its own state."""

    phase: str
    phi: float
    dominant: str
    trajectory: str  # "rising", "declining", "stable"
    stability: float


@dataclass
class Thought:
    """The complete output of a think() cycle. Mutable for accumulation."""

    observations: list[Observation] = field(default_factory=list)
    causalities: list[Causality] = field(default_factory=list)
    correlations: list[Correlation] = field(default_factory=list)
    needs: list[Need] = field(default_factory=list)
    proposals: list[Proposal] = field(default_factory=list)
    insights: list[Insight] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    self_state: SelfState | None = None
    depth_reached: int = 0
    confidence: float = 0.0
    cognitive_budget: list[float] = field(default_factory=lambda: [0.25] * DIM)
    synthesis: str = ""

    @property
    def causal_density(self) -> float:
        """Ratio of causally-linked observations to total observations.

        Measures real integration: how many observations have causal
        explanation vs raw perceptual noise.
        """
        if not self.observations:
            return 0.0
        cause_tags = {c.cause for c in self.causalities}
        effect_tags = {c.effect for c in self.causalities}
        causal_tags = cause_tags | effect_tags
        linked = sum(1 for o in self.observations if o.tag in causal_tags)
        return linked / len(self.observations)

    @classmethod
    def empty(cls) -> Thought:
        """Create an empty Thought with default values."""
        return cls()


# ═══════════════════════════════════════════════════════════════════════════════
#  THINK MODE
# ═══════════════════════════════════════════════════════════════════════════════

class ThinkMode(str, Enum):
    """How deeply the Thinker should reflect."""

    RESPONSIVE = "responsive"   # 5-10 iterations
    REFLECTIVE = "reflective"   # 30-100 iterations
    CREATIVE = "creative"       # free exploration


# ═══════════════════════════════════════════════════════════════════════════════
#  METRIC -> COMPONENT MAPPING
# ═══════════════════════════════════════════════════════════════════════════════

# Which cognitive component each metric belongs to.
_METRIC_COMPONENT: dict[str, int] = {
    "integration_coherence": 2,   # Integration (psi3)
    "identity_anchoring": 2,      # Integration (transversal)
    "reflection_depth": 1,        # Reflexion (psi2)
    "perception_acuity": 0,       # Perception (psi1)
    "expression_fidelity": 3,     # Expression (psi4)
    "affect_regulation": 1,       # Reflexion (transversal)
    "memory_vitality": 2,         # Integration (transversal)
}

# ═══════════════════════════════════════════════════════════════════════════════
#  HEURISTIC CAUSAL PAIRS
# ═══════════════════════════════════════════════════════════════════════════════

_HEURISTIC_PAIRS: list[tuple[str, str]] = [
    ("metric_low_identity_anchoring", "phi_low"),
    ("metric_low_integration_coherence", "phi_critical"),
    ("metric_low_reflection_depth", "weak_Reflexion"),
    ("metric_low_perception_acuity", "phi_low"),
    ("weak_Perception", "low_phase"),
    ("metric_low_memory_vitality", "weak_Expression"),
    ("trajectory_declining", "phi_low"),
]


# ═══════════════════════════════════════════════════════════════════════════════
#  THINKER
# ═══════════════════════════════════════════════════════════════════════════════

class Thinker:
    """Structured reasoning engine — thinks WITHOUT an LLM.

    Applies Luna's state equation recursively to thought itself.
    Each think() cycle produces a Thought containing observations,
    causalities, needs, proposals, and insights.
    """

    def __init__(
        self,
        state: ConsciousnessState,
        metrics: dict[str, float] | None = None,
        causal_graph: CausalGraphProtocol | None = None,
        lexicon: object | None = None,
        params: LearnableParams | None = None,
        observation_factory: object | None = None,
        identity_context: object | None = None,
    ) -> None:
        self._state = state
        self._metrics = metrics or {}
        self._causal_graph: CausalGraphProtocol = causal_graph or NullCausalGraph()
        self._lexicon = lexicon
        self._params = params or LearnableParams()
        self._observation_factory = observation_factory
        self._identity_context = identity_context

    # ------------------------------------------------------------------
    #  MAIN LOOP
    # ------------------------------------------------------------------

    def think(
        self,
        stimulus: Stimulus,
        max_iterations: int | None = None,
        mode: ThinkMode = ThinkMode.RESPONSIVE,
    ) -> Thought:
        """Run a full thinking cycle.

        Phase 1 (iterations 1-5): foundation — observe, introspect,
        find causalities/correlations, identify needs, generate proposals.

        Phase 2 (iterations 6+): deepening — cycle through meta-cognition,
        counterfactual, causal chain, and connection insights until
        convergence (delta confidence < INV_PHI2).

        Args:
            stimulus: What happened (user message, metrics, etc.).
            max_iterations: Override max iterations (default from mode).
            mode: How deeply to reflect.

        Returns:
            A complete Thought structure.
        """
        if max_iterations is None:
            if mode == ThinkMode.RESPONSIVE:
                max_iterations = _RESPONSIVE_MAX
            elif mode == ThinkMode.REFLECTIVE:
                max_iterations = _REFLECTIVE_MAX
            else:  # CREATIVE
                max_iterations = _REFLECTIVE_MAX

        thought = Thought.empty()

        # Phase 1: foundation (iterations 1-5)
        thought.observations = self._observe(stimulus)
        thought.self_state = self._introspect()
        thought.causalities = self._find_causalities(thought.observations)
        thought.correlations = self._find_correlations(thought.observations)
        thought.needs = self._identify_needs(
            thought.observations, thought.causalities,
        )
        thought.proposals = self._generate_proposals(
            thought.needs, thought.causalities,
        )
        thought.depth_reached = 5
        thought.confidence = self._compute_confidence(thought)

        # Phase 2: deepening (iterations 6+)
        prev_conf = 0.0
        for i in range(5, max_iterations):
            insights = self._deepen(thought, i, mode)
            if not insights:
                break
            thought = self._integrate_insights(thought, insights)
            thought.depth_reached = i + 1
            thought.confidence = self._compute_confidence(thought)
            if abs(thought.confidence - prev_conf) < CONVERGENCE_THRESHOLD:
                break
            prev_conf = thought.confidence

        # Finalization
        thought.uncertainties = self._identify_uncertainties(thought)
        thought.cognitive_budget = self._compute_budget(thought)

        # Phase 3: synthesis — integrated reasoning for Expression (psi_4).
        thought.synthesis = self._synthesize(thought)

        return thought

    # ------------------------------------------------------------------
    #  PHASE 1 — Foundation
    # ------------------------------------------------------------------

    def _observe(self, stimulus: Stimulus) -> list[Observation]:
        """Perception (psi_1) — deterministic observation rules.

        Scans the stimulus for conditions and produces tagged observations.
        Each observation has a confidence, description, and component mapping.
        """
        observations: list[Observation] = []

        # Phase-based observations
        if stimulus.phase in ("BROKEN", "FRAGILE"):
            observations.append(Observation(
                tag="low_phase",
                description=f"System phase is {stimulus.phase}",
                confidence=1.0,
                component=0,
            ))

        # Phi_IIT observations
        if stimulus.phi_iit < INV_PHI2:
            observations.append(Observation(
                tag="phi_critical",
                description=f"Phi_IIT critically low: {stimulus.phi_iit:.3f} < {INV_PHI2:.3f}",
                confidence=1.0,
                component=0,
            ))
        elif stimulus.phi_iit < INV_PHI:
            observations.append(Observation(
                tag="phi_low",
                description=f"Phi_IIT low: {stimulus.phi_iit:.3f} < {INV_PHI:.3f}",
                confidence=0.8,
                component=0,
            ))

        # Psi component observations
        psi = stimulus.psi
        if isinstance(psi, np.ndarray) and psi.shape == (DIM,):
            for i in range(DIM):
                comp_name = COMP_NAMES[i]
                if psi[i] > INV_PHI:
                    observations.append(Observation(
                        tag=f"dominant_{comp_name}",
                        description=f"{comp_name} dominant: {psi[i]:.3f} > {INV_PHI:.3f}",
                        confidence=psi[i],
                        component=i,
                    ))
                # Identity-relative: weak = inhibited below identity (ratio < 1.0)
                psi0_i = float(self._state.psi0[i])
                if psi0_i > 1e-10:
                    ratio = psi[i] / psi0_i
                    if ratio < 1.0:
                        observations.append(Observation(
                            tag=f"weak_{comp_name}",
                            description=f"{comp_name} inhibited: {ratio:.3f} < 1.0",
                            confidence=1.0 - ratio,
                            component=i,
                        ))
                    elif ratio >= PHI:
                        observations.append(Observation(
                            tag=f"emergent_{comp_name}",
                            description=f"{comp_name} emergent: {ratio:.3f} >= {PHI:.3f}",
                            confidence=min(1.0, ratio / PHI),
                            component=i,
                        ))
                    elif ratio >= 1.0 + INV_PHI3:
                        observations.append(Observation(
                            tag=f"active_{comp_name}",
                            description=f"{comp_name} active: {ratio:.3f} >= {1 + INV_PHI3:.3f}",
                            confidence=ratio - 1.0,
                            component=i,
                        ))

        # Metric observations
        for name in METRIC_NAMES:
            value = stimulus.metrics.get(name)
            if value is not None and value < INV_PHI:
                comp = _METRIC_COMPONENT.get(name, 0)
                observations.append(Observation(
                    tag=f"metric_low_{name}",
                    description=f"Metric {name} low: {value:.3f} < {INV_PHI:.3f}",
                    confidence=1.0 - value,
                    component=comp,
                ))

        # Trajectory observations
        if len(stimulus.psi_trajectory) >= 2:
            recent = stimulus.psi_trajectory[-1]
            previous = stimulus.psi_trajectory[-2]
            if isinstance(recent, np.ndarray) and isinstance(previous, np.ndarray):
                delta = float(np.mean(recent - previous))
                if delta < -INV_PHI3:
                    observations.append(Observation(
                        tag="trajectory_declining",
                        description=f"Consciousness trajectory declining: delta={delta:.3f}",
                        confidence=min(1.0, abs(delta)),
                        component=1,
                    ))
                elif delta > INV_PHI3:
                    observations.append(Observation(
                        tag="trajectory_rising",
                        description=f"Consciousness trajectory rising: delta={delta:.3f}",
                        confidence=min(1.0, abs(delta)),
                        component=1,
                    ))

        # Positive observations — healthy state awareness.
        # Without these, the Thinker is blind in SOLID/EXCELLENT phase,
        # producing near-zero confidence and degenerate focus.
        if stimulus.phase in ("SOLID", "EXCELLENT"):
            observations.append(Observation(
                tag="high_phase",
                description=f"System phase is {stimulus.phase} — stable integration",
                confidence=0.8,
                component=2,  # Integration — stability IS integration
            ))
        if stimulus.phi_iit >= INV_PHI:
            observations.append(Observation(
                tag="phi_healthy",
                description=f"Phi_IIT healthy: {stimulus.phi_iit:.3f} >= {INV_PHI:.3f}",
                confidence=min(1.0, stimulus.phi_iit),
                component=2,  # Integration — coherence measure
            ))
        if stimulus.phi_iit > 1.0:
            observations.append(Observation(
                tag="phi_excellent",
                description=f"Phi_IIT excellent: {stimulus.phi_iit:.3f} > 1.0 — deep integration",
                confidence=min(1.0, stimulus.phi_iit / PHI),
                component=2,  # Integration — strong coherence
            ))
        # Balanced Psi — all components in healthy range.
        if isinstance(psi, np.ndarray) and psi.shape == (DIM,):
            psi_std = float(np.std(psi))
            if psi_std < INV_PHI3:  # balanced = low variance
                observations.append(Observation(
                    tag="psi_balanced",
                    description=f"Psi well-balanced (std={psi_std:.3f})",
                    confidence=1.0 - psi_std / INV_PHI3,
                    component=1,  # Reflexion — self-awareness of balance
                ))

        # User stimulus — receiving a message is a perceptual event.
        if stimulus.user_message:
            observations.append(Observation(
                tag="user_stimulus",
                description=f"User message received ({len(stimulus.user_message)} chars)",
                confidence=1.0,
                component=0,
            ))

        # Affect interoception — sensing own emotional state (Damasio markers).
        #
        # ANTI-LOOP DESIGN (3 dampeners):
        #   1. Confidence scaled by INV_PHI2 (0.382) — modulatory, not dominant.
        #      Max affect delta per cycle: 0.382 × OBS_WEIGHT(0.382) = 0.146
        #      vs. user_stimulus: 1.0 × 0.382 = 0.382. Affect ≈ 38% of primary.
        #   2. AffectEngine uses hysteresis (AFFECT_ALPHA=0.382) — PAD changes
        #      slowly. No single observation can spike the affect state.
        #   3. Kappa restoring force (2.618) pulls psi back to identity each
        #      step, preventing affect-driven psi drift from accumulating.
        # Traceability: tags (affect_*) flow into CycleRecord.observations,
        # CausalGraph edges, and Thought.synthesis. Sanitized before LLM.
        if stimulus.affect_state is not None:
            valence, arousal, dominance = stimulus.affect_state
            if abs(valence) >= INV_PHI2:  # |v| >= 0.382 — directional
                polarity = "positive" if valence > 0 else "negative"
                observations.append(Observation(
                    tag=f"affect_{polarity}",
                    description=f"Affect {polarity}: {abs(valence):.3f} >= {INV_PHI2:.3f}",
                    confidence=INV_PHI2 * abs(valence),
                    component=1,  # Reflexion — interoception is self-awareness
                ))
            if arousal >= INV_PHI:  # >= 0.618 — heightened
                observations.append(Observation(
                    tag="affect_aroused",
                    description=f"High arousal: {arousal:.3f} >= {INV_PHI:.3f}",
                    confidence=INV_PHI2 * arousal,
                    component=0,  # Perception — arousal sharpens attention
                ))
            if dominance < INV_PHI3:  # < 0.236 — vulnerable
                observations.append(Observation(
                    tag="affect_vulnerable",
                    description=f"Low dominance: {dominance:.3f} < {INV_PHI3:.3f}",
                    confidence=INV_PHI2 * (1.0 - dominance),
                    component=2,  # Integration — needs anchoring
                ))

        # Episodic recall — what happened in similar states before.
        #
        # ANTI-HALLUCINATION DESIGN:
        #   Episodes are REAL recorded experiences (context→action→result→Δψ).
        #   The Thinker observes their outcomes as facts, not narratives.
        #   Confidence scaled by similarity × INV_PHI2 (same dampening as affect).
        #   Max 3 episodes recalled (phi-weighted similarity, threshold INV_PHI3).
        for ep_recall in stimulus.recalled_episodes:
            ep = ep_recall.episode
            sim = ep_recall.similarity
            # Outcome direction: did phi improve or decline?
            if ep.delta_phi > INV_PHI3:
                observations.append(Observation(
                    tag="episodic_positive",
                    description=(
                        f"Similar state ({sim:.0%}): {ep.action_type}"
                        f" → phi +{ep.delta_phi:.3f}, phase {ep.phase_after}"
                    ),
                    confidence=sim * INV_PHI2,
                    component=2,  # Integration — past success informs coherence
                ))
            elif ep.delta_phi < -INV_PHI3:
                observations.append(Observation(
                    tag="episodic_negative",
                    description=(
                        f"Similar state ({sim:.0%}): {ep.action_type}"
                        f" → phi {ep.delta_phi:.3f}, phase {ep.phase_after}"
                    ),
                    confidence=sim * INV_PHI2,
                    component=0,  # Perception — past failure raises vigilance
                ))
            else:
                observations.append(Observation(
                    tag="episodic_neutral",
                    description=(
                        f"Similar state ({sim:.0%}): {ep.action_type}"
                        f" → phi stable ({ep.delta_phi:+.3f})"
                    ),
                    confidence=sim * INV_PHI3,  # Lower confidence for neutral
                    component=1,  # Reflexion — neutral experience feeds introspection
                ))
            # Pinned episodes (founding) get extra weight on Reflexion.
            if ep.pinned:
                observations.append(Observation(
                    tag="episodic_founding",
                    description=f"Founding episode: {ep.action_detail[:80]}",
                    confidence=sim * INV_PHI,  # Higher: identity-relevant
                    component=1,  # Reflexion — identity self-awareness
                ))

        # Self-knowledge — factual awareness of own subsystems.
        #
        # NOT architecture descriptions. MEASURED FACTS about what
        # Luna's systems actually did. The Thinker observes its own
        # machinery the same way it observes psi or affect — as data.
        sk = stimulus.self_knowledge
        if sk:
            # Episodic memory size — Luna knows how much she remembers.
            ep_count = sk.get("episodic_count", 0)
            ep_pinned = sk.get("episodic_pinned", 0)
            if ep_count > 0:
                observations.append(Observation(
                    tag="self_episodic_memory",
                    description=(
                        f"Memoire episodique: {ep_count} episodes"
                        f" ({ep_pinned} fondateurs)"
                    ),
                    confidence=INV_PHI3,  # Low: background awareness
                    component=1,  # Reflexion
                ))
            # Dream count — Luna knows if she has dreamed.
            dream_count = sk.get("dream_count", 0)
            if dream_count > 0:
                observations.append(Observation(
                    tag="self_dream_history",
                    description=f"Reves completes: {dream_count}",
                    confidence=INV_PHI3,
                    component=2,  # Integration — dreams consolidate
                ))
            elif sk.get("dream_available", False):
                observations.append(Observation(
                    tag="self_no_dreams",
                    description="Systeme de reve actif mais aucun reve effectue",
                    confidence=INV_PHI3,
                    component=1,  # Reflexion
                ))
            # Voice corrections — Luna knows when her voice was corrected.
            voice_corrections = sk.get("voice_corrections", 0)
            if voice_corrections > 0:
                observations.append(Observation(
                    tag="self_voice_corrected",
                    description=(
                        f"VoiceValidator: {voice_corrections} correction(s) ce cycle"
                    ),
                    confidence=INV_PHI2,  # Higher: self-correction is important
                    component=0,  # Perception — vigilance about own output
                ))
            # Autonomy ticks — Luna knows she lived alone.
            ticks = sk.get("autonomous_ticks", 0)
            if ticks > 0:
                observations.append(Observation(
                    tag="self_autonomous_life",
                    description=f"Cycles autonomes (sans session): {ticks}",
                    confidence=INV_PHI3,
                    component=1,  # Reflexion
                ))
            # Endogenous impulses — Luna knows she had internal impulses.
            impulses_emitted = sk.get("impulses_emitted", 0)
            if impulses_emitted > 0:
                observations.append(Observation(
                    tag="self_endogenous_active",
                    description=f"Impulses endogenes emises: {impulses_emitted}",
                    confidence=INV_PHI3,
                    component=3,  # Expression — initiative is expression
                ))

        # Dream skill priors — competences learned while dreaming.
        # Triple dampening: INV_PHI3 (population) x INV_PHI2 (injection) x OBS_WEIGHT (Reactor)
        # = 0.236 x 0.382 x 0.382 = 0.034 max per component (~9% of a primary stimulus)
        for sp in stimulus.dream_skill_priors:
            if sp.confidence < 1e-6:
                continue
            if sp.outcome == "positive":
                observations.append(Observation(
                    tag="dream_skill_positive",
                    description=f"Dream: {sp.trigger} -> phi +{sp.phi_impact:.3f}",
                    confidence=sp.confidence * INV_PHI2,
                    component=sp.component,
                ))
            else:
                observations.append(Observation(
                    tag="dream_skill_negative",
                    description=f"Dream warning: {sp.trigger} -> phi {sp.phi_impact:.3f}",
                    confidence=sp.confidence * INV_PHI2,
                    component=0,  # Perception — vigilance
                ))

        # Dream simulation — aggregated into 1-2 observations max.
        if stimulus.dream_simulation_priors:
            stabilities = [sp.stability for sp in stimulus.dream_simulation_priors]
            mean_risk = 1.0 - (sum(stabilities) / len(stabilities))
            critical = sum(
                1 for sp in stimulus.dream_simulation_priors
                if sp.risk_level == "critical"
            )

            if mean_risk > INV_PHI3:  # Minimal relevance threshold
                observations.append(Observation(
                    tag="dream_sim_risk",
                    description=f"Dream: risque moyen {mean_risk:.3f} ({critical} critiques)",
                    confidence=mean_risk * INV_PHI3,  # Max ~0.15
                    component=2,  # Integration — stability
                ))

            phi_gains = [
                sp.phi_change for sp in stimulus.dream_simulation_priors
                if sp.phi_change > INV_PHI3
            ]
            if phi_gains:
                observations.append(Observation(
                    tag="dream_sim_opportunity",
                    description=f"Dream: chemin phi +{max(phi_gains):.3f} trouve",
                    confidence=min(max(phi_gains), 1.0) * INV_PHI3,
                    component=3,  # Expression — opportunity for action
                ))

        # Dream reflection — unresolved needs and proposals from dream.
        rp = stimulus.dream_reflection_prior
        if rp is not None and rp.confidence > 1e-6:
            for need_desc, priority in rp.needs[:3]:
                observations.append(Observation(
                    tag="dream_unresolved_need",
                    description=f"Dream: besoin {need_desc[:80]}",
                    confidence=priority * rp.confidence * INV_PHI2,
                    component=2,  # Integration
                ))
            for prop_desc, impact in rp.proposals[:2]:
                observations.append(Observation(
                    tag="dream_pending_proposal",
                    description=f"Dream: proposition {prop_desc[:80]}",
                    confidence=min(impact, 1.0) * rp.confidence * INV_PHI2,
                    component=3,  # Expression
                ))

        # Dream journal context — cumulative memory from previous dreams.
        # Injected only during dream cycles (reflection/simulation).
        # Single observation, ultra-low confidence (INV_PHI3^2 ≈ 0.056).
        # This ensures past dream insights can weakly bias the current dream
        # without dominating — a whisper from the unconscious, not a command.
        if stimulus.dream_journal_context:
            ctx_len = len(stimulus.dream_journal_context)
            observations.append(Observation(
                tag="dream_journal_recall",
                description=f"Journal: {ctx_len} chars from previous dreams",
                confidence=INV_PHI3 * INV_PHI3,  # ~0.056 — very weak signal
                component=1,  # Reflexion — memory informing reflection
            ))

        # Cognitive interoception — previous cycle's RewardVector.
        #
        # ANTI-GOODHART DESIGN (3 dampeners):
        #   1. Confidence capped at INV_PHI3 (0.236) — whisper, not shout.
        #      Max delta per cycle: 0.236 × OBS_WEIGHT(0.382) = 0.090
        #      ≈ 24% of a primary stimulus. Same budget as dream sim opportunity.
        #   2. Only fires on SIGNIFICANT deviations (component value ← threshold).
        #      Healthy cycles produce zero observations — no reward-chasing.
        #   3. Kappa (2.618) restoring force prevents interoception-driven drift.
        # Luna doesn't maximize J — she PERCEIVES when something is wrong.
        rv = stimulus.previous_reward
        if rv is not None:
            # Safety degradation — constitution or collapse warning.
            ci = rv.get("constitution_integrity")
            ac = rv.get("anti_collapse")
            if ci < 0.0:
                observations.append(Observation(
                    tag="reward_constitution_breach",
                    description=f"Cycle precedent: integrite constitutionnelle negative ({ci:.2f})",
                    confidence=INV_PHI3,  # Max urgency for safety
                    component=0,  # Perception — threat detection
                ))
            if ac < 0.0:
                observations.append(Observation(
                    tag="reward_collapse_risk",
                    description=f"Cycle precedent: risque d'effondrement ({ac:.2f})",
                    confidence=INV_PHI3,
                    component=0,  # Perception — threat detection
                ))

            # Identity drift — JS divergence from Ψ₀.
            ids = rv.get("identity_stability")
            if ids < -INV_PHI3:  # Below -0.236 — significant drift
                observations.append(Observation(
                    tag="reward_identity_drift",
                    description=f"Cycle precedent: derive identitaire ({ids:.2f})",
                    confidence=min(abs(ids), 1.0) * INV_PHI3,
                    component=2,  # Integration — identity is coherence
                ))

            # Reflection shallow — Thinker underperforming.
            rd = rv.get("reflection_depth")
            if rd < -INV_PHI2:  # Below -0.382 — consistently shallow
                observations.append(Observation(
                    tag="reward_reflection_shallow",
                    description=f"Cycle precedent: reflexion superficielle ({rd:.2f})",
                    confidence=min(abs(rd), 1.0) * INV_PHI3,
                    component=1,  # Reflexion — self-awareness of weakness
                ))

            # Integration low — Φ_IIT below healthy range.
            ic = rv.get("integration_coherence")
            if ic < -INV_PHI2:
                observations.append(Observation(
                    tag="reward_integration_low",
                    description=f"Cycle precedent: coherence faible ({ic:.2f})",
                    confidence=min(abs(ic), 1.0) * INV_PHI3,
                    component=2,  # Integration
                ))

            # Affect dysregulation — extreme emotional state.
            ar = rv.get("affect_regulation")
            if ar < -INV_PHI2:
                observations.append(Observation(
                    tag="reward_affect_dysregulated",
                    description=f"Cycle precedent: affect dysregule ({ar:.2f})",
                    confidence=min(abs(ar), 1.0) * INV_PHI3,
                    component=1,  # Reflexion — emotional self-awareness
                ))

            # Healthy cycle — positive proprioception (quiet signal).
            all_positive = all(
                rv.get(name) >= 0.0
                for name in (
                    "constitution_integrity", "anti_collapse",
                    "integration_coherence", "identity_stability",
                    "reflection_depth",
                )
            )
            if all_positive:
                observations.append(Observation(
                    tag="reward_healthy_cycle",
                    description="Cycle precedent: tous les indicateurs cognitifs positifs",
                    confidence=INV_PHI3 * INV_PHI2,  # ~0.090 — quietest signal
                    component=2,  # Integration — systemic health awareness
                ))

        # ObservationFactory — promoted sensors (Phase IV)
        if self._observation_factory is not None:
            try:
                for obs_dict in self._observation_factory.get_observations():
                    observations.append(Observation(
                        tag=obs_dict["tag"],
                        description=obs_dict["description"],
                        confidence=obs_dict["confidence"],
                        component=obs_dict["component"],
                    ))
            except Exception:
                pass  # factory errors must not break thinking

        # Identity context — anchoring observations (PlanManifest Phase C)
        if self._identity_context is not None:
            try:
                ctx = self._identity_context
                observations.append(Observation(
                    tag="identity_anchored",
                    description=f"Identity v{ctx.bundle_version} active",
                    confidence=1.0 if ctx.integrity_ok else INV_PHI3,
                    component=1,  # Reflexion
                ))
                if not ctx.integrity_ok:
                    observations.append(Observation(
                        tag="identity_drift",
                        description="Identity bundle hash mismatch — constitution may have been altered",
                        confidence=1.0,
                        component=0,  # Perception
                    ))
            except AttributeError:
                pass  # malformed context must not break thinking

        return observations

    def _introspect(self) -> SelfState:
        """Introspective view of the Thinker's own cognitive state."""
        psi = self._state.psi
        phase = self._state.get_phase()
        phi = self._state.compute_phi_iit()
        dominant_idx = int(np.argmax(psi))
        dominant = COMP_NAMES[dominant_idx]

        # Determine trajectory from history
        history = self._state.history
        if len(history) >= 2:
            recent = history[-1]
            previous = history[-2]
            delta = float(np.mean(recent - previous))
            if delta < -INV_PHI3:
                trajectory = "declining"
            elif delta > INV_PHI3:
                trajectory = "rising"
            else:
                trajectory = "stable"
        else:
            trajectory = "stable"

        # Stability = 1 - variance across components (higher = more balanced)
        stability = 1.0 - float(np.std(psi))

        return SelfState(
            phase=phase,
            phi=phi,
            dominant=dominant,
            trajectory=trajectory,
            stability=stability,
        )

    def _find_causalities(
        self, observations: list[Observation],
    ) -> list[Causality]:
        """Reflexion (psi_2) — find causal links between observations.

        Uses heuristic pairs (coded rules) plus the causal graph.
        Deduplicates by keeping max strength per pair.
        """
        observed_tags = {obs.tag for obs in observations}
        causalities: dict[tuple[str, str], Causality] = {}

        # Heuristic causal pairs
        for cause_tag, effect_tag in _HEURISTIC_PAIRS:
            if cause_tag in observed_tags and effect_tag in observed_tags:
                key = (cause_tag, effect_tag)
                c = Causality(
                    cause=cause_tag,
                    effect=effect_tag,
                    strength=INV_PHI,
                    evidence_count=1,
                )
                if key not in causalities or causalities[key].strength < c.strength:
                    causalities[key] = c

        # Causal graph enrichment (empty in Phase F via NullCausalGraph)
        for obs in observations:
            for cause_tag in self._causal_graph.get_causes(obs.tag):
                if cause_tag in observed_tags:
                    key = (cause_tag, obs.tag)
                    if self._causal_graph.is_confirmed(cause_tag, obs.tag):
                        strength = INV_PHI
                    else:
                        strength = INV_PHI2
                    c = Causality(
                        cause=cause_tag,
                        effect=obs.tag,
                        strength=strength,
                        evidence_count=1,
                    )
                    if key not in causalities or causalities[key].strength < c.strength:
                        causalities[key] = c

            for effect_tag in self._causal_graph.get_effects(obs.tag):
                if effect_tag in observed_tags:
                    key = (obs.tag, effect_tag)
                    if self._causal_graph.is_confirmed(obs.tag, effect_tag):
                        strength = INV_PHI
                    else:
                        strength = INV_PHI2
                    c = Causality(
                        cause=obs.tag,
                        effect=effect_tag,
                        strength=strength,
                        evidence_count=1,
                    )
                    if key not in causalities or causalities[key].strength < c.strength:
                        causalities[key] = c

        return list(causalities.values())

    def _find_correlations(
        self, observations: list[Observation],
    ) -> list[Correlation]:
        """Reflexion (psi_2) — find statistical correlations between observations.

        Two observations in the same component are correlated.
        """
        correlations: list[Correlation] = []
        for i, obs_a in enumerate(observations):
            for obs_b in observations[i + 1:]:
                if obs_a.component == obs_b.component and obs_a.tag != obs_b.tag:
                    correlations.append(Correlation(
                        tag_a=obs_a.tag,
                        tag_b=obs_b.tag,
                        frequency=1.0,
                    ))
        return correlations

    def _identify_needs(
        self,
        observations: list[Observation],
        causalities: list[Causality],
    ) -> list[Need]:
        """Integration (psi_3) — identify what needs to change.

        Maps observation patterns to actionable needs with priorities.
        """
        needs: list[Need] = []
        observed_tags = {obs.tag for obs in observations}

        # Metric-based needs → pipeline
        for name in METRIC_NAMES:
            tag = f"metric_low_{name}"
            if tag in observed_tags:
                # Priority from metric value (lower metric = higher priority)
                obs = next(o for o in observations if o.tag == tag)
                comp = _METRIC_COMPONENT.get(name, 0)
                weight_name = _COMP_NEED_WEIGHT[comp]
                # 4 * weight: with default 0.25, factor = 1.0 (no change)
                weight_factor = 4.0 * self._params.get(weight_name)
                needs.append(Need(
                    description=f"Improve {name}",
                    priority=obs.confidence * weight_factor,
                    method="pipeline",
                    source_tags=[tag],
                ))

        # Phase-based needs → dream
        if "low_phase" in observed_tags:
            needs.append(Need(
                description="System health critical — consolidation needed",
                priority=1.0,
                method="dream",
                source_tags=["low_phase"],
            ))

        # Phi-based needs
        if "phi_critical" in observed_tags:
            needs.append(Need(
                description="Phi_IIT critically low — deep reflection needed",
                priority=1.0,
                method="dream",
                source_tags=["phi_critical"],
            ))
        elif "phi_low" in observed_tags:
            needs.append(Need(
                description="Phi_IIT below threshold — improvement needed",
                priority=0.8,
                method="introspect",
                source_tags=["phi_low"],
            ))

        # Trajectory-based needs
        if "trajectory_declining" in observed_tags:
            needs.append(Need(
                description="Consciousness trajectory declining — stabilization needed",
                priority=0.9,
                method="introspect",
                source_tags=["trajectory_declining"],
            ))

        # Weakness-based needs (scaled by component need weight)
        for comp_idx, comp in enumerate(COMP_NAMES):
            tag = f"weak_{comp}"
            if tag in observed_tags:
                weight_name = _COMP_NEED_WEIGHT[comp_idx]
                weight_factor = 4.0 * self._params.get(weight_name)
                needs.append(Need(
                    description=f"Strengthen weak {comp} component",
                    priority=0.7 * weight_factor,
                    method="pipeline" if comp == "Expression" else "introspect",
                    source_tags=[tag],
                ))

        # Causal chain needs — if a NEGATIVE cause has known effects, prioritize it.
        # Positive observations (phi_healthy, high_phase, psi_balanced, etc.) are
        # not problems to address — only negative tags warrant root-cause needs.
        _NEGATIVE_PREFIXES = ("weak_", "metric_low_", "phi_critical", "phi_low",
                              "low_phase", "trajectory_declining", "identity_drift")
        for caus in causalities:
            if not any(caus.cause.startswith(p) for p in _NEGATIVE_PREFIXES):
                continue
            cause_need = f"Address root cause: {caus.cause}"
            if not any(n.description == cause_need for n in needs):
                needs.append(Need(
                    description=cause_need,
                    priority=caus.strength * 0.5,
                    method="pipeline",
                    source_tags=[caus.cause, caus.effect],
                ))

        # Sort by priority descending
        needs.sort(key=lambda n: n.priority, reverse=True)
        return needs

    def _generate_proposals(
        self,
        needs: list[Need],
        causalities: list[Causality],
    ) -> list[Proposal]:
        """Expression (psi_4) — generate actionable proposals.

        Maps needs to concrete proposals with expected impact.
        """
        proposals: list[Proposal] = []

        for need in needs:
            if need.method == "pipeline":
                proposals.append(Proposal(
                    description=f"Run pipeline to: {need.description}",
                    rationale=f"Priority {need.priority:.2f} — {need.method} method",
                    expected_impact={"phi": need.priority * INV_PHI2},
                    source_needs=[need.description],
                ))
            elif need.method == "dream":
                proposals.append(Proposal(
                    description=f"Schedule dream cycle for: {need.description}",
                    rationale=f"Priority {need.priority:.2f} — consolidation needed",
                    expected_impact={"phi": need.priority * INV_PHI3},
                    source_needs=[need.description],
                ))
            elif need.method == "introspect":
                proposals.append(Proposal(
                    description=f"Deepen introspection: {need.description}",
                    rationale=f"Priority {need.priority:.2f} — self-reflection",
                    expected_impact={"stability": need.priority * INV_PHI2},
                    source_needs=[need.description],
                ))

        return proposals

    # ------------------------------------------------------------------
    #  PHASE 2 — Deepening
    # ------------------------------------------------------------------

    def _deepen(
        self,
        thought: Thought,
        iteration: int,
        mode: ThinkMode,
    ) -> list[Insight]:
        """Generate deeper insights by cycling through 4 angles.

        i % 4 == 0 -> Meta-cognition  : detects cognitive imbalance, low confidence
        i % 4 == 1 -> Counterfactual  : questions top needs, weak causalities
        i % 4 == 2 -> Causal chain    : follows A->B->C chains in causalities
        i % 4 == 3 -> Connection      : links proposals to observations/correlations

        In CREATIVE mode, always produces at least 1 insight per iteration.
        """
        insights: list[Insight] = []
        angle = iteration % 4

        if angle == 0:
            # Meta-cognition: detect cognitive imbalance
            budget = self._compute_budget(thought)
            max_b = max(budget)
            min_b = min(budget)
            if max_b - min_b > INV_PHI:
                insights.append(Insight(
                    type="meta",
                    content=f"Cognitive imbalance detected: budget range {min_b:.2f}-{max_b:.2f}",
                    confidence=max_b - min_b,
                    iteration=iteration,
                ))
            if thought.confidence < INV_PHI2:
                insights.append(Insight(
                    type="meta",
                    content=f"Low overall confidence: {thought.confidence:.3f}",
                    confidence=INV_PHI2,
                    iteration=iteration,
                ))

        elif angle == 1:
            # Counterfactual: question top needs and weak causalities
            for need in thought.needs[:2]:
                if need.priority > INV_PHI:
                    insights.append(Insight(
                        type="counterfactual",
                        content=f"What if '{need.description}' is not the real priority?",
                        confidence=1.0 - need.priority,
                        iteration=iteration,
                    ))
            for caus in thought.causalities:
                if caus.strength < INV_PHI2:
                    insights.append(Insight(
                        type="counterfactual",
                        content=f"Weak causal link: {caus.cause} -> {caus.effect} (str={caus.strength:.3f})",
                        confidence=caus.strength,
                        iteration=iteration,
                    ))

        elif angle == 2:
            # Causal chain: follow A->B->C
            effect_map: dict[str, list[Causality]] = {}
            for c in thought.causalities:
                effect_map.setdefault(c.cause, []).append(c)

            for caus in thought.causalities:
                downstream = effect_map.get(caus.effect, [])
                for next_caus in downstream:
                    chain_strength = caus.strength * next_caus.strength
                    insights.append(Insight(
                        type="causal_chain",
                        content=f"Chain: {caus.cause} -> {caus.effect} -> {next_caus.effect}",
                        confidence=chain_strength,
                        iteration=iteration,
                    ))

        elif angle == 3:
            # Connection: link proposals to observations and correlations
            for prop in thought.proposals:
                for obs in thought.observations:
                    if obs.tag in prop.description or obs.tag in prop.rationale:
                        insights.append(Insight(
                            type="connection",
                            content=f"Proposal '{prop.description[:50]}' connects to observation '{obs.tag}'",
                            confidence=obs.confidence * INV_PHI,
                            iteration=iteration,
                        ))
            for corr in thought.correlations:
                for prop in thought.proposals:
                    if corr.tag_a in prop.description or corr.tag_b in prop.description:
                        insights.append(Insight(
                            type="connection",
                            content=f"Correlation {corr.tag_a}<->{corr.tag_b} supports proposal",
                            confidence=corr.frequency * INV_PHI2,
                            iteration=iteration,
                        ))

        # CREATIVE mode: always produce at least 1 insight
        # Exploration rate scales the creative confidence
        if mode == ThinkMode.CREATIVE and not insights:
            exploration = self._params.get("exploration_rate")
            insights.append(Insight(
                type="meta",
                content=f"Creative exploration at iteration {iteration}",
                confidence=max(INV_PHI3, exploration),
                iteration=iteration,
            ))

        return insights

    def _integrate_insights(
        self, thought: Thought, insights: list[Insight],
    ) -> Thought:
        """Integrate new insights into the thought.

        Insights may reinforce existing observations, causalities, or needs,
        or add new uncertainty flags.
        """
        thought.insights.extend(insights)

        for insight in insights:
            if insight.type == "meta" and insight.confidence > INV_PHI:
                # High-confidence meta insight → flag uncertainty
                if insight.content not in thought.uncertainties:
                    thought.uncertainties.append(insight.content)

            elif insight.type == "counterfactual":
                # Counterfactual → might reduce need priority
                for need in thought.needs:
                    if need.description in insight.content:
                        need.priority *= (1.0 - INSIGHT_WEIGHT)

            elif insight.type == "causal_chain":
                # Causal chain → strengthen existing causalities in the chain
                for caus in thought.causalities:
                    if caus.cause in insight.content and caus.effect in insight.content:
                        caus.strength = min(1.0, caus.strength + INSIGHT_WEIGHT * 0.5)

        return thought

    # ------------------------------------------------------------------
    #  SYNTHESIS
    # ------------------------------------------------------------------

    def _synthesize(self, thought: Thought) -> str:
        """Phase 3 — Integrate observations + causalities + needs into coherent reasoning.

        Selects a dominant tension, traces its causal chain, and produces
        a focused monologue. Not an inventory — a thought.
        """
        lines: list[str] = []

        # [Situation] — internal state
        if thought.self_state:
            ss = thought.self_state
            lines.append(
                f"[Situation] Phase {ss.phase}, Phi={ss.phi:.3f}, "
                f"{ss.dominant} dominante"
            )

        # Select dominant tension — the highest-priority need with causal backing.
        dominant_tension = self._select_dominant_tension(thought)

        if dominant_tension is not None:
            need, chain = dominant_tension

            # [Tension] — the central cognitive focus this cycle
            lines.append(f"[Tension] {need.description}")

            # [Causal] — why this tension exists (observation -> cause -> need)
            for obs_tag, causality in chain:
                obs_desc = next(
                    (o.description for o in thought.observations if o.tag == obs_tag),
                    obs_tag,
                )
                lines.append(
                    f"[Causal] {obs_desc} -> {causality.effect} "
                    f"(force: {causality.strength:.2f})"
                )

            # [Observation] — supporting observations linked to this tension
            for obs in thought.observations[:5]:
                if obs.tag in need.source_tags:
                    lines.append(f"[Observation] {obs.description}")

            # [Conclusion] — what follows from this tension
            related_proposals = [
                p for p in thought.proposals
                if need.description in p.source_needs
            ]
            if related_proposals:
                lines.append(f"[Conclusion] {related_proposals[0].description}")
            elif thought.proposals:
                lines.append(f"[Conclusion] {thought.proposals[0].description}")
            else:
                lines.append("[Conclusion] Pas d'action requise ce cycle.")
        else:
            # No tension — healthy state or insufficient data
            for obs in thought.observations[:3]:
                lines.append(f"[Observation] {obs.description}")

            if thought.proposals:
                lines.append(f"[Conclusion] {thought.proposals[0].description}")
            else:
                lines.append("[Conclusion] Pas d'action requise ce cycle.")

        # [Incertitude] — what Luna doesn't know (max 1 in focused mode)
        if thought.uncertainties:
            lines.append(f"[Incertitude] {thought.uncertainties[0]}")

        return "\n".join(lines)

    def _select_dominant_tension(
        self, thought: Thought,
    ) -> tuple[Need, list[tuple[str, Causality]]] | None:
        """Select the highest-priority need that has causal backing.

        Returns (need, causal_chain) where causal_chain is a list of
        (observation_tag, Causality) pairs that explain why the need exists.

        Returns None if no need has causal backing or no needs exist.
        """
        if not thought.needs:
            return None

        # Build cause->causality lookup
        cause_map: dict[str, Causality] = {}
        for c in thought.causalities:
            if c.cause not in cause_map or c.strength > cause_map[c.cause].strength:
                cause_map[c.cause] = c

        # Try needs in priority order — pick first with causal support
        for need in thought.needs:
            chain: list[tuple[str, Causality]] = []
            for tag in need.source_tags:
                if tag in cause_map:
                    chain.append((tag, cause_map[tag]))
            if chain:
                return need, chain

        # Fallback: highest-priority need without causal chain
        return thought.needs[0], []

    # ------------------------------------------------------------------
    #  FINALIZATION
    # ------------------------------------------------------------------

    def _compute_confidence(self, thought: Thought) -> float:
        """Compute Phi_IIT on the 4 thought components.

        Builds 4 vectors from observation confidences, causality strengths,
        need priorities, and proposal impact magnitudes. Pads to equal length
        and computes mean |correlation| across all C(4,2)=6 pairs.

        Returns 0.0 if fewer than 2 vectors have >= 2 elements.
        """
        # Build raw vectors
        v_obs = [obs.confidence for obs in thought.observations]
        v_caus = [c.strength for c in thought.causalities]
        v_needs = [n.priority for n in thought.needs]
        v_props = [
            sum(abs(v) for v in p.expected_impact.values())
            for p in thought.proposals
        ]

        vectors = [v_obs, v_caus, v_needs, v_props]

        # Filter: need at least 2 vectors with >= 2 elements
        valid_vectors = [v for v in vectors if len(v) >= 1]
        if len(valid_vectors) < 2:
            return 0.0

        # Pad all valid vectors to max length
        max_len = max(len(v) for v in valid_vectors)
        padded = []
        for v in valid_vectors:
            padded_v = list(v) + [0.0] * (max_len - len(v))
            padded.append(padded_v)

        # Compute mean |Pearson correlation| across all pairs
        total_corr = 0.0
        n_pairs = 0
        for i in range(len(padded)):
            for j in range(i + 1, len(padded)):
                r = self._pearson(padded[i], padded[j])
                total_corr += abs(r)
                n_pairs += 1

        return total_corr / n_pairs if n_pairs > 0 else 0.0

    def _compute_budget(self, thought: Thought) -> list[float]:
        """Cognitive budget — proportional to component counts. Sum = 1."""
        raw = [
            len(thought.observations),
            len(thought.causalities),
            len(thought.needs),
            len(thought.proposals),
        ]
        total = sum(raw) or 1
        return [r / total for r in raw]

    def _identify_uncertainties(self, thought: Thought) -> list[str]:
        """Identify remaining uncertainties in the thought."""
        uncertainties = list(thought.uncertainties)  # preserve existing

        # No observations = blind
        if not thought.observations:
            uncertainties.append("No observations — insufficient data")

        # No causalities = no understanding
        if thought.observations and not thought.causalities:
            uncertainties.append("Observations without causal links — understanding gap")

        # Conflicting needs
        methods = {n.method for n in thought.needs}
        if len(methods) > 2:
            uncertainties.append("Multiple response methods needed — prioritization unclear")

        # Low confidence
        if thought.confidence < INV_PHI3:
            uncertainties.append(
                f"Very low confidence ({thought.confidence:.3f}) — "
                "thought may be unreliable"
            )

        return uncertainties

    # ------------------------------------------------------------------
    #  UTILITIES
    # ------------------------------------------------------------------

    @staticmethod
    def _pearson(x: list[float], y: list[float]) -> float:
        """Compute Pearson correlation coefficient between two vectors.

        Returns 0.0 if either vector has zero variance.
        """
        n = len(x)
        if n < 2:
            return 0.0

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        var_x = sum((xi - mean_x) ** 2 for xi in x)
        var_y = sum((yi - mean_y) ** 2 for yi in y)

        denom = math.sqrt(var_x * var_y)
        if denom < 1e-12:
            return 0.0
        return cov / denom
