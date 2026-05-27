import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'
import { formatPct } from '../utils'

const COLORS = [
  'var(--fmlv2-ink)',
  'var(--fmlv2-ink-2)',
  'var(--fmlv2-ink-3)',
  '#94BDE0',
  'var(--fmlv2-pos)',
]

// Pizza shape do backend (aggregator.py:214-222):
// array de { label: string, valor: number, pct: number }
// labels: "Custo", "Imposto", "Tarifa", "Frete", "MC"
export function DonutTile({ pizza }) {
  const items = pizza || []
  const data = items.map((it) => ({ name: it.label, value: Number(it.valor) || 0 }))
  const mcItem = items.find((i) => i.label === 'MC') || { pct: 0 }

  return (
    <div
      className="rounded-xl p-3 bg-white border border-[var(--fmlv2-border)] flex gap-3 items-center"
      style={{ gridColumn: 'span 2', gridRow: 'span 2' }}
    >
      <div className="relative shrink-0" style={{ width: 90, height: 90 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data.length ? data : [{ name: 'empty', value: 1 }]}
              dataKey="value"
              cx="50%"
              cy="50%"
              innerRadius={26}
              outerRadius={42}
              startAngle={90}
              endAngle={-270}
              isAnimationActive={false}
            >
              {(data.length ? data : [{}]).map((_, i) => (
                <Cell key={i} fill={data.length ? COLORS[i] : '#E5E7EB'} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <div className="fmlv2-mono text-[13px] font-bold text-[var(--fmlv2-ink)] leading-none">
            {formatPct(Number(mcItem.pct) || 0, 1)}
          </div>
          <div className="text-[7px] uppercase text-[var(--fmlv2-muted)] mt-0.5">MC</div>
        </div>
      </div>

      <div className="flex-1 min-w-0">
        <div className="text-[9px] uppercase tracking-[0.08em] text-[var(--fmlv2-muted)] font-semibold mb-1">
          Composição
        </div>
        {items.length === 0 && (
          <div className="text-[10px] text-[var(--fmlv2-muted)] italic">Sem dados no período</div>
        )}
        {items.map((it, i) => (
          <div key={i} className="flex items-center gap-1.5 py-0.5">
            <div
              className="shrink-0 rounded-sm"
              style={{ width: 7, height: 7, background: COLORS[i] }}
            />
            <div className="flex-1 text-[10px] truncate text-[var(--fmlv2-text)]">
              {it.label}
            </div>
            <div className="fmlv2-mono text-[9px] text-[var(--fmlv2-muted)]">
              {formatPct(Number(it.pct) || 0, 1)}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
