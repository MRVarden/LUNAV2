// Luna Dashboard — CC-BY-NC-4.0 — (c) Varden
// https://creativecommons.org/licenses/by-nc/4.0/
import { useState, useEffect, useCallback, useRef } from 'react'
import type { DashboardState, RewardVector } from '../api/types'
import { fetchSnapshot, getMockState } from '../api/client'

const POLL_INTERVAL = 2000

function clamp(v: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, v))
}

/**
 * Derive a live RewardVector client-side from consciousness state.
 * Mirrors Evaluator.evaluate_live() logic (same thresholds, same mapping).
 * Used when the API doesn't provide live_reward (disconnected or evaluator not init).
 */
function deriveLiveReward(
  psi: [number, number, number, number],
  psi0: [number, number, number, number],
  phiIit: number,
  arousal?: number,
): RewardVector {
  const minPsi = Math.min(...psi)
  // JS divergence approximation (L2-based for speed)
  const drift = Math.sqrt(
    psi.reduce((sum, v, i) => sum + (v - psi0[i]) ** 2, 0)
  )

  const HARDCODED_PHI = 1.618

  // Same formulas as Evaluator._compute_*
  const ci = 1.0
  const acRaw = minPsi / 0.25
  const ac = clamp(2.0 * acRaw - 1.0, -1, 1)

  const rest = 0.33
  let ic: number
  if (phiIit <= rest) ic = -1.0
  else if (phiIit >= HARDCODED_PHI) ic = 1.0
  else ic = clamp(2.0 * (phiIit - rest) / (HARDCODED_PHI - rest) - 1.0, -1, 1)

  const jsApprox = drift * drift * 0.5 // rough JS ~ 0.5 * L2^2 for simplex
  const jsNorm = jsApprox / Math.LN2
  const ids = clamp(1.0 - 2.0 * jsNorm, -1, 1)

  const ar = arousal != null
    ? clamp(2.0 * (1.0 - Math.abs(arousal - 0.3) - Math.max(0, 0)) - 1.0, -1, 1)
    : 0.0

  return {
    components: [
      { name: 'constitution_integrity', value: ci, raw: ci },
      { name: 'anti_collapse', value: ac, raw: acRaw },
      { name: 'integration_coherence', value: ic, raw: phiIit },
      { name: 'identity_stability', value: ids, raw: ids },
      { name: 'reflection_depth', value: 0, raw: 0 },
      { name: 'perception_acuity', value: 0, raw: 0 },
      { name: 'expression_fidelity', value: 1, raw: 1 },
      { name: 'affect_regulation', value: ar, raw: ar },
      { name: 'memory_vitality', value: 0, raw: 0 },
    ],
    dominance_rank: 0,
    delta_j: 0,
  }
}

export function useLunaState(): DashboardState & { refreshing: boolean } {
  const mock = useRef(getMockState())
  const [state, setState] = useState<DashboardState>(mock.current)
  const [refreshing, setRefreshing] = useState(false)

  const poll = useCallback(async () => {
    setRefreshing(true)
    try {
      // Try snapshot endpoint first (single call)
      const snapshot = await fetchSnapshot()
      if (snapshot && snapshot.consciousness) {
        setState(prev => {
          const cs = snapshot.consciousness!
          // Use API live_reward if provided, else derive client-side
          const apiLive = (snapshot as any).live_reward ?? null
          const liveReward = apiLive ?? deriveLiveReward(
            cs.psi, cs.psi0, cs.phi_iit,
            snapshot.affect?.affect?.arousal,
          )
          return {
            consciousness: cs,
            affect: snapshot.affect ?? prev.affect,
            identity: (snapshot as any).identity ?? prev.identity,
            autonomy: (snapshot as any).autonomy ?? prev.autonomy,
            episodic: (snapshot as any).episodic ?? prev.episodic,
            initiative: (snapshot as any).initiative ?? prev.initiative,
            causal_graph: (snapshot as any).causal_graph ?? prev.causal_graph,
            endogenous: (snapshot as any).endogenous ?? prev.endogenous,
            cycles: (snapshot as any).cycles?.length ? (snapshot as any).cycles : prev.cycles,
            dream: snapshot.dream ?? prev.dream,
            live_reward: liveReward,
            circuit_breaker: (snapshot as any).circuit_breaker ?? prev.circuit_breaker,
            synthesis: (snapshot as any).synthesis ?? prev.synthesis,
            connected: true,
            last_update: Date.now(),
          }
        })
      } else {
        // Fallback: animate mock data for visual life
        setState(prev => {
          const t = Date.now() / 1000
          const psi = prev.consciousness?.psi ?? [0.260, 0.322, 0.250, 0.168]
          const psi0 = prev.consciousness?.psi0 ?? [0.260, 0.322, 0.250, 0.168]
          const drift = 0.004
          const newPsi: [number, number, number, number] = [
            psi[0] + Math.sin(t * 0.7) * drift,
            psi[1] + Math.sin(t * 0.5 + 1) * drift,
            psi[2] + Math.sin(t * 0.6 + 2) * drift,
            psi[3] + Math.sin(t * 0.8 + 3) * drift,
          ]
          const sum = newPsi.reduce((a, b) => a + b, 0)
          const normalized: [number, number, number, number] = [
            newPsi[0] / sum, newPsi[1] / sum, newPsi[2] / sum, newPsi[3] / sum,
          ]
          const phiIit = 0.55 + Math.sin(t * 0.3) * 0.1
          const arousal = 0.4 + Math.sin(t * 0.15 + 1) * 0.1

          return {
            ...prev,
            consciousness: prev.consciousness ? {
              ...prev.consciousness,
              psi: normalized,
              phi_iit: phiIit,
            } : prev.consciousness,
            affect: prev.affect ? {
              ...prev.affect,
              affect: {
                valence: 0.3 + Math.sin(t * 0.2) * 0.15,
                arousal,
                dominance: 0.6 + Math.sin(t * 0.1 + 2) * 0.08,
              },
            } : prev.affect,
            live_reward: deriveLiveReward(normalized, psi0 as [number, number, number, number], phiIit, arousal),
            episodic: prev.episodic,
            initiative: prev.initiative,
            endogenous: prev.endogenous,
            causal_graph: prev.causal_graph,
            connected: false,
            last_update: Date.now(),
          }
        })
      }
    } catch {
      setState(prev => ({ ...prev, connected: false }))
    }
    setRefreshing(false)
  }, [])

  useEffect(() => {
    poll()
    const id = setInterval(poll, POLL_INTERVAL)
    return () => clearInterval(id)
  }, [poll])

  return { ...state, refreshing }
}
