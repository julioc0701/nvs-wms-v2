import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { financeiroMLApi } from '../api/financeiroML'
import { FiltrosBar } from '../components/financeiro-ml/FiltrosBar'
import { KPICards } from '../components/financeiro-ml/KPICards'
import { PizzaChart } from '../components/financeiro-ml/PizzaChart'
import { TabelaVendas } from '../components/financeiro-ml/TabelaVendas'

export default function FinanceiroMLResumo() {
  const [resultado, setResultado] = useState(null)
  const [filtrosAtuais, setFiltrosAtuais] = useState(null)

  const mutation = useMutation({
    mutationFn: (filtros) => financeiroMLApi.getResumo(filtros),
    onSuccess: (data, filtros) => {
      setResultado(data)
      setFiltrosAtuais(filtros)
    },
  })

  const onPage = (page) => mutation.mutate({ ...filtrosAtuais, page })
  const onPageSize = (page_size) => mutation.mutate({ ...filtrosAtuais, page: 1, page_size })

  const exportar = async (formato) => {
    if (!filtrosAtuais) return
    const blob = await financeiroMLApi.exportResumo(filtrosAtuais, formato)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `resumo.${formato === 'csv' ? 'csv' : 'xlsx'}`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="p-4 space-y-4">
      <h1 className="text-xl font-bold">Resumo Financeiro Mercado Livre</h1>
      <FiltrosBar onBuscar={mutation.mutate} loading={mutation.isPending} />
      {mutation.isError && (
        <div className="border border-red-300 bg-red-50 p-3 rounded text-red-700 text-sm">
          Erro: {String(mutation.error)}
        </div>
      )}
      {resultado && (
        <>
          <div className="grid lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2"><KPICards cards={resultado.cards} /></div>
            <PizzaChart pizza={resultado.pizza} />
          </div>
          <div className="flex gap-2">
            <button onClick={() => exportar('excel')} className="px-3 py-1.5 text-sm border rounded">Exportar Excel</button>
            <button onClick={() => exportar('csv')} className="px-3 py-1.5 text-sm border rounded">Exportar CSV</button>
          </div>
          <TabelaVendas
            data={resultado.tabela}
            pagination={resultado.pagination}
            onPageChange={onPage}
            onPageSizeChange={onPageSize}
          />
        </>
      )}
    </div>
  )
}
