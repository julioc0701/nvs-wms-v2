import React, { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useFeedback } from '../components/ui/FeedbackProvider'
import {
  ArrowLeft, ArrowRight, Package, CheckCircle2,
  RefreshCcw, Search, ScanBarcode, X, Copy,
  AlertCircle, Clock, MapPin, Image as ImageIcon
} from 'lucide-react'
import { cn } from '../lib/utils'

const sndSuccess = { play: () => Promise.resolve() }
const sndError = { play: () => Promise.resolve() }

export default function PickingListDetail() {
  const { listId } = useParams()
  const navigate = useNavigate()
  const { notify } = useFeedback()
  const inputRef = useRef(null)
  const internalInputRef = useRef(null)
  
  const [list, setList] = useState(null)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [pickedIds, setPickedIds] = useState(new Set())
  const [shortageIds, setShortageIds] = useState(new Set())
  const [activeTab, setActiveTab] = useState('produtos')
  const [sepDiag, setSepDiag] = useState([]) // diagnóstico por separação
  
  // Estado para Bipagem e UX
  const [searchQuery, setSearchQuery] = useState('')
  const itemsRef = useRef([])
  const pickedIdsRef = useRef(new Set())
  const [barcode, setBarcode] = useState('')
  const [internalBarcode, setInternalBarcode] = useState('')
  const [scanStatus, setScanStatus] = useState({ type: null, msg: null })
  const [linkingItem, setLinkingItem] = useState(null)
  const [selectedItem, setSelectedItem] = useState(null)
  const [itemImage, setItemImage] = useState(null)
  const [imageLoading, setImageLoading] = useState(false)
  const [confirmUndo, setConfirmUndo] = useState(null)
  const [shortageDialog, setShortageDialog] = useState(null) // Para o fluxo de falta/parcial
  const [qtyDialog, setQtyDialog] = useState(null) // Modal de quantidade ao digitar SKU direto
  const [statusMenuOpen, setStatusMenuOpen] = useState(null)
  const [isMobilePhone] = useState(() => window.innerWidth < 768)

  // Suporte ao ESC para fechar modais
  useEffect(() => {
    const handleEsc = (event) => {
       if (event.keyCode === 27) {
        setSelectedItem(null)
        setConfirmUndo(null)
        setLinkingItem(null)
        setStatusMenuOpen(null)
       }
    }
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [])

  // Lazy load de imagem — dispara quando operador abre item
  useEffect(() => {
    if (!selectedItem) { setItemImage(null); return }
    let cancelled = false
    setItemImage(null)
    setImageLoading(true)
    api.getProductImage(selectedItem.sku)
      .then(res => { if (!cancelled) setItemImage(res.image_url || null) })
      .catch(() => { if (!cancelled) setItemImage(null) })
      .finally(() => { if (!cancelled) setImageLoading(false) })
    return () => { cancelled = true }
  }, [selectedItem?.sku])

  async function loadData() {
    setLoading(true)
    try {
      const data = await api.getPickingListDetails(listId)
      setList(data)
      const sorted = [...(data.items || [])].sort((a, b) => {
        const pickedA = pickedIds.has(a.id) ? 1 : 0
        const pickedB = pickedIds.has(b.id) ? 1 : 0
        return pickedA - pickedB 
      })
      itemsRef.current = sorted
      setItems(sorted)
      
      const alreadyPicked = new Set((data.items || []).filter(i => (i.qty_picked || 0) >= i.quantity && i.quantity > 0).map(i => i.id))
      pickedIdsRef.current = alreadyPicked
      setPickedIds(alreadyPicked)

      const alreadyShortage = new Set((data.items || []).filter(i => i.is_shortage).map(i => i.id))
      setShortageIds(alreadyShortage)

      // Mobile: auto-seleciona primeiro item pendente (maior qty primeiro)
      if (isMobilePhone) {
        const firstPending = sorted
          .filter(i => !alreadyPicked.has(i.id) && !alreadyShortage.has(i.id))
          .sort((a, b) => b.quantity - a.quantity)[0] || null
        if (firstPending) setTimeout(() => setSelectedItem(firstPending), 600)
      }

      // Pre-aquece cache de imagens em background — sem bloquear UX
      const skus = [...new Set((data.items || []).map(i => i.sku))]
      if (skus.length) api.warmProductImages(skus).catch(() => {})

      // Monta diagnóstico por separação a partir dos itens da lista
      const sepMap = {}
      ;(data.items || []).forEach(it => {
        if (!it.source_separation_ids) return
        it.source_separation_ids.split(',').forEach(sid => {
          sid = sid.trim()
          if (!sid) return
          if (!sepMap[sid]) sepMap[sid] = []
          sepMap[sid].push(it)
        })
      })
      const diag = Object.entries(sepMap).map(([sid, its]) => {
        const total = its.length
        const done = its.filter(i => (i.qty_picked || 0) >= i.quantity - 0.001 || i.is_shortage).length
        const pending = its.filter(i => !((i.qty_picked || 0) >= i.quantity - 0.001 || i.is_shortage))
        return { sep_id: sid, total, done, pending }
      }).sort((a, b) => (a.done === a.total ? 1 : 0) - (b.done === b.total ? 1 : 0) || a.done - b.done)
      setSepDiag(diag)
    } catch (err) {
      notify('Erro ao carregar lista.', 'error')
    } finally {
      setLoading(false)
      setTimeout(() => inputRef.current?.focus(), 500)
    }
  }

  useEffect(() => {
    loadData()
  }, [listId])

  useEffect(() => {
    if (selectedItem) {
      setInternalBarcode('')
      setTimeout(() => internalInputRef.current?.focus(), 300)
    }
  }, [selectedItem])

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text)
    notify('SKU copiado para a área de transferência!', 'success')
  }

  const updateItemInState = (updatedItem) => {
    setItems(prev => {
      const next = prev.map(i => i.id === updatedItem.id ? { ...i, ...updatedItem } : i)
      itemsRef.current = next
      return next
    })
    setSelectedItem(prev => {
      if (prev && prev.id === updatedItem.id) {
        return { ...prev, ...updatedItem }
      }
      return prev
    })
    
    // Atualiza pickedIds: se coletou tudo, marca como concluído
    const isComplete = updatedItem.qty_picked >= updatedItem.quantity
    setPickedIds(prev => {
      const next = new Set(prev)
      if (isComplete) next.add(updatedItem.id)
      else next.delete(updatedItem.id)
      pickedIdsRef.current = next
      return next
    })

    // Atualiza shortageIds: sincroniza flag visual de falta
    if (updatedItem.is_shortage !== undefined) {
      setShortageIds(prev => {
        const next = new Set(prev)
        if (updatedItem.is_shortage) next.add(updatedItem.id)
        else next.delete(updatedItem.id)
        return next
      })
    }
  }

  const togglePick = async (id, forceState = null, qty = null, mode = 'unit') => {
    try {
      // Se estamos fazendo UNPICK (zerando tudo)
      if (qty === 0 && forceState === false) {
        const res = await api.unpickItem(id)
        updateItemInState(res.item)
        setConfirmUndo(null)
        return
      }

      // De resto, deixamos o backend gerenciar (WMS style)
      // Se qty é passado, usamos 'set'. 
      // Se forceState é true (Sem qty), usamos 'box' para completar tudo.
      let finalMode = mode
      if (qty !== null) finalMode = 'set'
      else if (forceState === true) finalMode = 'box'
      
      const res = await api.pickItem(id, { mode: finalMode, qty })
      
      if (res.status === 'success') {
        updateItemInState(res.item)
        if (res.item.qty_picked >= res.item.quantity) {
          if (isMobilePhone) {
            autoAdvance(id)
          } else {
            setSelectedItem(null)
          }
          setScanStatus({ type: 'success', msg: 'Item concluído!' })
        }
      }
    } catch (err) {
      notify('Erro ao atualizar item.', 'error')
    }
  }



  // Mobile: avança para o próximo item pendente após conclusão/falta
  const autoAdvance = (completedId) => {
    setTimeout(() => {
      const allItems = itemsRef.current
      const currentPickedIds = pickedIdsRef.current
      const pending = allItems
        .filter(i => i.id !== completedId && !currentPickedIds.has(i.id) && !i.is_shortage)
        .sort((a, b) => b.quantity - a.quantity)
      setSelectedItem(pending[0] || null)
    }, 800)
  }

  // ── Processa bipe no campo PRINCIPAL (fora do modal) ────────────────────
  const processMainCode = async (code) => {
    setScanStatus({ type: 'processing', msg: 'Validando bip...' })
    try {
      const res = await api.resolveBarcode(code, null)
      const resolvedSku = res.sku.trim().toUpperCase()
      const currentItems = itemsRef.current
      const currentPickedIds = pickedIdsRef.current
      const alreadyDone = currentItems.find(i => i.sku.trim().toUpperCase() === resolvedSku && currentPickedIds.has(i.id))
      const pending = currentItems.find(i => i.sku.trim().toUpperCase() === resolvedSku && !currentPickedIds.has(i.id))
      if (pending) {
        setSelectedItem(pending)
        setScanStatus({ type: null, msg: null })
      } else if (alreadyDone) {
        setScanStatus({ type: 'warning', msg: `JÁ CONCLUÍDO: ${resolvedSku}` })
        sndError.play().catch(() => {})
      } else {
        setScanStatus({ type: 'error', msg: `NÃO ENCONTRADO: ${resolvedSku}` })
        sndError.play().catch(() => {})
      }
    } catch (err) {
      setScanStatus({ type: 'error', msg: 'Erro de comunicação' })
      sndError.play().catch(() => {})
      api.sendLog('error', 'Erro no scan', { code, error: err.message, listId })
    }
    setTimeout(() => setScanStatus({ type: null, msg: null }), 3000)
    inputRef.current?.focus()
  }

  // ── Processa bipe no campo INTERNO do modal (ou clique de copiar) ────────
  const processInternalCode = async (code) => {
    setInternalBarcode('')
    setScanStatus({ type: 'processing', msg: 'Validando bip...' })
    try {
      // SKU digitado diretamente → rejeitado (somente barcode é aceito)
      if (selectedItem && code === selectedItem.sku.trim().toUpperCase()) {
        notify('SKU não é aceito como bipagem. Use o código de barras.', 'error')
        setScanStatus({ type: 'error', msg: 'SKU não aceito. Use o código de barras.' })
        sndError.play().catch(() => {})
        return
      }
      const res = await api.resolveBarcode(code, selectedItem?.sku ?? null)
      const resolvedSku = res.sku.trim().toUpperCase()
      if (selectedItem) {
        const selectedSku = selectedItem.sku.trim().toUpperCase()
        // res.found === false significa que não há barcode vinculado → nunca aceita como pick direto
        if (res.found && resolvedSku === selectedSku) {
          const pickRes = await api.pickItem(selectedItem.id, { mode: 'unit' })
          if (pickRes.status === 'success') {
            const updated = pickRes.item
            updateItemInState(updated)
            if (updated.qty_picked >= updated.quantity) {
              setScanStatus({ type: 'success', msg: `COLETADO (TOTAL): ${selectedSku}` })
              if (isMobilePhone) {
                autoAdvance(selectedItem.id)
              } else {
                setTimeout(() => setSelectedItem(null), 700)
              }
            } else {
              setScanStatus({ type: 'success', msg: `COLETADO (${updated.qty_picked}/${updated.quantity.toFixed(0)}): ${selectedSku}` })
            }
            sndSuccess.play().catch(() => {})
          }
        } else {
          setLinkingItem({ barcode: code, targetSku: selectedItem.sku, targetId: selectedItem.id })
          setScanStatus({ type: null, msg: null })
        }
      } else {
        setScanStatus({ type: 'error', msg: 'Nenhum item selecionado' })
        sndError.play().catch(() => {})
      }
    } catch (err) {
      setScanStatus({ type: 'error', msg: 'Erro de comunicação' })
      sndError.play().catch(() => {})
      api.sendLog('error', 'Erro no scan', { code, error: err.message, listId })
    }
    setTimeout(() => setScanStatus({ type: null, msg: null }), 3000)
    internalInputRef.current?.focus()
  }

  const handleScan = async (e, source = 'main') => {
    const val = source === 'main' ? barcode : internalBarcode
    if (e.key !== 'Enter' || !val.trim()) return
    const code = val.trim().toUpperCase()
    source === 'main' ? setBarcode('') : setInternalBarcode('')
    if (source === 'internal') {
      await processInternalCode(code)
    } else {
      await processMainCode(code)
    }
  }


  const handleLinkNewBarcode = async (sku) => {
    if (!linkingItem) return
    const targetId = linkingItem.targetId
    try {
      await api.linkBarcode(linkingItem.barcode, sku)
      setLinkingItem(null)

      // Após vincular, incrementa o item imediatamente (mesmo comportamento do picking)
      if (targetId) {
        const pickRes = await api.pickItem(targetId, { mode: 'unit' })
        if (pickRes.status === 'success') {
          const updated = pickRes.item
          updateItemInState(updated)
          if (updated.qty_picked >= updated.quantity) {
            setScanStatus({ type: 'success', msg: `VINCULADO E COLETADO (TOTAL): ${sku}` })
            if (isMobilePhone) {
              autoAdvance(targetId)
            } else {
              setTimeout(() => setSelectedItem(null), 700)
            }
          } else {
            setScanStatus({ type: 'success', msg: `VINCULADO E COLETADO (${updated.qty_picked}/${updated.quantity.toFixed(0)}): ${sku}` })
          }
          sndSuccess.play().catch(() => {})
        }
      } else {
        notify(`Código vinculado ao SKU ${sku}`, 'success')
        setScanStatus({ type: 'success', msg: `VINCULADO: ${sku}` })
      }
      setTimeout(() => internalInputRef.current?.focus(), 100)
    } catch (err) {
      notify('Erro ao vincular: ' + (err?.message || 'erro'), 'error')
    }
  }

  const handleItemClick = (item) => {
    if (pickedIds.has(item.id)) {
      setConfirmUndo(item)
    } else {
      setSelectedItem(item)
    }
  }

  const handlePickAll = async () => {
    if (!window.confirm('Deseja marcar TODOS os itens desta lista como coletados?')) return
    
    setLoading(true)
    try {
      const remainingItems = items.filter(i => !pickedIds.has(i.id))
      for (const item of remainingItems) {
        await api.pickItem(item.id)
      }
      notify('Todos os itens foram coletados!', 'success')
      loadData()
    } catch (err) {
      notify('Erro ao coletar todos os itens.', 'error')
    } finally {
      setLoading(false)
    }
  }

  if (!list && loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-white">
        <div className="flex flex-col items-center gap-4">
           <div className="w-12 h-12 border-4 border-slate-100 border-t-blue-600 rounded-full animate-spin"></div>
           <p className="font-medium text-slate-400">Preparando ambiente...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col bg-white overflow-hidden relative" onClick={() => !selectedItem && !confirmUndo && !statusMenuOpen && !linkingItem && !shortageDialog && inputRef.current?.focus()}>
      {/* HEADER PRINCIPAL */}
      <div className="px-4 py-3 sm:px-8 sm:py-6 flex items-center justify-between border-b border-slate-50 bg-white z-10">
        <div className="flex items-center gap-4">
           <button onClick={() => navigate('/separacao/listas')} className="p-2 hover:bg-slate-50 rounded-full transition-colors text-slate-400">
             <ArrowLeft size={20} />
           </button>
           <div>
             <h1 className="text-xl font-bold text-slate-800 tracking-tight">
               <span className="hidden sm:inline">Separação de mercadorias</span>
               <span className="sm:hidden">{list?.name}</span>
             </h1>
             <p className="text-[10px] font-black text-slate-300 uppercase tracking-[0.2em]">{list?.name}</p>
           </div>
        </div>
        <div className="flex items-center gap-6">
           <div className="text-right hidden sm:block">
              <p className="text-[10px] font-black text-slate-300 uppercase tracking-widest">Progresso</p>
              <p className="text-sm font-black text-slate-900 tabular-nums">{pickedIds.size} / {items.length}</p>
           </div>
           
           {pickedIds.size < items.length && items.length > 0 && (
             <button 
               onClick={handlePickAll}
               className="px-4 py-2 bg-emerald-50 text-emerald-600 rounded-xl text-[10px] font-black uppercase tracking-widest hover:bg-emerald-500 hover:text-white transition-all flex items-center gap-2 border border-emerald-100"
             >
                <CheckCircle2 size={14} />
                Coletar Tudo
             </button>
           )}

           <button onClick={loadData} className="p-2 text-slate-400 hover:text-blue-600 transition-colors">
              <RefreshCcw size={18} className={cn(loading && "animate-spin")} />
           </button>
        </div>
      </div>

      {/* TABS ESTILO TINY */}
      <div className="px-4 sm:px-8 border-b border-slate-100 flex gap-6 sm:gap-8 pt-4 bg-white z-10 shadow-sm">
         <button onClick={() => setActiveTab('produtos')} className={cn("pb-3 text-sm font-semibold transition-all relative", activeTab === 'produtos' ? "text-slate-900" : "text-slate-400 hover:text-slate-600")}>
           produtos {activeTab === 'produtos' && <div className="absolute bottom-0 left-0 w-full h-0.5 bg-slate-800" />}
         </button>
         <button onClick={() => setActiveTab('notas')} className={cn("pb-3 text-sm font-semibold transition-all relative", activeTab === 'notas' ? "text-slate-900" : "text-slate-400 hover:text-slate-600")}>
           separações
           {sepDiag.length > 0 && (
             <span className={cn("ml-1.5 text-[9px] font-black px-1.5 py-0.5 rounded-full",
               sepDiag.every(s => s.done === s.total) ? "bg-emerald-100 text-emerald-600" : "bg-orange-100 text-orange-600"
             )}>
               {sepDiag.filter(s => s.done === s.total).length}/{sepDiag.length}
             </span>
           )}
           {activeTab === 'notas' && <div className="absolute bottom-0 left-0 w-full h-0.5 bg-slate-800" />}
         </button>
      </div>

      <div className="flex-1 overflow-auto bg-slate-50/50">
        {activeTab === 'produtos' ? (
          <div className="px-3 sm:px-8 pb-32 pt-4 sm:pt-6">

            {/* SCANNER AREA (INLINE) */}
            <div className="mb-6 flex flex-col items-center gap-2">
               <div className="relative w-full max-w-4xl">
                  <input 
                    ref={inputRef}
                    type="text" 
                    placeholder="BIPE AQUI OU DIGITE SKU MANUAL..."
                    className={cn(
                      "w-full h-16 bg-white border-2 text-center text-xl font-mono font-black tracking-widest rounded-[1.25rem] shadow-sm outline-none transition-all placeholder:text-slate-300",
                      scanStatus.type === 'success' ? "border-emerald-500 text-emerald-600 ring-4 ring-emerald-500/10" :
                      scanStatus.type === 'error' ? "border-red-500 text-red-600 ring-4 ring-red-500/10" :
                      scanStatus.type === 'warning' ? "border-amber-500 text-amber-600 ring-4 ring-amber-500/10" :
                      "border-slate-100 text-slate-900 focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10"
                    )}
                    value={barcode}
                    onChange={e => setBarcode(e.target.value)}
                    onKeyDown={(e) => handleScan(e, 'main')}
                  />
                  <div className="absolute left-6 top-1/2 -translate-y-1/2 text-slate-200">
                     <ScanBarcode size={28} />
                  </div>
               </div>
               {scanStatus.msg && (
                 <div className={cn(
                   "text-[10px] font-black uppercase tracking-[0.2em] animate-in fade-in slide-in-from-top-2",
                   scanStatus.type === 'success' ? "text-emerald-500" :
                   scanStatus.type === 'error' ? "text-red-500" :
                   scanStatus.type === 'warning' ? "text-amber-500" :
                   "text-blue-500"
                 )}>
                   {scanStatus.msg}
                 </div>
               )}
            </div>

            {/* ── MOBILE CARD LIST ─────────────────────────────────────────── */}
            <div className="md:hidden space-y-2">
              {items.map((item) => {
                const isPicked = pickedIds.has(item.id)
                const isShortage = shortageIds.has(item.id)
                const pickedQty = item.qty_picked || 0
                const isPartialShortage = isShortage && pickedQty > 0
                return (
                  <div
                    key={item.id}
                    onClick={() => handleItemClick(item)}
                    className={cn(
                      "flex items-center gap-3 p-4 rounded-2xl border active:scale-[0.98] transition-all cursor-pointer",
                      isPicked ? "bg-emerald-50/60 border-emerald-100 opacity-75" :
                      isPartialShortage ? "bg-amber-50 border-amber-100" :
                      isShortage ? "bg-red-50 border-red-100" :
                      pickedQty > 0 ? "bg-blue-50/30 border-blue-100" :
                      "bg-white border-slate-100 shadow-sm"
                    )}
                  >
                    {/* Status circle */}
                    <div className={cn(
                      "w-11 h-11 rounded-2xl flex items-center justify-center shrink-0",
                      isPicked ? "bg-emerald-500 shadow-md shadow-emerald-200" :
                      isPartialShortage ? "bg-amber-400 shadow-md shadow-amber-200" :
                      isShortage ? "bg-red-500 shadow-md shadow-red-200" :
                      "bg-blue-50 border-2 border-blue-300"
                    )}>
                      {isPicked && <CheckCircle2 className="text-white" size={18} strokeWidth={3} />}
                      {!isPicked && isPartialShortage && <AlertCircle className="text-white" size={18} strokeWidth={3} />}
                      {!isPicked && !isPartialShortage && isShortage && <X className="text-white" size={18} strokeWidth={4} />}
                      {!isPicked && !isShortage && <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />}
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <p className={cn(
                        "text-sm font-bold leading-tight line-clamp-2 mb-1",
                        isPicked ? "text-slate-400 line-through" :
                        isShortage ? "text-red-600" :
                        "text-slate-800"
                      )}>
                        {item.description}
                      </p>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={cn(
                          "text-[10px] font-black font-mono px-2 py-0.5 rounded-lg",
                          isPicked ? "bg-slate-100 text-slate-400" :
                          isShortage ? "bg-red-50 text-red-500" :
                          "bg-blue-50 text-blue-600"
                        )}>
                          {item.sku}
                        </span>
                        {item.location && (
                          <span className="text-[9px] font-bold text-slate-400 flex items-center gap-0.5">
                            <MapPin size={9} /> {item.location}
                          </span>
                        )}
                        {item.notes && (
                          <span className="text-[9px] font-bold text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-100 uppercase">Obs</span>
                        )}
                      </div>
                    </div>

                    {/* Qty */}
                    <div className="text-right shrink-0">
                      <p className={cn(
                        "text-lg font-black tabular-nums leading-none",
                        isPicked ? "text-emerald-500" :
                        isShortage ? "text-red-500" :
                        "text-slate-800"
                      )}>
                        {pickedQty.toFixed(0)}<span className="text-slate-300 text-xs font-bold">/{item.quantity.toFixed(0)}</span>
                      </p>
                      {isShortage && item.qty_shortage > 0 && (
                        <p className="text-[9px] text-red-400 font-bold mt-0.5">-{item.qty_shortage.toFixed(0)} falta</p>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>

            {/* ── DESKTOP TABLE ─────────────────────────────────────────────── */}
            <div className="hidden md:block bg-white rounded-[2rem] border border-slate-100 shadow-sm overflow-hidden">
              <table className="w-full text-left border-collapse">
                 <thead>
                   <tr className="border-b border-slate-50 bg-slate-50/30">
                     <th className="w-16 py-4"></th>
                     <th className="py-4 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] pl-16">Produto</th>
                     <th className="py-4 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Código</th>
                     <th className="py-4 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] text-right">Qtd</th>
                     <th className="py-4 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] px-4">Un</th>
                     <th className="py-4 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Localização</th>
                     <th className="py-4 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] px-8">Situação</th>
                   </tr>
                 </thead>
                 <tbody className="divide-y divide-slate-50">
                   {items.map((item) => {
                     const isPicked = pickedIds.has(item.id)
                     const isShortage = shortageIds.has(item.id)
                     const pickedQty = item.qty_picked || 0
                     const isPartial = pickedQty > 0 && pickedQty < item.quantity
                     const isPartialShortage = isShortage && pickedQty > 0
                     
                     return (
                       <tr 
                         key={item.id} 
                         className={cn(
                           "group transition-all duration-300",
                           isPicked ? "bg-emerald-50/40 opacity-70" :
                           isPartialShortage ? "bg-amber-50/60" :
                           isShortage ? "bg-red-50/60" :
                           isPartial ? "bg-blue-50/20" :
                           "hover:bg-slate-50/80 cursor-pointer"
                         )}
                         onClick={() => handleItemClick(item)}
                       >
                         <td className="py-5 text-center">
                           <div className={cn(
                               "w-7 h-7 mx-auto border-2 rounded-xl flex items-center justify-center transition-all",
                               isPicked ? "bg-emerald-500 border-emerald-500 scale-110 shadow-lg shadow-emerald-200" :
                               isPartialShortage ? "bg-amber-400 border-amber-400 shadow-lg shadow-amber-200" :
                               isShortage ? "bg-red-500 border-red-500 shadow-lg shadow-red-200" :
                               "border-blue-400 bg-blue-50 group-hover:border-blue-600 group-hover:bg-blue-100"
                             )}>
                             {isPicked && <CheckCircle2 className="text-white" size={16} strokeWidth={3} />}
                             {isPartialShortage && <AlertCircle className="text-white" size={16} strokeWidth={3} />}
                             {!isPicked && !isPartialShortage && isShortage && <X className="text-white" size={16} strokeWidth={4} />}
                             {!isPicked && !isShortage && <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse" />}
                           </div>
                         </td>
                         <td className="py-5 flex items-center gap-4">
                            <span className={cn(
                              "text-xs font-bold transition-all line-clamp-2 max-w-sm", 
                              isPicked ? "text-slate-400 line-through" :
                              isPartialShortage ? "text-amber-700" :
                              isShortage ? "text-red-600" :
                              "text-slate-700 group-hover:text-blue-600"
                            )}>
                              {item.description}
                            </span>
                         </td>
                         <td className="py-5">
                            <div className="flex items-center gap-1">
                               <span className={cn(
                                 "text-[10px] font-black font-mono px-2 py-1 rounded-lg bg-slate-50 truncate max-w-[120px]", 
                                 isShortage ? "text-red-500 bg-red-50" :
                                 !isPicked ? "text-blue-600 bg-blue-50/50" : "text-slate-400"
                               )}>
                                 {item.sku}
                               </span>
                               <button
                                 onClick={(e) => {
                                   e.stopPropagation()
                                   navigator.clipboard.writeText(item.sku)
                                   processMainCode(item.sku.trim().toUpperCase())
                                 }}
                                 className="p-1 text-slate-300 hover:text-blue-600 transition-colors"
                               >
                                 <Copy size={12} />
                               </button>
                               {item.notes && (
                                 <div className="ml-auto text-[8px] font-bold text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-100 uppercase">
                                   Obs
                                 </div>
                               )}
                            </div>
                         </td>
                         <td className="py-5 text-sm font-black text-slate-900 text-right tabular-nums">
                            <div className="flex flex-col items-end">
                               <span className={isShortage ? "text-red-600" : ""}>
                                 {(item.qty_picked || 0).toFixed(0)} / {item.quantity.toFixed(0)}
                               </span>
                               {isShortage && item.qty_shortage > 0 && (
                                 <span className="text-[9px] text-red-400">-{item.qty_shortage.toFixed(0)} Faltam</span>
                               )}
                            </div>
                         </td>
                         <td className="py-5 text-[10px] font-black text-slate-300 px-4 uppercase tracking-widest">UN</td>
                         <td className="py-5">
                            <div className={cn(
                              "flex items-center gap-1.5 font-black text-[10px] uppercase tracking-[0.2em]", 
                              isPicked ? "text-slate-300" : 
                              isShortage ? "text-red-400" :
                              "text-blue-600"
                            )}>
                               <MapPin size={10} className="opacity-50" />
                               {item.location || 'S/ LOCAL'}
                            </div>
                         </td>
                         <td className="py-5 px-8 whitespace-nowrap text-right">
                            {statusMenuOpen?.id === item.id ? (
                              <div className="flex items-center justify-end gap-2 bg-white px-2 py-1 rounded-xl shadow-sm border border-slate-200 inline-flex">
                                <button
                                  onClick={async (e) => {
                                    e.stopPropagation();
                                    await togglePick(item.id, false, 0);
                                    setStatusMenuOpen(null);
                                  }}
                                  className="min-w-[80px] text-[10px] font-black uppercase tracking-wide bg-blue-50 text-blue-600 border border-blue-100 rounded-lg px-3 py-2 hover:bg-blue-600 hover:text-white transition-all"
                                >
                                  Pendente
                                </button>
                                <button
                                  onClick={async (e) => {
                                    e.stopPropagation();
                                    await togglePick(item.id, true);
                                    setStatusMenuOpen(null);
                                  }}
                                  className="min-w-[80px] text-[10px] font-black uppercase tracking-wide bg-emerald-50 text-emerald-600 border border-emerald-100 rounded-lg px-3 py-2 hover:bg-emerald-600 hover:text-white transition-all"
                                >
                                  Concluído
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setShortageDialog({
                                      item,
                                      qtyPicked: item.qty_picked || 0,
                                      qtyShortage: item.quantity - (item.qty_picked || 0),
                                      notes: ''
                                    });
                                    setStatusMenuOpen(null);
                                  }}
                                  className="min-w-[80px] text-[10px] font-black uppercase tracking-wide bg-red-50 text-red-600 border border-red-100 rounded-lg px-3 py-2 hover:bg-red-600 hover:text-white transition-all"
                                >
                                  Sem Estoque
                                </button>
                                <button
                                  onClick={(e) => { e.stopPropagation(); setStatusMenuOpen(null) }}
                                  className="p-1.5 text-slate-400 hover:text-slate-800 transition-colors rounded-lg hover:bg-slate-100"
                                >
                                  <X size={14} strokeWidth={3} />
                                </button>
                              </div>
                            ) : (
                              <button 
                                onClick={(e) => { e.stopPropagation(); setStatusMenuOpen(item) }}
                                className={cn(
                                  "inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[9px] font-black uppercase tracking-widest border transition-all shadow-sm",
                                  isPicked ? "bg-emerald-50 text-emerald-600 border-emerald-100 hover:bg-emerald-100" :
                                  isPartialShortage ? "bg-amber-50 text-amber-600 border-amber-100 hover:bg-amber-100" :
                                  isShortage ? "bg-red-50 text-red-600 border-red-100 hover:bg-red-100" :
                                  "bg-blue-50 text-blue-600 border-blue-100 hover:bg-blue-100"
                                )}
                              >
                                {isPicked ? (
                                  <><CheckCircle2 size={12} strokeWidth={3} /> Concluído</>
                                ) : isPartialShortage ? (
                                  <><AlertCircle size={12} strokeWidth={3} /> Parcial</>
                                ) : isShortage ? (
                                  <><AlertCircle size={12} strokeWidth={3} /> Sem Estoque</>
                                ) : (item.qty_picked || 0) > 0 ? (
                                  <><Clock size={12} strokeWidth={3} /> Parcial</>
                                ) : (
                                  <><Clock size={12} strokeWidth={3} /> Pendente</>
                                )}
                              </button>
                            )}
                         </td>
                       </tr>
                     )
                   })}
                 </tbody>
              </table>
            </div>

            {/* OBSERVAÇÕES INTERNAS */}
            <div className="mt-12 py-8 border-t border-slate-100">
               <h3 className="text-sm font-bold text-slate-900 mb-4 tracking-tight">Observações Internas:</h3>
               <div className="space-y-1 text-xs font-semibold text-slate-600">
                  {list?.items?.[0]?.source_separation_ids?.split(',').map(id => (
                    <p key={id}>Pedido {id}: <span className="text-slate-400">Compõe esta lista consolidada</span></p>
                  ))}
               </div>
            </div>
          </div>
        ) : (
          <div className="px-8 pb-32 pt-6 max-w-3xl">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="font-black text-slate-800">Progresso por Separação</p>
                <p className="text-xs text-slate-400 mt-0.5">{sepDiag.filter(s => s.done === s.total).length} de {sepDiag.length} separações concluídas</p>
              </div>
              <button
                onClick={() => api.post(`/tiny/picking-lists/${listId}/recheck-statuses`, {}).then(() => { loadData(); notify('Status recalculados.', 'success') }).catch(() => notify('Erro ao recalcular.', 'error'))}
                className="h-9 px-4 bg-blue-50 text-blue-600 rounded-xl text-xs font-black hover:bg-blue-100 transition-colors flex items-center gap-2"
              >
                <RefreshCcw size={13} /> Recalcular Status
              </button>
            </div>

            <div className="space-y-2">
              {sepDiag.map(s => {
                const pct = s.total > 0 ? Math.round((s.done / s.total) * 100) : 0
                const done = s.done === s.total
                return (
                  <div key={s.sep_id} className={cn("rounded-2xl border p-4", done ? "bg-emerald-50 border-emerald-100" : "bg-white border-slate-100")}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className={cn("w-2 h-2 rounded-full", done ? "bg-emerald-500" : "bg-orange-400")} />
                        <span className="text-xs font-black text-slate-700">Sep. #{s.sep_id}</span>
                      </div>
                      <span className={cn("text-[10px] font-black uppercase tracking-widest", done ? "text-emerald-600" : "text-orange-500")}>
                        {done ? "✓ concluída" : `${s.done}/${s.total} itens`}
                      </span>
                    </div>
                    <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                      <div className={cn("h-full rounded-full transition-all", done ? "bg-emerald-500" : "bg-orange-400")} style={{ width: `${pct}%` }} />
                    </div>
                    {!done && s.pending.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {s.pending.map((it, i) => (
                          <span key={i} className="text-[9px] font-black bg-orange-100 text-orange-600 px-2 py-0.5 rounded-full">
                            {it.sku} {it.qty_picked || 0}/{it.quantity}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* MODAL / PAINEL DE FOCO (ESTILO COMPACTO PARA COLETOR) */}
      {selectedItem && (
        <div className="fixed inset-0 z-[100] bg-slate-900/40 backdrop-blur-md flex items-center justify-center p-4">
           <div className="bg-white w-full max-w-md rounded-[3rem] shadow-2xl overflow-hidden overflow-y-auto max-h-[90vh] animate-in zoom-in-95 duration-200">
              <div className="p-6 sm:p-8">
                 <div className="mb-6 flex items-center justify-between">
                   <button onClick={() => setSelectedItem(null)} className="flex items-center gap-2 text-slate-400 hover:text-blue-600 transition-all">
                     <ArrowLeft size={16} /> Voltar (ESC)
                   </button>
                   <button onClick={() => autoAdvance(selectedItem.id)} className="flex items-center gap-2 text-slate-400 hover:text-blue-600 transition-all">
                     Próximo <ArrowRight size={16} />
                   </button>
                 </div>
                 <div className="flex justify-between items-start mb-6">
                    <div className="flex-1">
                       <p className="text-[9px] font-black text-blue-600 uppercase tracking-[0.2em] mb-1">✦ SEPARAR AGORA</p>
                       <div className="flex items-center gap-3">
                          <h2 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tighter truncate max-w-[min(280px,60vw)]">{selectedItem.sku}</h2>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              navigator.clipboard.writeText(selectedItem.sku).catch(() => {})
                              processInternalCode(selectedItem.sku.trim().toUpperCase())
                            }}
                            className="p-2 text-slate-300 hover:text-blue-600 hover:bg-blue-50 rounded-xl transition-all"
                            title="Copiar SKU e bipe automático"
                          >
                             <Copy size={18} />
                          </button>
                       </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                       {isMobilePhone && (
                         <span className="text-[11px] font-black bg-blue-50 text-blue-700 px-3 py-1.5 rounded-full border border-blue-100 whitespace-nowrap">
                           {items.filter(i => pickedIds.has(i.id) || shortageIds.has(i.id)).length} / {items.length}
                         </span>
                       )}
                       <button onClick={() => setSelectedItem(null)} className="p-3 bg-slate-50 text-slate-300 hover:text-slate-900 rounded-2xl transition-all">
                         <X size={20} />
                       </button>
                    </div>
                 </div>

                 <p className="text-sm font-bold text-slate-400 leading-tight mb-4 line-clamp-2">
                   {selectedItem.description}
                 </p>

                 {/* IMAGEM DO PRODUTO — lazy load */}
                 {imageLoading && (
                   <div className="mb-4 h-48 bg-slate-100 rounded-2xl animate-pulse flex items-center justify-center">
                     <ImageIcon size={28} className="text-slate-300" />
                   </div>
                 )}
                 {!imageLoading && itemImage && (
                   <div className="mb-4 h-48 rounded-2xl overflow-hidden border border-slate-100 flex items-center justify-center bg-white">
                     <img
                       src={itemImage}
                       alt={selectedItem.sku}
                       className="h-full w-full object-contain"
                       onError={e => { e.currentTarget.parentElement.style.display = 'none' }}
                     />
                   </div>
                 )}

                 {/* STATUS DE SCAN DENTRO DO MODAL */}
                 {scanStatus.msg && (
                   <div className={cn(
                     "mb-4 px-4 py-3 rounded-2xl text-[10px] font-black uppercase tracking-widest text-center animate-in slide-in-from-top-2 duration-300",
                     scanStatus.type === 'success' ? "bg-emerald-50 text-emerald-600 border border-emerald-100" :
                     scanStatus.type === 'error' ? "bg-red-50 text-red-600 border border-red-100" :
                     scanStatus.type === 'warning' ? "bg-amber-50 text-amber-600 border border-amber-100" :
                     "bg-blue-50 text-blue-600 border border-blue-100"
                   )}>
                     {scanStatus.msg}
                   </div>
                 )}

                 {/* SCANNER INPUT INTERNO */}
                 <div className="mb-8 relative">
                    <input
                      ref={internalInputRef}
                      type="text"
                      className="w-full h-14 bg-slate-50 border-2 border-slate-100 rounded-2xl text-center font-mono font-black text-lg focus:border-blue-500 transition-all outline-none"
                      placeholder="BIPE CÓDIGO OU SKU AQUI..."
                      autoComplete="off"
                      spellCheck="false"
                      value={internalBarcode}
                      onChange={e => setInternalBarcode(e.target.value)}
                      onKeyDown={(e) => handleScan(e, 'internal')}
                    />
                    <div className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-200">
                       <ScanBarcode size={20} />
                    </div>
                 </div>

                 <div className="bg-slate-50 rounded-[2rem] p-6 border border-slate-100 mb-6">
                     <div className="flex items-baseline gap-2 justify-center mb-4">
                        <span className="text-5xl font-black text-emerald-500 tabular-nums">{(selectedItem.qty_picked || 0).toFixed(0)}</span>
                        <span className="text-xl font-black text-slate-300">/ {selectedItem.quantity.toFixed(0)} un</span>
                     </div>
                     <div className="h-3 bg-slate-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-emerald-500 transition-all duration-500"
                          style={{ width: `${((selectedItem.qty_picked || 0) / selectedItem.quantity) * 100}%` }}
                        />
                     </div>
                  </div>

                  {selectedItem.notes && (
                    <div className="mb-6 px-6 py-4 bg-amber-50 border border-amber-100 rounded-2xl">
                       <p className="text-[10px] font-black text-amber-600 uppercase tracking-widest mb-1">Observação do Operador</p>
                       <p className="text-xs font-semibold text-amber-800 italic leading-relaxed">"{selectedItem.notes}"</p>
                    </div>
                  )}

                 <button
                   onClick={() => {
                     setShortageDialog({
                       item: selectedItem,
                       qtyPicked: selectedItem.qty_picked || 0,
                       qtyShortage: selectedItem.quantity - (selectedItem.qty_picked || 0),
                       notes: ''
                     })
                     setSelectedItem(null)
                   }}
                   className="w-full h-16 bg-red-600 text-white rounded-3xl flex items-center justify-center gap-3 shadow-lg shadow-red-100 hover:bg-red-700 active:scale-95 transition-all pb-2"
                 >
                   <X size={22} strokeWidth={3} />
                   <span className="text-[10px] font-black uppercase tracking-widest leading-none">Sem Estoque (Relatório)</span>
                 </button>
              </div>
              <div className="h-1.5 bg-gradient-to-r from-red-400 via-red-500 to-red-400" />
           </div>
        </div>
      )}

      {/* CONFIRMAÇÃO DE DESFAZER */}
      {confirmUndo && (
        <div className="fixed inset-0 z-[120] bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-6">
           <div className="bg-white w-full max-sm:max-w-xs max-w-sm rounded-[3rem] p-8 text-center shadow-2xl animate-in zoom-in-95 duration-200">
              <div className="w-16 h-16 bg-amber-100 text-amber-600 rounded-[1.5rem] flex items-center justify-center mx-auto mb-6">
                 <RefreshCcw size={32} />
              </div>
              <h3 className="text-xl font-black text-slate-900 tracking-tight mb-2">Deseja desfazer?</h3>
              <p className="text-slate-400 text-xs font-semibold mb-8 px-2">
                Remover a coleta de {confirmUndo.sku}?
              </p>
              <div className="flex gap-3">
                 <button onClick={() => setConfirmUndo(null)} className="flex-1 h-14 rounded-2xl font-black text-[10px] uppercase tracking-widest text-slate-400 hover:bg-slate-50 transition-colors">Não</button>
                 <button onClick={() => togglePick(confirmUndo.id, false, 0)} className="flex-1 h-14 rounded-2xl font-black text-[10px] uppercase tracking-widest bg-amber-500 text-white shadow-lg shadow-amber-200 hover:bg-amber-600 active:scale-95 transition-all">Sim, desfazer</button>
              </div>
           </div>
        </div>
      )}

      {/* MODAL DE VÍNCULO */}
      {linkingItem && (
        <div
          className="fixed inset-0 z-[130] bg-slate-900/80 backdrop-blur-sm flex items-center justify-center p-4"
          onKeyDown={(e) => { if (e.key === 'Enter' && linkingItem?.targetSku) handleLinkNewBarcode(linkingItem.targetSku) }}
        >
           <div className="bg-white w-full max-w-md rounded-[3rem] shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200 text-center" tabIndex={-1} autoFocus>
              <div className="bg-blue-600 p-8 text-white">
                 <ScanBarcode size={40} strokeWidth={3} className="mx-auto mb-3 opacity-50" />
                 <h2 className="text-xl font-black tracking-tight uppercase">Vincular Código</h2>
                 <p className="text-blue-100 text-[10px] mt-2 font-semibold">
                    Desconhecido: <strong className="bg-white/20 px-2 py-0.5 rounded ml-1">{linkingItem.barcode}</strong>
                 </p>
              </div>

              {linkingItem.targetSku ? (
                /* Confirmação direta — item selecionado no momento da bipagem */
                <div className="p-8">
                  <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">Vincular ao SKU ativo?</p>
                  <p className="text-2xl font-black text-blue-600 tracking-tight mb-1">{linkingItem.targetSku}</p>
                  <p className="text-xs text-slate-400 mb-8">
                    {items.find(i => i.id === linkingItem.targetId)?.description}
                  </p>
                  <div className="flex gap-3">
                    <button
                      onClick={() => setLinkingItem(null)}
                      className="flex-1 h-14 rounded-2xl font-black text-[10px] uppercase tracking-widest text-slate-400 hover:bg-slate-50 transition-colors"
                    >
                      Cancelar
                    </button>
                    <button
                      onClick={() => handleLinkNewBarcode(linkingItem.targetSku)}
                      className="flex-1 h-14 bg-blue-600 text-white rounded-2xl font-black text-[10px] uppercase tracking-widest shadow-lg shadow-blue-100 hover:bg-blue-700 active:scale-95 transition-all"
                    >
                      Sim, vincular
                    </button>
                  </div>
                </div>
              ) : (
                /* Lista completa — nenhum item selecionado */
                <>
                  <div className="p-4 max-h-[50vh] overflow-auto space-y-2 bg-slate-50">
                    {items.filter(i => !pickedIds.has(i.id)).map(item => (
                      <button key={item.id} onClick={() => handleLinkNewBarcode(item.sku)} className="w-full flex items-center gap-4 p-4 rounded-2xl bg-white border border-slate-100 hover:border-blue-400 transition-all text-left">
                        <div className="w-10 h-10 bg-slate-50 rounded-xl flex items-center justify-center shrink-0">
                          <Package size={20} />
                        </div>
                        <div className="flex-1">
                          <p className="text-[9px] font-black text-blue-600 uppercase tracking-widest mb-0.5">{item.sku}</p>
                          <p className="text-[10px] font-bold text-slate-800 line-clamp-1">{item.description}</p>
                        </div>
                      </button>
                    ))}
                  </div>
                  <div className="p-6 bg-white flex justify-center">
                    <button onClick={() => setLinkingItem(null)} className="text-[10px] font-black uppercase text-slate-400 tracking-widest">Cancelar</button>
                  </div>
                </>
              )}
           </div>
        </div>
      )}


      {/* BOTÃO FINALIZAR */}
      {pickedIds.size === items.length && items.length > 0 && (
        <div className="absolute bottom-6 right-6 animate-in slide-in-from-bottom-10 duration-500 z-[90]">
           <button className="bg-emerald-600 text-white px-8 py-5 rounded-2xl font-black shadow-2xl shadow-emerald-200 hover:scale-105 active:scale-95 transition-all flex items-center gap-3 group text-sm">
              FINALIZAR SEPARAÇÃO
              <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center group-hover:bg-white/40 transition-colors">
                <CheckCircle2 size={18} strokeWidth={4} />
              </div>
           </button>
        </div>
)}
      
      {/* DIALOG DE FALTA / PARCIAL */}
      {shortageDialog && (
        <div className="fixed inset-0 z-[150] bg-slate-900/40 backdrop-blur-md flex items-center justify-center p-4">
           <div className="bg-white w-full max-w-md rounded-[3rem] shadow-2xl overflow-hidden overflow-y-auto max-h-[90vh] animate-in zoom-in-95 duration-200">
              <div className="p-6 sm:p-8">
                 <div className="flex justify-between items-start mb-6">
                    <div className="flex-1">
                       <p className="text-[9px] font-black text-red-600 uppercase tracking-[0.2em] mb-1">✦ REGISTRAR FALTA</p>
                       <h2 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tighter truncate max-w-[min(280px,60vw)]">{shortageDialog.item.sku}</h2>
                    </div>
                    <button onClick={() => setShortageDialog(null)} className="p-3 bg-slate-50 text-slate-300 hover:text-slate-900 rounded-2xl transition-all">
                       <X size={20} />
                    </button>
                 </div>

                 <div className="bg-red-50 rounded-[2rem] p-6 border border-red-100 mb-8 text-center">
                    <p className="text-[10px] font-black text-red-400 uppercase tracking-widest mb-1">Saldo Remanescente</p>
                    <div className="flex items-baseline gap-2 justify-center">
                       <span className="text-5xl font-black text-red-600 tabular-nums">-{shortageDialog.qtyShortage.toFixed(0)}</span>
                       <span className="text-xl font-black text-red-300">/ {shortageDialog.item.quantity.toFixed(0)} un</span>
                    </div>
                 </div>

                 <div className="space-y-4 mb-8">
                    <div>
                       <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1 mb-1.5 block">Observações do Operador</label>
                       <textarea 
                         className="w-full bg-slate-50 border-2 border-slate-100 rounded-2xl p-4 text-xs font-semibold focus:border-blue-500 transition-all outline-none min-h-[100px] resize-none"
                         placeholder="Ex: Embalagem danificada, grade furada, etc..."
                         value={shortageDialog.notes || ''}
                         onChange={(e) => setShortageDialog(prev => ({ ...prev, notes: e.target.value }))}
                       />
                    </div>
                 </div>

                 <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <button
                      onClick={() => setShortageDialog(null)}
                      className="h-14 rounded-2xl font-black text-[10px] uppercase tracking-widest text-slate-400 hover:bg-slate-50 transition-colors"
                    >
                      Cancelar
                    </button>
                    <button 
                      onClick={async () => {
                         const itemId = shortageDialog.item.id
                         try {
                            const operator = JSON.parse(localStorage.getItem('operator') || 'null')
                            await api.reportShortage({
                               sku: shortageDialog.item.sku,
                               qty: shortageDialog.qtyShortage,
                               category: 'organico',
                               list_id: listId,
                               item_id: shortageDialog.item.id,
                               description: shortageDialog.item.description,
                               operator_id: operator?.id,
                               notes: shortageDialog.notes
                            })
                            // Atualiza estados locais usando padrão funcional para evitar stale state
                            setShortageIds(prev => new Set([...prev, shortageDialog.item.id]))
                            
                            setItems(prev => {
                               const next = prev.map(it => it.id === shortageDialog.item.id ? { 
                                  ...it, 
                                  is_shortage: true, 
                                  qty_shortage: shortageDialog.qtyShortage, 
                                  notes: shortageDialog.notes 
                               } : it)
                               itemsRef.current = next
                               return next
                            })

                            setPickedIds(prev => {
                               const next = new Set(prev)
                               next.delete(shortageDialog.item.id)
                               pickedIdsRef.current = next
                               return next
                            })

                            notify('Falta registrada com sucesso.', 'success')
                            setShortageDialog(null)
                            setSelectedItem(null)
                            if (isMobilePhone) autoAdvance(itemId)
                         } catch (err) {
                            notify('Erro ao salvar: ' + err.message, 'error')
                         }
                      }}
                      className="h-14 bg-red-600 text-white rounded-2xl font-black text-[10px] uppercase tracking-widest shadow-lg shadow-red-100 hover:bg-red-700 active:scale-95 transition-all"
                    >
                      Confirmar Falta
                    </button>
                 </div>
              </div>
           </div>
        </div>
      )}
      {/* MODAL DE QUANTIDADE (digitou SKU direto no input interno) */}
      {qtyDialog && (
        <div className="fixed inset-0 z-[160] bg-slate-900/40 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-white w-full max-w-md rounded-[3rem] shadow-2xl overflow-hidden overflow-y-auto max-h-[90vh] animate-in zoom-in-95 duration-200">
            <div className="p-6 sm:p-8">
              <div className="flex justify-between items-start mb-6">
                <div className="flex-1">
                  <p className="text-[9px] font-black text-blue-600 uppercase tracking-[0.2em] mb-1">✦ CONFIRMAR QUANTIDADE</p>
                  <h2 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tighter">{qtyDialog.item.sku}</h2>
                </div>
                <button onClick={() => setQtyDialog(null)} className="p-3 bg-slate-50 text-slate-300 hover:text-slate-900 rounded-2xl transition-all">
                  <X size={20} />
                </button>
              </div>

              <p className="text-sm font-bold text-slate-400 leading-tight mb-6 line-clamp-2">
                {qtyDialog.item.description}
              </p>

              <div className="bg-slate-50 rounded-[2rem] p-6 border border-slate-100 mb-6 text-center">
                <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">Necessário</p>
                <p className="text-4xl font-black text-slate-800 tabular-nums">
                  {qtyDialog.item.quantity.toFixed(0)} <span className="text-xl text-slate-300">un</span>
                </p>
              </div>

              <div className="mb-6">
                <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1 mb-1.5 block">
                  Quantidade coletada
                </label>
                <input
                  type="number"
                  min="1"
                  max={qtyDialog.item.quantity}
                  className="w-full h-14 bg-slate-50 border-2 border-slate-100 rounded-2xl text-center text-2xl font-black focus:border-blue-500 transition-all outline-none"
                  placeholder={qtyDialog.item.quantity.toFixed(0)}
                  value={qtyDialog.qty}
                  onChange={e => setQtyDialog(prev => ({ ...prev, qty: e.target.value }))}
                  onKeyDown={async e => {
                    if (e.key === 'Enter') {
                      await togglePick(qtyDialog.item.id, true, qtyDialog.item.quantity)
                      setQtyDialog(null)
                    }
                  }}
                  autoFocus
                />
              </div>

              <button
                onClick={async () => {
                  await togglePick(qtyDialog.item.id, true, qtyDialog.item.quantity)
                  setQtyDialog(null)
                }}
                className="w-full h-16 bg-emerald-500 text-white rounded-3xl flex flex-col items-center justify-center gap-1 shadow-lg shadow-emerald-100 hover:bg-emerald-600 active:scale-95 transition-all"
              >
                <CheckCircle2 size={20} strokeWidth={3} />
                <span className="text-[9px] font-black uppercase tracking-widest">Coletar Tudo</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
