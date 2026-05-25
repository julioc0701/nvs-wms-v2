import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Eye, CheckCircle2, Plus, Calendar, ChevronDown, AlertTriangle, Wallet, DollarSign } from 'lucide-react'
import { api } from '../api/client'
import { nomeBanco, urgenciaVencimento } from '../utils/boletoBancos'
import { cn } from '../lib/utils'
import FinanceiroDrawer from '../components/FinanceiroDrawer'
import FinanceiroConfirmDialog from '../components/dialogs/FinanceiroConfirmDialog'

/**
 * Painel /financeiro — lista de boletos com dashboard e filtros.
 *
 * Default ao abrir:
 *   - status = registrado
 *   - vencimento de hoje até domingo da semana corrente
 *
 * Dashboard no topo (3 cards):
 *   - Total a pagar (respeita filtros de vencimento)
 *   - Vencidos (ignora filtros, sempre todos os atrasados)
 *   - Pagos (respeita filtro de data, comparando com pago_em)
 *
 * Click em Vencidos → limpa todos os filtros e seta status=atrasado.
 */

// ── Helpers de data ──────────────────────────────────────────────────────────

function fmtDate(d) {
  const dd = String(d.getDate()).padStart(2, '0')
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const yyyy = d.getFullYear()
  return `${yyyy}-${mm}-${dd}`
}

function obterSemanaCorrente() {
  // De hoje até o domingo dessa semana
  const hoje = new Date()
  hoje.setHours(0, 0, 0, 0)
  const diaSemana = hoje.getDay() // 0=domingo, 1=seg, ..., 6=sab
  const diasAteDomingo = (7 - diaSemana) % 7 // 0 se hoje for domingo
  const domingo = new Date(hoje)
  domingo.setDate(hoje.getDate() + diasAteDomingo)
  return { de: fmtDate(hoje), ate: fmtDate(domingo) }
}

function aplicarPreset(preset) {
  const hoje = new Date()
  hoje.setHours(0, 0, 0, 0)
  if (preset === 'sem_filtro') return { de: '', ate: '' }
  if (preset === 'dia') return { de: fmtDate(hoje), ate: fmtDate(hoje) }
  if (preset === '7d') {
    const de = new Date(hoje); de.setDate(hoje.getDate() - 6)
    return { de: fmtDate(de), ate: fmtDate(hoje) }
  }
  if (preset === '30d') {
    const de = new Date(hoje); de.setDate(hoje.getDate() - 29)
    return { de: fmtDate(de), ate: fmtDate(hoje) }
  }
  if (preset === 'mes') {
    const de = new Date(hoje.getFullYear(), hoje.getMonth(), 1)
    const ate = new Date(hoje.getFullYear(), hoje.getMonth() + 1, 0)
    return { de: fmtDate(de), ate: fmtDate(ate) }
  }
  if (preset === 'semana') return obterSemanaCorrente()
  return { de: '', ate: '' }
}

const PRESETS = [
  { id: 'sem_filtro', label: 'sem filtro' },
  { id: 'semana', label: 'esta semana' },
  { id: 'dia', label: 'do dia' },
  { id: '7d', label: 'últimos 7 dias' },
  { id: '30d', label: 'últimos 30 dias' },
  { id: 'mes', label: 'do mês' },
  { id: 'intervalo', label: 'do intervalo' },
]

// ── Componente FiltroData ────────────────────────────────────────────────────

function FiltroData({ vencimento_de, vencimento_ate, onChange }) {
  const [open, setOpen] = useState(false)
  const [preset, setPreset] = useState('semana')
  const [tempDe, setTempDe] = useState(vencimento_de)
  const [tempAte, setTempAte] = useState(vencimento_ate)
  const ref = useRef(null)

  useEffect(() => {
    setTempDe(vencimento_de)
    setTempAte(vencimento_ate)
  }, [vencimento_de, vencimento_ate])

  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  function aplicar() {
    if (preset === 'intervalo') {
      onChange({ vencimento_de: tempDe, vencimento_ate: tempAte })
    } else {
      const r = aplicarPreset(preset)
      onChange({ vencimento_de: r.de, vencimento_ate: r.ate })
    }
    setOpen(false)
  }

  const labelAtivo = useMemo(() => {
    if (!vencimento_de && !vencimento_ate) return 'sem filtro de data'
    if (vencimento_de && vencimento_ate && vencimento_de === vencimento_ate) {
      return `dia ${new Date(vencimento_de + 'T00:00:00').toLocaleDateString('pt-BR')}`
    }
    const de = vencimento_de ? new Date(vencimento_de + 'T00:00:00').toLocaleDateString('pt-BR') : '—'
    const ate = vencimento_ate ? new Date(vencimento_ate + 'T00:00:00').toLocaleDateString('pt-BR') : '—'
    return `${de} → ${ate}`
  }, [vencimento_de, vencimento_ate])

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          'h-10 px-4 border text-xs font-medium flex items-center gap-2 rounded-full transition-all',
          open
            ? 'bg-cyan-600 border-cyan-600 text-white shadow-lg'
            : 'bg-cyan-50/50 border-cyan-100 text-cyan-700 hover:bg-cyan-100'
        )}
      >
        <Calendar size={14} />
        Vencimento: {labelAtivo}
        <ChevronDown size={14} className={cn('transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute top-12 left-0 w-[min(95vw,420px)] bg-white border border-slate-200 rounded-2xl shadow-2xl z-30 p-6">
          <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-3">Período</p>
          <div className="flex flex-wrap gap-2 mb-4">
            {PRESETS.map((p) => (
              <button
                key={p.id}
                onClick={() => setPreset(p.id)}
                className={cn(
                  'px-3 py-1.5 rounded-full text-xs font-medium border transition-all',
                  preset === p.id
                    ? 'bg-cyan-100 border-cyan-200 text-cyan-700'
                    : 'bg-slate-50 border-slate-100 text-slate-500 hover:bg-slate-100'
                )}
              >
                {p.label}
              </button>
            ))}
          </div>

          {preset === 'intervalo' && (
            <div className="grid grid-cols-2 gap-2 mb-4">
              <div>
                <label className="text-xs text-slate-500">De</label>
                <input
                  type="date"
                  value={tempDe}
                  onChange={(e) => setTempDe(e.target.value)}
                  className="w-full border rounded p-2 text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-slate-500">Até</label>
                <input
                  type="date"
                  value={tempAte}
                  onChange={(e) => setTempAte(e.target.value)}
                  className="w-full border rounded p-2 text-sm"
                />
              </div>
            </div>
          )}

          <div className="flex items-center gap-3">
            <button
              onClick={aplicar}
              className="bg-cyan-600 hover:bg-cyan-700 text-white px-6 py-2 rounded-full font-bold text-sm shadow active:scale-95 transition-all"
            >
              Aplicar
            </button>
            <button
              onClick={() => setOpen(false)}
              className="text-slate-500 hover:text-slate-800 text-sm font-medium"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Card de Dashboard ────────────────────────────────────────────────────────

function CardDash({ label, qtd, valor, cor, icon: Icon, onClick, destaque }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex-1 bg-white rounded-xl p-4 shadow-sm border-2 text-left transition-all hover:shadow-md active:scale-[0.98]',
        cor === 'amber' ? 'border-amber-200 hover:border-amber-300' :
        cor === 'red' ? 'border-red-200 hover:border-red-300' :
        cor === 'green' ? 'border-green-200 hover:border-green-300' :
        'border-slate-200 hover:border-slate-300',
        destaque && 'ring-2 ring-cyan-300'
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs uppercase tracking-wider font-semibold text-slate-500">{label}</div>
        <Icon
          size={20}
          className={
            cor === 'amber' ? 'text-amber-500' :
            cor === 'red' ? 'text-red-500' :
            cor === 'green' ? 'text-green-500' :
            'text-slate-400'
          }
        />
      </div>
      <div className="flex items-baseline gap-2">
        <div className={cn(
          'text-2xl md:text-3xl font-bold',
          cor === 'red' ? 'text-red-700' :
          cor === 'green' ? 'text-green-700' :
          'text-slate-900'
        )}>
          {qtd}
        </div>
        <div className="text-xs text-slate-500">
          {qtd === 1 ? 'boleto' : 'boletos'}
        </div>
      </div>
      <div className="text-sm text-slate-600 mt-1 font-mono">
        R$ {valor.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
      </div>
    </button>
  )
}

// ── Painel principal ─────────────────────────────────────────────────────────

export default function FinanceiroPainel() {
  const navigate = useNavigate()
  const operador = JSON.parse(localStorage.getItem('operator') || 'null')
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768

  useEffect(() => {
    if (!operador || operador.name !== 'Master') navigate('/sessions')
  }, [operador, navigate])

  // Filtro padrão: semana corrente, status registrado
  const semana = obterSemanaCorrente()
  const [filtros, setFiltros] = useState({
    status: 'registrado',
    vencimento_de: semana.de,
    vencimento_ate: semana.ate,
    valor_min: '',
    valor_max: '',
  })

  const [dados, setDados] = useState({ boletos: [], total: 0, valor_total: 0 })
  const [stats, setStats] = useState({
    total_a_pagar: { qtd: 0, valor: 0 },
    vencidos: { qtd: 0, valor: 0 },
    pagos: { qtd: 0, valor: 0 },
  })
  const [carregando, setCarregando] = useState(false)
  const [selecionado, setSelecionado] = useState(null)
  const [pagarDialog, setPagarDialog] = useState(null)

  async function carregar() {
    setCarregando(true)
    try {
      const [lista, stat] = await Promise.all([
        api.listarBoletos(filtros),
        api.statsBoletos({
          vencimento_de: filtros.vencimento_de,
          vencimento_ate: filtros.vencimento_ate,
          // Pra card de Pagos, usa as mesmas datas mas comparando com pago_em
          pago_de: filtros.vencimento_de,
          pago_ate: filtros.vencimento_ate,
        }),
      ])
      setDados(lista)
      setStats(stat)
    } finally {
      setCarregando(false)
    }
  }

  useEffect(() => {
    carregar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(filtros)])

  async function confirmarPagar() {
    await api.pagarBoleto(pagarDialog.id, operador.id)
    setPagarDialog(null)
    carregar()
  }

  function abrirDetalhe(boleto) {
    if (isMobile) {
      navigate(`/financeiro/boleto/${boleto.id}`)
    } else {
      setSelecionado(boleto)
    }
  }

  function filtroVencidos() {
    // Click no card de Vencidos: limpa filtros de data, seta status=atrasado
    setFiltros({
      status: 'atrasado',
      vencimento_de: '',
      vencimento_ate: '',
      valor_min: '',
      valor_max: '',
    })
  }

  function filtroPagos() {
    setFiltros({ ...filtros, status: 'pago' })
  }

  function filtroAPagar() {
    setFiltros({ ...filtros, status: 'registrado' })
  }

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4 md:mb-6">
        <h1 className="text-xl md:text-2xl font-bold">Financeiro — Boletos a Pagar</h1>
        <button
          onClick={() => navigate('/financeiro/scan')}
          className="flex items-center justify-center gap-2 bg-cyan-600 hover:bg-cyan-500 text-white px-4 py-3 rounded-xl font-bold shadow"
        >
          <Plus size={20} /> Adicionar boleto
        </button>
      </div>

      {/* Dashboard cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        <CardDash
          label="A Pagar (filtro)"
          qtd={stats.total_a_pagar.qtd}
          valor={stats.total_a_pagar.valor}
          cor="amber"
          icon={Wallet}
          onClick={filtroAPagar}
          destaque={filtros.status === 'registrado'}
        />
        <CardDash
          label="⚠ Vencidos (todos)"
          qtd={stats.vencidos.qtd}
          valor={stats.vencidos.valor}
          cor="red"
          icon={AlertTriangle}
          onClick={filtroVencidos}
          destaque={filtros.status === 'atrasado'}
        />
        <CardDash
          label="Pagos (filtro)"
          qtd={stats.pagos.qtd}
          valor={stats.pagos.valor}
          cor="green"
          icon={DollarSign}
          onClick={filtroPagos}
          destaque={filtros.status === 'pago'}
        />
      </div>

      {/* Filtros */}
      <div className="bg-white rounded-lg shadow p-3 md:p-4 mb-4 flex flex-wrap items-center gap-2 md:gap-3 text-sm">
        <FiltroData
          vencimento_de={filtros.vencimento_de}
          vencimento_ate={filtros.vencimento_ate}
          onChange={(v) => setFiltros({ ...filtros, ...v })}
        />

        <select
          value={filtros.status}
          onChange={(e) => setFiltros({ ...filtros, status: e.target.value })}
          className="border rounded-full px-3 h-10 text-xs font-medium bg-white"
        >
          <option value="">Todos status</option>
          <option value="registrado">Registrados</option>
          <option value="atrasado">Atrasados</option>
          <option value="pago">Pagos</option>
        </select>

        <input
          type="number"
          step="0.01"
          value={filtros.valor_min}
          onChange={(e) => setFiltros({ ...filtros, valor_min: e.target.value })}
          className="border rounded-full px-3 h-10 text-xs w-24 md:w-28"
          placeholder="R$ mín"
        />
        <input
          type="number"
          step="0.01"
          value={filtros.valor_max}
          onChange={(e) => setFiltros({ ...filtros, valor_max: e.target.value })}
          className="border rounded-full px-3 h-10 text-xs w-24 md:w-28"
          placeholder="R$ máx"
        />

        <div className="ml-auto text-xs text-slate-500">
          {dados.total} {dados.total === 1 ? 'boleto' : 'boletos'} · R$ {dados.valor_total.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
        </div>
      </div>

      {/* Lista: tabela desktop, cards mobile */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        {carregando && (
          <div className="p-6 text-center text-slate-500">Carregando…</div>
        )}
        {!carregando && dados.boletos.length === 0 && (
          <div className="p-6 text-center text-slate-500">Nenhum boleto encontrado.</div>
        )}

        {/* Cards no mobile */}
        {!carregando && dados.boletos.length > 0 && (
          <div className="md:hidden divide-y">
            {dados.boletos.map((b) => {
              const urg = urgenciaVencimento(b.vencimento)
              return (
                <button
                  key={b.id}
                  onClick={() => abrirDetalhe(b)}
                  className="w-full text-left p-4 hover:bg-slate-50 active:bg-slate-100 transition-colors"
                >
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <div className="font-semibold text-slate-900 line-clamp-2">
                      {b.beneficiario_razao_social || b.beneficiario_texto || '—'}
                    </div>
                    <div className="font-mono font-bold text-slate-900 whitespace-nowrap">
                      {b.valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-slate-600">
                    <span>Venc. {new Date(b.vencimento + 'T00:00:00').toLocaleDateString('pt-BR')}</span>
                    <span className={`px-2 py-0.5 rounded ${urg.classes}`}>{urg.label}</span>
                    <span className="ml-auto">{b.banco_emissor}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-2">
                    <span className={`px-2 py-0.5 rounded text-xs ${b.status === 'pago' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>
                      {b.status}
                    </span>
                    <span className="text-xs text-slate-500">por {b.capturado_por_nome}</span>
                  </div>
                </button>
              )
            })}
          </div>
        )}

        {/* Tabela no desktop */}
        {!carregando && dados.boletos.length > 0 && (
          <table className="hidden md:table w-full text-sm">
            <thead className="bg-slate-100 text-left">
              <tr>
                <th className="p-3">Empresa</th>
                <th className="p-3 text-right">Valor</th>
                <th className="p-3">Vencimento</th>
                <th className="p-3">Banco</th>
                <th className="p-3">Capturado por</th>
                <th className="p-3">Status</th>
                <th className="p-3">Ações</th>
              </tr>
            </thead>
            <tbody>
              {dados.boletos.map((b) => {
                const urg = urgenciaVencimento(b.vencimento)
                return (
                  <tr key={b.id} className="border-t hover:bg-slate-50">
                    <td className="p-3">{b.beneficiario_razao_social || b.beneficiario_texto || '—'}</td>
                    <td className="p-3 text-right font-mono">
                      {b.valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                    </td>
                    <td className="p-3">
                      {new Date(b.vencimento + 'T00:00:00').toLocaleDateString('pt-BR')}
                      <span className={`ml-2 text-xs px-2 py-0.5 rounded ${urg.classes}`}>
                        {urg.label}
                      </span>
                    </td>
                    <td className="p-3">{b.banco_emissor} · {nomeBanco(b.banco_emissor)}</td>
                    <td className="p-3">{b.capturado_por_nome}</td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded text-xs ${b.status === 'pago' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>
                        {b.status}
                      </span>
                    </td>
                    <td className="p-3 flex gap-2">
                      <button onClick={() => abrirDetalhe(b)} title="Ver detalhe">
                        <Eye size={18} className="text-slate-600 hover:text-cyan-600" />
                      </button>
                      {b.status === 'registrado' && (
                        <button onClick={() => setPagarDialog(b)} title="Marcar como pago">
                          <CheckCircle2 size={18} className="text-slate-600 hover:text-green-600" />
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Drawer só no desktop */}
      {selecionado && (
        <FinanceiroDrawer
          boleto={selecionado}
          onClose={() => setSelecionado(null)}
          onChange={() => { carregar(); setSelecionado(null) }}
        />
      )}

      {/* Dialog de pagar do desktop */}
      {pagarDialog && (
        <FinanceiroConfirmDialog
          titulo="Marcar como pago?"
          iconBg="bg-green-100"
          iconColor="text-green-600"
          icon={<CheckCircle2 size={28} strokeWidth={2.5} />}
          detalhes={
            <>
              <p className="text-gray-500 text-xs uppercase font-bold tracking-wider mb-1">EMPRESA</p>
              <p className="text-xl font-black text-gray-800 mb-4">
                {pagarDialog.beneficiario_razao_social || pagarDialog.beneficiario_texto || '—'}
              </p>
              <div className="grid grid-cols-2 gap-4 border-t border-gray-200 pt-4">
                <div>
                  <p className="text-gray-500 text-xs uppercase font-bold tracking-wider">VALOR</p>
                  <p className="text-lg font-bold text-green-700">
                    {pagarDialog.valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                  </p>
                </div>
                <div>
                  <p className="text-gray-500 text-xs uppercase font-bold tracking-wider">VENCIMENTO</p>
                  <p className="text-lg font-bold text-gray-700">
                    {new Date(pagarDialog.vencimento + 'T00:00:00').toLocaleDateString('pt-BR')}
                  </p>
                </div>
              </div>
            </>
          }
          pergunta="Após confirmar, o boleto sai da lista de pendentes. Você pode reabrir depois pelo painel de detalhe."
          confirmLabel="MARCAR COMO PAGO"
          confirmClasses="bg-green-600 hover:bg-green-700 shadow-green-200"
          onConfirm={confirmarPagar}
          onCancel={() => setPagarDialog(null)}
        />
      )}
    </div>
  )
}
