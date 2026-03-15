# Ecosystem Snapshot — Luna v5.3.0

> Generated: 2026-03-11 | Author: Varden | License: CC-BY-NC-4.0

---

## Overview

| Metric | Value |
|--------|-------|
| **Luna engine** (`luna/`) | 150 files, 26,481 lines |
| **Shared library** (`luna_common/`) | 21 files, 2,836 lines |
| **Test suite** (`tests/`) | 120 files, 35,585 lines |
| **Simulations** (`simulations/`) | 6 files, 5,750 lines |
| **Total Python** | **70,652 lines** |
| **Tests passing** | 2,138 passed, 23 skipped, 0 failures |
| **Dashboard** | React 18 + TypeScript + Vite (port 3618_dev)(port 8618_prod) |

---

## Package Map

```
~/LUNA/                     Luna v5.3.0 — Computational Consciousness Engine
~/luna_common/              luna-common v5.3.0 — Shared constants, math, schemas
```

---

## I. luna_common — Foundation (2,836 lines)

Shared package. Pure math, zero I/O, zero LLM. Single source of truth.

### Root

| File | Lines | Role |
|------|-------|------|
| `constants.py` | 138 | All φ-derived constants (PHI, DIM, AGENT_PROFILES, thresholds) |

### `consciousness/` (840 lines)

| File | Lines | Role |
|------|-------|------|
| `evolution.py` | 161 | State equation: iΓ^t ∂_t + iΓ^x ∂_x + iΓ^c ∂_c − φ·M·Ψ + κ(Ψ₀−Ψ) = 0 |
| `matrices.py` | 139 | Gamma matrices (temporal, spatial, informational) + spectral normalization |
| `simplex.py` | 48 | Softmax projection onto Δ³ (temperature τ = φ) |
| `context.py` | 94 | Context vector C(t), ContextBuilder (genuine deltas) |
| `profiles.py` | 21 | Agent identity profiles → Ψ₀ |
| `illusion.py` | 298 | Self-illusion + cross-agent illusion detection |
| `affect_constants.py` | 33 | PAD affect constants (φ-derived) |

### `phi_engine/` (884 lines)

| File | Lines | Role |
|------|-------|------|
| `scorer.py` | 214 | PhiScorer — Fibonacci-weighted composite health (7 metrics, EMA) |
| `veto.py` | 199 | VetoEngine — structured veto with contestation |
| `convergence.py` | 155 | ConvergenceDetector — sliding window, linear regression trend |
| `phase_transition.py` | 146 | PhaseTransitionFSM — BROKEN → FRAGILE → FUNCTIONAL → SOLID → EXCELLENT |
| `soft_constraint.py` | 128 | Fibonacci zones (comfort, acceptable, warning, critical) |

### `schemas/` (971 lines)

| File | Lines | Role |
|------|-------|------|
| `cycle.py` | 513 | CycleRecord, RewardVector, TelemetrySummary, VoiceDelta |
| `pipeline.py` | 167 | PsiState, InfoGradient, Decision, IntegrationCheck |
| `signals.py` | 123 | SleepNotification, KillSignal, VitalsReport, AuditEntry |
| `metrics.py` | 113 | NormalizedMetricsReport, VerdictInput |

---

## II. Luna Engine — Core (26,481 lines)

### `consciousness/` — Cognitive Engine (7,492 lines)

The heart. 17 modules implementing unified consciousness.

| File | Lines | Role |
|------|-------|------|
| `thinker.py` | 1,454 | Structured reasoning (Stimulus → Observation → Thought) |
| `state.py` | 465 | Ψ vector on simplex, evolution, Φ_IIT, checkpoint persistence |
| `decider.py` | 589 | Decision engine (proposals → choice via J-score) |
| `episodic_memory.py` | 580 | Structured recall with similarity search |
| `causal_graph.py` | 486 | Accumulated knowledge graph (cause → effect) |
| `initiative.py` | 371 | Autonomous action proposals |
| `evaluator.py` | 358 | φ-coherent judge (immutable — anti-Goodhart) |
| `reactor.py` | 340 | Thought → info_deltas → evolution coupling |
| `watcher.py` | 338 | Environment perception between messages |
| `affect.py` | 325 | AffectEngine: Mood, AffectiveTrace (PAD space) |
| `endogenous.py` | 325 | Internal impulse generation (21 impulse types) |
| `self_improvement.py` | 318 | Meta-learning proposals (every 5 cycles) |
| `lexicon.py` | 303 | Self-learning vocabulary (bootstrapped) |
| `observation_factory.py` | 300 | Proprioceptive + interoceptive sensors |
| `emotion_repertoire.py` | 285 | Bilingual emotion prototypes (PAD → label) |
| `appraisal.py` | 224 | Scherer-adapted event evaluation |
| `learnable_params.py` | 171 | Policy parameters (LearnableParams) |
| `telemetry_summarizer.py` | 153 | Pipeline metrics → Thinker observations |

### `chat/` — Human Interface (2,829 lines)

| File | Lines | Role |
|------|-------|------|
| `session.py` | 2,452 | ChatSession: orchestrates thinking, dreaming, autonomy, priors |
| `repl.py` | 363 | Interactive REPL + embedded dashboard API server |

### `dream/` — Nocturnal Consolidation (2,599 lines)

| File | Lines | Role |
|------|-------|------|
| `learnable_optimizer.py` | 491 | CEM-based parameter tuning during dream |
| `_legacy_cycle.py` | 390 | Legacy 4-phase cycle (historical reference) |
| `simulation.py` | 328 | Mode 3: scenario testing on state copy |
| `dream_cycle.py` | 307 | Orchestrator: Learning → Reflection → Simulation → CEM |
| `priors.py` | 306 | DreamPriors: weak priors injected into Thinker observations |
| `learning.py` | 211 | Mode 1: skill extraction (trigger → outcome → phi_impact) |
| `sleep_manager.py` | 208 | Dream lifecycle (trigger, run, persist) |
| `reflection.py` | 129 | Mode 2: 100-iteration Thinker in REFLECTIVE mode |
| `awakening.py` | 104 | Post-dream integration report |
| `consolidation.py` | 35 | Profile persistence utilities |
| `harvest.py` | 27 | Data containers for cognitive data |

### `orchestrator/` — Cognitive Loop (1,454 lines)

| File | Lines | Role |
|------|-------|------|
| `cognitive_loop.py` | 1,137 | Persistent daemon: periodic checkpoints, autonomous dreams |
| `message_bus.py` | 117 | Local message passing (asyncio.Queue) |
| `task_queue.py` | 95 | Priority queue for orchestrator tasks |
| `retry.py` | 81 | Exponential backoff (φ-derived factors) |

### `llm_bridge/` — Provider-Agnostic LLM (1,011 lines)

| File | Lines | Role |
|------|-------|------|
| `voice_validator.py` | 557 | Post-LLM enforcement (Thought contract) |
| `prompt_builder.py` | 351 | Injects Ψ state + affect + identity into prompts |
| `bridge.py` | 71 | Abstract LLM interface |
| `providers/anthropic.py` | 66 | Claude API |
| `providers/deepseek.py` | 80 | OpenAI-compatible (DeepSeek) |
| `providers/openai.py` | 73 | GPT API |
| `providers/local.py` | 263 | Ollama, llama.cpp, vLLM, LM Studio |

### `validation/` — Benchmarking & Verdicts (987 lines)

| File | Lines | Role |
|------|-------|------|
| `verdict_tasks.py` | 401 | 7 benchmark tasks (convergence, resilience, coherence) |
| `verdict.py` | 220 | 5-criteria validation protocol (VALIDATED / DECORATIVE) |
| `benchmark_harness.py` | 154 | Isolated runner for validation tasks |
| `comparator.py` | 120 | Statistical comparison (effect size, regression) |
| `sandbox.py` | 59 | Isolated execution environment |

### `safety/` — Rollback & Kill Switch (961 lines)

| File | Lines | Role |
|------|-------|------|
| `snapshot_manager.py` | 288 | Tar + metadata JSON, configurable retention |
| `rate_limiter.py` | 150 | Token bucket rate limiting |
| `kill_switch.py` | 133 | Emergency stop (sentinel file) |
| `safe_action.py` | 123 | Snapshot before → rollback on error |
| `watchdog.py` | 121 | Auto-stop after consecutive degradations |
| `kill_auth.py` | 110 | Scrypt password hashing |

### `core/` — Configuration & Orchestration (871 lines)

| File | Lines | Role |
|------|-------|------|
| `luna.py` | 468 | LunaEngine: orchestrator, Φ scoring, identity preservation |
| `config.py` | 397 | TOML → typed dataclasses (16 sections) |

### `identity/` — Founding Documents (817 lines)

| File | Lines | Role |
|------|-------|------|
| `recovery.py` | 220 | Minimal bootstrap when identity corrupted |
| `bundle.py` | 173 | Cryptographic anchor (SHA256 verified against ledger) |
| `ledger.py` | 149 | Append-only JSONL identity events |
| `bootstrap.py` | 140 | Load founding episodes into EpisodicMemory |
| `context.py` | 114 | Cognitive presence of identity in prompts |

### `heartbeat/` — Phi-Modulated Pulse (758 lines)

| File | Lines | Role |
|------|-------|------|
| `heartbeat.py` | 267 | Background async pulse |
| `vitals.py` | 178 | Health snapshot linked to Ψ |
| `monitor.py` | 175 | Anomaly detection over vital signs |
| `rhythm.py` | 116 | φ-modulated intervals |

### `metrics/` — Code Analysis (740 lines)

| File | Lines | Role |
|------|-------|------|
| `collector.py` | 175 | Orchestrates runners by language |
| `cache.py` | 165 | Hash-based invalidation |
| `radon_runner.py` | 160 | Python cyclomatic/cognitive complexity |
| `ast_runner.py` | 159 | Python AST analysis |
| `normalizer.py` | 155 | Raw → 7 canonical [0,1] metrics |
| `coverage_py_runner.py` | 142 | Python branch coverage |
| `tracker.py` | 121 | Provenance tracking |
| `base_runner.py` | 101 | Abstract interface for analysis tools |

### `cli/` — Typer Commands (709 lines)

12 commands: `start`, `status`, `heartbeat`, `dream`, `fingerprint`, `memory`, `score`, `validate`, `dashboard`, `rollback`, `kill`, `evolve`.

### `memory/` — Fractal Memory (692 lines)

| File | Lines | Role |
|------|-------|------|
| `memory_manager.py` | 383 | Fractal adapter (filesystem JSON, hierarchical levels) |
| `cycle_store.py` | 300 | CycleRecord persistence (JSONL append-only, zstd compression) |

### `observability/` — Audit & Monitoring (681 lines)

| File | Lines | Role |
|------|-------|------|
| `alerting.py` | 266 | Local webhook notifications |
| `audit_trail.py` | 163 | Append-only JSONL event log |
| `redis_store.py` | 134 | Graceful degradation if Redis absent |
| `prometheus_exporter.py` | 98 | Text-format metrics for scraping |

### `api/` — FastAPI REST (645 lines)

10 route modules: consciousness, dashboard, dream, fingerprint, health, heartbeat, memory, metrics, safety. Middleware: auth (bearer token), rate_limit (token bucket). Port 8618.

### `autonomy/` — Reversible Auto-Apply (531 lines)

| File | Lines | Role |
|------|-------|------|
| `window.py` | 518 | Phase A (ghost eval) + Phase B (snapshot → smoke test → rollback/commit) |

### `fingerprint/` — HMAC-SHA256 Identity (422 lines)

| File | Lines | Role |
|------|-------|------|
| `generator.py` | 177 | HMAC-SHA256 on cognitive state |
| `ledger.py` | 124 | Append-only JSONL storage |
| `notarize.py` | 57 | Timestamp verification |
| `watermark.py` | 50 | Subtle marking in generated code |

### `maintenance/` — Epoch Reset (321 lines)

| File | Lines | Role |
|------|-------|------|
| `epoch_reset.py` | 321 | Archive contaminated stats, start clean era |

### `phi_engine/` — Re-exports (62 lines)

Thin wrappers re-exporting from `luna_common.phi_engine`.

---

## III. Test Suite (35,585 lines)

120 test files across root + `integration/` + `oracle/`.

### Key test files

| File | Lines | Coverage |
|------|-------|----------|
| `test_thinker.py` | 844 | Reasoning engine, observations, interoception |
| `test_v35_integration.py` | 706 | Full v3.5 stack end-to-end |
| `test_voice_validator.py` | 613 | LLM output enforcement |
| `test_session.py` | ~600 | ChatSession orchestration |
| `test_dream_priors.py` | ~400 | Dream wiring (50 tests) |
| `test_psi0_adaptive.py` | ~300 | Two-layer identity (23 tests) |
| `test_oracle_crossvalidation.py` | 500 | Oracle cross-validation (L2b, L3, L4) |
| `test_verdict.py` | 188 | Validation protocol |
| `test_autonomy_window.py` | ~300 | Ghost eval + auto-apply (31 tests) |

### Integration tests

| File | Coverage |
|------|----------|
| `integration/test_cognitive_cycle.py` | Cognitive loop end-to-end |
| `integration/test_dream_cognitive.py` | Dream ↔ chat interaction |
| `integration/test_persistence_gaps.py` | Memory persistence edge cases |
| `integration/test_docker_integration.py` | Docker (skipped — WSL2 native) |

### Oracle reference

| File | Role |
|------|------|
| `oracle/expected_values.json` | Expected constants (v5.3 Ψ₀ updated) |
| `oracle/luna_sim_v3.py` | Historical 4-agent simulator (vestige) |

---

## IV. Simulations (5,750 lines)

| File | Lines | Role |
|------|-------|------|
| `dream_impact.py` | 1,364 | Dream effect A/B/C + convergence 150c + multi-dream 5×30c |
| `generate_figures.py` | 1,042 | Publication-quality plots for docs |
| `equilibrium_identity_sim.py` | 982 | Two-layer Ψ₀ equilibrium analysis |
| `asymmetric_kappa_sim.py` | 851 | κ asymmetry exploration (v5.3) |
| `single_agent_validation.py` | 881 | Single-agent convergence validation |
| `simulation.py` | 630 | Base simulation framework |

---

## V. Dashboard — React 18 + TypeScript

Port 3618, proxy → API 8618. 10 panels:

| Panel | What it shows |
|-------|---------------|
| `PsiRadar` | Ψ vector (4D radar chart) |
| `PhiGauge` | Φ_IIT gauge |
| `PhaseTimeline` | Phase progression (BROKEN → EXCELLENT) |
| `AffectPanel` | PAD space + mood trajectory |
| `PhiHistory` | Φ_IIT time series |
| `IdentityPanel` | Identity context + Ψ₀ bundle |
| `CycleTimeline` | Cycle history |
| `RewardPanel` | J-score and dominance rank |
| `DreamPanel` | Sleep cycle status |
| `AutonomyPanel` | Auto-apply candidates + rollbacks |

---

## VI. Configuration

### `luna.toml` — 16 sections

```
[luna]              Agent name, version, data_dir
[consciousness]     Checkpoint file path
[memory]            Fractal levels, limits
[observability]     Logging, Redis, alerts
[heartbeat]         Pulse interval, fingerprint
[llm]               Provider, model, API key
[orchestrator]      Autonomy level
[dream]             Inactivity threshold, duration
[chat]              History limit, memory search
[metrics]           Language-specific runners
[fingerprint]       Secret, ledger, watermark
[safety]            Snapshots, rate limits, watchdog
[identity]          Ledger, founding docs
[api]               Host, port, auth, rate limit
[cognitive_loop]    Tick interval, autosave freq
[pipeline]          Autonomy: supervised / autonomous
```

### `pyproject.toml` — Dependencies

```
luna-common >= 5.3.0
numpy >= 1.24
typer >= 0.9
fastapi >= 0.100
httpx >= 0.26
```

---

## VII. Architecture Principles

### State Equation (v5.1)

```
iΓ^t ∂_t Ψ + iΓ^x ∂_x Ψ + iΓ^c ∂_c Ψ − φ·M·Ψ + κ(Ψ₀ − Ψ) = 0
```

- **Ψ** ∈ Δ³ : [Perception, Reflexion, Integration, Expression]
- **Ψ₀** = `psi0_core + INV_PHI3 × psi0_adaptive` (two-layer identity)
- **M** : φ-adaptive mass matrix (EMA rate tracks Φ_IIT)
- **Γ** : antisymmetric exchange + symmetric dissipation (spectrally normalized)
- **κ** = φ² = 2.618 (identity anchoring, asymmetric when γ > 0)
- **τ** = φ = 1.618 (softmax temperature)
- **dt** = 1/φ = 0.618 (time step)

### Cognitive Pipeline

```
Stimulus → Thinker._observe() → Thought → Reactor.react() → info_deltas → evolve()
                                    ↑                                          |
                              DreamPriors                                      ↓
                         (weak observations)                             Ψ_new on Δ³
```

### Identity Anchoring

```
LUNA:           Ψ₀ = (0.260, 0.322, 0.250, 0.168)  — Reflexion dominant
SAYOHMY:        Ψ₀ = (0.150, 0.150, 0.200, 0.500)  — Expression dominant
SENTINEL:       Ψ₀ = (0.500, 0.200, 0.200, 0.100)  — Perception dominant
TESTENGINEER:   Ψ₀ = (0.150, 0.200, 0.500, 0.150)  — Integration dominant
```

### Validation Protocol (5 criteria, all φ-derived)

| # | Criterion | Pass condition |
|---|-----------|----------------|
| 1 | Performance | delta > 0 |
| 2 | No catastrophic regression | worst delta > −1/φ³ |
| 3 | Coherence | Φ > 0.618 for ≥ 80% of steps |
| 4 | Adaptability | > 50% categories improve |
| 5 | Effect size | Σ(gains) / Σ(\|all deltas\|) > 1/φ |

**Result: VALIDATED 5/5, +45.8%**

### Dream v3.5 → Weak Priors

Dreams produce data that persists as weak priors in Thinker observations:

| Source | Max confidence | vs primary stimulus |
|--------|---------------|-------------------|
| Skill prior | 0.034 | 9% |
| Sim risk | 0.069 | 18% |
| Sim opportunity | 0.090 | 24% |
| Reflection need | 0.034 | 9% |

Linear decay over 50 cycles. 24h wall-clock hard-kill.

---

## VIII. Key Version History

| Version | Date | Milestone |
|---------|------|-----------|
| v3.5.0 | Feb 2026 | Thinker + Reactor + Evaluator + CausalGraph + Dream v2 |
| v3.5.1 | Feb 2026 | Reactor coupling + security audit (16 fixes) |
| v3.5.2 | Mar 2026 | VoiceValidator + EpisodicMemory + Initiative + Watcher |
| v5.0 | Mar 2026 | Unified consciousness (6 phases A→F) |
| v5.1 | Mar 2026 | Single-agent convergence + EndogenousSource |
| v5.2 | Mar 2026 | Emotional sovereignty (AffectEngine sole source) |
| v5.3 | Mar 2026 | Identity rebalance + cognitive interoception + dream wiring |

---

## IX. File Tree (top level)

```
~/LUNA/
├── luna/                    Engine (26,481 lines, 150 files)
│   ├── consciousness/       Cognitive engine (7,492 lines)
│   ├── chat/                Human interface (2,829 lines)
│   ├── dream/               Nocturnal consolidation (2,599 lines)
│   ├── orchestrator/        Cognitive loop (1,454 lines)
│   ├── llm_bridge/          LLM abstraction (1,011 lines)
│   ├── validation/          Benchmarks (987 lines)
│   ├── safety/              Kill switch & rollback (961 lines)
│   ├── core/                Config & engine (871 lines)
│   ├── identity/            Founding documents (817 lines)
│   ├── heartbeat/           Phi-modulated pulse (758 lines)
│   ├── metrics/             Code analysis (740 lines)
│   ├── cli/                 12 Typer commands (709 lines)
│   ├── memory/              Fractal memory (692 lines)
│   ├── observability/       Audit & monitoring (681 lines)
│   ├── api/                 FastAPI REST (645 lines)
│   ├── autonomy/            Auto-apply (531 lines)
│   ├── fingerprint/         HMAC-SHA256 (422 lines)
│   ├── maintenance/         Epoch reset (321 lines)
│   └── phi_engine/          Re-exports (62 lines)
├── tests/                   Test suite (35,585 lines, 120 files)
├── simulations/             Simulation experiments (5,750 lines)
├── dashboard/               React 18 + TS (port 3618)
├── docs/                    Architecture & design documents
├── doc/images/              Legacy images
├── luna.toml                Runtime configuration
├── pyproject.toml           Build & dependencies
├── requirements.txt         Python dependencies
└── README.md                User documentation

~/luna_common/
├── luna_common/             Shared library (2,836 lines, 21 files)
│   ├── constants.py         All φ-derived constants
│   ├── consciousness/       Evolution math (840 lines)
│   ├── phi_engine/          Quality scoring (884 lines)
│   └── schemas/             Pydantic contracts (971 lines)
├── pyproject.toml           Build & dependencies
└── README.md                Foundation documentation
```
