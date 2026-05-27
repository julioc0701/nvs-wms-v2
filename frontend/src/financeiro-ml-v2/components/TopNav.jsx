import { DateRangePicker } from './DateRangePicker'

export function TopNav({ totalVendas, activePreset, onPresetChange }) {
  return (
    <div className="flex items-center gap-4 px-4 py-2.5 bg-white border border-[var(--fmlv2-border)] rounded-xl mb-3">
      <div className="flex items-baseline gap-2">
        <h1 className="text-sm font-bold text-[var(--fmlv2-ink)] tracking-tight">
          Análise Financeira
        </h1>
        <span className="text-xs text-[var(--fmlv2-muted)]">
          · Mercado Livre
          {totalVendas != null && (
            <> · <span className="fmlv2-mono">{totalVendas}</span> vendas no período</>
          )}
        </span>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <DateRangePicker active={activePreset} onChange={onPresetChange} />
      </div>
    </div>
  )
}
