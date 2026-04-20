import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import MarketplaceLogo from '../components/MarketplaceLogo'
import { 
  AlertTriangle, 
  PackageX, 
  Plus, 
  Minus, 
  ArrowLeft, 
  Layers, 
  LayoutGrid, 
  ExternalLink,
  ChevronRight
} from 'lucide-react'
import { useFeedback } from '../components/ui/FeedbackProvider'

export default function ShortageReport() {
  const navigate = useNavigate()
  const [shortages, setShortages] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedGroups, setExpandedGroups] = useState({ full: true, organico: true })

  useEffect(() => {
    api.getShortages()
      .then(setShortages)
      .finally(() => setLoading(false))
  }, [])

  const fullGroup = shortages.filter(s => s.category === 'full')
  const organicGroup = shortages.filter(s => s.category === 'organico')
  const totalFaltas = shortages.reduce((acc, curr) => acc + curr.quantity, 0)

  const toggleGroup = (group) => {
    setExpandedGroups(prev => ({ ...prev, [group]: !prev[group] }))
  }

  if (loading) return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-4 text-slate-400">
       <div className="w-10 h-10 border-4 border-slate-200 border-t-blue-500 rounded-full animate-spin" />
       <span className="font-bold uppercase tracking-widest text-xs">Carregando Faltas...</span>
    </div>
  )

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* HEADER PREMIUM */}
      <div className="bg-white/80 backdrop-blur-md sticky top-0 z-30 border-b border-slate-200 px-6 py-6">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-6">
            <button 
              onClick={() => navigate('/sessions')}
              className="p-3 hover:bg-slate-100 rounded-2xl text-slate-400 hover:text-slate-900 transition-all active:scale-90"
            >
               <ArrowLeft size={24} />
            </button>
            <div>
              <h1 className="text-3xl font-black text-slate-900 tracking-tight flex items-center gap-3">
                 <AlertTriangle core className="text-red-500" size={32} />
                 Relatório de Faltas
              </h1>
              <p className="text-slate-400 text-sm font-bold uppercase tracking-widest mt-1">Consolidação de estoque zerado durante o Picking</p>
            </div>
          </div>

          <div className="bg-red-50 border border-red-100 px-6 py-3 rounded-3xl flex flex-col items-end">
             <span className="text-[10px] font-black text-red-400 uppercase tracking-widest">Total Faltante</span>
             <span className="text-2xl font-black text-red-600 tabular-nums">{totalFaltas.toFixed(0)} <small className="text-sm">UNID.</small></span>
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
            {/* GRUPO FULL */}
            <GroupSection 
              title="Full Shopee / ML" 
              subtitle="Itens faltantes nas sessões de carregamento do Full"
              items={fullGroup}
              expanded={expandedGroups.full}
              onToggle={() => toggleGroup('full')}
              icon={<LayoutGrid className="text-blue-500" size={24} />}
              color="blue"
            />

            {/* GRUPO ORGÂNICO */}
            <GroupSection 
              title="Orgânico" 
              subtitle="Itens faltantes nas listas de separação avulsas/Tiny"
              items={organicGroup}
              expanded={expandedGroups.organico}
              onToggle={() => toggleGroup('organico')}
              icon={<Layers className="text-emerald-500" size={24} />}
              color="emerald"
            />
          </>
        )}
      </div>
    </div>
  )
}

function GroupSection({ title, subtitle, items, expanded, onToggle, icon, color }) {
  const totalQtd = items.reduce((acc, curr) => acc + curr.quantity, 0)
  
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between group">
        <div className="flex items-center gap-4">
           <div className={`p-3 bg-${color}-50 rounded-2xl shadow-sm border border-${color}-100`}>
             {icon}
           </div>
           <div>
              <h2 className="text-xl font-black text-slate-800 tracking-tight">{title}</h2>
              <p className="text-slate-400 text-xs font-bold uppercase tracking-widest">{subtitle}</p>
           </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right">
             <span className={`text-lg font-black text-${color}-600 tabular-nums`}>{totalQtd.toFixed(0)} <small className="text-[10px] uppercase">un</small></span>
             <p className="text-[10px] text-slate-400 font-bold uppercase tracking-widest">{items.length} skus</p>
          </div>
          <button 
            onClick={onToggle}
            className={`w-12 h-12 flex items-center justify-center rounded-2xl transition-all active:scale-90 ${
              expanded 
                ? 'bg-slate-800 text-white' 
                : `bg-${color}-100 text-${color}-600 hover:bg-${color}-200`
            }`}
          >
            {expanded ? <Minus size={20} /> : <Plus size={20} />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="bg-white rounded-[2.5rem] border border-slate-200 shadow-xl shadow-slate-200/50 overflow-hidden animate-in fade-in slide-in-from-top-4 duration-300">
          {items.length === 0 ? (
            <div className="p-12 text-center text-slate-300 italic text-sm">Nenhum registro para este grupo</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="bg-slate-50/50 border-b border-slate-100 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">
                    <th className="px-8 py-5">SKU / Descrição</th>
                    <th className="px-8 py-5 text-center">Lista de Origem</th>
                    <th className="px-8 py-5 text-center">Operador</th>
                    <th className="px-8 py-5">Observação</th>
                    <th className="px-8 py-5 text-center">Data Registro</th>
                    <th className="px-8 py-5 text-right">Qtd Faltante</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {items.map(item => (
                    <tr key={item.id} className="hover:bg-slate-50/50 transition-colors group">
                      <td className="px-8 py-6">
                        <div className="flex flex-col gap-1">
                           <span className="font-mono font-black text-slate-700 text-base group-hover:text-blue-600 transition-colors">{item.sku}</span>
                           <span className="text-xs font-semibold text-slate-400 truncate max-w-sm">{item.description || 'Sem descrição cadastrada'}</span>
                        </div>
                      </td>
                      <td className="px-8 py-6 text-center">
                        <div className="inline-flex items-center gap-2 bg-slate-100 border border-slate-200 px-3 py-1.5 rounded-xl font-mono text-xs font-bold text-slate-500">
                           <ChevronRight size={14} className="text-slate-300"/> {item.list_id || '—'}
                        </div>
                      </td>
                      <td className="px-8 py-6 text-center">
                         <div className="flex items-center justify-center gap-2">
                           <div className="w-8 h-8 bg-blue-50 border border-blue-100 rounded-full flex items-center justify-center text-[10px] font-black text-blue-600 uppercase shadow-sm shrink-0">
                             {item.operator_name ? item.operator_name.slice(0, 2).toUpperCase() : 'AD'}
                           </div>
                           <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest truncate">
                             {item.operator_name || 'Sistema / ADM'}
                           </span>
                         </div>
                      </td>
                      <td className="px-8 py-6 max-w-[200px]">
                        {item.notes
                          ? <span className="text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-100 px-2 py-1 rounded-lg italic leading-relaxed block truncate" title={item.notes}>{item.notes}</span>
                          : <span className="text-xs text-slate-300">—</span>
                        }
                      </td>
                      <td className="px-8 py-6 text-center">
                         <span className="text-xs font-bold text-slate-400 uppercase tabular-nums">
                            {new Date(item.created_at).toLocaleDateString('pt-BR')}
                            <span className="opacity-50 ml-1 font-normal">{new Date(item.created_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}</span>
                         </span>
                      </td>
                      <td className="px-8 py-6 text-right">
                         <span className="text-xl font-black text-red-500 tabular-nums">-{item.quantity.toFixed(0)}</span>
                         <span className="text-[10px] font-bold text-slate-300 ml-1 uppercase">unid.</span>
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
