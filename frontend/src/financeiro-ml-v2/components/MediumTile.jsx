import { Line, LineChart, ResponsiveContainer } from 'recharts'

const buildSpark = (total, points = 12) => {
  if (!total) return Array(points).fill({ v: 0 })
  return Array.from({ length: points }, (_, i) => ({
    v: total * (0.7 + 0.4 * Math.sin(i / 1.5) + 0.05 * i),
  }))
}

/**
 * tag:          label superior pequena
 * display:      conteúdo do big number (string ou JSX já formatado)
 * displayTone:  'ink' (default) | 'pos' | 'neg' — cor do display
 * subline:      jsx de subtítulo
 * sparkValue:   valor numérico usado pra gerar sparkline (opcional)
 */
export function MediumTile({ tag, display, displayTone = 'ink', subline, sparkValue }) {
  const series = buildSpark(sparkValue ?? 0)
  return (
    <div
      className="rounded-xl p-4 bg-white border border-[var(--fmlv2-border-strong)] flex flex-col"
      style={{ gridColumn: 'span 3', gridRow: 'span 2', boxShadow: '0 2px 8px rgba(10,34,64,0.06)' }}
    >
      <div className="text-[9px] uppercase tracking-[0.08em] text-[var(--fmlv2-muted)] font-semibold">
        {tag}
      </div>

      <div
        className="fmlv2-mono text-[28px] font-bold mt-1 tracking-tight leading-none"
        style={{ color: `var(--fmlv2-${displayTone})` }}
      >
        {display}
      </div>

      {subline && <div className="mt-2">{subline}</div>}

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
