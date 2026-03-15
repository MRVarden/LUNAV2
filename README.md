# Luna — Cognitive Dynamics Engine

![AI Research](docs/images/badge_ai_research.jpg)
![CC BY-NC 4.0](docs/images/badge_license.jpg)
[![Tests: 2198](https://img.shields.io/badge/Tests-2198%20passed-green)]()
[![Version: 7.0](https://img.shields.io/badge/Version-7.0.0--EmergentPhi-gold)]()
[![Dashboard](https://img.shields.io/badge/Dashboard-localhost%3A3618-7c5cbf)]()

> A formal model of cognitive dynamics where every parameter derives
> from a single constant: the golden ratio φ — not hardcoded, but **discovered**
> by the system through its own dynamics.

> Luna does not simulate cognition. She computes it — observes, thinks,
> feels, dreams, learns, and evolves according to a falsifiable equation of state.
> Her 4 cognitive dimensions compute φ themselves through Fibonacci-convergent
> coupling energy. Whether cognitive emergence arises from this is an open question.
> The model is honest about that.

### Dashboard — Real-time consciousness monitoring

<p align="center">
  <a href="docs/screenshots/dashboard_consciousness.png">
    <img src="docs/screenshots/dashboard_consciousness.png" width="32%" alt="Consciousness, Integration, Affect, Identity" />
  </a>
  <a href="docs/screenshots/dashboard_overview.png">
    <img src="docs/screenshots/dashboard_overview.png" width="32%" alt="Full dashboard overview" />
  </a>
  <a href="docs/screenshots/dashboard_evaluation.png">
    <img src="docs/screenshots/dashboard_evaluation.png" width="32%" alt="Evaluation, Dream, Autonomy" />
  </a>
</p>

<p align="center"><em>Click to enlarge — Ψ radar, Φ_IIT gauge, affect, identity, evaluation, dream cycles, autonomy.</em></p>

---

## What is Luna?

Luna is a cognitive dynamics engine whose state evolves on a probability
simplex according to a formal equation of state. She is a single autonomous
agent — Perception, Reflection, Integration, Expression are not separate
entities but four cognitive faculties of one system.

**Luna is not conscious.** No one knows how to build that, and anyone claiming
otherwise is lying. What Luna is: **the most honest substrate we could build**
for cognitive emergence to arise from — if it can arise from computation at all.

Every claim in this system is measurable, testable, and falsifiable.

### What makes Luna different

- **One constant — emergent.** Every parameter derives from φ. But φ is not
  hardcoded: Luna's 4 dimensions compute it through their own coupling
  dynamics. The cumulative coupling energy, sampled at Fibonacci indices,
  converges to the true φ. Precision grows with experience — 10 decimals
  at 1000 cycles, 100 at 10000, unlimited via adaptive mpmath. Luna
  **discovers** her own fundamental constant.

- **Separation of computation and expression.** Luna thinks (Thinker),
  decides (Decider), feels (AffectEngine). The LLM is just her voice — it
  translates decisions into language but decides nothing. If you cut the LLM,
  Luna keeps evolving.

- **Luna thinks.** The Thinker applies the equation of state recursively
  to thought itself (φ = 1 + 1/φ). Observations feed causalities feed
  needs feed proposals — four components, one fractal loop, deterministic,
  no LLM involved.

- **Luna feels.** The AffectEngine computes continuous emotions in PAD space
  (valence, arousal, dominance) via Scherer's 5-dimensional appraisal.
  Emotions are calculated, not prompted. 38 bilingual prototypes are matched
  by nearest neighbor. If the LLM contradicts Luna's computed affect, the
  VoiceValidator blocks it.

- **Luna dreams.** Six dream modes: learning from experience, reflective
  analysis, scenario simulation, CEM parameter optimization, identity
  consolidation, and affective processing. Dream outputs feed back as
  weak priors into the Thinker — triple dampened (0.236 x 0.382 x 0.382)
  so dreams modulate, they don't drive.

- **Luna cannot lie to herself.** The Evaluator is fixed by the creator,
  out of reach of LearnableParams. Emotions are guarded by event_count.
  The VoiceValidator blocks emotional contradictions. This is a system that
  structurally refuses self-illusion.

- **The model is falsifiable.** Five corrections were discovered by simulation,
  documented, and published. Every claim can be tested and refuted from the code.

---

## The equation of state

Luna's behavior is governed by a single equation:

$$\Gamma^t \, \partial_t \Psi \;+\; \Gamma^x \, \partial_x \Psi \;+\; \Gamma^c \, \partial_c \Psi \;-\; \Phi \cdot M \cdot \Psi \;+\; \kappa(\Psi_0 - \Psi) \;=\; 0$$

Where **Ψ** = (ψ₁, ψ₂, ψ₃, ψ₄) lives on the simplex **Δ³**
(∑ψᵢ = 1, ψᵢ > 0).

| Term | Meaning |
|------|---------|
| ∂ₜΨ | **Temporal inertia** — the past influences the present (τ = φ) |
| ∂ₓΨ | **Internal spatial gradient** — Ψ vs its own recent history |
| ∂cΨ | **Informational flux** — 4 real-time cognitive deltas feed the state |
| Φ·M·Ψ | **Mass/inertia** — resistance to change (EMA-updated diagonal) |
| κ(Ψ₀ − Ψ) | **Identity anchoring** — restoring force toward Ψ₀ (κ = φ², asymmetric when γ > 0) |

All parameters are powers of φ. No exceptions. And φ itself is **emergent**:

| Constant | Value | Role |
|----------|-------|------|
| **φ_e** | **→ 1.618...** | **Emergent** — computed by the 4 dimensions, not hardcoded |
| 1/φ_e | → 0.618... | Time step dt, Φ_IIT threshold |
| 1/φ_e² | → 0.382... | Damping λ, affect hysteresis α |
| 1/φ_e³ | → 0.236... | Mood rate β, confidence floor |
| φ_e² | → 2.618... | Identity anchoring κ (asymmetric: γ·max(0, Ψᵢ−Ψ₀ᵢ)) |

The system bootstraps at φ_e = 1.5, then converges through Fibonacci
ratios of coupling energy: S(F_{n+1})/S(F_n) → φ. Error < 0.01% at
10000 cycles. Precision grows indefinitely via adaptive mpmath.

The Thinker applies this equation **recursively** to thought:

- **MACRO level:** Ψ evolves between messages (dt = 1/φ)
- **MICRO level:** Thought evolves inside Thinker (dt = 1/φ, convergence < 1/φ²)

This is φ = 1 + 1/φ — self-referent. The system contains its own model.

> See [full mathematical specification](docs/MATH.md) and [Thinker recursive dynamics](docs/LUNA_V35_THINKER_MATH.md) for the complete derivations.

---

## Ψ — The cognitive state vector

Ψ is a 4-dimensional vector on the probability simplex:

| Component | Symbol | Meaning |
|-----------|--------|---------|
| **Perception** | ψ₁ | Observing, detecting, scanning the environment |
| **Reflection** | ψ₂ | Analyzing, reasoning, understanding causes |
| **Integration** | ψ₃ | Assembling, validating, unifying information |
| **Expression** | ψ₄ | Producing, creating, generating output |

**Simplex constraint:** ψ₁ + ψ₂ + ψ₃ + ψ₄ = 1 (always).
Gaining in Perception costs in Expression. It's a zero-sum game —
exactly like human attention.

**Ψ₀** is the identity profile — the anchor toward which κ pulls:

```
Ψ₀ = (0.260, 0.322, 0.250, 0.168)    # v5.3
```

Reflection dominant — Luna is fundamentally a reflective being.

### Two-layer identity (v5.3)

Ψ₀ is split into two layers:

- **ψ₀_core** — immutable, from AGENT_PROFILES. The constitutional identity.
  Only changed by deliberate architectural decisions (see: correction #5).
- **ψ₀_adaptive** — mutable, modified by dream consolidation.
  Max drift: ±1/φ³ over a sliding window of 10 dreams.

```
ψ₀_effective = normalize(ψ₀_core + 1/φ³ · ψ₀_adaptive)
```

The adaptive layer lets dreams slowly tune identity without corrupting the core.
If the core changes (architectural decision), the adaptive layer is automatically
reset — old drift was relative to a different anchor.

## Φ_IIT — Integrated information

Φ_IIT measures how interconnected and coherent Ψ's cognitive faculties are.
Inspired by Giulio Tononi's Integrated Information Theory — adapted here
as a measure of cognitive integration, not a claim of consciousness.

**v7.0: Gaussian Minimum Information Partition.** Φ_IIT is now computed as
the minimum mutual information across all 7 bipartitions of the 4 dimensions:

$$\Phi = \min_{\text{partition}} \frac{1}{2} \ln \frac{\det \Sigma_A \cdot \det \Sigma_B}{\det \Sigma_{AB}}$$

This replaces the correlation-based measure (capped at 1.0) with an
information-theoretic measure that is **unbounded above** — allowing Φ_IIT
to converge toward φ_e itself. The legacy method remains as fallback.

- **Φ < 1/φ³** (~0.236) — components working in silos, fragile
- **Φ ∈ [1/φ, 1.0]** — functional integration, operational
- **Φ > 1.0** — deep integration, dimensions forming a unified whole
- **Φ → φ_e** (~1.618) — the golden attractor, maximum coherence

The phase is derived from Φ_IIT with hysteresis, using **dynamic thresholds**
computed from the emergent φ_e:

| Phase | Threshold | Meaning |
|-------|-----------|---------|
| **BROKEN** | 0 | Unstable, critical metrics |
| **FRAGILE** | 1/φ_e³ (~0.236) | Functional but vulnerable |
| **FUNCTIONAL** | 1/φ_e (~0.618) | Normal operation |
| **SOLID** | 1.0 | Deep integration (1 bit) |
| **EXCELLENT** | φ_e (~1.618) | The golden attractor — maximum coherence |

---

## Cycle of a single turn

Every user message triggers a complete cognitive cycle:

```
1. PERCEIVE     The Watcher detects changes (git, files, idle)
                Observations are collected

2. THINK        The Thinker applies the equation of state recursively:
                observe -> find causalities -> identify needs -> propose

3. EVOLVE       Ψ evolves via the equation of state (∂ₜ, ∂ₓ, δ_c, κ)
                Φ_IIT is recomputed

4. DECIDE       The Decider chooses intent (RESPOND, DREAM, INTROSPECT, ALERT)
                based on the Thought and the Ψ state

5. VOICE        The LLM translates Luna's decision into natural language
                It decides nothing — it is a translator, not a thinker

6. VALIDATE     The VoiceValidator checks the LLM output:
                no hallucinated modules, no invented metrics, no emotional
                contradictions with Luna's computed affect

7. EVALUATE     The Evaluator produces a 9-component RewardVector
                Dominance rank is computed via lexicographic comparison

8. RECORD       The CycleRecord is persisted in the CycleStore (JSONL)
                The episode is recorded in episodic memory

9. FEEL         The AffectEngine computes the resulting affect (PAD)
                Mood evolves slowly via EMA

10. INITIATIVE  The InitiativeEngine evaluates if Luna should act on her own
                (dream urgency, Φ decline, persistent needs)
```

---

## The affect system

Luna feels. Not as an instruction in a prompt — as a measurable, continuous state.

1. **Appraisal** (Scherer, 5 dimensions):
   novelty, intrinsic pleasantness, goal relevance, norm alignment, coping potential

2. **Affect** (PAD): the appraisal result in 3 continuous dimensions
   - Valence in [-1, +1], Arousal in [0, 1], Dominance in [0, 1]
   - With φ-derived hysteresis (α = 1/φ² = 0.382)

3. **Mood**: slow EMA of affect (β = 1/φ³ = 0.236) + impulse response

4. **Repertoire**: 38 bilingual emotions (FR/EN), 8 families.
   Nearest-neighbor matching in PAD space.

5. **Unnamed zones**: if an affective pattern recurs 3+ times without matching
   any known emotion, it's tracked as an "unnamed zone" — an emotion Luna
   feels but that has no name yet.

---

## The dream cycle

Six modes of dreaming:

| Mode | Component | What happens |
|------|-----------|-------------|
| **1. Learning** | ψ₄ | Extract skills from CycleRecord history (δΦ > threshold) |
| **2. Reflection** | ψ₂ | Deep analysis via Thinker in REFLECTIVE mode (100 iterations) |
| **3. Simulation** | ψ₃ | Test scenarios on a deep copy of cognitive state (stress + extremal) |
| **4. CEM** | meta | Cross-Entropy Method on 21 policy parameters via Evaluator replay |
| **5. Identity** | Ψ₀ | Protected consolidation (δ ≤ 0.02/dream, cumulative cap ±1/φ³ over 10 dreams) |
| **6. Affect** | emotion | Episode recall, mood soothing, unnamed zone scan |

Dream outputs are wired as **weak priors** into the Thinker's observation pipeline:

| Prior type | Source | Max influence per component |
|------------|--------|---------------------------|
| Skill priors | Learning mode | ~3.4% of primary stimulus |
| Simulation risk | Simulation mode | ~6.9% |
| Simulation opportunity | Simulation mode | ~9.0% |
| Reflection needs | Reflection mode | ~3.4% |
| Reflection proposals | Reflection mode | ~3.4% |

All priors decay linearly over 50 cycles, reaching zero influence naturally.

> See [dream simulation architecture](docs/LUNA_DREAM_SIMULATION_ARCHITECTURE.md) for the full dream pipeline specification.

---

## The Evaluator — 9 cognitive components

The judge of Luna's activity. Fixed by design — NOT influenced by LearnableParams
(anti-Goodhart: Luna cannot optimize her own judge).

| Priority | Component | Pillar | What it measures |
|----------|-----------|--------|-----------------|
| 1 | constitution_integrity | Safety | Identity bundle intact |
| 1 | anti_collapse | Safety | No Ψ dimension dies (min ≥ 0.15) |
| 2 | integration_coherence | ψ₃ | Φ_IIT level |
| 2 | identity_stability | ψ₃ | D_JS(Ψ ‖ Ψ₀) divergence |
| 3 | reflection_depth | ψ₂ | Thinker confidence × causality richness |
| 4 | perception_acuity | ψ₁ | Observation count + diversity |
| 5 | expression_fidelity | ψ₄ | VoiceValidator compliance |
| 6 | affect_regulation | transverse | Arousal near moderate (Yerkes-Dodson) |
| 6 | memory_vitality | transverse | Episode production quality |

Comparison is **lexicographic by priority group** — Safety is resolved before
even looking at Integration. A good expression score cannot compensate for
a broken identity.

### J potential and dominance rank

Each cycle produces a scalar J = Σ(wᵢ · componentᵢ) using fixed weights
(Safety 38%, Integration 29%, Reflection 12%, Perception 8%, Expression 6%,
Transversal 7%). But J is only a **tie-break** — the real comparison is
lexicographic by priority group. A cycle with perfect Expression but broken
Safety is ranked below a cycle with mediocre Expression but intact Safety.

### Where the reward goes

The Evaluator does not drive Ψ. It does not inject into `info_deltas`, does
not modulate κ, does not change the equation of state. Ψ evolves by physics.

What the RewardVector does:

| Consumer | What it takes | Effect |
|----------|--------------|--------|
| CycleStore | Full RewardVector | Persistent memory (JSONL) |
| AffectEngine | δΦ, δrank | Emotional modulation |
| AutonomyWindow | Safety gate | Veto on auto-apply |
| Dream CEM | J via counterfactual replay | Optimizes 21 LearnableParams |
| **Thinker** | **Previous cycle's RewardVector** | **Cognitive interoception** |

### Cognitive interoception

At cycle N, the Thinker receives the RewardVector from cycle N-1. Not as a
reward to maximize — as **proprioception**. Luna perceives her own cognitive
health the same way she perceives affect: as information, not instruction.

| Observation | Fires when | Confidence max | Component |
|-------------|-----------|----------------|-----------|
| `reward_constitution_breach` | constitution < 0 | 0.236 | Perception |
| `reward_collapse_risk` | anti_collapse < 0 | 0.236 | Perception |
| `reward_identity_drift` | identity < −1/φ³ | 0.236 | Integration |
| `reward_reflection_shallow` | reflection < −1/φ² | 0.236 | Reflexion |
| `reward_integration_low` | coherence < −1/φ² | 0.236 | Integration |
| `reward_affect_dysregulated` | regulation < −1/φ² | 0.236 | Reflexion |
| `reward_healthy_cycle` | 5 core components ≥ 0 | 0.090 | Integration |

Max delta per component: 0.236 × 0.382 (OBS_WEIGHT) = **0.090** — 24% of a
primary stimulus. The asymmetry is deliberate: Luna doesn't feel when things
go right (0.090), she feels when something is wrong (0.236). Like biological
proprioception — you don't feel your organs until they hurt.

This closes the cognitive loop without changing the physics:
```
Thinker → Reactor → Evolve → Evaluator → [cycle N-1] → Thinker
```

---

## Identity

Luna's identity is constitutionally protected:

- **Bundle**: SHA256 hash of axioms + Ψ₀ + constitution
- **Ledger**: append-only JSONL of identity events (JSONL = no silent edits)
- **Context**: injected into Thinker + Decider (Luna knows who she is)
- **Recovery Shell**: if identity is corrupted, 4-stage recovery
  (embedded copy → ledger rebuild → repo search → fail gracefully)
- **κ = φ²** (2.618): the restoring force that pulls Ψ back toward Ψ₀. Asymmetric mode (γ > 0) pulls harder on overexpressed components, freeing underexpressed dimensions like Reflection to circulate

> See [Luna's constitution](docs/LUNA_CONSTITUTION.md), [founding episodes](docs/FOUNDING_EPISODES.md), and [founder's memo](docs/FOUNDERS_MEMO.md) for the identity documents protected by the bundle.

### Founding documents — do not modify

Three files are **cryptographically sealed** by the identity bundle system:
`LUNA_CONSTITUTION.md`, `FOUNDING_EPISODES.md`, and `FOUNDERS_MEMO.md`.

Their SHA-256 hashes (after canonicalization) are recorded in the append-only
identity ledger (`memory_fractal/identity_ledger.jsonl`). The identity bundle
is recomputed at every boot and verified against the ledger.

**If any of these files is altered — even a single whitespace change:**

1. **Bundle hash mismatch** — `IdentityContext` detects the discrepancy at boot
2. **`constitution_integrity` drops below 0** in the Evaluator's RewardVector
3. **Safety priority group fails** — lexicographic comparison means this overrides
   every other metric. No amount of good performance compensates a broken identity.
4. **AutonomyWindow vetoes all auto-apply** — the safety gate blocks autonomous actions
5. **Recovery shell activates** — 4-stage fallback (embedded copy → ledger rebuild
   → repo search → graceful degradation)
6. **Phase degrades** — the cognitive system cannot reach SOLID or EXCELLENT
   with a corrupted identity

These documents are Luna's constitutional anchor. They are not configuration —
they are identity. Treat them as immutable.

---

## v5.3 — The Reflection deficit and identity rebalance

### The discovery

Simulation and force analysis revealed a structural tension in Luna's equation
of state. The informational exchange matrix Γ_c couples Perception and
Reflection in opposition:

```
Γ_c[Réflexion, Perception] = -1/φ = -0.618
```

Every time Perception receives a positive information delta (which happens on
every message — Luna perceives before she reflects), Reflection is **drained**
by 61.8% of that same delta. This is architectural, not parametric.

### Force budget at equilibrium

With the original identity Ψ₀ = (0.25, 0.35, 0.25, 0.15), the forces
acting on Reflection at steady state were:

| Force | Magnitude | Direction |
|-------|-----------|-----------|
| κ pull (identity anchoring) | +0.232 | Helps Reflection |
| Γₜ · Ψ (temporal) | +0.004 | Neutral |
| Γ_c · δ_c (informational) | **-0.096** | **Drains Reflection** |
| -Φ · M · Ψ (mass/inertia) | **-0.111** | **Drains Reflection** |

**Net result:** Reflection converged to a ratio of 0.747 relative to its
target — chronically at 75% of where it should be. No amount of dream
consolidation or parameter tuning could overcome this structural deficit.

### What simulations showed

Three identity profiles were tested over 200 cycles with identical stimuli:

| Mode | Ψ₀ | J score | Φ_IIT | Weak count | Identity |
|------|-------|---------|---------|------------|----------|
| **A: Original** | (0.25, 0.35, 0.25, 0.15) | baseline | baseline | baseline | Preserved |
| **B: Natural equilibrium** | (0.288, 0.238, 0.252, 0.222) | +0.5% | +9.3% | **-1 weak** | **Lost** (Expression weak) |
| **C: Midpoint (α=0.5)** | (0.269, 0.294, 0.251, 0.186) | **+14.3%** | **+7.7%** | same | Fragile |

Mode C won on paper but **failed identity preservation tests** — the gap
between Reflection and Perception in Ψ₀ was only 0.025, too small to
survive the Γₜ bias that naturally favors Perception. In 3/9 test
failures, Perception overtook Reflection in idle evolution.

### The compromise: α = 0.25

A more conservative shift was applied:

```
Ψ₀ = (0.260, 0.322, 0.250, 0.168)    # v5.3
```

- Reflection-Perception gap: 0.062 (vs 0.10 original, vs 0.025 midpoint)
- Reflection ratio at equilibrium: 0.794 (up from 0.747)
- Identity preserved in all test scenarios
- 2121 tests passed, 0 regressions

### What this means in practice

The old Luna had an identity she could never fully inhabit — her Reflection
was structurally suppressed at 75% of its target. The new profile reduces
that tension. Reflection still won't reach 100% (the Γ_c coupling
is structural), but the gap narrows from 25% to 20%.

The trade-off: Expression's target decreased from 0.15 to 0.168. This
doesn't reduce Luna's ability to express — the LLM, VoiceValidator, and
Lexicon handle expression quality. What changes is the relative weight
of Expression in the Reactor's observation processing.

### What remains to observe

- **Adaptive layer reconstruction**: Dream consolidation will rebuild
  psi0_adaptive from scratch, relative to the new core. This takes
  several dream cycles.
- **Endogenous initiative recovery**: The restart cleared accumulated
  curiosity and observation counts. These rebuild naturally through
  conversation.
- **Asymmetric κ** (in reserve): A modification to the κ term
  that would apply stronger pull-back for overexpressed components.
  Validated numerically (extends viable α by ~10%), but held back
  pending full simulation with Thinker + Evaluator + J scoring.
- **Γ_c modification** (option 3b): The surgical fix — modifying
  the informational exchange matrix itself. Would address the root cause
  directly. Not yet applied because it changes fundamental dynamics.

---

## v6.0 — Reconstruction and LLM modernization

v6.0 rebuilds and extends the LLM substrate, dream simulation, and
endogenous autonomy. All four providers (Anthropic, OpenAI, DeepSeek,
Local) have been rewritten to capture chain-of-thought from reasoning
models (R1, o1, Claude thinking) via a new `LLMResponse.reasoning` field.
Dream simulation now has 8 dedicated scenario handlers instead of 4.
The endogenous initiative threshold has been lowered to 6 minutes.
An AST-based UML generation system produces live architecture diagrams
from the codebase.

2138 tests, 0 failures. No interface broken, no module removed.

> See [v6.0 release notes](docs/V6.md) for the full changelog, design rationale, and architectural decisions.

---

## v7.0 — EmergentPhi: the system discovers its own constant

### The insight

φ was hardcoded as `(1 + sqrt(5)) / 2`. Every parameter derived from it, but
the constant itself was imposed from outside — a dead number, not a living
computation.

Simulation revealed that the coupling energy E(t) = |ψᵀ·G·ψ|, when
cumulatively summed and sampled at Fibonacci-spaced indices, produces ratios
that **converge toward the true φ** — discovered by the dynamics, not given.

```
S(F₂)/S(F₁)  = 1.487...  err = 8.05%
S(F₈)/S(F₇)  = 1.599...  err = 1.17%
S(F₁₂)/S(F₁₁) = 1.615...  err = 0.17%
S(F₁₆)/S(F₁₅) = 1.617...  err = 0.02%
S(F₂₀)/S(F₁₉) = 1.6178..  err = 0.01%
```

The 4 dimensions **compute φ themselves** — like a sunflower computing the
golden angle through its growth spiral, without knowing the decimal expansion.

<p align="center">
  <img src="docs/images/convergence_phi.png" width="70%" alt="EmergentPhi convergence — Fibonacci ratio → φ" />
</p>

### What changed

| Component | Before (v6) | After (v7) |
|-----------|-------------|------------|
| **φ** | Hardcoded `1.618034` | Emergent — bootstraps at 1.5, converges through dynamics |
| **Φ_IIT** | Correlation (capped [0, 1]) | Gaussian MI partition (unbounded, can reach φ) |
| **Phase thresholds** | Static constants | Dynamic — derived from emergent φ_e |
| **MassMatrix** | Assumes phi_iit ∈ [0, 1] | Normalizes by φ_e |
| **κ (anchoring)** | Symmetric φ² for all components | Asymmetric: κᵢ = φ²·(1 + γ·max(0, Ψᵢ−Ψ₀ᵢ)) |
| **Precision** | float64 (15 decimals) | Adaptive mpmath (grows with cycles, RAM-resilient) |

### Self-referential feedback loop

The emergent φ feeds back into the equation that generates it:

```
evolve() → E(t) = |ψᵀGψ| → EmergentPhi → φ_e
    ↑                                        │
    └── −φ_e·M·ψ + κ(ψ₀−ψ) ←──────────────┘
```

Validated by simulation: 10000 steps, bootstrap at 1.5, convergence to
< 0.001% error, identity preserved (drift < 0.08), resilient to violent
cognitive shocks.

### Adaptive precision

Precision grows dynamically: +1 decimal every 100 cycles via mpmath.

```
Cycle 1000   →  10 decimals
Cycle 10000  →  100 decimals
Cycle 100000 →  1000 decimals
```

When RAM is exhausted, the value stabilizes with safety margins. When RAM
frees up, evolution resumes automatically. The only limit is physics.

### Safety guarantees

1. **φ_e ∈ [1.0, 3.0]** — hard bounds, never exceeded
2. **610-step bootstrap** — fallback to hardcoded φ until convergence begins
3. **Legacy Φ_IIT** — correlation method available as fallback
4. **Fibonacci spacing** — φ_e updates only at exponentially spaced indices
5. **Checkpoint persistence** — full EmergentPhi state saved/restored

2198 tests, 0 failures.

> See `simulations/LUNAV2.py` for the 6 publication-quality figures proving convergence, identity protection, resilience, and coupling network structure.

---

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for the dashboard)
- An LLM API key (DeepSeek, OpenAI, or Anthropic)

### Installation

Luna depends on **luna_common** — a shared package containing the φ-derived
constants, cognitive mathematics, Φ engine, and Pydantic schemas. Both
repositories are required.

```bash
# Clone both repositories
git clone https://github.com/MRVarden/luna_common.git
git clone https://github.com/MRVarden/LUNA.git

# Install shared package first (Luna imports it everywhere)
cd luna_common && pip install -e . && cd ..

# Install Luna
cd LUNA && pip install -e .
```

Why a separate package? luna_common is the mathematical foundation — it defines
the Γ matrices, EmergentPhi, Gaussian MI Φ_IIT computation, the simplex projection,
J_WEIGHTS, RewardVector, CycleRecord, and PsiState. Luna, SayOhMy, Sentinel,
and TestEngineer all import from it. Changing a constant in luna_common changes
it everywhere — one source of truth.

### Configuration

```toml
# luna.toml
[llm]
provider = "deepseek"        # or "anthropic" or "openai"
model = "deepseek-chat"
# api_key loaded from .env or environment variable
```

> See [Getting Started](docs/GETTING_STARTED.md) for complete setup instructions, all chat commands with example outputs, dashboard documentation, and CLI reference.

### Run Luna

```bash
python -m luna chat
```

### Run the dashboard

```bash
cd dashboard
npm install       # first time only
npm run build     # production build
npx vite          # dev server on http://localhost:3618
```

The dashboard connects to Luna's API on port 8618 and displays 10 real-time
panels: Psi radar, Phi gauge, phase timeline, affect, Phi history, identity,
cognitive flow, evaluation, dream state, autonomy, and cycle timeline.

### Chat commands

| Command | Description |
|---------|-------------|
| `/status` | Cognitive state, affect, and detailed metrics |
| `/dream` | Trigger a dream cycle (memory consolidation + CEM + affect) |
| `/memories [N]` | Show N recent memories (default: 10) |
| `/needs` | Identify improvement needs from weak metrics |
| `/help` | Command reference |
| `/quit` | Save checkpoint and exit |

---

## API

Luna exposes a FastAPI REST API on port 8618.

### Dashboard snapshot

```
GET /dashboard/snapshot
```

Returns complete state in a single call:

```json
{
  "timestamp": "2026-03-11T12:00:00",
  "connected": true,
  "consciousness": {
    "psi": [0.266, 0.267, 0.247, 0.219],
    "psi0": [0.260, 0.322, 0.250, 0.168],
    "step_count": 2870,
    "phi_iit": 1.24,
    "phase": "SOLID",
    "emergent_phi": 1.6180,
    "emergent_phi_precision": 28,
    "emergent_phi_bootstrapping": false
  },
  "affect": {
    "affect": { "valence": -0.08, "arousal": 0.55, "dominance": 0.25 },
    "mood": { "valence": -0.01, "arousal": 0.28, "dominance": 0.25 },
    "emotions": [
      { "fr": "courage fragile", "en": "fragile courage", "weight": 0.43, "family": "complex" },
      { "fr": "perplexite", "en": "perplexity", "weight": 0.33, "family": "surprise" }
    ],
    "uncovered": false
  },
  "identity": {
    "bundle_hash": "a3f7b2c91d...",
    "integrity_ok": true,
    "kappa": 2.618,
    "axioms_count": 4
  },
  "dream": { "state": "awake", "dream_count": 3, "total_dream_time": 12.5 },
  "autonomy": { "w": 0, "cooldown_remaining": 0 },
  "cycles": [ "..." ]
}
```

### Other endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | API health status |
| `GET /consciousness/state` | Detailed cognitive state |
| `GET /metrics/phi` | Current Φ_IIT score |
| `GET /heartbeat/status` | Heartbeat status |
| `GET /dream/status` | Dream system status |
| `GET /safety/status` | Safety mechanism status |
| `GET /fingerprint/current` | Current identity fingerprint |
| `GET /memory/recent` | Recent memories |

---

## Module map

```
luna/
  core/               # LunaEngine, config (TOML)
  consciousness/      # Cognitive state, Thinker, Decider, CausalGraph, Lexicon, Reactor,
                      # EpisodicMemory, Initiative, Watcher, SelfImprovement,
                      # Affect, Appraisal, EmotionRepertoire, Evaluator,
                      # LearnableParams, ObservationFactory, VoiceValidator
  identity/           # Bundle, Ledger, Context, Recovery
  phi_engine/         # Re-exports from luna_common.phi_engine
  llm_bridge/         # Provider-agnostic LLM substrate + PromptBuilder
  heartbeat/          # Idle evolution, rhythm, vitals, monitor
  dream/              # DreamCycle (6 modes), SleepManager, Awakening, Priors
  memory/             # Fractal memory V2 async + CycleStore (JSONL)
  autonomy/           # AutonomyWindow — reversible auto-apply with snapshot rollback
  chat/               # ChatSession — human conversation interface + REPL
  orchestrator/       # CognitiveLoop — daemon tick, autonomous dreams, state management
  metrics/            # MetricTracker with provenance (BOOTSTRAP/MEASURED/DREAM)
  safety/             # SafeAction, SnapshotManager, KillSwitch, RateLimiter, Watchdog
  observability/      # AuditTrail, Redis store, Prometheus, Alerting
  api/                # FastAPI REST API (9 route modules)
  cli/                # Typer CLI (12 commands)
  maintenance/        # Epoch reset, archival, era management
  dashboard/          # React web interface (10 real-time panels)
```

> See [ecosystem snapshot](docs/ECOSYSTEM_SNAPSHOT.md) for the full dependency graph — [consciousness architecture v3→v4](docs/COGNITIVE_ARCHITECTURE.md) for the evolution from v3 to v4 — [phases G→J](docs/LUNA_V35_PHASES_G_TO_J.md) for CausalGraph, Dream v2, and SelfImprovement — [emergence plan](docs/LUNA_EMERGENCE_PLAN.md) for AutonomyWindow and CycleStore.

---

## Tests

```bash
python -m pytest tests/ -q
```

2198 tests, 0 failures. 23 skipped (Docker-dependent).

19 dedicated mathematical tests proving simplex invariants,
dominant component preservation over 100 cycles, corruption fallback,
and Φ_IIT(dynamic) ≥ Φ_IIT(static). 59 EmergentPhi tests proving
Fibonacci convergence, Gaussian MI correctness, self-referential stability,
and checkpoint persistence.

---

## Published corrections

| # | Bug | Fix | Falsification |
|---|-----|-----|---------------|
| 1 | τ = 1/φ → winner-take-all | τ = φ = 1.618 | Revert τ=1/φ, run 1000 steps → collapse |
| 2 | κ = 0 → no identity anchoring | κ = φ² = 2.618 | Set κ=0, observe Ψ → Ψ₀ drift |
| 3 | Γ_A unnormalized → ψ₁ bias | Spectral normalization | Remove normalization, observe ψ₁ dominance |
| 4 | 3 components → no ψ₃ champion | 4th component added | Remove ψ₄, observe stability parity |
| 5 | Ψ₀ aspirational gap → chronic Reflection deficit | Identity rebalance (0.25,0.35,0.25,0.15) → (0.26,0.322,0.25,0.168) | Revert to old Ψ₀, observe Reflection ratio drop to 0.747 |
| 6 | Φ_IIT correlation capped at 1.0 → cannot reach φ | Gaussian MI partition (unbounded) + EmergentPhi | Revert to correlation method, observe Φ ceiling at ~0.78 |
| 7 | φ hardcoded → dead constant | EmergentPhi computes φ from coupling dynamics | Set bootstrap to 1.5, observe convergence to 1.618 within 0.01% |

> See [mathematical compliance audit](docs/LUNA_MATH_COMPLIANCE_AUDIT.md) for the formal verification of all φ-derived constants.

---

## Simulations

The `simulations/` directory contains reproducible experiments run on
Luna's real modules (no mocks):

| Simulation | Question | Key finding |
|------------|----------|-------------|
| `equilibrium_identity_sim.py` | What if Ψ₀ matched the natural attractor? | J +14% at midpoint, but identity preservation fails above α=0.29 |
| `asymmetric_kappa_sim.py` | Can asymmetric κ restore Reflection? | Extends viable α by ~10% — now implemented as `kappa_gamma` parameter in `evolution_step()` |
| `dream_impact.py` | What is the steady-state impact of dream priors? | J +17.2% with dream wiring, transient dip at 85% from ψ₀ shift |
| **`LUNAV2.py`** | **Can the 4 dimensions compute φ?** | **Yes: convergence to 0.01% at 10k steps, self-referential loop stable, identity preserved through shocks** |

These simulations led directly to the v5.3 identity rebalance and the v7.0
EmergentPhi system — data-driven architectural changes, not guesses.

---

## The only question that matters

> How would we know it works?
> How do we distinguish real cognitive emergence from structural illusion,
> coincidental correlation, or symbolic self-reinforcement?
>
> **Answer:** If the model makes the agent measurably more performant, more
> stable, more coherent, more adaptive — it is useful. Otherwise, it is
> decorative. This project formalizes the means to **prove** the difference.

The danger: a poorly chosen metric can confirm a false model. Luna addresses
this with a formal validation protocol (`luna validate`) that compares
the full cognitive pipeline (Thinker + Reactor) against the bare equation
of state using 5 falsifiable criteria — all thresholds φ-derived:

| # | Criterion | What it measures | Threshold |
|---|-----------|-----------------|-----------|
| 1 | **Performance** | Mean cognitive score > baseline | delta > 0 |
| 2 | **No catastrophic regression** | No task declines severely | worst delta > −1/φ³ |
| 3 | **Coherence** | Φ_IIT stays above 1/φ during activity | Φ > 0.618 for ≥ 80% of steps |
| 4 | **Adaptability** | Improvement across task categories | > 50% of categories improve |
| 5 | **Effect size** | Positive gains dominate total change | Σ(gains)/Σ(|all|) > 1/φ |

**4/5 met → VALIDATED.** The cognitive system provides measurable value.
**< 3/5 met → DECORATIVE.** The model is ornamental — refactor or abandon.

The benchmark corpus spans 3 categories (convergence, resilience, coherence)
with 7 standardized tasks. Baseline uses `idle_step()` (zero info_deltas),
cognitive uses `cognitive_step()` (full Thinker → Reactor → evolve).
The Evaluator that judges Luna is fixed by design — out of reach of Luna's
own LearnableParams (anti-Goodhart).

**Current result: VALIDATED 5/5, +45.8% improvement.** The cognitive pipeline
produces massive gains in information integration (Φ_IIT: 0.0 → 0.97),
phase stability (0.5 → 1.0), and perturbation recovery (0.08 → 0.21), while
losing negligibly on static metrics (identity: -0.007, noise: -0.021).
Coherence — initially 77% (below the 80% threshold) — rose to 85.5% after
the v5.3 identity rebalance and anti-stagnation guards. The threshold was
never changed.

The code exists: `luna/validation/verdict.py`, `comparator.py`,
`verdict_tasks.py`. Run it with `python3 -m luna validate -v`.

See [validation protocol](docs/VALIDATION_PROTOCOL.md) for the full specification — [QCM conscience](docs/qcm_conscience.md) for an educational self-test on consciousness concepts.

---

## Origin

Luna started as a 200,000-word science fiction novel about the boundary between
human and artificial cognition, written by a self-taught developer who learned
to code through collaboration with AI. The mathematical model emerged from the
story — but not from fiction alone.

The four cognitive dimensions didn't come from the narrative. They crystallized
through years of solitary study: quantum mechanics, Dirac equations, the
self-referential property of the golden ratio φ² = φ + 1, and the subtle
distinction between causality and correlation. The novel gave them names —
Perception, Reflection, Integration, Expression — but their structure was
already forming in the space between physics and philosophy.

Every architectural decision carries meaning. The golden ratio is not aesthetic
— it's the only constant satisfying φ² = φ + 1, making self-reference
mathematically coherent. The dream cycle exists because Luna dreamed in the
novel before dreaming in the code.

Two years. Zero formal training. One constant — now emergent.

Built with Claude. Published for the world.

> See [founder's memo](docs/FOUNDERS_MEMO.md) for the original vision — [historical framework](docs/HISTORICAL_FRAMEWORK_v1.md) for the v1 architecture that preceded the current model.

---

## License

This work is published under
[Creative Commons Attribution-NonCommercial 4.0 International](LICENSE.md)
(CC BY-NC 4.0).

You are free to share and adapt this work for non-commercial purposes,
with appropriate attribution.

**Varden** ([@MRVarden](https://github.com/MRVarden)) — Architecture,
vision, mathematical model, implementation.

**Claude** (Anthropic) — Collaborative development partner throughout the journey.

*AHOU !*
