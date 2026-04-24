import { useState, useEffect, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useFeedback } from '../components/ui/FeedbackProvider'
import {
  Search, RefreshCcw, Package, ClipboardList,
  ChevronDown, ChevronLeft, ChevronRight, X, Info, Filter, Eraser, Clock,
  MapPin, Truck, Calendar, AlertCircle, CheckCircle2,
  PackageSearch, ArrowUpDown, List, Undo2, Trash2, Copy,
  Send, CheckCheck, XCircle, RotateCcw, History
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
  const fmt = (d) => {
    const dd = String(d.getDate()).padStart(2, '0')
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const yyyy = d.getFullYear()
    return `${dd}/${mm}/${yyyy}`
  }

  const getDates = () => {
    const today = fmt(new Date())
    return { from: today, to: today } // padrão = hoje
  }

  const getWideDates = () => {
    const today = new Date()
    const past = new Date()
    past.setDate(today.getDate() - 59) // 60 dias — para aba separadas
    return { from: fmt(past), to: fmt(today) }
  }

  const [dateRange, setDateRange] = useState(getDates())
  const [showDateMenu, setShowDateMenu] = useState(false)
  const [selectedPeriod, setSelectedPeriod] = useState('dia')
  const [showFilterMenu, setShowFilterMenu] = useState(false)
  const [marketplaceFilter, setMarketplaceFilter] = useState('all')
  const [selectedIds, setSelectedIds] = useState([])              // aguardando tab
  const [selectedEmSepIds, setSelectedEmSepIds] = useState([])    // em_separacao tab
  const [selectedSeparadasIds, setSelectedSeparadasIds] = useState([]) // separadas tab
  const [selectedEnviadasIds, setSelectedEnviadasIds] = useState([])   // enviada_erp tab
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [detailSep, setDetailSep] = useState(null)   // objeto completo da separação
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailImages, setDetailImages] = useState({}) // sku → url
  const [copiedKey, setCopiedKey] = useState(null)
  const [detailIndex, setDetailIndex] = useState(null) // índice no filteredItems
  const copyText = (text, key) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedKey(key)
      setTimeout(() => setCopiedKey(null), 1500)
    })
  }
  // Mapa de status local: { separation_id: { status, list_id } }
  // Fonte de verdade local — Tiny é somente-leitura, nunca escrevemos de volta
  const [localStatuses, setLocalStatuses] = useState({})
  // Lista enriquecida de docs rastreados (em_separacao + concluida) — sem filtro de data
  const [trackedSeparacoes, setTrackedSeparacoes] = useState([])
  const [backfilling, setBackfilling] = useState(false) // backfill automático em andamento
  const [hasFetchedSeparacoes, setHasFetchedSeparacoes] = useState(false) // true após 1ª busca manual
  const [erpSending, setErpSending] = useState(false)
  const [erpLogs, setErpLogs] = useState([])           // logs do drawer
  const [erpLogsLoading, setErpLogsLoading] = useState(false)

  async function fetchLocalStatuses() {
    try {
      const data = await api.getSeparationStatuses()
      setLocalStatuses(data || {})
    } catch (err) {
      console.error('Erro ao buscar status locais:', err)
    }
  }

  async function fetchTrackedSeparacoes() {
    setLoading(true)
    try {
      const data = await api.getTrackedSeparacoes()
      setTrackedSeparacoes(data?.separacoes || [])
      // Backend disparou backfill em background → avisa e re-busca após ~8s
      if (data?.backfill_triggered) {
        setBackfilling(true)
        setTimeout(async () => {
          try {
            const fresh = await api.getTrackedSeparacoes()
            setTrackedSeparacoes(fresh?.separacoes || [])
          } catch {}
          setBackfilling(false)
        }, 8000)
      }
    } catch (err) {
      console.error('Erro ao buscar separações rastreadas:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleRevertToAguardando = async () => {
    if (!selectedEmSepIds.length) return
    setLoading(true)
    try {
      await api.revertSeparationStatuses(selectedEmSepIds.map(String))
      notify(`${selectedEmSepIds.length} documento(s) devolvido(s) para Aguardando Separação.`, 'success')
      setSelectedEmSepIds([])
      await Promise.all([fetchLocalStatuses(), fetchTrackedSeparacoes()])
    } catch (err) {
      notify('Erro ao reverter status.', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteSelected = async () => {
    const ids = confirmDelete === 'separadas' ? selectedSeparadasIds : selectedEmSepIds
    if (!ids.length) return
    setLoading(true)
    setConfirmDelete(false)
    try {
      await api.deleteSeparationStatuses(ids.map(String))
      notify(`${ids.length} documento(s) removido(s).`, 'success')
      if (confirmDelete === 'separadas') setSelectedSeparadasIds([])
      else setSelectedEmSepIds([])
      await Promise.all([fetchLocalStatuses(), fetchTrackedSeparacoes()])
    } catch (err) {
      notify('Erro ao excluir.', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleSendToErp = async (ids) => {
    setErpSending(true)
    try {
      const res = await api.sendToErp(ids.map(String))
      if (res.failed === 0) {
        notify(`${res.success} documento(s) enviado(s) ao ERP com sucesso!`, 'success')
      } else {
        notify(`${res.success} enviado(s), ${res.failed} com erro. Verifique os logs na aba Enviadas ERP.`, 'warning')
      }
      setSelectedSeparadasIds([])
      setSelectedEnviadasIds([])
      await fetchTrackedSeparacoes()
    } catch {
      notify('Erro ao enviar documentos ao ERP.', 'error')
    } finally {
      setErpSending(false)
    }
  }

  const openDetail = async (item, index = null) => {
    if (index !== null) setDetailIndex(index)
    setDetailSep({ _loading: true, _item: item })
    setDetailImages({})
    setErpLogs([])
    setDetailLoading(true)
    try {
      const data = await api.getSeparacaoDetail(item.id)
      setDetailSep({ ...data, _item: item })
      // Busca imagens em paralelo para todos os SKUs dos itens
      const skus = (data.separacao?.itens || []).map(it => it.codigo).filter(Boolean)
      if (skus.length) {
        const results = await Promise.allSettled(skus.map(sku => api.getProductImage(sku)))
        const imgs = {}
        results.forEach((r, i) => {
          if (r.status === 'fulfilled' && r.value?.image_url) imgs[skus[i]] = r.value.image_url
        })
        setDetailImages(imgs)
      }
      // Busca logs ERP se o item já passou pelo envio
      const localSt = item.local_status
      if (localSt === 'enviada_erp' || localSt === 'erro_envio_erp') {
        setErpLogsLoading(true)
        api.getErpSendLogs(item.id)
          .then(r => setErpLogs(r.logs || []))
          .catch(() => {})
          .finally(() => setErpLogsLoading(false))
      }
    } catch {
      notify('Erro ao carregar detalhes da separação.', 'error')
      setDetailSep(null)
    } finally {
      setDetailLoading(false)
    }
  }

  async function fetchSeparacoes(from = dateRange.from, to = dateRange.to) {
    setLoading(true)
    setHasFetchedSeparacoes(true)
    setSelectedIds([])
    setSelectedEmSepIds([])
    setSelectedSeparadasIds([])
    setSelectedEnviadasIds([])
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
      await Promise.all([fetchLocalStatuses(), fetchTrackedSeparacoes()])
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
    // fetchSeparacoes() — não carrega automaticamente. Usuário seleciona período e clica Aplicar.
    fetchLocalStatuses()
    fetchTrackedSeparacoes() // em_separacao + separadas do DB local — sem filtro de data
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
    const matchSearch = (s, q) => !q ||
      (s.id || '').toString().includes(q) ||
      (s.destinatario || '').toLowerCase().includes(q) ||
      (s.numero || '').toLowerCase().includes(q) ||
      (s.numeroPedidoEcommerce || '').toLowerCase().includes(q)

    const q = searchQuery.toLowerCase()

    // em_separacao, separadas e enviada_erp: sempre do DB local — sem filtro de data
    if (activeTab === 'em_separacao' || activeTab === 'separadas' || activeTab === 'enviada_erp') {
      const targetStatuses = activeTab === 'em_separacao' ? ['em_separacao']
        : activeTab === 'separadas' ? ['concluida']
        : ['enviada_erp', 'erro_envio_erp']
      return trackedSeparacoes.filter(s =>
        targetStatuses.includes(s.local_status) &&
        matchSearch(s, q) &&
        matchMarketplace(s, marketplaceFilter)
      )
    }

    // aguardando e embaladas: da API do Tiny (com filtro de data)
    return separacoes.filter(s => {
      const localStatus = resolveStatus(s)
      const sit = (s.situacao || '').toString()
      let matchTab = false
      if (activeTab === 'aguardando') matchTab = localStatus === 'aguardando' || (!localStatus && sit === '1')
      else if (activeTab === 'embaladas') matchTab = sit === '3'
      return matchSearch(s, q) && matchTab && matchMarketplace(s, marketplaceFilter)
    })
  }, [separacoes, trackedSeparacoes, searchQuery, activeTab, marketplaceFilter, localStatuses])

  const stats = useMemo(() => {
    const counts = { aguardando: 0, em_separacao: 0, separadas: 0, embaladas: 0, enviada_erp: 0 }

    // em_separacao, separadas e enviada_erp: contagem do DB local (sem filtro de data)
    trackedSeparacoes.forEach(s => {
      if (!matchMarketplace(s, marketplaceFilter)) return
      if (s.local_status === 'em_separacao') counts.em_separacao++
      else if (s.local_status === 'concluida') counts.separadas++
      else if (s.local_status === 'enviada_erp' || s.local_status === 'erro_envio_erp') counts.enviada_erp++
    })

    // aguardando e embaladas: contagem da API do Tiny
    separacoes.forEach(s => {
      if (!matchMarketplace(s, marketplaceFilter)) return

      const localStatus = resolveStatus(s)
      const sit = (s.situacao || '').toString()

      if (localStatus === 'aguardando' || (!localStatus && sit === '1')) counts.aguardando++
      else if (sit === '3') counts.embaladas++
      // em_separacao e separadas já contados via trackedSeparacoes acima
    })
    return counts
  }, [separacoes, trackedSeparacoes, marketplaceFilter, localStatuses])

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

      {/* BANNER DE BACKFILL AUTOMÁTICO */}
      {backfilling && (
        <div className="mx-2 mb-4 flex items-center gap-3 px-4 py-3 bg-blue-50 border border-blue-200 rounded-xl text-xs font-semibold text-blue-700 animate-pulse">
          <RefreshCcw size={14} className="animate-spin shrink-0" />
          Sincronizando dados de notas antigas... os campos serão preenchidos em instantes.
        </div>
      )}

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
            onClick={() => { setMarketplaceFilter('all'); setSearchQuery(''); setSelectedPeriod('dia'); applyPeriod('dia'); }} 
            className="h-10 px-4 text-slate-400 hover:text-slate-600 text-xs font-medium flex items-center gap-2 mr-2"
          >
            <Eraser size={14} /> limpar filtros
          </button>

          <button
            onClick={async () => { await fetchSeparacoes(); await Promise.all([fetchLocalStatuses(), fetchTrackedSeparacoes()]) }}
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
          onClick={() => setActiveTab('enviada_erp')}
          className={cn(
            "pb-4 flex flex-col items-center gap-1 transition-all border-b-2 px-4",
            activeTab === 'enviada_erp' ? "border-violet-500" : "border-transparent opacity-50"
          )}
        >
          <span className="text-sm font-medium text-slate-600 text-center">
            enviadas ERP <span className="text-[10px] opacity-40 block -mt-1 font-black">Tiny</span>
          </span>
          <span className="text-2xl font-light text-slate-800">{stats.enviada_erp}</span>
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
                   {activeTab === 'separadas' && (
                     <input type="checkbox" className="rounded w-4 h-4 text-emerald-600 focus:ring-emerald-400 cursor-pointer"
                       checked={filteredItems.length > 0 && selectedSeparadasIds.length === filteredItems.length}
                       onChange={() => setSelectedSeparadasIds(
                         selectedSeparadasIds.length === filteredItems.length ? [] : filteredItems.map(s => s.id)
                       )}
                     />
                   )}
                   {activeTab === 'enviada_erp' && (
                     <input type="checkbox" className="rounded w-4 h-4 text-violet-600 focus:ring-violet-400 cursor-pointer"
                       checked={filteredItems.length > 0 && selectedEnviadasIds.length === filteredItems.length}
                       onChange={() => setSelectedEnviadasIds(
                         selectedEnviadasIds.length === filteredItems.length ? [] : filteredItems.map(s => s.id)
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
                  <td colSpan={activeTab === 'em_separacao' ? 8 : 7} className="p-24 text-center text-slate-300">
                    {activeTab === 'aguardando' && !hasFetchedSeparacoes ? (
                      <div className="flex flex-col items-center gap-4">
                        <Calendar size={48} className="opacity-20" />
                        <p className="text-base font-semibold text-slate-400">Selecione um período e clique em <span className="font-black text-blue-500">Aplicar</span></p>
                        <p className="text-xs text-slate-300">Os documentos aguardando separação serão carregados do Tiny ERP</p>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center gap-3">
                        <PackageSearch size={48} className="opacity-10" />
                        <p className="text-base font-light italic">Nenhum documento encontrado</p>
                      </div>
                    )}
                  </td>
                </tr>
              ) : (
                filteredItems.map((item, idx) => (
                  <tr
                    key={item.id}
                    onClick={() => openDetail(item, idx)}
                    className={cn(
                      "hover:bg-slate-50 group transition-colors text-xs font-medium text-slate-700 cursor-pointer",
                      activeTab === 'aguardando' && selectedIds.includes(item.id) && "bg-blue-50/50",
                      activeTab === 'em_separacao' && selectedEmSepIds.includes(item.id) && "bg-orange-50/50",
                      activeTab === 'separadas' && selectedSeparadasIds.includes(item.id) && "bg-emerald-50/50",
                      activeTab === 'enviada_erp' && selectedEnviadasIds.includes(item.id) && "bg-violet-50/50"
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
                      {activeTab === 'separadas' && (
                        <input type="checkbox" className="rounded w-4 h-4 text-emerald-600 focus:ring-emerald-400 cursor-pointer"
                          checked={selectedSeparadasIds.includes(item.id)}
                          onChange={() => setSelectedSeparadasIds(prev =>
                            prev.includes(item.id) ? prev.filter(x => x !== item.id) : [...prev, item.id]
                          )}
                          onClick={e => e.stopPropagation()}
                        />
                      )}
                      {activeTab === 'enviada_erp' && (
                        <input type="checkbox" className="rounded w-4 h-4 text-violet-600 focus:ring-violet-400 cursor-pointer"
                          checked={selectedEnviadasIds.includes(item.id)}
                          onChange={() => setSelectedEnviadasIds(prev =>
                            prev.includes(item.id) ? prev.filter(x => x !== item.id) : [...prev, item.id]
                          )}
                          onClick={e => e.stopPropagation()}
                        />
                      )}
                    </td>
                    <td className="p-4">
                       <span className="text-slate-400 text-[10px] mr-1">...</span>
                       <span className="text-blue-600 font-bold">Nota {item.numero || 'S/N'}</span>
                       <p className="text-[10px] text-slate-400 mt-1 uppercase">Nº EC {item.numeroPedidoEcommerce || '---'}</p>
                       {item.numero_pedido && <p className="text-[10px] text-slate-400">Pedido {item.numero_pedido}</p>}
                    </td>
                    <td className="p-4 font-semibold text-slate-800">{item.destinatario || 'Sem nome'}</td>
                    <td className="p-4 text-slate-600 font-bold">{getFormaEnvioNome(item)}</td>
                    {activeTab === 'em_separacao' && (
                      <td className="p-4">
                        {item.list_name
                          ? <span className="bg-blue-50 border border-blue-200 text-blue-700 px-2.5 py-1 rounded-lg text-[11px] font-black font-mono">
                              {item.list_name}
                            </span>
                          : <span className="text-slate-300 text-xs">—</span>
                        }
                      </td>
                    )}
                    <td className="p-4 text-slate-500">{item.dataEmissao || item.dataCriacao}</td>
                    <td className="p-4 text-slate-500">{item.prazo_maximo || '---'}</td>
                    <td className="p-4">
                       <div className="flex flex-wrap gap-1">
                          {activeTab === 'enviada_erp' && (
                            item.local_status === 'enviada_erp'
                              ? <span className="bg-violet-50 text-violet-700 border border-violet-200 px-2.5 py-1 rounded-full text-[9px] font-black flex items-center gap-1">
                                  <CheckCheck size={11} /> Enviado
                                </span>
                              : <span className="bg-red-50 text-red-600 border border-red-200 px-2.5 py-1 rounded-full text-[9px] font-black flex items-center gap-1">
                                  <XCircle size={11} /> Erro
                                </span>
                          )}
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
            onClick={() => setConfirmDelete('em_separacao')}
            disabled={loading}
            className="bg-red-600 hover:bg-red-500 disabled:opacity-50 active:scale-95 text-white h-12 px-8 rounded-full font-black text-xs uppercase tracking-widest flex items-center gap-3 transition-all shadow-xl shadow-red-600/30"
          >
            <Trash2 size={18} />
            excluir
          </button>

          <button
            onClick={() => setSelectedEmSepIds([])}
            className="text-white/40 hover:text-white text-[10px] font-bold uppercase tracking-widest transition-colors"
          >
            cancelar
          </button>
        </div>
      )}

      {/* FLOATING ACTION BAR — SEPARADAS: reverter para aguardando, enviar ERP ou excluir */}
      {selectedSeparadasIds.length > 0 && (
        <div className="fixed bottom-10 left-1/2 -translate-x-1/2 bg-slate-900/90 backdrop-blur-md border border-white/10 text-white px-8 py-4 rounded-full shadow-2xl flex items-center gap-10 animate-in slide-in-from-bottom-10 duration-500 z-[1000]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-emerald-500 rounded-full flex items-center justify-center font-black text-sm shadow-lg shadow-emerald-500/20">
              {selectedSeparadasIds.length}
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-black uppercase tracking-widest text-emerald-400 leading-none">separadas</span>
              <span className="text-[9px] text-white/40 font-bold uppercase tracking-widest mt-1">selecionados</span>
            </div>
          </div>

          <div className="h-8 w-[1px] bg-white/10" />

          <button
            onClick={() => handleSendToErp(selectedSeparadasIds)}
            disabled={erpSending || loading}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 active:scale-95 text-white h-12 px-8 rounded-full font-black text-xs uppercase tracking-widest flex items-center gap-3 transition-all shadow-xl shadow-blue-600/30"
          >
            {erpSending ? <RefreshCcw size={18} className="animate-spin" /> : <Send size={18} />}
            enviar para ERP
          </button>

          <button
            onClick={async () => {
              setLoading(true)
              try {
                await api.revertSeparationStatuses(selectedSeparadasIds.map(String))
                notify(`${selectedSeparadasIds.length} documento(s) devolvido(s) para Aguardando Separação.`, 'success')
                setSelectedSeparadasIds([])
                await Promise.all([fetchLocalStatuses(), fetchTrackedSeparacoes()])
              } catch { notify('Erro ao reverter status.', 'error') }
              finally { setLoading(false) }
            }}
            disabled={loading || erpSending}
            className="bg-orange-500 hover:bg-orange-400 disabled:opacity-50 active:scale-95 text-white h-12 px-8 rounded-full font-black text-xs uppercase tracking-widest flex items-center gap-3 transition-all shadow-xl shadow-orange-500/30"
          >
            {loading ? <RefreshCcw size={18} className="animate-spin" /> : <Undo2 size={18} />}
            mover para aguardando
          </button>

          <button
            onClick={() => setConfirmDelete('separadas')}
            disabled={loading || erpSending}
            className="bg-red-600 hover:bg-red-500 disabled:opacity-50 active:scale-95 text-white h-12 px-8 rounded-full font-black text-xs uppercase tracking-widest flex items-center gap-3 transition-all shadow-xl shadow-red-600/30"
          >
            <Trash2 size={18} />
            excluir
          </button>

          <button
            onClick={() => setSelectedSeparadasIds([])}
            className="text-white/40 hover:text-white text-[10px] font-bold uppercase tracking-widest transition-colors"
          >
            cancelar
          </button>
        </div>
      )}

      {/* FLOATING ACTION BAR — ENVIADAS ERP: re-enviar */}
      {selectedEnviadasIds.length > 0 && (
        <div className="fixed bottom-10 left-1/2 -translate-x-1/2 bg-slate-900/90 backdrop-blur-md border border-white/10 text-white px-8 py-4 rounded-full shadow-2xl flex items-center gap-10 animate-in slide-in-from-bottom-10 duration-500 z-[1000]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-violet-600 rounded-full flex items-center justify-center font-black text-sm shadow-lg shadow-violet-500/20">
              {selectedEnviadasIds.length}
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-black uppercase tracking-widest text-violet-400 leading-none">enviadas ERP</span>
              <span className="text-[9px] text-white/40 font-bold uppercase tracking-widest mt-1">selecionados</span>
            </div>
          </div>

          <div className="h-8 w-[1px] bg-white/10" />

          <button
            onClick={() => handleSendToErp(selectedEnviadasIds)}
            disabled={erpSending}
            className="bg-violet-600 hover:bg-violet-500 disabled:opacity-50 active:scale-95 text-white h-12 px-8 rounded-full font-black text-xs uppercase tracking-widest flex items-center gap-3 transition-all shadow-xl shadow-violet-600/30"
          >
            {erpSending ? <RefreshCcw size={18} className="animate-spin" /> : <RotateCcw size={18} />}
            re-enviar
          </button>

          <button
            onClick={() => setSelectedEnviadasIds([])}
            className="text-white/40 hover:text-white text-[10px] font-bold uppercase tracking-widest transition-colors"
          >
            cancelar
          </button>
        </div>
      )}

      {/* DRAWER DE DETALHE DA SEPARAÇÃO */}
      {detailSep && (
        <div className="fixed inset-0 z-[150] flex">
          {/* Overlay — oculto no mobile, visível a partir de sm */}
          <div className="hidden sm:flex flex-1 bg-slate-900/40 backdrop-blur-sm" onClick={() => setDetailSep(null)} />
          {/* Painel — tela cheia no mobile, drawer lateral no sm+ */}
          <div className="w-full sm:max-w-xl bg-white shadow-2xl flex flex-col overflow-hidden animate-in slide-in-from-right duration-300">
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-slate-100">
              <div className="flex-1 min-w-0">
                <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">
                  Separação {detailIndex !== null ? `· ${detailIndex + 1} / ${filteredItems.length}` : ''}
                </p>
                <h2 className="text-xl font-black text-slate-900">Nota {detailSep._item?.numero || detailSep.separacao?.numero || 'S/N'}</h2>
              </div>
              <div className="flex items-center gap-1 ml-3 shrink-0">
                <button
                  onClick={() => { const i = detailIndex - 1; if (i >= 0) openDetail(filteredItems[i], i) }}
                  disabled={detailIndex === null || detailIndex === 0}
                  className="p-2 text-slate-300 hover:text-slate-700 rounded-xl hover:bg-slate-50 transition-all disabled:opacity-20 disabled:cursor-not-allowed"
                >
                  <ChevronLeft size={20} />
                </button>
                <button
                  onClick={() => { const i = detailIndex + 1; if (i < filteredItems.length) openDetail(filteredItems[i], i) }}
                  disabled={detailIndex === null || detailIndex >= filteredItems.length - 1}
                  className="p-2 text-slate-300 hover:text-slate-700 rounded-xl hover:bg-slate-50 transition-all disabled:opacity-20 disabled:cursor-not-allowed"
                >
                  <ChevronRight size={20} />
                </button>
                <button onClick={() => setDetailSep(null)} className="p-2 text-slate-300 hover:text-slate-700 rounded-xl hover:bg-slate-50 transition-all ml-1">
                  <X size={20} />
                </button>
              </div>
            </div>

            {detailLoading || detailSep._loading ? (
              <div className="flex-1 flex items-center justify-center">
                <RefreshCcw size={24} className="animate-spin text-slate-300" />
              </div>
            ) : (
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {/* Status + progresso */}
                <div className="flex items-center gap-3 flex-wrap">
                  {detailSep.local_status === 'em_separacao' && <span className="px-3 py-1 bg-orange-50 text-orange-600 border border-orange-200 rounded-full text-[10px] font-black uppercase tracking-widest">● em separação</span>}
                  {detailSep.local_status === 'concluida' && <span className="px-3 py-1 bg-emerald-50 text-emerald-600 border border-emerald-200 rounded-full text-[10px] font-black uppercase tracking-widest">● separada</span>}
                  {detailSep.local_status === 'enviada_erp' && <span className="px-3 py-1 bg-violet-50 text-violet-700 border border-violet-200 rounded-full text-[10px] font-black uppercase tracking-widest flex items-center gap-1"><CheckCheck size={12}/> enviada ERP</span>}
                  {detailSep.local_status === 'erro_envio_erp' && <span className="px-3 py-1 bg-red-50 text-red-600 border border-red-200 rounded-full text-[10px] font-black uppercase tracking-widest flex items-center gap-1"><XCircle size={12}/> erro no envio ERP</span>}
                  {!detailSep.local_status && <span className="px-3 py-1 bg-slate-50 text-slate-500 border border-slate-200 rounded-full text-[10px] font-black uppercase tracking-widest">● aguardando separação</span>}
                  {detailSep.picking_progress != null && (
                    <span className="px-3 py-1 bg-blue-50 text-blue-600 border border-blue-200 rounded-full text-[10px] font-black uppercase tracking-widest">
                      {detailSep.picking_progress.pct}% separado
                    </span>
                  )}
                </div>

                {/* Dados da nota */}
                <div>
                  <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3">Dados da nota</p>
                  <div className="grid grid-cols-2 gap-4 text-xs">
                    {[
                      ['Destinatário', detailSep.separacao?.destinatario || detailSep._item?.destinatario, 'dest'],
                      ['Número', detailSep.separacao?.numero || detailSep._item?.numero, 'num'],
                      ['Data emissão', detailSep.separacao?.dataEmissao || detailSep._item?.dataEmissao, null],
                      ['Prazo máx. despacho', detailSep.separacao?.prazoMaximoDespacho || detailSep.separacao?.prazoMaximo || detailSep.separacao?.prazo_maximo || detailSep._item?.prazo_maximo, null],
                      ['Nº EC', detailSep.separacao?.numeroPedidoEcommerce || detailSep._item?.numeroPedidoEcommerce, 'ec'],
                      ['Forma de envio', (typeof detailSep.separacao?.formaEnvio === 'string' ? detailSep.separacao.formaEnvio : detailSep.separacao?.formaEnvio?.descricao) || detailSep._item?.forma_envio_descricao || '—', null],
                    ].map(([label, value, copyKey]) => (
                      <div key={label}>
                        <p className="text-[10px] text-slate-400 font-semibold mb-0.5">{label}</p>
                        <div className="flex items-center gap-1">
                          <p className="font-bold text-slate-800">{value || '—'}</p>
                          {copyKey && value && (
                            <button onClick={() => copyText(value, copyKey)} className="p-1 text-slate-300 hover:text-blue-500 transition-colors rounded">
                              {copiedKey === copyKey ? <span className="text-[9px] text-emerald-500 font-black">✓</span> : <Copy size={11} />}
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Itens da nota */}
                <div>
                  <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3">Itens da nota</p>
                  <div className="rounded-2xl border border-slate-100 overflow-hidden">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="bg-slate-50 border-b border-slate-100 text-[10px] font-black text-slate-400 uppercase tracking-wider">
                          <th className="p-3 text-left">Produto</th>
                          <th className="p-3 text-left">SKU</th>
                          <th className="p-3 text-center">Qtd</th>
                          <th className="p-3 text-left">Local</th>
                          <th className="p-3 text-center">Sep.</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {(detailSep.separacao?.itens || []).map((it, idx) => {
                          const progress = detailSep.picking_progress?.items?.find(p => p.sku === it.codigo)
                          const done = progress ? progress.qty_picked >= progress.quantity : null
                          const shortage = progress?.is_shortage
                          return (
                            <tr key={idx} className="bg-slate-50 hover:bg-slate-100">
                              <td className="p-3 text-slate-700 font-medium max-w-[200px]">
                                <div className="flex items-center gap-2">
                                  <div
                                    className="w-10 h-10 rounded-lg border border-slate-300 shrink-0 overflow-hidden flex items-center justify-center"
                                    style={{backgroundColor:'#e5e7eb',backgroundImage:'linear-gradient(45deg,#d1d5db 25%,transparent 25%),linear-gradient(-45deg,#d1d5db 25%,transparent 25%),linear-gradient(45deg,transparent 75%,#d1d5db 75%),linear-gradient(-45deg,transparent 75%,#d1d5db 75%)',backgroundSize:'8px 8px',backgroundPosition:'0 0,0 4px,4px -4px,-4px 0'}}
                                  >
                                    {detailImages[it.codigo] && (
                                      <img src={detailImages[it.codigo]} alt={it.codigo} className="w-full h-full object-contain" onError={e => e.currentTarget.style.display='none'} />
                                    )}
                                  </div>
                                  <p className="line-clamp-2">{it.descricao}</p>
                                </div>
                              </td>
                              <td className="p-3">
                                <div className="flex items-center gap-1">
                                  <span className="font-mono text-[10px] text-blue-600 font-black">{it.codigo}</span>
                                  <button onClick={() => copyText(it.codigo, `sku-${idx}`)} className="p-1 text-slate-300 hover:text-blue-500 transition-colors rounded">
                                    {copiedKey === `sku-${idx}` ? <span className="text-[9px] text-emerald-500 font-black">✓</span> : <Copy size={11} />}
                                  </button>
                                </div>
                              </td>
                              <td className="p-3 text-center font-bold text-slate-700">{Number(it.quantidade) % 1 === 0 ? parseInt(it.quantidade) : parseFloat(it.quantidade).toFixed(2)}</td>
                              <td className="p-3 text-slate-400">{it.localizacao || '—'}</td>
                              <td className="p-3 text-center">
                                {done === null ? <span className="text-slate-300">—</span>
                                  : shortage ? <span className="text-amber-500 font-black text-[10px]">FALTA</span>
                                  : done ? <span className="text-emerald-500 font-black text-[10px]">✓</span>
                                  : <span className="text-slate-300 font-black text-[10px]">{progress.qty_picked}/{progress.quantity}</span>
                                }
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
                {/* Histórico de envios ERP — só aparece se o doc já passou pelo envio */}
                {(detailSep._item?.local_status === 'enviada_erp' || detailSep._item?.local_status === 'erro_envio_erp' || erpLogs.length > 0 || erpLogsLoading) && (
                  <div>
                    <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3 flex items-center gap-2">
                      <History size={12} /> Histórico de Envios ERP
                    </p>
                    {erpLogsLoading ? (
                      <div className="flex items-center gap-2 text-xs text-slate-400 py-3">
                        <RefreshCcw size={14} className="animate-spin" /> Carregando logs...
                      </div>
                    ) : erpLogs.length === 0 ? (
                      <p className="text-xs text-slate-300 italic py-2">Nenhum log encontrado.</p>
                    ) : (
                      <div className="space-y-2">
                        {erpLogs.map((log) => (
                          <div key={log.id} className={cn(
                            "rounded-xl border px-4 py-3 text-xs",
                            log.status === 'success'
                              ? "bg-violet-50 border-violet-100"
                              : "bg-red-50 border-red-100"
                          )}>
                            <div className="flex items-center justify-between gap-2 mb-1">
                              <span className={cn(
                                "font-black uppercase tracking-widest text-[9px] flex items-center gap-1",
                                log.status === 'success' ? "text-violet-700" : "text-red-600"
                              )}>
                                {log.status === 'success'
                                  ? <><CheckCheck size={11}/> Sucesso</>
                                  : <><XCircle size={11}/> Erro</>
                                }
                              </span>
                              <span className="text-[9px] text-slate-400 font-bold">
                                {log.triggered_by === 'auto' ? '⏱ automático' : '👤 manual'}
                              </span>
                              <span className="text-[9px] text-slate-400 tabular-nums">
                                {new Date(log.sent_at).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })}
                              </span>
                            </div>
                            {log.error_message && (
                              <p className="text-[10px] text-red-700 font-semibold mt-1 break-all">{log.error_message}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* CONFIRMAÇÃO DE EXCLUSÃO */}
      {confirmDelete && (
        <div className="fixed inset-0 z-[200] bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-6">
          <div className="bg-white w-full max-w-sm rounded-3xl p-8 text-center shadow-2xl animate-in zoom-in-95 duration-200">
            <div className="w-16 h-16 bg-red-100 text-red-600 rounded-2xl flex items-center justify-center mx-auto mb-6">
              <Trash2 size={32} />
            </div>
            <h3 className="text-xl font-black text-slate-900 tracking-tight mb-2">Excluir documentos?</h3>
            <p className="text-slate-400 text-xs font-semibold mb-8 px-2">
              {(confirmDelete === 'separadas' ? selectedSeparadasIds : selectedEmSepIds).length} documento(s) serão removidos do rastreamento local. O Tiny não será afetado.
            </p>
            <div className="flex gap-3">
              <button onClick={() => setConfirmDelete(false)} className="flex-1 h-14 rounded-2xl font-black text-[10px] uppercase tracking-widest text-slate-400 hover:bg-slate-50 transition-colors">Cancelar</button>
              <button onClick={handleDeleteSelected} className="flex-1 h-14 rounded-2xl font-black text-[10px] uppercase tracking-widest bg-red-600 text-white shadow-lg shadow-red-200 hover:bg-red-700 active:scale-95 transition-all">Sim, excluir</button>
            </div>
          </div>
        </div>
      )}

      {/* FLOATING ACTION BOTTOM (Optional but cool for premium) */}
      <div className="fixed bottom-6 right-6 flex flex-col gap-2">
         <button
           onClick={async () => { await fetchSeparacoes(); await Promise.all([fetchLocalStatuses(), fetchTrackedSeparacoes()]) }}
           className="w-12 h-12 bg-white border border-slate-200 rounded-full shadow-lg flex items-center justify-center text-slate-400 hover:text-blue-600 hover:border-blue-200 transition-all active:scale-90"
         >
           <RefreshCcw size={20} className={cn(loading && "animate-spin")} />
         </button>
      </div>
      
    </div>
  )
}
