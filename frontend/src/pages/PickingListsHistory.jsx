import React, { useState, useEffect } from 'react'
import { api } from '../api/client'
import { useFeedback } from '../components/ui/FeedbackProvider'
import { ClipboardList, Calendar, ChevronRight, Package, Clock, Search, List as ListIcon, Trash2, Filter } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { cn } from '../lib/utils'
import MarketplaceLogo from '../components/MarketplaceLogo'

export default function PickingListsHistory() {
  const { notify } = useFeedback()
  const navigate = useNavigate()
  const [lists, setLists] = useState([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [marketplaceFilter, setMarketplaceFilter] = useState('all')
  const [showFilterMenu, setShowFilterMenu] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(null) // list object

  async function handleDelete(list) {
    setLoading(true)
    setConfirmDelete(null)
    try {
      await api.deletePickingList(list.id)
      notify(`Lista "${list.name}" excluída. Pedidos devolvidos para aguardando separação.`, 'success')
      await loadLists()
    } catch (err) {
      notify('Erro ao excluir lista.', 'error')
    } finally {
      setLoading(false)
    }
  }

  async function loadLists() {
    setLoading(true)
    try {
      const data = await api.getPickingLists()
      setLists(data)
    } catch (err) {
      notify('Erro ao carregar histórico de listas.', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadLists()
  }, [])

  const matchMarketplace = (list) => {
    if (marketplaceFilter === 'all') return true
    if (marketplaceFilter === 'organico') return !list.marketplace
    return list.marketplace === marketplaceFilter
  }

  // Ordena por # (id) desc — lista mais nova primeiro
  const filtered = lists
    .filter(l =>
      (l.name.toLowerCase().includes(search.toLowerCase()) ||
       l.id.toString().includes(search)) &&
      matchMarketplace(l)
    )
    .slice()
    .sort((a, b) => b.id - a.id)

  return (
    <div className="flex-1 flex flex-col bg-white p-6 font-sans">
      <div className="flex items-center gap-2 text-[10px] font-bold text-slate-400 mb-6 uppercase tracking-widest px-2">
         <span>início</span> <span className="opacity-30">/</span>
         <span>separação</span> <span className="opacity-30">/</span>
         <span className="text-slate-900">listas geradas</span>
      </div>

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8 px-2">
        <div>
          <h1 className="text-2xl font-black text-slate-800 tracking-tight">Listas de Separação</h1>
          <p className="text-xs text-slate-400 font-medium mt-1 uppercase tracking-widest">Histórico de picking consolidado</p>
        </div>

        <div className="flex items-center gap-2">
           <div className="relative">
              <input
                type="text"
                placeholder="Pesquisar lista..."
                className="w-full sm:w-64 h-10 pl-4 pr-10 bg-white border border-slate-400 rounded-xl text-xs font-bold outline-none focus:border-blue-500 focus:bg-white transition-all placeholder:font-bold placeholder:text-slate-500"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
              <Search className="absolute right-3 top-2.5 text-slate-500" size={14} />
           </div>

           <div className="relative">
             <button
               onClick={() => setShowFilterMenu(!showFilterMenu)}
               className={cn(
                 "h-10 px-4 border text-xs font-bold flex items-center gap-2 rounded-xl transition-all",
                 showFilterMenu || marketplaceFilter !== 'all'
                   ? "bg-slate-800 border-slate-800 text-white"
                   : "bg-white border-slate-400 text-slate-700 hover:bg-slate-50"
               )}
             >
               <Filter size={14} /> filtros {marketplaceFilter !== 'all' && '(ativo)'}
             </button>

             {showFilterMenu && (
               <div className="absolute top-12 right-0 w-[min(95vw,420px)] bg-white border border-slate-200 rounded-2xl shadow-2xl z-[100] p-6 animate-in fade-in zoom-in duration-200">
                 <div className="flex flex-wrap gap-4 sm:gap-8 border-b border-slate-100 mb-6 pb-2">
                   <button className="text-xs font-bold text-slate-800 border-b-2 border-slate-800 pb-2">e-commerce</button>
                 </div>

                 <div className="mb-2">
                   <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-3">Selecione o marketplace</p>
                   <div className="flex flex-wrap gap-2">
                     {[
                       { id: 'all', label: 'todos' },
                       { id: 'shopee', label: 'Shopee' },
                       { id: 'ml', label: 'Mercado Livre' },
                       { id: 'organico', label: 'Orgânico' },
                     ].map(mk => (
                       <button
                         key={mk.id}
                         onClick={() => { setMarketplaceFilter(mk.id); setShowFilterMenu(false) }}
                         className={cn(
                           "px-4 py-2 rounded-full text-xs font-medium border transition-all",
                           marketplaceFilter === mk.id
                             ? "bg-slate-800 border-slate-800 text-white"
                             : "bg-slate-50 border-slate-100 text-slate-500 hover:bg-slate-100"
                         )}
                       >
                         {mk.label}
                       </button>
                     ))}
                   </div>
                 </div>
               </div>
             )}
           </div>

           <button onClick={loadLists} className="h-10 w-10 flex items-center justify-center bg-white border border-slate-400 rounded-xl text-slate-600 hover:text-blue-600 hover:border-blue-400 transition-colors">
              <Clock size={16} />
           </button>
        </div>
      </div>

      <div className="flex-1 flex flex-col gap-2 max-w-5xl">
        {loading ? (
             Array.from({ length: 8 }).map((_, i) => (
               <div key={i} className="h-16 bg-slate-50 rounded-xl border border-slate-100 animate-pulse" />
             ))
        ) : filtered.length === 0 ? (
          <div className="py-20 text-center text-slate-300">
             <Package size={48} className="mx-auto mb-4 opacity-10" />
             <p className="text-sm font-medium">Nenhuma lista encontrada.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {filtered.map((list, idx) => {
              const isZebra = idx % 2 === 0
              const mk = list.marketplace
              const rowStyle =
                mk === 'ml' ? "bg-yellow-100 border-l-yellow-500 hover:bg-yellow-200 hover:border-l-yellow-600"
                : mk === 'shopee' ? "bg-red-200 border-l-red-500 hover:bg-red-300 hover:border-l-red-700"
                : isZebra ? "bg-blue-100 border-l-blue-500 hover:bg-blue-200 hover:border-l-blue-700"
                : "bg-slate-200 border-l-slate-400 hover:bg-slate-300 hover:border-l-blue-400"
              return (
              <div key={list.id} className="w-full flex items-center gap-2">
              <button
                onClick={() => navigate(`/separacao/listas/${list.id}`)}
                className={cn(
                  "flex-1 flex items-center gap-4 p-5 rounded-2xl border-l-4 border border-slate-100 hover:shadow-lg hover:shadow-slate-100 transition-all group relative overflow-hidden text-left",
                  rowStyle
                )}
              >
                <div className={cn(
                  "w-20 h-20 rounded-xl flex items-center justify-center shrink-0 transition-colors",
                  list.marketplace ? "p-0" : "p-1 bg-blue-50 text-blue-600 group-hover:bg-blue-600 group-hover:text-white"
                )}>
                   {list.marketplace
                     ? <MarketplaceLogo marketplace={list.marketplace} size={list.marketplace === 'ml' ? 76 : 48} />
                     : <ListIcon size={24} />}
                </div>

                <div className="flex-1 min-w-0">
                   <div className="flex items-center justify-between gap-2 mb-1">
                      <h3 className={cn(
                        "text-base font-black truncate group-hover:text-blue-700 transition-colors",
                        isZebra ? "text-blue-700" : "text-slate-900"
                      )}>
                         {list.name}
                      </h3>
                      <span className={cn(
                        "text-xs font-black shrink-0 tabular-nums",
                        isZebra ? "text-blue-600" : "text-slate-500"
                      )}>#{list.id}</span>
                   </div>

                   <div className="flex items-center gap-3 flex-wrap">
                      <div className="flex items-center gap-1.5 text-[11px] text-slate-700 font-bold uppercase tracking-wider">
                         <Calendar size={12} className="text-slate-500" />
                         {new Date(list.created_at).toLocaleDateString()}
                         <span className="opacity-40">•</span>
                         <span className="tabular-nums">{new Date(list.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      </div>

                      <div className="flex items-center gap-1.5 text-[11px] text-slate-700 font-bold uppercase tracking-wider">
                         <Package size={12} className="text-slate-500" />
                         <span className="tabular-nums">{list.separation_count || 0} separações</span>
                      </div>

                      <span className={cn(
                        "px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-widest",
                        list.status === 'concluida'
                          ? "bg-emerald-100 text-emerald-700 border border-emerald-200"
                          : "bg-blue-100 text-blue-700 border border-blue-200"
                      )}>
                        {list.status}
                      </span>
                   </div>
                </div>

                <div className="p-2 text-slate-400 group-hover:text-blue-600 transition-colors">
                   <ChevronRight size={20} />
                </div>
              </button>
              <button
                onClick={() => setConfirmDelete(list)}
                title="Excluir lista"
                className="w-11 h-11 flex items-center justify-center rounded-xl border border-red-100 bg-red-50/60 text-red-500 hover:bg-red-500 hover:text-white hover:border-red-500 hover:shadow-lg hover:shadow-red-100 transition-all shrink-0 active:scale-95"
              >
                <Trash2 size={18} />
              </button>
              </div>
              )
            })}
          </div>
        )}
      </div>
      {confirmDelete && (
        <div className="fixed inset-0 z-[200] bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-6">
          <div className="bg-white w-full max-w-sm rounded-3xl p-8 text-center shadow-2xl animate-in zoom-in-95 duration-200">
            <div className="w-16 h-16 bg-red-100 text-red-600 rounded-2xl flex items-center justify-center mx-auto mb-6">
              <Trash2 size={32} />
            </div>
            <h3 className="text-xl font-black text-slate-900 tracking-tight mb-2">Excluir lista?</h3>
            <p className="text-slate-500 text-sm font-semibold mb-1">{confirmDelete.name}</p>
            <p className="text-slate-400 text-xs mb-8 px-2">
              A lista será excluída e os pedidos associados voltarão para <strong>aguardando separação</strong>.
            </p>
            <div className="flex gap-3">
              <button onClick={() => setConfirmDelete(null)} className="flex-1 h-14 rounded-2xl font-black text-[10px] uppercase tracking-widest text-slate-400 hover:bg-slate-50 transition-colors">Cancelar</button>
              <button onClick={() => handleDelete(confirmDelete)} className="flex-1 h-14 rounded-2xl font-black text-[10px] uppercase tracking-widest bg-red-600 text-white shadow-lg shadow-red-200 hover:bg-red-700 active:scale-95 transition-all">Sim, excluir</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
