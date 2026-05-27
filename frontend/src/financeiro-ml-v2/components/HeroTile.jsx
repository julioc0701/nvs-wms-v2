import { Area, AreaChart, ResponsiveContainer } from 'recharts'
import { formatBRL, formatPct } from '../utils'

// Placeholder de dados de evolução temporal. Em v2 inicial, usamos a MC global
// repetida (sem série diária). Quando aggregator expor série, troca aqui.
const buildSeries = (mcTotal, points = 14) => {
  if (!mcTotal) return Array(points).fill({ v: 0 })
  return Array.from({ length: points }, (_, i) => ({
    v: mcTotal * (0.85 + 0.3 * Math.sin(i / 2)),
  }))
}

export function HeroTile({ cards }) {
  const mcTotal = cards?.mc_total ?? 0
  const mcPct = cards?.mc_pct_global ?? 0
  const series = buildSeries(mcTotal)

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
        Margem de Contribuição
      </div>

      <div className="fmlv2-mono text-[42px] font-bold leading-none tracking-tight mt-2">
        {formatBRL(mcTotal)}
      </div>

      <div className="flex items-baseline gap-3 mt-2">
        <div
          className="fmlv2-mono text-[22px] font-semibold"
          style={{ color: 'var(--fmlv2-accent-light)' }}
        >
          {formatPct(mcPct)}
        </div>
        <div className="text-[10px] opacity-70">margem média no período</div>
      </div>

      <div className="flex-1 mt-3 min-h-[60px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={series} margin={{ top: 5, right: 0, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="fmlv2HeroGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#6FE8A5" stopOpacity={0.5} />
                <stop offset="100%" stopColor="#6FE8A5" stopOpacity={0} />
              </linearGradient>
            </defs>
            <Area
              type="monotone"
              dataKey="v"
              stroke="#6FE8A5"
              strokeWidth={2}
              fill="url(#fmlv2HeroGrad)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
