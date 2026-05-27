import { formatBRL } from '../utils'

/**
 * tag:        label superior pequena (uppercase)
 * value:      número (BRL ou unidades; passar prop `int` se for inteiro)
 * sub:        linha de texto pequena abaixo (opcional)
 * delta:      objeto { value, label } com cor automática (positivo=verde, negativo=vermelho)
 * int:        se true, formata como inteiro com Intl
 */
export function SmallTile({ tag, value, sub, delta, int = false }) {
  return (
    <div
      className="rounded-xl p-3 bg-white border border-[var(--fmlv2-border)] flex flex-col justify-center"
      style={{ gridColumn: 'span 1', gridRow: 'span 1' }}
    >
      <div className="text-[9px] uppercase tracking-[0.05em] text-[var(--fmlv2-muted)] font-semibold">
        {tag}
      </div>

      <div className="fmlv2-mono text-base font-bold text-[var(--fmlv2-ink)] mt-0.5 tracking-tight">
        {int
          ? new Intl.NumberFormat('pt-BR').format(value ?? 0)
          : formatBRL(value)}
      </div>

      {sub && (
        <div className="text-[10px] text-[var(--fmlv2-muted)] mt-0.5">{sub}</div>
      )}

      {delta && (
        <div
          className="text-[10px] mt-1 font-medium"
          style={{
            color: delta.value >= 0
              ? 'var(--fmlv2-pos)'
              : 'var(--fmlv2-neg)',
          }}
        >
          {delta.value >= 0 ? '↑' : '↓'} {delta.label}
        </div>
      )}
    </div>
  )
}
