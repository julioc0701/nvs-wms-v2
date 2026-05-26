import { DollarSign, MinusCircle, Tag, Truck, Equal, Package, Receipt, Footprints } from 'lucide-react'
import { Tooltip } from './Tooltip'

const fmt = (n) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(n ?? 0)
const fmtPct = (n) => `${(Number(n) || 0).toFixed(2).replace('.', ',')}%`
const fmtInt = (n) => new Intl.NumberFormat('pt-BR').format(n ?? 0)

const EMPTY = {
  vendas_aprovadas: 0, faturamento_ml: 0, vendas_canceladas: 0,
  custo_imposto_total: 0, custo_total: 0, imposto_total: 0,
  tarifa_venda: 0,
  frete_total: 0, frete_comprador_total: 0, frete_vendedor_total: 0,
  mc_total: 0, mc_pct_global: 0,
  ticket_medio: 0, ticket_mc: 0,
  devolucoes_parciais_valor: 0,
  qtd_vendas_aprovadas: 0, qtd_total_vendas: 0, qtd_vendas_canceladas: 0,
  unidades_aprovadas: 0,
  breakdown_logistico: {},
}

// ─────────────────────────────────────────────────────────────────────────────
// Card grande (linha 1)
// ─────────────────────────────────────────────────────────────────────────────
function BigCard({ icon: Icon, accent, label, value, tooltip, right, children }) {
  const accents = {
    purple: 'bg-purple-50 border-purple-200 text-purple-700',
    red:    'bg-orange-50 border-orange-200 text-orange-700',
    yellow: 'bg-yellow-50 border-yellow-200 text-yellow-700',
    blue:   'bg-blue-50 border-blue-200 text-blue-700',
    green:  'bg-emerald-50 border-emerald-200 text-emerald-700',
  }
  return (
    <div className={`relative overflow-hidden border-2 rounded-lg p-3 flex items-stretch min-h-[110px] ${accents[accent] || accents.purple}`}>
      <div className="opacity-30 mr-3 flex items-start pt-1">
        <Icon size={36} strokeWidth={2.2} />
      </div>
      <div className="flex-1 flex flex-col justify-between">
        <div>
          <div className="flex items-center gap-1 text-xs font-medium opacity-80">
            {label}
            {tooltip && (
              <Tooltip content={tooltip}>
                <span className="cursor-help text-[10px] rounded-full border border-current w-3.5 h-3.5 inline-flex items-center justify-center opacity-60">?</span>
              </Tooltip>
            )}
          </div>
          <div className="text-2xl font-bold tracking-tight mt-0.5 text-slate-900">{value}</div>
          {children}
        </div>
      </div>
      {right && (
        <div className="text-right text-[11px] text-slate-700 ml-2 self-start space-y-1 leading-tight">
          {right}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Card pequeno (linha 2 — branco, neutro)
// ─────────────────────────────────────────────────────────────────────────────
function SmallCard({ icon: Icon, label, value, sub, tooltip, right }) {
  return (
    <div className="relative overflow-hidden bg-white border border-slate-200 rounded-lg p-3 min-h-[95px] flex items-stretch">
      <div className="opacity-25 mr-3 flex items-start text-slate-400">
        <Icon size={32} strokeWidth={2} />
      </div>
      <div className="flex-1 flex flex-col">
        <div className="flex items-center gap-1 text-xs font-medium text-slate-600">
          {label}
          {tooltip && (
            <Tooltip content={tooltip}>
              <span className="cursor-help text-[10px] rounded-full border border-slate-400 w-3.5 h-3.5 inline-flex items-center justify-center text-slate-500">?</span>
            </Tooltip>
          )}
        </div>
        {value && <div className="text-lg font-bold text-slate-900 mt-0.5">{value}</div>}
        {sub && <div className="text-[11px] text-slate-500 mt-0.5">{sub}</div>}
      </div>
      {right && (
        <div className="text-right text-[11px] text-slate-600 ml-2 self-start leading-tight space-y-0.5">
          {right}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// KPICards principal
// ─────────────────────────────────────────────────────────────────────────────
export function KPICards({ cards }) {
  const c = { ...EMPTY, ...(cards || {}) }
  const bl = c.breakdown_logistico || {}

  return (
    <div className="space-y-3">
      {/* Linha 1 — 5 cards coloridos */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3">
        <BigCard
          icon={DollarSign}
          accent="purple"
          label="Vendas Aprovadas"
          tooltip='"Vendas Aprovadas" considera o valor do produto + frete pago pelo comprador.'
          value={fmt(c.vendas_aprovadas)}
          right={
            <>
              <div><span className="opacity-60">Faturamento ML</span><br/><span className="font-semibold text-slate-800">{fmt(c.faturamento_ml)}</span></div>
              <div><span className="opacity-60">Vendas Canceladas</span><br/><span className="font-semibold text-slate-800">{fmt(c.vendas_canceladas)}</span></div>
            </>
          }
        />

        <BigCard
          icon={MinusCircle}
          accent="red"
          label="Custo & Imposto"
          tooltip="Valores vinculados aos SKUs cadastrados em Cadastro Custo SKU."
          value={fmt(c.custo_imposto_total)}
          right={
            <>
              <div><span className="opacity-60">Custo</span><br/><span className="font-semibold text-slate-800">{fmt(c.custo_total)}</span></div>
              <div><span className="opacity-60">Imposto</span><br/><span className="font-semibold text-slate-800">{fmt(c.imposto_total)}</span></div>
            </>
          }
        />

        <BigCard
          icon={Tag}
          accent="yellow"
          label="Tarifa de Venda"
          tooltip="Tarifa cobrada pelo Mercado Livre, descontada de devoluções parciais."
          value={fmt(c.tarifa_venda)}
        />

        <BigCard
          icon={MinusCircle}
          accent="blue"
          label="Frete Total"
          tooltip="Soma dos fretes em VENDAS APROVADAS."
          value={fmt(c.frete_total)}
          right={
            <>
              <div><span className="opacity-60">Frete Comprador</span><br/><span className="font-semibold text-slate-800">{fmt(c.frete_comprador_total)}</span></div>
              <div><span className="opacity-60">Frete Vendedor</span><br/><span className="font-semibold text-slate-800">{fmt(c.frete_vendedor_total)}</span></div>
            </>
          }
        />

        <BigCard
          icon={Equal}
          accent="green"
          label="Margem de Contribuição"
          tooltip="Vendas aprovadas − custo & imposto − tarifa − frete vendedor − devolução parcial."
          value={fmt(c.mc_total)}
        >
          <div className="text-sm font-semibold text-emerald-700 mt-0.5">({fmtPct(c.mc_pct_global)})</div>
        </BigCard>
      </div>

      {/* Linha 2 — 5 cards brancos */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3">
        <SmallCard
          icon={Truck}
          label="Por Tipo de Frete"
          right={
            <>
              <div><span className="opacity-60">Places/Coleta</span> <span className="font-semibold">{fmt(bl.places_coleta || 0)}</span></div>
              <div><span className="opacity-60">Flex</span> <span className="font-semibold">{fmt(bl.flex || 0)}</span></div>
              <div><span className="opacity-60">Full</span> <span className="font-semibold">{fmt(bl.full || 0)}</span></div>
              <div><span className="opacity-60">ME1</span> <span className="font-semibold">{fmt(bl.me1 || 0)}</span></div>
              <div><span className="opacity-60">Outros</span> <span className="font-semibold">{fmt(bl.outros || 0)}</span></div>
              <div className="border-t border-slate-200 pt-0.5 mt-0.5"><span className="opacity-60">Total</span> <span className="font-semibold">{fmt(c.vendas_aprovadas)}</span></div>
            </>
          }
        />

        <SmallCard
          icon={Package}
          label="Qtd Vendas Aprovadas"
          tooltip="Quantidade de vendas e somatória de unidades."
          value={fmtInt(c.qtd_vendas_aprovadas)}
          sub={`(${fmtInt(c.unidades_aprovadas)} unidades)`}
          right={
            <>
              <div className="opacity-60">Qtd Total Vendas</div>
              <div className="font-semibold text-slate-800">{fmtInt(c.qtd_total_vendas)}</div>
              <div className="opacity-60 mt-1">Qtd Vendas Canceladas</div>
              <div className="font-semibold text-slate-800">{fmtInt(c.qtd_vendas_canceladas)}</div>
            </>
          }
        />

        <SmallCard
          icon={Receipt}
          label="Ticket Médio por Venda Aprovada"
          tooltip='"Vendas Aprovadas" ÷ "Qtd Vendas Aprovadas".'
          value={fmt(c.ticket_medio)}
        />

        <SmallCard
          icon={Receipt}
          label="Ticket Médio da Margem das Vendas Aprovadas"
          tooltip='"Margem de Contribuição" ÷ "Qtd Vendas Aprovadas".'
          value={fmt(c.ticket_mc)}
          sub={`(${fmtPct(c.mc_pct_global)})`}
        />

        <SmallCard
          icon={Footprints}
          label="Devoluções Parciais"
          tooltip="Soma do valor de pedidos com refund parcial."
          value={fmt(c.devolucoes_parciais_valor)}
          sub="(0 vendas)"
        />
      </div>
    </div>
  )
}
