/**
 * 2 inputs date "De" → "Até". Gatilho único da busca.
 * onChange dispara quando qualquer um dos campos muda.
 */
export function DateRangePicker({ dataInicio, dataFim, onChange }) {
  const set = (key, value) => {
    onChange({ data_inicio: key === 'data_inicio' ? value : dataInicio,
               data_fim:    key === 'data_fim'    ? value : dataFim })
  }

  return (
    <div className="flex items-center gap-2 bg-[var(--fmlv2-surface)] border border-[var(--fmlv2-border)] rounded-md px-2 py-1">
      <label className="flex items-center gap-1.5 text-xs text-[var(--fmlv2-muted)]">
        <span className="font-medium">De</span>
        <input
          type="date"
          value={dataInicio || ''}
          onChange={(e) => set('data_inicio', e.target.value)}
          className="text-xs px-2 py-1 bg-white border border-[var(--fmlv2-border)] rounded text-[var(--fmlv2-text)]"
        />
      </label>
      <span className="text-[var(--fmlv2-muted)] text-xs">→</span>
      <label className="flex items-center gap-1.5 text-xs text-[var(--fmlv2-muted)]">
        <span className="font-medium">Até</span>
        <input
          type="date"
          value={dataFim || ''}
          onChange={(e) => set('data_fim', e.target.value)}
          className="text-xs px-2 py-1 bg-white border border-[var(--fmlv2-border)] rounded text-[var(--fmlv2-text)]"
        />
      </label>
    </div>
  )
}
