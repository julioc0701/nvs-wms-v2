import { useState, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import '../tokens.css'
import { financeiroMLApi } from '../api'
import { TopNav } from '../components/TopNav'
import { BentoGrid } from '../components/BentoGrid'
import { HeroTile } from '../components/HeroTile'
import { MediumTile } from '../components/MediumTile'
import { SmallTile } from '../components/SmallTile'
import { DonutTile } from '../components/DonutTile'
import { FilterChips } from '../components/FilterChips'
import { DataTable } from '../components/DataTable'

const today = () => new Date().toISOString().slice(0, 10)
const daysAgo = (n) => {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}

const INITIAL_FILTERS = {
  data_inicio: daysAgo(6),
  data_fim:    today(),
  sku:         '',
  mlb:         '',
  status:      'todos',
  modalidade:  'todos',
  tipo_frete:  'todos',
  custo_imposto: 'todos',
  considerar_frete_comprador: false,
  page:        1,
  page_size:   50,
}

export default function FinanceiroMLResumoV2() {
  const [filtros, setFiltros] = useState(INITIAL_FILTERS)
  const [resultado, setResultado] = useState(null)

  const mutation = useMutation({
    mutationFn: async (filtrosAtuais) => {
      console.log('[BUSCAR-V2] frontend.start', filtrosAtuais)
      const t0 = performance.now()
      const data = await financeiroMLApi.getResumo(filtrosAtuais)
      console.log(`[BUSCAR-V2] frontend.success ms=${Math.round(performance.now() - t0)}`,
        { cards: data.cards, tabela_linhas: data.tabela?.length })
      return data
    },
    onSuccess: (data) => setResultado(data),
  })

  // Dispara busca inicial ao montar (1x)
  useEffect(() => {
    mutation.mutate(INITIAL_FILTERS)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const onDateChange = ({ data_inicio, data_fim }) => {
    const novos = { ...filtros, data_inicio, data_fim, page: 1 }
    setFiltros(novos)
    if (data_inicio && data_fim && data_inicio <= data_fim) {
      mutation.mutate(novos)
    }
  }

  const onFiltersChange = (novos) => {
    setFiltros(novos)
    mutation.mutate(novos)
  }

  const onPageChange = (page) => {
    const novos = { ...filtros, page }
    setFiltros(novos)
    mutation.mutate(novos)
  }

  const onPageSizeChange = (page_size) => {
    const novos = { ...filtros, page: 1, page_size }
    setFiltros(novos)
    mutation.mutate(novos)
  }

  const onExport = async (formato) => {
    const blob = await financeiroMLApi.exportResumo(filtros, formato)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `analise-financeira.${formato === 'csv' ? 'csv' : 'xlsx'}`
    a.click()
    URL.revokeObjectURL(url)
  }

  const cards = resultado?.cards
  const totalVendas = resultado?.pagination?.total

  return (
    <div className="fmlv2-root min-h-screen p-5">
      <div className="max-w-[1400px] mx-auto">
        <TopNav
          totalVendas={totalVendas}
          dataInicio={filtros.data_inicio}
          dataFim={filtros.data_fim}
          onDateChange={onDateChange}
        />

        {mutation.isError && (
          <div className="mb-3 px-4 py-2 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
            Erro: {String(mutation.error)}
            <button
              onClick={() => mutation.mutate(filtros)}
              className="ml-3 px-2 py-0.5 bg-red-600 text-white rounded text-xs"
            >
              Tentar novamente
            </button>
          </div>
        )}

        <BentoGrid>
          <HeroTile cards={cards} />

          <MediumTile
            tag="Faturamento ML"
            value={cards?.faturamento_ml}
            breakdown={[
              { label: 'Aprov.',  value: cards?.vendas_aprovadas },
              { label: 'Cancel.', value: cards?.vendas_canceladas },
            ]}
            sparkValue={cards?.vendas_aprovadas}
          />

          <DonutTile pizza={resultado?.pizza} />

          <SmallTile
            tag="Custo + Imp."
            value={cards?.custo_imposto_total}
          />
          <SmallTile
            tag="Tarifa ML"
            value={cards?.tarifa_venda}
          />
          <SmallTile
            tag="Frete Total"
            value={cards?.frete_total}
          />
          <SmallTile
            tag="Qtd Vendas"
            value={cards?.qtd_vendas_aprovadas}
            sub={`${cards?.unidades_aprovadas ?? 0} unid.`}
            int
          />
        </BentoGrid>

        <div className="text-center text-[var(--fmlv2-ink-2)] text-base opacity-50 py-2 select-none">
          ▼
        </div>

        <DataTable
          data={resultado?.tabela}
          pagination={resultado?.pagination}
          chips={
            <FilterChips filters={filtros} onChange={onFiltersChange} />
          }
          onPageChange={onPageChange}
          onPageSizeChange={onPageSizeChange}
          onExport={onExport}
        />

        {mutation.isPending && (
          <div className="fixed top-3 right-3 px-3 py-1.5 bg-[var(--fmlv2-ink-2)] text-white rounded-md text-xs shadow-lg">
            Buscando…
          </div>
        )}
      </div>
    </div>
  )
}
