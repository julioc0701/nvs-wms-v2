import { useState, useRef, useEffect } from 'react'
import { MessageSquare, Cpu, Send, RefreshCcw, Loader2, Database, ShieldCheck, DatabaseZap, Activity, TimerReset } from 'lucide-react'
import { api } from '../api/client'
import { useFeedback } from '../components/ui/FeedbackProvider'
import { cn } from '../lib/utils'

// Importando o layout antigo para usar via Generative UI
import OlistOrders from './OlistOrders'

export default function GemmaDashboard() {
  const { notify } = useFeedback()
  const [activePanel, setActivePanel] = useState('sync')
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      content: 'Olá! Sou o Gemma 4, o cérebro neural por trás do seu estoque. Analiso métricas de expedição, curvas ABC e desempenho de marcadores. Como posso ajudar nas operações de hoje?'
    }
  ])
  const [input, setInput] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  
  // Controls Generative UI injection
  const [activeGenerativeUI, setActiveGenerativeUI] = useState(null)
  const [isVacuuming, setIsVacuuming] = useState(false)
  const [dbStats, setDbStats] = useState({ orders: 0, items: 0, canonical: 0 })
  const [syncStatus, setSyncStatus] = useState({ runs: [], canonical_total: 0, raw_total: 0, scheduler_running: false, sync_in_progress: false })
  const [syncAction, setSyncAction] = useState(null)
  const [isRefreshingSync, setIsRefreshingSync] = useState(false)

  const messagesEndRef = useRef(null)

  // Auto-scroll para mensagens novas
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, activeGenerativeUI])

  // Busca o status do SQLite na inicialização para exibir ao usuário
  useEffect(() => {
    async function loadDbStats() {
      try {
        const res = await api.get('/health')
        setDbStats({
          orders: res.db_orders_synced || 0,
          items: res.db_items_synced || 0,
          canonical: res.db_orders_canonical || 0,
        })
      } catch (err) {
        console.error('Falha ao carregar estado do BD:', err)
      }
    }
    loadDbStats()
  }, [])

  const loadSyncStatus = async () => {
    try {
      setIsRefreshingSync(true)
      const res = await api.getTinySyncStatus()
      setSyncStatus(res)
    } catch (err) {
      console.error('Falha ao carregar status do sync:', err)
      notify('error', 'Falha ao atualizar', 'Nao consegui recarregar o status da sincronizacao.')
    } finally {
      setIsRefreshingSync(false)
    }
  }

  useEffect(() => {
    loadSyncStatus()
    const timer = setInterval(loadSyncStatus, 8000)
    return () => clearInterval(timer)
  }, [])

  const handleVacuum = async () => {
    try {
      setIsVacuuming(true)
      const forceToken = localStorage.getItem('tiny_token') || '' 
      const res = await api.post(`/tiny/vacuum-30-days?api_token=${forceToken}`, {})
      notify('success', 'Aspirador Massivo Acionado!', res.message || 'Mapeamento invisível dos últimos 30 dias iniciado com sucesso.')
      
      // Auto mensagem do assistant para avisar
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: `Acabei de disparar as engrenagens de fundo. O servidor está varrendo a API de forma cirúrgica para preencher o Data Warehouse SQLite. Você pode sair dessa tela, vai demorar algumas horas para finalizar tudo nos bastidores.`
      }])
    } catch (error) {
      notify('error', 'Ops!', 'A estrutura precisa estar com o Token Tiny na primeira camada.')
    } finally {
      setIsVacuuming(false)
    }
  }

  const handleSyncAction = async (mode) => {
    try {
      setSyncAction(mode)
      let res
      if (mode === 'full') {
        res = await api.triggerTinyFullSync(60)
      } else if (mode === 'incremental') {
        res = await api.triggerTinyIncrementalSync(3)
      } else {
        res = await api.triggerTinyReconcileSync(30)
      }
      notify('success', 'Sync acionado', res.message || 'Processo iniciado com sucesso.')
      await loadSyncStatus()
    } catch (error) {
      notify('error', 'Falha no sync', error.message || 'Não consegui iniciar a sincronização.')
    } finally {
      setSyncAction(null)
    }
  }

  const latestRun = syncStatus.runs?.[0] || null
  const syncIsRunning = syncStatus.sync_in_progress || latestRun?.status === 'running'
  const primarySyncLabel = syncIsRunning
    ? 'Carga em andamento'
    : syncAction === 'full'
      ? 'Disparando carga inicial...'
      : 'Carga Inicial'

  const handleSend = async () => {
    if (!input.trim()) return
    
    const userMessage = input.trim()
    setInput('')
    
    // Adiciona msg do user
    const novaMensagemId = Date.now().toString()
    setMessages(prev => [...prev, { id: novaMensagemId, role: 'user', content: userMessage }])
    setIsTyping(true)

    try {
      // 1. Prepara o histórico para mandar pro backend (ignora tool_calls se houver, ou a gente manda só o formato text)
      // O backend quer um array de messages no padrão [{"role": "user", "content": "..."}]
      const messagesToSend = messages
         .filter(m => m.id !== 'welcome') // Removemos a msg inicial hardcoded caso queira economizar contexto
         .map(m => ({ role: m.role, content: m.content }));
         
      messagesToSend.push({ role: 'user', content: userMessage });
      
      const res = await api.chatWithGemma(messagesToSend);
      
      // Recebe Resposta em Texto
      if (res.message && res.message.content) {
          setMessages(prev => [...prev, {
            id: Date.now().toString(),
            role: 'assistant',
            content: res.message.content
          }]);
      }
      
      // Recebe Resposta Generativa Visuais (Function Calling)
      if (res.generative_ui) {
          setActiveGenerativeUI(res.generative_ui);
      } else {
          setActiveGenerativeUI(null);
      }
      
    } catch (err) {
      console.error(err);
      notify('error', 'Falha Neural', 'O Cérebro Gemma não conseguiu responder. Verifique os logs.');
    } finally {
      setIsTyping(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col p-4 md:p-8 animate-in fade-in duration-700">
      
      {/* Header Neural */}
      <div className="w-full max-w-5xl mx-auto flex items-center justify-between mb-6 bg-slate-800/50 p-4 rounded-xl border border-blue-500/20 backdrop-blur-md shadow-lg shadow-blue-500/5">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-blue-500/10 rounded-xl relative group overflow-hidden">
            <Cpu className="text-blue-400 w-8 h-8 relative z-10 animate-pulse" />
            <div className="absolute inset-0 bg-blue-400/20 translate-y-full group-hover:translate-y-0 transition-transform duration-500" />
          </div>
          <div>
            <h1 className="text-2xl font-black text-white/90 tracking-tight flex items-center gap-2">
              Gemma 4 <span className="text-sm font-semibold px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300">Inteligente</span>
            </h1>
            <p className="text-slate-400 text-sm font-medium">Centro Operacional Unificado</p>
          </div>
        </div>
        
        {/* Painel Tático SQLite */}
        <div className="flex items-center gap-3 md:gap-6">
           {/* Stats: visível apenas em md+ (tablet/desktop) */}
           <div className="hidden md:flex flex-col items-end">
             <span className="text-xs text-slate-500 font-bold tracking-wider">Carga do Data Warehouse</span>
             <div className="flex items-center gap-2 mt-1">
               <ShieldCheck className="w-4 h-4 text-emerald-400" />
               <span className="text-emerald-400 text-sm font-bold">{dbStats.orders.toLocaleString()} <span className="text-slate-500 font-medium">Pedidos</span></span>
               <span className="text-slate-500">|</span>
               <span className="text-emerald-400 text-sm font-bold">{dbStats.items.toLocaleString()} <span className="text-slate-500 font-medium">Itens</span></span>
               <span className="text-slate-500">|</span>
               <span className="text-cyan-300 text-sm font-bold">{dbStats.canonical.toLocaleString()} <span className="text-slate-500 font-medium">Canônico</span></span>
             </div>
           </div>
           {/* Botão sempre visível — label oculto em telas < sm */}
           <button
             onClick={handleVacuum}
             disabled={isVacuuming}
             className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 md:px-4 py-2 md:py-2.5 rounded-lg border border-slate-700 hover:border-slate-500 transition-all font-medium text-sm disabled:opacity-50 min-h-[44px] active:scale-95"
           >
             {isVacuuming ? <Loader2 className="w-4 h-4 animate-spin text-blue-400" /> : <DatabaseZap className="w-4 h-4 text-amber-400 shrink-0" />}
             <span className="hidden sm:inline">Limpar Fundo/Mapear</span>
           </button>
        </div>
      </div>

      <div className="w-full max-w-5xl mx-auto mb-6">
        <div className="inline-flex rounded-2xl border border-slate-700 bg-slate-800/70 p-1 shadow-lg">
          <button
            onClick={() => setActivePanel('sync')}
            className={cn(
              'rounded-xl px-5 py-2.5 text-sm font-black tracking-wide transition',
              activePanel === 'sync' ? 'bg-cyan-500 text-slate-950 shadow-lg' : 'text-slate-300 hover:text-white'
            )}
          >
            Sincronização
          </button>
          <button
            onClick={() => setActivePanel('agent')}
            className={cn(
              'rounded-xl px-5 py-2.5 text-sm font-black tracking-wide transition',
              activePanel === 'agent' ? 'bg-blue-500 text-white shadow-lg' : 'text-slate-300 hover:text-white'
            )}
          >
            Agent
          </button>
        </div>
      </div>

      {activePanel === 'sync' && (
      <div className="w-full max-w-5xl mx-auto mb-6 grid gap-4 md:grid-cols-[1.25fr_0.75fr]">
        <div className="rounded-2xl border border-cyan-500/20 bg-slate-800/40 p-4 shadow-lg shadow-cyan-500/5">
          <div className="flex items-start justify-between gap-4 mb-4">
            <div>
              <div className="flex items-center gap-2 text-cyan-300 text-xs font-black uppercase tracking-[0.25em]">
                <Database className="w-4 h-4" /> Sync Center
              </div>
              <h2 className="text-xl font-black text-white mt-2">Sincronização do Banco</h2>
              <p className="text-sm text-slate-400 mt-1">Clique uma vez e acompanhe o andamento aqui.</p>
            </div>
            <button
              onClick={loadSyncStatus}
              disabled={isRefreshingSync}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2 text-sm font-semibold text-slate-300 hover:border-slate-500 hover:text-white"
            >
              {isRefreshingSync ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCcw className="w-4 h-4" />}
              {isRefreshingSync ? 'Atualizando...' : 'Atualizar'}
            </button>
          </div>

          <div className={cn(
            'mb-4 rounded-2xl border px-4 py-4',
            syncIsRunning ? 'border-amber-400/30 bg-amber-500/10' : 'border-emerald-400/20 bg-emerald-500/10'
          )}>
            <div className="flex items-center gap-3">
              {syncIsRunning ? <Loader2 className="w-5 h-5 animate-spin text-amber-300" /> : <ShieldCheck className="w-5 h-5 text-emerald-300" />}
              <div>
                <div className="text-sm font-black uppercase tracking-wider text-white">
                  {syncIsRunning ? 'Sincronização em andamento' : 'Sincronização parada'}
                </div>
                <div className="text-sm text-slate-300 mt-1">
                  {latestRun?.notes || 'Nenhuma execução ativa agora.'}
                </div>
              </div>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <button
              onClick={() => handleSyncAction('full')}
              disabled={!!syncAction || syncIsRunning}
              className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-4 text-left transition hover:bg-emerald-500/15 disabled:opacity-60"
            >
              <div className="flex items-center gap-2 text-emerald-300 font-black">
                {syncIsRunning || syncAction === 'full' ? <Loader2 className="w-4 h-4 animate-spin" /> : <DatabaseZap className="w-4 h-4" />}
                {primarySyncLabel}
              </div>
              <div className="text-sm text-slate-300 mt-2">Faz a carga forte dos últimos 60 dias em blocos automáticos.</div>
            </button>

            <button
              onClick={() => handleSyncAction('reconcile')}
              disabled={!!syncAction || syncIsRunning}
              className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-4 text-left transition hover:bg-amber-500/15 disabled:opacity-60"
            >
              <div className="flex items-center gap-2 text-amber-300 font-black"><TimerReset className="w-4 h-4" /> Reconciliação</div>
              <div className="text-sm text-slate-300 mt-2">Usa quando quiser revisar e corrigir o banco.</div>
            </button>
          </div>

          <div className="mt-4 rounded-xl border border-slate-700 bg-slate-900/60 p-4">
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <span className={cn(
                'inline-flex items-center gap-2 rounded-full px-3 py-1 font-bold',
                syncStatus.scheduler_running ? 'bg-emerald-500/15 text-emerald-300' : 'bg-slate-700 text-slate-300'
              )}>
                <span className="w-2 h-2 rounded-full bg-current" />
                Scheduler {syncStatus.scheduler_running ? 'ativo' : 'parado'}
              </span>
              <span className={cn(
                'inline-flex items-center gap-2 rounded-full px-3 py-1 font-bold',
                syncStatus.sync_in_progress ? 'bg-amber-500/15 text-amber-300' : 'bg-slate-700 text-slate-300'
              )}>
                <span className="w-2 h-2 rounded-full bg-current" />
                {syncStatus.sync_in_progress ? 'Sincronizando agora' : 'Sem sync em execução'}
              </span>
              {syncAction && (
                <span className="inline-flex items-center gap-2 rounded-full bg-cyan-500/15 px-3 py-1 font-bold text-cyan-300">
                  <Loader2 className="w-4 h-4 animate-spin" /> Disparando {syncAction}
                </span>
              )}
            </div>

            {latestRun && (
              <div className="mt-4 grid gap-2 text-sm text-slate-300 md:grid-cols-2">
                <div>Última execução: <span className="font-bold text-white">{latestRun.sync_type}</span></div>
                <div>Status: <span className="font-bold text-white">{latestRun.status}</span></div>
                <div>Pedidos vistos: <span className="font-bold text-white">{latestRun.orders_seen}</span></div>
                <div>Inseridos/Atualizados: <span className="font-bold text-white">{latestRun.orders_inserted} / {latestRun.orders_updated}</span></div>
                {latestRun.updated_at && (
                  <div>Última atualização: <span className="font-bold text-white">{latestRun.updated_at}</span></div>
                )}
                {latestRun.notes && (
                  <div className="md:col-span-2 rounded-lg bg-slate-950/60 px-3 py-2 text-xs text-cyan-200">
                    {latestRun.notes}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-700 bg-slate-800/40 p-4 shadow-lg">
          <div className="flex items-center gap-2 text-slate-300 text-xs font-black uppercase tracking-[0.25em]">
            <MessageSquare className="w-4 h-4" /> Log
          </div>
          <div className="mt-3 space-y-3 max-h-[280px] overflow-y-auto pr-1">
            {syncStatus.runs?.length ? syncStatus.runs.map((run) => (
              <div key={run.id} className="rounded-xl border border-slate-700 bg-slate-900/70 p-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-black text-white">{run.sync_type}</span>
                  <span className="text-xs font-bold uppercase text-slate-400">{run.status}</span>
                </div>
                <div className="mt-2 text-xs text-slate-400">
                  janela {run.window_start || '-'} até {run.window_end || '-'}
                </div>
                <div className="mt-2 text-sm text-slate-300">
                  vistos {run.orders_seen} | novos {run.orders_inserted} | atualizados {run.orders_updated} | falhas {run.orders_failed}
                </div>
                {run.notes && <div className="mt-2 text-xs text-slate-500">{run.notes}</div>}
              </div>
            )) : (
              <div className="rounded-xl border border-dashed border-slate-700 bg-slate-900/40 p-4 text-sm text-slate-500">
                Ainda sem execuções registradas.
              </div>
            )}
          </div>
        </div>
      </div>
      )}

      {activePanel === 'agent' && (
      <>
      {/* Main Chat Area */}
      <div className="w-full max-w-5xl mx-auto flex-1 flex flex-col bg-slate-800/30 border border-slate-700/50 rounded-2xl overflow-hidden backdrop-blur-xl shadow-2xl relative">
        
        <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
          {messages.map((msg) => (
            <div key={msg.id} className={cn("flex", msg.role === 'user' ? "justify-end" : "justify-start")}>
              <div className={cn(
                "max-w-[85%] md:max-w-[75%] rounded-2xl p-4 shadow-sm",
                msg.role === 'user' 
                  ? "bg-blue-600 text-white rounded-br-none" 
                  : "bg-slate-800 text-slate-200 border border-slate-700 rounded-bl-none"
              )}>
                {msg.role === 'assistant' && (
                  <div className="flex items-center gap-2 mb-2 text-blue-400 text-xs font-black uppercase tracking-wider">
                    <MessageSquare className="w-3 h-3" /> Gemma System
                  </div>
                )}
                <p className="leading-relaxed text-sm md:text-base">{msg.content}</p>
              </div>
            </div>
          ))}

          {/* Generative UI Component Injection Area */}
          {activeGenerativeUI === 'olist_orders' && (
             <div className="w-full mt-8 border border-emerald-500/30 rounded-xl overflow-hidden shadow-2xl shadow-emerald-500/5 bg-slate-800/80 animate-in slide-in-from-bottom-6 duration-700 fade-in">
                <div className="bg-emerald-500/10 px-4 py-2 border-b border-emerald-500/20 flex items-center justify-between">
                    <span className="text-emerald-400 text-xs font-bold uppercase tracking-widest flex items-center gap-2">
                        <Cpu className="w-4 h-4" /> Componente Visual Injetado Pela IA
                    </span>
                    <button onClick={() => setActiveGenerativeUI(null)} className="text-slate-400 hover:text-white text-xs">
                        Fechar Visão X
                    </button>
                </div>
                {/* Aqui renderizamos o Grid inteirinho! */}
                <div className="relative h-[800px] overflow-y-auto custom-scrollbar bg-slate-50">
                    <OlistOrders isGenerativeMode={true} />
                </div>
             </div>
          )}

          {isTyping && (
            <div className="flex justify-start">
              <div className="bg-slate-800 border border-slate-700 rounded-2xl rounded-bl-none p-4 flex gap-2 items-center">
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce delay-75" />
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce delay-150" />
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce delay-300" />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="p-4 bg-slate-800/50 border-t border-slate-700/50">
          <form 
            onSubmit={(e) => { e.preventDefault(); handleSend(); }}
            className="flex gap-3 max-w-4xl mx-auto relative"
          >
            <input 
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Peça gráficos, chame telas completas ou faça perguntas ao Gemma 4..."
              className="flex-1 bg-slate-900 border border-slate-600 rounded-xl px-5 py-4 focus:ring-2 focus:ring-blue-500 focus:outline-none text-white placeholder-slate-500 shadow-inner"
            />
            <button 
              type="submit"
              disabled={!input.trim() || isTyping}
              className="bg-blue-600 hover:bg-blue-500 text-white rounded-xl px-6 py-4 flex items-center justify-center transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-blue-600/30"
            >
              <Send className="w-5 h-5" />
            </button>
          </form>
        </div>

      </div>
      </>
      )}

    </div>
  )
}
