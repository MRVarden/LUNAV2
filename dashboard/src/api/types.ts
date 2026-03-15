// Luna Dashboard — CC-BY-NC-4.0 — (c) Varden
// https://creativecommons.org/licenses/by-nc/4.0/
// Luna Consciousness Engine — TypeScript data contracts
//
// RULE: Python (schemas) = truth, TS = mirror.
// Every interface here mirrors a Python dataclass/BaseModel or
// the exact shape serialized by /dashboard/snapshot.
//
// Sources:
//   ConsciousnessSnapshot  → dashboard.py composite (state.py + engine.get_status)
//   AffectState / Mood     → luna/consciousness/affect.py
//   EmotionEntry           → luna/consciousness/emotion_repertoire.py (EmotionWord)
//   IdentitySnapshot       → luna/identity/context.py (IdentityContext)
//   AutonomySnapshot       → luna/autonomy/window.py (AutonomyWindow @property)
//   CycleRecord            → luna_common/schemas/cycle.py (CycleRecord BaseModel)
//   RewardVector/Component → luna_common/schemas/cycle.py
//   DreamStatus            → luna/dream/sleep_manager.py (SleepStatus)
//   Intent / Phase         → luna_common/schemas/cycle.py (VALID_INTENTS, Literal)

// ── Consciousness ──────────────────────────────────────────────
// Composite: fields from ConsciousnessState + engine.get_status()

export interface ConsciousnessSnapshot {
  psi: [number, number, number, number]          // np.ndarray shape(4), simplex
  psi0: [number, number, number, number]         // identity anchor
  psi0_core: [number, number, number, number]    // immutable identity (from IdentityContext)
  psi0_adaptive: [number, number, number, number] // dream overlay (psi0 - psi0_core drift)
  step_count: number                             // int, total evolution steps
  agent_name: string                             // str
  phi_iit: number                                // float [0, 1]
  phase: Phase                                   // consciousness phase (from Phi_IIT)
  emergent_phi: number                           // float, current emergent phi value (~1.618)
  emergent_phi_precision: number                 // int, number of correct decimals
  emergent_phi_bootstrapping: boolean            // bool, true if still bootstrapping
}

// ── Affect ─────────────────────────────────────────────────────
// Mirrors: affect.py AffectState dataclass

export interface AffectState {
  valence: number     // float [-1, +1]
  arousal: number     // float [0, 1]
  dominance: number   // float [0, 1]
}

// Mirrors: emotion_repertoire.py EmotionWord (subset used by interpret())
export interface EmotionEntry {
  fr: string          // French name
  en: string          // English name
  weight: number      // float [0, 1], matching distance
  family: string      // "joy"|"fear"|"anger"|"sadness"|"surprise"|"trust"|"anticipation"|"complex"
}

// Composite: AffectEngine state serialized by dashboard.py
export interface AffectSnapshot {
  affect: AffectState            // current instant affect (AffectState)
  mood: AffectState              // slow EMA (Mood dataclass, same 3 fields)
  emotions: EmotionEntry[]       // top emotions from interpret()
  uncovered: boolean             // UnnamedZoneTracker active
}

// ── Identity ───────────────────────────────────────────────────
// Mirrors: identity/context.py IdentityContext (frozen dataclass)

export interface IdentitySnapshot {
  bundle_hash: string       // str, truncated to 12 chars + "..."
  integrity_ok: boolean     // bool, hash matches ledger
  kappa: number             // float, phi² = 2.618
  psi0: number[]            // tuple[float, ...], identity anchor
  axioms_count: number      // int, len(axioms)
}

// ── Autonomy ───────────────────────────────────────────────────
// Mirrors: autonomy/window.py AutonomyWindow @property w, @property cooldown_remaining

export interface AutonomySnapshot {
  w: number                    // int [0, 10], current autonomy level (0 during cooldown)
  cooldown_remaining: number   // int, cycles until cooldown lifts
}

// ── Enums ──────────────────────────────────────────────────────
// Mirrors: luna_common/schemas/cycle.py VALID_INTENTS, Literal phase

export type Intent = 'RESPOND' | 'DREAM' | 'INTROSPECT' | 'ALERT'
export type Mode = 'virtuoso' | 'architect' | 'mentor' | 'reviewer' | 'debugger'
export type Phase = 'BROKEN' | 'FRAGILE' | 'FUNCTIONAL' | 'SOLID' | 'EXCELLENT'
export type SleepState = 'awake' | 'entering_sleep' | 'sleeping' | 'waking_up'

// ── Reward ─────────────────────────────────────────────────────
// Mirrors: luna_common/schemas/cycle.py RewardComponent, RewardVector

export interface RewardComponent {
  name: string       // one of REWARD_COMPONENT_NAMES
  value: number      // float [-1, +1], normalized
  raw: number        // float, pre-normalization
}

export interface RewardVector {
  components: RewardComponent[]  // max 9 (v5.0 cognitive)
  dominance_rank: number         // int [0, ∞), 0=best
  delta_j: number                // float, J(t) - J(t-1)
}

// ── Cycle Record ───────────────────────────────────────────────
// Mirrors: luna_common/schemas/cycle.py CycleRecord (subset for dashboard)
// Full Python model has 51 fields; we mirror only what we display.

export interface CycleRecord {
  // Identity
  cycle_id: string                              // str, short UUID
  timestamp: string                             // datetime -> ISO string

  // Internal state
  psi_before: [number, number, number, number]  // tuple[float x4]
  psi_after: [number, number, number, number]
  phi_before: number                            // float [0, 2]
  phi_after: number
  phi_iit_before: number                        // float [0, 1]
  phi_iit_after: number
  phase_before: Phase
  phase_after: Phase

  // Thinker output
  observations: string[]                        // list[str]
  needs: string[]                               // list[str]
  thinker_confidence: number                    // float [0, 1]

  // Decision
  intent: Intent                                // str (VALID_INTENTS)
  mode: Mode | null                             // str | None
  focus: 'PERCEPTION' | 'REFLECTION' | 'INTEGRATION' | 'EXPRESSION'

  // Affect
  affect_trace: {
    valence_before?: number
    arousal_before?: number
    dominance_before?: number
    valence_after?: number
    arousal_after?: number
    dominance_after?: number
  } | null

  // Evaluation
  reward: RewardVector | null                   // RewardVector | None

  // LLM health (v6.0)
  llm_failed: boolean                            // bool
  llm_latency_ms: number                         // float >= 0
  llm_circuit_state: string                      // "closed" | "open" | "half_open"

  // Emergent phi
  emergent_phi?: number | null                  // float | null, convergent phi value

  // Meta
  duration_seconds: number                      // float >= 0
  dream_priors_active: number                   // int >= 0, dream observations injected this cycle

  // Ghost (Phase A)
  auto_apply_candidate: boolean                 // bool
  // Auto-apply (Phase B)
  auto_applied: boolean                         // bool
  auto_rolled_back: boolean                     // bool
}

// ── Dream ──────────────────────────────────────────────────────
// Mirrors: dream/sleep_manager.py SleepStatus dataclass

export interface DreamStatus {
  state: SleepState            // SleepState enum value
  dream_count: number          // int
  last_dream_at: string | null // str | None, ISO timestamp
  last_dream_duration: number  // float, seconds
  total_dream_time: number     // float, cumulative seconds
  // Dream wiring (v5.3)
  dream_mode: string | null    // str | None, current dream mode
  skills_learned: number       // int, total skills from last dream
  psi0_drift: number[]         // cumulative drift per component
}

// ── Episodic Memory ──────────────────────────────────────────
// Mirrors: consciousness/episodic_memory.py EpisodicMemory summary

export interface EpisodicSnapshot {
  total_episodes: number       // int, current count
  pinned_count: number         // int, founding/identity episodes
  last_episode_outcome: string | null  // "success" | "veto" | "failure" | "neutral"
  last_episode_action: string | null   // action_type of most recent
}

// ── Initiative ───────────────────────────────────────────────
// Mirrors: consciousness/initiative.py InitiativeEngine summary

export interface PersistentNeed {
  key: string                  // str, need identifier
  turns: number                // int, how many cycles this need persists
}

export interface InitiativeSnapshot {
  initiative_count: number     // int, total autonomous actions taken
  cooldown: number             // int, remaining cooldown turns
  phi_declining: boolean       // bool, Φ decline detected
  persistent_needs: PersistentNeed[]  // list of persisting needs
}

// ── Endogenous ───────────────────────────────────────────────
// Mirrors: consciousness/endogenous.py EndogenousSource summary

export interface PendingImpulse {
  source: string       // ImpulseSource enum value
  message: string      // truncated to 100 chars
  urgency: number      // float [0, 1]
}

export interface EndogenousSnapshot {
  buffer_size: number           // int, pending impulses
  total_emitted: number         // int, total emitted
  last_valence: number          // float [-1, +1]
  pending_impulses: PendingImpulse[]  // up to 5
}

// ── Causal Graph ─────────────────────────────────────────────
// Mirrors: consciousness/causal_graph.py CausalGraph summary

export interface CausalGraphSnapshot {
  node_count: number        // int
  edge_count: number        // int
  confirmed_count: number   // int (strength > 0.618)
  avg_strength: number      // float [0, 1]
  density: number           // float [0, 1]
}


// ── Circuit Breaker (v6.0) ──────────────────────────────────────
// Mirrors: llm_bridge/circuit_breaker.py CircuitBreaker.to_dict()

export interface CircuitBreakerSnapshot {
  state: 'closed' | 'open' | 'half_open'
  failure_count: number
  failure_threshold: number
  recovery_timeout: number     // seconds
  total_trips: number
  last_failure_time: number    // monotonic seconds (0 = never)
}

// ── Synthesis (v6.0) ────────────────────────────────────────────
// Mirrors: consciousness/synthesis.py TrendLine, Anomaly, CrossPattern, SynthesisReport

export interface TrendSnapshot {
  metric: string
  slope: number
  r_squared: number
  direction: 'up' | 'down' | 'stable'
  window: number
}

export interface AnomalySnapshot {
  metric: string
  cycle_index: number
  value: number
  sigma_deviation: number
}

export interface CrossPatternSnapshot {
  metric_a: string
  metric_b: string
  correlation: number
  description: string
}

export interface SynthesisSnapshot {
  cycles_analyzed: number
  trends: TrendSnapshot[]
  anomalies: AnomalySnapshot[]
  cross_patterns: CrossPatternSnapshot[]
  summary: string
}

// ── Dashboard State ────────────────────────────────────────────
// Shape returned by GET /dashboard/snapshot

export interface DashboardState {
  consciousness: ConsciousnessSnapshot | null
  affect: AffectSnapshot | null
  identity: IdentitySnapshot | null
  autonomy: AutonomySnapshot | null
  episodic: EpisodicSnapshot | null
  initiative: InitiativeSnapshot | null
  causal_graph: CausalGraphSnapshot | null
  endogenous: EndogenousSnapshot | null
  cycles: CycleRecord[]
  dream: DreamStatus | null
  live_reward: RewardVector | null
  circuit_breaker: CircuitBreakerSnapshot | null
  synthesis: SynthesisSnapshot | null
  connected: boolean
  last_update: number     // client-side timestamp (Date.now())
}
