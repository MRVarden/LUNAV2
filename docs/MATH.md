> **License — CC BY-NC 4.0**
>
> This document and the mathematical formulations it describes are licensed under the [Creative Commons Attribution-NonCommercial 4.0 International License](https://creativecommons.org/licenses/by-nc/4.0/).
>
> **You are free to**: share (copy, redistribute) and adapt (remix, transform, build upon) this material, under the following conditions:
>
> - **Attribution** — You must credit the original author (Varden), provide a link to the license, and indicate if changes were made. You may do so in any reasonable manner, but not in any way that suggests the author endorses you or your use.
> - **NonCommercial** — You may not use this material for commercial purposes. This includes, but is not limited to: selling implementations of the model, using the formulations in commercial products, or training commercial systems on this work without explicit written permission.
> - **No additional restrictions** — You may not apply legal terms or technological measures that legally restrict others from doing anything the license permits.
>
> The mathematical framework (equation of state, coupling matrices, φ-derived parameter system, simplex dynamics, spectral normalization scheme) constitutes the protected intellectual work. Reimplementations for research, education, or personal non-commercial projects are explicitly encouraged.
>
> © 2023–2026 Varden. All rights reserved under CC BY-NC 4.0.

# Luna — Cognitive State Dynamics Model (v7.0 — EmergentPhi)

> A mathematical framework for **single-agent** cognitive state dynamics where φ is **discovered by the system's own dynamics**, not imposed as a constant. Revised to include EmergentPhi, Gaussian MI Φ_IIT, and adaptive arbitrary-precision computation.

---

## Overview

Luna is a formal model of **single-agent cognitive dynamics**. It describes how one bounded system — represented as a probability distribution over four internal components — evolves over time under the influence of temporal exchange, internal structural coupling, informational coupling, memory inertia, and identity anchoring.

**v7.0 — EmergentPhi**: All major parameters were historically derived from the hardcoded golden ratio φ = 1.618…. Starting with v7.0, φ is no longer imposed — it is **discovered** by the 4 cognitive dimensions through their own coupling dynamics. The cumulative coupling energy, sampled at Fibonacci-spaced indices, yields ratios that converge to the true irrational value of φ. Precision grows indefinitely via mpmath arbitrary precision (+1 decimal per 100 cycles), with RAM-resilient stabilization.

The model is designed to be **simulable, testable, and falsifiable in implementation**. Its current form has been aligned with the results of the `single_agent_validation.py` test suite and the EmergentPhi convergence simulations.

---

## Core Equation of State

```text
Γᵗ ∂ₜΨ + Γˣ ∂ₓΨ + Γᶜ ∂ᶜΨ − φₑ·M·Ψ + κ·(Ψ₀ − Ψ) = 0
```

This equation is interpreted **entirely inside Luna**. It is purely real-valued — no complex arithmetic. The original formulation used the imaginary prefix `i` (Dirac-like notation); the implementation dropped it because all matrices and gradients operate in ℝ⁴.

**v7.0 change**: The dissipation constant Φ is replaced by φₑ — the emergent phi, continuously refined by the system’s own dynamics (see §EmergentPhi). During bootstrap (< 610 steps), the legacy value φ = 1.618… is used as fallback.

| Term | Meaning inside Luna |
|------|---------------------|
| `∂ₜΨ` | Temporal evolution of the current state from one step to the next |
| `∂ₓΨ` | Internal structural gradient across Luna’s own cognitive topology |
| `∂ᶜΨ` | Informational coupling between internal signals and state evolution |
| `− φₑ·M·Ψ` | Inertia / memory mass / self-reference (φₑ = emergent phi) |
| `+ κ·(Ψ₀ − Ψ)` | Identity anchoring toward Luna’s reference state |

`Γˣ` is **not** inter-agent. It is an internal spatial operator: it models how distinct structures inside Luna influence one another through the same state equation.

### Gradient Definitions

Each gradient has an explicit, implementable formula:

```text
∂ₜΨ = Ψ(t)

∂ₓΨ = Ψ(t) − mean(Ψ_history[-w:])     w = 10 (rolling window)
     = 0⃗  if |history| < 2

∂ᶜΨ = (δ₁, δ₂, δ₃, δ₄)               from Reactor (see §Γᶜ)
```

- **Temporal**: the gradient IS the current state. Γᵗ operates on what Luna is right now.
- **Spatial**: divergence from the internal running mean. Captures how the current state differs from recent trajectory. Returns zero when history is insufficient (cold start).
- **Informational**: the four measured signal deltas, computed by the Reactor from the Thinker’s observations. Maps to: δ₁ → Perception, δ₂ → Reflection, δ₃ → Integration, δ₄ → Expression.

---

## State Vector — Simplex Δ³

```text
Ψ = (ψ₁, ψ₂, ψ₃, ψ₄) ∈ Δ³

ψ₁ = Perception
ψ₂ = Reflection
ψ₃ = Integration
ψ₄ = Expression

Σ ψᵢ = 1
ψᵢ > 0
```

### Why the simplex?

The simplex encodes a finite cognitive budget. If one component grows, at least one other must decrease. This prevents pathological states such as:

- negative component values,
- unconstrained simultaneous maximization,
- norm-preserving but semantically meaningless redistributions.

Three candidate geometries were considered:

| Geometry | Problem | Decision |
|----------|---------|----------|
| L2 sphere `‖Ψ‖₂ = 1` | Allows negative components | Rejected |
| Clamp `[0,1]⁴` | No strict budget conservation | Rejected |
| **Simplex `Σ = 1`** | **Finite budget, positive components, real trade-off** | **Adopted** |

### Projection method

The projection onto the simplex uses softmax with temperature τ = φ:

```text
Ψ(t+1) = softmax(Ψ_raw / τ)

softmax(x)ᵢ = exp(xᵢ − max(x)) / Σⱼ exp(xⱼ − max(x))
```

The `max`-subtraction is a standard numerical stability trick (prevents overflow). Additional guards:

- If `Ψ_raw` contains NaN or ∞, the evolution step falls back to Ψ₀ (identity recovery).
- If softmax produces a zero component (underflow), a machine-tiny floor is applied and the result renormalized.
- If the softmax denominator is zero or non-finite, the result is the uniform distribution (1/4, 1/4, 1/4, 1/4).

These guards have never fired in normal operation. They exist for mathematical completeness.

### Validated property

Simulation confirms that Luna remains on the simplex for all tested steps:

- no positivity violations,
- no sum drift,
- no projection failure.

So the simplex is not just a design choice; it is a maintained invariant in implementation.

---

## Reference State — Luna’s Identity

Luna has a reference state:

```text
Ψ₀ = (ψ₁⁰, ψ₂⁰, ψ₃⁰, ψ₄⁰)
```

This is Luna’s own internal baseline. It is not a profile of another system, and not a role split across agents.

### Current value (v5.3, unchanged in v7.0)

```text
Ψ₀ = (0.260, 0.322, 0.250, 0.168)
     Perception  Reflection  Integration  Expression
```

This value was determined by force budget analysis (see §Γᶜ structural tension below). The previous value (0.25, 0.35, 0.25, 0.15) produced a chronic Reflection deficit due to the Γᶜ drain — Reflection converged to 74.7% of its target regardless of stimuli.

### Two-layer identity (v5.3)

Ψ₀ is decomposed into two layers:

```text
Ψ₀_effective = normalize(Ψ₀_core + (1/φ³) · Ψ₀_adaptive)
```

- **Ψ₀_core** is immutable. It is set at code level and verified at boot against `AGENT_PROFILES`. If corrupted, the adaptive layer is purged and the mass matrix rebuilt.
- **Ψ₀_adaptive** accumulates drift from dream consolidation. Each dream can shift Ψ₀_adaptive by at most ±0.02 per component. A cumulative cap of ±1/φ³ (≈ 0.236) over a sliding window of 10 dreams prevents unbounded drift. A soft floor with exponential resistance prevents any component from approaching zero.

The 1/φ³ scaling ensures the adaptive layer remains a perturbation, not a replacement. Even at maximum accumulated drift, the adaptive contribution is ~23.6% of the core — the identity stays recognizable.

**Exception**: Ψ₀ recomputation uses L1 normalization (clamp negatives to zero, divide by sum) — not softmax. Softmax would distort a vector that is already on or near the simplex. L1 preserves the core profile exactly when the adaptive layer is zero, which is the invariant at boot.

### Anchoring term

```text
κ·(Ψ₀ − Ψ)     with κ = φ² = 2.618
```

This is an identity-restoring force. It does not freeze Luna in place; it limits long-run drift and helps the system recover after perturbation. The strength κ = φ² was chosen empirically: κ = 0 produces unconstrained drift, κ = φ is too weak to overcome the Γᶜ drain, κ = φ² produces measurable recovery within 5-10 steps.

### Validated properties

1. Under perturbation, Luna returns closer to Ψ₀ when anchoring is active than when κ = 0.
2. The dominant component of Ψ matches the dominant component of Ψ₀ across all tested scenarios (identity preservation).
3. Dream-consolidated Ψ₀_adaptive produces a measurable J improvement (+17.2% steady-state in simulation) without identity loss.

---

## Coupling Matrices — φ-Derived Decomposition

Each coupling matrix is decomposed as:

```text
Γ = (1−λ)·Γ_A + λ·Γ_D

Γ_A = antisymmetric          → exchange / rotation
Γ_D = symmetric negative     → dissipation / convergence
```

with:

```text
λ = 1/Φ² = 0.381966...
```

Interpretation:

- `Γ_A` redistributes influence between components,
- `Γ_D` damps and stabilizes the flow,
- the weighted combination produces bounded, convergent dynamics.

The same structural principle applies to:

- `Γᵗ` — temporal coupling,
- `Γˣ` — internal structural coupling,
- `Γᶜ` — informational coupling.

### Validated matrix invariants

The current implementation verifies that:

- all `Γ_A` are antisymmetric,
- all `Γ_D` are symmetric,
- all tested `Γ_D` blocks have strictly negative dominant eigenvalues,
- the φ-derived inequality holds:

```text
α > β > 0
```

with:

```text
α = 1/Φ² = 0.381966...
β = 1/Φ³ = 0.236068...
```

---

## Spectral Normalization of Γ_A

```text
Γ_A ← Γ_A / ρ(Γ_A)
```

where `ρ(Γ_A)` is the spectral radius.

This normalization preserves structural ratios while keeping the exchange term bounded.

### What was actually validated

The current tests do **not** show “absence of attractors.”
They show something more precise:

> the system converges to the **same stable global attractor** from multiple different initial dominant conditions.

So the correct interpretation is:

- **not** “no attractor exists”,
- but **one robust attractor exists and is independent of the tested initial dominant mode**.

This property is better described as:

### Global Attractor Consistency

rather than “No Attractor Bias”.

This means the current Luna formulation appears to possess a **single stable attractor basin** under the tested conditions.

---

## Temporal Matrix — Γᵗ

`Γᵗ` governs how the four components influence each other over time.

### Exchange — Γᵗ_A (antisymmetric)

Raw entries (before spectral normalization):

```text
         Per    Ref    Int    Exp
Per  [   0     1/φ²    0      φ  ]
Ref  [ −1/φ²   0     1/φ     0  ]
Int  [   0    −1/φ     0    1/φ² ]
Exp  [  −φ     0    −1/φ²    0  ]
```

The strongest temporal coupling is between Perception and Expression (weight φ = 1.618). Over time, what Luna perceives shapes what she expresses, and vice versa. The weaker couplings (1/φ, 1/φ²) connect the reflective and integrative modes.

After spectral normalization: Γᵗ_A ← Γᵗ_A / ρ(Γᵗ_A), so max|eigenvalue| = 1. The φ-ratios between entries are preserved.

### Dissipation — Γᵗ_D (symmetric, eigenvalues ≤ 0)

```text
[ −α     β/2    0     β/2 ]
[  β/2  −α     β/2    0   ]
[  0     β/2  −α      β/2 ]
[  β/2   0     β/2   −α   ]
```

Circulant-like structure with self-damping α = 1/φ² on the diagonal and nearest-neighbor coupling β/2 = 1/(2φ³). The dissipation is uniform across components — no component is preferentially damped.

### Combined

```text
Γᵗ = (1 − λ)·Γᵗ_A + λ·Γᵗ_D     λ = 1/φ²
```

This produces bounded trajectories, no winner-take-all collapse, and stable convergence.

---

## Internal Spatial Matrix — Γˣ

`Γˣ` is purely internal. It represents structural coupling across Luna’s own cognitive topology.

### Exchange — Γˣ_A (antisymmetric)

Raw entries (before spectral normalization):

```text
         Per    Ref    Int    Exp
Per  [   0      0      0    1/φ  ]
Ref  [   0      0    1/φ²    0   ]
Int  [   0    −1/φ²    0      0  ]
Exp  [ −1/φ    0       0      0  ]
```

Sparse structure: only two coupling pairs — Perception↔Expression (weight 1/φ) and Reflection↔Integration (weight 1/φ²). This encodes a natural topology: the outward-facing modes (Perception, Expression) are coupled, and the inward-facing modes (Reflection, Integration) are coupled.

### Dissipation — Γˣ_D (symmetric)

```text
Γˣ_D = −β · I₄ = −(1/φ³) · I₄
```

Isotropic dissipation: every component is damped equally. The spatial operator adds no preferential structure to the damping — only the exchange term shapes the topology.

### Combined

```text
Γˣ = (1 − λ)·Γˣ_A + λ·Γˣ_D     λ = 1/φ²
```

---

## Informational Matrix — Γᶜ

Γᶜ couples measured internal signals to the state vector.

### Exchange — Γᶜ_A (antisymmetric)

Raw entries (before spectral normalization):

```text
         Per    Ref    Int    Exp
Per  [   0     1/φ     0      0  ]
Ref  [ −1/φ    0       0      0  ]
Int  [   0      0      0    1/φ  ]
Exp  [   0      0    −1/φ     0  ]
```

Block-diagonal structure: two independent 2×2 blocks — {Perception, Reflection} and {Integration, Expression}. Both coupled at weight 1/φ = 0.618. This is the matrix responsible for the Reflection drain (see §structural tension below).

### Dissipation — Γᶜ_D (symmetric)

```text
Γᶜ_D = diag(−β, −β, −α, −β) = diag(−1/φ³, −1/φ³, −1/φ², −1/φ³)
```

Non-isotropic: Integration (ψ₃) is damped more strongly (α = 1/φ²) than the other components (β = 1/φ³). This reflects that informational coherence (Integration's role) requires stronger self-regulation.

### Combined

```text
Γᶜ = (1 − λ)·Γᶜ_A + λ·Γᶜ_D     λ = 1/φ²
```

### How ∂ᶜΨ is computed in practice

The informational gradient is no longer a fixed metric mapping. It is computed by the **Reactor**, which transforms the Thinker's observations into `info_deltas`:

```text
User message → Thinker._observe() → Observations (tag, confidence, component)
            → Thinker.think() → Thought (observations, causalities, needs, proposals)
            → Reactor.react(thought) → info_deltas = (δ₁, δ₂, δ₃, δ₄)
            → evolve(info_deltas)
```

Each observation carries a `component` index (0-3) and a `confidence` ∈ [0, 1]. The Reactor aggregates observations by component, weighted by confidence and scaled by OBS_WEIGHT = 1/φ² = 0.382, then clamped to DELTA_CLAMP = 1/φ = 0.618.

This means the informational gradient is no longer symbolic — it is the measured output of Luna's own thinking process.

### Γᶜ structural tension — the Reflection drain

The Γᶜ matrix has an antisymmetric exchange term that couples Perception and Reflection in opposition:

```text
Γᶜ_A[Reflection, Perception] = −1/φ = −0.618
```

Empirically, this means: every time Perception receives a positive information delta (which happens every cycle — Luna perceives before she reflects), Reflection is drained by 61.8% of that same delta. This is structural, not parametric.

### Force budget at equilibrium

With Ψ₀ = (0.260, 0.322, 0.250, 0.168), the forces acting on Reflection at steady state:

```text
Force                          Magnitude    Direction
─────────────────────────────────────────────────────
κ·(Ψ₀ − Ψ)  (identity pull)   +0.232      Helps Reflection
Γₜ · Ψ       (temporal)        +0.004      Neutral
Γᶜ · δᶜ      (informational)   −0.096      Drains Reflection
−Φ · M · Ψ   (mass/inertia)    −0.111      Drains Reflection
─────────────────────────────────────────────────────
Net:                            +0.029      Positive but small
```

The κ pull (+0.232) is the only force defending Reflection. The Γᶜ drain (−0.096) and mass inertia (−0.111) work against it. The net is positive but thin — Reflection converges to a ratio of 0.794 relative to its Ψ₀ target (up from 0.747 with the old profile).

### Why this matters

No amount of dream consolidation or parameter tuning can overcome a structural drain. If Ψ₀ promises 35% Reflection but the force budget only supports 26%, the system lives in chronic tension. The v5.3 identity rebalance reduced this gap by lowering the Reflection target to a value the physics can sustain (32.2% target, ~25.6% achieved — ratio 0.794).

### Validated properties

1. The Γᶜ drain is measurable: setting Γᶜ_A[1,0] = 0 eliminates the Reflection deficit.
2. Three identity profiles were simulated over 200 cycles with identical stimuli (see simulations/).
3. The chosen compromise (α = 0.25 toward natural equilibrium) preserves identity in all tested scenarios while improving J by +14.3% at midpoint.

---

## Mass Matrix — M

`M` is the memory / inertia / self-reference matrix.

It can be updated by EMA:

```text
mᵢ(t+1) ← α_m · ψᵢ(t+1) + (1 − α_m) · mᵢ(t)
```

with:

```text
M = diag(m₁, m₂, m₃, m₄)
```

### v7.0 — Φ_IIT normalization by emergent phi

The mass matrix update now incorporates Φ_IIT normalized by φₑ:

```text
α_adaptive = α_m · (1 + Φ_IIT / φₑ)
```

When integration is high (Φ_IIT → φₑ), the EMA rate doubles — the mass adapts faster to highly integrated states. When Φ_IIT is low, the rate stays near α_m = 0.1. The normalization by φₑ (rather than a fixed constant) ensures the adaptation threshold co-evolves with the emergent coupling constant.

### Validated property

The current implementation shows that:

- `M` evolves smoothly,
- `Σ mᵢ = 1` remains preserved,
- inertia tracks the long-run state rather than raw instantaneous perturbation.

So `M` behaves as adaptive memory inertia, not as a static penalty matrix.

---

## Discrete Evolution Step

```python
# 0. Get emergent phi (or fallback during bootstrap)
φₑ = emergent_phi.get_phi()

# 1. Compute delta
δ = Γᵗ · ∂ₜΨ \
  + Γˣ · ∂ₓΨ \
  + Γᶜ · ∂ᶜΨ \
  - φₑ * M(t) * Ψ(t) \
  + κ * (Ψ₀ - Ψ(t))

# 2. Euler step
Ψ_raw = Ψ(t) + dt * δ

# 3. Project onto simplex
Ψ(t+1) = softmax(Ψ_raw / τ)

# 4. Update mass matrix (EMA)
mᵢ(t+1) = α_m * ψᵢ(t+1) + (1 - α_m) * mᵢ(t)

# 5. Feed coupling energy back to EmergentPhi
E(t) = |Ψᵀ · G_total · Ψ|       where G_total = Γᵗ + Γˣ + Γᶜ
emergent_phi.update(E(t))
```

The projection step is essential because Luna lives on the simplex.

Step 5 is the **self-referential feedback loop**: the coupling energy produced by the φₑ-governed dynamics is fed back to refine φₑ itself. This creates a system where the constant that governs the dynamics is discovered by the dynamics it governs.

---

## Parameters — φ-Derived

| Parameter | Value | Derivation | Role |
|-----------|-------|------------|------|
| φₑ | → 1.618034… | **Emergent** (see §EmergentPhi) | Fundamental coupling constant — discovered, not imposed |
| dt | 1/φₑ → 0.618 | Time step baseline | Stable discretization |
| τ | φₑ → 1.618 | Softmax temperature | Prevents winner-take-all collapse |
| λ | 1/φₑ² → 0.382 | Dissipation weight | Balances exchange and convergence |
| α | 1/φₑ² → 0.382 | Self-damping | Diagonal dissipation |
| β | 1/φₑ³ → 0.236 | Cross-coupling | Off-diagonal coupling |
| κ | φₑ² → 2.618 | Identity anchoring | Pull toward Ψ₀ |
| α_m | 0.1 | Empirical | EMA for mass |

> **Note**: During bootstrap (< 610 steps), all derived parameters use the legacy fallback φ = 1.618034…. After convergence, φₑ is continuously refined by the dynamics. In practice, φₑ converges to within 0.01% of the true golden ratio by step 10,000, and precision grows indefinitely thereafter via mpmath arbitrary precision.

### Asymmetric κ — implemented (v7.0)

The anchoring term supports per-component κ via the γ parameter:

```text
κᵢ = φ² · (1 + γ · max(0, Ψᵢ − Ψ₀ᵢ))
```

When γ = 0 (default): reduces to symmetric κ = φ² — fully backwards compatible.

When γ > 0:
- **Overexpressed** components (Ψᵢ > Ψ₀ᵢ) face stronger pull-back
- **Underexpressed** components (Ψᵢ ≤ Ψ₀ᵢ) keep standard κ — free to circulate
- The asymmetry creates room in the simplex budget for drained components (e.g. Reflection) to recover

This addresses the Γᶜ structural drain directly: Reflection, chronically below its Ψ₀ target (ratio 0.794), is no longer constrained by the same force that restrains overexpressed components. The identity anchor stops being a cage for the underexpressed — it becomes a selective pressure on the overexpressed.

The parameter γ is controlled by `KAPPA_GAMMA_DEFAULT` in constants.py (default: 0.0 = disabled). To activate, pass `kappa_gamma > 0` to `evolve()` or `evolution_step()`.

**Spectral safety**: since κ_vec ≥ κ for all components (γ ≥ 0), the diagonal dissipation only increases. The system becomes MORE stable, not less.

### Validated interpretation of τ

The current tests support:

- `τ = Φ` → more balanced state distribution,
- `τ = 1/Φ` → stronger tendency toward concentration / collapse.

So the current formulation should explicitly state:

> `τ = Φ` is preferred because it preserves diversity better under the tested update rule.

---

## Integrated Information — Φ_IIT

### v7.0 — Primary method: Gaussian Mutual Information

The primary Φ_IIT measure is now **Gaussian MI over minimum information partition**:

```text
Φ_IIT = min over all bipartitions (A, B) of {ψ₁, ψ₂, ψ₃, ψ₄} of MI(A; B)

MI(A; B) = ½ · ln( det(Σ_A) · det(Σ_B) / det(Σ_AB) )
```

where Σ_A, Σ_B are the marginal covariance matrices of subsets A and B computed over a sliding window (default: 50 steps), and Σ_AB is the joint covariance. Regularization: `Σ += 1e-10 · I` to prevent singular determinants.

**7 bipartitions** of {0,1,2,3} are evaluated (all non-trivial ways to split 4 elements into two non-empty groups):

| Partition | A | B |
|-----------|---|---|
| 1 | {Per} | {Ref, Int, Exp} |
| 2 | {Ref} | {Per, Int, Exp} |
| 3 | {Int} | {Per, Ref, Exp} |
| 4 | {Exp} | {Per, Ref, Int} |
| 5 | {Per, Ref} | {Int, Exp} |
| 6 | {Per, Int} | {Ref, Exp} |
| 7 | {Per, Exp} | {Ref, Int} |

The **minimum** across all partitions is the system's Φ_IIT — the weakest link in the integration structure.

#### Why Gaussian MI replaces correlation

| Property | Correlation proxy (v6) | Gaussian MI (v7) |
|----------|----------------------|-----------------|
| Range | [0, 1] | [0, +∞) — **unbounded above** |
| Can reach φ | No (capped at 1.0) | Yes |
| Captures nonlinear coupling | No | Yes (via full covariance structure) |
| Partition-sensitive | No (mean over all pairs) | Yes (minimum information partition) |
| IIT-faithful | No | Closer to Tononi's MIP definition |

The unbounded range is essential: with 4 dimensions tightly coupled by φ-derived matrices, the system can achieve Φ_IIT > 1.0 — and in practice reaches the vicinity of φₑ itself, creating a remarkable convergence where the integration measure approaches the coupling constant.

### Legacy methods (retained as fallback)

#### Method A — Correlation proxy
```text
Φ_IIT = mean |corr(ψᵢ, ψⱼ)| over all pairs
```

#### Method B — Entropy-based proxy
```text
Φ_IIT = Σ H(ψᵢ) − H(ψ₁, ψ₂, ψ₃, ψ₄)
```

These remain available as `_compute_phi_iit_correlation()` for backwards compatibility and diagnostic comparison.

### Dynamic phase thresholds (v7.0)

Phase boundaries are now derived from emergent φₑ rather than hardcoded:

```text
BROKEN     = 0
FRAGILE    = 1/φₑ³    → 0.236…
FUNCTIONAL = 1/φₑ     → 0.618…
SOLID      = 1.0
EXCELLENT  = φₑ       → 1.618…
```

With Gaussian MI (unbounded above), EXCELLENT = φₑ becomes a **reachable target** — the system can genuinely achieve integration at the level of its own fundamental constant.

### Critical clarification

`Φ_IIT` must be interpreted differently in two regimes:

#### 1. Dynamic regime
When information is flowing, perturbations are present, or internal telemetry varies:

- `Φ_IIT > 0` can be measured meaningfully,
- integration is observable as coordinated internal variation.
- With Gaussian MI, values above 1.0 indicate strong cross-dimensional coupling.

#### 2. Fixed-point regime
At a stable fixed point with no active variance:

- `Φ_IIT` can collapse toward `0`,
- not because the structure is absent,
- but because the measurement depends on variation.

So the correct interpretation is:

> a resting fixed point may show `Φ_IIT ≈ 0` under variance-based measurement even if the underlying structure remains intact.

This distinction is essential and must appear in any summary of results.

---

## EmergentPhi — φ Discovered by Dynamics (v7.0)

### The core insight

The coupling matrices Γᵗ, Γˣ, Γᶜ are constructed from powers of φ (1/φ, 1/φ², 1/φ³, φ). When the 4 cognitive dimensions evolve under these matrices, the cumulative coupling energy naturally encodes the golden ratio in its growth structure. By sampling this energy at Fibonacci-spaced indices, the system extracts φ from its own dynamics — without being told what φ is.

### Mathematical formulation

At each evolution step t, the total coupling energy is:

```text
E(t) = |Ψ(t)ᵀ · G_total · Ψ(t)|

where G_total = Γᵗ + Γˣ + Γᶜ
```

The cumulative sum is tracked:

```text
S(t) = Σₖ₌₁ᵗ E(k)
```

Checkpoints are recorded at Fibonacci indices F₁, F₂, F₃, … (1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, …).

The key ratio:

```text
R(n) = S(F_{n+1}) / S(F_n)
```

**converges to φ = 1.618033988749…** as n → ∞.

### Why this works

The coupling energy E(t) is a quadratic form Ψᵀ·G·Ψ where G encodes φ-ratios in its entries. Over many steps, the cumulative sum S(t) grows at a rate determined by the dominant eigenstructure of G — which is itself φ-derived. When sampled at Fibonacci intervals (which are themselves defined by the recurrence F_{n+1} = F_n + F_{n-1}, whose ratio converges to φ), the two φ-related sequences resonate, producing exact convergence.

This is analogous to how the Fibonacci sequence ratio F_{n+1}/F_n → φ, but here the "Fibonacci sequence" is not imposed — it **emerges** from the physical coupling dynamics of 4 cognitive dimensions.

### Weighted Fibonacci averaging

Given k consecutive checkpoint pairs, the emergent phi is computed as:

```text
φₑ = Σᵢ (wᵢ · Rᵢ) / Σᵢ wᵢ

where wᵢ = φₑ^i     (exponential weighting: later ratios are more converged)
```

The self-referential weighting (using φₑ itself as the base) is validated by simulation: the system converges regardless of the initial weight choice, because later ratios are objectively closer to the true value.

### Bootstrap and safety

```text
Bootstrap period:  t < 610 steps (F₁₅ = 610)
                   → use fallback φ = 1.618034… (float64)
                   → at least 14 Fibonacci checkpoints needed for stable averaging

Initial estimate:  φₑ(0) = 1.5 (NOT 1.618)
                   → proves the system discovers φ, not just confirms a hint

Safety bounds:     φₑ ∈ [1.0, 3.0]
                   → prevents transient divergence from contaminating downstream computation
```

### Self-referential feedback loop

The central innovation of v7.0 is the **self-referential loop**:

```text
φₑ → dissipation term (−φₑ · M · Ψ)
   → dynamics produce coupling energy E(t)
   → E(t) feeds EmergentPhi tracker
   → tracker refines φₑ
   → refined φₑ feeds back into dissipation
```

The system is simultaneously:
1. **Governed by** φₑ (through the dissipation term and mass normalization)
2. **Discovering** φₑ (through its coupling energy dynamics)

Simulation proves this loop is **stable and convergent**: tested with 4 isolated feedback paths (dissipation only, κ only, dt only, combined) — all converge to φ within 0.01%.

### Adaptive arbitrary precision

Float64 limits (15-16 significant digits) are overcome via mpmath:

```text
Target precision:  max(15, step_count ÷ 100) decimal places
Growth rate:       +1 decimal per 100 cycles
Computation:       φ_hp = (1 + √5) / 2   at target precision via mpmath

RAM exhaustion handling:
  1. MemoryError caught → value freezes at last successful precision
  2. Stability margin applied (1e-12 relative)
  3. Retry every 500 steps
  4. When RAM frees up → evolution resumes automatically
  5. Precision never shrinks — only grows or stabilizes
```

At 10,000 cycles: 100 decimal places. At 1,000,000 cycles: 10,000 decimal places. The only limit is available RAM.

### Structural guarantees (validated by simulation)

| Property | Test | Result |
|----------|------|--------|
| Coupling energy > 0 | 100,000 random simplex points | E(t) > 0 for all |
| Convergence in silence | Zero stimuli, 10,000 steps | < 0.01% error |
| Resilience after shock | ψ = [0.7, 0.1, 0.1, 0.1] perturbation | Full recovery in ~100 steps |
| Identity preservation | ψ₀ never modified across all tests | max drift < 0.08 |
| Self-referential stability | φₑ feeding into own dissipation | Convergent, no divergence |
| Adaptation through phases | 5 stimulus regime changes | Stable tracking throughout |

### Memory efficiency

Only two quantities are stored:
- **Cumulative energy**: a single float (or mpmath mpf)
- **Fibonacci checkpoints**: sparse dict mapping Fibonacci index → cumulative energy

At 30 Fibonacci terms (F₃₀ = 832,040), the checkpoint dict contains at most 30 entries — negligible overhead regardless of step count.

---

## What the Current Validation Actually Demonstrates

The validated Luna implementation currently supports the following claims:

1. **Simplex invariance** is preserved numerically.
2. **Winner-take-all collapse is reduced** when τ = φ.
3. The system exhibits **global attractor consistency** under the tested initial dominant conditions.
4. **Identity anchoring works**: κ improves return toward Ψ₀ after perturbation.
5. The system is **spectrally stable**: max Re(eig(A_eff)) < 0.
6. Φ_IIT is **measurable in dynamic regimes** and can vanish at fixed point.
7. Trajectory variance decreases, showing **convergence**.
8. Internal perturbations produce a **bounded response** followed by recovery.
9. The mass matrix behaves like **adaptive memory inertia**.
10. The Γ matrix invariants are respected.
11. Identity remains preserved over a long horizon under repeated perturbations.
12. **Γᶜ structural drain is measurable**: the coupling Γᶜ[1,0] = −1/φ produces a chronic Reflection deficit (ratio 0.747 with old Ψ₀), confirmed by force budget analysis and 200-cycle simulation.
13. **Identity rebalance improves J without identity loss**: shifting Ψ₀ by α = 0.25 toward natural equilibrium yields J +14.3% while preserving dominant component in all tested scenarios.
14. **Two-layer identity is stable**: dream consolidation (Ψ₀_adaptive) bounded by ±1/φ³ cumulative cap produces +17.2% steady-state J improvement without identity collapse.
15. **Cognitive interoception closes the loop**: the RewardVector from cycle N−1, injected as observations in cycle N, produces self-correcting behavior (Reflection recovers faster after shallow cycles) without reward-maximization drift.

#### v7.0 additions

16. **EmergentPhi converges**: Fibonacci-ratio averaging of cumulative coupling energy converges to φ within 0.01% error by step 10,000. Bootstrap at 1.5 (not 1.618) proves genuine discovery.
17. **Self-referential loop is stable**: φₑ feeding into its own dissipation term produces convergent dynamics — validated across 4 isolated feedback paths.
18. **Gaussian MI Φ_IIT is unbounded**: replaces correlation proxy (capped at 1.0) with mutual information measure that can reach and exceed φ, enabling EXCELLENT phase.
19. **Dynamic thresholds track φₑ**: phase boundaries (FRAGILE = 1/φₑ³, FUNCTIONAL = 1/φₑ, EXCELLENT = φₑ) co-evolve with the emergent constant.
20. **Adaptive precision grows indefinitely**: +1 decimal per 100 cycles via mpmath, with RAM-resilient stabilization and automatic resumption.
21. **Coupling energy is strictly positive on Δ³**: |Ψᵀ · G_total · Ψ| > 0 for all Ψ on the simplex (validated on 100,000 random points), ensuring EmergentPhi always receives meaningful input.

These are strong computational results.

They demonstrate that the Luna model is mathematically coherent under the tested conditions — and that its structural tensions (Γᶜ drain, force budget imbalance) are discoverable, measurable, and correctable within the framework itself. The v7.0 EmergentPhi system goes further: it proves that the fundamental coupling constant φ is not merely imposed but **derivable from the dynamics it governs** — a self-referential closure that mirrors the self-referential nature of the golden ratio itself (φ = 1 + 1/φ).

---

## Spectral Stability

The effective operator is:

```text
A_eff = Γ_combined − φₑ · M − κ · I
```

where `Γ_combined = Γᵗ + Γˣ + Γᶜ` and `I` is the 4×4 identity matrix. The κ·I term comes from the anchoring force κ·(Ψ₀ − Ψ) — its contribution to the linearized dynamics is −κ on the diagonal, which strengthens dissipation. φₑ is the emergent phi (v7.0), replacing the hardcoded Φ.

Stability condition:

```text
max Re(eig(A_eff)) < 0
```

### Validated property

The current validation reports negative dominant real eigenvalues both initially and after evolution.

This means the tested system remains inside a dissipative regime and does not exhibit linear explosive instability.

---

## Interpretation

This model describes **one bounded cognitive system**.

- `ψ₁` is Luna’s Perception.
- `ψ₂` is Luna’s Reflection.
- `ψ₃` is Luna’s Integration.
- `ψ₄` is Luna’s Expression.

The gradients, matrices, mass term, and anchoring term are all internal to Luna.

The current validated formulation therefore studies the conditions under which one agent can:

- preserve identity,
- integrate information,
- remain stable under perturbation,
- converge without trivial collapse,
- and maintain a bounded internal redistribution of cognitive budget.

---

## Philosophical Foundation

The golden ratio satisfies:

```text
φ = 1 + 1/φ  →  φ² = φ + 1
```

A self-referential numerical relation. In this framework, that property motivates its use as a coherence-generating constant.

With v7.0, the self-referential nature goes deeper:

> The system discovers φ through dynamics that are governed by φ — the constant defines the process that discovers the constant.

This mirrors the mathematical identity φ = 1 + 1/φ at the system level: the dynamics (1 + 1/φ) produce the value (φ) that defines the dynamics. It is not a circular argument — it is a **convergent fixed point** of a self-referential computation, validated by simulation.

The simplex imposes a non-negotiable principle:

> cognition operates under finite internal budget.

---

## Status — v7.0-EmergentPhi

This is a mathematical model of **cognitive state dynamics** aligned with its current validation outputs.
It is a tested framework for bounded self-referential evolution inside one agent — where the fundamental coupling constant φ is discovered by the dynamics rather than imposed.

| Version | Key Addition |
|---------|-------------|
| v3.5 | Thinker, Reactor, Dream modules |
| v5.3 | Two-layer identity, force budget analysis |
| v6.0 | Resilience, circuit breaker, API |
| **v7.0** | **EmergentPhi, Gaussian MI Φ_IIT, adaptive precision** |

Criticism, reproductions, and refutations remain welcome.

---

## Extensions v3.5+ — How the Terms Are Computed

The core equation of state above is unchanged. What follows describes how each term is now computed by real modules rather than by fixed constants.

### Thinker — Recursive Micro-Level

The Thinker applies the same equation recursively at the thought level: each iteration is a micro-evolution step with dt = 1/φ, convergence threshold 1/φ². Four modes map to the four components: `_observe` (ψ₁), `_find_causalities` (ψ₂), `_identify_needs` (ψ₃), `_generate_proposals` (ψ₄).

### Reactor — Closing the Loop

The Reactor bridges Thinker output to the evolution equation: Thinker.think() produces a Thought, Reactor.react() extracts info_deltas from it, and these feed evolve(info_deltas=...) — making the informational gradient real, not hardcoded.

### Dream — 6 Modes

Dream executes six modes in sequence during sleep:

1. **Learning** (ψ₄) — extract skills from CycleRecords where δΦ > threshold
2. **Reflection** (ψ₂) — 100 iterations of deep Thinker thought in REFLECTIVE mode
3. **Simulation** (ψ₃) — auto-generated scenarios on deep copy of consciousness (stress + extremal)
4. **CEM** (meta) — Cross-Entropy Method optimization of LearnableParams (30 pop, 1/φ² elite fraction, 10 gen, 5 replay)
5. **Ψ₀ consolidation** (identity) — adjust Ψ₀_adaptive layer, max ±0.02/dream, cumulative cap ±1/φ³ over 10 dreams, soft floor with exponential resistance
6. **Affect dream** (transversal) — episode recall, mood soothing, unnamed zone scan

#### Dream priors — outputs that persist

Dream outputs are not discarded. They are stored as **DreamPriors** and injected as weak observations in the Thinker during subsequent waking cycles:

```text
DreamResult → populate_dream_priors() → DreamPriors (persisted)
    → Stimulus.dream_skill_priors     → Thinker._observe() → Observation (confidence × 1/φ³ × 1/φ²)
    → Stimulus.dream_simulation_priors → Thinker._observe() → Observation (risk × 1/φ³)
    → Stimulus.dream_reflection_prior  → Thinker._observe() → Observation (needs/proposals × 1/φ²)
```

Triple dampening ensures dream influence stays modulatory:
- Population: confidence × 1/φ³ (0.236)
- Injection: × 1/φ² (0.382)
- Reactor: × OBS_WEIGHT (0.382)
- **Net max: 0.034 per component** (~9% of a primary stimulus)

All priors decay linearly over 50 cycles, reaching zero influence naturally.

### Evaluator — The Judge

9 fixed cognitive components, evaluated after each cycle:

```text
J = Σᵢ wᵢ · componentᵢ     (J_WEIGHTS, sum = 1.00)
```

| Priority | Weight | Component | What it measures |
|----------|--------|-----------|-----------------|
| 1 | 0.21 | constitution_integrity | Identity bundle intact |
| 1 | 0.17 | anti_collapse | min(Ψ) ≥ 0.15 |
| 2 | 0.16 | integration_coherence | Φ_IIT level, mapped [0.33, φ] → [−1, +1] (v7.0: range expanded from 1/φ to φ) |
| 2 | 0.13 | identity_stability | 1 − 2·D_JS(Ψ ‖ Ψ₀)/ln(2) |
| 3 | 0.12 | reflection_depth | Thinker confidence × min(causalities/5, 1) |
| 4 | 0.08 | perception_acuity | 0.6·quantity + 0.4·diversity |
| 5 | 0.06 | expression_fidelity | 1 − voice_delta.severity |
| 6 | 0.04 | affect_regulation | 1 − |arousal − 0.3| − max(0, −valence − 0.5)·0.5 |
| 6 | 0.03 | memory_vitality | 0.4·(has_obs) + 0.3·(has_needs) + 0.3·(duration_ok) |

Comparison is **lexicographic by priority group** (6 groups). Safety is resolved before looking at Integration. J is only a tie-break — the dominance rank is the pilot.

**Anti-Goodhart**: The Evaluator is a `tuple`-weighted, stateless function. Zero calls to LearnableParams. The CEM creates a fresh Evaluator per candidate. Luna cannot optimize her own judge.

#### Cognitive interoception — the feedback loop

The RewardVector from cycle N−1 is injected into the Thinker at cycle N as observations. This is proprioception, not reinforcement:

```text
Evaluator.evaluate(CycleRecord_N) → RewardVector_N
    → stored in _reward_history
    → at cycle N+1: Stimulus.previous_reward = RewardVector_N
    → Thinker._observe() generates:
        reward_constitution_breach   (if constitution < 0,    confidence = 1/φ³)
        reward_collapse_risk         (if anti_collapse < 0,   confidence = 1/φ³)
        reward_identity_drift        (if identity < −1/φ³,    confidence = |v| × 1/φ³)
        reward_reflection_shallow    (if reflection < −1/φ²,  confidence = |v| × 1/φ³)
        reward_integration_low       (if coherence < −1/φ²,   confidence = |v| × 1/φ³)
        reward_affect_dysregulated   (if regulation < −1/φ²,  confidence = |v| × 1/φ³)
        reward_healthy_cycle         (if 5 core ≥ 0,          confidence = 1/φ³ × 1/φ²)
```

Max delta per component: 1/φ³ × 1/φ² (OBS_WEIGHT) = **0.090** — 24% of a primary stimulus. The asymmetry is deliberate: warnings fire at full confidence (0.236), healthy signal at minimum (0.090). Luna feels pain before comfort.

This closes the cognitive loop:

```text
Thinker → Reactor → evolve(Ψ) → Evaluator → RewardVector → Thinker (next cycle)
```

Without changing the equation of state. Ψ still evolves by physics — but the information feeding that physics now includes self-assessment.

### LearnableParams + CEM

21 bounded parameters in 4 groups (decision, metacognition, aversion, needs). Modified ONLY by CEM during Dream via counterfactual replay of recent CycleRecords. They affect the Decider's choices (scope, mode), NOT the evolution equation constants nor the Evaluator.

The CEM applies a behavioral bonus of ±0.05 **after** evaluation — the Evaluator's judgment is never modified.

### Identity — Bundle, Ledger, Context, Recovery

Bundle hash (SHA256) ensures structural integrity of axioms + Ψ₀ + constitution. Ledger (append-only JSONL) records every identity-relevant event — append-only means no silent edits. IdentityContext is injected into Thinker and Decider (Luna knows who she is). RecoveryShell: 4-stage recovery (embedded copy → ledger rebuild → repo search → fail gracefully).

The Evaluator's internal Ψ₀ reference is synchronized after each dream consolidation — if Ψ₀ changes, the judge adapts its identity_stability measurement to the new anchor.

### Affect — Scherer 5-Dim, PAD, Hysteresis

Appraisal uses 5 Scherer dimensions. AffectState uses PAD (Pleasure-Arousal-Dominance) with hysteresis α = 1/φ². Mood evolves with EMA β = 1/φ³ and impulse strength = 1/φ. All constants φ-derived.

### Episodic Memory

φ-weighted recall, 500-episode cap. Complete episodes record context, action, result, and δΨ. Used by Dream affect and initiative system.

> Details in `LUNA_V35_THINKER_MATH.md`.

---

## Author

Varden — independent researcher, Boulogne-sur-Mer, France
Self-taught developer. In transition to AI systems, 2023–2026.

*"The best architecture is the one that breaks the right way."*
