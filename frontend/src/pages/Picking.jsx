import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams, useLocation } from 'react-router-dom'
import { api } from '../api/client'
import MarketplaceLogo from '../components/MarketplaceLogo'
import TransferConfirmDialog from '../components/dialogs/TransferConfirmDialog'
import SearchSelectionDialog from '../components/dialogs/SearchSelectionDialog'
import ShortageDialog from '../components/dialogs/ShortageDialog'
import UnknownBarcodeDialog from '../components/dialogs/UnknownBarcodeDialog'
import WrongSkuDialog from '../components/dialogs/WrongSkuDialog'
import { cn } from '../lib/utils'
import { ArrowLeft, Box, Check, CheckCircle2, RotateCcw, ShieldAlert, Printer, AlertTriangle, XCircle, RefreshCcw, Hand, Info, Zap, AlertCircle, Home } from 'lucide-react'
import { useFeedback } from '../components/ui/FeedbackProvider'
import { useCompactViewport } from '../hooks/useCompactViewport'

const STATUS_COLOR = {
  pending: 'bg-slate-200 text-slate-600',
  in_progress: 'bg-blue-500 text-white',
  complete: 'bg-emerald-500 text-white',
  partial: 'bg-amber-500 text-white',
  out_of_stock: 'bg-red-500 text-white',
}

const STATUS_LABEL = {
  pending: 'Pendente',
  in_progress: 'Separando...',
  complete: '✓ Completo',
  partial: '⚠ Parcial',
  out_of_stock: '✗ Sem estoque',
}


function buildZplBlock(mlCode, description, sku) {
  const safeDesc = (description || '').replace(/\^/g, ' ').replace(/~/g, ' ').substring(0, 120)
  return '^XA^CI28\n^LH0,0\n' +
    `^FO30,15^BY2,,0^BCN,54,N,N^FD${mlCode}^FS\n` +
    `^FO105,75^A0N,20,25^FH^FD${mlCode}^FS\n` +
    `^FO105,76^A0N,20,25^FH^FD${mlCode}^FS\n` +
    `^FO16,115^A0N,18,18^FB300,2,2,L^FH^FD${safeDesc}^FS\n` +
    `^FO16,153^A0N,18,18^FB300,1,0,L^FH^FD^FS\n` +
    `^FO15,153^A0N,18,18^FB300,1,0,L^FH^FD^FS\n` +
    `^FO16,172^A0N,18,18^FH^FDSKU: ${sku}^FS\n` +
    '^CI28\n^LH0,0\n' +
    `^FO350,15^BY2,,0^BCN,54,N,N^FD${mlCode}^FS\n` +
    `^FO425,75^A0N,20,25^FH^FD${mlCode}^FS\n` +
    `^FO425,76^A0N,20,25^FH^FD${mlCode}^FS\n` +
    `^FO346,115^A0N,18,18^FB300,2,2,L^FH^FD${safeDesc}^FS\n` +
    `^FO346,153^A0N,18,18^FB300,1,0,L^FH^FD^FS\n` +
    `^FO345,153^A0N,18,18^FB300,1,0,L^FH^FD^FS\n` +
    `^FO346,172^A0N,18,18^FH^FDSKU: ${sku}^FS\n^XZ`
}

function buildZplBlockSingle(mlCode, description, sku) {
  const safeDesc = (description || '').replace(/\^/g, ' ').replace(/~/g, ' ').substring(0, 120)
  return '^XA^CI28\n^LH0,0\n' +
    `^FO30,15^BY2,,0^BCN,54,N,N^FD${mlCode}^FS\n` +
    `^FO105,75^A0N,20,25^FH^FD${mlCode}^FS\n` +
    `^FO105,76^A0N,20,25^FH^FD${mlCode}^FS\n` +
    `^FO16,115^A0N,18,18^FB300,2,2,L^FH^FD${safeDesc}^FS\n` +
    `^FO16,172^A0N,18,18^FH^FDSKU: ${sku}^FS\n^XZ`
}

function buildShopeeZplBlock(mlCode, description, sku) {
  let nameLine = (description || '').replace(/\^/g, ' ')
  if (nameLine.length > 40) {
    const sub = nameLine.substring(0, 40)
    const lastSpace = sub.lastIndexOf(' ')
    nameLine = lastSpace > 0 ? sub.substring(0, lastSpace) : sub
  }
  return '^XA^CI28\n' +
    '^LH0,0\n' +
    `^FO10,5^A0N,18,18^FD${nameLine}^FS\n` +
    `^FO90,27^BQN,2,3^FDQA,${mlCode}^FS\n` +
    `^FO10,135^A0N,18,18^FDseller sku: ${sku}^FS\n` +
    `^FO10,155^A0N,18,18^FDbarcode: ${mlCode}^FS\n` +
    `^FO10,175^A0N,18,18^FDwhs skuid: ${mlCode}^FS\n` +
    '^CI28\n' +
    '^LH0,0\n' +
    `^FO350,5^A0N,18,18^FD${nameLine}^FS\n` +
    `^FO430,27^BQN,2,3^FDQA,${mlCode}^FS\n` +
    `^FO350,135^A0N,18,18^FDseller sku: ${sku}^FS\n` +
    `^FO350,155^A0N,18,18^FDbarcode: ${mlCode}^FS\n` +
    `^FO350,175^A0N,18,18^FDwhs skuid: ${mlCode}^FS\n` +
    '^XZ'
}

function buildShopeeZplBlockSingle(mlCode, description, sku) {
  let nameLine = (description || '').replace(/\^/g, ' ')
  if (nameLine.length > 40) {
    const sub = nameLine.substring(0, 40)
    const lastSpace = sub.lastIndexOf(' ')
    nameLine = lastSpace > 0 ? sub.substring(0, lastSpace) : sub
  }
  return '^XA^CI28\n' +
    '^LH0,0\n' +
    `^FO10,5^A0N,18,18^FD${nameLine}^FS\n` +
    `^FO90,27^BQN,2,3^FDQA,${mlCode}^FS\n` +
    `^FO10,135^A0N,18,18^FDseller sku: ${sku}^FS\n` +
    `^FO10,155^A0N,18,18^FDbarcode: ${mlCode}^FS\n` +
    `^FO10,175^A0N,18,18^FDwhs skuid: ${mlCode}^FS\n` +
    '^XZ'
}

export default function Picking() {
  const compact = useCompactViewport(800)
  const { notify } = useFeedback()
  const { sessionId } = useParams()
  const [searchParams] = useSearchParams()
  const focusSku = searchParams.get('sku')
  const navigate = useNavigate()
  const location = useLocation()
  const isOverlay = !!location.state?.backgroundLocation
  const operator = JSON.parse(localStorage.getItem('operator') || 'null')

  const goBackToItems = useCallback(() => navigate(`/sessions/${sessionId}/items`), [sessionId, navigate])

  const [session, setSession] = useState(null)
  const [item, setItem] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [transferData, setTransferData] = useState(null) 
  const [recentItems, setRecentItems] = useState([])
  const [barcode, setBarcode] = useState('')
  const [flash, setFlash] = useState(null) 
  const [dialog, setDialog] = useState(null)
  const [printers, setPrinters] = useState([])
  const [selectedPrinter, setSelectedPrinter] = useState(null)
  const [wrongItem, setWrongItem] = useState(null) 

  const [printStatus, setPrintStatus] = useState(null)
  const [printError, setPrintError] = useState(null)

  const [loading, setLoading] = useState(true)
  const [allItems, setAllItems] = useState([])
  const [scanMode, setScanMode] = useState('box')
  const [fixingSpooler, setFixingSpooler] = useState(false)

  const inputRef = useRef(null)

  const focusInput = useCallback(() => {
    if (dialog) return
    setTimeout(() => inputRef.current?.focus(), 80)
  }, [dialog])

  useEffect(() => {
    if (!operator) { navigate('/'); return }
    Promise.all([api.getSession(sessionId), api.getPrinters()]).then(([s, p]) => {
      setSession(s)
      setPrinters(p)
      if (p.length > 0) setSelectedPrinter(p[0].id)
      if (focusSku) {
        api.getItems(sessionId).then(items => {
          const focused = items.find(i => i.sku === focusSku)
          setItem(focused || null)
          if (!focused) api.getItems(sessionId).then(setAllItems)
        })
      } else {
        setItem(s.current_item)
        if (!s.current_item) api.getItems(sessionId).then(setAllItems)
      }
    }).finally(() => { setLoading(false); focusInput() })
  }, [sessionId, focusSku])

  function refreshSession() {
    api.getSession(sessionId).then(s => {
      setSession(s)
      setItem(s.current_item)
      if (!s.current_item) api.getItems(sessionId).then(setAllItems)
    })
  }

  function triggerFlash(type) {
    setFlash(type)
    setTimeout(() => setFlash(null), 600)
  }

  async function handleScan(e, codeOverride = null) {
    if (e && e.key !== 'Enter') return
    const code = (codeOverride || barcode || '').trim()
    if (!code) return
    if (!codeOverride) setBarcode('')
    // SKU digitado diretamente → rejeita com mensagem de erro
    if (item && code.toUpperCase() === item.sku.trim().toUpperCase()) {
      notify('SKU não é aceito como bipagem. Use o código de barras.', 'error')
      triggerFlash('error')
      focusInput()
      return
    }
    try {
      if (scanMode === 'box' && item) {
        const res = await api.scan(sessionId, code, operator.id, focusSku || null)
        if (res.status === 'ok') {
          await api.undo(sessionId, item.sku, operator.id)
          setDialog({ type: 'box_qty', data: { code } })
          return
        }
        await updateFromResponse(res, code)
        return
      }
      const res = await api.scan(sessionId, code, operator.id, focusSku || null)
      await updateFromResponse(res, code)
    } catch (err) {
      triggerFlash('error')
      focusInput()
    }
  }

  async function updateFromResponse(res, code) {
    if (res.progress) setSession(prev => prev ? { ...prev, progress: res.progress } : prev)
    switch (res.status) {
      case 'ok':
        setItem(res.item); triggerFlash('ok')
        break
      case 'complete':
        setItem(res.item)
        setPrintStatus(null); setPrintError(null)
        triggerFlash('complete')
        if (res.item?.labels_ready) await autoPrintLabels(res.item)
        if (focusSku) setTimeout(goBackToItems, 600)
        else {
          setRecentItems(prev => [res.item, ...prev.slice(0, 4)])
          setTimeout(() => {
            api.getSession(sessionId).then(s => {
              setSession(s)
              setItem(s.current_item)
              if (!s.current_item) api.getItems(sessionId).then(setAllItems)
            })
          }, 400)
        }
        break
      case 'excess':
        triggerFlash('error'); break
      case 'unknown_barcode':
        setDialog({ type: 'unknown', data: { barcode: code } }); return
      case 'multiple_matches':
        setDialog({ type: 'multiple_matches', data: { candidates: res.candidates } }); return
      case 'wrong_session':
        if (res.action === 'transfer_available') {
          setBarcode('')
          setTransferData({ item_id: res.item_id, sku: res.sku, ownerName: res.owner_name })
        } else if (res.action === 'in_progress_other') {
          setDialog({ type: 'wrong_sku', data: { ...res, barcode: code } })
        } else {
          setDialog({
            type: 'wrong_session',
            data: { barcode: code, sku: res.sku, description: res.description, all_skus: res.all_skus || [res.sku] }
          })
        }
        return
      case 'ambiguous_barcode':
        setDialog({ type: 'multiple_matches', data: { candidates: res.candidates } }); return
      case 'wrong_sku':
        if (focusSku) setDialog({ type: 'wrong_session', data: { barcode: code, sku: res.scanned_sku, description: res.item?.description } })
        else setDialog({ type: 'wrong_sku', data: { ...res, barcode: code } })
        return
    }
    focusInput()
  }

  async function handleShortageConfirm(qtyFound, notes) {
    setDialog(null)
    const res = await api.shortage(sessionId, item.sku, qtyFound, operator.id, notes)
    
    // REGISTRA NO RELATÓRIO DE FALTAS
    try {
      const missing = item.qty_required - qtyFound
      if (missing > 0) {
        await api.reportShortage({
          sku: item.sku,
          qty: missing,
          category: 'full',
          list_id: sessionId,
          description: item.description,
          operator_id: operator.id
        })
      }
    } catch (e) {
      console.error('Erro ao reportar shortage no consolidado', e)
    }

    setSession(prev => prev ? { ...prev, progress: res.progress } : prev)
    if (res.item?.labels_ready) await autoPrintLabels(res.item)
    if (focusSku) goBackToItems()
    else {
      setRecentItems(prev => [res.item, ...prev.slice(0, 4)])
      const s = await api.getSession(sessionId)
      setSession(s); setItem(s.current_item)
      if (!s.current_item) api.getItems(sessionId).then(setAllItems)
      focusInput()
    }
  }

  async function handleOutOfStock() {
    if (item.status === 'complete') {
      setDialog({ type: 'defect_adjust', data: { defectQty: 0, reprint: false } })
      return
    }
    setDialog({ type: 'oos_confirm', data: { notes: '' } })
  }

  async function handleDefectAdjustConfirm({ defectQty, reprint }) {
    setDialog(null)
    const validQty = Math.max(0, item.qty_picked - defectQty)
    const res = await api.shortage(sessionId, item.sku, validQty, operator.id, `Ajuste por defeito: ${defectQty} um com problema`)
    setSession(prev => prev ? { ...prev, progress: res.progress } : prev)
    if (reprint && res.item?.labels_ready) await autoPrintLabels(res.item, true, validQty)
    if (focusSku) goBackToItems()
    else {
      setRecentItems(prev => [res.item, ...prev.slice(0, 4)])
      const s = await api.getSession(sessionId)
      setSession(s); setItem(s.current_item)
      if (!s.current_item) api.getItems(sessionId).then(setAllItems)
      focusInput()
    }
  }

  async function _doOutOfStock(notes) {
    setDialog(null)
    const res = await api.outOfStock(sessionId, item.sku, operator.id, notes)
    
    // REGISTRA NO RELATÓRIO DE FALTAS (TOTAL)
    try {
      await api.reportShortage({
        sku: item.sku,
        qty: item.qty_required,
        category: 'full',
        list_id: sessionId,
        description: item.description,
        operator_id: operator.id
      })
    } catch (e) {
      console.error('Erro ao reportar oos no consolidado', e)
    }

    setSession(prev => prev ? { ...prev, progress: res.progress } : prev)
    if (res.item?.labels_ready) await autoPrintLabels(res.item)
    if (focusSku) goBackToItems()
    else {
      setRecentItems(prev => [res.item, ...prev.slice(0, 4)])
      const s = await api.getSession(sessionId)
      setSession(s); setItem(s.current_item)
      if (!s.current_item) api.getItems(sessionId).then(setAllItems)
      focusInput()
    }
  }

  async function handleUndo() {
    const res = await api.undo(sessionId, item.sku, operator.id)
    setItem(res.item); setSession(prev => prev ? { ...prev, progress: res.progress } : prev)
    focusInput()
  }

  async function handleReopen(sku) {
    const res = await api.reopen(sessionId, sku, operator.id)
    setRecentItems(prev => prev.map(i => i.sku === sku ? res.item : i))
    refreshSession(); focusInput()
  }

  async function handleAddBarcode(code) {
    setDialog(null)
    if (item) {
      try {
        await api.addBarcode(sessionId, code, item.sku, operator.id)
        if (scanMode === 'box') { setDialog({ type: 'box_qty', data: { code } }); return }
        const res = await api.scan(sessionId, code, operator.id, focusSku || null)
        updateFromResponse(res, code)
      } catch (err) { notify('Erro ao vincular código: ' + err.message, 'error'); triggerFlash('error') }
    }
    focusInput()
  }

  async function handleBoxQtyConfirm(qty) {
    const { code } = dialog.data; setDialog(null)
    try {
      if (qty === 0) {
        const res = await api.outOfStock(sessionId, item.sku, operator.id)
        setSession(prev => prev ? { ...prev, progress: res.progress } : prev)
        if (focusSku) goBackToItems()
        else {
          setRecentItems(prev => [res.item, ...prev.slice(0, 4)])
          const s = await api.getSession(sessionId)
          setSession(s); setItem(s.current_item)
          if (!s.current_item) api.getItems(sessionId).then(setAllItems)
          focusInput()
        }
      } else if (qty < item.qty_required) {
        const res = await api.shortage(sessionId, item.sku, qty, operator.id)
        setSession(prev => prev ? { ...prev, progress: res.progress } : prev)
        if (res.item?.labels_ready) await autoPrintLabels(res.item)
        if (focusSku) goBackToItems()
        else {
          setRecentItems(prev => [res.item, ...prev.slice(0, 4)])
          const s = await api.getSession(sessionId)
          setSession(s); setItem(s.current_item)
          if (!s.current_item) api.getItems(sessionId).then(setAllItems)
          focusInput()
        }
      } else if (qty >= item.qty_required) {
        const res = await api.scanBox(sessionId, code, operator.id, focusSku || null)
        await updateFromResponse(res, code)
      }
    } catch (err) { triggerFlash('error'); focusInput() }
  }

  async function autoPrintLabels(pickedItem, force = false, overrideQty = null) {
    if (!force && pickedItem.labels_printed) { setPrintStatus('done'); return }
    setPrintStatus('printing'); setPrintError(null)
    const mlCode = pickedItem.ml_code || pickedItem.sku
    const desc = pickedItem.description
    const sku = pickedItem.sku
    const qty = overrideQty !== null ? overrideQty : (pickedItem.qty_picked || 1)
    const fullPairs = Math.floor(qty / 2)
    const remainder = qty % 2

    let fullZpl = ''
    if (session?.marketplace === 'shopee') {
      const blocks = [
        ...Array.from({ length: fullPairs }, () => buildShopeeZplBlock(mlCode, desc, sku)),
        ...(remainder === 1 ? [buildShopeeZplBlockSingle(mlCode, desc, sku), '^XA^XZ'] : []),
      ]
      fullZpl = blocks.join('\n')
    } else {
      const blocks = [
        ...Array.from({ length: fullPairs }, () => buildZplBlock(mlCode, desc, sku)),
        ...(remainder === 1 ? [buildZplBlockSingle(mlCode, desc, sku)] : []),
      ]
      fullZpl = blocks.join('\n')
    }

    // Aplica um ajuste fino de -15 dots na esquerda (aprox 1.8mm) para todas as posições (FOx)
    fullZpl = fullZpl.replace(/\^FO(\d+),/g, (match, x) => `^FO${Math.max(0, parseInt(x, 10) - 15)},`)

    try {
      // Agente v3 usa WebSocket puro — createPrintJob funciona tanto em HTTP quanto HTTPS
      await api.createPrintJob(sessionId, pickedItem.sku, fullZpl, operator?.id)
      setPrintStatus('done')
    } catch (err) { console.error('Erro ao processar impressão:', err); setPrintError(err?.message || 'Erro'); setPrintStatus('error') }
  }

  function handlePrint() { if (item) setDialog({ type: 'reprint_qty', data: { qty: item.qty_required } }) }
  function handleForcePrint() { if (item) setDialog({ type: 'reprint_qty', data: { qty: item.qty_required } }) }
  async function handleReprintConfirm(qty) { setDialog(null); if (item && qty > 0) await autoPrintLabels(item, true, qty); focusInput() }

  async function handleFixSpooler() {
    if (!window.confirm('Isso irá reiniciar o serviço de impressão do Windows e limpar a fila. Deseja continuar?')) return
    setFixingSpooler(true)
    try {
      await api.fixSpoolerViaAgent()
      notify('Comando enviado ao agente. Aguarde alguns segundos e tente imprimir novamente.', 'success')
      setPrintStatus(null)
    } catch (err) {
      notify('Não foi possível comunicar com o agente: ' + (err?.message || 'erro'), 'error')
    } finally {
      setFixingSpooler(false)
      focusInput()
    }
  }

  async function handleTransfer() {
    if (!transferData) return
    setSubmitting(true)
    try {
      const res = await api.transferItem(transferData.item_id, operator.id)
      setTransferData(null)
      navigate(`/picking/${res.new_session_id}`)
    } catch (err) { notify(err.message, 'error') } finally { setSubmitting(false) }
  }

  async function onSelectSearchResult(candidate) {
    setDialog(null)
    const isInSession = allItems.some(i => i.sku === candidate.sku)
    if (isInSession) {
      if (focusSku) await handleScan(null, candidate.sku)
      else await handleScan(null, candidate.sku)
    } else { handleScan(null, candidate.sku) }
  }

  if (loading) return (
    <div className="flex flex-col items-center justify-center min-h-screen text-slate-400 gap-4 bg-slate-50">
      <div className="w-8 h-8 rounded-full border-4 border-slate-200 border-t-slate-400 animate-spin"/>
      <span className="font-bold tracking-widest text-sm uppercase">Carregando Sessão...</span>
    </div>
  )

  const progress = session?.progress || {}
  const pct = progress.items_total ? Math.round((progress.items_picked / progress.items_total) * 100) : 0

  return (
    <div className={cn(
      "flex flex-col items-center transition-colors duration-200 py-4 px-4",
      isOverlay
        ? "fixed inset-0 z-50 overflow-y-auto"
        : "min-h-[100dvh] bg-slate-200",
      compact && "compact-density",
      isOverlay && flash === null && "bg-black/50 backdrop-blur-sm",
      isOverlay && flash === 'ok' && "bg-emerald-900/40 backdrop-blur-sm",
      isOverlay && flash === 'error' && "bg-red-900/40 backdrop-blur-sm",
      isOverlay && flash === 'complete' && "bg-blue-900/40 backdrop-blur-sm",
      !isOverlay && flash === 'ok' && "bg-emerald-100",
      !isOverlay && flash === 'error' && "bg-red-100",
      !isOverlay && flash === 'complete' && "bg-blue-100",
      !isOverlay && flash === null && "bg-slate-200",
    )} onClick={() => !dialog && focusInput()}>

      {transferData && <TransferConfirmDialog sku={transferData.sku} ownerName={transferData.ownerName} onConfirm={handleTransfer} onCancel={() => setTransferData(null)} />}
      {dialog?.type === 'multiple_matches' && <SearchSelectionDialog candidates={dialog.data.candidates} onSelect={onSelectSearchResult} onCancel={() => setDialog(null)} />}

      {/* ── CARD MODAL ─────────────────────────────────────── */}
      <div className="w-full max-w-sm bg-white rounded-3xl shadow-2xl overflow-hidden" tabIndex={0} onKeyDown={(e) => {
        if (dialog) return
        if (document.activeElement?.tagName !== 'INPUT' && document.activeElement?.tagName !== 'TEXTAREA') {
          inputRef.current?.focus()
        }
      }}>

        {/* HEADER */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
          <button
            onClick={() => isOverlay ? navigate(-1) : (focusSku ? goBackToItems() : navigate('/sessions'))}
            className="flex items-center gap-1.5 text-sm font-bold text-slate-500 hover:text-slate-800 transition-colors"
          >
            <ArrowLeft size={16}/> Voltar
          </button>
          <div className="flex flex-col items-center">
            <span className="text-xs font-black text-slate-700 flex items-center gap-1.5">
              <MarketplaceLogo marketplace={session?.marketplace} size={14}/> {session?.session_code}
            </span>
            <span className="text-[10px] text-slate-400 font-bold tabular-nums">
              {progress.items_picked}/{progress.items_total} un · {progress.skus_complete}/{progress.skus_total} sku
            </span>
          </div>
          <button
            onClick={() => { localStorage.removeItem('operator'); navigate('/') }}
            className="text-slate-400 hover:text-slate-700 transition-colors p-1"
            title="Trocar operador"
          >
            <Home size={16}/>
          </button>
        </div>

        {/* BARRA DE PROGRESSO GERAL */}
        <div className="h-1 bg-slate-100">
          <div className="h-full bg-blue-500 transition-all duration-300" style={{ width: `${pct}%` }}/>
        </div>

        {item ? (
          <div className="p-5 flex flex-col gap-4">

            {/* SKU + DESCRIÇÃO */}
            <div className="relative pr-20">
              <span className="text-[10px] font-black text-blue-600 uppercase tracking-widest flex items-center gap-1 mb-1">
                <Zap size={10}/> Separar agora
              </span>
              <p className="text-2xl font-black text-slate-800 break-all leading-tight">{item.sku}</p>
              <p className="text-sm text-slate-500 mt-1 line-clamp-2 leading-snug">{item.description}</p>
              <div className={cn("absolute top-0 right-0 px-2.5 py-1 rounded-xl text-[10px] font-black uppercase tracking-wide", STATUS_COLOR[item.status])}>
                {STATUS_LABEL[item.status]}
              </div>
            </div>

            {/* MODO DE LEITURA */}
            <div className="grid grid-cols-2 gap-2">
              <button onMouseDown={e => e.preventDefault()} onClick={() => { setScanMode('unit'); focusInput() }}
                className={cn("py-2 px-3 rounded-xl text-xs font-bold uppercase tracking-widest border-2 transition-all flex items-center justify-center gap-2",
                  scanMode === 'unit' ? "bg-blue-600 text-white border-blue-600 shadow-md" : "bg-white text-slate-400 border-slate-200 opacity-70 hover:opacity-100"
                )}>
                <div className="w-4 h-4 rounded-full bg-black/20 text-white flex items-center justify-center font-black text-[10px]">1</div>
                Bipe Unitário
              </button>
              <button onMouseDown={e => e.preventDefault()} onClick={() => { setScanMode('box'); focusInput() }}
                className={cn("py-2 px-3 rounded-xl text-xs font-bold uppercase tracking-widest border-2 transition-all flex items-center justify-center gap-2",
                  scanMode === 'box' ? "bg-amber-500 text-white border-amber-500 shadow-md" : "bg-white text-slate-400 border-slate-200 opacity-70 hover:opacity-100"
                )}>
                <Box size={16} strokeWidth={2.5}/> Caixa
              </button>
            </div>

            {/* INPUT */}
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                <Zap size={16}/>
              </div>
              <input
                ref={inputRef}
                className="w-full h-12 pl-10 pr-10 border-2 border-slate-200 rounded-2xl outline-none font-mono text-base text-slate-700 font-black placeholder-slate-300 focus:border-blue-400 transition-colors bg-slate-50 tracking-wide"
                placeholder="BIPE O CÓDIGO DE BARRAS AQUI..."
                value={barcode}
                onChange={e => setBarcode(e.target.value)}
                onKeyDown={handleScan}
                autoFocus
                readOnly={false}
              />
              <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none opacity-40">
                {scanMode === 'box' ? <Box size={16} className="text-amber-500"/> : <Check size={16} className="text-blue-500"/>}
              </div>
            </div>

            {/* AVISO MODO CAIXA */}
            {scanMode === 'box' && (
              <p className="bg-amber-50 text-amber-700 border-l-4 border-amber-500 rounded-r-xl p-2 text-xs font-bold flex items-start gap-2 -mt-2 animate-in fade-in">
                <Info size={13} className="shrink-0 mt-0.5"/> 1 bipe = 1 caixa cheia. Sistema informará caixas restantes.
              </p>
            )}

            {/* CONTADOR */}
            <div className="text-center py-3 bg-slate-50 rounded-2xl border border-slate-100">
              <div className="flex items-end justify-center gap-2">
                <span className={cn("text-5xl font-black tabular-nums tracking-tighter leading-none",
                  item.qty_picked >= item.qty_required ? "text-emerald-500" : "text-blue-600"
                )}>{item.qty_picked}</span>
                <span className="text-lg text-slate-400 font-bold mb-1">/ {item.qty_required} un</span>
              </div>
              <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden mx-4 mt-3">
                <div
                  className={cn("h-full rounded-full transition-all duration-300",
                    item.qty_picked >= item.qty_required ? 'bg-emerald-500' : 'bg-blue-500'
                  )}
                  style={{ width: `${Math.min((item.qty_picked / item.qty_required) * 100, 100)}%` }}
                />
              </div>
            </div>

            {/* BOTÕES DE AÇÃO */}
            <div className="flex flex-col gap-2">
              <button
                onClick={handleOutOfStock}
                className="w-full py-4 bg-red-600 text-white rounded-2xl font-black text-sm flex items-center justify-center gap-2 hover:bg-red-700 active:scale-[0.98] transition-all shadow-md"
              >
                <XCircle size={18} strokeWidth={2.5}/> SEM ESTOQUE (RELATÓRIO)
              </button>
              <button
                onClick={handleUndo} disabled={item.qty_picked === 0}
                className="w-full py-3 border-2 border-slate-200 rounded-2xl font-bold text-sm text-slate-500 flex items-center justify-center gap-2 hover:bg-slate-50 disabled:opacity-20 active:scale-[0.98] transition-all group"
              >
                <RotateCcw size={15} className="group-hover:-rotate-90 transition-transform"/> Desfazer Último Bip
              </button>
            </div>

            {/* ZONA DE IMPRESSÃO */}
            {item.labels_ready && (
              <div className="border-t-2 border-slate-100 border-dashed pt-4 flex flex-col gap-2">
                {printStatus === null && (
                  <button onClick={handlePrint} className="py-3 w-full bg-emerald-500 text-white rounded-2xl font-black text-sm hover:bg-emerald-600 active:scale-[0.98] transition-all shadow-md flex justify-center items-center gap-2">
                    <Printer size={16}/> IMPRIMIR {item.qty_required} ETIQUETAS
                  </button>
                )}
                {printStatus === 'printing' && (
                  <div className="py-3 px-4 bg-blue-50 border border-blue-200 rounded-2xl flex items-center justify-center gap-2 text-blue-700 font-bold text-sm">
                    <RefreshCcw size={16} className="animate-spin"/> Transferindo para Zebra...
                  </div>
                )}
                {printStatus === 'done' && (
                  <div className="flex flex-col gap-2">
                    <div className="py-3 px-4 bg-emerald-50 border border-emerald-200 rounded-2xl flex items-center gap-2 text-emerald-800 font-bold text-sm">
                      <CheckCircle2 size={18} className="text-emerald-500"/> Etiquetas descarregadas
                    </div>
                    <button onClick={handleForcePrint} className="py-2 px-4 bg-slate-100 text-slate-600 font-bold rounded-xl hover:bg-slate-200 active:scale-95 text-xs flex items-center justify-center gap-1.5 transition-all">
                      <RefreshCcw size={13}/> Reimprimir
                    </button>
                  </div>
                )}
                {printStatus === 'error' && (
                  <div className="flex flex-col gap-2">
                    <div className="py-3 px-4 bg-red-50 border border-red-200 rounded-2xl flex items-start gap-2 text-red-800 text-xs font-medium">
                      <AlertCircle size={16} className="text-red-500 shrink-0 mt-0.5"/>
                      Falha de conexão com HUB 9100. Verifique o app Windows.
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <button onClick={handlePrint} className="py-2 bg-red-600 text-white font-bold rounded-xl hover:bg-red-700 text-xs uppercase active:scale-95 transition-all">
                        Reiniciar Print
                      </button>
                      <button onClick={handleFixSpooler} disabled={fixingSpooler} className="py-2 bg-slate-800 text-white font-bold rounded-xl hover:bg-black text-xs uppercase flex items-center justify-center gap-1 active:scale-95 transition-all">
                        {fixingSpooler ? <RefreshCcw size={12} className="animate-spin"/> : <AlertTriangle size={12}/>} Fix Spooler
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="p-5">
            <CompletionSummary items={allItems} onBack={() => navigate('/sessions')} />
          </div>
        )}
      </div>

      {/* RECENTES — abaixo do card */}
      {item && recentItems.length > 0 && (
        <div className="w-full max-w-sm mt-4">
          <h3 className="section-kicker mb-2 flex items-center gap-2"><History size={12}/> Acabaram de Passar</h3>
          <div className="flex flex-col gap-2">
            {recentItems.map(ri => (
              <div key={ri.sku} className="metric-tile text-sm flex justify-between items-center">
                <div className="flex items-center gap-3">
                  <div className={cn("w-2 h-2 rounded-full ring-4 shadow-sm",
                    ri.status === 'complete' ? "bg-emerald-500 ring-emerald-100" : ri.status === 'out_of_stock' ? "bg-red-500 ring-red-100" : "bg-amber-500 ring-amber-100"
                  )}/>
                  <span className="font-mono font-bold text-slate-700 text-xs">{ri.sku}</span>
                  <span className="bg-slate-100 px-2 py-0.5 rounded text-slate-500 font-bold tabular-nums text-xs">{ri.qty_picked} u.</span>
                  {ri.shortage_qty > 0 && <span className="text-red-600 bg-red-50 px-2 py-0.5 rounded font-bold text-xs">{ri.shortage_qty} falta</span>}
                </div>
                <button onClick={() => handleReopen(ri.sku)} className="text-blue-600 hover:text-blue-800 hover:bg-blue-50 px-2.5 py-1 rounded-lg font-bold text-xs transition-colors">Abrir Correção</button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── MODAIS ─────────────────────────────────────────────────── */}
      {dialog?.type === 'oos_confirm' && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-[100] p-4">
          <div className="bg-white rounded-3xl shadow-2xl p-6 md:p-8 max-w-sm w-full flex flex-col gap-6 animate-in zoom-in-95">
            <div className="w-16 h-16 bg-red-100 rounded-2xl flex items-center justify-center mx-auto text-red-600 mb-2"><XCircle size={32}/></div>
            <h2 className="text-2xl font-black text-center text-slate-800 tracking-tight">Decretar Ruptura</h2>
            <div className="bg-slate-50 border border-slate-200 rounded-2xl p-5 text-center text-sm">
              {item.qty_picked > 0 ? (
                <div className="flex flex-col gap-2">
                  <p className="font-bold text-emerald-700 py-1 bg-emerald-50 rounded-md">Manter {item.qty_picked} bipados salvos</p>
                  <p className="font-bold text-red-700 py-1 bg-red-50 rounded-md">Assinalar {item.qty_required - item.qty_picked} como inexistentes</p>
                </div>
              ) : (
                 <p className="font-bold text-red-700">O SKU total será movido para falta no inventário.</p>
              )}
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">Motivo do Saldo Remanescente (Opcional)</label>
              <textarea
                value={dialog.data.notes}
                onChange={e => setDialog({ ...dialog, data: { ...dialog.data, notes: e.target.value } })}
                autoFocus
                placeholder="Exemplo prático..."
                className="w-full text-sm font-medium border-2 border-slate-200 rounded-xl p-4 focus:outline-none focus:border-red-400 min-h-[100px] resize-none"
              />
            </div>
            <div className="grid grid-cols-2 gap-3 mt-2">
              <button onClick={() => { setDialog(null); focusInput() }} className="py-4 rounded-xl border-2 border-slate-200 text-slate-600 font-bold hover:bg-slate-50">Cancelar</button>
              <button onClick={() => _doOutOfStock(dialog.data.notes)} className="py-4 rounded-xl bg-red-600 text-white font-bold hover:bg-red-700 shadow-md">CONFIRMAR RUPTURA</button>
            </div>
          </div>
        </div>
      )}

      {dialog?.type === 'defect_adjust' && item && <DefectAdjustDialog item={item} onConfirm={handleDefectAdjustConfirm} onCancel={() => { setDialog(null); focusInput() }} />}
      {dialog?.type === 'unknown' && <UnknownBarcodeDialog barcode={dialog.data.barcode} currentSku={item?.sku} onAdd={() => handleAddBarcode(dialog.data.barcode)} onSkip={() => { setDialog(null); focusInput() }} />}

      {dialog?.type === 'wrong_session' && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-[100] p-4">
          <div className="bg-white rounded-3xl shadow-2xl p-6 md:p-8 max-w-sm w-full flex flex-col gap-6 animate-in zoom-in-95">
            <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mx-auto text-blue-600 mb-2"><Hand size={32}/></div>
            <h2 className="text-2xl font-black text-center text-slate-800 tracking-tight">Permissão de Agrupamento</h2>
            <div className="bg-blue-50 border border-blue-200 rounded-2xl p-6 text-center text-sm">
              <p className="text-slate-500 mb-3 font-medium">Você tem certeza que irá cruzar os pacotes? O código extra</p>
              <p className="font-mono font-bold text-xl bg-white border border-blue-100 py-2 rounded-lg break-all text-slate-700">{dialog.data.barcode}</p>
              <p className="text-slate-500 mt-4 mb-2 font-medium">já pertence historicamente ao SKU mestre:</p>
              <p className="font-mono font-black text-2xl text-blue-800">{dialog.data.sku}</p>
            </div>
            <div className="grid grid-cols-1 gap-3 mt-2">
              <button onClick={() => handleAddBarcode(dialog.data.barcode)} className="py-4 w-full rounded-2xl bg-blue-600 shadow-md text-white font-black hover:bg-blue-700">VINCULAR FORÇADO</button>
              <button onClick={() => { setDialog(null); focusInput() }} className="py-4 w-full rounded-2xl bg-slate-100 text-slate-600 font-bold hover:bg-slate-200">Rejeitar Tentativa</button>
            </div>
          </div>
        </div>
      )}

      {dialog?.type === 'box_qty' && item && <BoxQtyDialog item={item} onConfirm={handleBoxQtyConfirm} onCancel={() => { setDialog(null); focusInput() }} />}
      {dialog?.type === 'reprint_qty' && item && <ReprintQtyDialog item={item} defaultQty={dialog.data.qty} onConfirm={handleReprintConfirm} onCancel={() => { setDialog(null); focusInput() }} />}

      {dialog?.type === 'wrong_sku' && (
        <WrongSkuDialog scannedItem={dialog.data.item} expectedSku={dialog.data.expected_sku} onCancel={() => { setDialog(null); focusInput() }} onConfirm={async () => {
          const code = dialog.data.barcode
          const sku = dialog.data.scanned_sku
          setDialog(null)
          if (scanMode === 'box') {
            const res = await api.scan(sessionId, code, operator.id, sku)
            if (res.status === 'ok' || res.status === 'complete') {
              await api.undo(sessionId, sku, operator.id)
              setItem(res.item); setDialog({ type: 'box_qty', data: { code } })
            } else { updateFromResponse(res, code) }
          } else {
            const res = await api.reopen(sessionId, sku, operator.id)
            setItem(res.item); focusInput()
          }
        }} />
      )}
    </div>
  )
}

function DefectAdjustDialog({ item, onConfirm, onCancel }) {
  const [validQtyInput, setValidQtyInput] = useState(item.qty_picked)
  const [reprint, setReprint] = useState(false)
  const validQty = Math.max(0, Math.min(item.qty_picked, Number(validQtyInput) || 0))
  const oosQty = item.qty_picked - validQty
  const isInvalid = validQty >= item.qty_picked

  function handleConfirm() { if (!isInvalid) onConfirm({ defectQty: oosQty, reprint }) }

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-end md:items-center justify-center z-[100] md:p-4">
      <div className="bg-white rounded-t-3xl md:rounded-3xl shadow-2xl w-full max-w-sm flex flex-col gap-6 md:animate-in zoom-in-95 pb-safe pb-6">
        <div className="px-6 pt-8">
          <div className="w-16 h-16 bg-orange-100 rounded-2xl flex items-center justify-center mx-auto text-orange-600 mb-4"><AlertTriangle size={32}/></div>
          <h2 className="text-2xl font-black text-center text-slate-800">Ajuste de Saldo Corrompido</h2>
        </div>
        <div className="mx-6 bg-slate-50 border border-slate-200 rounded-2xl p-5 text-center">
          <p className="font-mono font-bold text-xl text-slate-800">{item.sku}</p>
          <p className="text-slate-500 text-xs mt-2 uppercase tracking-wide font-bold">Volume de sucesso prévio: <str className="text-slate-800 text-base">{item.qty_picked}</str></p>
        </div>
        <div className="mx-6 flex flex-col gap-3">
          <label className="text-xs font-bold text-slate-400 uppercase tracking-widest text-center">Digite o NÚMERO EXATO em bom estado</label>
          <input type="number" min={0} max={item.qty_picked - 1} value={validQtyInput} onChange={e => setValidQtyInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') handleConfirm() }} onFocus={e => e.target.select()} autoFocus
            className="text-center text-6xl font-black border-none bg-slate-100 text-slate-800 focus:bg-slate-200 rounded-2xl py-6 outline-none shadow-inner transition-colors" />
        </div>
        {oosQty > 0 && (
          <div className="mx-6 bg-red-50 text-red-700 rounded-xl p-4 text-center text-sm font-bold shadow-sm">
             -{oosQty} sub-peças atestadas em Falta / Dano
          </div>
        )}
        <div className={`mx-6 flex items-center gap-4 p-4 rounded-xl cursor-pointer transition-colors border-2 ${reprint ? 'bg-blue-50 border-blue-400' : 'bg-slate-50 border-transparent hover:border-slate-300'}`} onClick={() => setReprint(v => !v)}>
          <div className={`w-6 h-6 rounded-md flex items-center justify-center border-2 transition-colors ${reprint ? 'bg-blue-600 border-blue-600' : 'border-slate-300 bg-white'}`}>
            {reprint && <Check size={16} strokeWidth={4} className="text-white"/>}
          </div>
          <div><p className="text-sm font-black text-slate-700 uppercase">ZPL REPRINT OVERRIDE</p></div>
        </div>
        <div className="mx-6 grid grid-cols-2 gap-3 mt-2">
          <button onClick={onCancel} className="py-4 rounded-xl bg-slate-100 text-slate-600 font-bold hover:bg-slate-200">Abandonar</button>
          <button onClick={handleConfirm} disabled={isInvalid} className="py-4 rounded-xl bg-orange-500 shadow-md text-white font-bold hover:bg-orange-600 disabled:opacity-40">GRAVAR</button>
        </div>
      </div>
    </div>
  )
}

function ReprintQtyDialog({ item, defaultQty, onConfirm, onCancel }) {
  const [qtyInput, setQtyInput] = useState(String(defaultQty || item.qty_required))
  const qtyNum = Number(qtyInput)
  const safeQty = Number.isFinite(qtyNum) ? Math.max(1, qtyNum) : 1

  function handleConfirm() { onConfirm(safeQty) }
  function add(delta) {
    setQtyInput(String(Math.max(1, safeQty + delta)))
  }

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-end md:items-center justify-center z-[100] md:p-4">
      <div 
        className="bg-white rounded-t-3xl md:rounded-3xl shadow-2xl w-full max-w-md flex flex-col gap-6 md:animate-in zoom-in-95 pb-safe pb-6 border border-slate-200"
        onKeyDown={(e) => {
          if (e.key === 'Enter') handleConfirm()
          if (e.key === 'Escape') onCancel()
          if (e.key === 'ArrowUp') { e.preventDefault(); add(1) }
          if (e.key === 'ArrowDown') { e.preventDefault(); add(-1) }
        }}
      >
        <div className="px-6 pt-8 text-center text-slate-800">
          <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mx-auto text-blue-600 mb-4"><Printer size={32}/></div>
          <h2 className="text-2xl font-black tracking-tight">Cota da Bobina</h2>
          <p className="text-sm font-medium text-slate-500 mt-1">Ajuste a quantidade de etiquetas que deseja imprimir.</p>
        </div>
        
        <div className="mx-6 flex flex-col gap-3">
          <label className="text-xs font-bold text-slate-400 uppercase tracking-widest text-center">Quantidade de etiquetas</label>
          <input
            type="number"
            inputMode="numeric"
            min={1}
            value={qtyInput}
            onChange={e => setQtyInput(e.target.value)}
            onFocus={e => e.target.select()}
            autoFocus
            className="w-full text-center text-6xl font-black border-none bg-slate-100 text-slate-800 focus:bg-slate-200 rounded-2xl py-6 outline-none shadow-inner transition-colors [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
          />
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => add(-1)}
              className="py-5 rounded-2xl bg-slate-100 border border-slate-200 text-3xl font-black text-slate-700 hover:bg-slate-200 active:scale-95 transition-all"
            >
              −
            </button>
            <button
              onClick={() => add(1)}
              className="py-5 rounded-2xl bg-slate-100 border border-slate-200 text-3xl font-black text-slate-700 hover:bg-slate-200 active:scale-95 transition-all"
            >
              +
            </button>
          </div>
        </div>

        <div className="mx-6 grid grid-cols-2 gap-3 mt-2">
          <button onClick={onCancel} className="py-4 rounded-xl bg-slate-100 text-slate-600 font-bold hover:bg-slate-200 active:scale-95 transition-all">Voltar</button>
          <button onClick={handleConfirm} className="py-4 rounded-xl bg-blue-600 text-white font-black hover:bg-blue-700 shadow-md active:scale-95 transition-all">IMPRIMIR</button>
        </div>
      </div>
    </div>
  )
}

function BoxQtyDialog({ item, onConfirm, onCancel }) {
  const [qtyInput, setQtyInput] = useState(String(item.qty_required))
  const qtyNum = Number(qtyInput)
  const safeQty = Number.isFinite(qtyNum)
    ? Math.max(0, Math.min(item.qty_required, qtyNum))
    : 0

  function handleConfirm() { onConfirm(safeQty) }
  function add(delta) {
    setQtyInput(String(Math.max(0, Math.min(item.qty_required, safeQty + delta))))
  }

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-end md:items-center justify-center z-[100] md:p-4">
      <div
        className="bg-white rounded-t-3xl md:rounded-3xl shadow-2xl w-full max-w-md flex flex-col gap-6 md:animate-in zoom-in-95 pb-safe pb-6 border border-slate-200"
        onKeyDown={(e) => {
          if (e.key === 'Enter') handleConfirm()
          if (e.key === 'Escape') onCancel()
        }}
      >
        <div className="px-6 pt-8">
          <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mx-auto text-blue-700 mb-4"><Box size={32}/></div>
          <h2 className="text-2xl font-black text-center text-slate-900 tracking-tight">Ajuste de Caixa</h2>
          <p className="text-center text-slate-500 text-sm mt-1">Digite no teclado ou use os controles para confirmar o conteúdo real.</p>
        </div>
        <div className="mx-6 flex flex-col gap-3">
          <label className="text-xs font-bold text-slate-500 uppercase tracking-widest text-center">Quantidade encontrada na caixa</label>
          <div className="flex items-center gap-3">
            <button
              onClick={() => add(-1)}
              className="h-16 w-16 rounded-2xl bg-slate-100 border border-slate-300 text-3xl font-black text-slate-700 hover:bg-slate-200"
            >
              -
            </button>
            <input
              type="number"
              inputMode="numeric"
              min={0}
              max={item.qty_required}
              value={qtyInput}
              onChange={e => setQtyInput(e.target.value)}
              onFocus={e => e.target.select()}
              autoFocus
              className="flex-1 text-center text-6xl font-black border-none bg-slate-100 focus:bg-slate-200 rounded-2xl py-6 outline-none shadow-inner"
            />
            <button
              onClick={() => add(1)}
              className="h-16 w-16 rounded-2xl bg-slate-100 border border-slate-300 text-3xl font-black text-slate-700 hover:bg-slate-200"
            >
              +
            </button>
          </div>
        </div>
        <div className="mx-6 grid grid-cols-2 gap-3 mt-4">
          <button onClick={onCancel} className="py-4 rounded-xl bg-slate-100 text-slate-700 font-bold hover:bg-slate-200">Voltar</button>
          <button onClick={handleConfirm} className="py-4 rounded-xl bg-blue-600 text-white font-black hover:bg-blue-700 shadow-md">Confirmar</button>
        </div>
      </div>
    </div>
  )
}

function CompletionSummary({ items, onBack }) {
  if (items.length === 0) return <div className="flex justify-center py-20"><div className="animate-spin text-slate-400"><RefreshCcw size={40}/></div></div>
  const totalPicked = items.reduce((s, i) => s + i.qty_picked, 0)
  return (
    <div className="flex flex-col gap-6 max-w-2xl mx-auto w-full pt-10">
      <div className="panel-elevated bg-emerald-50 border border-emerald-200 rounded-3xl p-10 text-center">
        <CheckCircle2 size={80} className="mx-auto text-emerald-500 mb-4 drop-shadow-sm"/>
        <p className="text-4xl font-black text-emerald-800 tracking-tight">Plano Executado</p>
        <p className="text-emerald-600 font-medium text-lg mt-2">A fragmentação foi entregue no picking.</p>
        <div className="mt-8 pt-8 border-t border-emerald-200 border-dashed">
           <p className="font-black text-emerald-700 text-6xl">{items.filter(i=>i.status==='complete').length}<span className="text-2xl text-emerald-500 font-bold ml-2">SKU</span></p>
           <p className="font-bold text-emerald-600 mt-2 bg-emerald-100 rounded-lg py-1 px-4 inline-block">{totalPicked} Itens Lidos no Leitor 3D</p>
        </div>
      </div>
      <button onClick={onBack} className="w-full py-5 bg-slate-900 border text-white text-lg font-black tracking-widest uppercase rounded-2xl shadow-xl hover:bg-black active:scale-95 transition-all outline-none">
        SAIR DA OPERAÇÃO
      </button>
    </div>
  )
}
