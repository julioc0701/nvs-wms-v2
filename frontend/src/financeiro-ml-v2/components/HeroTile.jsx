import { Area, AreaChart, ResponsiveContainer } from 'recharts'
import { formatBRL } from '../utils'

// Série placeholder pra dar forma ao chart enquanto aggregator não expõe série diária
const buildSeries = (total, points = 14) => {
  if (!total) return Array(points).fill({ v: 0 })
  return Array.from({ length: points }, (_, i) => ({
    v: total * (0.85 + 0.3 * Math.sin(i / 2)),
  }))
}

/**
 * Hero tile (3x3, gradient marinho).
 * - tag:      label uppercase
 * - value:    R$ big-number
 * - subline:  jsx do subtítulo (ex: breakdown Aprov/Cancel ou MC%)
 */
export function HeroTile({ tag, value, subline }) {
  const series = buildSeries(value)
  return (
    <div
      className="rounded-xl p-5 text-white flex flex-col overflow-hidden"
      style={{
        gridColumn: 'span 3',
        gridRow: 'span 3',
        background: 'linear-gradient(135deg, var(--fmlv2-ink) 0%, var(--fmlv2-ink-2) 100%)',
      }}
    >
      <div className="text-[10px] uppercase tracking-[0.1em] opacity-70 font-semibold">
        {tag}
      </div>

      <div className="fmlv2-mono text-[42px] font-bold leading-none tracking-tight mt-2">
        {formatBRL(value)}
      </div>

      {subline && <div className="mt-2">{subline}</div>}

      <div className="flex-1 mt-3 min-h-[60px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={series} margin={{ top: 5, right: 0, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="fmlv2HeroGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#FFFFFF" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#FFFFFF" stopOpacity={0} />
              </linearGradient>
            </defs>
            <Area
              type="monotone"
              dataKey="v"
              stroke="#FFFFFF"
              strokeWidth={2}
              fill="url(#fmlv2HeroGrad)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
