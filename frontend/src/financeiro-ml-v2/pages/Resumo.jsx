import { useState, useCallback } from 'react'
import { useMutation } from '@tanstack/react-query'
import '../tokens.css'
import { formatBRL, formatPct } from '../utils'
import { financeiroMLApi } from '../api'
import { TopNav } from '../components/TopNav'
import { BentoGrid } from '../components/BentoGrid'
import { HeroTile } from '../components/HeroTile'
import { MediumTile } from '../components/MediumTile'
import { DonutTile } from '../components/DonutTile'
import { StatsStrip } from '../components/StatsStrip'
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

  // Busca sempre manual via botão Buscar — nunca dispara ao montar.
  const onBuscar = () => {
    if (filtros.data_inicio && filtros.data_fim && filtros.data_inicio <= filtros.data_fim) {
      mutation.mutate({ ...filtros, page: 1 })
    }
  }

  // Callbacks memoizados pra estabilizar identidade — caso contrário cada render
  // do Resumo invalida toda cadeia de useCallbacks dos componentes filhos
  const onDateChange = useCallback(({ data_inicio, data_fim }) => {
    setFiltros((f) => ({ ...f, data_inicio, data_fim, page: 1 }))
  }, [])

  const onFiltersChange = useCallback((novos) => {
    // Atualiza estado mas não dispara — usuário precisa clicar Buscar
    setFiltros(novos)
  }, [])

  // Paginação re-busca automático (não é nova busca, é navegação do dataset já carregado)
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
          onBuscar={onBuscar}
          loading={mutation.isPending}
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
          <HeroTile
            tag="Vendas Aprovadas"
            value={cards?.vendas_aprovadas}
            subline={
              <div className="flex items-baseline gap-3 text-[11px] opacity-85">
                <span>Faturamento ML <span className="fmlv2-mono font-semibold">{formatBRL(cards?.faturamento_ml)}</span></span>
                <span>Cancel. <span className="fmlv2-mono font-semibold">{formatBRL(cards?.vendas_canceladas)}</span></span>
              </div>
            }
          />

          <MediumTile
            tag="Margem de Contribuição"
            value={cards?.mc_total}
            subline={
              <div className="flex items-baseline gap-2">
                <span className="fmlv2-mono text-[16px] font-semibold" style={{ color: 'var(--fmlv2-pos)' }}>
                  {formatPct(cards?.mc_pct_global ?? 0)}
                </span>
                <span className="text-[10px] text-[var(--fmlv2-muted)]">margem média no período</span>
              </div>
            }
          />

          <DonutTile pizza={resultado?.pizza} />

          <StatsStrip
            items={[
              {
                label: 'Custo + Imposto',
                value: formatBRL(cards?.custo_imposto_total),
                sub: `Custo ${formatBRL(cards?.custo_total)} · Imp ${formatBRL(cards?.imposto_total)}`,
                tone: 'neg',
              },
              {
                label: 'Tarifa ML',
                value: formatBRL(cards?.tarifa_venda),
                sub: cards?.faturamento_ml
                  ? `${formatPct((cards.tarifa_venda / cards.faturamento_ml) * 100)} do faturamento`
                  : '—',
                tone: 'neg',
              },
              {
                label: 'Frete Total',
                value: formatBRL(cards?.frete_total),
                sub: `Comp ${formatBRL(cards?.frete_comprador_total)} · Vend ${formatBRL(cards?.frete_vendedor_total)}`,
              },
              {
                label: 'Qtd Vendas',
                value: new Intl.NumberFormat('pt-BR').format(cards?.qtd_vendas_aprovadas ?? 0),
                sub: `${cards?.unidades_aprovadas ?? 0} unid. · ticket ${formatBRL(cards?.ticket_medio)}`,
              },
            ]}
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
