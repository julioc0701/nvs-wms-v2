/**
 * Strip horizontal full-width (6 cols × 1 row) — "ticker" de métricas secundárias.
 * items: [{ label, value (jsx ou string), sub?, tone? }]
 *   tone: 'pos' | 'neg' | 'ink' (default 'ink')
 */
export function StatsStrip({ items }) {
  return (
    <div
      className="rounded-xl bg-white border border-[var(--fmlv2-border)] flex items-stretch divide-x divide-[var(--fmlv2-border)] overflow-hidden"
      style={{ gridColumn: 'span 6', gridRow: 'span 1' }}
    >
      {items.map((it, i) => (
        <div key={i} className="flex-1 px-4 py-3 flex flex-col justify-center min-w-0">
          <div className="text-[9px] uppercase tracking-[0.08em] text-[var(--fmlv2-muted)] font-semibold">
            {it.label}
          </div>
          <div
            className="fmlv2-mono text-[18px] font-bold tracking-tight mt-0.5 truncate"
            style={{ color: `var(--fmlv2-${it.tone || 'ink'})` }}
          >
            {it.value}
          </div>
          {it.sub && (
            <div className="text-[10px] text-[var(--fmlv2-muted)] mt-0.5 truncate">
              {it.sub}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
