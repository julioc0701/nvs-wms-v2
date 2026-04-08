import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import MarketplaceLogo from '../components/MarketplaceLogo'
import SearchSelectionDialog from '../components/dialogs/SearchSelectionDialog'
import { Search, Hourglass, ArrowRight, CheckCircle2, Lock, XCircle, AlertTriangle, ArrowRightCircle, ListTodo } from 'lucide-react'
import { cn } from '../lib/utils'
import { useCompactViewport } from '../hooks/useCompactViewport'

export default function SessionSelect() {
  const compact = useCompactViewport(800)
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const view = searchParams.get('view') || 'active'
  const operator = JSON.parse(sessionStorage.getItem('operator') || 'null')

  const [searchBarcode, setSearchBarcode] = useState('')
  const [searchResult, setSearchResult] = useState(null)
  const [searching, setSearching] = useState(false)
  const searchRef = useRef()
  const dismissTimer = useRef()

  useEffect(() => {
    if (!operator) { navigate('/'); return }
    load()
  }, [])

  useEffect(() => {
    searchRef.current?.focus()
  }, [])

  useEffect(() => {
    return () => clearTimeout(dismissTimer.current)
  }, [])

  useEffect(() => {
    // Limpa alertas contextuais ao trocar de visão para não "vazar" estado entre abas.
    setSearchResult(null)
    clearTimeout(dismissTimer.current)
  }, [view])

  function load() {
    setLoading(true)
    api.getSessions()
      .then(data => setSessions(data))
      .finally(() => setLoading(false))
  }

  const mySessions = sessions.filter(
    s => s.operator_id === operator?.id && s.status !== 'completed'
  )

  const available = sessions.filter(s =>
    s.status === 'open' && !s.operator_id
  )

  const myDone = sessions.filter(
    s => s.operator_id === operator?.id && s.status === 'completed'
  )
  const totalOpen = sessions.filter(s => s.status === 'open' && !s.operator_id).length
  const totalMine = sessions.filter(s => s.operator_id === operator?.id && s.status !== 'completed').length

  function openSession(sessionId) {
    navigate(`/sessions/${sessionId}/items`)
  }

  async function handleBarcodeSearch(e) {
    if (e.key !== 'Enter' || !searchBarcode.trim()) return
    const code = searchBarcode.trim()
    setSearchBarcode('')
    setSearching(true)
    setSearchResult(null)
    clearTimeout(dismissTimer.current)

    try {
      const result = await api.findByBarcode(code, operator.id)

      if (result.action === 'open' || result.action === 'transfer_available') {
        const { session_id } = result.best_match
        navigate(`/picking/${session_id}?sku=${encodeURIComponent(result.sku)}`)
        return
      }

      if (result.action === 'multiple_matches') {
        setSearchResult({ action: 'multiple_matches', candidates: result.candidates })
        return
      }

      setSearchResult(result)
      dismissTimer.current = setTimeout(() => setSearchResult(null), 4000)
    } catch {
      setSearchResult({ action: 'error' })
      dismissTimer.current = setTimeout(() => setSearchResult(null), 4000)
    } finally {
      setSearching(false)
      searchRef.current?.focus()
    }
  }

  async function handleShowAllPending() {
    setSearching(true)
    setSearchResult(null)
    clearTimeout(dismissTimer.current)
    try {
      const candidates = await api.getAllPendingItems()
      if (candidates.length === 0) {
        setSearchResult({ action: 'not_in_sessions', sku: '---' })
        dismissTimer.current = setTimeout(() => setSearchResult(null), 4000)
      } else {
        setSearchResult({ action: 'multiple_matches', candidates })
      }
    } catch (err) {
      setSearchResult({ action: 'error', message: err.message })
      dismissTimer.current = setTimeout(() => setSearchResult(null), 4000)
    } finally {
      setSearching(false)
    }
  }

  async function onSelectSearchResult(candidate) {
    setSearchResult(null)
    const isOtherOperator = candidate.operator_name && candidate.operator_name !== operator.name && candidate.operator_name !== 'Disponível'
    
    if (isOtherOperator) {
      setSearching(true)
      try {
        const res = await api.transferItem(candidate.item_id, operator.id)
        navigate(`/picking/${res.new_session_id}?sku=${encodeURIComponent(candidate.sku)}`)
      } catch (err) {
        setSearchResult({ action: 'error', message: `Erro na transferência automática: ${err.message}` })
      } finally {
        setSearching(false)
      }
      return
    }

    navigate(`/picking/${candidate.session_id}?sku=${encodeURIComponent(candidate.sku)}`)
  }

  return (
    <div className={cn("p-4 md:p-8 max-w-7xl mx-auto w-full", compact && "compact-density")}>
      {/* Header Contexto Dinâmico */}
      <div className="mb-6 relative">
        <div className="action-rail-floating hidden md:flex absolute -left-[178px] top-3 z-10">
          <div className="action-rail flex flex-col gap-2 min-w-[156px]">
            {view !== 'active' && (
              <button
                onClick={() => navigate('/sessions?view=active')}
                className="text-xs font-bold text-blue-700 bg-blue-50 px-4 py-2 rounded-full border border-blue-100 hover:bg-blue-100 transition-colors shadow-sm"
              >
                Voltar para Ativas
              </button>
            )}
            <button
              onClick={() => { sessionStorage.removeItem('operator'); navigate('/') }}
              className="text-xs font-bold text-slate-700 bg-slate-100 px-4 py-2 rounded-full border border-slate-300 hover:bg-slate-200 transition-colors shadow-sm"
            >
              Trocar Usuário
            </button>
          </div>
        </div>

        <div className="panel-elevated p-6 md:p-7 text-center md:text-left">
          <p className="section-kicker text-blue-700 mb-2">Painel de Operação</p>
          <h2 className="text-3xl font-extrabold text-slate-800 tracking-tight">
            {view === 'active' && 'Sessões em Andamento'}
            {view === 'available' && 'Listas Disponíveis'}
            {view === 'history' && 'Histórico de Conclusão'}
          </h2>
          <p className="text-sm font-medium text-slate-600 mt-2">
            {view === 'active' && 'Gerencie seus lotes de trabalho atuais.'}
            {view === 'available' && 'Escolha uma nova demanda para iniciar a bipagem.'}
            {view === 'history' && 'Consulte os lotes que você finalizou hoje.'}
          </p>
          <div className="compact-actions-inline mt-4 flex md:hidden flex-wrap items-center gap-2 justify-center md:justify-start">
            {view !== 'active' && (
              <button 
                onClick={() => navigate('/sessions?view=active')}
                className="text-xs font-bold text-blue-700 bg-blue-50 px-4 py-2 rounded-full border border-blue-100 hover:bg-blue-100 transition-colors"
              >
                Voltar para Ativas
              </button>
            )}
            <button
              onClick={() => { sessionStorage.removeItem('operator'); navigate('/') }}
              className="text-xs font-bold text-slate-700 bg-slate-100 px-4 py-2 rounded-full border border-slate-300 hover:bg-slate-200 transition-colors"
            >
              Trocar Usuário
            </button>
          </div>
        </div>
      </div>

      <div className="mb-6 grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="metric-tile">
          <p className="metric-label">Minhas Ativas</p>
          <p className="metric-value mt-1">{totalMine}</p>
        </div>
        <div className="metric-tile">
          <p className="metric-label">Fila Livre</p>
          <p className="metric-value mt-1">{totalOpen}</p>
        </div>
        <div className="metric-tile">
          <p className="metric-label">Concluídas Hoje</p>
          <p className="metric-value mt-1">{myDone.length}</p>
        </div>
      </div>

      {/* Barcode Seach Box (Sempre visível conforme pedido) */}
      <div className="mb-8 panel-elevated p-4 md:p-5 flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 group">
          <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
            <Search className="text-slate-400 group-focus-within:text-blue-500 transition-colors" size={24} />
          </div>
          <input
            ref={searchRef}
            type="text"
            value={searchBarcode}
            onChange={e => setSearchBarcode(e.target.value)}
            onKeyDown={handleBarcodeSearch}
            placeholder="EAN, SKU ou título p/ atalho mágico..."
            className="w-full bg-slate-50 border border-slate-300 focus:border-blue-500 focus:ring-4 focus:ring-blue-100 rounded-2xl pl-12 pr-5 py-4 text-lg font-medium outline-none transition-all shadow-sm"
            disabled={searching}
          />
        </div>
        <button
          onClick={handleShowAllPending}
          disabled={searching}
          className="bg-gradient-to-r from-slate-900 to-slate-700 hover:from-black hover:to-slate-900 disabled:bg-slate-300 text-white font-bold px-6 py-4 rounded-2xl flex items-center justify-center gap-3 transition-colors shadow-sm sm:w-auto w-full group"
        >
          <Hourglass className={cn("text-slate-400 group-hover:text-white transition-colors", searching && "animate-spin")} size={22} />
          <span className="text-xs uppercase tracking-widest whitespace-nowrap">SKU Faltantes</span>
        </button>
      </div>

      {searchResult && searchResult.action !== 'multiple_matches' && (
        <div className={cn(
          "mt-2 mb-8 rounded-2xl p-5 border shadow-sm animate-in fade-in slide-in-from-top-2",
          searchResult.action === 'already_done'       ? 'bg-emerald-50 border-emerald-200' : 
          (searchResult.action === 'in_progress_other' || searchResult.action === 'transfer_available') ? 'bg-amber-50 border-amber-200' : 
          'bg-red-50 border-red-200'
        )}>
          {searchResult.action === 'already_done' && (() => {
            const m = searchResult.best_match
            return (
              <div className="flex gap-4 items-start">
                 <CheckCircle2 className="text-emerald-500 shrink-0 mt-1" size={24}/>
                 <div>
                   <p className="font-bold text-emerald-800 text-lg">Produto já recolhido!</p>
                   <p className="mt-1 text-emerald-700 font-medium text-sm leading-relaxed">
                     O sistema acusa que esse item já foi bipado anteriormente por <strong className="uppercase bg-emerald-100 px-1 rounded">{m.operator_name}</strong> na jornada do lote <strong>{m.session_code}</strong>.
                   </p>
                 </div>
              </div>
            )
          })()}

          {(searchResult.action === 'in_progress_other' || searchResult.action === 'transfer_available') && (() => {
            const m = searchResult.best_match
            const isTransfer = searchResult.action === 'transfer_available'
            const IconCall = isTransfer ? ArrowRightCircle : Lock
            return (
              <div className="flex gap-4 items-start">
                 <IconCall className="text-amber-500 shrink-0 mt-1" size={24}/>
                 <div>
                   <p className="font-bold text-amber-800 text-lg">
                     {isTransfer ? 'Disponível para Tomada de Posse' : 'Bloqueado por Outro Operador'}
                   </p>
                   <p className="mt-1 text-amber-700 font-medium text-sm leading-relaxed">
                     O item <span className="bg-amber-100 font-mono px-2 py-0.5 rounded text-amber-900 border border-amber-200">{searchResult.sku}</span> {' '}
                     {isTransfer ? 'pode ser trazido para o seu controle da respectiva lista de' : 'já está retido no carimbo de trabalho de'} {' '}
                     <strong className="uppercase bg-amber-100 px-1 rounded">{m.operator_name}</strong> no lote <strong>{m.session_code}</strong>.
                   </p>
                 </div>
              </div>
            )
          })()}

          {(searchResult.action === 'not_found' || searchResult.action === 'not_in_sessions') && (
            <div className="flex gap-4 items-start">
              <XCircle className="text-red-500 shrink-0 mt-1" size={24}/>
               <div>
                 <p className="font-bold text-red-800 text-lg">Leitura não reconhecida</p>
                 <p className="mt-1 text-red-700 font-medium text-sm leading-relaxed">
                   {searchResult.action === 'not_in_sessions'
                     ? <>O código <span className="font-mono font-bold bg-white px-1 rounded">{searchResult.sku}</span> foi encontrado na base, mas não existe demanda para ele nos lotes abertos ou pendentes.</>
                     : 'O código de barra emitido pelo leitor não consta em nenhum registro matriz do banco de dados.'}
                 </p>
               </div>
            </div>
          )}

          {searchResult.action === 'error' && (
            <div className="flex gap-4 items-center text-red-800">
               <AlertTriangle className="text-red-500" size={24}/>
               <p className="font-bold text-lg">{searchResult.message || 'Falha sistêmica — repita a tentativa'}</p>
            </div>
          )}
        </div>
      )}

      {searchResult?.action === 'multiple_matches' && (
        <SearchSelectionDialog
          candidates={searchResult.candidates}
          onSelect={onSelectSearchResult}
          onCancel={() => setSearchResult(null)}
        />
      )}

      {loading && (
        <div className="surface-card p-10 flex justify-center items-center text-slate-500 gap-3">
          <Hourglass className="animate-spin" /> Carregando operações...
        </div>
      )}

      {!loading && (
        <div className="flex flex-col gap-10">
          {/* SEÇÃO 1: SESSÕES ATIVAS (EM ANDAMENTO) */}
          {view === 'active' && (
            <div>
              <h3 className="text-xs font-bold text-slate-500 uppercase tracking-[0.2em] mb-5 flex items-center gap-3">
                 <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" /> Minhas Operações Correntes
              </h3>
              {mySessions.length === 0 ? (
                <div className="panel-elevated rounded-[1.25rem] py-16 flex flex-col items-center justify-center text-center opacity-70">
                   <div className="p-3 bg-slate-100 rounded-full mb-4">
                     <ListTodo size={32} className="text-slate-400" />
                   </div>
                   <p className="text-lg font-black text-slate-600">Nenhuma sessão ativa</p>
                   <p className="text-xs font-medium text-slate-400 mt-1">Vá para 'Listas Disponíveis' para assumir uma carga.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {mySessions.map(s => (
                    <button
                      key={s.id}
                      onClick={() => navigate(`/sessions/${s.id}/items`)}
                      className="panel-elevated group relative overflow-hidden flex flex-col p-5 rounded-2xl text-left border-l-4 border-l-blue-500"
                    >
                      <div className="absolute -right-10 -top-10 w-32 h-32 bg-blue-500/5 rounded-full blur-3xl group-hover:bg-blue-500/10 transition-colors duration-500" />
                      <div className="relative z-10 flex justify-between items-center mb-6">
                        <div className="flex items-center gap-4">
                          <MarketplaceLogo marketplace={s.marketplace} size={56} />
                          <div>
                            <span className="text-2xl font-black text-slate-800 tracking-tight block">{s.session_code}</span>
                            <span className="text-[10px] font-bold text-blue-700 uppercase tracking-widest">Retomar Lote</span>
                          </div>
                        </div>
                        <div className="w-10 h-10 rounded-full bg-slate-50 flex items-center justify-center text-slate-400 group-hover:bg-blue-600 group-hover:text-white transition-all duration-300">
                          <ArrowRight size={20} />
                        </div>
                      </div>
                      <div className="relative z-10 mt-auto">
                        <ProgressBar picked={s.items_picked} total={s.items_total} color="blue" />
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* SEÇÃO 2: LISTAS DISPONÍVEIS (FILA) */}
          {view === 'available' && (
            <div>
              <h3 className="text-xs font-bold text-slate-500 uppercase tracking-[0.2em] mb-5">
                Fila de Distribuição Livre
              </h3>
              {available.length === 0 ? (
                <div className="panel-elevated rounded-[1.25rem] py-20 flex flex-col items-center justify-center text-center">
                  <div className="p-4 bg-slate-50 rounded-full mb-4">
                     <AlertTriangle size={40} className="text-slate-300" />
                  </div>
                  <p className="text-xl font-black text-slate-700">Linha de Produção Vazia</p>
                  <p className="text-sm font-medium text-slate-400 mt-2 max-w-[200px]">Nenhum novo lote ou transferência em espera.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {available.map(s => (
                    <button
                      key={s.id}
                      onClick={() => openSession(s.id)}
                      className="panel-elevated group p-5 rounded-2xl flex flex-col text-left relative overflow-hidden border-l-4 border-l-slate-400"
                    >
                      <div className="flex items-center gap-4 mb-6">
                         <MarketplaceLogo marketplace={s.marketplace} size={40} />
                         <div className="flex-1">
                           <span className="text-lg font-black text-slate-800 block truncate">{s.session_code}</span>
                           <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Ingressar</span>
                         </div>
                      </div>
                      <div className="mt-auto">
                         <ProgressBar picked={s.items_picked} total={s.items_total} color="gray" />
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* SEÇÃO 3: HISTÓRICO CONCLUÍDO */}
          {view === 'history' && (
            <div>
              <h3 className="text-xs font-bold text-slate-500 uppercase tracking-[0.2em] mb-5 flex items-center gap-3">
                 <CheckCircle2 size={16} className="text-emerald-500" /> Histórico do Turno
              </h3>
              {myDone.length === 0 ? (
                <div className="panel-elevated rounded-[1.25rem] py-16 flex flex-col items-center justify-center text-center opacity-70">
                   <CheckCircle2 size={40} className="text-slate-200 mb-2" />
                   <p className="text-lg font-black text-slate-600">Nenhum lote finalizado</p>
                   <p className="text-xs font-medium text-slate-400 mt-1">Conclua uma carga para que ela apareça no seu registro de hoje.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {myDone.map(s => (
                    <button
                      key={s.id}
                      onClick={() => navigate(`/sessions/${s.id}/items`)}
                      className="panel-elevated border-l-4 border-l-emerald-500 rounded-[1rem] p-5 text-left transition-all group opacity-70 hover:opacity-100"
                    >
                      <div className="flex justify-between items-center mb-4">
                        <div className="flex items-center gap-3">
                          <MarketplaceLogo marketplace={s.marketplace} size={24} className="grayscale group-hover:grayscale-0 transition-all" />
                          <span className="font-bold text-slate-600">{s.session_code}</span>
                        </div>
                        <CheckCircle2 size={18} className="text-emerald-500" />
                      </div>
                      <ProgressBar picked={s.items_picked} total={s.items_total} color="green" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ProgressBar({ picked, total, color = 'blue' }) {
  const pct = total ? Math.round((picked / total) * 100) : 0
  const barColor = color === 'green' ? 'bg-emerald-500' : color === 'blue' ? 'bg-blue-500' : 'bg-slate-400'
  return (
    <div className="mt-4 flex flex-col gap-2">
      <div className="flex justify-between text-xs font-bold tabular-nums">
        <span className="text-slate-400">Progresso</span>
        <span className="text-slate-600">{picked}/{total}</span>
      </div>
      <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden shadow-inner flex">
        <div className={cn("h-full rounded-full transition-all duration-700", barColor)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
