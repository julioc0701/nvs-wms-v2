export const formatBRL = (v) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v ?? 0)

export const formatPct = (v, digits = 1) =>
  `${(Number(v) || 0).toFixed(digits).replace('.', ',')}%`

export const formatInt = (v) =>
  new Intl.NumberFormat('pt-BR').format(v ?? 0)

// Calcula delta % entre valor atual e anterior. Retorna null se sem comparação.
export const deltaCalc = (current, previous) => {
  if (previous == null || previous === 0) return null
  return ((current - previous) / Math.abs(previous)) * 100
}
