// Luna Dashboard — CC-BY-NC-4.0 — (c) Varden
// https://creativecommons.org/licenses/by-nc/4.0/
import { Brain, Heart, GitBranch, Award, Moon, Zap, Shield, Radio, BarChart3, TrendingUp } from 'lucide-react'
import { Header } from './components/layout/Header'
import { GlassCard } from './components/layout/GlassCard'
import { PsiRadar } from './components/consciousness/PsiRadar'
import { PhiGauge } from './components/consciousness/PhiGauge'
import { PhaseTimeline } from './components/consciousness/PhaseTimeline'
import { AffectPanel } from './components/affect/AffectPanel'
import { RewardPanel } from './components/metrics/RewardPanel'
import { PhiHistory } from './components/metrics/PhiHistory'
import { CycleTimeline } from './components/metrics/CycleTimeline'
import { CognitiveFlow } from './components/consciousness/CognitiveFlow'
import { DreamPanel } from './components/dream/DreamPanel'
import { IdentityPanel } from './components/identity/IdentityPanel'
import { AutonomyPanel } from './components/autonomy/AutonomyPanel'
import { SynthesisPanel } from './components/metrics/SynthesisPanel'
import { useLunaState } from './hooks/useLunaState'

export default function App() {
  const state = useLunaState()
  const cs = state.consciousness
  const lastCycle = state.cycles[state.cycles.length - 1] ?? null

  return (
    <div className="min-h-screen bg-luna-bg bg-grid">
      <Header
        connected={state.connected}
        phase={cs?.phase ?? 'BROKEN'}
        stepCount={cs?.step_count ?? 0}
        llmState={state.circuit_breaker?.state ?? 'closed'}
      />

      <main className="p-4 max-w-[1600px] mx-auto">
        {/* Phase timeline */}
        <div className="mb-4 px-2">
          <PhaseTimeline current={cs?.phase ?? 'BROKEN'} />
        </div>

        {/* Main grid */}
        <div className="grid grid-cols-12 gap-4">

          {/* ── Row 1: Conscience + Phi + Affect ── */}

          <GlassCard
            title="Conscience"
            subtitle="Vecteur Ψ — Simplex 4D"
            icon={<Brain className="w-4 h-4" />}
            className="col-span-4 row-span-2"
            glow
          >
            {cs && (
              <div className="flex flex-col items-center gap-2">
                <PsiRadar psi={cs.psi} psi0={cs.psi0} />
                <div className="flex items-center gap-3 text-[9px] text-luna-text-muted">
                  <span className="flex items-center gap-1">
                    <div className="w-3 h-0.5 bg-luna-primary rounded" />
                    Ψ actuel
                  </span>
                  <span className="flex items-center gap-1">
                    <div className="w-3 h-0.5 rounded" style={{ borderBottom: '1px dashed #53a8b6' }} />
                    Ψ₀ identité
                  </span>
                </div>
              </div>
            )}
          </GlassCard>

          <GlassCard
            title="Intégration"
            subtitle="Φ_IIT — Information Intégrée"
            icon={<Zap className="w-4 h-4" />}
            className="col-span-3"
          >
            {cs && (
              <PhiGauge
                value={cs.phi_iit}
                phase={cs.phase ?? 'BROKEN'}
                emergentPhi={cs.emergent_phi ?? 1.5}
                emergentPhiPrecision={cs.emergent_phi_precision ?? 0}
                bootstrapping={cs.emergent_phi_bootstrapping ?? true}
              />
            )}
          </GlassCard>

          <GlassCard
            title="Affect"
            subtitle="Espace PAD — Émotions bilingues"
            icon={<Heart className="w-4 h-4" />}
            className="col-span-5"
          >
            {state.affect && <AffectPanel affect={state.affect} />}
          </GlassCard>

          {/* ── Row 2: Phi History + Identity + Autonomy ── */}

          <GlassCard
            title="Trajectoire Φ"
            subtitle="Historique Phi_IIT par cycle"
            className="col-span-4"
          >
            <PhiHistory cycles={state.cycles} />
          </GlassCard>

          <GlassCard
            title="Identité"
            subtitle="Bundle constitutionnel — Article 12"
            icon={<Shield className="w-4 h-4" />}
            className="col-span-4"
          >
            <IdentityPanel identity={state.identity} episodic={state.episodic} />
          </GlassCard>

          {/* ── Row 3: Cognitive Flow + Reward + Autonomy ── */}

          <GlassCard
            title="Flux Cognitif"
            subtitle="Perception → Réflexion → Intégration → Expression"
            icon={<GitBranch className="w-4 h-4" />}
            className="col-span-8"
          >
            <CognitiveFlow lastCycle={lastCycle} psi={cs?.psi ?? null} causalGraph={state.causal_graph} />
          </GlassCard>

          <GlassCard
            title="Autonomie"
            subtitle="Fenêtre W — Ghost & Auto-apply"
            icon={<Radio className="w-4 h-4" />}
            className="col-span-4 row-span-2"
          >
            <AutonomyPanel
              autonomy={state.autonomy}
              cycles={state.cycles}
              psi={cs?.psi ?? null}
              psi0={cs?.psi0 ?? null}
              phiIit={cs?.phi_iit}
              initiative={state.initiative}
              endogenous={state.endogenous}
            />
          </GlassCard>

          {/* ── Row 4: Reward + Dream + Cycles ── */}

          <GlassCard
            title="Évaluation"
            subtitle="RewardVector — J Components (fixed weights)"
            icon={<Award className="w-4 h-4" />}
            className="col-span-4"
          >
            <RewardPanel
              reward={lastCycle?.reward ?? null}
              liveReward={state.live_reward}
            />
          </GlassCard>

          <GlassCard
            title="Rêve"
            subtitle="DreamCycle — Consolidation & CEM"
            icon={<Moon className="w-4 h-4" />}
            className="col-span-4"
          >
            <DreamPanel dream={state.dream} />
          </GlassCard>

          {/* ── Row 5: Synthesis ── */}

          <GlassCard
            title="Synthese"
            subtitle="Retrospective longitudinale — tendances & anomalies"
            icon={<TrendingUp className="w-4 h-4" />}
            className="col-span-12 md:col-span-8"
          >
            <SynthesisPanel synthesis={state.synthesis} />
          </GlassCard>

          {/* ── Row 6: Cycle Timeline full width ── */}

          <GlassCard
            title="Cycles Récents"
            subtitle="Confiance Thinker par cycle — coloré par intent"
            icon={<BarChart3 className="w-4 h-4" />}
            className="col-span-12"
          >
            <CycleTimeline cycles={state.cycles} />
          </GlassCard>

        </div>

        {/* Footer */}
        <div className="mt-6 flex items-center justify-center gap-4 py-4">
          <span className="text-[9px] text-luna-text-muted font-mono">Φ = 1.618033988749895</span>

          {/* CC BY-NC 4.0 badge */}
          <a
            href="https://creativecommons.org/licenses/by-nc/4.0/"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-stretch rounded overflow-hidden text-[10px] font-semibold leading-none border border-[#a22] hover:opacity-90 transition-opacity"
          >
            <span className="flex items-center gap-1 bg-[#3c1111] text-[#f08080] px-2 py-1">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor">
                <circle cx="12" cy="12" r="11" stroke="currentColor" strokeWidth="1.5" fill="none" />
                <text x="12" y="16" textAnchor="middle" fontSize="12" fontWeight="bold" fill="currentColor">C</text>
              </svg>
              CC BY-NC 4.0
            </span>
            <span className="flex items-center bg-[#a22] text-white px-2 py-1">
              Varden
            </span>
          </a>

          <span className="text-[9px] text-luna-text-muted">Luna Consciousness Engine v6.0.0</span>
        </div>
      </main>
    </div>
  )
}
