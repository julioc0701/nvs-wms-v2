import React, { useState, useEffect } from 'react'
import { api } from '../api/client'
import { useFeedback } from '../components/ui/FeedbackProvider'
import { ClipboardList, Calendar, ChevronRight, Package, Clock, Search, List as ListIcon, Trash2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { cn } from '../lib/utils'

export default function PickingListsHistory() {
  const { notify } = useFeedback()
  const navigate = useNavigate()
  const [lists, setLists] = useState([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
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

  const filtered = lists.filter(l => 
    l.name.toLowerCase().includes(search.toLowerCase()) ||
    l.id.toString().includes(search)
  )

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
                className="w-full sm:w-64 h-10 pl-4 pr-10 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium outline-none focus:border-blue-400 focus:bg-white transition-all"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
              <Search className="absolute right-3 top-2.5 text-slate-300" size={14} />
           </div>
           <button onClick={loadLists} className="h-10 w-10 flex items-center justify-center bg-white border border-slate-200 rounded-xl text-slate-400 hover:text-blue-600 transition-colors">
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
            {filtered.map(list => (
              <div key={list.id} className="w-full flex items-center gap-2">
              <button
                onClick={() => navigate(`/separacao/listas/${list.id}`)}
                className="flex-1 flex items-center gap-4 bg-white p-4 rounded-2xl border border-slate-100 hover:border-blue-200 hover:shadow-lg hover:shadow-slate-100 transition-all group relative overflow-hidden text-left"
              >
                <div className="w-10 h-10 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center shrink-0 group-hover:bg-blue-600 group-hover:text-white transition-colors">
                   <ListIcon size={18} />
                </div>
                
                <div className="flex-1 min-w-0">
                   <div className="flex items-center justify-between gap-2 mb-0.5">
                      <h3 className="text-sm font-bold text-slate-700 truncate group-hover:text-blue-600 transition-colors">
                         {list.name}
                      </h3>
                      <span className="text-[10px] font-black text-slate-300 uppercase shrink-0">#{list.id}</span>
                   </div>
                   
                   <div className="flex items-center gap-3">
                      <div className="flex items-center gap-1.5 text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                         <Calendar size={12} className="opacity-50" />
                         {new Date(list.created_at).toLocaleDateString()}
                         <span className="opacity-30">•</span>
                         {new Date(list.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </div>
                      
                      <div className="flex items-center gap-1.5">
                         <div className={cn(
                           "w-1.5 h-1.5 rounded-full",
                           list.status === 'concluida' ? "bg-emerald-500" : "bg-blue-500"
                         )} />
                         <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{list.status}</span>
                      </div>
                   </div>
                </div>

                <div className="p-2 text-slate-300 group-hover:text-blue-600 transition-colors">
                   <ChevronRight size={18} />
                </div>
              </button>
              <button
                onClick={() => setConfirmDelete(list)}
                className="w-10 h-10 flex items-center justify-center rounded-xl border border-slate-100 text-slate-300 hover:text-red-500 hover:border-red-100 hover:bg-red-50 transition-all shrink-0"
              >
                <Trash2 size={16} />
              </button>
              </div>
            ))}
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
