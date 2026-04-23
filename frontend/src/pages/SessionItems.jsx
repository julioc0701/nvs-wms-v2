import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import MarketplaceLogo from '../components/MarketplaceLogo'

const STATUS_COLOR = {
  pending: 'text-gray-400',
  in_progress: 'text-blue-600',
  complete: 'text-green-600',
  partial: 'text-orange-500',
  out_of_stock: 'text-red-500',
}

const STATUS_LABEL = {
  pending: 'Pendente',
  in_progress: 'Em separação',
  complete: '✓ Completo',
  partial: '⚠ Parcial',
  out_of_stock: '✗ Sem estoque',
}

// Statuses that can be reset
const RESETTABLE = ['complete', 'partial', 'out_of_stock', 'in_progress']

export default function SessionItems() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const operator = JSON.parse(localStorage.getItem('operator') || 'null')

  const [session, setSession] = useState(null)
  const [items, setItems] = useState([])
  const [barcode, setBarcode] = useState('')
  const [errMsg, setErrMsg] = useState(null)
  const [loading, setLoading] = useState(true)
  const [confirmResetAll, setConfirmResetAll] = useState(false)
  const [resettingAll, setResettingAll] = useState(false)
  const inputRef = useRef()

  useEffect(() => {
    if (!operator) { navigate('/'); return }
    loadAll()
  }, [sessionId])

  function loadAll() {
    return Promise.all([api.getSession(sessionId), api.getItems(sessionId)])
      .then(([s, its]) => { setSession(s); setItems(its) })
      .finally(() => { setLoading(false); setTimeout(() => inputRef.current?.focus(), 100) })
  }

  function goToPicking(sku) {
    navigate(`/picking/${sessionId}?sku=${encodeURIComponent(sku)}`)
  }

  async function handleScan(e) {
    if (e.key !== 'Enter' || !barcode.trim()) return
    const code = barcode.trim()
    setBarcode('')
    setErrMsg(null)

    const bySkU = items.find(i => i.sku === code)
    if (bySkU) { goToPicking(bySkU.sku); return }

    try {
      const res = await api.resolveBarcode(code)
      // Check all SKUs returned (a barcode can now be linked to multiple SKUs)
      const resolvedSkus = res.skus || [res.sku]
      const found = items.find(i => resolvedSkus.includes(i.sku))

      if (found) { goToPicking(found.sku); return }
      setErrMsg(`SKU(s) "${resolvedSkus.join(', ')}" não encontrado(s) nesta lista`)
    } catch {
      setErrMsg('Código de barras não encontrado')
    }

    setTimeout(() => setErrMsg(null), 3000)
    inputRef.current?.focus()
  }

  async function handleResetAll() {
    setResettingAll(true)
    try {
      await api.resetAllItems(sessionId, operator.id)
      await loadAll()
      setConfirmResetAll(false)
    } catch (err) {
      setErrMsg(err.message)
    } finally {
      setResettingAll(false)
    }
  }

  if (loading) return (
    <div className="flex flex-col items-center justify-center min-h-screen text-slate-400 gap-4 bg-slate-50">
      <div className="w-8 h-8 rounded-full border-4 border-slate-200 border-t-slate-400 animate-spin"/>
      <span className="font-bold tracking-widest text-sm uppercase">Carregando Itens...</span>
    </div>
  )

  const progress = session?.progress || {}
  const pct = progress.items_total
    ? Math.round((progress.items_picked / progress.items_total) * 100)
    : 0

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col">

      {/* Header Imersivo */}
      <div className="bg-slate-900 border-b border-slate-800 shadow-sm px-4 md:px-8 py-5 flex flex-col md:flex-row md:items-center justify-between gap-4 sticky top-0 z-20">
        <div className="flex items-center justify-between md:justify-start gap-6 w-full md:w-auto">
          <div className="flex items-center gap-4">
            <button onClick={() => navigate('/sessions')} className="p-2 -ml-2 text-slate-300 hover:text-white hover:bg-slate-800 rounded-xl transition-colors shrink-0">
               <span className="text-xl font-bold">←</span>
            </button>
            <div className="flex flex-col">
              <span className="text-xl font-black text-white flex items-center gap-3">
                <MarketplaceLogo marketplace={session?.marketplace} size={24} className="brightness-0 invert drop-shadow-[0_0_8px_rgba(255,255,255,0.3)]"/> 
                {session?.session_code}
              </span>
              <span className="text-xs font-bold text-slate-400 uppercase tracking-widest mt-1">
                Operador: <span className="text-blue-400">{operator?.name}</span>
              </span>
            </div>
          </div>
        </div>

        <div className="flex flex-col items-end gap-2 text-slate-300 pointer-events-none">
          <div className="flex items-center gap-3 font-mono text-sm">
             <span className="flex items-center gap-2"><strong className="text-white text-lg">{progress.items_picked}</strong> / {progress.items_total} un</span>
             <span className="text-slate-600">|</span>
             <span className="flex items-center gap-2"><strong className="text-white text-lg">{progress.skus_complete}</strong> / {progress.skus_total} sku</span>
          </div>
          <div className="w-full md:w-64 h-2 bg-slate-800 rounded-full overflow-hidden shadow-inner">
            <div className="h-full bg-blue-500 rounded-full transition-all duration-700 ease-out" style={{ width: `${pct}%` }} />
          </div>
        </div>
      </div>

      <div className="flex-1 p-4 md:p-8 max-w-5xl mx-auto w-full flex flex-col gap-8">

        {/* Scanner */}
        <div className="bg-white rounded-[2rem] shadow-sm border border-slate-200 p-8 flex flex-col items-center">
          <p className="text-center text-slate-400 text-xs font-bold mb-4 uppercase tracking-[0.2em]">
            Bipe ou digite para iniciar a separação
          </p>
          <div className="relative w-full max-w-xl">
            <input
              ref={inputRef}
              className="w-full text-center text-2xl font-mono font-bold bg-slate-50 border-2 border-slate-200 rounded-2xl py-5 px-6 outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100 transition-all placeholder-slate-300"
              placeholder="▐ _ ▌"
              value={barcode}
              onChange={e => setBarcode(e.target.value)}
              onKeyDown={handleScan}
              autoFocus
            />
          </div>
          {errMsg && <p className="text-center text-red-500 font-bold mt-4 text-sm bg-red-50 px-4 py-2 rounded-lg">{errMsg}</p>}
        </div>

        {/* Tabela de itens */}
        <div className="bg-white rounded-[2rem] shadow-sm border border-slate-200 overflow-hidden">

          {/* Cabeçalho */}
          <div className="flex justify-between items-center px-6 py-4 bg-slate-50 border-b border-slate-100">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-widest">
              Inventário ({items.length} skus)
            </span>

            {!confirmResetAll ? (
              <button
                onClick={() => setConfirmResetAll(true)}
                className="text-xs font-bold text-orange-600 hover:text-white border border-orange-200 hover:bg-orange-500 rounded-lg px-4 py-2 transition-all shadow-sm bg-white"
              >
                ↺ RST TOTAL
              </button>
            ) : (
              <div className="flex items-center gap-3 bg-white px-3 py-1.5 rounded-xl border border-orange-200 shadow-sm">
                <span className="text-xs text-slate-600 font-bold uppercase tracking-wide px-2">Zerar operação?</span>
                <button
                  onClick={() => setConfirmResetAll(false)}
                  className="text-xs text-slate-500 hover:text-slate-800 font-bold px-3 py-1.5 transition-colors"
                >
                  NÃO
                </button>
                <button
                  onClick={handleResetAll}
                  disabled={resettingAll}
                  className="text-xs bg-orange-500 text-white rounded-lg px-4 py-1.5 font-bold hover:bg-orange-600 disabled:opacity-60 transition-colors"
                >
                  {resettingAll ? 'Aguarde...' : 'SIM, ZERAR'}
                </button>
              </div>
            )}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-left border-collapse">
              <thead>
                <tr className="text-slate-400 uppercase text-[10px] font-bold tracking-widest border-b border-slate-100">
                  <th className="px-6 py-4">SKU do Produto</th>
                  <th className="px-6 py-4 hidden md:table-cell">Descrição</th>
                  <th className="px-6 py-4 text-center">Unidades</th>
                  <th className="px-6 py-4 text-right">Situação</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map(i => (
                  <ItemRow
                    key={i.sku}
                    item={i}
                    sessionId={sessionId}
                    operator={operator}
                    onNavigate={goToPicking}
                    onReset={loadAll}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  )
}

function ItemRow({ item, sessionId, operator, onNavigate, onReset }) {
  const [confirmReset, setConfirmReset] = useState(false)
  const [resetting, setResetting] = useState(false)

  const canReset = RESETTABLE.includes(item.status)

  async function doReset(e) {
    e.stopPropagation()
    setResetting(true)
    try {
      await api.resetItem(sessionId, item.sku, operator.id)
      await onReset()
      setConfirmReset(false)
    } finally {
      setResetting(false)
    }
  }

  async function doForceComplete(e) {
    e.stopPropagation()
    setResetting(true)
    try {
      await api.forceCompleteItem(sessionId, item.sku, operator.id)
      await onReset()
      setConfirmReset(false)
    } finally {
      setResetting(false)
    }
  }

  return (
    <tr
      onClick={() => onNavigate(item.sku)}
      className="group hover:bg-slate-50/80 cursor-pointer transition-colors"
    >
      <td className="px-6 py-5 align-middle">
        <span className="inline-flex items-center whitespace-nowrap font-mono font-black text-sm md:text-base text-slate-700 bg-white border border-slate-200 px-3 py-1.5 rounded-lg shadow-sm group-hover:border-blue-300 transition-colors">
          {item.sku}
        </span>
      </td>
      <td className="px-6 py-5 align-middle hidden md:table-cell">
        <div className="text-sm font-medium text-slate-500 line-clamp-2 max-w-sm group-hover:text-slate-800 transition-colors">
          {item.description || <span className="italic opacity-50">Sem descrição</span>}
        </div>
      </td>
      <td className="px-6 py-5 align-middle text-center">
        <span className="text-xl font-black text-slate-800 tabular-nums">{item.qty_required}</span>
        <span className="text-xs font-bold text-slate-400 ml-1">un</span>
      </td>

      {/* Status */}
      <td className="px-6 py-5 align-middle text-right" onClick={e => e.stopPropagation()}>
        {!confirmReset ? (
          <button
            onClick={() => setConfirmReset(true)}
            title="Ajuste manual de integridade"
            className={`whitespace-nowrap leading-none font-bold text-xs uppercase tracking-wide px-3 py-2 rounded-full border transition-all ${
              item.status === 'complete' ? 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100' :
              item.status === 'pending' ? 'bg-slate-50 text-slate-500 border-slate-200 hover:bg-slate-100' :
              item.status === 'out_of_stock' ? 'bg-red-50 text-red-600 border-red-200 hover:bg-red-100' :
              item.status === 'partial' ? 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100' :
              'bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100'
            }`}
          >
            {STATUS_LABEL[item.status] || item.status}
          </button>
        ) : (
          <div className="flex items-center justify-end gap-2 bg-white px-2 py-1 rounded-xl shadow-sm border border-slate-200 inline-flex whitespace-nowrap">
            {item.status !== 'pending' && (
              <button
                onClick={doReset}
                disabled={resetting}
                className="min-w-[92px] text-[11px] font-black uppercase tracking-wide bg-orange-100 text-orange-700 border border-orange-200 rounded-lg px-3 py-2 hover:bg-orange-500 hover:text-white transition-all disabled:opacity-50"
              >
                {resetting ? '...' : 'Resetar'}
              </button>
            )}
            {item.status !== 'complete' && (
              <button
                onClick={doForceComplete}
                disabled={resetting}
                className="min-w-[92px] text-[11px] font-black uppercase tracking-wide bg-emerald-100 text-emerald-700 border border-emerald-200 rounded-lg px-3 py-2 hover:bg-emerald-500 hover:text-white transition-all disabled:opacity-50"
              >
                {resetting ? '...' : 'Concluir'}
              </button>
            )}
            <button
              onClick={e => { e.stopPropagation(); setConfirmReset(false) }}
              className="p-1.5 text-slate-400 hover:text-slate-800 transition-colors rounded-lg hover:bg-slate-100"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
            </button>
          </div>
        )}
      </td>
    </tr>
  )
}
