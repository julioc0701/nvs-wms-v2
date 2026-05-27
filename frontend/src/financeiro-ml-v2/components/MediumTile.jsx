import { Line, LineChart, ResponsiveContainer } from 'recharts'
import { formatBRL } from '../utils'

const buildSpark = (total, points = 12) => {
  if (!total) return Array(points).fill({ v: 0 })
  return Array.from({ length: points }, (_, i) => ({
    v: total * (0.7 + 0.4 * Math.sin(i / 1.5) + 0.05 * i),
  }))
}

/**
 * tag:    label superior pequena
 * value:  big number
 * breakdown: array de { label, value } pra mostrar embaixo (max 2 itens)
 */
export function MediumTile({ tag, value, breakdown, sparkValue }) {
  const series = buildSpark(sparkValue ?? value)
  return (
    <div
      className="rounded-xl p-4 bg-white border border-[var(--fmlv2-border)] flex flex-col"
      style={{ gridColumn: 'span 3', gridRow: 'span 2' }}
    >
      <div className="text-[9px] uppercase tracking-[0.08em] text-[var(--fmlv2-muted)] font-semibold">
        {tag}
      </div>

      <div className="fmlv2-mono text-[24px] font-bold text-[var(--fmlv2-ink)] mt-1 tracking-tight">
        {formatBRL(value)}
      </div>

      {breakdown && (
        <div className="flex gap-3.5 mt-1.5 text-[11px]">
          {breakdown.map((b, i) => (
            <div key={i} className="text-[var(--fmlv2-muted)]">
              {b.label}{' '}
              <span className="fmlv2-mono font-semibold text-[var(--fmlv2-ink-2)]">
                {formatBRL(b.value)}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="flex-1 mt-2 min-h-[30px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={series} margin={{ top: 5, right: 0, left: 0, bottom: 0 }}>
            <Line
              type="monotone"
              dataKey="v"
              stroke="#1B4F8A"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
