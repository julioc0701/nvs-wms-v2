import { Tooltip } from './Tooltip'

const fmt = (n) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(n ?? 0)
const fmtPct = (n) => `${(n ?? 0).toFixed(2).replace('.', ',')}%`
const fmtInt = (n) => new Intl.NumberFormat('pt-BR').format(n ?? 0)

function Card({ label, value, sub, tooltip, color = 'gray' }) {
  const bg = {
    green: 'bg-emerald-50 border-emerald-200',
    red: 'bg-red-50 border-red-200',
    yellow: 'bg-yellow-50 border-yellow-200',
    blue: 'bg-blue-50 border-blue-200',
    gray: 'bg-gray-50 border-gray-200',
  }[color]

  return (
    <Tooltip content={tooltip}>
      <div className={`border rounded-lg p-3 ${bg}`}>
        <div className="text-xs text-gray-600">{label}</div>
        <div className="text-xl font-semibold">{value}</div>
        {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
      </div>
    </Tooltip>
  )
}

export function KPICards({ cards }) {
  if (!cards) return null
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
      <Card label="Vendas Aprovadas" value={fmt(cards.vendas_aprovadas)}
            sub={`Faturamento ML ${fmt(cards.faturamento_ml)} · Canceladas ${fmt(cards.vendas_canceladas)}`}
            tooltip="Considera valor do produto + frete pago pelo comprador." />
      <Card label="Custo & Imposto" value={fmt(cards.custo_imposto_total)} color="red"
            sub={`Custo ${fmt(cards.custo_total)} · Imposto ${fmt(cards.imposto_total)}`}
            tooltip="Valores vinculados aos SKUs cadastrados em Cadastro SKU." />
      <Card label="Tarifa de Venda" value={fmt(cards.tarifa_venda)} color="yellow"
            tooltip="Tarifa ML descontada de eventual refund parcial." />
      <Card label="Frete Total" value={fmt(cards.frete_total)} color="blue"
            sub={`Comprador ${fmt(cards.frete_comprador_total)} · Vendedor ${fmt(cards.frete_vendedor_total)}`}
            tooltip="Soma dos fretes em vendas aprovadas." />
      <Card label="Margem de Contribuição" value={fmt(cards.mc_total)} color="green"
            sub={`(${fmtPct(cards.mc_pct_global)})`}
            tooltip="Vendas aprovadas menos custo, imposto, tarifa, frete vendedor e devolução parcial." />

      <Card label="Places/Coleta" value={fmt(cards.breakdown_logistico?.places_coleta || 0)} />
      <Card label="Flex" value={fmt(cards.breakdown_logistico?.flex || 0)} />
      <Card label="Full" value={fmt(cards.breakdown_logistico?.full || 0)} />
      <Card label="ME1" value={fmt(cards.breakdown_logistico?.me1 || 0)} />
      <Card label="Outros" value={fmt(cards.breakdown_logistico?.outros || 0)} />

      <Card label="Qtd Vendas Aprovadas" value={fmtInt(cards.qtd_vendas_aprovadas)}
            sub={`${fmtInt(cards.unidades_aprovadas)} unidades`} />
      <Card label="Qtd Total Vendas" value={`${fmtInt(cards.qtd_total_vendas)}`}
            sub={`canceladas: ${fmtInt(cards.qtd_vendas_canceladas)}`} />
      <Card label="Ticket Médio" value={fmt(cards.ticket_medio)} />
      <Card label="Ticket Médio MC" value={fmt(cards.ticket_mc)} sub={fmtPct(cards.mc_pct_global)} />
      <Card label="Devoluções Parciais" value={fmt(cards.devolucoes_parciais_valor)} />
    </div>
  )
}
