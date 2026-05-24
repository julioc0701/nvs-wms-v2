import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'

/**
 * Estratégia híbrida de leitura de boleto:
 *   1. Tenta BarcodeDetector nativo (Chrome Android/Desktop, Edge) — mais rápido
 *   2. Fallback para zbar-wasm (Safari iOS, browsers antigos) — robusto pra ITF
 *
 * Lê frames do <video> via requestAnimationFrame (~30fps) e decodifica.
 * BarcodeDetector chama a engine do sistema (sub-millisegundo).
 * zbar-wasm roda em WASM (50-100ms por frame em mobile decente).
 */

// Lazy import do zbar-wasm — só carrega se BarcodeDetector não estiver disponível
let zbarModule = null
async function getZbar() {
  if (!zbarModule) {
    zbarModule = await import('@undecaf/zbar-wasm')
  }
  return zbarModule
}

// Detecta se BarcodeDetector nativo está disponível e suporta ITF
async function criarDetectorNativo() {
  if (typeof window.BarcodeDetector === 'undefined') return null
  try {
    const formats = await window.BarcodeDetector.getSupportedFormats()
    if (!formats.includes('itf')) return null
    return new window.BarcodeDetector({ formats: ['itf', 'code_128'] })
  } catch {
    return null
  }
}

export default function FinanceiroScan() {
  const navigate = useNavigate()
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)
  const rafRef = useRef(null)
  const ultimoCodigoRef = useRef(null)
  const [erro, setErro] = useState(null)
  const [estado, setEstado] = useState('scanning') // scanning | processando | manual
  const [cameraAtiva, setCameraAtiva] = useState(false)
  const [engineUsada, setEngineUsada] = useState('') // 'nativo' | 'zbar'

  useEffect(() => {
    if (estado !== 'scanning') return
    let mounted = true

    async function iniciar() {
      try {
        // Pede câmera traseira em resolução alta
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: { ideal: 'environment' },
            width: { ideal: 1920 },
            height: { ideal: 1080 },
          },
        })
        if (!mounted) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }
        streamRef.current = stream
        const video = videoRef.current
        video.srcObject = stream
        await video.play()
        setCameraAtiva(true)

        // Detecta qual engine usar
        const detectorNativo = await criarDetectorNativo()
        let engine
        if (detectorNativo) {
          engine = async (frame) => {
            const results = await detectorNativo.detect(frame)
            return results.length > 0 ? results[0].rawValue : null
          }
          setEngineUsada('nativo')
        } else {
          const zbar = await getZbar()
          engine = async (frame) => {
            const ctx = canvasRef.current.getContext('2d', { willReadFrequently: true })
            canvasRef.current.width = frame.videoWidth
            canvasRef.current.height = frame.videoHeight
            ctx.drawImage(frame, 0, 0)
            const imageData = ctx.getImageData(0, 0, canvasRef.current.width, canvasRef.current.height)
            const symbols = await zbar.scanImageData(imageData)
            if (symbols.length === 0) return null
            // Prefere símbolos do tipo ITF (boleto bancário)
            const itf = symbols.find((s) => s.typeName === 'ZBAR_I25')
            return (itf || symbols[0]).decode()
          }
          setEngineUsada('zbar')
        }

        // Loop de detecção
        async function tick() {
          if (!mounted || video.readyState < 2) {
            if (mounted) rafRef.current = requestAnimationFrame(tick)
            return
          }
          try {
            const texto = await engine(video)
            if (texto && texto !== ultimoCodigoRef.current) {
              ultimoCodigoRef.current = texto
              await processarLeitura(texto)
              return // para o loop após detectar
            }
          } catch {
            // engines podem falhar em frames específicos — ignora e continua
          }
          if (mounted) rafRef.current = requestAnimationFrame(tick)
        }

        rafRef.current = requestAnimationFrame(tick)
      } catch (e) {
        setErro(`Câmera indisponível: ${e.message}`)
        setEstado('manual')
      }
    }

    async function processarLeitura(texto) {
      setEstado('processando')
      try {
        const dados = await api.scanBoleto(texto)
        try { navigator.vibrate?.(200) } catch {}
        pararCamera()
        sessionStorage.setItem('boletoScanResult', JSON.stringify(dados))
        sessionStorage.setItem('boletoScanCodigo', texto)
        navigate('/financeiro/confirmar')
      } catch (e) {
        ultimoCodigoRef.current = null
        setErro(e.message)
        setEstado('scanning')
        setTimeout(() => setErro(null), 2500)
      }
    }

    function pararCamera() {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop())
        streamRef.current = null
      }
    }

    iniciar()

    return () => {
      mounted = false
      pararCamera()
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
        <span className="text-sm">
          {cameraAtiva ? 'Aponte para o código de barras' : 'Iniciando câmera…'}
        </span>
        <button onClick={() => setEstado('manual')} className="text-sm underline">Digitar</button>
      </div>
      <div className="relative flex-1 flex items-center justify-center">
        <video ref={videoRef} className="w-full h-full object-cover" playsInline muted autoPlay />
        <canvas ref={canvasRef} className="hidden" />
        {/* Mira do scanner */}
        <div className="absolute inset-x-8 top-1/2 -translate-y-1/2 h-32 border-2 border-cyan-400 rounded-lg pointer-events-none">
          {cameraAtiva && estado === 'scanning' && (
            <div className="absolute inset-x-0 top-1/2 h-0.5 bg-cyan-400 shadow-[0_0_8px_2px_rgba(34,211,238,0.8)] animate-pulse" />
          )}
        </div>
        {cameraAtiva && estado === 'scanning' && (
          <div className="absolute bottom-24 inset-x-0 text-center text-white/80 text-xs px-6">
            Mantenha o código de barras dentro do retângulo, parado, com boa iluminação.
            {engineUsada && (
              <div className="mt-1 text-white/40 text-[10px]">
                engine: {engineUsada === 'nativo' ? 'BarcodeDetector (nativo)' : 'zbar-wasm'}
              </div>
            )}
          </div>
        )}
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

/**
 * Formata uma linha digitável (47 dígitos) no padrão do boleto físico:
 * "23792.37213 90016.790967 25000.527306 3 14580000058182"
 * Estrutura: 5.5 (10) + 5.6 (11) + 5.6 (11) + 1 (DV) + 14 (fator+valor) = 47.
 */
function formatarLinhaDigitavel(raw) {
  const d = raw.replace(/\D/g, '')
  if (d.length <= 5) return d
  if (d.length <= 10) return `${d.slice(0, 5)}.${d.slice(5)}`
  if (d.length <= 15) return `${d.slice(0, 5)}.${d.slice(5, 10)} ${d.slice(10)}`
  if (d.length <= 21) return `${d.slice(0, 5)}.${d.slice(5, 10)} ${d.slice(10, 15)}.${d.slice(15)}`
  if (d.length <= 26) return `${d.slice(0, 5)}.${d.slice(5, 10)} ${d.slice(10, 15)}.${d.slice(15, 21)} ${d.slice(21)}`
  if (d.length <= 32) return `${d.slice(0, 5)}.${d.slice(5, 10)} ${d.slice(10, 15)}.${d.slice(15, 21)} ${d.slice(21, 26)}.${d.slice(26)}`
  if (d.length <= 33) return `${d.slice(0, 5)}.${d.slice(5, 10)} ${d.slice(10, 15)}.${d.slice(15, 21)} ${d.slice(21, 26)}.${d.slice(26, 32)} ${d.slice(32)}`
  return `${d.slice(0, 5)}.${d.slice(5, 10)} ${d.slice(10, 15)}.${d.slice(15, 21)} ${d.slice(21, 26)}.${d.slice(26, 32)} ${d.slice(32, 33)} ${d.slice(33, 47)}`
}

function ScanManualFallback({ erro, onSubmit, onVoltar }) {
  const [valor, setValor] = useState('')
  const digitos = valor.replace(/\D/g, '')
  const ok = digitos.length === 44 || digitos.length === 47

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-slate-900 text-white">
      <h2 className="text-lg mb-3 text-center">Digite ou cole a linha digitável</h2>
      <textarea
        value={valor}
        onChange={(e) => setValor(formatarLinhaDigitavel(e.target.value))}
        className="w-full max-w-md bg-slate-800 border border-slate-700 rounded p-3 text-white font-mono tracking-wide text-lg"
        rows={3}
        placeholder="00000.00000 00000.000000 00000.000000 0 0000000000000"
        inputMode="numeric"
        autoFocus
      />
      <div className="text-xs text-slate-400 mt-1">
        {digitos.length}/47 dígitos {ok && '✓'}
      </div>
      {erro && <div className="mt-2 text-red-400 text-sm max-w-md text-center">{erro}</div>}
      <div className="flex gap-2 mt-4">
        <button onClick={onVoltar} className="px-4 py-2 border border-slate-700 rounded">Câmera</button>
        <button
          onClick={() => onSubmit(valor)}
          disabled={!ok}
          className="px-6 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 disabled:text-slate-500 rounded"
        >
          Continuar
        </button>
      </div>
    </div>
  )
}
