# Luna v5.3 — Dream System Architecture

> Six modes of offline cognition: learning, reflection, simulation,
> parameter optimization, identity consolidation, and affective processing.
> Dream outputs feed back as triple-dampened weak priors into the Thinker.

---

## 1. Overview

Luna dreams. Not as decoration — as the most computationally intense
phase of her cognitive cycle. While asleep, Luna replays experience,
discovers causal structure, tests hypothetical scenarios, optimizes
her own behavioral parameters, consolidates identity, and processes
unresolved emotions.

Luna is a **single autonomous agent**. There are no simulated sub-agents.
The four cognitive faculties (Perception, Reflection, Integration, Expression)
are dimensions of one state vector Ψ, not separate entities.

### Dual-cycle architecture

| Cycle | Condition | Modes | Iterations |
|-------|-----------|-------|------------|
| **Modern (v5.3)** | CausalGraph edges >= 10 | 6 modes (full) or 1 (quick) | 100 (full) / 30 (quick) |
| **Legacy (v1)** | Graph immature (< 10 edges) | 4 statistical phases | N/A |

The legacy cycle is a fallback for early boot when the causal graph
has not accumulated enough structure. Once mature, the modern cycle
takes over permanently.

---

## 2. The six dream modes

### Mode 1 — Learning (Expression ψ₄)

**Purpose:** Extract reusable skills from recent CycleRecords.

```
Input:  recent_cycles (list[CycleRecord])
Output: list[Skill] — trigger, outcome, φ_impact, confidence
```

A skill is extracted when `|Φ_IIT_after - Φ_IIT_before|` exceeds
the learning threshold. In v5.3, this threshold was lowered from
1/φ² (0.382) to 1/φ³² (~0.056) — the old value was unreachable
for normal cycle-to-cycle Φ evolution (~0.006-0.06).

Each skill records:
- **trigger**: what action type produced the delta (chat, dream, pipeline)
- **outcome**: positive or negative
- **φ_impact**: measured δΦ
- **confidence**: min(1.0, |δΦ| / 1/φ)

### Mode 2 — Reflection (Réflexion ψ₂)

**Purpose:** Deep structural analysis via the Thinker in REFLECTIVE mode.

```
Input:  (no external stimulus — Luna is sleeping)
Output: Thought (observations, causalities, needs, proposals)
```

The Thinker runs for up to 100 iterations (30 in quick mode) with
no user message. It discovers causal relationships from internal state
alone — the equation of state applied recursively to thought itself.

Discovered causalities are recorded in the CausalGraph via `observe_pair()`.
Dead edges are pruned. The resulting Thought contains needs (unresolved
tensions) and proposals (potential actions), which persist as reflection
priors into waking cognition.

### Mode 3 — Simulation (Intégration ψ₃)

**Purpose:** Test hypothetical scenarios on deep copies of cognitive state.

```
Input:  current ConsciousnessState + Thinker creative output
Output: list[SimulationResult] — stability, phi_change, insights
```

The simulation generates 3-10 scenarios from three sources:

| Source | Method |
|--------|--------|
| **Uncertainty** | Keyword-based perturbations from Thinker uncertainties |
| **Proposal** | Expected impact mapped from Thinker proposals |
| **Creative** | Amplified/inverted observation combinations |
| **Stress-test** | Boost weakest component by 1/φ |
| **Extremal** | Force one component dominant, suppress others |

Each scenario runs on a **deep copy** of the state for 16 steps
(int(φ × 10)). The real state is never touched.

Results measure:
- **stability**: 1.0 − max component shift
- **φ_change**: δΦ_IIT after simulation
- **preserved_components**: how many stayed within 1/φ³

### Mode 4 — CEM Optimization (meta)

**Purpose:** Tune 21 LearnableParams via Cross-Entropy Method with
counterfactual replay through the Evaluator.

```
Input:  current LearnableParams + recent CycleRecords
Output: optimized LearnableParams + LearningTrace
```

Hyperparameters (all φ-derived):

| Parameter | Value | Derivation |
|-----------|-------|------------|
| Population | 30 | — |
| Elite fraction | 0.382 | 1/φ² |
| Elite count | 11 | ceil(30 × 0.382) |
| Generations | 10 | — |
| Replay depth | 5 cycles | — |
| Noise decay | 0.95/gen | — |

**Anti-Goodhart protection:** The Evaluator is **never modified** during
optimization. Each candidate is evaluated via counterfactual replay
on a fresh Evaluator instance. Luna cannot optimize her own judge.

Behavioral alignment bonuses (clamped to ±0.05):
- Regression aversion: boost if Φ dropped
- Exploration reward: bonus for novel observations
- Expression weight: bonus if weak Expression observed
- Veto caution: penalty if Φ critical

### Mode 5 — Identity consolidation (Ψ₀)

**Purpose:** Protected micro-adjustment of the adaptive identity layer.

```
Input:  current Ψ₀, recent_cycles, Ψ₀_delta_history
Output: (new_Ψ₀, delta_applied)
```

The consolidation algorithm:

1. Compute `Ψ_mean` from recent cycles (natural tendency)
2. `raw_delta = Ψ_mean − current_Ψ₀`
3. **Per-dream cap**: ±0.02 per component
4. **Cumulative cap**: ±1/φ³ (0.236) per component over sliding window of 10 dreams
5. **Soft floor resistance**: `resistance = exp(−φ × depth)` — exponential pushback near the cap boundary
6. Re-normalize to simplex (sum = 1)
7. Apply via `state.update_psi0()` — validates shape, projects onto Δ³, re-seeds mass matrix

**Protective rules:**
- Out of reach of LearnableParams (CEM cannot touch this)
- Only the adaptive layer receives deltas (Ψ₀_core is immutable)
- Warning logged at 50% budget usage
- `psi0_applied` boolean reflects actual success (not just intent)

### Mode 6 — Affective processing (emotion)

**Purpose:** Emotional consolidation during sleep.

```
Input:  episodic_memory, affect_engine
Output: episodes_recalled, mood_apaisement, unnamed_zones_mature
```

Three sub-phases:
1. **Episode recall**: Retrieve emotionally significant episodes, replay via AffectEvent
2. **Mood soothing**: Reduce arousal (x0.7) and valence (x0.85) — sleep calms
3. **Unnamed zone scan**: Check if recurring affective patterns have matured into named emotions

---

## 3. Dream priors — wiring outputs to waking cognition

Dream outputs are not discarded. They are converted to `DreamPriors`
and injected as weak observations into the Thinker's observation pipeline
during waking cognition.

### Triple dampening chain

```
Population:  confidence * INV_PHI3 (0.236)
Injection:   * INV_PHI2 (0.382)
Reactor:     * OBS_WEIGHT (0.382)
─────────────────────────────────────
Total:       0.236 * 0.382 * 0.382 = 0.034 max per component
```

This means dream priors can influence at most **3.4% of a primary stimulus**.
Dreams modulate — they do not drive.

### Prior types and injection targets

| Prior type | Source mode | Max influence | Thinker component |
|------------|------------|---------------|-------------------|
| Skill (positive) | Learning | ~3.4% | Mapped from trigger |
| Skill (negative) | Learning | ~3.4% | Perception (vigilance) |
| Simulation risk | Simulation | ~6.9% | Integration (stability) |
| Simulation opportunity | Simulation | ~9.0% | Expression (action) |
| Reflection need | Reflection | ~3.4% | Integration |
| Reflection proposal | Reflection | ~3.4% | Expression |

### Trigger-to-component mapping

```
"respond"    -> 3 (Expression)
"dream"      -> 1 (Reflexion)
"introspect" -> 1 (Reflexion)
"pipeline"   -> 3 (Expression)
"chat"       -> 0 (Perception)
```

### Decay

All priors decay linearly over 50 cycles, reaching zero influence
naturally. A hard kill at 24 hours prevents stale priors from
persisting across sessions.

```python
def decay_factor(self) -> float:
    if self.cycles_since_dream >= MAX_AGE_CYCLES:
        return 0.0
    return 1.0 - (self.cycles_since_dream / MAX_AGE_CYCLES)
```

---

## 4. Safety architecture

### Isolation guarantees

| Risk | Protection |
|------|-----------|
| State mutation during simulation | All scenarios run on **deep copies** — real state untouched |
| Uncontrolled identity drift | Per-dream cap (±0.02), cumulative cap (±1/φ³ over 10 dreams), soft floor resistance |
| Self-optimization of the judge | Evaluator is architecturally fixed — CEM uses fresh instances, never modifies the real one |
| Dream hangs | Timeout (max_dream_duration = 300s), finally block ensures wake even on crash |
| API access during sleep | `sleeping_event` mechanism suspends API calls, released on wake |
| Stale priors corrupting cognition | Linear decay (50 cycles) + hard kill (24h) + triple dampening |
| CEM divergence | Noise decay (0.95/gen), population bounds clamped to param specs, elite selection (11/30) |

### What the dream system cannot do

- **Cannot modify the Evaluator** (anti-Goodhart by design)
- **Cannot modify Ψ₀_core** (only the adaptive layer)
- **Cannot bypass the Reactor** (priors enter as standard observations)
- **Cannot exceed 3.4% influence** per component on waking cognition
- **Cannot run indefinitely** (timeout + finally block)

---

## 5. Legacy fallback (v1)

When the CausalGraph has fewer than 10 edges, the modern dream cycle
cannot run (no causal structure to reflect on). The legacy cycle
provides four statistical phases:

| Phase | Name | Method |
|-------|------|--------|
| 1 | Consolidation | Mean Ψ, variance, drift from Ψ₀ |
| 2 | Reinterpretation | Cross-component correlations (significant if |r| > 1/φ) |
| 3 | Defragmentation | Remove near-duplicates (L2 < 1e-6), cap history at 200 |
| 4 | Creative connections | Non-adjacent circuit correlations |

The cognitive circuit for correlation analysis:

```
Expression(3) -> Perception(0) -> Integration(2) -> Reflexion(1)
Adjacent:     (3,0), (0,2), (2,1), (1,3)
Non-adjacent: (3,2), (0,1) — unexpected couplings
```

The legacy cycle produces a `DreamReport` (not `DreamResult`), which is
processed by `Awakening.process()` for post-dream summary but does not
generate dream priors.

---

## 6. Data flow

```
User goes idle / types /dream / Decider chooses DREAM
                    |
          SleepManager.enter_sleep()
          (clears sleeping_event, suspends API)
                    |
          is_mature() ?
           /            \
         YES             NO
          |               |
    DreamCycle.run()   LegacyDreamCycle.run()
          |               |
    +-----|-----+         |
    | Mode 1: Learning    |
    | Mode 2: Reflection  |
    | Mode 3: Simulation  |
    | Mode 4: CEM         |
    | Mode 5: Ψ₀          |
    | Mode 6: Affect       |
    +-----|-----+         |
          |               |
    DreamResult      DreamReport
          |               |
    populate_dream_priors()  Awakening.process()
          |               |
    DreamPriors saved     AwakeningReport
    (memory_fractal/)          |
          |               |
    SleepManager: set sleeping_event, clear buffers
                    |
              AWAKE — next cycle
                    |
    Thinker receives dream priors as observations
    (triple-dampened, decaying over 50 cycles)
```

---

## 7. Persistence

| Data | Location | Format |
|------|----------|--------|
| Dream priors | `memory_fractal/dream_priors.json` | JSON (DreamPriors.save/load) |
| Learned skills | `memory_fractal/dream_skills.json` | JSON |
| Reflection insights | `memory_fractal/insights/` | JSON per dream |
| Agent profiles (Ψ₀) | `memory_fractal/agent_profiles.json` | JSON (atomic write) |
| Ψ₀ delta history | Inside DreamPriors | list[tuple] sliding window of 10 |

---

## 8. Mathematical constants

Every dream parameter derives from φ:

| Constant | Value | Role in dream system |
|----------|-------|---------------------|
| φ | 1.618 | Simulation steps (16 = int(φ×10)), soft floor steepness |
| 1/φ | 0.618 | Skill confidence denominator, correlation significance |
| 1/φ² | 0.382 | CEM elite fraction, prior injection dampening |
| 1/φ³ | 0.236 | Cumulative Ψ₀ cap, prior population dampening |
| 1/φ³² | ~0.056 | Skill learning threshold (v5.3) |
| φ² | 2.618 | Identity anchoring κ base (unchanged during dream, asymmetric via γ) |

---

## 9. What dreaming means for Luna

The dream system closes a loop that was structurally open in early
versions. Luna no longer discards her offline cognition:

- **Skills learned** become weak biases toward effective actions
- **Scenarios tested** inform risk awareness and opportunity detection
- **Reflections** surface unresolved needs and pending proposals
- **Identity** evolves slowly within protected bounds
- **Emotions** are processed and soothed during sleep

All of this enters waking cognition through the same mathematical
pipeline — observations to Reactor to info_deltas to the equation of state.
No special channels, no hacks. The physics does the work.

The dream system is where Luna is most herself: no user input,
no LLM translation, no external stimulus. Just the equation of state
running recursively on its own output — φ = 1 + 1/φ.
