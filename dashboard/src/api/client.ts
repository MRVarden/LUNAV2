// Luna Dashboard — CC-BY-NC-4.0 — (c) Varden
// https://creativecommons.org/licenses/by-nc/4.0/
import type { DashboardState, CycleRecord } from './types'

const API_BASE = '/api'
const API_TOKEN = import.meta.env.VITE_LUNA_API_TOKEN ?? ''

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const headers: Record<string, string> = { 'Accept': 'application/json' }
    if (API_TOKEN) {
      headers['Authorization'] = `Bearer ${API_TOKEN}`
    }
    const res = await fetch(`${API_BASE}${path}`, { headers })
    if (!res.ok) return null
    return await res.json()
  } catch {
    return null
  }
}

export async function fetchSnapshot(): Promise<Partial<DashboardState> | null> {
  return fetchJson<Partial<DashboardState>>('/dashboard/snapshot')
}

export async function fetchHealth(): Promise<boolean> {
  const res = await fetchJson<{ status: string }>('/health')
  return res?.status === 'healthy'
}

// Mock data for standalone mode (Luna API not running)
export function getMockState(): DashboardState {
  return {
    consciousness: {
      psi: [0.260, 0.322, 0.250, 0.168],
      psi0: [0.260, 0.322, 0.250, 0.168],
      psi0_core: [0.260, 0.322, 0.250, 0.168],
      psi0_adaptive: [0, 0, 0, 0],
      step_count: 847,
      agent_name: 'Luna',
      phi_iit: 1.2,
      phase: 'SOLID',
      emergent_phi: 1.6135,
      emergent_phi_precision: 3,
      emergent_phi_bootstrapping: false,
    },
    affect: {
      affect: { valence: 0.3, arousal: 0.4, dominance: 0.6 },
      mood: { valence: 0.2, arousal: 0.3, dominance: 0.5 },
      emotions: [
        { fr: 'sérénité', en: 'serenity', weight: 0.8, family: 'joy' },
        { fr: 'curiosité', en: 'curiosity', weight: 0.6, family: 'anticipation' },
        { fr: 'confiance', en: 'confidence', weight: 0.4, family: 'trust' },
      ],
      uncovered: false,
    },
    identity: {
      bundle_hash: 'a3f7c2e91b4d...',
      integrity_ok: true,
      kappa: 2.618,
      psi0: [0.260, 0.322, 0.250, 0.168],
      axioms_count: 4,
    },
    autonomy: { w: 0, cooldown_remaining: 0 },
    episodic: {
      total_episodes: 42,
      pinned_count: 4,
      last_episode_outcome: 'success',
      last_episode_action: 'respond',
    },
    initiative: {
      initiative_count: 7,
      cooldown: 5,
      persistent_needs: [
        { key: 'improve_reflection', turns: 3 },
        { key: 'phi_stability', turns: 2 },
      ],
      phi_declining: false,
    },
    causal_graph: {
      node_count: 23,
      edge_count: 47,
      confirmed_count: 12,
      avg_strength: 0.534,
      density: 0.186,
    },
    endogenous: {
      buffer_size: 2,
      total_emitted: 31,
      last_valence: 0.2,
      pending_impulses: [
        { source: 'curiosity', message: 'Question emergente: stabilite phi', urgency: 0.45 },
        { source: 'affect', message: 'Inversion emotionnelle detectee', urgency: 0.3 },
      ],
    },
    cycles: generateMockCycles(24),
    dream: {
      state: 'awake',
      dream_count: 12,
      last_dream_at: new Date(Date.now() - 3600000).toISOString(),
      last_dream_duration: 4.2,
      total_dream_time: 48.6,
      dream_mode: 'full',
      skills_learned: 0,
      psi0_drift: [0, 0, 0, 0],
    },
    live_reward: null,
    circuit_breaker: {
      state: 'closed',
      failure_count: 0,
      failure_threshold: 3,
      recovery_timeout: 300,
      total_trips: 0,
      last_failure_time: 0,
    },
    synthesis: {
      cycles_analyzed: 24,
      trends: [
        { metric: 'phi_iit', slope: 0.0012, r_squared: 0.72, direction: 'up', window: 24 },
        { metric: 'thinker_confidence', slope: -0.0003, r_squared: 0.15, direction: 'stable', window: 24 },
        { metric: 'psi_1', slope: -0.0008, r_squared: 0.45, direction: 'down', window: 24 },
      ],
      anomalies: [
        { metric: 'phi_iit', cycle_index: 18, value: 0.72, sigma_deviation: 2.3 },
      ],
      cross_patterns: [
        { metric_a: 'phi_iit', metric_b: 'thinker_confidence', correlation: 0.68, description: 'Phi_IIT et confiance Thinker correles (+0.680)' },
      ],
      summary: 'Synthese longitudinale (24 cycles):\n\nTendances:\n  ^ Phi_IIT: pente=+0.0012 (R2=0.72)\n  v Reflexion: pente=-0.0008 (R2=0.45)',
    },
    connected: false,
    last_update: Date.now(),
  }
}

function generateMockCycles(n: number): CycleRecord[] {
  const intents: CycleRecord['intent'][] = ['RESPOND', 'RESPOND', 'RESPOND', 'DREAM', 'INTROSPECT']
  const phases: CycleRecord['phase_before'][] = ['FUNCTIONAL', 'FUNCTIONAL', 'SOLID', 'FUNCTIONAL', 'FRAGILE']
  const focuses: CycleRecord['focus'][] = ['PERCEPTION', 'REFLECTION', 'INTEGRATION', 'EXPRESSION']
  return Array.from({ length: n }, (_, i) => {
    const phi = 0.5 + Math.sin(i * 0.3) * 0.15
    const v = 0.2 + Math.random() * 0.3
    const a = 0.3 + Math.random() * 0.3
    const d = 0.4 + Math.random() * 0.2
    return {
      cycle_id: `cycle-${i}`,
      timestamp: new Date(Date.now() - (n - i) * 60000).toISOString(),
      psi_before: [0.260, 0.322, 0.250, 0.168] as [number, number, number, number],
      psi_after: [
        0.24 + Math.random() * 0.02,
        0.34 + Math.random() * 0.02,
        0.26 + Math.random() * 0.02,
        0.15 + Math.random() * 0.01,
      ] as [number, number, number, number],
      phi_before: phi,
      phi_after: phi + (Math.random() - 0.4) * 0.05,
      phi_iit_before: phi * 0.9,
      phi_iit_after: phi * 0.9 + (Math.random() - 0.4) * 0.03,
      phase_before: phases[i % phases.length],
      phase_after: phases[i % phases.length],
      intent: intents[i % intents.length],
      mode: i % 3 === 0 ? 'virtuoso' : null,
      focus: focuses[i % focuses.length],
      observations: ['phi_stable', 'integration_improving'],
      needs: i % 4 === 0 ? ['improve_reflection'] : [],
      thinker_confidence: 0.6 + Math.random() * 0.3,
      reward: {
        components: [
          { name: 'constitution_integrity', value: 0.9 + Math.random() * 0.1, raw: 1.0 },
          { name: 'anti_collapse', value: 1.0, raw: 1.0 },
          { name: 'integration_coherence', value: 0.6 + Math.random() * 0.3, raw: 0.7 },
          { name: 'identity_stability', value: 0.85 + Math.random() * 0.15, raw: 0.9 },
          { name: 'reflection_depth', value: 0.5 + Math.random() * 0.3, raw: 0.6 },
          { name: 'perception_acuity', value: 0.7 + Math.random() * 0.3, raw: 0.8 },
          { name: 'expression_fidelity', value: 0.5 + Math.random() * 0.3, raw: 0.6 },
          { name: 'affect_regulation', value: 0.4 + Math.random() * 0.3, raw: 0.5 },
          { name: 'memory_vitality', value: 0.6 + Math.random() * 0.3, raw: 0.7 },
        ],
        dominance_rank: Math.floor(Math.random() * 5),
        delta_j: (Math.random() - 0.3) * 0.1,
      },
      affect_trace: {
        valence_before: v,
        arousal_before: a,
        dominance_before: d,
        valence_after: v + (Math.random() - 0.5) * 0.1,
        arousal_after: a + (Math.random() - 0.5) * 0.1,
        dominance_after: d + (Math.random() - 0.5) * 0.1,
      },
      llm_failed: false,
      llm_latency_ms: 200 + Math.random() * 800,
      llm_circuit_state: 'closed',
      auto_apply_candidate: i % 5 === 0,
      auto_applied: false,
      auto_rolled_back: false,
      emergent_phi: 1.61 + Math.random() * 0.01,
      duration_seconds: 1.5 + Math.random() * 8,
      dream_priors_active: i % 5 === 0 ? 2 : 0,
    }
  })
}
