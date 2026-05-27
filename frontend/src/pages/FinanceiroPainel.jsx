import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Eye, CheckCircle2, Plus, Calendar, ChevronDown, AlertTriangle, Wallet, ArrowRight, SlidersHorizontal, X } from 'lucide-react'
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

// ── Popover de filtros adicionais ────────────────────────────────────────────

function FiltroPopover({ aberto, setAberto, ativos, categorias, filtros, onChange, onLimpar }) {
  const ref = useRef(null)

  useEffect(() => {
    if (!aberto) return
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setAberto(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [aberto, setAberto])

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setAberto(!aberto)}
        className={cn(
          'h-10 px-4 border text-xs font-medium flex items-center gap-2 rounded-full transition-all',
          aberto
            ? 'bg-slate-900 border-slate-900 text-white shadow-lg'
            : 'bg-slate-50 border-slate-200 text-slate-700 hover:bg-slate-100'
        )}
      >
        <SlidersHorizontal size={14} />
        Filtro
        {ativos > 0 && (
          <span className={cn(
            'inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-bold',
            aberto ? 'bg-white text-slate-900' : 'bg-cyan-600 text-white'
          )}>
            {ativos}
          </span>
        )}
        <ChevronDown size={14} className={cn('transition-transform', aberto && 'rotate-180')} />
      </button>

      {aberto && (
        <div className="absolute top-12 right-0 md:right-auto md:left-0 w-[min(95vw,360px)] bg-white border border-slate-200 rounded-2xl shadow-2xl z-30 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-slate-900">Filtros adicionais</h3>
            <button onClick={() => setAberto(false)} className="text-slate-400 hover:text-slate-600">
              <X size={18} />
            </button>
          </div>

          <div className="space-y-3">
            <div>
              <label className="text-xs font-semibold text-slate-700 mb-1 block">Status</label>
              <select
                value={filtros.status}
                onChange={(e) => onChange({ status: e.target.value })}
                className="w-full p-2 border-2 border-slate-300 focus:border-cyan-500 outline-none rounded-lg bg-white text-sm"
              >
                <option value="">Todos status</option>
                <option value="registrado">Registrados</option>
                <option value="atrasado">Atrasados</option>
                <option value="pago">Pagos</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 mb-1 block">Categoria</label>
              <select
                value={filtros.categoria_id}
                onChange={(e) => onChange({ categoria_id: e.target.value })}
                className="w-full p-2 border-2 border-slate-300 focus:border-cyan-500 outline-none rounded-lg bg-white text-sm"
              >
                <option value="">Todas categorias</option>
                {categorias.map((c) => (
                  <option key={c.id} value={c.id}>{c.nome}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 mb-1 block">Empresa</label>
              <input
                type="text"
                value={filtros.empresa}
                onChange={(e) => onChange({ empresa: e.target.value })}
                placeholder="Buscar… (contém)"
                className="w-full p-2 border-2 border-slate-300 focus:border-cyan-500 outline-none rounded-lg bg-white text-sm"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 mb-1 block">Nota Fiscal</label>
              <input
                type="text"
                value={filtros.nota_fiscal}
                onChange={(e) => onChange({ nota_fiscal: e.target.value })}
                placeholder="Ex: 12345"
                className="w-full p-2 border-2 border-slate-300 focus:border-cyan-500 outline-none rounded-lg bg-white text-sm"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs font-semibold text-slate-700 mb-1 block">Valor mín</label>
                <input
                  type="number"
                  step="0.01"
                  value={filtros.valor_min}
                  onChange={(e) => onChange({ valor_min: e.target.value })}
                  placeholder="R$"
                  className="w-full p-2 border-2 border-slate-300 focus:border-cyan-500 outline-none rounded-lg bg-white text-sm"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-700 mb-1 block">Valor máx</label>
                <input
                  type="number"
                  step="0.01"
                  value={filtros.valor_max}
                  onChange={(e) => onChange({ valor_max: e.target.value })}
                  placeholder="R$"
                  className="w-full p-2 border-2 border-slate-300 focus:border-cyan-500 outline-none rounded-lg bg-white text-sm"
                />
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 mt-5 pt-4 border-t border-slate-100">
            <button
              onClick={onLimpar}
              className="flex-1 py-2 border-2 border-slate-300 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50"
            >
              Limpar filtros
            </button>
            <button
              onClick={() => setAberto(false)}
              className="flex-1 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded-lg text-xs font-bold shadow"
            >
              Fechar
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Cards de stat no padrão Supervisor ───────────────────────────────────────

function StatTileDark({ label, qtd, valor, sublabel, onClick, ativo }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'rounded-xl border border-slate-400 bg-slate-900 text-white p-3.5 relative overflow-hidden text-left transition-all hover:brightness-110 active:scale-[0.98]',
        ativo && 'ring-2 ring-cyan-400'
      )}
    >
      <div className="absolute -right-6 -top-6 w-20 h-20 rounded-full bg-white/10" />
      <p className="text-[10px] uppercase tracking-[0.2em] font-bold text-slate-300 mb-2">{label}</p>
      <p className="text-2xl font-black tabular-nums">{qtd}</p>
      <p className="text-[11px] text-slate-300 mt-1.5 font-mono">
        R$ {valor.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
      </p>
      {sublabel && <p className="text-[10px] text-slate-400 mt-0.5">{sublabel}</p>}
    </button>
  )
}

function StatTileLight({ label, qtd, valor, sublabel, onClick, ativo }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'rounded-xl border border-slate-400 bg-[linear-gradient(135deg,#f8fafc_0%,#e2e8f0_60%,#cbd5e1_100%)] p-3.5 text-left transition-all hover:shadow-md active:scale-[0.98]',
        ativo && 'ring-2 ring-cyan-400'
      )}
    >
      <p className="text-[10px] uppercase tracking-[0.2em] font-bold text-slate-500 mb-2">{label}</p>
      <p className="text-2xl font-black text-slate-900 tabular-nums">{qtd}</p>
      <p className="text-[11px] text-slate-600 mt-1.5 font-mono">
        R$ {valor.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
      </p>
      {sublabel && <p className="text-[10px] text-slate-500 mt-0.5">{sublabel}</p>}
    </button>
  )
}

function StatTileRed({ label, qtd, valor, sublabel, onClick, ativo }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'rounded-xl border border-red-400 bg-[linear-gradient(135deg,#fff1f2_0%,#fee2e2_60%,#fecaca_100%)] p-3.5 text-left transition-all hover:shadow-md active:scale-[0.98]',
        ativo && 'ring-2 ring-red-400'
      )}
    >
      <p className="text-[10px] uppercase tracking-[0.2em] font-bold text-red-500 mb-2">{label}</p>
      <p className="text-2xl font-black text-red-700 tabular-nums">{qtd}</p>
      <p className="text-[11px] text-red-600 mt-1.5 font-mono">
        R$ {valor.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
      </p>
      {sublabel && <p className="text-[10px] text-red-500/80 mt-0.5">{sublabel}</p>}
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
    categoria_id: '',
    empresa: '',
    nota_fiscal: '',
  })
  const [categorias, setCategorias] = useState([])
  const [filtroPopoverAberto, setFiltroPopoverAberto] = useState(false)

  // Conta quantos filtros do popover estão ativos (pra mostrar badge no botão)
  const filtrosAtivos = useMemo(() => {
    let n = 0
    if (filtros.status) n++
    if (filtros.categoria_id) n++
    if (filtros.empresa) n++
    if (filtros.nota_fiscal) n++
    if (filtros.valor_min !== '' && filtros.valor_min != null) n++
    if (filtros.valor_max !== '' && filtros.valor_max != null) n++
    return n
  }, [filtros.status, filtros.categoria_id, filtros.empresa, filtros.nota_fiscal, filtros.valor_min, filtros.valor_max])

  useEffect(() => {
    api.listarCategorias().then(setCategorias).catch(() => {})
  }, [])

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

  // Para a taxa de pagamento no hero mobile
  const totalNoFiltro = stats.total_a_pagar.qtd + stats.pagos.qtd
  const taxaPagamento = totalNoFiltro > 0
    ? Math.round((stats.pagos.qtd / totalNoFiltro) * 100)
    : 0

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto space-y-4 pb-24 md:pb-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <h1 className="text-xl md:text-2xl font-bold">Financeiro — Boletos a Pagar</h1>
        {/* No desktop, botão é inline. No mobile, vira FAB lá embaixo */}
        <button
          onClick={() => navigate('/financeiro/scan')}
          className="hidden md:flex items-center justify-center gap-2 bg-cyan-600 hover:bg-cyan-500 text-white px-4 py-3 rounded-xl font-bold shadow"
        >
          <Plus size={20} /> Adicionar boleto
        </button>
      </div>

      {/* MOBILE: Hero + 2 chips */}
      <div className="md:hidden space-y-3">
        <button
          onClick={filtroAPagar}
          className={cn(
            'w-full rounded-2xl border border-slate-700 bg-slate-900 text-white p-5 relative overflow-hidden text-left transition-all active:scale-[0.98]',
            filtros.status === 'registrado' && 'ring-2 ring-cyan-400'
          )}
        >
          <div className="absolute -right-10 -top-10 w-32 h-32 rounded-full bg-white/5" />
          <div className="absolute -right-4 -bottom-8 w-24 h-24 rounded-full bg-cyan-500/10" />
          <p className="text-[10px] uppercase tracking-[0.25em] font-bold text-slate-300 mb-2">
            A Pagar esta semana
          </p>
          <p className="font-black tabular-nums text-4xl mb-1">
            R$ {stats.total_a_pagar.valor.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
          </p>
          <p className="text-sm text-slate-300 mb-3">
            {stats.total_a_pagar.qtd} {stats.total_a_pagar.qtd === 1 ? 'boleto' : 'boletos'}
            {totalNoFiltro > 0 && ` · taxa ${taxaPagamento}% pago`}
          </p>
          <div className="w-full h-2 bg-slate-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-cyan-400 rounded-full transition-all duration-1000"
              style={{ width: `${taxaPagamento}%` }}
            />
          </div>
        </button>

        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={filtroVencidos}
            className={cn(
              'rounded-xl border border-red-300 bg-red-50 px-3 py-3 text-left active:scale-[0.98] transition-all',
              filtros.status === 'atrasado' && 'ring-2 ring-red-400'
            )}
          >
            <div className="flex items-center gap-1.5 mb-1">
              <AlertTriangle size={14} className="text-red-600" />
              <p className="text-[10px] uppercase tracking-wider font-bold text-red-600">Vencidos</p>
            </div>
            <p className="text-xl font-black text-red-700 tabular-nums leading-none">
              {stats.vencidos.qtd}
            </p>
            <p className="text-[11px] text-red-600 mt-1 font-mono">
              R$ {stats.vencidos.valor.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
            </p>
          </button>

          <button
            onClick={filtroPagos}
            className={cn(
              'rounded-xl border border-slate-300 bg-slate-50 px-3 py-3 text-left active:scale-[0.98] transition-all',
              filtros.status === 'pago' && 'ring-2 ring-cyan-400'
            )}
          >
            <div className="flex items-center gap-1.5 mb-1">
              <CheckCircle2 size={14} className="text-emerald-600" />
              <p className="text-[10px] uppercase tracking-wider font-bold text-slate-600">Pagos</p>
            </div>
            <p className="text-xl font-black text-slate-900 tabular-nums leading-none">
              {stats.pagos.qtd}
            </p>
            <p className="text-[11px] text-slate-600 mt-1 font-mono">
              R$ {stats.pagos.valor.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
            </p>
          </button>
        </div>
      </div>

      {/* DESKTOP: 3 stat tiles no estilo Supervisor */}
      <div className="hidden md:grid grid-cols-3 gap-3">
        <StatTileDark
          label="A Pagar (filtro)"
          qtd={stats.total_a_pagar.qtd}
          valor={stats.total_a_pagar.valor}
          sublabel="boletos pendentes"
          onClick={filtroAPagar}
          ativo={filtros.status === 'registrado'}
        />
        <StatTileRed
          label="Vencidos (todos)"
          qtd={stats.vencidos.qtd}
          valor={stats.vencidos.valor}
          sublabel="independe do filtro"
          onClick={filtroVencidos}
          ativo={filtros.status === 'atrasado'}
        />
        <StatTileLight
          label="Pagos (filtro)"
          qtd={stats.pagos.qtd}
          valor={stats.pagos.valor}
          sublabel="por data de pagamento"
          onClick={filtroPagos}
          ativo={filtros.status === 'pago'}
        />
      </div>

      {/* Toolbar: Data + botão "Filtro" (todos os outros filtros dentro) */}
      <div className="bg-white rounded-lg shadow p-3 md:p-4 mb-4 flex flex-wrap items-center gap-2 md:gap-3 text-sm">
        <FiltroData
          vencimento_de={filtros.vencimento_de}
          vencimento_ate={filtros.vencimento_ate}
          onChange={(v) => setFiltros({ ...filtros, ...v })}
        />

        <FiltroPopover
          aberto={filtroPopoverAberto}
          setAberto={setFiltroPopoverAberto}
          ativos={filtrosAtivos}
          categorias={categorias}
          filtros={filtros}
          onChange={(patch) => setFiltros({ ...filtros, ...patch })}
          onLimpar={() => setFiltros({
            ...filtros,
            status: '',
            categoria_id: '',
            empresa: '',
            nota_fiscal: '',
            valor_min: '',
            valor_max: '',
          })}
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
                    {b.status === 'registrado' && (
                      <span className={`px-2 py-0.5 rounded ${urg.classes}`}>{urg.label}</span>
                    )}
                    {b.banco_emissor && <span className="ml-auto">{b.banco_emissor}</span>}
                  </div>
                  <div className="flex items-center gap-2 mt-2 flex-wrap">
                    <span className={`px-2 py-0.5 rounded text-xs ${b.status === 'pago' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>
                      {b.status}
                    </span>
                    {b.categoria_nome && (
                      <span className="px-2 py-0.5 rounded text-xs bg-cyan-100 text-cyan-700">
                        {b.categoria_nome}
                      </span>
                    )}
                    <span className="text-xs text-slate-500 ml-auto">por {b.capturado_por_nome}</span>
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
                <th className="p-3">Categoria</th>
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
                    <td className="p-3">
                      {b.categoria_nome ? (
                        <span className="px-2 py-0.5 rounded text-xs bg-cyan-100 text-cyan-700">
                          {b.categoria_nome}
                        </span>
                      ) : <span className="text-slate-400">—</span>}
                    </td>
                    <td className="p-3 text-right font-mono">
                      {b.valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                    </td>
                    <td className="p-3">
                      {new Date(b.vencimento + 'T00:00:00').toLocaleDateString('pt-BR')}
                      {b.status === 'registrado' && (
                        <span className={`ml-2 text-xs px-2 py-0.5 rounded ${urg.classes}`}>
                          {urg.label}
                        </span>
                      )}
                    </td>
                    <td className="p-3">
                      {b.banco_emissor
                        ? `${b.banco_emissor} · ${nomeBanco(b.banco_emissor)}`
                        : <span className="text-slate-400">—</span>}
                    </td>
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

      {/* FAB mobile pra adicionar boleto */}
      <button
        onClick={() => navigate('/financeiro/scan')}
        className="md:hidden fixed right-5 bottom-24 z-30 w-14 h-14 rounded-full bg-cyan-600 hover:bg-cyan-500 active:scale-90 text-white shadow-xl shadow-cyan-900/30 flex items-center justify-center transition-all"
        aria-label="Adicionar boleto"
      >
        <Plus size={28} strokeWidth={2.5} />
      </button>

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
