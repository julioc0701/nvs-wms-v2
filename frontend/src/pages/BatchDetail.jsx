import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import Card from '../components/ui/Card'
import PageHeader from '../components/ui/PageHeader'
import Button from '../components/ui/Button'
import SkeletonRows from '../components/ui/SkeletonRows'
import { RefreshCcw, PackageX, FolderArchive, Plus, X, Trash2, Search } from 'lucide-react'
import { useFeedback } from '../components/ui/FeedbackProvider'
import { ProgressHero, OperatorRanking } from './Supervisor'

function normalizeMarket(value) {
  const v = String(value || '').toLowerCase()
  if (v === 'ml' || v === 'mercado_livre' || v === 'mercadolivre' || v === 'mercado livre') return 'ml'
  if (v === 'shopee') return 'shopee'
  return v
}

// ── Icons ─────────────────────────────────────────────────────────────────────
function TrashIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6M14 11v6" />
      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    </svg>
  )
}

// ── SessionRow (full detail, same as Supervisor) ───────────────────────────────
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
    <div className="border-b last:border-0">
      <div className="flex items-center gap-4 py-3">
        <span className="font-mono font-semibold w-48 truncate text-sm">{s.session_code}</span>
        <span className="text-gray-500 w-28 text-sm truncate">{s.operator_name || '—'}</span>
        <div className="flex-1 flex items-center gap-2">
          <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
            <div className="h-full bg-blue-500 rounded-full transition-all" style={{ width: `${pct}%` }} />
          </div>
          <span className="text-sm text-gray-600 whitespace-nowrap">{s.items_picked}/{s.items_total}</span>
        </div>
        <button onClick={toggleDetails} className="text-sm text-blue-500 hover:underline px-2">
          {details ? 'Ocultar' : 'Ver SKUs'}
        </button>
        {(s.status === 'completed' || s.status === 'in_progress') && !confirmReopen ? (
          <button
            onClick={() => setConfirmReopen(true)} disabled={reopening}
            className={`text-sm font-medium w-28 text-right disabled:opacity-50 hover:underline ${
              s.status === 'completed' ? 'text-green-600 hover:text-blue-600' : 'text-blue-600 hover:text-orange-500'
            }`}
          >
            {reopening ? 'Aguarde...' : s.status === 'completed' ? '✓ Concluída' : 'Em andamento'}
          </button>
        ) : s.status === 'open' ? (
          <span className="text-sm font-medium w-28 text-right text-gray-500">Disponível</span>
        ) : null}

        {confirmReopen && (
          <div className="flex items-center gap-1 w-28 justify-end">
            <button onClick={() => setConfirmReopen(false)} className="px-2 py-1 text-xs rounded border border-gray-300 hover:bg-gray-100">Não</button>
            <button onClick={doReopen} disabled={reopening} className="px-2 py-1 text-xs rounded bg-orange-500 text-white hover:bg-orange-600 disabled:opacity-50">Sim</button>
          </div>
        )}
        {!confirm ? (
          <button onClick={handleDelete} title="Excluir lista"
            className={`p-1.5 rounded-lg transition-colors text-gray-400 hover:text-red-500 hover:bg-red-50`}>
            <TrashIcon />
          </button>
        ) : (
          <div className="flex items-center gap-1">
            <button onClick={() => setConfirm(false)} className="px-2 py-1 text-xs rounded border border-gray-300 hover:bg-gray-100">Não</button>
            <button onClick={confirmDelete} disabled={deleting} className="px-2 py-1 text-xs rounded bg-red-500 text-white hover:bg-red-600 disabled:opacity-50">{deleting ? '...' : 'Sim'}</button>
          </div>
        )}
      </div>
      {confirmReopen && <p className="text-xs text-orange-500 pb-2 pl-1">Reinicializar esta lista? O operador perderá o acesso.</p>}
      {confirm && !deleting && <p className="text-xs text-red-500 pb-2 pl-1">Excluir esta lista? Esta ação não pode ser desfeita.</p>}
      {errMsg && <p className="text-xs text-red-500 pb-2 pl-1">{errMsg}</p>}

      {details && (
        <div className="bg-gray-50 m-2 rounded-xl p-4 border-2 border-gray-100">
          {loadingItems ? (
            <p className="text-center text-gray-400">Carregando itens...</p>
          ) : (
            <div className="overflow-x-auto"><table className="w-full text-sm min-w-[480px]">
              <thead>
                <tr className="text-gray-400 text-left border-b border-gray-200">
                  <th className="pb-2 font-medium">SKU</th>
                  <th className="pb-2 font-medium">Qtd</th>
                  <th className="pb-2 font-medium w-1/4">Obs</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 font-medium text-right">Ações</th>
                </tr>
              </thead>
              <tbody>
                {items.map(item => (
                  <tr key={item.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-100/50 transition-colors">
                    <td className="py-2 font-mono">{item.sku}</td>
                    <td className="py-2">{item.qty_picked}/{item.qty_required}</td>
                    <td className="py-2">
                      <div
                        onClick={async (e) => {
                          e.stopPropagation()
                          const newNotes = await askPrompt({
                            title: `Observação ${item.sku}`,
                            initialValue: item.notes || '',
                            placeholder: 'Digite a observação',
                          })
                          if (newNotes === null) return
                          try {
                            await api.updateItemNotes(item.id, newNotes.trim() || null)
                            setItems(prev => prev.map(i => i.id === item.id ? { ...i, notes: newNotes.trim() || null } : i))
                          } catch (e) { notify('Erro: ' + e.message, 'error') }
                        }}
                        className="truncate max-w-[220px] cursor-pointer text-blue-600 hover:text-blue-800 italic hover:bg-blue-50 p-1 rounded transition-colors group"
                        title={item.notes || 'Clique para adicionar'}
                      >
                        <span className="mr-1 opacity-0 group-hover:opacity-100 transition-opacity">✏️</span>
                        {item.notes || <span className="text-gray-300">clique para add</span>}
                      </div>
                    </td>
                    <td className="py-2">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        item.status === 'complete' ? 'bg-green-100 text-green-700' :
                        item.status === 'pending'  ? 'bg-gray-200 text-gray-600' :
                        'bg-blue-100 text-blue-700'
                      }`}>
                        {item.status}
                      </span>
                    </td>
                    <td className="py-2 text-right">
                      {item.qty_picked === 0 && (
                        <button onClick={() => handleTransfer(item.id)} className="text-xs font-bold text-orange-600 hover:text-orange-800">
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

// ── BatchDetail Page ──────────────────────────────────────────────────────────
export default function BatchDetail() {
  const { batchId } = useParams()
  const navigate = useNavigate()
  const { notify } = useFeedback()
  const [batch, setBatch] = useState(null)
  const [shortageItems, setShortageItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [extraOpen, setExtraOpen] = useState(false)
  const [deleteAllConfirm, setDeleteAllConfirm] = useState(false)
  const [deletingAll, setDeletingAll] = useState(false)

  async function handleDeleteAllSessions() {
    if (!batch?.sessions?.length) { setDeleteAllConfirm(false); return }
    setDeletingAll(true)
    try {
      await Promise.all(batch.sessions.map(s => api.deleteSession(s.id)))
      setDeleteAllConfirm(false)
      load()
    } catch (err) {
      notify('Erro ao apagar listas: ' + (err.message || err), 'error')
    } finally {
      setDeletingAll(false)
    }
  }

  function load() {
    api.listBatches()
      .then(all => {
        const found = all.find(b => String(b.id) === String(batchId))
        setBatch(found || null)
      })
      .finally(() => setLoading(false))
    api.getShortages().then(setShortageItems).catch(() => {})
  }

  useEffect(() => { load() }, [batchId])

  if (loading) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <div className="w-full max-w-3xl px-6">
        <SkeletonRows rows={7} />
      </div>
    </div>
  )

  if (!batch) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <div className="text-center">
        <PackageX size={56} className="mx-auto mb-3 text-slate-400" />
        <p className="text-xl font-bold text-slate-700">Lote não encontrado</p>
        <Button onClick={() => navigate('/supervisor')} className="mt-4">
          Voltar ao Supervisor
        </Button>
      </div>
    </div>
  )

  const batchMarketplace = normalizeMarket(batch.marketplace)
  const visibleShortages = shortageItems.filter(i =>
    normalizeMarket(i.marketplace) === batchMarketplace &&
    i.status === 'pendente'
  )
  const shortageStats = {
    totalUnits: visibleShortages.reduce((sum, i) => sum + (i.quantity || 0), 0),
    skuCount: new Set(visibleShortages.map(i => i.sku)).size,
    sessionCount: new Set(visibleShortages.map(i => i.list_id)).size,
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-6xl mx-auto px-4 md:px-8 py-8 flex flex-col gap-6">
        <PageHeader
          title={batch.name}
          subtitle="Detalhamento visual e operacional do lote"
          backLabel="Voltar para listas"
          onBack={() => {
            if (window.history.length > 1) navigate(-1)
            else navigate('/supervisor?tab=lists')
          }}
          right={
            batch.status === 'active' ? (
              <Button
                variant="danger"
                onClick={() => api.archiveBatch(batch.id).then(() => navigate('/supervisor?tab=lists'))}
              >
                <FolderArchive size={16} />
                Arquivar Lote
              </Button>
            ) : (
              <span className="text-xs font-semibold bg-slate-100 text-slate-500 px-3 py-1.5 rounded-full">Arquivado</span>
            )
          }
        />

        <ProgressHero sessions={batch.sessions} shortageStats={shortageStats} />
        <OperatorRanking batches={[batch]} marketplace={batchMarketplace} />

        {/* Sessions list */}
        <Card>
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
            <h2 className="font-bold text-slate-800">Listas do Lote</h2>
            <div className="flex items-center gap-2">
              {batch.status === 'active' && (
                <Button onClick={() => setExtraOpen(true)} className="text-sm" variant="primary">
                  <Plus size={14} />
                  Nova Lista Extra
                </Button>
              )}
              <Button onClick={load} className="text-sm">
                <RefreshCcw size={14} />
                Atualizar
              </Button>
              {batch.sessions.length > 0 && (
                <button
                  onClick={() => setDeleteAllConfirm(true)}
                  title="Apagar todas as listas deste lote"
                  className="p-2 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                >
                  <Trash2 size={16} />
                </button>
              )}
            </div>
          </div>

          {batch.sessions.length === 0 ? (
            <p className="text-center text-slate-400 py-12">Nenhuma lista neste lote.</p>
          ) : (() => {
            // Ordena: mono-SKU primeiro, depois por items_total desc
            const sortMonoFirst = (arr) => [...arr].sort((a, b) => {
              const monoA = a.unique_sku_count === 1 ? 0 : 1
              const monoB = b.unique_sku_count === 1 ? 0 : 1
              if (monoA !== monoB) return monoA - monoB
              return (b.items_total || 0) - (a.items_total || 0)
            })
            const inProgress = sortMonoFirst(batch.sessions.filter(s => s.status === 'in_progress'))
            const opens      = sortMonoFirst(batch.sessions.filter(s => s.status === 'open'))
            const dones      = sortMonoFirst(batch.sessions.filter(s => s.status === 'completed'))
            return (
            <div className="px-6 divide-y divide-slate-50">
              {/* In progress */}
              {inProgress.length > 0 && (
                <div className="py-2">
                  <p className="text-xs font-bold text-blue-600 uppercase tracking-widest flex items-center gap-2 mb-2 mt-2">
                    <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse inline-block" /> Em Andamento
                  </p>
                  {inProgress.map(s => (
                    <SessionRow key={s.id} s={s} onDeleted={load} />
                  ))}
                </div>
              )}
              {/* Open */}
              {opens.length > 0 && (
                <div className="py-2">
                  <p className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-2 mt-2">Disponíveis</p>
                  {opens.map(s => (
                    <SessionRow key={s.id} s={s} onDeleted={load} />
                  ))}
                </div>
              )}
              {/* Done */}
              {dones.length > 0 && (
                <div className="py-2">
                  <p className="text-xs font-bold text-green-600 uppercase tracking-widest mb-2 mt-2">Concluídas</p>
                  {dones.map(s => (
                    <SessionRow key={s.id} s={s} onDeleted={load} />
                  ))}
                </div>
              )}
            </div>
            )
          })()}
        </Card>
      </div>

      {extraOpen && (
        <ExtraListModal
          batch={batch}
          onClose={() => setExtraOpen(false)}
          onCreated={(code) => {
            setExtraOpen(false)
            notify(`Lista ${code} criada`, 'success')
            load()
          }}
        />
      )}

      {deleteAllConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-sm w-full p-6">
            <div className="flex items-center gap-3 mb-4">
              <Trash2 size={28} className="text-red-500" />
              <div>
                <p className="font-bold text-gray-900 text-lg">Apagar todas as listas?</p>
                <p className="text-sm text-gray-500 mt-0.5">
                  {batch.sessions.length} lista(s) deste lote serão apagadas
                </p>
              </div>
            </div>
            <p className="text-sm text-red-600 bg-red-50 rounded-xl p-3 mb-5">
              ⚠️ Esta ação não pode ser desfeita. Todos os itens e histórico de bipagem serão removidos.
            </p>
            <div className="flex gap-3">
              <button onClick={() => setDeleteAllConfirm(false)} disabled={deletingAll}
                className="flex-1 py-2.5 rounded-xl border border-gray-300 text-sm font-medium hover:bg-gray-50 disabled:opacity-50">
                Não, cancelar
              </button>
              <button onClick={handleDeleteAllSessions} disabled={deletingAll}
                className="flex-1 py-2.5 rounded-xl bg-red-500 text-white text-sm font-bold hover:bg-red-600 disabled:opacity-50 transition-colors">
                {deletingAll ? 'Apagando...' : 'Sim, apagar tudo'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}


// ── Extra List Modal ──────────────────────────────────────────────────────────
function ExtraListModal({ batch, onClose, onCreated }) {
  const { notify } = useFeedback()
  const [items, setItems] = useState([{ sku: '', ml_code: '', qty_required: '', description: '', resolved: null, checking: false }])
  const [submitting, setSubmitting] = useState(false)
  const [skuModalOpen, setSkuModalOpen] = useState(null)

  const addRow = () => setItems(prev => [...prev, { sku: '', ml_code: '', qty_required: '', description: '', resolved: null, checking: false }])
  const removeRow = (idx) => setItems(prev => prev.length === 1 ? prev : prev.filter((_, i) => i !== idx))
  const updateRow = (idx, patch) => setItems(prev => prev.map((it, i) => i === idx ? { ...it, ...patch } : it))

  async function checkSku(idx) {
    const sku = items[idx]?.sku?.trim() || ''
    if (!sku) {
      updateRow(idx, { resolved: null, description: '' })
      return
    }
    const dup = items.findIndex((it, i) => i !== idx && it.sku.trim() === sku)
    if (dup !== -1) {
      notify(`SKU "${sku}" já adicionado nesta lista`, 'error')
      updateRow(idx, { sku: '', resolved: null, description: '' })
      return
    }
    updateRow(idx, { checking: true })
    try {
      const r = await api.resolveBarcode(sku)
      if (r && r.sku) {
        updateRow(idx, { resolved: true, description: r.description || '', checking: false, sku: r.sku })
      } else {
        updateRow(idx, { resolved: false, checking: false })
        setSkuModalOpen({ idx, sku })
      }
    } catch {
      updateRow(idx, { resolved: false, checking: false })
      setSkuModalOpen({ idx, sku })
    }
  }

  async function handleSkuRegistered(idx, sku, description) {
    try {
      await api.createProduct(sku, description, [])
      updateRow(idx, { sku, description, resolved: true, checking: false })
      setSkuModalOpen(null)
      notify(`SKU ${sku} cadastrado na Base`, 'success')
    } catch (e) {
      notify(`Erro ao cadastrar: ${e.message}`, 'error')
    }
  }

  async function submit() {
    const cleaned = items
      .map(it => ({
        sku: it.sku.trim(),
        ml_code: (it.ml_code || '').trim().toUpperCase() || null,
        qty_required: Number(it.qty_required),
        description: it.description?.trim() || '',
      }))
      .filter(it => it.sku && it.qty_required > 0)

    if (cleaned.length === 0) {
      notify('Adicione ao menos um item válido', 'error')
      return
    }
    // Duplicação considera (sku, ml_code) — mesmo SKU com ml_codes diferentes é OK
    const keys = cleaned.map(i => `${i.sku}::${i.ml_code || ''}`)
    if (new Set(keys).size !== keys.length) {
      notify('Item duplicado (mesmo SKU + Código ML) na lista', 'error')
      return
    }
    const allResolved = items.every(it => !it.sku.trim() || it.resolved === true)
    if (!allResolved) {
      notify('Há SKUs não cadastrados na Base', 'error')
      return
    }

    setSubmitting(true)
    try {
      const res = await api.createManualSession(batch.id, cleaned)
      onCreated(res.session_code)
    } catch (e) {
      notify(`Erro: ${e.message}`, 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div>
            <h2 className="text-xl font-black text-slate-900">Nova Lista Extra</h2>
            <p className="text-xs text-slate-500 mt-0.5">Lote {batch.name} · {batch.marketplace?.toUpperCase()}</p>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-lg">
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          <div className="grid grid-cols-12 gap-2 px-2 mb-2 text-[10px] font-bold uppercase tracking-widest text-slate-400">
            <div className="col-span-3">SKU</div>
            <div className="col-span-3">Código ML <span className="text-slate-300 normal-case font-medium">(opcional)</span></div>
            <div className="col-span-3">Descrição</div>
            <div className="col-span-2">Qtd</div>
            <div className="col-span-1"></div>
          </div>

          {items.map((it, idx) => (
            <div key={idx} className="grid grid-cols-12 gap-2 mb-2 items-center">
              <div className="col-span-3 relative">
                <input
                  type="text"
                  value={it.sku}
                  onChange={e => updateRow(idx, { sku: e.target.value.toUpperCase(), resolved: null, description: '' })}
                  onBlur={() => checkSku(idx)}
                  onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); checkSku(idx) } }}
                  placeholder="Digite o SKU"
                  className={`w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-300 ${
                    it.resolved === true ? 'border-emerald-300 bg-emerald-50/30' :
                    it.resolved === false ? 'border-red-300 bg-red-50/30' :
                    'border-slate-200'
                  }`}
                />
                {it.checking && <Search size={14} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 animate-pulse" />}
              </div>
              <div className="col-span-3">
                <input
                  type="text"
                  value={it.ml_code}
                  onChange={e => updateRow(idx, { ml_code: e.target.value.toUpperCase() })}
                  placeholder="Ex: LLAP88233"
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-300 font-mono"
                />
              </div>
              <div className="col-span-3">
                <input
                  type="text"
                  value={it.description}
                  readOnly
                  placeholder={it.resolved === false ? 'Cadastre o SKU' : 'Descrição da Base'}
                  className="w-full px-3 py-2 text-sm bg-slate-50 border border-slate-200 rounded-lg text-slate-600"
                />
              </div>
              <div className="col-span-2">
                <input
                  type="number"
                  min="1"
                  value={it.qty_required}
                  onChange={e => updateRow(idx, { qty_required: e.target.value })}
                  placeholder="0"
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-300"
                />
              </div>
              <div className="col-span-1 flex justify-end">
                <button
                  onClick={() => removeRow(idx)}
                  disabled={items.length === 1}
                  className="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg disabled:opacity-30 disabled:hover:bg-transparent"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))}

          <button
            onClick={addRow}
            className="mt-2 w-full py-2 text-sm font-semibold text-blue-600 border-2 border-dashed border-blue-200 rounded-lg hover:bg-blue-50 hover:border-blue-300 transition-colors flex items-center justify-center gap-2"
          >
            <Plus size={14} />
            Adicionar item
          </button>
        </div>

        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-slate-100">
          <button
            onClick={onClose}
            disabled={submitting}
            className="px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100 rounded-lg"
          >
            Cancelar
          </button>
          <Button onClick={submit} disabled={submitting} variant="primary" className="text-sm">
            {submitting ? 'Gerando...' : 'Gerar Lista'}
          </Button>
        </div>
      </div>

      {skuModalOpen && (
        <SkuRegisterModal
          initialSku={skuModalOpen.sku}
          onClose={() => {
            updateRow(skuModalOpen.idx, { sku: '', resolved: null, description: '' })
            setSkuModalOpen(null)
          }}
          onSave={(sku, description) => handleSkuRegistered(skuModalOpen.idx, sku, description)}
        />
      )}
    </div>
  )
}


// ── SKU Register Modal ────────────────────────────────────────────────────────
function SkuRegisterModal({ initialSku, onClose, onSave }) {
  const [sku, setSku] = useState((initialSku || '').toUpperCase())
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)

  const canSave = sku.trim() && description.trim() && !saving

  async function handleSave() {
    setSaving(true)
    await onSave(sku.trim().toUpperCase(), description.trim())
    setSaving(false)
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-[60] p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full">
        <div className="px-6 py-4 border-b border-slate-100">
          <h3 className="text-lg font-black text-slate-900">SKU não encontrado na Base</h3>
          <p className="text-xs text-slate-500 mt-1">Cadastre agora para continuar.</p>
        </div>
        <div className="px-6 py-4 space-y-3">
          <div>
            <label className="text-[10px] font-bold uppercase tracking-widest text-slate-500">SKU</label>
            <input
              type="text"
              value={sku}
              onChange={e => setSku(e.target.value.toUpperCase())}
              className="mt-1 w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-300"
              autoFocus
            />
          </div>
          <div>
            <label className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Descrição *</label>
            <input
              type="text"
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Ex: Capa de banco preta XL"
              className="mt-1 w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-300"
              onKeyDown={e => { if (e.key === 'Enter' && canSave) handleSave() }}
            />
          </div>
        </div>
        <div className="flex justify-end gap-2 px-6 py-4 border-t border-slate-100">
          <button onClick={onClose} disabled={saving} className="px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100 rounded-lg">
            Cancelar
          </button>
          <Button onClick={handleSave} disabled={!canSave} variant="primary" className="text-sm">
            {saving ? 'Salvando...' : 'Cadastrar e usar'}
          </Button>
        </div>
      </div>
    </div>
  )
}
