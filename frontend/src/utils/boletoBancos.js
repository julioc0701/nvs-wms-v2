// Mapping código FEBRABAN → nome curto do banco.
export const BANCOS = {
  '001': 'Banco do Brasil',
  '033': 'Santander',
  '041': 'Banrisul',
  '077': 'Inter',
  '104': 'Caixa',
  '237': 'Bradesco',
  '260': 'Nu Pagamentos',
  '341': 'Itaú',
  '422': 'Safra',
  '748': 'Sicredi',
  '756': 'Sicoob',
}

export function nomeBanco(codigo) {
  return BANCOS[codigo] || `Banco ${codigo}`
}

// Classes Tailwind literais — purge da Tailwind exige strings completas.
export function urgenciaVencimento(vencimentoISO) {
  const hoje = new Date()
  hoje.setHours(0, 0, 0, 0)
  const venc = new Date(vencimentoISO + 'T00:00:00')
  const diffDias = Math.floor((venc - hoje) / 86400000)
  if (diffDias < 0) return { nivel: 'vencido', label: `Vencido há ${-diffDias}d`, classes: 'bg-red-100 text-red-700' }
  if (diffDias === 0) return { nivel: 'hoje', label: 'Vence hoje', classes: 'bg-red-100 text-red-700' }
  if (diffDias <= 3) return { nivel: 'urgente', label: `${diffDias}d`, classes: 'bg-orange-100 text-orange-700' }
  if (diffDias <= 7) return { nivel: 'proximo', label: `${diffDias}d`, classes: 'bg-yellow-100 text-yellow-700' }
  return { nivel: 'ok', label: `${diffDias}d`, classes: 'bg-green-100 text-green-700' }
}
