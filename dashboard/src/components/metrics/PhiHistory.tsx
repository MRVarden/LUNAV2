// Luna Dashboard — CC-BY-NC-4.0 — (c) Varden
// https://creativecommons.org/licenses/by-nc/4.0/
import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer, ReferenceLine, Line } from 'recharts'
import type { CycleRecord } from '../../api/types'

interface Props {
  cycles: CycleRecord[]
}

const PHI_TARGET = 1.618034

export function PhiHistory({ cycles }: Props) {
  const data = cycles.map((c, i) => ({
    idx: i,
    phi: c.phi_iit_after,
    phi_before: c.phi_iit_before,
    emergent_phi: c.emergent_phi ?? null,
    time: new Date(c.timestamp).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
  }))

  // Compute Y-axis upper bound: auto-scale to fit all data + phi target
  const allValues = data.flatMap(d => [d.phi, d.emergent_phi].filter((v): v is number => v != null))
  const maxVal = Math.max(PHI_TARGET, ...allValues)
  const yMax = Math.ceil(maxVal * 10) / 10 // round up to nearest 0.1

  return (
    <ResponsiveContainer width="100%" height={140}>
      <AreaChart data={data} margin={{ top: 5, right: 5, bottom: 0, left: -20 }}>
        <defs>
          <linearGradient id="phiGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#7c5cbf" stopOpacity={0.4} />
            <stop offset="100%" stopColor="#7c5cbf" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="time"
          tick={{ fontSize: 9, fill: '#4a4a70' }}
          axisLine={false}
          tickLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          domain={[0, yMax]}
          tick={{ fontSize: 9, fill: '#4a4a70' }}
          axisLine={false}
          tickLine={false}
          tickCount={4}
        />
        {/* Reference line at golden ratio target */}
        <ReferenceLine
          y={PHI_TARGET}
          stroke="#FFD700"
          strokeDasharray="2 4"
          opacity={0.5}
          label={{ value: '\u03C6', position: 'right', fill: '#FFD700', fontSize: 9 }}
        />
        {/* Legacy reference line at inverse phi */}
        <ReferenceLine y={0.618} stroke="#533483" strokeDasharray="3 3" opacity={0.3} />
        {/* Phi IIT area */}
        <Area
          type="monotone"
          dataKey="phi"
          stroke="#7c5cbf"
          strokeWidth={2}
          fill="url(#phiGrad)"
          dot={false}
          animationDuration={1000}
        />
        {/* Emergent phi line */}
        <Line
          type="monotone"
          dataKey="emergent_phi"
          stroke="#FFD700"
          strokeWidth={1.5}
          strokeDasharray="4 3"
          dot={false}
          connectNulls
          animationDuration={1000}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
