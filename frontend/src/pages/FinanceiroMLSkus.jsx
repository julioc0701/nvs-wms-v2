import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { financeiroMLApi } from '../api/financeiroML'

export default function FinanceiroMLSkus() {
  const [q, setQ] = useState('')
  const [novoSku, setNovoSku] = useState('')
  const qc = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['skus', q],
    queryFn: () => financeiroMLApi.listSkus(q),
  })

  const salvar = useMutation({
    mutationFn: ({ sku, custo_unit, imposto_pct }) =>
      financeiroMLApi.putSku(sku, { custo_unit: String(custo_unit), imposto_pct: String(imposto_pct) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['skus'] }),
  })

  const remover = useMutation({
    mutationFn: (sku) => financeiroMLApi.deleteSku(sku),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['skus'] }),
  })

  const importar = useMutation({
    mutationFn: (file) => financeiroMLApi.importSkusExcel(file),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['skus'] }),
  })

  return (
    <div className="p-4 space-y-4">
      <h1 className="text-xl font-bold">Cadastro SKU — Custo & Imposto</h1>

      <div className="flex gap-2 items-center">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar SKU…"
               className="border rounded px-2 py-1 flex-1" />
        <label className="px-3 py-1.5 border rounded cursor-pointer">
          Importar Excel
          <input type="file" accept=".xlsx" hidden
                 onChange={(e) => e.target.files[0] && importar.mutate(e.target.files[0])} />
        </label>
      </div>

      {importar.data && (
        <div className="text-xs bg-green-50 border border-green-200 p-2 rounded">
          Import: {importar.data.created} criados · {importar.data.updated} atualizados ·
          {importar.data.errors?.length || 0} erros
        </div>
      )}

      <div className="flex gap-2">
        <input value={novoSku} onChange={(e) => setNovoSku(e.target.value)} placeholder="Novo SKU"
               className="border rounded px-2 py-1" />
        <button onClick={() => {
          if (novoSku.trim()) {
            salvar.mutate({ sku: novoSku.trim(), custo_unit: '0', imposto_pct: '0' })
            setNovoSku('')
          }
        }} className="px-3 py-1.5 bg-violet-600 text-white rounded">
          Adicionar
        </button>
      </div>

      <table className="min-w-full border rounded bg-white text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-3 py-2 text-left">SKU</th>
            <th className="px-3 py-2 text-left">Custo Unit. (R$)</th>
            <th className="px-3 py-2 text-left">Imposto (%)</th>
            <th className="px-3 py-2 text-left">Ações</th>
          </tr>
        </thead>
        <tbody>
          {isLoading && <tr><td colSpan="4" className="p-3 text-center">Carregando…</td></tr>}
          {data?.items?.map((row) => (
            <SkuRow key={row.sku} row={row}
                    onSave={(updates) => salvar.mutate({ sku: row.sku, ...updates })}
                    onDelete={() => remover.mutate(row.sku)} />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SkuRow({ row, onSave, onDelete }) {
  const [custo, setCusto] = useState(row.custo_unit)
  const [imposto, setImposto] = useState(row.imposto_pct)
  const dirty = custo !== row.custo_unit || imposto !== row.imposto_pct
  return (
    <tr className="border-t">
      <td className="px-3 py-2 font-mono">{row.sku}</td>
      <td className="px-3 py-2">
        <input value={custo} onChange={(e) => setCusto(e.target.value)} className="w-24 border rounded px-1" />
      </td>
      <td className="px-3 py-2">
        <input value={imposto} onChange={(e) => setImposto(e.target.value)} className="w-20 border rounded px-1" />
      </td>
      <td className="px-3 py-2 flex gap-2">
        <button disabled={!dirty} onClick={() => onSave({ custo_unit: custo, imposto_pct: imposto })}
                className="px-2 py-1 text-xs border rounded disabled:opacity-30">Salvar</button>
        <button onClick={onDelete} className="px-2 py-1 text-xs border rounded text-red-600">Excluir</button>
      </td>
    </tr>
  )
}
