// Luna Dashboard — CC-BY-NC-4.0 — (c) Varden
// https://creativecommons.org/licenses/by-nc/4.0/
import { motion } from 'framer-motion'

interface Props {
  value: number  // phi_iit (Gaussian MI, unbounded but typically [0, φ])
  phase: string
  emergentPhi: number          // convergent emergent phi value
  emergentPhiPrecision: number // number of correct decimals
  bootstrapping: boolean       // true if still bootstrapping
}

const PHI_TARGET = 1.618034

const SIZE = 160
const STROKE = 10
const RADIUS = (SIZE - STROKE) / 2
const CIRCUMFERENCE = 2 * Math.PI * RADIUS
const ARC_OFFSET = CIRCUMFERENCE * 0.25 // start from top

function phaseColor(phase: string): string {
  switch (phase) {
    case 'BROKEN': return '#ef4444'
    case 'FRAGILE': return '#f97316'
    case 'FUNCTIONAL': return '#53a8b6'
    case 'SOLID': return '#10b981'
    case 'EXCELLENT': return '#f5a623'
    default: return '#533483'
  }
}

export function PhiGauge({ value, phase, emergentPhi, emergentPhiPrecision, bootstrapping }: Props) {
  const progress = Math.min(Math.max(value / PHI_TARGET, 0), 1)
  const dashLength = progress * CIRCUMFERENCE * 0.75 // 270° arc
  const color = phaseColor(phase)

  return (
    <div className="relative flex flex-col items-center">
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
        <defs>
          <linearGradient id="phi-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={color} stopOpacity="0.3" />
            <stop offset="100%" stopColor={color} stopOpacity="1" />
          </linearGradient>
          <filter id="phi-glow">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Background arc */}
        <circle
          cx={SIZE / 2} cy={SIZE / 2} r={RADIUS}
          fill="none"
          stroke="#1e1e4a"
          strokeWidth={STROKE}
          strokeLinecap="round"
          strokeDasharray={`${CIRCUMFERENCE * 0.75} ${CIRCUMFERENCE}`}
          strokeDashoffset={-ARC_OFFSET}
          transform={`rotate(135 ${SIZE / 2} ${SIZE / 2})`}
        />

        {/* Progress arc */}
        <motion.circle
          cx={SIZE / 2} cy={SIZE / 2} r={RADIUS}
          fill="none"
          stroke="url(#phi-grad)"
          strokeWidth={STROKE}
          strokeLinecap="round"
          filter="url(#phi-glow)"
          strokeDasharray={`${dashLength} ${CIRCUMFERENCE}`}
          strokeDashoffset={-ARC_OFFSET}
          transform={`rotate(135 ${SIZE / 2} ${SIZE / 2})`}
          initial={false}
          animate={{ strokeDasharray: `${dashLength} ${CIRCUMFERENCE}` }}
          transition={{ duration: 1.5, ease: 'easeInOut' }}
        />

        {/* Center value */}
        <text
          x={SIZE / 2} y={SIZE / 2 - 8}
          textAnchor="middle"
          dominantBaseline="central"
          className="fill-luna-text font-mono text-[28px] font-light"
        >
          {value.toFixed(3)}
        </text>
        <text
          x={SIZE / 2} y={SIZE / 2 + 16}
          textAnchor="middle"
          className="fill-luna-text-dim text-[10px] font-medium uppercase tracking-widest"
        >
          {'\u03A6'}_IIT
        </text>
      </svg>

      <div className={`phase-badge phase-${phase} -mt-2`}>
        {phase}
      </div>

      {/* Emergent Phi */}
      <motion.div
        className="mt-3 text-center"
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.3 }}
      >
        <div className="text-[10px] uppercase tracking-widest text-luna-text-muted mb-1">
          {'\u03C6'} {'\u00E9'}mergent
        </div>
        <motion.div
          className="font-mono text-lg"
          style={{ color: '#FFD700' }}
          key={emergentPhi.toFixed(Math.min(emergentPhiPrecision, 10))}
          initial={{ opacity: 0.6 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4 }}
        >
          {emergentPhi.toFixed(Math.min(emergentPhiPrecision, 10))}
        </motion.div>
        <div className="text-[9px] text-luna-text-dim mt-0.5">
          {bootstrapping
            ? 'bootstrap...'
            : `${emergentPhiPrecision} d\u00E9cimales`
          }
        </div>
      </motion.div>
    </div>
  )
}
