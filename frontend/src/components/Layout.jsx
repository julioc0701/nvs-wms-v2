import { useEffect } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import novaesLogo from '../assets/logo-novaes-v3.png'
import { 
  Home, PackageSearch, Users, AlertCircle, LogOut, Database,
  LayoutDashboard, ListTodo, Wrench, Settings as SettingsIcon, CheckCircle2, ClipboardList
} from 'lucide-react'
import { cn } from '../lib/utils'

export default function Layout() {
  const navigate = useNavigate()
  const location = useLocation()
  const operator = JSON.parse(localStorage.getItem('operator') || 'null')

  const isMaster = operator?.name === 'Master'
  const isMobilePhone = window.innerWidth < 768

  // Redireciona não-master no celular para /separacao/listas (fora da rota de separação)
  useEffect(() => {
    const isLogin = location.pathname === '/'
    if (!isMaster && isMobilePhone && !isLogin) {
      const inSeparacao = location.pathname.startsWith('/separacao')
      if (!inSeparacao) navigate('/separacao/listas')
    }
  }, [location.pathname])

  // Detectar se estamos em uma sub-rota de supervisão de marketplace
  // Formato esperado: /supervisor/ml/* ou /supervisor/shopee/*
  const pathParts = location.pathname.split('/')
  const isSeparacaoActive = pathParts[1] === 'separacao'
  const isMarketplaceActive = pathParts[1] === 'supervisor' && (pathParts[2] === 'ml' || pathParts[2] === 'shopee')
  const activeMarketplace = isMarketplaceActive ? pathParts[2] : null

  const navItems = isMaster
    ? [
        { label: 'Supervisão Full', path: '/supervisor', icon: PackageSearch },
        { label: 'Separação', path: '/separacao', icon: ClipboardList },
        { label: 'Faltas', path: '/shortage-report', icon: AlertCircle, newTab: true },
        { label: 'ERP Olist', path: '/olist-orders', icon: Database },
        { label: 'Base', path: '/master-data', icon: Database },
        { label: 'Operadores', path: '/operators', icon: Users },
      ]
    : [
        { label: 'Sessões', path: '/sessions?view=active', icon: Home },
        { label: 'Listas Disponíveis', path: '/sessions?view=available', icon: ListTodo },
        { label: 'Listas Concluídas', path: '/sessions?view=history', icon: CheckCircle2 },
        { label: 'Faltantes', path: '/shortage-report', icon: AlertCircle, newTab: true },
        { label: 'Separação', path: '/separacao', icon: ClipboardList },
      ]

  // Sub-menus baseados na rota ativa
  const subNavItems = isMarketplaceActive ? [
    { label: 'Visão Geral',  path: `/supervisor/${activeMarketplace}/overview`, icon: LayoutDashboard },
    { label: 'Listas e Lotes', path: `/supervisor/${activeMarketplace}/lists`,    icon: ListTodo },
    { label: 'Processamento',  path: `/supervisor/${activeMarketplace}/tools`,    icon: Wrench },
    { label: 'Sistema',        path: `/supervisor/${activeMarketplace}/settings`, icon: SettingsIcon },
  ] : isSeparacaoActive ? [
    { label: 'Notas (Tiny)',   path: '/separacao', icon: ClipboardList },
    { label: 'Listas Geradas', path: '/separacao/listas', icon: ListTodo, newTab: true },
  ] : []

  const handleNav = (item) => {
    if (item.newTab) {
      window.open(item.path, '_blank', 'noopener')
    } else {
      navigate(item.path)
    }
  }

  function handleLogout() {
    localStorage.removeItem('operator')
    navigate('/')
  }

  const isPickingPage = location.pathname.includes('/picking/')
  const isLoginPage = location.pathname === '/'

  // Segurança de rota
  if (!operator && !isLoginPage) {
      setTimeout(() => navigate('/'), 0)
      return null
  }

  return (
    <div className="min-h-screen flex flex-col lg:flex-row font-sans text-slate-900">
      
      {/* SIDEBAR DESKTOP */}
      <aside className="hidden lg:flex w-72 flex-col bg-gradient-to-b from-slate-900 via-slate-900 to-blue-950 border-r border-slate-800 shadow-[0_16px_34px_rgba(2,6,23,0.35)] z-10 transition-all duration-300 text-slate-200">
        <div className="flex flex-col items-center px-6 py-8 border-b border-slate-800 gap-4">
          <div className="w-24 h-24 flex items-center justify-center group overflow-visible">
             <img src={novaesLogo} alt="NVS Logo" className="w-full h-full object-contain drop-shadow-[0_15px_30px_rgba(59,130,246,0.2)] transition-transform duration-700 group-hover:scale-110" />
          </div>
          <div className="text-center">
            <h1 className="text-2xl font-extrabold text-white tracking-tight leading-none">NVS<span className="text-cyan-300 font-extrabold">·</span>WMS</h1>
            <p className="text-[10px] font-semibold text-cyan-100 uppercase tracking-[0.22em] mt-2 px-3 py-1.5 bg-cyan-500/10 rounded-full inline-block border border-cyan-300/25">Novaes Moto Peças</p>
          </div>
        </div>
        
        <div className="flex-1 overflow-y-auto py-6 px-3 flex flex-col gap-1.5">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path) && !isMarketplaceActive)
            // Se for Supervisão Full e houver um marketplace ativo, mantemos o pai ativo
            const isParentActive = item.path === '/supervisor' && isMarketplaceActive
            
            return (
              <button
                key={item.path}
                onClick={() => handleNav(item)}
                className={cn(
                  "flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition-all duration-200",
                  (isActive || isParentActive)
                    ? "bg-gradient-to-r from-cyan-500 to-blue-500 text-white shadow-md shadow-cyan-900/30"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                )}
              >
                <Icon size={20} strokeWidth={(isActive || isParentActive) ? 2.5 : 2} />
                {item.label}
                {item.newTab && <span className="ml-auto text-[9px] opacity-40">↗</span>}
              </button>
            )
          })}

          {/* SUB-MENU DINÂMICO */}
          {(isMarketplaceActive || isSeparacaoActive) && (
            <div className="mt-4 pt-4 border-t border-slate-800 flex flex-col gap-1 animate-in fade-in slide-in-from-bottom-2 duration-500">
              <p className="px-3 mb-2 text-[10px] font-bold text-slate-400 uppercase tracking-[0.2em]">
                {isMarketplaceActive ? `Monitoramento ${activeMarketplace.toUpperCase()}` : "Gestão de Separação"}
              </p>
              {subNavItems.map((sub) => {
                const SubIcon = sub.icon
                const isSubActive = location.pathname === sub.path
                return (
                  <button
                    key={sub.path}
                    onClick={() => handleNav(sub)}
                    className={cn(
                      "flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-semibold transition-all duration-200 ml-2",
                      isSubActive
                        ? "bg-white text-slate-900 shadow-md border border-slate-200"
                        : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                    )}
                  >
                    <SubIcon size={16} strokeWidth={isSubActive ? 2.5 : 2} />
                    {sub.label}
                    {sub.newTab && <span className="ml-auto text-[9px] opacity-40">↗</span>}
                  </button>
                )
              })}
            </div>
          )}
        </div>

        <div className="p-4 border-t border-slate-800">
          <div className="flex items-center gap-3 px-3 py-3 rounded-xl bg-slate-800/80 border border-slate-700 mb-2">
            <div className="w-8 h-8 rounded-full bg-cyan-500 text-slate-950 flex items-center justify-center font-bold text-sm uppercase">
              {operator?.name?.charAt(0) || 'O'}
            </div>
            <div className="flex-1 overflow-hidden text-left">
               <p className="text-sm font-semibold truncate text-slate-100">{operator?.name || 'Operador'}</p>
            </div>
          </div>
          <button 
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2.5 text-sm font-medium text-slate-300 hover:text-red-200 hover:bg-red-500/15 rounded-lg transition-colors"
          >
            <LogOut size={18} />
            Sair
          </button>
        </div>
      </aside>

      {/* HEADER MOBILE */}
      <header className="lg:hidden flex h-14 bg-slate-900 border-b border-slate-800 items-center px-4 justify-between shadow-sm z-10 sticky top-0 transition-all duration-300">
         <div className="flex items-center gap-2">
           <img src={novaesLogo} className="w-8 h-8 rounded-lg shadow-sm border border-slate-100" />
           <h1 className="text-lg font-black text-white tracking-tight">NVS<span className="text-cyan-300">·</span></h1>
         </div>
         <div className="flex items-center gap-2">
           <span className="text-sm font-semibold text-slate-100 bg-slate-800 px-2 py-1 rounded-md">{operator?.name}</span>
           <button onClick={handleLogout} className="text-slate-400 hover:text-red-300 p-2">
             <LogOut size={18} />
           </button>
         </div>
      </header>

      {/* MOBILE SUB-NAV BAR — só aparece quando há sub-rotas e não é picking */}
      {!isPickingPage && subNavItems.length > 0 && (
        <div className="lg:hidden sticky top-14 z-10 bg-slate-800/95 border-b border-slate-700 flex overflow-x-auto gap-1 px-3 py-2 backdrop-blur-sm shrink-0">
          {subNavItems.map((sub) => {
            const SubIcon = sub.icon
            const isSubActive = location.pathname === sub.path
            return (
              <button
                key={sub.path}
                onClick={() => navigate(sub.path)}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors shrink-0 min-h-[36px] active:scale-95",
                  isSubActive
                    ? "bg-cyan-500 text-slate-950"
                    : "text-slate-300 hover:bg-slate-700"
                )}
              >
                <SubIcon size={14} />
                {sub.label}
              </button>
            )
          })}
        </div>
      )}

      {/* RENDER PAGES HERE */}
      <main className={cn(
        "flex-1 flex flex-col overflow-auto relative",
        // Padding bottom no mobile SE não for tela de picking
        (!isPickingPage) && "pb-16 lg:pb-0"
      )}>
        <Outlet />
      </main>

      {/* MOBILE BOTTOM NAVIGATION */}
      {!isPickingPage && (
        <nav className="lg:hidden flex h-16 bg-slate-900 border-t border-slate-800 justify-around items-center px-2 pb-safe fixed bottom-0 w-full z-20 shadow-[0_-4px_10px_-1px_rgba(2,6,23,0.35)]">
          {((!isMaster && isMobilePhone)
            ? [{ label: 'Listas', path: '/separacao/listas', icon: ListTodo }]
            : navItems
          ).map((item) => {
            const Icon = item.icon
            const isActive = location.pathname.startsWith(item.path)
            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                className={cn(
                  "flex flex-col items-center justify-center w-full h-full gap-1 transition-colors min-w-0 overflow-hidden px-0.5",
                  isActive ? "text-cyan-300" : "text-slate-400 hover:text-slate-200"
                )}
              >
                <div className={cn("p-1 rounded-full shrink-0", isActive && "bg-cyan-500/20")}>
                  <Icon size={isActive ? 22 : 20} strokeWidth={isActive ? 2.5 : 2} />
                </div>
                <span className={cn("text-[10px] uppercase tracking-wide w-full text-center truncate", isActive ? "font-bold" : "font-medium")}>
                  {item.label}
                </span>
              </button>
            )
          })}
        </nav>
      )}
    </div>
  )
}
