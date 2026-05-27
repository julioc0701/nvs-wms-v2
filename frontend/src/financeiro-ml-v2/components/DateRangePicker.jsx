import { useState } from 'react'

const today = () => new Date().toISOString().slice(0, 10)
const daysAgo = (n) => {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}
const firstOfMonth = () => {
  const d = new Date()
  d.setDate(1)
  return d.toISOString().slice(0, 10)
}

const PRESETS = [
  { key: 'hoje',  label: 'Hoje',    from: today,                  to: today },
  { key: '7d',    label: '7 dias',  from: () => daysAgo(6),       to: today },
  { key: '30d',   label: '30 dias', from: () => daysAgo(29),      to: today },
  { key: 'mes',   label: 'Mês',     from: firstOfMonth,           to: today },
]

export function DateRangePicker({ active, onChange }) {
  const [showCustom, setShowCustom] = useState(active === 'custom')
  const [customFrom, setCustomFrom] = useState(today())
  const [customTo, setCustomTo] = useState(today())

  const choose = (preset) => {
    setShowCustom(false)
    onChange({
      preset: preset.key,
      data_inicio: preset.from(),
      data_fim: preset.to(),
    })
  }

  const applyCustom = () => {
    onChange({
      preset: 'custom',
      data_inicio: customFrom,
      data_fim: customTo,
    })
  }

  return (
    <div className="flex items-center gap-1">
      <div className="flex border border-[var(--fmlv2-border)] rounded-md overflow-hidden bg-[var(--fmlv2-surface)]">
        {PRESETS.map((p) => (
          <button
            key={p.key}
            onClick={() => choose(p)}
            className={`px-3 py-1.5 text-xs font-medium border-r border-[var(--fmlv2-border)] last:border-r-0 transition-colors ${
              active === p.key
                ? 'bg-[var(--fmlv2-ink-2)] text-white'
                : 'text-[var(--fmlv2-muted)] hover:bg-white'
            }`}
          >
            {p.label}
          </button>
        ))}
        <button
          onClick={() => setShowCustom((v) => !v)}
          className={`px-3 py-1.5 text-xs font-medium transition-colors ${
            active === 'custom'
              ? 'bg-[var(--fmlv2-ink-2)] text-white'
              : 'text-[var(--fmlv2-muted)] hover:bg-white'
          }`}
        >
          Custom
        </button>
      </div>

      {showCustom && (
        <div className="flex items-center gap-1 ml-2 p-1.5 bg-white border border-[var(--fmlv2-border)] rounded-md">
          <input
            type="date"
            value={customFrom}
            onChange={(e) => setCustomFrom(e.target.value)}
            className="text-xs px-2 py-1 border border-[var(--fmlv2-border)] rounded"
          />
          <span className="text-[var(--fmlv2-muted)] text-xs">→</span>
          <input
            type="date"
            value={customTo}
            onChange={(e) => setCustomTo(e.target.value)}
            className="text-xs px-2 py-1 border border-[var(--fmlv2-border)] rounded"
          />
          <button
            onClick={applyCustom}
            className="text-xs px-2 py-1 bg-[var(--fmlv2-ink-2)] text-white rounded hover:opacity-90"
          >
            OK
          </button>
        </div>
      )}
    </div>
  )
}
