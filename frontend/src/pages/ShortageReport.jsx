import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import {
  AlertTriangle,
  PackageX,
  Plus,
  Minus,
  ArrowLeft,
  Layers,
  LayoutGrid,
  ChevronRight,
  Trash2,
  CheckCircle2,
  Clock,
} from 'lucide-react'

export default function ShortageReport() {
  const navigate = useNavigate()
  const [shortages, setShortages] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedGroups, setExpandedGroups] = useState({ ml: true, shopee: true, organico: true })
  const [deleteAllConfirm, setDeleteAllConfirm] = useState(false)
  const [deletingAll, setDeletingAll] = useState(false)

  const load = () => {
    setLoading(true)
    api.getShortages()
      .then(setShortages)
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const mlGroup      = shortages.filter(s => s.category === 'full' && s.marketplace === 'ml')
  const shopeeGroup  = shortages.filter(s => s.category === 'full' && s.marketplace === 'shopee')
  const organicGroup = shortages.filter(s => s.category === 'organico')
  // Total do header conta só pendentes
  const totalPendente = shortages
    .filter(s => s.status === 'pendente')
    .reduce((a, s) => a + s.quantity, 0)

  const toggleGroup = (g) => setExpandedGroups(p => ({ ...p, [g]: !p[g] }))

  async function handleToggleStatus(item) {
    if (item.is_legacy) return
    try {
      await api.toggleShortageStatus(item.id)
      setShortages(prev => prev.map(s =>
        s.id === item.id
          ? { ...s, status: s.status === 'pendente' ? 'concluido' : 'pendente' }
          : s
      ))
    } catch (e) { alert('Erro: ' + e.message) }
  }

  async function handleDelete(item) {
    try {
      if (item.is_legacy) {
        const legacyId = String(item.id).replace('legacy_', '')
        await api.deleteShortageLegacy(legacyId)
      } else {
        await api.deleteShortage(item.id)
      }
      setShortages(prev => prev.filter(s => s.id !== item.id))
    } catch (e) { alert('Erro: ' + e.message) }
  }

  async function handleDeleteAll() {
    setDeletingAll(true)
    try {
      await api.deleteAllShortages()
      setShortages([])
      setDeleteAllConfirm(false)
    } catch (e) { alert('Erro: ' + e.message) }
    finally { setDeletingAll(false) }
  }

  if (loading) return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-4 text-slate-400">
       <div className="w-10 h-10 border-4 border-slate-200 border-t-blue-500 rounded-full animate-spin" />
       <span className="font-bold uppercase tracking-widest text-xs">Carregando Faltas...</span>
    </div>
  )

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* HEADER */}
      <div className="bg-white/80 backdrop-blur-md sticky top-0 z-30 border-b border-slate-200 px-6 py-6">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-6">
            <button
              onClick={() => {
                if (window.history.length > 1) navigate(-1)
                else navigate('/supervisor')
              }}
              className="p-3 hover:bg-slate-100 rounded-2xl text-slate-400 hover:text-slate-900 transition-all active:scale-90"
            >
               <ArrowLeft size={24} />
            </button>
            <div>
              <h1 className="text-3xl font-black text-slate-900 tracking-tight flex items-center gap-3">
                 <AlertTriangle className="text-red-500" size={32} />
                 Relatório de Faltas
              </h1>
              <p className="text-slate-400 text-sm font-bold uppercase tracking-widest mt-1">
                Consolidação de estoque zerado durante o Picking
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="bg-red-50 border border-red-100 px-5 py-3 rounded-3xl flex flex-col items-end">
               <span className="text-[10px] font-black text-red-400 uppercase tracking-widest">Pendentes</span>
               <span className="text-2xl font-black text-red-600 tabular-nums">
                 {totalPendente.toFixed(0)} <small className="text-sm">UNID.</small>
               </span>
            </div>
            {shortages.length > 0 && (
              <button
                onClick={() => setDeleteAllConfirm(true)}
                title="Apagar todas as faltas"
                className="p-3 rounded-2xl text-slate-400 hover:text-red-500 hover:bg-red-50 transition-all active:scale-90"
              >
                <Trash2 size={22} />
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="flex-1 p-6 md:p-10 max-w-6xl mx-auto w-full space-y-12 pb-24">
        {shortages.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-32 text-slate-300">
             <PackageX size={80} strokeWidth={1} className="mb-6 opacity-20" />
             <p className="text-xl font-black text-slate-400">Tudo em dia!</p>
             <p className="text-sm font-medium">Não há registros de falta no momento.</p>
          </div>
        ) : (
          <>
            <GroupSection
              title="Mercado Livre Full"
              subtitle="Itens faltantes nas sessões de carregamento do Full Mercado Livre"
              items={mlGroup}
              expanded={expandedGroups.ml}
              onToggle={() => toggleGroup('ml')}
              icon={<LayoutGrid className="text-yellow-500" size={24} />}
              color="yellow"
              onToggleStatus={handleToggleStatus}
              onDelete={handleDelete}
            />
            <GroupSection
              title="Shopee Full"
              subtitle="Itens faltantes nas sessões de carregamento do Full Shopee"
              items={shopeeGroup}
              expanded={expandedGroups.shopee}
              onToggle={() => toggleGroup('shopee')}
              icon={<LayoutGrid className="text-orange-500" size={24} />}
              color="orange"
              onToggleStatus={handleToggleStatus}
              onDelete={handleDelete}
            />
            <GroupSection
              title="Orgânico (Tiny)"
              subtitle="Itens faltantes nas listas de separação avulsas/Tiny"
              items={organicGroup}
              expanded={expandedGroups.organico}
              onToggle={() => toggleGroup('organico')}
              icon={<Layers className="text-emerald-500" size={24} />}
              color="emerald"
              onToggleStatus={handleToggleStatus}
              onDelete={handleDelete}
            />
          </>
        )}
      </div>

      {/* Modal — apagar tudo */}
      {deleteAllConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-sm w-full p-6">
            <div className="flex items-center gap-3 mb-4">
              <Trash2 size={28} className="text-red-500" />
              <div>
                <p className="font-bold text-gray-900 text-lg">Apagar todas as faltas?</p>
                <p className="text-sm text-gray-500 mt-0.5">
                  {shortages.length} registro(s) serão removidos permanentemente
                </p>
              </div>
            </div>
            <p className="text-sm text-red-600 bg-red-50 rounded-xl p-3 mb-5">
              ⚠️ Esta ação não pode ser desfeita.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setDeleteAllConfirm(false)}
                disabled={deletingAll}
                className="flex-1 py-2.5 rounded-xl border border-gray-300 text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
              >
                Não, cancelar
              </button>
              <button
                onClick={handleDeleteAll}
                disabled={deletingAll}
                className="flex-1 py-2.5 rounded-xl bg-red-500 text-white text-sm font-bold hover:bg-red-600 disabled:opacity-50 transition-colors"
              >
                {deletingAll ? 'Apagando...' : 'Sim, apagar tudo'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const COLOR_CLASSES = {
  blue:    { bg50: 'bg-blue-50',    border100: 'border-blue-100',    text600: 'text-blue-600',    bg100: 'bg-blue-100',    hover200: 'hover:bg-blue-200' },
  emerald: { bg50: 'bg-emerald-50', border100: 'border-emerald-100', text600: 'text-emerald-600', bg100: 'bg-emerald-100', hover200: 'hover:bg-emerald-200' },
  yellow:  { bg50: 'bg-yellow-50',  border100: 'border-yellow-100',  text600: 'text-yellow-600',  bg100: 'bg-yellow-100',  hover200: 'hover:bg-yellow-200' },
  orange:  { bg50: 'bg-orange-50',  border100: 'border-orange-100',  text600: 'text-orange-600',  bg100: 'bg-orange-100',  hover200: 'hover:bg-orange-200' },
}

function GroupSection({ title, subtitle, items, expanded, onToggle, icon, color, onToggleStatus, onDelete }) {
  const c = COLOR_CLASSES[color] || COLOR_CLASSES.blue
  const totalPendente = items
    .filter(s => s.status === 'pendente')
    .reduce((a, s) => a + s.quantity, 0)
  const totalQtd = items.reduce((a, s) => a + s.quantity, 0)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between group">
        <div className="flex items-center gap-4">
           <div className={`p-3 ${c.bg50} rounded-2xl shadow-sm border ${c.border100}`}>
             {icon}
           </div>
           <div>
              <h2 className="text-xl font-black text-slate-800 tracking-tight">{title}</h2>
              <p className="text-slate-400 text-xs font-bold uppercase tracking-widest">{subtitle}</p>
           </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right">
            <span className={`text-lg font-black ${c.text600} tabular-nums`}>
              {totalPendente.toFixed(0)} <small className="text-[10px] uppercase">pendentes</small>
            </span>
            <p className="text-[10px] text-slate-400 font-bold uppercase tracking-widest">
              {items.length} skus · {totalQtd.toFixed(0)} total
            </p>
          </div>
          <button
            onClick={onToggle}
            className={`w-12 h-12 flex items-center justify-center rounded-2xl transition-all active:scale-90 ${
              expanded
                ? 'bg-slate-800 text-white'
                : `${c.bg100} ${c.text600} ${c.hover200}`
            }`}
          >
            {expanded ? <Minus size={20} /> : <Plus size={20} />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="bg-white rounded-[2.5rem] border border-slate-200 shadow-xl shadow-slate-200/50 overflow-hidden animate-in fade-in slide-in-from-top-4 duration-300">
          {items.length === 0 ? (
            <div className="p-12 text-center text-slate-300 italic text-sm">
              Nenhum registro para este grupo
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left table-fixed">
                <thead>
                  <tr className="bg-slate-50/50 border-b border-slate-100 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">
                    <th className="px-3 py-5 w-[26%]">SKU / Descrição</th>
                    <th className="px-3 py-5 text-center w-[9%]">Lista</th>
                    <th className="px-3 py-5 text-center w-[12%]">Operador</th>
                    <th className="px-3 py-5 text-center w-[11%]">Data</th>
                    <th className="px-3 py-5 text-center w-[12%]">Status</th>
                    <th className="px-3 py-5 text-right w-[9%]">Qtd</th>
                    <th className="px-3 py-5 w-[17%]">Observação</th>
                    <th className="px-2 py-5 w-[4%]"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {items.map(item => (
                    <tr
                      key={item.id}
                      className={`hover:bg-slate-50/50 transition-colors group ${
                        item.status === 'concluido' ? 'opacity-50' : ''
                      }`}
                    >
                      {/* SKU */}
                      <td className="px-3 py-6 align-middle">
                        <div className="flex flex-col gap-1 min-w-0">
                           <span className="font-mono font-black text-slate-700 text-sm group-hover:text-blue-600 transition-colors truncate" title={item.sku}>
                             {item.sku}
                           </span>
                           <span className="text-[11px] font-semibold text-slate-400 truncate" title={item.description || ''}>
                             {item.description || 'Sem descrição cadastrada'}
                           </span>
                        </div>
                      </td>

                      {/* Lista */}
                      <td className="px-3 py-6 text-center align-middle">
                        <div className="inline-flex items-center gap-1 bg-slate-100 border border-slate-200 px-2 py-1 rounded-xl font-mono text-xs font-bold text-slate-500">
                           <ChevronRight size={12} className="text-slate-300"/> {item.list_id || '—'}
                        </div>
                      </td>

                      {/* Operador */}
                      <td className="px-3 py-6 text-center align-middle">
                         <div className="flex items-center justify-center gap-2 min-w-0">
                           <div className="w-7 h-7 bg-blue-50 border border-blue-100 rounded-full flex items-center justify-center text-[10px] font-black text-blue-600 uppercase shadow-sm shrink-0">
                             {item.operator_name ? item.operator_name.slice(0, 2).toUpperCase() : 'AD'}
                           </div>
                           <span className="text-[10px] font-black text-slate-500 uppercase tracking-wide truncate">
                             {item.operator_name || 'Sistema'}
                           </span>
                         </div>
                      </td>

                      {/* Data */}
                      <td className="px-3 py-6 text-center align-middle">
                         <span className="text-[11px] font-bold text-slate-400 uppercase tabular-nums whitespace-nowrap">
                            {new Date(item.created_at).toLocaleDateString('pt-BR')}
                            <span className="opacity-50 ml-1 font-normal">
                              {new Date(item.created_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
                            </span>
                         </span>
                      </td>

                      {/* STATUS — clicável para toggle */}
                      <td className="px-3 py-6 text-center align-middle">
                        {item.is_legacy ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold bg-orange-50 text-orange-500 border border-orange-100">
                            <Clock size={10} /> Pendente
                          </span>
                        ) : (
                          <button
                            onClick={() => onToggleStatus(item)}
                            title="Clique para alternar status"
                            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold border transition-all active:scale-95 cursor-pointer ${
                              item.status === 'concluido'
                                ? 'bg-emerald-50 text-emerald-600 border-emerald-200 hover:bg-emerald-100'
                                : 'bg-orange-50 text-orange-500 border-orange-100 hover:bg-orange-100'
                            }`}
                          >
                            {item.status === 'concluido'
                              ? <><CheckCircle2 size={10} /> Concluído</>
                              : <><Clock size={10} /> Pendente</>
                            }
                          </button>
                        )}
                      </td>

                      {/* Qtd */}
                      <td className="px-3 py-6 text-right align-middle">
                         <span className={`text-lg font-black tabular-nums ${
                           item.status === 'concluido' ? 'text-slate-300 line-through' : 'text-red-500'
                         }`}>
                           -{item.quantity.toFixed(0)}
                         </span>
                         <span className="text-[9px] font-bold text-slate-300 ml-0.5 uppercase">un</span>
                      </td>

                      {/* Obs — movida pro fim */}
                      <td className="px-3 py-6 align-middle">
                        {item.notes
                          ? <span className="text-[11px] font-semibold text-amber-700 bg-amber-50 border border-amber-100 px-2 py-1 rounded-lg italic leading-relaxed block truncate" title={item.notes}>{item.notes}</span>
                          : <span className="text-xs text-slate-300">—</span>
                        }
                      </td>

                      {/* Delete por linha — aparece no hover */}
                      <td className="px-2 py-6 align-middle">
                        <button
                          onClick={() => onDelete(item)}
                          title="Remover este registro"
                          className="p-2 rounded-xl text-slate-300 hover:text-red-500 hover:bg-red-50 transition-all active:scale-90 opacity-0 group-hover:opacity-100"
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
