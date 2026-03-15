// Luna Dashboard — CC-BY-NC-4.0 — (c) Varden
// https://creativecommons.org/licenses/by-nc/4.0/
import { motion } from 'framer-motion'
import type { CycleRecord } from '../../api/types'

interface Props {
  cycles: CycleRecord[]
}

const INTENT_COLORS: Record<string, string> = {
  RESPOND: '#53a8b6',
  DREAM: '#7c5cbf',
  INTROSPECT: '#a855f7',
  ALERT: '#e94560',
}

export function CycleTimeline({ cycles }: Props) {
  const recent = cycles.slice(-16)

  return (
    <div className="flex flex-col gap-2">
      {/* Mini bars */}
      <div className="flex items-end gap-1 h-16">
        {recent.map((cycle, i) => {
          const height = Math.max(cycle.thinker_confidence * 100, 10)
          const color = INTENT_COLORS[cycle.intent] ?? '#533483'
          return (
            <motion.div
              key={cycle.cycle_id}
              className="flex-1 rounded-t relative group cursor-pointer"
              style={{ backgroundColor: color }}
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: `${height}%`, opacity: 0.7 }}
              whileHover={{ opacity: 1 }}
              transition={{ duration: 0.4, delay: i * 0.03 }}
            >
              {/* Tooltip */}
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-10">
                <div className="glass-panel px-2 py-1 text-[9px] whitespace-nowrap">
                  <div className="text-luna-text font-mono">{cycle.intent}</div>
                  <div className="text-luna-text-dim">
                    {'\u03A6'} {cycle.phi_iit_after.toFixed(3)} • {cycle.duration_seconds.toFixed(1)}s
                  </div>
                  {cycle.emergent_phi != null && (
                    <div style={{ color: '#FFD700' }} className="font-mono">
                      {'\u03C6'}e {cycle.emergent_phi.toFixed(4)}
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )
        })}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-3 justify-center">
        {Object.entries(INTENT_COLORS).map(([intent, color]) => (
          <div key={intent} className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-sm" style={{ backgroundColor: color }} />
            <span className="text-[8px] text-luna-text-muted">{intent}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
