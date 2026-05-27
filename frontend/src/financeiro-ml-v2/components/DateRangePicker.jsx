import { useState, useRef, useEffect, useMemo, useCallback } from 'react'
import { DayPicker } from 'react-day-picker'
import { ptBR } from 'date-fns/locale'
import { Calendar } from 'lucide-react'
import 'react-day-picker/style.css'

const parseDate = (s) => (s ? new Date(s + 'T00:00:00') : undefined)
const toISO     = (d) => (d ? d.toISOString().slice(0, 10) : '')
const fmtBR     = (s) => (s ? new Date(s + 'T00:00:00').toLocaleDateString('pt-BR') : '—')

function SingleDatePicker({ label, value, onChange }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  // Memoiza a Date — sem isso, DayPicker recebe nova instância a cada render
  // e dispara loop interno (effect deps comparam por identidade).
  const selected = useMemo(() => parseDate(value), [value])

  const handleSelect = useCallback((d) => {
    onChange(toISO(d))
    setOpen(false)
  }, [onChange])

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div ref={ref} className="relative flex items-center gap-1.5">
      <span className="text-xs font-medium text-[var(--fmlv2-muted)]">{label}</span>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 text-xs px-2 py-1 bg-white border border-[var(--fmlv2-border)] rounded text-[var(--fmlv2-text)] min-w-[110px] hover:border-[var(--fmlv2-border-strong)]"
      >
        <Calendar size={12} className="text-[var(--fmlv2-muted)]" />
        {fmtBR(value)}
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 z-30 bg-white border border-[var(--fmlv2-border)] rounded-lg shadow-xl p-2 fmlv2-daypicker">
          <DayPicker
            mode="single"
            selected={selected}
            onSelect={handleSelect}
            locale={ptBR}
            showOutsideDays
          />
        </div>
      )}
    </div>
  )
}

export function DateRangePicker({ dataInicio, dataFim, onChange }) {
  // Memoiza callbacks pra estabilizar identidade
  const onDeChange = useCallback(
    (v) => onChange({ data_inicio: v, data_fim: dataFim }),
    [onChange, dataFim]
  )
  const onAteChange = useCallback(
    (v) => onChange({ data_inicio: dataInicio, data_fim: v }),
    [onChange, dataInicio]
  )

  return (
    <div className="flex items-center gap-2 bg-[var(--fmlv2-surface)] border border-[var(--fmlv2-border)] rounded-md px-2 py-1">
      <SingleDatePicker label="De"  value={dataInicio} onChange={onDeChange} />
      <span className="text-[var(--fmlv2-muted)] text-xs">→</span>
      <SingleDatePicker label="Até" value={dataFim}    onChange={onAteChange} />
    </div>
  )
}
