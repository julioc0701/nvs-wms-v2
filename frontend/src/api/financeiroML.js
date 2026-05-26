const BASE = '/api/financeiro-ml'

async function jsonOrThrow(res) {
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText} ${text}`)
  }
  return res.json()
}

export const financeiroMLApi = {
  health: () => fetch(`${BASE}/health`).then(jsonOrThrow),

  getResumo: (filters) =>
    fetch(`${BASE}/resumo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(filters),
    }).then(jsonOrThrow),

  listSkus: (q = '') =>
    fetch(`${BASE}/skus?q=${encodeURIComponent(q)}`).then(jsonOrThrow),

  putSku: (sku, { custo_unit, imposto_pct }) =>
    fetch(`${BASE}/skus/${encodeURIComponent(sku)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ custo_unit, imposto_pct }),
    }).then(jsonOrThrow),

  deleteSku: (sku) =>
    fetch(`${BASE}/skus/${encodeURIComponent(sku)}`, { method: 'DELETE' }).then(jsonOrThrow),

  importSkusExcel: async (file) => {
    const fd = new FormData()
    fd.append('file', file)
    const res = await fetch(`${BASE}/skus/import-excel`, { method: 'POST', body: fd })
    return jsonOrThrow(res)
  },

  exportResumo: (filters, formato = 'excel') =>
    fetch(`${BASE}/export?formato=${formato}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(filters),
    }).then((res) => res.blob()),
}
