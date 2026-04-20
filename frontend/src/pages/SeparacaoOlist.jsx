import { useState, useEffect, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useFeedback } from '../components/ui/FeedbackProvider'
import { 
  Search, RefreshCcw, Package, ClipboardList,
  ChevronDown, X, Info, Filter, Eraser, Clock,
  MapPin, Truck, Calendar, AlertCircle, CheckCircle2,
  PackageSearch, ArrowUpDown, List, Undo2
} from 'lucide-react'
import { cn } from '../lib/utils'

export default function SeparacaoOlist() {
  const navigate = useNavigate()
  const { notify } = useFeedback()
  const [loading, setLoading] = useState(false)
  const [separacoes, setSeparacoes] = useState([])
  const [searchQuery, setSearchQuery] = useState('')
  const [activeTab, setActiveTab] = useState('aguardando') // Default tab
  
  // Calcula os últimos 7 dias (Hoje + 6 anteriores)
  const getDates = () => {
    const today = new Date()
    const past = new Date()
    past.setDate(today.getDate() - 6) // 7 dias (Hoje + 6 anteriores)
    
    const fmt = (d) => {
      const dd = String(d.getDate()).padStart(2, '0')
      const mm = String(d.getMonth() + 1).padStart(2, '0')
      const yyyy = d.getFullYear()
      return `${dd}/${mm}/${yyyy}`
    }
    
    return { from: fmt(past), to: fmt(today) }
  }

  const [dateRange, setDateRange] = useState(getDates())
  const [showDateMenu, setShowDateMenu] = useState(false)
  const [selectedPeriod, setSelectedPeriod] = useState('7d') 
  const [showFilterMenu, setShowFilterMenu] = useState(false)
  const [marketplaceFilter, setMarketplaceFilter] = useState('all')
  const [selectedIds, setSelectedIds] = useState([])          // aguardando tab
  const [selectedEmSepIds, setSelectedEmSepIds] = useState([]) // em_separacao tab
  // Mapa de status local: { separation_id: { status, list_id } }
  // Fonte de verdade local — Tiny é somente-leitura, nunca escrevemos de volta
  const [localStatuses, setLocalStatuses] = useState({})

  async function fetchLocalStatuses() {
    try {
      const data = await api.getSeparationStatuses()
      setLocalStatuses(data || {})
    } catch (err) {
      console.error('Erro ao buscar status locais:', err)
    }
  }

  const handleRevertToAguardando = async () => {
    if (!selectedEmSepIds.length) return
    setLoading(true)
    try {
      await api.revertSeparationStatuses(selectedEmSepIds.map(String))
      notify(`${selectedEmSepIds.length} documento(s) devolvido(s) para Aguardando Separação.`, 'success')
      setSelectedEmSepIds([])
      await fetchLocalStatuses()
    } catch (err) {
      notify('Erro ao reverter status.', 'error')
    } finally {
      setLoading(false)
    }
  }

  async function fetchSeparacoes(from = dateRange.from, to = dateRange.to) {
    setLoading(true)
    setSelectedIds([])
    setSelectedEmSepIds([])
    try {
      const resp = await api.getTinySeparacoes(1, from, to)
      const list = resp.separacoes || []
      const items = list.map(item => item.separacao || item)
      
      const filteredItems = items.filter(s => (s.situacao || '').toString() !== '3')
      setSeparacoes(filteredItems)

      // Aquece cache de itens em background — quando o usuário gerar a lista, já estará pronto
      const aguardandoIds = filteredItems
        .filter(s => (s.situacao || '').toString() === '1')
        .map(s => s.id.toString())
      if (aguardandoIds.length > 0) {
        api.warmSeparationCache(aguardandoIds).catch(() => {})
      }
      
      const sitCounts = { "1": 0, "4": 0, "2": 0 }
      items.forEach(it => {
        const s = (it.situacao || '').toString()
        if (sitCounts[s] !== undefined) sitCounts[s]++
      })

      if (activeTab === 'aguardando' && sitCounts["1"] === 0) {
        if (sitCounts["4"] > 0) setActiveTab('em_separacao')
        else if (sitCounts["2"] > 0) setActiveTab('separadas')
      }
    } catch (err) {
      if (err.message.includes('35')) {
          notify('Sem registros no período selecionado.', 'info')
          setSeparacoes([])
      } else {
          notify('Erro ao sincronizar com o Tiny.', 'error')
      }
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const toggleSelect = (id) => {
    setSelectedIds(prev => 
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  const toggleSelectAll = (items) => {
    if (selectedIds.length === items.length) {
      setSelectedIds([])
    } else {
      setSelectedIds(items.map(s => s.id))
    }
  }

  const handleCreatePickingList = async () => {
    setLoading(true)
    try {
      const res = await api.createPickingList(null, selectedIds)
      notify(`Lista "${res.name}" gerada com sucesso!`, 'success')
      setSelectedIds([])
      await fetchLocalStatuses()
      navigate('/separacao/listas')
    } catch (err) {
      notify('Erro ao gerar lista de separação.', 'error')
    } finally {
      setLoading(false)
    }
  }

  const applyPeriod = (period) => {
    setSelectedPeriod(period)
    const today = new Date()
    const past = new Date()
    
    const fmt = (d) => {
      const dd = String(d.getDate()).padStart(2, '0')
      const mm = String(d.getMonth() + 1).padStart(2, '0')
      const yyyy = d.getFullYear()
      return `${dd}/${mm}/${yyyy}`
    }

    let from = fmt(today)
    let to = fmt(today)

    if (period === '30d') {
      past.setDate(today.getDate() - 29)
      from = fmt(past)
    } else if (period === '7d') {
      past.setDate(today.getDate() - 6)
      from = fmt(past)
    } else if (period === 'dia') {
      from = fmt(today)
    } else if (period === 'mes') {
      const firstDay = new Date(today.getFullYear(), today.getMonth(), 1)
      from = fmt(firstDay)
    } else if (period === 'all') {
      past.setDate(today.getDate() - 90) // 90 dias como 'sem filtro' para performance
      from = fmt(past)
    }

    const newRange = { from, to }
    setDateRange(newRange)
    setShowDateMenu(false)
    fetchSeparacoes(from, to)
  }

  useEffect(() => {
    fetchSeparacoes()
    fetchLocalStatuses()
  }, [])

  const matchMarketplace = (s, filter) => {
    if (filter === 'all') return true
    const idEnvio = (s.idFormaEnvio || '').toString()
    if (filter === 'shopee') return idEnvio === '735725326'
    if (filter === 'ml') return idEnvio === '735794407'
    if (filter === 'tiktok') return idEnvio === 'tiktok_placeholder' // Ajustar quando tiver o ID
    return true
  }

  // Resolve o status efetivo de um documento: status local tem precedência sobre Tiny
  // Valores possíveis: "em_separacao" | "concluida" | "aguardando" (override) | null (usa Tiny)
  const resolveStatus = (s) => {
    const localEntry = localStatuses[(s.id || '').toString()]
    if (localEntry) return localEntry.status
    return null
  }

  const filteredItems = useMemo(() => {
    return separacoes.filter(s => {
      const q = searchQuery.toLowerCase()
      const matchSearch = !q ||
        (s.id || '').toString().includes(q) ||
        (s.destinatario || '').toLowerCase().includes(q) ||
        (s.numero || '').toLowerCase().includes(q) ||
        (s.numeroPedidoEcommerce || '').toLowerCase().includes(q)

      const matchMk = matchMarketplace(s, marketplaceFilter)

      const localStatus = resolveStatus(s)
      const sit = (s.situacao || '').toString()
      let matchTab = false
      if (activeTab === 'aguardando')    matchTab = localStatus === 'aguardando' || (!localStatus && sit === '1')
      else if (activeTab === 'em_separacao') matchTab = localStatus === 'em_separacao' || (!localStatus && sit === '4')
      else if (activeTab === 'separadas')    matchTab = localStatus === 'concluida'    || (!localStatus && sit === '2')
      else if (activeTab === 'embaladas')    matchTab = sit === '3'

      return matchSearch && matchTab && matchMk
    })
  }, [separacoes, searchQuery, activeTab, marketplaceFilter, localStatuses])

  const stats = useMemo(() => {
    const counts = { aguardando: 0, em_separacao: 0, separadas: 0, embaladas: 0 }
    separacoes.forEach(s => {
      if (!matchMarketplace(s, marketplaceFilter)) return

      const localStatus = resolveStatus(s)
      const sit = (s.situacao || '').toString()

      if (localStatus === 'aguardando') counts.aguardando++
      else if (localStatus === 'em_separacao') counts.em_separacao++
      else if (localStatus === 'concluida') counts.separadas++
      else if (sit === '1') counts.aguardando++
      else if (sit === '4') counts.em_separacao++
      else if (sit === '2') counts.separadas++
      else if (sit === '3') counts.embaladas++
    })
    return counts
  }, [separacoes, marketplaceFilter, localStatuses])

  const getFormaEnvioNome = (item) => {
    const id = (item.idFormaEnvio || '').toString()
    const mapa = {
      '735794407': 'Mercado Envios',
      '735725326': 'Shopee'
    }
    return mapa[id] || id || '---'
  }

  return (
    <div className="flex-1 flex flex-col bg-[#fcfcfc] min-h-full p-4 md:p-6 font-sans">
      
      {/* breadcrumb */}
      <div className="flex items-center gap-2 text-[11px] font-medium text-slate-400 mb-4 px-2">
         <span>início</span> <span className="opacity-30">/</span>
         <span>vendas</span> <span className="opacity-30">/</span>
         <span className="text-slate-900">separação</span>
      </div>

      <h1 className="text-xl sm:text-2xl font-medium text-slate-800 mb-6 px-2">Separação de Mercadorias</h1>

      {/* TOOLBAR STYLE TINY */}
      <div className="flex flex-col gap-4 mb-8 px-2">
        <div className="flex flex-wrap items-center gap-2">
          
          {/* SEARCH BAR */}
          <div className="relative w-full md:w-96">
            <input 
              type="text"
              placeholder="Pesquise por destinatário ou número"
              className="w-full h-10 pl-4 pr-10 bg-white border border-slate-200 rounded-lg text-sm outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100 placeholder-slate-400"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
            />
            <Search className="absolute right-3 top-2.5 text-slate-400" size={18} />
          </div>

          {/* DATE FILTER BUTTON & DROPDOWN */}
          <div className="relative">
            <button 
              onClick={() => setShowDateMenu(!showDateMenu)}
              className={cn(
                "h-10 px-4 border text-xs font-medium flex items-center gap-2 rounded-full transition-all",
                showDateMenu 
                  ? "bg-blue-600 border-blue-600 text-white shadow-lg" 
                  : "bg-blue-50/50 border-blue-100 text-blue-600 hover:bg-blue-100"
              )}
            >
              <Calendar size={14} /> 
              envio para separação: {
                selectedPeriod === '7d' ? 'últimos 7 dias' :
                selectedPeriod === '30d' ? 'últimos 30 dias' :
                selectedPeriod === 'dia' ? 'do dia' :
                selectedPeriod === 'mes' ? 'do mês' :
                selectedPeriod === 'all' ? 'sem filtro' : 'período'
              }
              <ChevronDown size={14} className={cn("transition-transform", showDateMenu && "rotate-180")} />
            </button>

            {showDateMenu && (
              <div className="absolute top-12 left-0 w-[min(95vw,420px)] bg-white border border-slate-200 rounded-2xl shadow-2xl z-[100] p-6 animate-in fade-in zoom-in duration-200">
                <div className="flex flex-wrap gap-4 sm:gap-8 border-b border-slate-100 mb-6 pb-2">
                   <button className="text-xs font-bold text-slate-800 border-b-2 border-slate-800 pb-2">data de envio a separação</button>
                   <button className="text-xs font-medium text-slate-300 pb-2 hover:text-slate-400">data do pedido</button>
                   <button className="text-xs font-medium text-slate-300 pb-2 hover:text-slate-400">data máxima do despacho</button>
                </div>

                <div className="mb-8">
                  <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-3">Período</p>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { id: 'all', label: 'sem filtro' },
                      { id: '30d', label: 'últimos 30 dias' },
                      { id: '7d', label: 'últimos 7 dias' },
                      { id: 'dia', label: 'do dia' },
                      { id: 'mes', label: 'do mês' },
                      { id: 'custom', label: 'do intervalo' }
                    ].map(p => (
                      <button 
                        key={p.id}
                        onClick={() => setSelectedPeriod(p.id)}
                        className={cn(
                          "px-4 py-2 rounded-full text-xs font-medium border transition-all",
                          selectedPeriod === p.id 
                            ? "bg-blue-100 border-blue-200 text-blue-600" 
                            : "bg-slate-50 border-slate-100 text-slate-500 hover:bg-slate-100"
                        )}
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex items-center gap-4">
                   <button 
                     onClick={() => applyPeriod(selectedPeriod)}
                     className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-3 rounded-full font-bold text-sm shadow-lg shadow-blue-100 active:scale-95 transition-all"
                   >
                     aplicar
                   </button>
                   <button 
                     onClick={() => setShowDateMenu(false)}
                     className="text-slate-500 hover:text-slate-800 text-sm font-medium"
                   >
                     cancelar
                   </button>
                </div>
              </div>
            )}
          </div>

          <button className="h-10 px-4 bg-white border border-slate-200 text-slate-600 rounded-full text-xs font-medium flex items-center gap-2 hover:bg-slate-50 transition-colors">
            <ArrowUpDown size={14} /> mais antigas
          </button>

          <button className="h-10 px-4 bg-white border border-slate-200 text-slate-600 rounded-full text-xs font-medium flex items-center gap-2 hover:bg-slate-50 transition-colors">
             por forma de envio
          </button>

          <div className="relative">
            <button 
              onClick={() => setShowFilterMenu(!showFilterMenu)}
              className={cn(
                "h-10 px-4 border text-xs font-medium flex items-center gap-2 rounded-full transition-all",
                showFilterMenu || marketplaceFilter !== 'all'
                  ? "bg-slate-800 border-slate-800 text-white" 
                  : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
              )}
            >
              <Filter size={14} /> filtros {marketplaceFilter !== 'all' && ' (ativo)'}
            </button>

            {showFilterMenu && (
              <div className="absolute top-12 left-0 w-[min(95vw,420px)] bg-white border border-slate-200 rounded-2xl shadow-2xl z-[100] p-6 animate-in fade-in zoom-in duration-200">
                <div className="flex flex-wrap gap-4 sm:gap-8 border-b border-slate-100 mb-6 pb-2">
                   <button className="text-xs font-bold text-slate-800 border-b-2 border-slate-800 pb-2">e-commerce</button>
                   <button className="text-xs font-medium text-slate-300 pb-2 cursor-not-allowed">outros</button>
                </div>

                <div className="mb-8">
                  <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-3">Selecione o marketplace</p>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { id: 'all', label: 'todos' },
                      { id: 'shopee', label: 'Shopee' },
                      { id: 'ml', label: 'Mercado Livre' },
                      { id: 'tiktok', label: 'Tik Tok' }
                    ].map(mk => (
                      <button 
                        key={mk.id}
                        onClick={() => setMarketplaceFilter(mk.id)}
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

                <div className="flex items-center gap-4">
                   <button 
                     onClick={() => setShowFilterMenu(false)}
                     className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-3 rounded-full font-bold text-sm shadow-lg shadow-blue-100 active:scale-95 transition-all"
                   >
                     aplicar
                   </button>
                   <button 
                     onClick={() => { setMarketplaceFilter('all'); setShowFilterMenu(false); }}
                     className="text-slate-500 hover:text-slate-800 text-sm font-medium"
                   >
                     limpar
                   </button>
                </div>
              </div>
            )}
          </div>

          <button 
            onClick={() => { setMarketplaceFilter('all'); setSearchQuery(''); setSelectedPeriod('7d'); applyPeriod('7d'); }} 
            className="h-10 px-4 text-slate-400 hover:text-slate-600 text-xs font-medium flex items-center gap-2 mr-2"
          >
            <Eraser size={14} /> limpar filtros
          </button>

          <button 
            onClick={() => fetchSeparacoes()} 
            disabled={loading}
            className={cn(
               "h-10 px-6 rounded-full text-xs font-bold flex items-center gap-2 transition-all active:scale-95",
               loading 
                ? "bg-slate-100 text-slate-400 cursor-not-allowed" 
                : "bg-emerald-500 hover:bg-emerald-600 text-white shadow-lg shadow-emerald-100"
            )}
          >
            <RefreshCcw size={14} className={cn(loading && "animate-spin")} />
            {loading ? 'Buscando...' : 'Atualizar Dados'}
          </button>

          <div className="flex-1"></div>

          {/* STATS SUMMARY BOX (Top right) */}
          <div className="flex items-center gap-4 text-right">
             <div>
                <p className="text-[10px] text-slate-400 uppercase font-black tracking-widest">embalar</p>
                <p className="text-xl font-black text-slate-700">{stats.aguardando} pedidos</p>
                <p className="text-[9px] text-slate-400 font-bold">CTRL+E</p>
             </div>
             <button className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-2xl font-bold text-sm shadow-lg shadow-blue-200 transition-all active:scale-95">
                separar {stats.aguardando} pedidos
                <span className="block text-[9px] opacity-70">CTRL+S</span>
             </button>
          </div>
        </div>
      </div>

      {/* TAB NAVIGATION STYLE TINY */}
      <div className="flex gap-10 border-b border-slate-200 px-6 mb-0 scrollbar-hide">
        <button 
          onClick={() => setActiveTab('aguardando')}
          className={cn(
            "pb-4 flex flex-col items-center gap-1 transition-all border-b-2 px-4",
            activeTab === 'aguardando' ? "border-orange-400" : "border-transparent opacity-50"
          )}
        >
          <span className="text-sm font-medium text-slate-600">aguardando separação</span>
          <span className="text-2xl font-light text-slate-800">{stats.aguardando}</span>
        </button>

        <button 
          onClick={() => setActiveTab('em_separacao')}
          className={cn(
            "pb-4 flex flex-col items-center gap-1 transition-all border-b-2 px-4",
            activeTab === 'em_separacao' ? "border-orange-400" : "border-transparent opacity-50"
          )}
        >
          <span className="text-sm font-medium text-slate-600">em separação</span>
          <span className="text-2xl font-light text-slate-800">{stats.em_separacao}</span>
        </button>

        <button 
          onClick={() => setActiveTab('separadas')}
          className={cn(
            "pb-4 flex flex-col items-center gap-1 transition-all border-b-2 px-4",
            activeTab === 'separadas' ? "border-orange-400" : "border-transparent opacity-50"
          )}
        >
          <span className="text-sm font-medium text-slate-600">separadas</span>
          <span className="text-2xl font-light text-slate-800">{stats.separadas}</span>
        </button>

        <button 
          onClick={() => setActiveTab('embaladas')}
          className={cn(
            "pb-4 flex flex-col items-center gap-1 transition-all border-b-2 px-4",
            activeTab === 'embaladas' ? "border-orange-400" : "border-transparent opacity-50"
          )}
        >
          <span className="text-sm font-medium text-slate-600 text-center">
            embaladas <span className="text-[10px] opacity-40 block -mt-1 font-black">checkout</span>
          </span>
          <span className="text-2xl font-light text-slate-800">{stats.embaladas}</span>
        </button>
      </div>

      {/* THE DATA TABLE (The big work) */}
      <div className="flex-1 bg-white overflow-hidden flex flex-col mt-0">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[1200px]">
            <thead>
              <tr className="border-b border-slate-100 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                <th className="p-4 w-10">
                   {activeTab === 'aguardando' && (
                     <input type="checkbox" className="rounded w-4 h-4 text-blue-600 focus:ring-blue-500 cursor-pointer"
                       checked={filteredItems.length > 0 && selectedIds.length === filteredItems.length}
                       onChange={() => toggleSelectAll(filteredItems)}
                     />
                   )}
                   {activeTab === 'em_separacao' && (
                     <input type="checkbox" className="rounded w-4 h-4 text-orange-500 focus:ring-orange-400 cursor-pointer"
                       checked={filteredItems.length > 0 && selectedEmSepIds.length === filteredItems.length}
                       onChange={() => setSelectedEmSepIds(
                         selectedEmSepIds.length === filteredItems.length ? [] : filteredItems.map(s => s.id)
                       )}
                     />
                   )}
                </th>
                <th className="p-4">Identificação</th>
                <th className="p-4">Destinatário</th>
                <th className="p-4">Forma de envio</th>
                {activeTab === 'em_separacao' && <th className="p-4">Lista</th>}
                <th className="p-4">Data do pedido</th>
                <th className="p-4">Prazo máximo de despacho</th>
                <th className="p-4">Marcadores</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {loading && separacoes.length === 0 ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    <td colSpan={activeTab === 'em_separacao' ? 8 : 7} className="p-6"><div className="h-10 bg-slate-50 rounded-lg w-full"></div></td>
                  </tr>
                ))
              ) : filteredItems.length === 0 ? (
                <tr>
                   <td colSpan={activeTab === 'em_separacao' ? 8 : 7} className="p-32 text-center text-slate-300">
                      <PackageSearch size={64} className="mx-auto mb-4 opacity-10" />
                      <p className="text-lg font-light italic">Sem pedidos aguardando separação...</p>
                   </td>
                </tr>
              ) : (
                filteredItems.map(item => (
                  <tr
                    key={item.id}
                    className={cn(
                      "hover:bg-slate-50 group transition-colors text-xs font-medium text-slate-700",
                      activeTab === 'aguardando' && selectedIds.includes(item.id) && "bg-blue-50/50",
                      activeTab === 'em_separacao' && selectedEmSepIds.includes(item.id) && "bg-orange-50/50"
                    )}
                  >
                    <td className="p-4">
                      {activeTab === 'aguardando' && (
                        <input type="checkbox" className="rounded w-4 h-4 text-blue-600 focus:ring-blue-500 cursor-pointer"
                          checked={selectedIds.includes(item.id)}
                          onChange={() => toggleSelect(item.id)}
                          onClick={e => e.stopPropagation()}
                        />
                      )}
                      {activeTab === 'em_separacao' && (
                        <input type="checkbox" className="rounded w-4 h-4 text-orange-500 focus:ring-orange-400 cursor-pointer"
                          checked={selectedEmSepIds.includes(item.id)}
                          onChange={() => setSelectedEmSepIds(prev =>
                            prev.includes(item.id) ? prev.filter(x => x !== item.id) : [...prev, item.id]
                          )}
                          onClick={e => e.stopPropagation()}
                        />
                      )}
                    </td>
                    <td className="p-4" onClick={() => activeTab === 'aguardando' ? toggleSelect(item.id) : null}>
                       <span className="text-slate-400 text-[10px] mr-1">...</span>
                       <span className="text-blue-600 font-bold">Nota {item.numero || 'S/N'}</span>
                       <p className="text-[10px] text-slate-400 mt-1 uppercase">Nº EC {item.numeroPedidoEcommerce || '---'}</p>
                       {item.numero_pedido && <p className="text-[10px] text-slate-400">Pedido {item.numero_pedido}</p>}
                    </td>
                    <td className="p-4 font-semibold text-slate-800">{item.destinatario || 'Sem nome'}</td>
                    <td className="p-4 text-slate-600 font-bold">{getFormaEnvioNome(item)}</td>
                    {activeTab === 'em_separacao' && (
                      <td className="p-4">
                        {localStatuses[(item.id || '').toString()]?.list_name
                          ? <span className="bg-blue-50 border border-blue-200 text-blue-700 px-2.5 py-1 rounded-lg text-[11px] font-black font-mono">
                              {localStatuses[(item.id || '').toString()].list_name}
                            </span>
                          : <span className="text-slate-300 text-xs">—</span>
                        }
                      </td>
                    )}
                    <td className="p-4 text-slate-500">{item.dataEmissao || item.dataCriacao}</td>
                    <td className="p-4 text-slate-500">{item.prazo_maximo || '---'}</td>
                    <td className="p-4">
                       <div className="flex flex-wrap gap-1">
                          {(item.marcadores || []).map((m, idx) => (
                            <span key={idx} className="bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full text-[9px] flex items-center gap-1 border border-slate-200 uppercase font-black">
                               <div className="w-1.5 h-1.5 rounded-full bg-slate-400"></div> {m.descricao || m}
                            </span>
                          ))}
                       </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* FLOATING ACTION BAR FOR PICKING LIST */}
      {selectedIds.length > 0 && (
        <div className="fixed bottom-10 left-1/2 -translate-x-1/2 bg-slate-900/90 backdrop-blur-md border border-white/10 text-white px-8 py-4 rounded-full shadow-2xl flex items-center gap-10 animate-in slide-in-from-bottom-10 duration-500 z-[1000]">
           <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center font-black text-sm shadow-lg shadow-blue-500/20">
                {selectedIds.length}
              </div>
              <div className="flex flex-col">
                <span className="text-xs font-black uppercase tracking-widest text-blue-400 leading-none">notas marcadas</span>
                <span className="text-[9px] text-white/40 font-bold uppercase tracking-widest mt-1">prontas para consolidar</span>
              </div>
           </div>

           <div className="h-8 w-[1px] bg-white/10" />

           <button 
             onClick={handleCreatePickingList}
             disabled={loading}
             className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 active:scale-95 text-white h-12 px-8 rounded-full font-black text-xs uppercase tracking-widest flex items-center gap-3 transition-all shadow-xl shadow-blue-600/30"
           >
             {loading ? <RefreshCcw size={18} className="animate-spin" /> : <List size={18} />}
             gerar lista de separação
           </button>

           <button 
             onClick={() => setSelectedIds([])}
             className="text-white/40 hover:text-white text-[10px] font-bold uppercase tracking-widest transition-colors"
           >
             cancelar
           </button>
        </div>
      )}

      {/* FLOATING ACTION BAR — EM SEPARAÇÃO: reverter para aguardando */}
      {selectedEmSepIds.length > 0 && (
        <div className="fixed bottom-10 left-1/2 -translate-x-1/2 bg-slate-900/90 backdrop-blur-md border border-white/10 text-white px-8 py-4 rounded-full shadow-2xl flex items-center gap-10 animate-in slide-in-from-bottom-10 duration-500 z-[1000]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-orange-500 rounded-full flex items-center justify-center font-black text-sm shadow-lg shadow-orange-500/20">
              {selectedEmSepIds.length}
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-black uppercase tracking-widest text-orange-400 leading-none">em separação</span>
              <span className="text-[9px] text-white/40 font-bold uppercase tracking-widest mt-1">selecionados para mover</span>
            </div>
          </div>

          <div className="h-8 w-[1px] bg-white/10" />

          <button
            onClick={handleRevertToAguardando}
            disabled={loading}
            className="bg-orange-500 hover:bg-orange-400 disabled:opacity-50 active:scale-95 text-white h-12 px-8 rounded-full font-black text-xs uppercase tracking-widest flex items-center gap-3 transition-all shadow-xl shadow-orange-500/30"
          >
            {loading ? <RefreshCcw size={18} className="animate-spin" /> : <Undo2 size={18} />}
            mover para aguardando
          </button>

          <button
            onClick={() => setSelectedEmSepIds([])}
            className="text-white/40 hover:text-white text-[10px] font-bold uppercase tracking-widest transition-colors"
          >
            cancelar
          </button>
        </div>
      )}

      {/* FLOATING ACTION BOTTOM (Optional but cool for premium) */}
      <div className="fixed bottom-6 right-6 flex flex-col gap-2">
         <button 
           onClick={() => fetchSeparacoes()}
           className="w-12 h-12 bg-white border border-slate-200 rounded-full shadow-lg flex items-center justify-center text-slate-400 hover:text-blue-600 hover:border-blue-200 transition-all active:scale-90"
         >
           <RefreshCcw size={20} className={cn(loading && "animate-spin")} />
         </button>
      </div>
      
    </div>
  )
}
