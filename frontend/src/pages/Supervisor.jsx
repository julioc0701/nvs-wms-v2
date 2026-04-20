import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import MarketplaceLogo from '../components/MarketplaceLogo'
import { 
  Trash2, Package, CheckCircle, Clock, Trophy, Target, 
  UploadCloud, Database, AlertCircle, Printer, ArrowLeft,
  Settings, Folder, Copy, LayoutDashboard, ListTodo, Wrench, ArrowRight, Activity, Search, FileText, Key, Users, LogOut,
  BarChart3, Gauge, TrendingUp, Plus, Minus, ChevronRight, Layers, LayoutGrid
} from 'lucide-react'
import { cn } from '../lib/utils'
import { useFeedback } from '../components/ui/FeedbackProvider'
import { useCompactViewport } from '../hooks/useCompactViewport'

const STATUS_LABEL = { open: 'Disponível', in_progress: 'Em andamento', completed: 'Concluída' }

function normalizeMarket(value) {
  const v = String(value || '').toLowerCase()
  if (v === 'ml' || v === 'mercado_livre' || v === 'mercadolivre' || v === 'mercado livre') return 'ml'
  if (v === 'shopee') return 'shopee'
  return v
}

function MetricTile({ label, value, detail, icon: Icon }) {
  return (
    <div className="metric-tile bg-slate-50/70">
      <div className="flex items-center justify-between mb-2">
        <span className="metric-label">{label}</span>
        {Icon ? <Icon size={16} className="text-slate-400" /> : null}
      </div>
      <p className="metric-value leading-none">{value}</p>
      {detail ? <p className="text-xs text-slate-500 mt-2 font-semibold">{detail}</p> : null}
    </div>
  )
}

// ── Progress Hero ─────────────────────────────────────────────────────────────
function ProgressHero({ sessions, shortageStats, compact = false }) {
  const totalPicked = sessions.reduce((s, r) => s + (r.items_picked || 0), 0)
  const totalItems  = sessions.reduce((s, r) => s + (r.items_total  || 0), 0)
  const done        = sessions.filter(s => s.status === 'completed').length
  const pct         = totalItems ? Math.round((totalPicked / totalItems) * 100) : 0

  const active    = sessions.filter(s => s.status === 'in_progress').length
  const available = sessions.filter(s => s.status === 'open').length
  const remaining = Math.max(totalItems - totalPicked, 0)
  const avgPerList = sessions.length ? Math.round(totalPicked / sessions.length) : 0
  const doneRate = sessions.length ? Math.round((done / sessions.length) * 100) : 0

  const doneShare = sessions.length ? Math.round((done / sessions.length) * 100) : 0
  const activeShare = sessions.length ? Math.round((active / sessions.length) * 100) : 0
  const availableShare = sessions.length ? Math.round((available / sessions.length) * 100) : 0
  const shortageImpactPct = totalItems ? Math.round((shortageStats.totalUnits / totalItems) * 100) : 0
  if (sessions.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-dashed border-slate-300 p-10 flex flex-col items-center justify-center text-slate-400">
        <Package size={48} strokeWidth={1} className="mb-4 text-slate-300" />
        <p className="text-lg font-semibold text-slate-600">Nenhuma lista carregada ainda</p>
        <p className="text-sm mt-1">Vá para a aba <strong>Ferramentas</strong> e carregue o PDF de picking.</p>
      </div>
    )
  }

  return (
    <div className={cn("panel-elevated", compact ? "p-3 md:p-4" : "p-4 md:p-5")}>
      <div className={cn(
        "chart-card bg-[radial-gradient(circle_at_top_right,#e2e8f0_0%,#f8fafc_45%,#ffffff_100%)] rounded-2xl",
        compact ? "p-3 md:p-4 mb-3" : "p-4 md:p-5 mb-4"
      )}>
        <div className={cn("flex flex-col md:flex-row md:items-start md:justify-between gap-3", compact ? "mb-3" : "mb-4")}>
          <div>
            <p className="section-kicker mb-2 flex items-center gap-2">
              <Gauge size={14} /> Painel Executivo de Expedição
            </p>
            <div className="flex items-end gap-3">
              <span className={cn("font-black text-slate-900 tracking-tighter tabular-nums", compact ? "text-3xl md:text-4xl" : "text-4xl md:text-5xl")}>{pct}%</span>
              <span className="text-sm md:text-base text-slate-600 font-semibold tabular-nums pb-1.5">
                {totalPicked.toLocaleString('pt-BR')} / {totalItems.toLocaleString('pt-BR')} unds
              </span>
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white/80 backdrop-blur px-4 py-3">
            <p className="text-[11px] uppercase tracking-[0.18em] font-bold text-slate-500">Taxa de Conclusão</p>
            <p className="text-2xl font-black text-slate-900 tabular-nums">{doneRate}%</p>
          </div>
        </div>

        <div className="w-full h-3 bg-slate-100 rounded-full overflow-hidden mb-2">
          <div className="h-full bg-slate-900 rounded-full transition-all duration-1000 ease-out" style={{ width: `${pct}%` }} />
        </div>
        <div className="flex justify-between text-[11px] text-slate-500 font-semibold">
          <span>Início</span>
          <span>Meta operacional: 100%</span>
        </div>
      </div>

      <div className={cn("grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3", compact ? "mb-3" : "mb-4")}>
        <div className="rounded-xl border border-slate-200 bg-slate-900 text-white p-3.5 relative overflow-hidden">
          <div className="absolute -right-6 -top-6 w-20 h-20 rounded-full bg-white/10" />
          <p className="text-[10px] uppercase tracking-[0.2em] font-bold text-slate-300 mb-2">Volume Processado</p>
          <p className="text-2xl font-black tabular-nums">{totalPicked.toLocaleString('pt-BR')}</p>
          <p className="text-[11px] text-slate-300 mt-1.5">itens separados</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-3.5">
          <p className="text-[10px] uppercase tracking-[0.2em] font-bold text-slate-500 mb-2">Pendentes</p>
          <p className="text-2xl font-black text-slate-900 tabular-nums">{remaining.toLocaleString('pt-BR')}</p>
          <p className="text-[11px] text-slate-500 mt-1.5">itens restantes</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-3.5">
          <p className="text-[10px] uppercase tracking-[0.2em] font-bold text-slate-500 mb-2">Listas Concluídas</p>
          <p className="text-2xl font-black text-slate-900 tabular-nums">{done}/{sessions.length}</p>
          <p className="text-[11px] text-slate-500 mt-1.5">{doneShare}% do total</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-3.5">
          <p className="text-[10px] uppercase tracking-[0.2em] font-bold text-slate-500 mb-2">Média por Lista</p>
          <p className="text-2xl font-black text-slate-900 tabular-nums">{avgPerList.toLocaleString('pt-BR')}</p>
          <p className="text-[11px] text-slate-500 mt-1.5">itens por sessão</p>
        </div>
      </div>

      <div className={cn("grid grid-cols-1 md:grid-cols-2", compact ? "gap-3" : "gap-4")}>
        <div className="chart-card">
          <p className="section-kicker mb-3">Distribuição de Status</p>
          {[
            { label: 'Em andamento', value: active, share: activeShare, tone: 'bg-blue-600' },
            { label: 'Disponíveis', value: available, share: availableShare, tone: 'bg-slate-500' },
            { label: 'Concluídas', value: done, share: doneShare, tone: 'bg-emerald-600' },
          ].map((r) => (
            <div key={r.label} className="mb-3 last:mb-0">
              <div className="flex justify-between text-xs font-semibold text-slate-700 mb-1">
                <span>{r.label}</span>
                <span className="tabular-nums">{r.value} ({r.share}%)</span>
              </div>
              <div className="h-2.5 bg-slate-100 rounded-full overflow-hidden">
                <div className={cn("h-full rounded-full", r.tone)} style={{ width: `${r.share}%` }} />
              </div>
            </div>
          ))}
        </div>

        <div className="rounded-xl border border-red-200 bg-red-50/40 p-4 shadow-sm">
          <p className="section-kicker text-red-600 mb-3">Relatório de Faltas</p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
            <div className="rounded-lg border border-red-200 bg-white px-3 py-2">
              <p className="text-[10px] uppercase tracking-wide font-bold text-red-500">Itens Faltantes</p>
              <p className="text-2xl font-black text-red-700 tabular-nums">{shortageStats.totalUnits}</p>
            </div>
            <div className="rounded-lg border border-red-200 bg-white px-3 py-2">
              <p className="text-[10px] uppercase tracking-wide font-bold text-red-500">SKUs com Falta</p>
              <p className="text-2xl font-black text-red-700 tabular-nums">{shortageStats.skuCount}</p>
            </div>
            <div className="rounded-lg border border-red-200 bg-white px-3 py-2">
              <p className="text-[10px] uppercase tracking-wide font-bold text-red-500">Impacto no Volume</p>
              <p className="text-2xl font-black text-red-700 tabular-nums">{shortageImpactPct}%</p>
            </div>
          </div>
          <div className="text-xs font-semibold text-red-700 bg-red-100/70 border border-red-200 rounded-lg px-3 py-2">
            Prioridade: revisar faltas antes do fechamento final do lote.
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Ranking with Batch Selector ──────────────────────────────────────────────
function OperatorRanking({ batches = [], marketplace = null, compact = false }) {
  const [selectedBatch, setSelectedBatch] = useState(null)
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getOperatorRanking(selectedBatch, marketplace)
      .then(res => { if (Array.isArray(res)) setData(res) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [selectedBatch, marketplace])

  const activeBatches = batches.filter(b => b.status === 'active')
  const sorted = [...data].sort((a, b) => (b.total || 0) - (a.total || 0))
  const maxValue = sorted.length > 0 ? Math.max(...sorted.map(d => d.total || 0), 1) : 1

  const topN = compact ? 4 : 5

  return (
    <div className={cn("panel-elevated", compact ? "p-3" : "p-3.5 md:p-4")}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-black text-slate-900 flex items-center gap-2">
          <BarChart3 size={20} className="text-slate-700" /> Performance de Operadores
        </h3>
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-widest bg-slate-100 px-3 py-1 rounded-full">
          Itens Separados
        </span>
      </div>

      <div className={cn("action-rail flex flex-wrap gap-2", compact ? "mb-2" : "mb-3")}>
        <button
          onClick={() => setSelectedBatch(null)}
          className={cn(
            "px-4 py-2 rounded-lg text-xs font-bold transition-colors border",
            selectedBatch === null
              ? "bg-slate-900 text-white border-slate-900"
              : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
          )}
        >
          Visão Global
        </button>
        {activeBatches.map(b => (
          <button
            key={b.id}
            onClick={() => setSelectedBatch(b.id)}
            className={cn(
              "px-4 py-2 rounded-lg text-xs font-bold transition-colors border flex items-center gap-2",
              selectedBatch === b.id
                ? "bg-blue-600 text-white border-blue-600 shadow-sm"
                : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
            )}
          >
            <Package size={14} /> {b.name}
          </button>
        ))}
      </div>

      {activeBatches.length === 0 && (
        <p className="text-xs text-slate-400 italic mb-3">
          📌 Os filtros de lote aparecerão após o upload do primeiro PDF.
        </p>
      )}

      {loading ? (
        <div className="space-y-4">
          {[1,2,3].map(i => <div key={i} className="h-10 bg-slate-100 rounded-lg animate-pulse" />)}
        </div>
      ) : sorted.length === 0 ? (
        <div className="text-center py-10 bg-slate-50 rounded-xl border border-dashed border-slate-200 text-slate-400 italic text-sm">
          Nenhum volume separado ainda.
        </div>
      ) : (
        <div className={cn("chart-card", compact ? "p-2" : "p-2.5")}>
          <p className="section-kicker mb-2">Ranking de Produção</p>
          <div className="space-y-2">
            {sorted.slice(0, topN).map((op, idx) => {
              const total = op.total || 0
              const width = Math.max(6, Math.round((total / maxValue) * 100))
              return (
                <div key={op.name} className="rounded-lg border border-slate-100 bg-slate-50/50 px-2.5 py-2">
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-[12px] font-bold text-slate-800 truncate">{idx + 1}. {op.name}</p>
                    <p className="text-[12px] font-black text-slate-900 tabular-nums">{total.toLocaleString('pt-BR')}</p>
                  </div>
                  <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className={cn("h-full rounded-full transition-all duration-700", idx === 0 ? "bg-slate-900" : "bg-blue-600")}
                      style={{ width: `${width}%` }}
                      title={`${op.name}: ${total.toLocaleString('pt-BR')} itens`}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Tool Card ───────────────────────────────────────────────────────────────
function ToolCard({ icon: Icon, title, description, children, accentColor = 'blue' }) {
  const accents = {
    blue:   'border-blue-200 bg-white shadow-sm hover:border-blue-300',
    green:  'border-emerald-200 bg-white shadow-sm hover:border-emerald-300',
    red:    'border-red-200 bg-white shadow-sm hover:border-red-300',
    indigo: 'border-indigo-200 bg-white shadow-sm hover:border-indigo-300',
  }
  const iconColors = {
    blue: "text-blue-500 bg-blue-50",
    green: "text-emerald-500 bg-emerald-50",
    red: "text-red-500 bg-red-50",
    indigo: "text-indigo-500 bg-indigo-50"
  }

  return (
    <div className={cn("rounded-2xl border transition-all p-6", accents[accentColor])}>
      <div className="flex items-center gap-4 mb-3">
        <div className={cn("p-3 rounded-xl", iconColors[accentColor])}>
          <Icon size={24} strokeWidth={2} />
        </div>
        <h3 className="text-lg font-bold text-slate-800">{title}</h3>
      </div>
      <p className="text-sm text-slate-500 mb-6 leading-relaxed">{description}</p>
      <div className="bg-slate-50 rounded-xl p-5 border border-slate-100">
        {children}
      </div>
    </div>
  )
}

// ── Session Row (Original intact business logic, completely renewed UI) ────────
function SessionRow({ s, onDeleted }) {
  const { askConfirm, askPrompt, notify } = useFeedback()
  const [confirm, setConfirm] = useState(false)
  const [confirmReopen, setConfirmReopen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [reopening, setReopening] = useState(false)
  const [details, setDetails] = useState(false)
  const [items, setItems] = useState([])
  const [loadingItems, setLoadingItems] = useState(false)
  const [errMsg, setErrMsg] = useState(null)
  
  const pct = s.items_total ? Math.round((s.items_picked / s.items_total) * 100) : 0

  async function doReopen() {
    setReopening(true); setConfirmReopen(false)
    try { await api.reopenSession(s.id); onDeleted() }
    catch (err) { setErrMsg(err.message); setTimeout(() => setErrMsg(null), 3000) }
    finally { setReopening(false) }
  }

  async function toggleDetails() {
    if (details) { setDetails(false); return }
    setLoadingItems(true); setDetails(true)
    try { const data = await api.getItems(s.id); setItems(data) }
    catch (err) { setErrMsg(err.message) }
    finally { setLoadingItems(false) }
  }

  async function handleTransfer(itemId) {
    const accepted = await askConfirm({
      title: 'Transferir item',
      message: 'Transferir este item para uma lista disponível?',
      confirmText: 'Transferir',
    })
    if (!accepted) return
    try { await api.transferItem(itemId, 0); toggleDetails(); onDeleted() }
    catch (err) { notify(err.message, 'error') }
  }

  async function handleDelete() {
    setConfirm(true)
  }

  async function confirmDelete() {
    setDeleting(true)
    try { await api.deleteSession(s.id); onDeleted() }
    catch (err) { setErrMsg(err.message); setTimeout(() => setErrMsg(null), 3000); setConfirm(false) }
    finally { setDeleting(false) }
  }

  return (
    <div className="border-b border-slate-100 last:border-0 hover:bg-slate-50 transition-colors">
      <div className="flex flex-col sm:flex-row sm:items-center gap-4 py-4 px-2">
        <span className="font-mono font-bold text-slate-700 w-48 text-sm bg-white px-2 py-1 rounded border border-slate-200 shadow-sm">{s.session_code}</span>
        
        <div className="flex items-center gap-2 w-32">
          {s.operator_name ? (
            <div className="flex items-center gap-2 text-sm text-slate-600 font-medium truncate">
               <div className="w-6 h-6 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-xs">
                 {s.operator_name.charAt(0)}
               </div>
               <span className="truncate">{s.operator_name}</span>
            </div>
          ) : (
            <span className="text-slate-400 text-sm italic">—</span>
          )}
        </div>

        <div className="flex-1 flex items-center gap-3">
          <div className="flex-1 h-2 bg-slate-200 rounded-full overflow-hidden">
            <div className={cn("h-full rounded-full transition-all", pct === 100 ? "bg-emerald-500" : "bg-blue-500")} style={{ width: `${pct}%` }} />
          </div>
          <span className="text-xs font-bold text-slate-600 tabular-nums w-12 text-right">{s.items_picked}/{s.items_total}</span>
        </div>
        
        <button onClick={toggleDetails} className="text-sm font-semibold text-slate-500 hover:text-blue-600 px-3 py-1.5 rounded-md hover:bg-blue-50 transition-colors">
          {details ? 'Ocultar' : 'Ver SKUs'}
        </button>

        <div className="w-32 flex justify-end">
          {(s.status === 'completed' || s.status === 'in_progress') && !confirmReopen ? (
            <button
              onClick={() => setConfirmReopen(true)} disabled={reopening}
              className={cn("text-xs font-bold px-3 py-1.5 rounded-full border transition-colors",
                s.status === 'completed' 
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100" 
                  : "bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100"
              )}
            >
              {reopening ? '...' : s.status === 'completed' ? 'Concluída' : 'Em Andamento'}
            </button>
          ) : s.status === 'open' ? (
            <span className="text-xs font-bold px-3 py-1.5 rounded-full border bg-slate-100 text-slate-600 border-slate-200">
              Disponível
            </span>
          ) : null}
        </div>

        <div className="flex items-center gap-2">
          {confirmReopen && (
            <div className="flex items-center gap-1 bg-amber-50 p-1 rounded-lg border border-amber-200">
              <button onClick={() => setConfirmReopen(false)} className="px-3 py-1 text-xs font-bold rounded text-slate-600 hover:bg-white">Não</button>
              <button onClick={doReopen} disabled={reopening} className="px-3 py-1 text-xs font-bold rounded bg-amber-500 text-white hover:bg-amber-600 shadow-sm">Sim</button>
            </div>
          )}
          
          {!confirm && !confirmReopen && (
            <button onClick={handleDelete} title="Excluir lista"
              className={cn("p-2 rounded-lg transition-colors border shadow-sm", 
                s.status === 'in_progress' 
                  ? "text-slate-500 border-slate-200 bg-white hover:text-red-500 hover:border-red-200 hover:bg-red-50" 
                  : "text-slate-500 border-slate-200 bg-white hover:text-red-500 hover:border-red-200 hover:bg-red-50"
              )}>
              <Trash2 size={16} />
            </button>
          )}

          {confirm && (
            <div className="flex items-center gap-1 bg-red-50 p-1 rounded-lg border border-red-200">
              <button onClick={() => setConfirm(false)} className="px-3 py-1 text-xs font-bold rounded text-slate-600 hover:bg-white">Não</button>
              <button onClick={confirmDelete} disabled={deleting} className="px-3 py-1 text-xs font-bold rounded bg-red-600 text-white hover:bg-red-700 shadow-sm">{deleting ? '...' : 'Excluir'}</button>
            </div>
          )}
        </div>
      </div>
      
      {confirmReopen && <p className="text-xs font-medium text-amber-600 pb-3 pl-2 flex items-center gap-1"><AlertCircle size={14}/> Reinicializar lista remove acesso do operador atual.</p>}
      {confirm && !deleting && <p className="text-xs font-medium text-red-600 pb-3 pl-2 flex items-center gap-1"><AlertCircle size={14}/>Ação destrutiva e irrevogável.</p>}
      {errMsg && <p className="text-xs font-bold text-red-600 pb-3 pl-2">{errMsg}</p>}

      {details && (
        <div className="bg-white m-3 mt-1 rounded-xl p-5 border border-slate-200 shadow-inner">
          {loadingItems ? (
            <div className="flex justify-center py-6 text-slate-400 animate-pulse"><Database size={24} /></div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left border-collapse">
                <thead>
                  <tr className="text-slate-500 border-b-2 border-slate-100">
                    <th className="pb-3 px-2 font-semibold">SKU</th>
                    <th className="pb-3 px-2 font-semibold text-center">Progresso</th>
                    <th className="pb-3 px-2 font-semibold w-1/3">Contexto (Obs)</th>
                    <th className="pb-3 px-2 font-semibold">Situação</th>
                    <th className="pb-3 px-2 font-semibold text-right">Ações de Rota</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {items.map(item => (
                    <tr key={item.id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="py-3 px-2 font-mono font-bold text-slate-800">{item.sku}</td>
                      <td className="py-3 px-2 text-center text-slate-600 tabular-nums font-medium">{item.qty_picked} / {item.qty_required}</td>
                      <td className="py-3 px-2">
                        <div
                          onClick={async (e) => {
                            e.stopPropagation()
                            const newNotes = await askPrompt({
                              title: `Observação para ${item.sku}`,
                              initialValue: item.notes || '',
                              placeholder: 'Digite a observação',
                              confirmText: 'Salvar',
                            })
                            if (newNotes === null) return
                            try {
                              await api.updateItemNotes(item.id, newNotes.trim() || null)
                              setItems(prev => prev.map(i => i.id === item.id ? { ...i, notes: newNotes.trim() || null } : i))
                            } catch (e) { notify('Erro: ' + e.message, 'error') }
                          }}
                          className="truncate max-w-[280px] cursor-pointer text-blue-600 hover:text-blue-800 border-b border-dashed border-blue-200 hover:border-blue-600 hover:bg-blue-50 p-1 rounded transition-colors group"
                          title={item.notes || 'Adicionar apontamento'}
                        >
                          {item.notes || <span className="text-slate-300 italic text-xs">Sem anotações...</span>}
                        </div>
                      </td>
                      <td className="py-3 px-2">
                        <span className={cn("px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider",
                          item.status === 'complete' ? 'bg-emerald-100 text-emerald-700' :
                          item.status === 'pending'  ? 'bg-slate-100 text-slate-600' :
                          'bg-amber-100 text-amber-700'
                        )}>
                          {item.status}
                        </span>
                      </td>
                      <td className="py-3 px-2 text-right">
                        {item.qty_picked === 0 && (
                          <button onClick={() => handleTransfer(item.id)} className="text-xs font-bold text-blue-600 bg-blue-50 border border-blue-200 px-3 py-1.5 rounded-lg hover:bg-blue-600 hover:text-white transition-colors">
                            TRANSFERIR
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Shortage Report (Embedded & Renewed) ──────────────────────────────────────────────
function ShortageSection() {
  const { notify } = useFeedback()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState({ full: true, organico: true })

  const loadData = () => {
    setLoading(true)
    api.getShortages()
      .then(setItems)
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadData()
  }, [])

  const groupShortages = (items) => {
    const groups = { full: [], organico: [] };
    items.forEach(item => {
      const cat = item.category?.toLowerCase() === 'organico' ? 'organico' : 'full';
      groups[cat].push(item);
    });
    return groups;
  };

  const handleDeleteShortage = async (id) => {
    if (!confirm('Deseja remover este registro de falta?')) return;
    try {
      if (typeof id === 'string' && id.startsWith('legacy_')) {
        alert('Este é um registro legado de uma lista de picking ativa. Para remover, altere a quantidade na lista original.');
        return;
      }
      await api.post(`/tiny/shortages/${id}/delete`, {});
      notify('Registro de falta removido.', 'success');
      loadData();
    } catch (err) {
      notify('Erro ao remover falta.', 'error');
    }
  };

  const groups = groupShortages(items);
  const fullGroup = groups.full
  const organicGroup = groups.organico
  const totalShortage = items.reduce((s, i) => s + (i.quantity || 0), 0)

  if (loading) return (
    <div className="flex justify-center py-20 text-slate-400 animate-pulse flex-col items-center gap-4">
      <Database size={48} />
      <span className="text-xs font-bold uppercase tracking-widest">Sincronizando Faltas...</span>
    </div>
  )

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="bg-white rounded-3xl border border-slate-200 p-4 sm:p-8 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm">
        <div>
          <h3 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight flex items-center gap-3">
             <AlertCircle size={24} className="text-red-500 shrink-0" /> Painel de Rupturas
          </h3>
          <p className="text-slate-400 text-sm font-semibold mt-1">Monitoramento em tempo real de itens não localizados</p>
        </div>
        <div className="bg-red-50 border border-red-100 px-5 sm:px-8 py-3 rounded-2xl text-right shrink-0">
           <p className="text-[10px] font-black text-red-400 uppercase tracking-[0.2em] mb-1">Déficit Total</p>
           <span className="text-3xl font-black text-red-600 tabular-nums">{totalShortage.toFixed(0)} <small className="text-sm">UN</small></span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8">
        <GroupCard 
          title="Operação Full (Shopee/ML)"
          subtitle="Itens faltantes nas listas de carregamento"
          items={fullGroup}
          isOpen={expanded.full}
          onToggle={() => setExpanded(e => ({ ...e, full: !e.full }))}
          onDelete={handleDeleteShortage}
          icon={<LayoutGrid size={20} />}
          color="blue"
        />

        <GroupCard 
          title="Operação Orgânico (Tiny)"
          subtitle="Itens faltantes nas separações avulsas"
          items={organicGroup}
          isOpen={expanded.organico}
          onToggle={() => setExpanded(e => ({ ...e, organico: !e.organico }))}
          onDelete={handleDeleteShortage}
          icon={<Layers size={20} />}
          color="emerald"
        />
      </div>
    </div>
  )
}

function GroupCard({ title, subtitle, items, isOpen, onToggle, onDelete, icon, color }) {
  const { notify } = useFeedback()
  const total = items.reduce((s, i) => s + (i.quantity || 0), 0)

  const copySku = (sku) => {
    navigator.clipboard.writeText(sku);
    notify('SKU copiado!', 'success');
  };
  
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between px-2">
        <div className="flex items-center gap-4">
           <div className={`w-12 h-12 rounded-2xl bg-${color}-50 text-${color}-600 flex items-center justify-center border border-${color}-100 shadow-sm`}>
              {icon}
           </div>
           <div>
              <h4 className="text-lg font-black text-slate-800">{title}</h4>
              <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">{subtitle}</p>
           </div>
        </div>
        <div className="flex items-center gap-4">
           <div className="text-right mr-2">
              <p className={`text-xl font-black text-${color}-600 tabular-nums`}>{total.toFixed(0)} <small className="text-[10px] uppercase opacity-60">un</small></p>
              <p className="text-[10px] font-bold text-slate-400 uppercase">{items.length} SKUs</p>
           </div>
           <button 
             onClick={onToggle}
             className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all ${
               isOpen ? 'bg-slate-800 text-white' : `bg-${color}-100 text-${color}-600 hover:bg-${color}-200`
             }`}
           >
             {isOpen ? <Minus size={18} /> : <Plus size={18} />}
           </button>
        </div>
      </div>

      {isOpen && (
        <div className="bg-white rounded-[2rem] border border-slate-200 shadow-lg overflow-hidden animate-in zoom-in-95 duration-200">
           {items.length === 0 ? (
             <div className="p-12 text-center text-slate-400 italic text-sm">Nenhuma falta registrada nesta categoria.</div>
           ) : (
             <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead className="bg-slate-50/50 border-b border-slate-100 text-[10px] font-black text-slate-400 uppercase tracking-widest">
                    <tr>
                      <th className="px-6 py-4">SKU / Descrição</th>
                      <th className="px-6 py-4 text-center">Origem</th>
                      <th className="px-6 py-4 text-center">Data</th>
                      <th className="px-6 py-4 text-right">Quantidade</th>
                      <th className="px-6 py-4 text-center">Operador</th>
                      <th className="px-6 py-4 text-center">Ação</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {items.map(item => (
                      <tr key={item.id} className="hover:bg-slate-50/50 transition-colors group/row">
                        <td className="px-6 py-4">
                          <div className="flex flex-col">
                             <div className="flex items-center gap-2">
                               <span className="font-mono font-black text-slate-700">{item.sku}</span>
                               <button 
                                 onClick={() => copySku(item.sku)}
                                 className="p-1.5 rounded-lg bg-slate-100 text-slate-400 hover:bg-blue-50 hover:text-blue-500 opacity-0 group-hover/row:opacity-100 transition-all"
                                 title="Copiar SKU"
                               >
                                 <Copy size={12} />
                               </button>
                             </div>
                             <span className="text-[11px] text-slate-400 truncate max-w-xs">{item.description || '—'}</span>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-center">
                           <span className="bg-slate-100 px-2 py-1 rounded-lg text-[10px] font-bold text-slate-500 border border-slate-200">
                              {item.list_id || 'Avulsa'}
                           </span>
                        </td>
                        <td className="px-6 py-4 text-center">
                           <span className="text-[11px] font-medium text-slate-400 tabular-nums">
                              {new Date(item.created_at).toLocaleDateString('pt-BR')}
                           </span>
                        </td>
                        <td className="px-6 py-4 text-right">
                           <span className="text-lg font-black text-red-500">-{item.quantity.toFixed(0)}</span>
                        </td>
                        <td className="px-6 py-4 text-center">
                           <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest bg-slate-100 px-3 py-1.5 rounded-lg border border-slate-200 shadow-sm">
                             {item.operator_name || 'Admin'}
                           </span>
                        </td>
                        <td className="px-6 py-4 text-center">
                           <button 
                             onClick={() => onDelete(item.id)}
                             className="w-10 h-10 rounded-xl bg-slate-50 text-slate-400 hover:bg-red-50 hover:text-red-500 transition-all flex items-center justify-center border border-slate-100"
                             title="Remover Falta"
                           >
                             <Trash2 size={16} />
                           </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
             </div>
           )}
        </div>
      )}
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function Supervisor() {
  const compact = useCompactViewport(800)
  const { notify, askPrompt } = useFeedback()
  const navigate = useNavigate()
  const params = useParams()
  
  // marketplaceView e tab agora vêm totalmente da URL
  const marketplaceView = params.marketplace || null
  const tab = params.tab || 'overview'

  const [batches, setBatches] = useState([])
  const [sessions, setSessions] = useState([])
  const [printers, setPrinters] = useState([])
  const [form, setForm] = useState({ full_date: '', marketplace: 'ml' })
  const [files, setFiles] = useState({ pdf: null, txt: null })
  const [uploading, setUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState(null)
  const [archiveConfirm, setArchiveConfirm] = useState(null) 
  const [newPrinter, setNewPrinter] = useState({ name: '', ip_address: '', port: 9100 })
  const [excelFile, setExcelFile] = useState(null)
  const [excelResult, setExcelResult] = useState(null)
  const [importingExcel, setImportingExcel] = useState(false)
  const [agentInfo, setAgentInfo] = useState(null)
  const [shortageItems, setShortageItems] = useState([])
  const [lastRefresh, setLastRefresh] = useState(null)
  
  const agentCheckRef = useRef(false)
  const refreshIntervalRef = useRef(null)

  useEffect(() => {
    refresh()
    if (!agentCheckRef.current) { agentCheckRef.current = true; checkAgent() }
    refreshIntervalRef.current = setInterval(refresh, 60_000)
    return () => clearInterval(refreshIntervalRef.current)
  }, [])

  function checkAgent() {
    setAgentInfo(null)
    fetch('http://localhost:6543/status', { signal: AbortSignal.timeout(2000) })
      .then(r => r.json())
      .then(d => setAgentInfo({ ok: d.status === 'ok', printer: d.printer, allPrinters: d.all_printers || [] }))
      .catch(() => setAgentInfo({ ok: false, printer: null, allPrinters: [] }))
  }

  function refresh() {
    Promise.all([api.getSessions(), api.getPrinters(), api.listBatches(), api.getShortages()]).then(([s, p, b, sh]) => {
      setSessions(s); setPrinters(p); setBatches(b)
      setShortageItems(Array.isArray(sh) ? sh : [])
      setLastRefresh(new Date())
    })
  }

  async function doUpload(fd) {
    setUploading(true); setUploadResult(null)
    try {
      const res = await api.uploadSession(fd)
      if (res.status === 'needs_confirmation') {
        setArchiveConfirm({ ...res, pendingFd: fd }); return
      }
      setUploadResult({ ok: true, msg: `Lote "${res.batch_name}" criado (${res.lists_created} listas / ${res.total_items} unid.)` })
      setForm({ full_date: '', marketplace: form.marketplace })
      setFiles({ pdf: null, txt: null })
      refresh()
    } catch (err) { setUploadResult({ ok: false, msg: err.message }) }
    finally { setUploading(false) }
  }

  async function handleUpload(e) {
    e.preventDefault()
    if (!files.pdf) { notify('Selecione o PDF', 'warning'); return }
    if (!form.full_date) { notify('Informe a data', 'warning'); return }
    const fd = new FormData()
    fd.append('full_date', form.full_date)
    fd.append('marketplace', marketplaceView)
    fd.append('picking_pdf', files.pdf)
    if (files.txt) fd.append('labels_txt', files.txt)
    await doUpload(fd)
  }

  async function handleConfirmArchive() {
    if (!archiveConfirm) return
    const fd = archiveConfirm.pendingFd;
    fd.append('force_archive_batch_id', archiveConfirm.oldest_batch_id)
    setArchiveConfirm(null)
    await doUpload(fd)
  }

  async function handleAddPrinter(e) {
    e.preventDefault()
    await api.createPrinter(newPrinter.name, newPrinter.ip_address, Number(newPrinter.port))
    setNewPrinter({ name: '', ip_address: '', port: 9100 }); refresh()
  }

  async function handleImportExcel(e) {
    e.preventDefault()
    if (!excelFile) return
    setImportingExcel(true); setExcelResult(null)
    try {
      const fd = new FormData(); fd.append('file', excelFile)
      const res = await api.importBarcodesExcel(fd)
      setExcelResult({ ok: true, msg: `${res.added} novos EANs (${res.deleted ?? 0} substituídos)` })
    } catch (err) { setExcelResult({ ok: false, msg: err.message }) }
    finally { setImportingExcel(false) }
  }

  const timeSince = lastRefresh
    ? `${Math.round((Date.now() - lastRefresh) / 1000)}s atrás`
    : 'Buscando...'

  const visibleBatches = batches.filter(b => normalizeMarket(b.marketplace) === normalizeMarket(marketplaceView))
  const visibleSessions = sessions.filter(s => normalizeMarket(s.marketplace) === normalizeMarket(marketplaceView))
  const shortageStats = {
    totalUnits: shortageItems.reduce((sum, i) => sum + (i.quantity || 0), 0),
    skuCount: new Set(shortageItems.map(i => i.sku)).size,
    sessionCount: new Set(shortageItems.map(i => i.list_id)).size,
  }

  return (
    <div className={cn("w-full", compact && "compact-density")}>
      {/* ── SELEÇÃO DE HUB (Master Experience) ────────────────────── */}
      {marketplaceView === null && (
        <div className="flex flex-col items-center justify-center p-8 h-full min-h-[calc(100vh-64px)] overflow-hidden relative">
          <div className="absolute top-[-10%] left-[-5%] w-[40%] h-[40%] bg-blue-500/5 rounded-full blur-[120px] pointer-events-none" />
          <div className="absolute bottom-[-10%] right-[-5%] w-[40%] h-[40%] bg-emerald-500/5 rounded-full blur-[120px] pointer-events-none" />

          <div className="max-w-4xl w-full relative z-10">
            <div className="text-center mb-16 animate-in fade-in slide-in-from-bottom-6 duration-700">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 border border-blue-100 mb-6">
                <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
                <span className="text-[10px] font-black text-blue-600 uppercase tracking-[0.2em]">Painel do Administrador</span>
              </div>
              <h1 className="text-5xl font-black text-slate-900 tracking-tighter sm:text-6xl">
                Olá, <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">Master</span>
              </h1>
              <p className="text-xl text-slate-500 mt-4 font-medium max-w-xl mx-auto leading-relaxed italic">
                A nave completa aguarda seu comando. Qual braço operacional deseja supervisionar hoje?
              </p>
            </div>
            
            <div className="flex flex-col md:flex-row justify-center items-start gap-12 md:gap-24 px-4 max-w-5xl mx-auto stagger-children pt-6 pb-20">
              {/* MERCADO LIVRE HUB ICON */}
              <button 
                onClick={() => navigate('/supervisor/ml/overview')} 
                className="group relative flex flex-col items-center outline-none animate-in fade-in slide-in-from-bottom-10 duration-1000 delay-100 p-4"
              >
                <div className="relative w-56 h-32 md:w-64 md:h-40 flex items-center justify-center transition-all duration-700 ease-[cubic-bezier(0.23,1,0.32,1)] group-hover:scale-110 group-hover:-translate-y-2">
                  <div className="absolute inset-0 bg-yellow-400/10 blur-[40px] opacity-0 group-hover:opacity-100 transition-opacity duration-700 rounded-full scale-75" />
                  <div className="relative z-10 drop-shadow-[0_10px_20px_rgba(250,204,21,0.1)] group-hover:drop-shadow-[0_30px_60px_rgba(250,204,21,0.3)] transition-all duration-700">
                    <MarketplaceLogo marketplace="ml" size={150} />
                  </div>
                </div>
                <div className="mt-4 flex flex-col items-center gap-1.5 opacity-40 group-hover:opacity-100 transition-all duration-500">
                  <span className="text-[9px] font-black text-yellow-700 uppercase tracking-[0.4em] px-3 py-1 bg-yellow-400/10 rounded-full border border-yellow-400/20 shadow-sm">Supervisão Full</span>
                  <div className="w-1 h-1 rounded-full bg-yellow-400 animate-pulse" />
                </div>
              </button>

              {/* SHOPEE HUB ICON */}
              <button 
                onClick={() => navigate('/supervisor/shopee/overview')} 
                className="group relative flex flex-col items-center outline-none animate-in fade-in slide-in-from-bottom-10 duration-1000 delay-200 p-4"
              >
                <div className="relative w-56 h-32 md:w-64 md:h-40 flex items-center justify-center transition-all duration-700 ease-[cubic-bezier(0.23,1,0.32,1)] group-hover:scale-110 group-hover:-translate-y-2">
                  <div className="absolute inset-0 bg-orange-500/10 blur-[40px] opacity-0 group-hover:opacity-100 transition-opacity duration-700 rounded-full scale-75" />
                  <div className="relative z-10 drop-shadow-[0_10px_20px_rgba(249,115,22,0.15)] group-hover:drop-shadow-[0_30px_60px_rgba(249,115,22,0.3)] transition-all duration-700">
                    <MarketplaceLogo marketplace="shopee" size={150} />
                  </div>
                </div>
                <div className="mt-4 flex flex-col items-center gap-1.5 opacity-40 group-hover:opacity-100 transition-all duration-500">
                  <span className="text-[9px] font-black text-orange-700 uppercase tracking-[0.4em] px-3 py-1 bg-orange-500/10 rounded-full border border-orange-500/20 shadow-sm">Supervisão Full</span>
                  <div className="w-1 h-1 rounded-full bg-orange-500 animate-pulse" />
                </div>
              </button>
            </div>

            {/* VOLTAR / LOGOUT BUTTON */}
            <div className="mt-20 flex justify-center animate-in fade-in slide-in-from-bottom-4 duration-1000 delay-500">
               <button 
                 onClick={() => {
                   sessionStorage.removeItem('operator');
                   navigate('/');
                 }}
                 className="group flex items-center gap-3 px-6 py-2.5 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 hover:text-slate-800 border border-slate-200 shadow-sm transition-all duration-300"
               >
                 <LogOut size={16} className="group-hover:-translate-x-1 transition-transform" />
                 <span className="text-[11px] font-black uppercase tracking-[0.2em]">Voltar para Seleção de Operador</span>
               </button>
            </div>
          </div>
        </div>
      )}

      {/* ── DASHBOARD PRINCIPAL ────────────────────────────────────────────── */}
      {marketplaceView !== null && (
        <div className="flex flex-col h-full min-h-[calc(100vh-64px)] bg-slate-50">
          
          {/* Header de Contexto (Breadcrumb/Banner) */}
          <div className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between sticky top-0 z-10 md:static">
             <div className="flex items-center gap-4">
               <button
                 onClick={() => {
                   if (tab !== 'overview') navigate(`/supervisor/${marketplaceView}/overview`)
                   else navigate('/supervisor')
                 }}
                 className="p-2 hover:bg-slate-100 rounded-full transition-colors text-slate-400 hover:text-blue-600"
               >
                 <ArrowLeft size={20} />
               </button>
               <div className="flex items-center gap-3">
                 <div className="w-10 h-10 rounded-xl bg-slate-50 border border-slate-100 flex justify-center items-center">
                   <MarketplaceLogo marketplace={marketplaceView} size={24} />
                 </div>
                 <div>
                   <h2 className="text-lg font-black text-slate-900 leading-none">Supervisão {marketplaceView === 'ml' ? 'Mercado Livre' : 'Shopee'}</h2>
                   <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mt-1">Conectado • {timeSince}</p>
                 </div>
               </div>
             </div>
             
             <div className="flex items-center gap-3">
               <div className="px-3 py-1.5 rounded-lg bg-emerald-50 border border-emerald-100 text-emerald-700 text-[10px] font-bold uppercase tracking-widest flex items-center gap-2">
                 <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" /> Sincronizado
               </div>
               <button onClick={refresh} className="p-2 text-slate-400 hover:bg-slate-50 hover:text-blue-600 rounded-lg transition-colors border border-transparent hover:border-slate-200">
                 <Activity size={18} />
               </button>
             </div>
          </div>

          {/* Main Content Area */}
          <main className="flex-1 p-3 md:p-4 overflow-auto">
            <div className="max-w-7xl mx-auto animate-in fade-in slide-in-from-bottom-2 duration-500">
              
              {tab === 'overview' && (
                <div className="flex flex-col gap-3">
                  <ProgressHero sessions={visibleSessions} shortageStats={shortageStats} compact={compact} />
                  <OperatorRanking batches={visibleBatches} marketplace={marketplaceView} compact={compact} />
                </div>
              )}

              {tab === 'shortage' && (
                <ShortageSection />
              )}

              {tab === 'lists' && (() => {
                const batchSessionIds = new Set(visibleBatches.flatMap(b => b.sessions.map(s => s.id)))
                const orphanSessions  = visibleSessions.filter(s => !batchSessionIds.has(s.id))
                return (
                  <div className="flex flex-col gap-10">
                    {/* Lotes Ativos */}
                    {visibleBatches.filter(b => b.status === 'active').length > 0 && (
                      <div>
                        <h3 className="text-sm font-bold text-slate-800 uppercase tracking-widest mb-4 flex items-center gap-2">
                          <Folder size={16} className="text-blue-500"/> Lotes Ativos
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-5">
                          {visibleBatches.filter(b => b.status === 'active').map(batch => {
                            const bPct = batch.pct || 0
                            const active    = batch.sessions.filter(s => s.status === 'in_progress').length
                            const available = batch.sessions.filter(s => s.status === 'open').length
                            const done      = batch.sessions.filter(s => s.status === 'completed').length
                            return (
                              <button key={batch.id} onClick={() => navigate(`/supervisor/batch/${batch.id}`)}
                                className="bg-white text-left rounded-2xl border border-slate-200 shadow-sm hover:shadow-lg hover:border-blue-300 hover:-translate-y-1 transition-all overflow-hidden group">
                                <div className="p-6">
                                  <div className="flex items-start justify-between mb-5">
                                    <div>
                                      <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center mb-3">
                                        <Package size={20} strokeWidth={2.5} />
                                      </div>
                                      <p className="font-black text-slate-900 text-lg leading-tight">{batch.name}</p>
                                      <p className="text-xs font-medium text-slate-500 mt-1">{batch.sessions.length} listas · {batch.total_items.toLocaleString('pt-BR')} itens</p>
                                    </div>
                                    <p className="text-2xl font-black text-slate-800 tabular-nums bg-slate-50 px-3 py-1 rounded-xl border border-slate-100">{bPct}<span className="text-sm text-slate-400">%</span></p>
                                  </div>
                                  <div className="h-2 bg-slate-100 rounded-full overflow-hidden mb-5">
                                    <div className={cn("h-full rounded-full transition-all duration-700", bPct >= 90 ? "bg-emerald-500" : bPct >= 50 ? "bg-blue-500" : "bg-amber-500")} style={{ width: `${bPct}%` }} />
                                  </div>
                                  <div className="flex gap-2 flex-wrap">
                                    {active > 0    && <span className="text-[10px] font-bold uppercase tracking-wider bg-blue-50 border border-blue-100 text-blue-700 px-2.5 py-1 rounded-md">Ativas {active}</span>}
                                    {available > 0 && <span className="text-[10px] font-bold uppercase tracking-wider bg-slate-50 border border-slate-200 text-slate-600 px-2.5 py-1 rounded-md">Abertas {available}</span>}
                                    {done > 0      && <span className="text-[10px] font-bold uppercase tracking-wider bg-emerald-50 border border-emerald-100 text-emerald-700 px-2.5 py-1 rounded-md">Picks {done}</span>}
                                  </div>
                                </div>
                                <div className="px-6 py-3 bg-slate-50/50 border-t border-slate-100 flex items-center justify-between text-xs font-bold text-slate-400">
                                  <span>{batch.total_picked.toLocaleString()} / {batch.total_items.toLocaleString()}</span>
                                  <span className="text-blue-600 group-hover:underline flex items-center gap-1">Supervisionar <ArrowLeft size={12} className="rotate-180" /></span>
                                </div>
                              </button>
                            )
                          })}
                        </div>
                      </div>
                    )}

                    {/* Lotes Arquivados */}
                    {visibleBatches.filter(b => b.status === 'archived').length > 0 && (
                      <div className="mt-8">
                        <h3 className="text-sm font-bold text-slate-600 uppercase tracking-widest mb-4 flex items-center gap-2 opacity-80">
                          <Activity size={16}/> Lotes Arquivados (Histórico)
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          {visibleBatches.filter(b => b.status === 'archived').map(batch => (
                            <button key={batch.id} onClick={() => navigate(`/supervisor/batch/${batch.id}`)}
                              className="bg-white text-left rounded-xl border border-slate-200 shadow-sm opacity-70 hover:opacity-100 transition-all group overflow-hidden">
                              <div className="p-4 flex items-center justify-between">
                                <div>
                                  <p className="font-bold text-slate-700 truncate">{batch.name}</p>
                                  <p className="text-xs text-slate-400 mt-0.5">{batch.sessions.length} listas integradas</p>
                                </div>
                                <span className="text-xs font-bold bg-slate-100 text-slate-500 px-2 py-1 rounded-md border border-slate-200">{batch.pct || 0}%</span>
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Listas Avulsas Agrupadas por Data */}
                    {orphanSessions.length > 0 && (() => {
                      // Agrupar sessions por data extraída do código (DD-MM-YYYY)
                      const groups = orphanSessions.reduce((acc, s) => {
                        const match = s.session_code.match(/(\d{2}-\d{2}-\d{4})/);
                        const dateKey = match ? match[1] : 'Outros';
                        if (!acc[dateKey]) acc[dateKey] = [];
                        acc[dateKey].push(s);
                        return acc;
                      }, {});

                      // Ordenar datas (mais recentes primeiro ou conforme preferência)
                      const sortedDates = Object.keys(groups).sort((a, b) => {
                        if (a === 'Outros') return 1;
                        if (b === 'Outros') return -1;
                        const [da, ma, ya] = a.split('-').map(Number);
                        const [db, mb, yb] = b.split('-').map(Number);
                        return new Date(ya, ma-1, da) - new Date(yb, mb-1, db);
                      });

                      return (
                        <div className="mt-10 space-y-6">
                          <div className="flex items-center justify-between px-2">
                             <div className="flex items-center gap-3">
                               <div className="w-10 h-10 rounded-xl bg-orange-100 text-orange-600 flex justify-center items-center shadow-sm">
                                 <AlertCircle size={20} strokeWidth={2.5}/>
                               </div>
                               <div>
                                 <h3 className="text-lg font-black text-slate-800 tracking-tight">Listas Avulsas</h3>
                                 <p className="text-xs font-semibold text-slate-500">Operações segmentadas por data de entrega</p>
                               </div>
                             </div>
                             <span className="badge-soft bg-orange-50 border-orange-100 text-orange-700">{orphanSessions.length} total</span>
                          </div>

                          <div className="grid grid-cols-1 gap-4">
                            {sortedDates.map(dateKey => {
                              const dateSessions = groups[dateKey];
                              const totalItems = dateSessions.reduce((sum, s) => sum + (s.items_total || 0), 0);
                              const pickedItems = dateSessions.reduce((sum, s) => sum + (s.items_picked || 0), 0);
                              const groupPct = totalItems ? Math.round((pickedItems / totalItems) * 100) : 0;
                              const isCompleted = groupPct === 100;

                              return (
                                <details key={dateKey} className="group overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm hover:shadow-md transition-all">
                                  <summary className="flex items-center justify-between p-5 cursor-pointer list-none select-none bg-white hover:bg-slate-50 transition-colors">
                                    <div className="flex items-center gap-4">
                                      <div className={cn(
                                        "w-12 h-12 rounded-xl flex flex-col items-center justify-center border font-black transition-colors",
                                        isCompleted ? "bg-emerald-50 border-emerald-100 text-emerald-600" : "bg-slate-100 border-slate-200 text-slate-600 group-hover:bg-blue-50 group-hover:border-blue-100 group-hover:text-blue-600"
                                      )}>
                                        <span className="text-[10px] uppercase leading-none opacity-60">Dia</span>
                                        <span className="text-lg leading-tight">{dateKey.split('-')[0]}</span>
                                      </div>
                                      <div>
                                        <p className="font-black text-slate-900 flex items-center gap-2">
                                          {dateKey === 'Outros' ? 'Sem Data Definida' : dateKey.replace(/-/g, '/')}
                                          {isCompleted && <CheckCircle size={14} className="text-emerald-500" />}
                                        </p>
                                        <p className="text-[11px] font-bold text-slate-500 uppercase tracking-widest mt-0.5">
                                          {dateSessions.length} {dateSessions.length === 1 ? 'Lista' : 'Listas'} · {totalItems.toLocaleString()} itens
                                        </p>
                                      </div>
                                    </div>
                                    
                                    <div className="flex items-center gap-6">
                                      <div className="hidden md:flex flex-col items-end gap-1.5">
                                        <div className="flex items-center gap-2">
                                          <span className="text-[10px] font-black text-slate-400 uppercase tracking-tighter">Progresso</span>
                                          <span className="text-sm font-black text-slate-800 tabular-nums">{groupPct}%</span>
                                        </div>
                                        <div className="w-24 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                                          <div className={cn("h-full rounded-full transition-all duration-1000", isCompleted ? "bg-emerald-500" : "bg-blue-600")} style={{ width: `${groupPct}%` }} />
                                        </div>
                                      </div>
                                      <div className="w-8 h-8 rounded-full border border-slate-200 flex items-center justify-center text-slate-400 group-open:rotate-180 transition-transform bg-white group-hover:border-blue-200 group-hover:text-blue-600 shadow-sm">
                                        <ArrowRight size={14} className="rotate-90" />
                                      </div>
                                    </div>
                                  </summary>
                                  <div className="border-t border-slate-100 divide-y divide-slate-50 bg-slate-50/30">
                                    {dateSessions.sort((a, b) => b.id - a.id).map(s => (
                                      <SessionRow key={s.id} s={s} onDeleted={refresh} />
                                    ))}
                                  </div>
                                </details>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                )
              })()}

              {tab === 'tools' && (
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
                  <ToolCard icon={UploadCloud} title="Carga de Coleta" description="Carregue o PDF de remessa da operação. O WMS irá fragmentar e distribuir em lotes." accentColor="blue">
                    {archiveConfirm && (
                      <div className="mb-5 p-4 bg-red-50 border border-red-200 rounded-xl">
                        <p className="text-sm font-bold text-red-800 flex items-center gap-2 mb-2"><AlertCircle size={16}/> Capacidade Excedida</p>
                        <p className="text-sm text-red-700/80 mb-4">{archiveConfirm.msg}</p>
                        <div className="flex gap-2">
                          <button onClick={() => setArchiveConfirm(null)} className="flex-1 py-2 rounded-lg bg-white border border-slate-200 text-slate-600 text-sm font-bold">Cancelar</button>
                          <button onClick={handleConfirmArchive} className="flex-1 py-2 rounded-lg bg-red-600 text-white text-sm font-bold">Proceder</button>
                        </div>
                      </div>
                    )}
                    <form onSubmit={handleUpload} className="flex flex-col gap-5">
                      <div>
                        <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">Data Alvo</label>
                        <input type="date" required value={form.full_date} onChange={e => setForm(f => ({ ...f, full_date: e.target.value }))}
                          className="w-full bg-white border-2 border-slate-200 rounded-xl p-3 text-sm" />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">Documento PDF</label>
                        <input type="file" accept=".pdf" required onChange={e => setFiles(f => ({ ...f, pdf: e.target.files[0] }))}
                          className="w-full bg-white border-2 border-slate-200 rounded-xl p-3 text-sm file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-bold file:bg-blue-50 file:text-blue-700" />
                      </div>
                      <button type="submit" disabled={uploading} className="mt-2 py-3.5 bg-blue-600 text-white rounded-xl text-sm font-bold shadow-sm disabled:opacity-50">
                        {uploading ? 'Fragmentando...' : 'PROCESSAR CARGA'}
                      </button>
                      {uploadResult && <p className={cn("text-center text-sm font-bold p-3 rounded-lg bg-white border", uploadResult.ok ? "text-emerald-600" : "text-red-600")}>{uploadResult.msg}</p>}
                    </form>
                  </ToolCard>

                  <div className="flex flex-col gap-8">
                    <ToolCard icon={FileText} title="Sincronizar Catálogo EAN" description="Atualize a planilha de SKUs da operação ativa." accentColor="green">
                      <form onSubmit={handleImportExcel} className="flex flex-col gap-4">
                        <input type="file" accept=".xlsx" required onChange={e => setExcelFile(e.target.files[0])}
                          className="w-full bg-white border-2 border-slate-200 rounded-xl p-3 text-sm file:mr-4 file:py-2 file:px-4 file:rounded-lg file:bg-emerald-50 file:text-emerald-700" />
                        <button type="submit" disabled={importingExcel || !excelFile} className="py-3 bg-white border-2 border-emerald-500 text-emerald-600 rounded-xl text-sm font-bold hover:bg-emerald-50 shadow-sm disabled:opacity-50">
                          {importingExcel ? 'Sincronizando...' : 'IMPORTAR PLANILHA'}
                        </button>
                        {excelResult && <p className={cn("text-center text-sm font-bold", excelResult.ok ? "text-emerald-600" : "text-red-600")}>{excelResult.msg}</p>}
                      </form>
                    </ToolCard>
                  </div>
                </div>
              )}

              {tab === 'settings' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                  <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8 h-fit">
                    <div className="flex items-center gap-3 mb-6">
                      <div className="w-10 h-10 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center"><Printer size={20} /></div>
                      <h2 className="text-lg font-black text-slate-800 leading-tight">Periféricos e Impressão</h2>
                    </div>
                    {/* Rest of the settings logic preserved */}
                    <div className="bg-slate-50 border border-slate-100 rounded-xl p-4 mb-8 flex justify-between items-center">
                       <div>
                         <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1">Status do Agente Local</p>
                         {agentInfo?.ok ? <p className="text-sm font-bold text-emerald-600">Online ({agentInfo.printer})</p> : <p className="text-sm font-bold text-slate-400">Desconectado</p>}
                       </div>
                       <Activity size={16} className="text-slate-300" />
                    </div>
                    <div className="divide-y divide-slate-100">
                      {printers.map(p => (
                        <div key={p.id} className="py-3 flex justify-between">
                          <span className="font-bold text-sm text-slate-700">{p.name}</span>
                          <span className="font-mono text-xs text-slate-400">{p.ip_address}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </main>
        </div>
      )}
    </div>
  )
}
