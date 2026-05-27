import { Search } from 'lucide-react'
import { DateRangePicker } from './DateRangePicker'

export function TopNav({ totalVendas, dataInicio, dataFim, onDateChange, onBuscar, loading }) {
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
        <DateRangePicker dataInicio={dataInicio} dataFim={dataFim} onChange={onDateChange} />
        <button
          onClick={onBuscar}
          disabled={loading || !dataInicio || !dataFim}
          className="flex items-center gap-1.5 px-4 py-1.5 bg-[var(--fmlv2-ink-2)] text-white text-xs font-semibold rounded-md hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
        >
          <Search size={13} />
          {loading ? 'Buscando…' : 'Buscar'}
        </button>
      </div>
    </div>
  )
}
