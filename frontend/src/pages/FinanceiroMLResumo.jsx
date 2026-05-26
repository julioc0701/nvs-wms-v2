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
      <h1 className="text-xl font-bold">Análise Financeira — Mercado Livre</h1>

      {/* CARDS sempre visíveis no topo (zeros se nada buscado) */}
      <KPICards cards={resultado?.cards} />

      {/* Erro de busca */}
      {mutation.isError && (
        <div className="border border-red-300 bg-red-50 p-3 rounded text-red-700 text-sm">
          Erro: {String(mutation.error)}
        </div>
      )}

      {/* FILTROS + GRÁFICO lado a lado */}
      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <FiltrosBar onBuscar={mutation.mutate} loading={mutation.isPending} />
        </div>
        <div>
          <PizzaChart pizza={resultado?.pizza} />
        </div>
      </div>

      {/* AÇÕES + TABELA — só aparecem após primeira busca */}
      {resultado && (
        <>
          <div className="flex gap-2">
            <button onClick={() => exportar('excel')} className="px-3 py-1.5 text-sm border rounded hover:bg-slate-50">📊 Exportar Excel</button>
            <button onClick={() => exportar('csv')} className="px-3 py-1.5 text-sm border rounded hover:bg-slate-50">📄 Exportar CSV</button>
            {resultado.sync_report && (
              <div className="ml-auto text-xs text-slate-500 self-center">
                Sync: {resultado.sync_report.dias_sincronizados} dia(s) atualizados · {resultado.sync_report.total_orders} pedidos
              </div>
            )}
          </div>
          <TabelaVendas
            data={resultado.tabela}
            pagination={resultado.pagination}
            onPageChange={onPage}
            onPageSizeChange={onPageSize}
          />
        </>
      )}

      {/* Estado vazio inicial */}
      {!resultado && !mutation.isPending && (
        <div className="text-center text-slate-400 text-sm py-8 border-2 border-dashed rounded-lg">
          Selecione um período e clique <strong>Buscar</strong> pra carregar os dados.
        </div>
      )}
    </div>
  )
}
