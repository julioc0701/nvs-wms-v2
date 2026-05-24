import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BrowserMultiFormatReader } from '@zxing/browser'
import { BarcodeFormat, DecodeHintType } from '@zxing/library'
import { api } from '../api/client'

export default function FinanceiroScan() {
  const navigate = useNavigate()
  const videoRef = useRef(null)
  const controlsRef = useRef(null)
  const [erro, setErro] = useState(null)
  const [estado, setEstado] = useState('scanning') // scanning | processando | manual

  useEffect(() => {
    if (estado !== 'scanning') return
    const hints = new Map()
    hints.set(DecodeHintType.POSSIBLE_FORMATS, [
      BarcodeFormat.ITF,
      BarcodeFormat.CODE_128,
    ])
    const reader = new BrowserMultiFormatReader(hints)
    let ultimoCodigo = null
    let mounted = true

    reader
      .decodeFromVideoDevice(undefined, videoRef.current, (result, _err, controls) => {
        if (!mounted) {
          controls?.stop()
          return
        }
        controlsRef.current = controls
        if (!result) return
        const texto = result.getText()
        if (texto === ultimoCodigo) return
        ultimoCodigo = texto
        setEstado('processando')
        api
          .scanBoleto(texto)
          .then((dados) => {
            try { navigator.vibrate?.(200) } catch {}
            controls?.stop()
            sessionStorage.setItem('boletoScanResult', JSON.stringify(dados))
            sessionStorage.setItem('boletoScanCodigo', texto)
            navigate('/financeiro/confirmar')
          })
          .catch((e) => {
            ultimoCodigo = null
            setErro(e.message)
            setEstado('scanning')
            setTimeout(() => setErro(null), 2000)
          })
      })
      .catch((e) => {
        setErro(`Câmera indisponível: ${e.message}`)
        setEstado('manual')
      })

    return () => {
      mounted = false
      controlsRef.current?.stop()
    }
  }, [estado, navigate])

  async function processarManual(linha) {
    try {
      const dados = await api.scanBoleto(linha)
      sessionStorage.setItem('boletoScanResult', JSON.stringify(dados))
      sessionStorage.setItem('boletoScanCodigo', linha)
      navigate('/financeiro/confirmar')
    } catch (e) {
      setErro(e.message)
    }
  }

  if (estado === 'manual') {
    return <ScanManualFallback erro={erro} onSubmit={processarManual} onVoltar={() => setEstado('scanning')} />
  }

  return (
    <div className="fixed inset-0 bg-black z-50 flex flex-col">
      <div className="flex items-center justify-between p-4 text-white">
        <button onClick={() => navigate('/sessions')} className="text-sm">← Voltar</button>
        <span className="text-sm">Aponte para o código de barras</span>
        <button onClick={() => setEstado('manual')} className="text-sm underline">Digitar</button>
      </div>
      <div className="relative flex-1 flex items-center justify-center">
        <video ref={videoRef} className="w-full h-full object-cover" playsInline muted />
        <div className="absolute inset-x-8 top-1/2 -translate-y-1/2 h-32 border-2 border-cyan-400 rounded-lg pointer-events-none" />
        {estado === 'processando' && (
          <div className="absolute inset-0 bg-black/60 flex items-center justify-center text-white">
            Processando…
          </div>
        )}
      </div>
      {erro && (
        <div className="bg-red-600 text-white text-sm p-3 text-center">{erro}</div>
      )}
    </div>
  )
}

function ScanManualFallback({ erro, onSubmit, onVoltar }) {
  const [valor, setValor] = useState('')
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-slate-900 text-white">
      <h2 className="text-lg mb-3">Digite ou cole o código / linha digitável</h2>
      <textarea
        value={valor}
        onChange={(e) => setValor(e.target.value)}
        className="w-full max-w-md bg-slate-800 border border-slate-700 rounded p-3 text-white"
        rows={3}
        placeholder="44 ou 47 dígitos"
      />
      {erro && <div className="mt-2 text-red-400 text-sm">{erro}</div>}
      <div className="flex gap-2 mt-4">
        <button onClick={onVoltar} className="px-4 py-2 border border-slate-700 rounded">Câmera</button>
        <button onClick={() => onSubmit(valor)} className="px-6 py-2 bg-cyan-600 hover:bg-cyan-500 rounded">
          Continuar
        </button>
      </div>
    </div>
  )
}
