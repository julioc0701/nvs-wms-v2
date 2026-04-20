import { useState, useEffect, useMemo, useRef } from 'react'
import { api } from '../api/client'
import { useFeedback } from '../components/ui/FeedbackProvider'
import { Search, Filter, RefreshCcw, Calendar, ChevronDown, Check, Package, CalendarDays, X, Image, User, MapPin, Truck, ShieldCheck, MessageSquare, TriangleAlert, Copy, Clock } from 'lucide-react'
import { cn } from '../lib/utils'
import mlLogo from '../assets/ml-logo-v3.png'
import shopeeLogo from '../assets/shopee-logo-v3.png'

export default function OlistOrders({ isGenerativeMode = false }) {
  const { notify } = useFeedback()
  const [loading, setLoading] = useState(false)
  const [orders, setOrders] = useState([])
  const [activeTab, setActiveTab] = useState('todos')
  const [searchQuery, setSearchQuery] = useState('')
  
  // States for Date Filter Popover
  const [showDateFilter, setShowDateFilter] = useState(false)
  const [dateFilterMode, setDateFilterMode] = useState('hoje') // Changed from 30d to 'hoje' by default for performance
  const dateFilterRef = useRef(null)
  
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  // States for "Mais Filtros" Popover
  const [showMoreFilters, setShowMoreFilters] = useState(false)
  const moreFiltersRef = useRef(null)
  const [filterMarketplace, setFilterMarketplace] = useState('') // '', 'Mercado Livre', 'Shopee'
  const [filterMarcador, setFilterMarcador] = useState('') 
  const [filterFormaEnvio, setFilterFormaEnvio] = useState('')
  
  // States for SAP Selection Options (SAP-Style Multiple Filtering)
  const [showSapModal, setShowSapModal] = useState(false)
  const [sapActiveTab, setSapActiveTab] = useState('incSingle') // incSingle, incRange, excSingle, excRange
  const [sapIncludeSingles, setSapIncludeSingles] = useState([])
  const [sapIncludeRanges, setSapIncludeRanges] = useState([])
  const [sapExcludeSingles, setSapExcludeSingles] = useState([])
  const [sapExcludeRanges, setSapExcludeRanges] = useState([])

  // Helper to sync SAP states (this acts as the 'Apply' logic)
  const [activeSapRules, setActiveSapRules] = useState({
    incSingles: [],
    incRanges: [],
    excSingles: [],
    excRanges: []
  })

  const hasActiveSapFilter = useMemo(() => {
    return activeSapRules.incSingles.length > 0 || 
           activeSapRules.incRanges.length > 0 || 
           activeSapRules.excSingles.length > 0 || 
           activeSapRules.excRanges.length > 0
  }, [activeSapRules])
  
  // Close the popovers when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (dateFilterRef.current && !dateFilterRef.current.contains(event.target)) {
        setShowDateFilter(false)
      }
      if (moreFiltersRef.current && !moreFiltersRef.current.contains(event.target)) {
        setShowMoreFilters(false)
      }
      if (sapFilterRef?.current && !sapFilterRef.current.contains(event.target)) {
         // Silently keep for retro-compatibility if needed, but we use a Modal now
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  // Formats YYYY-MM-DD to DD/MM/YYYY for Tiny
  const formatForTiny = (isoString) => {
    if (!isoString) return null
    const [y, m, d] = isoString.split('-')
    return `${d}/${m}/${y}`
  }

  // Fetch orders from API (Always max 30 days or the selected interval to prevent overload)
  async function fetchOrders(forceRefresh = false) {
    const cacheKey = `orders_${dateFilterMode}_${dateFrom}_${dateTo}`
    
    // 1. SWR: Stale-While-Revalidate Strategy
    // Se temos dados em cache para esse filtro e NÂO foi um refetch forçado, injeta instantaneamente na tela
    let hasCache = false
    if (!forceRefresh && window.__ORDERS_CACHE && window.__ORDERS_CACHE.key === cacheKey) {
       setOrders(window.__ORDERS_CACHE.data)
       hasCache = true
    }

    // Só exibe spinner de bloqueio se não tiver nenhum cache na manga
    if (!hasCache) {
       setLoading(true)
    }

    try {
      let dInicial = null
      let dFinal = null

      if (dateFilterMode === 'hoje') {
         const d = new Date()
         const today = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0')
         dInicial = formatForTiny(today)
         dFinal = formatForTiny(today)
      } else if (dateFilterMode === 'mes') {
         const now = new Date()
         const firstDay = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-01'
         
         const lastDayDate = new Date(now.getFullYear(), now.getMonth() + 1, 0)
         const lastDay = lastDayDate.getFullYear() + '-' + String(lastDayDate.getMonth() + 1).padStart(2, '0') + '-' + String(lastDayDate.getDate()).padStart(2, '0')
         
         dInicial = formatForTiny(firstDay)
         dFinal = formatForTiny(lastDay)
      } else if (dateFilterMode === 'intervalo' && dateFrom) {
         dInicial = formatForTiny(dateFrom)
         dFinal = formatForTiny(dateTo) // Se não tiver to, null é ok
      }

      const data = await api.listTinyPedidos(null, 1, null, dInicial, dFinal, forceRefresh)
      const pedidosList = data.pedidos || []
      const formatOrders = pedidosList.map(p => p.pedido)
      
      // Atualiza a tela (injetará silenciosamente se o cache já estava ativo)
      setOrders(formatOrders)
      
      // Salva no Memory Cache Global
      window.__ORDERS_CACHE = {
         key: cacheKey,
         data: formatOrders,
         timestamp: Date.now()
      }
      
      // Fechar popovers após busca
      setShowDateFilter(false)
      setShowMoreFilters(false)
    } catch (err) {
      if (!hasCache) {
         notify('FALHA: Nenhuma conexão encontrada.', 'error')
      }
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchOrders()
  }, [])

  // Close the date popover when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (dateFilterRef.current && !dateFilterRef.current.contains(event.target)) {
        setShowDateFilter(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const [selectedOrderId, setSelectedOrderId] = useState(null)

  // 1. Base Filtered Orders (Search + Marketplace Filters + SAP Rules applied)
  const baseFilteredOrders = useMemo(() => {
    return orders.filter(o => {
      // ---- SAP SELECT-OPTIONS LOGIC ----
      if (hasActiveSapFilter) {
          const val = (o.numero || '').toLowerCase()
          const valEco = (o.numero_ecommerce || '').toLowerCase()
          
          const matchSingle = (v, list) => list.some(item => v === item.toLowerCase())
          const matchRange = (v, list) => {
              const numVal = parseInt(v.replace(/\D/g, ''))
              if (isNaN(numVal)) return false
              return list.some(r => {
                  const from = parseInt(r.from.replace(/\D/g, ''))
                  const to = parseInt(r.to.replace(/\D/g, ''))
                  return numVal >= from && numVal <= to
              })
          }

          // 1. EXCLUSIONS FIRST (SAP Rule: Exclusions win)
          if (matchSingle(val, activeSapRules.excSingles) || matchSingle(valEco, activeSapRules.excSingles)) return false
          if (matchRange(val, activeSapRules.excRanges) || matchRange(valEco, activeSapRules.excRanges)) return false

          // 2. INCLUSIONS (If any Inclusions exist, the value MUST match one of them)
          const hasInclusions = activeSapRules.incSingles.length > 0 || activeSapRules.incRanges.length > 0
          if (hasInclusions) {
              const matchedInc = matchSingle(val, activeSapRules.incSingles) || 
                                 matchSingle(valEco, activeSapRules.incSingles) ||
                                 matchRange(val, activeSapRules.incRanges) ||
                                 matchRange(valEco, activeSapRules.incRanges)
              if (!matchedInc) return false
          }
      }

      // Filter by Search Query (Basic Keyword)
      if (searchQuery) {
        const q = searchQuery.toLowerCase()
        const matchSearch = (o.numero_ecommerce || '').toLowerCase().includes(q) ||
                            (o.numero || '').toLowerCase().includes(q) ||
                            (o.nome || '').toLowerCase().includes(q) ||
                            (o.cpf_cnpj || '').toLowerCase().includes(q)
        if (!matchSearch) return false
      }

      // Filter by Marketplace (Mais Filtros)
      if (filterMarketplace) {
          const eco = (o.ecommerce || '').toLowerCase()
          if (!eco.includes(filterMarketplace.toLowerCase())) return false
      }

      // Filter by Marcador (Smart Fixed Mapping)
      if (filterMarcador) {
          const marcadores = (o.marcadores || []).map(m => (m.descricao || '').toLowerCase())
          const f = filterMarcador.toLowerCase()
          
          let matched = false
          if (f === 'shopee full') {
              matched = marcadores.some(m => m.includes('shopee') && (m.includes('full') || m.includes('fulfillment')))
          } else if (f === 'shopee') {
              // Shopee normal (que não seja full se possível, mas vamos deixar abrangente)
              matched = marcadores.some(m => m.includes('shopee'))
          } else if (f === 'mercado full') {
              matched = marcadores.some(m => (m.includes('mercado') || m.includes('ml')) && (m.includes('full') || m.includes('fulfillment')))
          } else if (f === 'mercado livre') {
              matched = marcadores.some(m => m.includes('mercado livre') || m.includes('ml'))
          } else if (f === 'tik tok') {
              matched = marcadores.some(m => m.includes('tik tok') || m.includes('tiktok'))
          } else {
              // Caso geral para qualquer outro marcador que venha a ser configurado
              matched = marcadores.some(m => m.includes(f))
          }
          
          if (!matched) return false
      }

      // Filter by Forma de Envio
      if (filterFormaEnvio) {
          const envio = (o.forma_envio || '').toLowerCase()
          if (!envio.includes(filterFormaEnvio.toLowerCase())) return false
      }

      return true
    })
  }, [orders, searchQuery, filterMarketplace, filterMarcador, filterFormaEnvio, activeSapRules, hasActiveSapFilter])

  // 2. Calculate stats based strictly on what's visible after search
  const stats = useMemo(() => {
    const counts = {
      todos: baseFilteredOrders.length,
      em_aberto: 0,
      aprovado: 0,
      preparando_envio: 0,
      faturado: 0,
      pronto_envio: 0,
      enviado: 0,
      entregue: 0,
    }

    baseFilteredOrders.forEach(o => {
      const situacao = (o.situacao || '').toLowerCase()
      if (situacao === 'em aberto') counts.em_aberto++
      else if (situacao === 'aprovado') counts.aprovado++
      else if (situacao === 'preparando envio') counts.preparando_envio++
      else if (situacao === 'faturado') counts.faturado++
      else if (situacao === 'pronto para envio') counts.pronto_envio++
      else if (situacao === 'enviado') counts.enviado++
      else if (situacao === 'entregue') counts.entregue++
    })

    return counts
  }, [baseFilteredOrders])

  // 2.1 Compute Dynamic Filter Options based on current orders
  const filterOptions = useMemo(() => {
    const marcadores = new Set()
    const formasEnvio = new Set()

    orders.forEach(o => {
      if (o.marcadores) {
        o.marcadores.forEach(m => {
            if (m.descricao && m.descricao.trim()) marcadores.add(m.descricao.trim())
        })
      }
      if (o.forma_envio && o.forma_envio.trim()) {
        formasEnvio.add(o.forma_envio.trim())
      }
    })

    return {
      marcadores: Array.from(marcadores).sort(),
      formasEnvio: Array.from(formasEnvio).sort()
    }
  }, [orders])

  // 3. Final display list filtered by the active Status Tab
  const filteredOrders = useMemo(() => {
    return baseFilteredOrders.filter(o => {
      const sit = (o.situacao || '').toLowerCase()
      const matchTab = activeTab === 'todos' || 
                       (activeTab === 'em_aberto' && sit === 'em aberto') ||
                       (activeTab === 'aprovado' && sit === 'aprovado') ||
                       (activeTab === 'preparando_envio' && sit === 'preparando envio') ||
                       (activeTab === 'faturado' && sit === 'faturado') ||
                       (activeTab === 'pronto_envio' && sit === 'pronto para envio') ||
                       (activeTab === 'enviado' && sit === 'enviado') ||
                       (activeTab === 'entregue' && sit === 'entregue')
      return matchTab
    })
  }, [baseFilteredOrders, activeTab])

  // 4. Magia de UX: Auto-Pulo de Aba (Auto-Tab Switching)
  // Se o usuário pesquisa algo, o sistema avalia onde estão os resultados e pula exatamente pra aba correta.
  useEffect(() => {
      // Só realiza o pulo automático se tiver alguma coisa digitada e resultados na tela
      if (searchQuery.trim().length > 0 && baseFilteredOrders.length > 0) {
          // Descobre todas as abas das quais os pedidos encontrados pertencem
          const distinctSituations = new Set(baseFilteredOrders.map(o => (o.situacao || '').toLowerCase()));
          
          if (distinctSituations.size === 1) {
              // Se todos os resultados moram exatamente na mesma aba, TELEPORTA pra ela!
              const targetSit = [...distinctSituations][0];
              if (targetSit === 'em aberto') setActiveTab('em_aberto')
              else if (targetSit === 'aprovado') setActiveTab('aprovado')
              else if (targetSit === 'preparando envio') setActiveTab('preparando_envio')
              else if (targetSit === 'faturado') setActiveTab('faturado')
              else if (targetSit === 'pronto para envio') setActiveTab('pronto_envio')
              else if (targetSit === 'enviado') setActiveTab('enviado')
              else if (targetSit === 'entregue') setActiveTab('entregue')
              else setActiveTab('todos')
          } else {
              // Se pesquisou ex: Nome de cliente, e ele tem 1 Pedido Aberto e 1 Faturado.
              // Então teleporta pra "Todos" para a pessoa poder ver os dois ao mesmo tempo sem ocultar nenhum.
              setActiveTab('todos')
          }
      }
  }, [searchQuery, baseFilteredOrders])

  const tabs = [
    { id: 'todos', label: 'todos', count: stats.todos, color: 'text-slate-800' },
    { id: 'em_aberto', label: 'em aberto', count: stats.em_aberto, color: 'text-amber-500' },
    { id: 'aprovado', label: 'aprovado', count: stats.aprovado, color: 'text-emerald-500' },
    { id: 'preparando_envio', label: 'preparando envio', count: stats.preparando_envio, color: 'text-teal-500' },
    { id: 'faturado', label: 'faturado', count: stats.faturado, color: 'text-blue-500' },
    { id: 'pronto_envio', label: 'pronto para envio', count: stats.pronto_envio, color: 'text-orange-500' },
    { id: 'enviado', label: 'enviado', count: stats.enviado, color: 'text-indigo-500' },
    { id: 'entregue', label: 'entregue', count: stats.entregue, color: 'text-green-500' },
  ]

  return (

    <div className={cn("flex-1 flex flex-col bg-slate-50 relative", isGenerativeMode ? "p-0 min-h-0" : "min-h-full p-4 md:p-8")}>
      
      {/* HEADER ROW - Only show if not in Generative UI mode */}
      {!isGenerativeMode && (
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-6 relative">
        <div>
          <div className="flex items-center gap-2 text-xs font-medium text-slate-500 mb-2 uppercase tracking-widest">
            <span>Início</span> <span className="text-slate-300">/</span>
            <span>Vendas</span> <span className="text-slate-300">/</span>
            <span className="text-blue-600 font-bold">Pedidos Olist ERP</span>
          </div>
          <h1 className="text-3xl font-black text-slate-800 tracking-tight">Pedidos de Venda</h1>
        </div>
        
        {/* ACTION BUTTONS (Moved Filters here per UX requirement) */}
        <div className="flex flex-wrap gap-2">
          
          {/* POPOVER DE DATA (Olist Style) */}
          <div className="relative" ref={dateFilterRef}>
            <button 
              onClick={() => setShowDateFilter(!showDateFilter)}
              className={cn(
                "h-10 px-4 border text-sm font-semibold rounded-xl flex items-center gap-2 transition-all shadow-sm",
                showDateFilter 
                  ? "bg-blue-50 text-blue-700 border-blue-200" 
                  : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
              )}
            >
              <Calendar size={16} /> Data da Venda <ChevronDown size={14} className="ml-1 opacity-50" />
            </button>
            
            {showDateFilter && (
              <div className="absolute right-0 top-full mt-2 w-[min(calc(100vw-2rem),20rem)] bg-white rounded-2xl shadow-[0_10px_40px_rgba(0,0,0,0.12)] border border-slate-200 z-50 p-4 animate-in fade-in slide-in-from-top-2">
                <div className="flex justify-between items-center pb-3 border-b border-slate-100 mb-3">
                  <h3 className="font-bold text-slate-800 flex items-center gap-2"><CalendarDays size={16}/> Período</h3>
                  <button onClick={() => setShowDateFilter(false)} className="text-slate-400 hover:text-slate-600"><X size={16}/></button>
                </div>
                
                <div className="grid grid-cols-2 gap-2 mb-3">
                  <button onClick={() => setDateFilterMode('30d')} className={cn("py-2 text-sm font-semibold rounded-lg border", dateFilterMode === '30d' ? "bg-blue-50 border-blue-200 text-blue-700" : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50")}>Últimos 30 dias</button>
                  <button onClick={() => setDateFilterMode('hoje')} className={cn("py-2 text-sm font-semibold rounded-lg border", dateFilterMode === 'hoje' ? "bg-blue-50 border-blue-200 text-blue-700" : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50")}>Do Dia (Hoje)</button>
                  <button onClick={() => setDateFilterMode('mes')} className={cn("py-2 text-sm font-semibold rounded-lg border", dateFilterMode === 'mes' ? "bg-blue-50 border-blue-200 text-blue-700" : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50")}>Do Mês</button>
                  <button onClick={() => setDateFilterMode('intervalo')} className={cn("py-2 text-sm font-semibold rounded-lg border", dateFilterMode === 'intervalo' ? "bg-blue-50 border-blue-200 text-blue-700" : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50")}>Do Intervalo</button>
                </div>

                {dateFilterMode === 'intervalo' && (
                  <div className="flex flex-col gap-2 mb-4 bg-slate-50 p-3 rounded-xl border border-slate-100">
                    <div>
                      <label className="text-xs font-semibold text-slate-500 mb-1 block">De:</label>
                      <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="w-full border border-slate-200 rounded-lg p-2 text-sm font-medium focus:ring-2 focus:ring-blue-100 outline-none" />
                    </div>
                    <div>
                      <label className="text-xs font-semibold text-slate-500 mb-1 block">Até:</label>
                      <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="w-full border border-slate-200 rounded-lg p-2 text-sm font-medium focus:ring-2 focus:ring-blue-100 outline-none" />
                    </div>
                  </div>
                )}
                
                <div className="flex gap-2 mt-4 pt-3 border-t border-slate-100">
                   <button onClick={fetchOrders} className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 rounded-xl transition-colors">Aplicar</button>
                   <button onClick={() => setShowDateFilter(false)} className="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold py-2 rounded-xl transition-colors">Cancelar</button>
                </div>
              </div>
            )}
          </div>

          {/* POPOVER DE MAIS FILTROS */}
          <div className="relative" ref={moreFiltersRef}>
            <button 
              onClick={() => setShowMoreFilters(!showMoreFilters)}
              className={cn(
                "h-10 px-4 border text-sm font-semibold rounded-xl flex items-center gap-2 transition-all shadow-sm",
                showMoreFilters || filterMarketplace
                  ? "bg-blue-50 text-blue-700 border-blue-200" 
                  : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
              )}
            >
              <Filter size={16} /> Mais Filtros {filterMarketplace && <div className="w-2 h-2 bg-blue-600 rounded-full ml-1" />}
            </button>
            
            {showMoreFilters && (
              <div className="absolute right-0 top-full mt-2 w-72 bg-white rounded-2xl shadow-[0_10px_40px_rgba(0,0,0,0.12)] border border-slate-200 z-50 p-4 animate-in fade-in slide-in-from-top-2">
                <div className="flex justify-between items-center pb-3 border-b border-slate-100 mb-3">
                  <h3 className="font-bold text-slate-800 flex items-center gap-2"><Filter size={16}/> Opções</h3>
                  <button onClick={() => setShowMoreFilters(false)} className="text-slate-400 hover:text-slate-600"><X size={16}/></button>
                </div>
                
                <div className="mb-4">
                  <label className="text-xs font-semibold text-slate-500 mb-2 block">E-commerce (Marketplace)</label>
                  <select 
                    value={filterMarketplace}
                    onChange={e => setFilterMarketplace(e.target.value)}
                    className="w-full border border-slate-200 bg-slate-50 rounded-lg p-2.5 text-sm font-semibold text-slate-700 focus:ring-2 focus:ring-blue-100 outline-none"
                  >
                    <option value="">Todos</option>
                    <option value="Mercado Livre">Mercado Livre</option>
                    <option value="Shopee">Shopee</option>
                  </select>
                </div>

                <div className="mb-4">
                  <label className="text-xs font-semibold text-slate-500 mb-2 block">Marcador (Tag)</label>
                  <select 
                    value={filterMarcador}
                    onChange={e => setFilterMarcador(e.target.value)}
                    className="w-full border border-slate-200 bg-slate-50 rounded-lg p-2.5 text-sm font-semibold text-slate-700 focus:ring-2 focus:ring-blue-100 outline-none"
                  >
                    <option value="">Sem filtro por marcador</option>
                    <option value="Shopee">Shopee</option>
                    <option value="Shopee Full">Shopee Full</option>
                    <option value="Mercado Livre">Mercado Livre</option>
                    <option value="Mercado Full">Mercado Full</option>
                    <option value="Tik Tok">Tik Tok</option>
                  </select>
                </div>

                <div className="mb-4">
                  <label className="text-xs font-semibold text-slate-500 mb-2 block">Forma de Envio</label>
                  <select 
                    value={filterFormaEnvio}
                    onChange={e => setFilterFormaEnvio(e.target.value)}
                    className="w-full border border-slate-200 bg-slate-50 rounded-lg p-2.5 text-sm font-semibold text-slate-700 focus:ring-2 focus:ring-blue-100 outline-none"
                  >
                    <option value="">Todas</option>
                    {filterOptions.formasEnvio.map(f => (
                        <option key={f} value={f}>{f}</option>
                    ))}
                  </select>
                </div>
                
                <div className="flex gap-2 pt-3 border-t border-slate-100">
                   <button onClick={() => setShowMoreFilters(false)} className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 rounded-xl transition-colors">Fechar</button>
                   <button onClick={() => {setFilterMarketplace(''); setFilterMarcador(''); setFilterFormaEnvio(''); setShowMoreFilters(false);}} className="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold py-2 rounded-xl transition-colors">Limpar Tudo</button>
                </div>
              </div>
            )}
          </div>
          
          <div className="w-px h-10 bg-slate-200 mx-1"></div>

          <button onClick={() => fetchOrders(true)} className="h-10 px-4 bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 rounded-xl font-semibold text-sm transition-all flex items-center gap-2 shadow-sm">
            <RefreshCcw size={16} className={cn(loading && "animate-spin text-blue-500")} /> 
            <span className="hidden sm:inline">Atualizar ERP</span>
          </button>
        </div>
      </div>
      )}

      {/* SAP SELECT-OPTIONS MODAL (The SAP Master Piece) */}
      {showSapModal && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
              <div className="bg-[#f0f0f0] w-full max-w-2xl rounded-sm shadow-2xl border-t-[30px] border-[#33466a] overflow-hidden flex flex-col min-h-[500px]">
                  {/* SAP WINDOW TITLE BAR (Custom Look) */}
                  <div className="absolute top-0 left-0 right-0 h-[30px] flex items-center px-3 justify-between pointer-events-none">
                      <span className="text-white text-xs font-bold flex items-center gap-2"><div className="w-3 h-3 bg-indigo-400 rounded-sm"></div> Seleção múltipla por campos</span>
                      <div className="flex gap-1">
                          <div className="w-3 h-3 border border-white/40"></div>
                          <div className="w-3 h-3 border border-white/40"></div>
                      </div>
                  </div>

                  {/* SAP TABS AREA */}
                  <div className="flex bg-[#e1e1e1] border-b border-white px-2 pt-2">
                      <button onClick={() => setSapActiveTab('incSingle')} className={cn("px-4 py-1.5 text-xs font-bold border-t border-l border-r rounded-t-sm transition-all", sapActiveTab === 'incSingle' ? "bg-white border-white -mb-px" : "bg-[#d1d1d1] border-[#b1b1b1] opacity-70")}>Incluir Val. Individuais</button>
                      <button onClick={() => setSapActiveTab('incRange')} className={cn("px-4 py-1.5 text-xs font-bold border-t border-l border-r rounded-t-sm transition-all", sapActiveTab === 'incRange' ? "bg-white border-white -mb-px" : "bg-[#d1d1d1] border-[#b1b1b1] opacity-70")}>Incluir Intervalo</button>
                      <button onClick={() => setSapActiveTab('excSingle')} className={cn("px-4 py-1.5 text-xs font-bold border-t border-l border-r rounded-t-sm transition-all", sapActiveTab === 'excSingle' ? "bg-white border-white -mb-px" : "bg-[#d1d1d1] border-[#b1b1b1] opacity-70")}>Excluir Val. Individuais</button>
                      <button onClick={() => setSapActiveTab('excRange')} className={cn("px-4 py-1.5 text-xs font-bold border-t border-l border-r rounded-t-sm transition-all", sapActiveTab === 'excRange' ? "bg-white border-white -mb-px" : "bg-[#d1d1d1] border-[#b1b1b1] opacity-70")}>Excluir Intervalo</button>
                  </div>

                  {/* SAP TABLE AREA */}
                  <div className="flex-1 bg-white p-4 overflow-y-auto">
                      <div className="mb-2 text-[10px] font-bold text-slate-500 uppercase tracking-tighter">Entr. múltipla por documentos</div>
                      
                      <table className="w-full border-collapse text-xs">
                          <thead>
                              <tr className="bg-[#d9dee7] border-y border-[#b1b1b1]">
                                  <th className="w-10 p-1.5 border-r border-[#b1b1b1]"></th>
                                  <th className="p-1.5 border-r border-[#b1b1b1]">De valor</th>
                                  {(sapActiveTab === 'incRange' || sapActiveTab === 'excRange') && <th className="p-1.5">Até valor</th>}
                                  <th className="w-10"></th>
                              </tr>
                          </thead>
                          <tbody>
                              {/* RENDER ROWS BASED ON ACTIVE TAB */}
                              {((sapActiveTab === 'incSingle' ? sapIncludeSingles : (sapActiveTab === 'excSingle' ? sapExcludeSingles : (sapActiveTab === 'incRange' ? sapIncludeRanges : sapExcludeRanges)))).concat({}).map((row, idx) => (
                                  <tr key={idx} className="border-b border-slate-100 hover:bg-yellow-50/50">
                                      <td className="p-1.5 border-r border-slate-200 text-center">
                                          {(sapActiveTab.startsWith('inc')) ? (
                                              <div className="w-4 h-4 rounded-full bg-emerald-500 border border-emerald-600 flex items-center justify-center mx-auto shadow-sm">
                                                  <div className="w-1.5 h-1.5 bg-white rounded-full"></div>
                                              </div>
                                          ) : (
                                              <div className="w-4 h-4 rounded-full bg-red-500 border border-red-600 flex items-center justify-center mx-auto shadow-sm">
                                                  <div className="w-0.5 h-1.5 bg-white rotate-45 absolute transition-all"></div>
                                                  <div className="w-1.5 h-1.5 bg-white flex items-center justify-center font-bold text-[8px] text-white">=</div>
                                              </div>
                                          )}
                                      </td>
                                      <td className="p-0 border-r border-slate-200 bg-yellow-50/20">
                                          <input 
                                              type="text" 
                                              placeholder="..."
                                              className="w-full p-2 bg-transparent outline-none font-bold text-blue-900 placeholder-slate-300"
                                              value={sapActiveTab.endsWith('Range') ? row.from || '' : row || ''}
                                              onChange={(e) => {
                                                  const val = e.target.value;
                                                  if (sapActiveTab === 'incSingle') {
                                                      const list = [...sapIncludeSingles]; if(idx < list.length) list[idx] = val; else list.push(val); setSapIncludeSingles(list.filter(Boolean));
                                                  } else if (sapActiveTab === 'excSingle') {
                                                      const list = [...sapExcludeSingles]; if(idx < list.length) list[idx] = val; else list.push(val); setSapExcludeSingles(list.filter(Boolean));
                                                  } else if (sapActiveTab === 'incRange') {
                                                      const list = [...sapIncludeRanges]; if(idx < list.length) list[idx].from = val; else list.push({from: val, to: ''}); setSapIncludeRanges([...list]);
                                                  } else if (sapActiveTab === 'excRange') {
                                                      const list = [...sapExcludeRanges]; if(idx < list.length) list[idx].from = val; else list.push({from: val, to: ''}); setSapExcludeRanges([...list]);
                                                  }
                                              }}
                                          />
                                      </td>
                                      {(sapActiveTab === 'incRange' || sapActiveTab === 'excRange') && (
                                          <td className="p-0">
                                              <input 
                                                  type="text" 
                                                  placeholder="..."
                                                  className="w-full p-2 bg-transparent outline-none font-bold text-blue-900 placeholder-slate-300"
                                                  value={row.to || ''}
                                                  onChange={(e) => {
                                                      const val = e.target.value;
                                                      const list = (sapActiveTab === 'incRange' ? [...sapIncludeRanges] : [...sapExcludeRanges]);
                                                      if(idx < list.length) list[idx].to = val; else list.push({from: '', to: val});
                                                      if (sapActiveTab === 'incRange') setSapIncludeRanges([...list]); else setSapExcludeRanges([...list]);
                                                  }}
                                              />
                                          </td>
                                      )}
                                      <td className="border-l border-slate-200 bg-slate-50 text-center">
                                          <div className="w-5 h-5 bg-white border border-slate-300 rounded shadow-sm mx-auto flex items-center justify-center cursor-pointer hover:bg-slate-100">
                                              <div className="w-3 h-3 border-r-2 border-b-2 border-slate-400 rotate-45 -mt-1 ml-0.5 pointer-events-none"></div>
                                          </div>
                                      </td>
                                  </tr>
                              ))}
                          </tbody>
                      </table>
                      
                      <div className="mt-4 p-3 bg-blue-50 border border-blue-100 rounded-sm">
                          <p className="text-[10px] text-blue-600 font-medium leading-tight">DICA: Cole uma lista do Excel aqui para preenchimento rápido.</p>
                          <textarea 
                             placeholder="Cole aqui (Ex: doc1, doc2, doc3...)"
                             className="w-full mt-2 p-2 text-xs border border-blue-200 rounded-sm outline-none focus:ring-1 focus:ring-blue-400"
                             onChange={(e) => {
                                const pasted = e.target.value.split(/[\s,\n]+/).filter(Boolean);
                                if (sapActiveTab === 'incSingle') setSapIncludeSingles(pasted);
                                else if (sapActiveTab === 'excSingle') setSapExcludeSingles(pasted);
                                e.target.value = '';
                             }}
                          />
                      </div>
                  </div>

                  {/* SAP FOOTER ACTIONS */}
                  <div className="bg-[#e1e1e1] border-t border-white p-3 flex justify-between gap-2 overflow-x-auto">
                      <div className="flex gap-2">
                          <button 
                            onClick={() => {
                                setActiveSapRules({
                                    incSingles: sapIncludeSingles,
                                    incRanges: sapIncludeRanges.filter(r => r.from && r.to),
                                    excSingles: sapExcludeSingles,
                                    excRanges: sapExcludeRanges.filter(r => r.from && r.to)
                                });
                                setShowSapModal(false);
                                notify('Filtros SAP aplicados com sucesso.', 'success');
                            }}
                            className="bg-[#2a7a2a] hover:bg-[#1e5c1e] text-white text-[11px] font-bold px-6 py-1 border-b-2 border-[#154215] active:translate-y-px transition-all flex items-center gap-1"
                          >
                             <Check size={12}/> Executar (F8)
                          </button>
                          <button onClick={() => setShowSapModal(false)} className="bg-[#d1d1d1] hover:bg-[#c1c1c1] border border-[#b1b1b1] text-slate-800 text-[11px] font-bold px-4 py-1">Cancelar</button>
                      </div>
                      <button 
                        onClick={() => {
                            setSapIncludeSingles([]); setSapIncludeRanges([]); setSapExcludeSingles([]); setSapExcludeRanges([]);
                            setActiveSapRules({ incSingles: [], incRanges: [], excSingles: [], excRanges: [] });
                            notify('Filtros SAP limpos.', 'info');
                        }}
                        className="bg-red-600 hover:bg-red-700 text-white text-[11px] font-bold px-4 py-1"
                      >
                         Limpar Tudo
                      </button>
                  </div>
              </div>
          </div>
      )}

      {/* TABS E SEARCH (Lupa tomando toda a linha do meio) */}
      <div className="mb-4">
        <div className="relative flex-1 mb-4 shadow-sm border border-slate-200 rounded-2xl bg-white focus-within:ring-2 focus-within:ring-blue-100 focus-within:border-blue-400 transition-all flex items-center pr-2">
            <div className="pl-4 flex items-center pointer-events-none text-slate-400">
              <Search size={18} />
            </div>
            <input 
              type="text" 
              placeholder="Pesquise por Número do Ecommerce (Ex: 260309...), Nome ou CPF/CNPJ..." 
              className="flex-1 h-14 pl-4 pr-4 bg-transparent outline-none font-medium text-slate-700 placeholder-slate-400 rounded-2xl"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
            />
            {/* SAP MULTIPLE SELECTION ICON (Classic SAP Square with Arrow) */}
            <button 
                onClick={() => setShowSapModal(true)}
                title="Seleção múltipla por campos (Tipo SAP)"
                className={cn(
                    "w-10 h-10 rounded-xl flex items-center justify-center transition-all group",
                    hasActiveSapFilter ? "bg-indigo-600 text-white shadow-lg" : "hover:bg-slate-100 text-slate-400 hover:text-blue-600"
                )}
            >
                <div className="relative border-2 border-current w-5 h-5 rounded-sm flex items-center justify-center">
                    <div className="w-1 h-3 bg-current absolute rotate-45 -translate-y-[2px] translate-x-[2px]"></div>
                    <div className="w-2 h-2 border-r-2 border-b-2 border-current absolute translate-x-[3px] -translate-y-[1px] rotate-[-50deg]"></div>
                </div>
            </button>
        </div>

        {/* STATUS TABS */}
        <div className="flex gap-6 overflow-x-auto pb-4 border-b border-slate-200 scrollbar-hide">
          {tabs.map(tab => (
            <button 
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex flex-col items-center gap-1 min-w-[max-content] pb-4 -mb-4 border-b-[3px] transition-all px-2",
                activeTab === tab.id ? "border-blue-500" : "border-transparent opacity-60 hover:opacity-100"
              )}
            >
              <div className="flex items-center gap-2">
                 <div className={cn("w-2 h-2 rounded-full", tab.count > 0 ? tab.color.replace('text-', 'bg-') : 'bg-slate-300')} />
                 <span className="text-sm font-bold text-slate-600 uppercase tracking-wide">{tab.label}</span>
              </div>
              <span className={cn(
                "text-lg font-black tracking-tight", 
                activeTab === tab.id ? tab.color : "text-slate-400"
              )}>
                {tab.count}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* DATA TABLE V2 */}
      <div className="bg-white rounded-3xl shadow-[0_8px_30px_rgba(0,0,0,0.04)] border border-slate-200 overflow-hidden flex-1 shrink-0 flex flex-col">
        <div className="overflow-x-auto flex-1 h-0">
           <table className="w-full text-left border-collapse min-w-[1000px]">
             <thead>
               <tr className="bg-slate-50/80 border-b border-slate-200">
                 <th className="p-4 w-12"><input type="checkbox" className="w-4 h-4 rounded border-slate-300 text-blue-600" /></th>
                 <th className="p-4 text-xs font-bold uppercase tracking-wider text-slate-500">Nº Pedido</th>
                 <th className="p-4 text-xs font-bold uppercase tracking-wider text-slate-500">Data</th>
                 <th className="p-4 text-xs font-bold uppercase tracking-wider text-slate-500">Cliente</th>
                 <th className="p-4 text-xs font-bold uppercase tracking-wider text-slate-500">Total (R$)</th>
                 <th className="p-4 text-xs font-bold uppercase tracking-wider text-slate-500">Integração</th>
                 <th className="p-4 text-xs font-bold uppercase tracking-wider text-slate-500">Situação</th>
                 <th className="p-4 text-xs font-bold uppercase tracking-wider text-slate-500">Marcadores</th>
                 <th className="p-4 text-xs font-bold uppercase tracking-wider text-slate-500">Ações</th>
               </tr>
             </thead>
             <tbody className="divide-y divide-slate-100">
               {filteredOrders.length === 0 && !loading && (
                 <tr>
                   <td colSpan={8} className="p-16 text-center text-slate-400">
                     <Package size={48} className="mx-auto mb-4 opacity-30" />
                     <p className="text-lg font-bold">Nenhum pedido encontrado nesta aba.</p>
                     <p className="text-sm">Os pedidos podem estar com outro status ou o filtro ocultou.</p>
                   </td>
                 </tr>
               )}
               {filteredOrders.map((o, idx) => {
                 // Determine badge color based on ecommerce
                 let integrationBadge = 'bg-slate-100 text-slate-600 border-slate-200'
                 const ecommerce = (o.ecommerce || '').toUpperCase()
                 if (ecommerce.includes('MERCADO LIVRE')) integrationBadge = 'bg-amber-100 text-amber-800 border-amber-200'
                 else if (ecommerce.includes('SHOPEE')) integrationBadge = 'bg-orange-100 text-orange-800 border-orange-200'

                 return (
                   <tr 
                      key={o.id || idx} 
                      onClick={() => setSelectedOrderId(o.id)}
                      className="hover:bg-blue-50/50 transition-colors group cursor-pointer"
                   >
                     <td className="p-4" onClick={e => e.stopPropagation()}><input type="checkbox" className="w-4 h-4 rounded border-slate-300 text-blue-600" /></td>
                     <td className="p-4">
                       <div className="font-bold text-slate-800">{o.id}</div>
                       <div className="text-[11px] font-bold text-blue-600 bg-blue-50 px-1 py-0.5 rounded inline-block mt-1 border border-blue-100">{o.numero_ecommerce || 'S/ INT'}</div>
                     </td>
                     <td className="p-4 font-medium text-slate-600">{o.data_pedido}</td>
                     <td className="p-4">
                       <div className="font-semibold text-slate-700">{o.nome}</div>
                       <div className="text-xs text-slate-400 mt-0.5 font-mono">{o.cpf_cnpj}</div>
                     </td>
                     <td className="p-4 font-black text-slate-700">{Number(o.valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</td>
                     <td className="p-4">
                        <span className={cn("inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[10px] font-black uppercase tracking-widest border", integrationBadge)}>
                           {ecommerce || 'TINY ERP'}
                        </span>
                     </td>
                     <td className="p-4">
                        <div className="flex items-center gap-2">
                          <div className={cn("w-2 h-2 rounded-full", o.situacao === 'Entregue' ? 'bg-green-500' : 'bg-blue-500')} />
                          <span className="text-sm font-semibold text-slate-600 capitalize">{o.situacao || 'Indefinido'}</span>
                        </div>
                     </td>
                     <td className="p-4">
                        <div className="flex flex-wrap gap-1.5 max-w-[150px]">
                           {(o.marcadores && o.marcadores.length > 0) ? o.marcadores.map((mObj, mIdx) => {
                               const m = mObj.marcador || mObj
                               const bg = m.cor || '#e2e8f0'
                               // Basic contrast calculation to make text readable (white or black)
                               const hex = bg.replace('#', '')
                               const r = parseInt(hex.substring(0,2), 16) || 200
                               const g = parseInt(hex.substring(2,4), 16) || 200
                               const b = parseInt(hex.substring(4,6), 16) || 200
                               const luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
                               const fg = luma < 140 ? '#ffffff' : '#1e293b'

                               return (
                                 <span 
                                    key={mIdx} 
                                    className="px-2 py-0.5 text-[9px] font-black uppercase tracking-widest rounded border border-black/10 shadow-sm whitespace-nowrap" 
                                    style={{ backgroundColor: bg, color: fg }}
                                    title={m.descricao}
                                 >
                                    {m.descricao}
                                 </span>
                               )
                           }) : (
                               <span className="text-slate-300 font-mono text-xs">-</span>
                           )}
                        </div>
                     </td>
                     <td className="p-4">
                       <button onClick={(e) => { e.stopPropagation(); /* Future action */ }} className="px-3 py-1.5 bg-slate-100 text-slate-600 font-bold text-xs rounded-lg border border-slate-200 hover:bg-blue-600 hover:border-blue-600 hover:text-white transition-colors shadow-sm">
                         Separar Peças
                       </button>
                     </td>
                   </tr>
                 )
               })}
             </tbody>
           </table>
        </div>
        <div className="p-4 border-t border-slate-200 bg-slate-50/50 flex justify-between items-center text-sm font-semibold text-slate-500">
           <div>Página Única (Filtro Local Ativo)</div>
           <div className="flex gap-4">
              <span>Exibindo {filteredOrders.length} pedidos</span>
           </div>
        </div>
      </div>

      {/* NOVO: SLIDE-OVER DE DETALHES DO PEDIDO */}
      {selectedOrderId && (
        <OrderDetailsDrawer 
           pedidoId={selectedOrderId} 
           onClose={() => setSelectedOrderId(null)} 
        />
      )}

    </div>
  )
}

const TikTokIcon = ({ className }) => (
  <svg role="img" viewBox="0 0 24 24" className={className} xmlns="http://www.w3.org/2000/svg" fill="currentColor">
    <path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/>
  </svg>
)

function OrderDetailsDrawer({ pedidoId, onClose }) {
  const [loading, setLoading] = useState(true)
  const [details, setDetails] = useState(null)
  const [copiedText, setCopiedText] = useState(null)
  const { notify } = useFeedback()

  useEffect(() => {
    async function fetchDetails() {
      try {
        const data = await api.getTinyPedido(pedidoId)
        if (data.pedido) {
          setDetails(data.pedido)
        } else {
          notify('Detalhes não encontrados.', 'error')
          onClose()
        }
      } catch (err) {
        notify('Erro ao abrir pedido', 'error')
        onClose()
      } finally {
        setLoading(false)
      }
    }
    fetchDetails()
  }, [pedidoId])

  const handleCopy = (texto) => {
    if (!texto) return
    navigator.clipboard.writeText(texto)
    setCopiedText(texto)
    notify('Copiado para a área de transferência', 'success')
    setTimeout(() => setCopiedText(null), 2000)
  }

  // Dynamic Marketplace Aura (Inner Wash)
  const ecommerceName = details ? (typeof details.ecommerce === 'object' ? details.ecommerce.nomeEcommerce?.toUpperCase() || '' : (details.ecommerce?.toUpperCase() || '')) : ''
  const isShopee = ecommerceName.includes('SHOPEE')
  const isMeli = ecommerceName.includes('MERCADO LIVRE') || ecommerceName.includes('MERCADO')
  const isTikTok = ecommerceName.includes('TIKTOK') || ecommerceName.includes('TIK TOK')

  let modalOuterShadow = 'shadow-[0_0_80px_rgba(0,0,0,0.5)] border-slate-700/20'
  let headerBgClass = 'bg-white'
  let bodyBgClass = 'bg-slate-50'

  // Center Modal Layout (Command Center Aesthetic)
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/60 backdrop-blur-md transition-opacity p-4 md:p-8" onClick={onClose}>
      <div 
        className={cn(
          "w-full max-w-6xl bg-white h-[95vh] md:h-[90vh] rounded-[2rem] animate-in zoom-in-95 flex flex-col overflow-hidden border transition-all duration-700",
          modalOuterShadow
        )}
        onClick={e => e.stopPropagation()} 
      >
        {loading ? (
          <div className="flex-1 flex flex-col items-center justify-center text-slate-400 bg-white">
             <RefreshCcw size={48} className="animate-spin mb-4 text-blue-500" />
             <p className="font-bold text-lg">Iniciando Raio-X do Pedido...</p>
             <p className="text-sm font-medium mt-2">Buscando dados no Tiny ERP</p>
          </div>
        ) : details ? (
          <>
            {/* COMMAND CENTER HEADER (High Contrast & Clear) */}
            <div className={cn("px-8 py-5 border-b border-slate-200 z-10 flex flex-col md:flex-row md:justify-between md:items-center gap-4 shadow-sm shrink-0", headerBgClass)}>
               <div>
                  <div className="flex items-center gap-3">
                     <h2 className="text-3xl font-black text-slate-800 tracking-tight">O.S #{details.numero}</h2>
                     <div className="flex items-center">
                        <span className="px-2 py-1 bg-blue-50 text-blue-600 text-[10px] font-black rounded-l-lg uppercase tracking-widest border border-r-0 border-blue-200">
                           STATUS
                        </span>
                        <span className="px-3 py-1 bg-blue-600 text-white text-xs font-black rounded-r-lg uppercase tracking-widest border border-blue-600 shadow-sm">
                           {details.situacao}
                        </span>
                     </div>
                  </div>
                  <div className="flex items-center gap-3 mt-3">
                     <span className="flex items-center gap-1.5 text-sm font-semibold text-slate-500 bg-white px-3 py-1 rounded-md border border-slate-200 shadow-sm" title="Data da Venda">
                       <CalendarDays size={14}/> {details.data_pedido}
                     </span>
                     
                     <span className="flex items-center gap-1.5 text-sm font-bold text-rose-700 bg-rose-100/80 px-3 py-1 rounded-md border border-rose-200 shadow-sm animate-pulse-slow" title="Data Limite para Despacho">
                       <Clock size={14} className="text-rose-600"/> 
                       Despachar até: {details.data_prevista || details.data_faturamento || details.data_envio || `${details.data_pedido} 23:59`}
                     </span>

                     {/* BOLD E-COMMERCE BADGE WITH COPY FUNCTIONALITY AND LOGOS */}
                     <button 
                       onClick={() => handleCopy(details.numero_ecommerce || '')}
                       className="group flex items-center text-sm transition-transform hover:scale-105 hover:shadow-md rounded-md cursor-pointer active:scale-95"
                       title="Clique para copiar o código do e-commerce"
                     >
                       <span className={cn(
                          "px-3 py-1 rounded-l-md flex items-center justify-center h-8",
                           isShopee ? 'bg-white border-y border-l border-orange-200' : isMeli ? 'bg-amber-400' : isTikTok ? 'bg-black text-white' : 'bg-slate-800'
                       )}>
                         {isShopee && <img src={shopeeLogo} alt="Shopee" className="h-[28px] w-auto object-contain" />}
                         {isMeli && <img src={mlLogo} alt="Mercado Livre" className="h-[26px] w-auto object-contain" />}
                         {isTikTok && <TikTokIcon className="h-4 w-auto fill-current" />}
                         {isTikTok && <span className="text-[11px] font-black text-white uppercase tracking-widest px-1 ml-1">TikTok</span>}
                         {!isShopee && !isMeli && !isTikTok && <span className="text-[11px] font-black text-white uppercase tracking-widest px-1">NVS ERP</span>}
                       </span>
                       <span className="px-4 py-1 bg-slate-800 text-white font-mono font-black text-sm rounded-r-md border-l border-slate-700/50 flex items-center gap-2 h-8">
                         {details.numero_ecommerce || 'SEM INT'}
                         {copiedText === details.numero_ecommerce ? <Check size={16} className="text-emerald-400" /> : <Copy size={14} className="text-slate-400 group-hover:text-white transition-colors" />}
                       </span>
                     </button>
                  </div>
               </div>
               
               {/* TOTAL FATURADO IN HEADER */}
               <div className="flex items-center gap-6">
                 <div className="text-right">
                    <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-0.5">Total Faturado</p>
                    <p className="text-3xl font-black text-emerald-600 tracking-tighter">
                      {Number(details.total_pedido || details.valor || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                    </p>
                 </div>
                 <div className="h-10 w-px bg-slate-200"></div>
                 <button onClick={onClose} className="p-3 bg-white border border-slate-200 text-slate-500 hover:text-rose-600 rounded-2xl hover:bg-rose-50 transition-colors shadow-sm">
                    <X size={24} />
                 </button>
               </div>
            </div>

            {/* COMMAND CENTER BODY (Vertical Flow) */}
            <div className={cn("flex-1 flex flex-col overflow-hidden shrink-0 relative", bodyBgClass)}>
               
               {/* CUSTOMER INFO RIBBON (HORIZONTAL) */}
               <div className="grid grid-cols-1 md:grid-cols-3 gap-0 border-b border-slate-200 bg-white shrink-0">
                  <div className="p-6 border-b md:border-b-0 md:border-r border-slate-100 flex flex-col justify-center">
                    <h3 className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3 flex items-center gap-2">
                       <User size={14} className="text-blue-500" /> Destinatário
                    </h3>
                    <p className="font-black text-lg text-slate-800 mb-1 leading-tight">{details.cliente?.nome || details.nome}</p>
                    <p className="font-mono text-xs font-bold text-slate-500">{details.cliente?.cpf_cnpj || details.cpf_cnpj || 'Sem Cadastro de Doc.'}</p>
                    {(details.cliente?.telefone || details.cliente?.celular) && (
                      <p className="font-mono text-xs font-bold text-slate-500 mt-1">📞 {details.cliente?.celular || details.cliente?.telefone}</p>
                    )}
                  </div>

                  <div className="p-6 border-b md:border-b-0 md:border-r border-slate-100 flex flex-col justify-center">
                    <h3 className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3 flex items-center gap-2">
                       <MapPin size={14} className="text-amber-500" /> Geocalização (Entrega)
                    </h3>
                    <p className="text-sm text-slate-700 font-bold leading-relaxed">
                       {details.endereco_entrega?.endereco || details.cliente?.endereco || 'Não informado'}, {details.endereco_entrega?.numero || details.cliente?.numero || 'S/N'} 
                       {(details.endereco_entrega?.complemento || details.cliente?.complemento) && ` - ${details.endereco_entrega?.complemento || details.cliente?.complemento}`}<br/>
                       {details.endereco_entrega?.bairro || details.cliente?.bairro || 'S/ Bairro'} - {details.endereco_entrega?.cidade || details.cliente?.cidade || 'S/ Cidade'}/{details.endereco_entrega?.uf || details.cliente?.uf || ''}
                    </p>
                    <span className="inline-block mt-2 font-mono font-black text-slate-800 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded shadow-sm w-max text-xs">
                      CEP: {details.endereco_entrega?.cep || details.cliente?.cep}
                    </span>
                  </div>

                  <div className="p-6 flex flex-col justify-center">
                    <h3 className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3 flex items-center gap-2">
                       <Truck size={14} className="text-emerald-500" /> Logística Selecionada
                    </h3>
                    <p className="font-black text-slate-800 text-xl tracking-tight">{details.forma_envio || 'Transportadora Padrão'}</p>
                    <div className="flex gap-2 mt-2">
                      <span className="bg-slate-100 border border-slate-200 px-2 py-1 rounded text-xs font-black text-slate-600 font-mono">
                        CUSTO: {Number(details.valor_frete || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                      </span>
                      {Number(details.valor_frete) === 0 && (
                         <span className="bg-emerald-100 border border-emerald-200 px-2 py-1 rounded text-xs font-black text-emerald-800 tracking-widest uppercase">
                           Grátis
                         </span>
                      )}
                    </div>
                  </div>
               </div>

               {/* ITEMS LIST AREA (FULL WIDTH VERTICAL SCROLL) */}
               <div className="relative z-10 flex-1 overflow-y-auto p-6 md:p-8">
                  {/* ALERTS SECTION */}
                  {(details.obs_internas || details.observacoes) && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
                      {details.obs_internas && (
                        <div className="bg-amber-100/50 border-l-4 border-l-amber-500 border-r border-y border-amber-200/50 p-4 rounded-r-2xl">
                          <h4 className="flex items-center gap-2 text-xs font-black text-amber-900 uppercase tracking-widest mb-2"><TriangleAlert size={14}/> Obs. Interna (Aviso)</h4>
                          <p className="text-sm font-bold text-amber-800 whitespace-pre-wrap">{details.obs_internas}</p>
                        </div>
                      )}
                      {details.observacoes && (
                        <div className="bg-blue-50/50 border-l-4 border-l-blue-500 border-r border-y border-blue-100 p-4 rounded-r-2xl">
                          <h4 className="flex items-center gap-2 text-xs font-black text-blue-900 uppercase tracking-widest mb-2"><MessageSquare size={14}/> ObS. Vendedor</h4>
                          <p className="text-sm font-bold text-blue-800 whitespace-pre-wrap">{details.observacoes}</p>
                        </div>
                      )}
                    </div>
                  )}

                  {/* CAIXA DE PRODUTOS GLASSMORPHIC CONTAINER */}
                  <div className="bg-white/70 backdrop-blur-[2px] border border-slate-200/60 rounded-3xl shadow-sm overflow-hidden">
                     <div className="px-6 py-4 flex justify-between items-center border-b border-slate-200/60 bg-slate-50/50">
                        <h3 className="text-sm font-black text-slate-800 tracking-widest uppercase flex items-center gap-2"><Package size={16}/> Caixa de Produtos</h3>
                        <span className="px-3 py-1 bg-white/80 text-slate-600 font-black font-mono rounded-lg border border-slate-200/50 text-xs shadow-sm">TOTAL: {details.itens?.length || 0} ITENS</span>
                     </div>
                     
                     <div className="overflow-x-auto">
                        <table className="w-full text-left">
                           <thead className="bg-white/50 border-b border-slate-200/60">
                             <tr>
                               <th className="p-4 pl-6 text-[10px] font-black text-slate-400 uppercase tracking-widest w-12 text-center">Nº</th>
                               <th className="p-4 text-[10px] font-black text-slate-400 uppercase tracking-widest w-16 text-center">Foto</th>
                               <th className="p-4 text-[10px] font-black text-slate-400 uppercase tracking-widest min-w-[300px]">Estoque / Descrição</th>
                               <th className="p-4 text-[10px] font-black text-slate-400 uppercase tracking-widest text-center">SKU</th>
                               <th className="p-4 text-[10px] font-black text-slate-400 uppercase tracking-widest text-center">Volume</th>
                               <th className="p-4 text-[10px] font-black text-slate-400 uppercase tracking-widest text-right">Unitário</th>
                               <th className="p-4 pr-6 text-[10px] font-black text-slate-400 uppercase tracking-widest text-right">Subtotal</th>
                             </tr>
                           </thead>
                           <tbody className="divide-y divide-slate-200/50 bg-transparent relative z-10">
                             {(details.itens || []).map((i, idx) => {
                                const it = i.item
                                const imgUrl = it.anexos?.[0]?.url || it.imagem_url || it.imagem || it.url_imagem || null
                                
                                return (
                                  <tr key={idx} className="hover:bg-blue-50/40 transition-colors">
                                    <td className="p-4 pl-6 text-sm font-black text-slate-300 text-center">{String(idx + 1).padStart(2, '0')}</td>
                                    <td className="p-4 text-center">
                                      <div className="w-12 h-12 rounded-xl bg-slate-50/60 border border-slate-200/60 flex items-center justify-center overflow-hidden shrink-0 mx-auto shadow-sm">
                                        {imgUrl ? (
                                          <img src={imgUrl} alt="Produto" className="w-full h-full object-cover" />
                                        ) : (
                                          <Image className="text-slate-300" size={20} />
                                        )}
                                      </div>
                                    </td>
                                    <td className="p-4 text-sm font-semibold text-slate-700 py-6">
                                       <div className="max-w-[400px] leading-tight">
                                          {it.descricao}
                                       </div>
                                    </td>
                                    <td className="p-4 text-center">
                                       <button 
                                          onClick={() => handleCopy(it.codigo)}
                                          className="group inline-flex items-center gap-2 bg-slate-50/60 border border-slate-200/60 px-3 py-1.5 rounded-md text-xs font-mono font-black text-slate-800 shadow-sm cursor-pointer hover:bg-slate-100/80 hover:border-slate-300 transition-all active:scale-95"
                                          title="Clique para copiar SKU"
                                       >
                                          {it.codigo}
                                          {copiedText === it.codigo ? <Check size={14} className="text-emerald-500" /> : <Copy size={12} className="text-slate-400 group-hover:text-slate-600 transition-colors" />}
                                       </button>
                                    </td>
                                    <td className="p-4 text-center">
                                      <span className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-blue-100 text-blue-800 font-black font-mono border border-blue-200 shadow-sm">
                                        {Number(it.quantidade)}
                                      </span>
                                      <div className="text-[10px] text-slate-400 uppercase font-black mt-1">{it.unidade || 'UN'}</div>
                                    </td>
                                    <td className="p-4 text-sm font-bold text-slate-500 text-right font-mono">
                                      {Number(it.valor_unitario).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                                    </td>
                                    <td className="p-4 pr-6 text-sm font-black text-slate-800 text-right font-mono">
                                      {Number(it.quantidade * it.valor_unitario).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                                    </td>
                                  </tr>
                                )
                             })}
                           </tbody>
                        </table>
                     </div>
                     {/* Footer com descontos se houver */}
                     {Number(details.valor_desconto) > 0 && (
                        <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 text-right">
                           <span className="text-xs font-bold text-slate-500 uppercase mr-4">Desconto Aplicado</span>
                           <span className="font-mono font-black text-rose-500">- {Number(details.valor_desconto).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</span>
                        </div>
                     )}
                  </div>
               </div>
            </div>

            {/* COMMAND CENTER FOOTER */}
            <div className="px-8 py-5 border-t border-slate-200 bg-white flex justify-between items-center z-10 rounded-b-[2rem] shrink-0">
               <div className="text-xs font-bold text-slate-400 flex items-center gap-2">
                 <ShieldCheck size={16} className="text-emerald-500" />
                 Dados Sincronizados Oficialmente - API Tiny ERP
               </div>
               <div className="flex gap-4">
                 <button onClick={onClose} className="px-6 py-3 bg-white border-2 border-slate-200 text-slate-600 rounded-2xl font-black hover:bg-slate-50 transition-colors hover:border-slate-300">
                   Cancelar Visão
                 </button>
                 <button className="px-8 py-3 bg-blue-600 border-2 border-transparent text-white rounded-2xl font-black hover:bg-blue-700 transition-colors shadow-[0_4px_14px_rgba(37,99,235,0.39)] flex items-center gap-2 hover:-translate-y-0.5 duration-200 group">
                   <Package size={20} className="group-hover:scale-110 transition-transform" /> Transformar em Separação WMS
                 </button>
               </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}

