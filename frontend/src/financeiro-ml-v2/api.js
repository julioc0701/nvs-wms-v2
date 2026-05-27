const BASE = '/api/financeiro-ml'

function authHeaders(extra = {}) {
  const operator = JSON.parse(localStorage.getItem('operator') || 'null')
  return {
    ...extra,
    ...(operator?.id ? { 'X-Operator-Id': String(operator.id) } : {}),
  }
}

async function jsonOrThrow(res) {
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText} ${text}`)
  }
  return res.json()
}

async function blobOrThrow(res) {
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText} ${text}`)
  }
  return res.blob()
}

export const financeiroMLApi = {
  health: () => fetch(`${BASE}/health`).then(jsonOrThrow),

  getResumo: (filters) =>
    fetch(`${BASE}/resumo`, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(filters),
    }).then(jsonOrThrow),

  listSkus: (q = '') =>
    fetch(`${BASE}/skus?q=${encodeURIComponent(q)}`, {
      headers: authHeaders(),
    }).then(jsonOrThrow),

  putSku: (sku, { custo_unit, imposto_pct }) =>
    fetch(`${BASE}/skus/${encodeURIComponent(sku)}`, {
      method: 'PUT',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ custo_unit, imposto_pct }),
    }).then(jsonOrThrow),

  deleteSku: (sku) =>
    fetch(`${BASE}/skus/${encodeURIComponent(sku)}`, {
      method: 'DELETE',
      headers: authHeaders(),
    }).then(jsonOrThrow),

  importSkusExcel: async (file) => {
    const fd = new FormData()
    fd.append('file', file)
    const res = await fetch(`${BASE}/skus/import-excel`, {
      method: 'POST',
      headers: authHeaders(),
      body: fd,
    })
    return jsonOrThrow(res)
  },

  exportResumo: (filters, formato = 'excel') =>
    fetch(`${BASE}/export?formato=${formato}`, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(filters),
    }).then(blobOrThrow),
}
