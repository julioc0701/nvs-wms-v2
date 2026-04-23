import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import novaesLogo from '../assets/logo-novaes-v3.png'

export default function Login() {
  const [operators, setOperators] = useState([])
  const [selected, setSelected] = useState('')
  const [pin, setPin] = useState('')
  const [step, setStep] = useState(1) // 1 = select name, 2 = enter pin
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    api.getOperators().then(setOperators).catch(() => setError('Não foi possível conectar ao servidor'))
  }, [])

  async function handleConfirmPin() {
    if (pin.length < 4) {
      setError('O PIN deve ter pelo menos 4 dígitos')
      return
    }
    setError('')
    try {
      const res = await api.loginOperator(Number(selected), pin)
      if (res.status === 'ok') {
        localStorage.setItem('operator', JSON.stringify(res.operator))
        const isMobile = window.innerWidth < 768
        navigate(res.operator.name === 'Master' ? '/supervisor' : isMobile ? '/separacao/listas' : '/sessions')
      }
    } catch (err) {
      setError(err.message || 'Erro ao validar PIN')
      setPin('')
    }
  }

  function handleNumberClick(n) {
    if (pin.length < 6) setPin(prev => prev + n) // Limit to 6 digits visually
  }

  function handleDelete() {
    setPin(prev => prev.slice(0, -1))
  }

  return (
    <div className="premium-shell min-h-screen flex items-center justify-center p-4 md:p-8">
      
      {step === 1 && (
        <div className="w-full max-w-5xl grid md:grid-cols-2 overflow-hidden rounded-3xl border border-slate-200/80 shadow-[0_20px_48px_rgba(15,23,42,0.16)] transition-all duration-700 animate-in fade-in slide-in-from-bottom-10">
          <div className="hidden md:flex flex-col justify-between p-10 bg-gradient-to-br from-slate-900 via-blue-900 to-cyan-700 text-white relative">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(125,211,252,0.2),transparent_45%),radial-gradient(circle_at_80%_30%,rgba(56,189,248,0.2),transparent_45%)]" />
            <div className="relative z-10">
              <p className="text-xs uppercase tracking-[0.28em] text-cyan-100 font-bold">Plataforma Operacional</p>
              <h1 className="text-5xl font-black tracking-tight mt-3 leading-none">NVS·WMS</h1>
              <p className="mt-5 text-cyan-50/90 text-sm leading-relaxed max-w-sm">
                Interface de picking desenhada para ritmo de operação, leitura rápida e tomada de decisão sem fricção.
              </p>
            </div>
            <div className="relative z-10 flex justify-center items-center pt-2">
              <img
                src={novaesLogo}
                alt="NVS Novaes"
                className="w-72 h-72 object-contain drop-shadow-[0_22px_52px_rgba(56,189,248,0.42)]"
              />
            </div>
          </div>

          <div className="bg-white p-8 md:p-10 flex flex-col gap-8">
            <div className="md:hidden text-center">
              <div className="w-40 h-40 mx-auto mb-3 flex items-center justify-center">
                <img src={novaesLogo} alt="NVS Novaes" className="w-full h-full object-contain" />
              </div>
              <h1 className="text-4xl font-black tracking-tight text-slate-900 leading-none">NVS<span className="text-blue-600">·</span>WMS</h1>
            </div>

            <div>
              <p className="badge-soft">Acesso de Operador</p>
              <h2 className="text-2xl font-extrabold text-slate-900 mt-3">Entrar no Turno</h2>
              <p className="text-sm text-slate-600 mt-1">Selecione seu nome para iniciar o fluxo de picking.</p>
            </div>

            {error && <p className="text-red-600 text-center font-medium bg-red-50 p-3 rounded-xl border border-red-100">{error}</p>}

            <div className="flex flex-col gap-4">
              <select
                value={selected}
                onChange={e => setSelected(e.target.value)}
                className="w-full border border-slate-300 rounded-2xl p-4 text-lg bg-slate-50 focus:outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100 focus:bg-white transition-all shadow-sm"
              >
                <option value="">Selecionar operador</option>
                {operators.map(op => (
                  <option key={op.id} value={op.id}>{op.name}</option>
                ))}
              </select>

              <button
                onClick={() => {
                  if(selected) { setStep(2); setError(''); }
                }}
                disabled={!selected}
                className="w-full py-4 mt-2 bg-gradient-to-r from-blue-600 to-cyan-600 text-white text-lg font-bold rounded-2xl hover:from-blue-700 hover:to-cyan-700 disabled:opacity-40 transition-all shadow-md active:scale-[0.98]"
              >
                Continuar
              </button>
            </div>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="w-full max-w-sm bg-white/95 backdrop-blur-md p-8 rounded-3xl border border-slate-200/80 shadow-[0_16px_36px_rgba(15,23,42,0.12)] flex flex-col items-center gap-6">
          <div className="text-center w-full relative">
            <button 
              onClick={() => { setStep(1); setPin(''); setError(''); }}
              className="absolute left-0 top-1 text-slate-400 hover:text-slate-700"
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
            </button>
            <h2 className="text-xl font-bold text-slate-800">Confirme com PIN</h2>
            <p className="text-sm text-slate-500 mt-1">{operators.find(o => o.id === Number(selected))?.name}</p>
          </div>

          <div className="flex justify-center flex-col items-center w-full">
            <div className="flex gap-3 mb-2 h-16 items-center justify-center">
              {[...Array(6)].map((_, i) => (
                 <div key={i} className={`w-4 h-4 rounded-full transition-all ${i < pin.length ? 'bg-blue-600 scale-110' : 'bg-gray-200'} ${i >= 4 ? 'hidden' : ''} ${pin.length > 4 ? 'hidden' : ''}`} />
              ))}
              {pin.length > 4 && (
                <div className="text-3xl tracking-widest font-mono font-bold text-blue-600">
                  {'*'.repeat(pin.length)}
                </div>
              )}
            </div>
            {error && <p className="text-red-600 text-sm font-medium animate-pulse">{error}</p>}
          </div>

          <div className="grid grid-cols-3 gap-4 w-full mt-2">
            {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(n => (
              <button key={n} onClick={() => handleNumberClick(n.toString())} className="h-16 rounded-full bg-slate-50 text-2xl font-semibold text-slate-800 hover:bg-slate-200 active:bg-slate-300 transition-colors shadow-sm border border-slate-200">
                {n}
              </button>
            ))}
            <div />
            <button onClick={() => handleNumberClick('0')} className="h-16 rounded-full bg-slate-50 text-2xl font-semibold text-slate-800 hover:bg-slate-200 active:bg-slate-300 transition-colors shadow-sm border border-slate-200">
              0
            </button>
            <button onClick={handleDelete} className="h-16 rounded-full text-slate-500 hover:text-slate-800 hover:bg-slate-100 flex items-center justify-center transition-colors">
              <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M3 12l6.414 6.414a2 2 0 001.414.586H19a2 2 0 002-2V7a2 2 0 00-2-2h-8.172a2 2 0 00-1.414.586L3 12z" /></svg>
            </button>
          </div>

          <button
            onClick={handleConfirmPin}
            disabled={pin.length === 0}
            className="w-full py-4 mt-2 bg-gradient-to-r from-blue-600 to-blue-500 text-white text-xl font-bold rounded-2xl hover:from-blue-700 hover:to-blue-600 disabled:opacity-40 transition-colors shadow-md active:scale-[0.98]"
          >
            CONFIRMAR
          </button>
        </div>
      )}
    </div>
  )
}
