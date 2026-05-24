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
  const [cameraAtiva, setCameraAtiva] = useState(false)

  useEffect(() => {
    if (estado !== 'scanning') return

    // Hints do ZXing — TRY_HARDER faz diferença grande pra códigos ITF de boleto.
    const hints = new Map()
    hints.set(DecodeHintType.POSSIBLE_FORMATS, [
      BarcodeFormat.ITF,
      BarcodeFormat.CODE_128,
      BarcodeFormat.CODE_39,
      BarcodeFormat.EAN_13,
    ])
    hints.set(DecodeHintType.TRY_HARDER, true)

    // Time between frames (ms). Padrão 500; reduzimos pra 150 = mais tentativas.
    const reader = new BrowserMultiFormatReader(hints, 150)
    let ultimoCodigo = null
    let mounted = true

    // Pede câmera TRASEIRA em resolução alta — essencial pra ler código fino de boleto
    const constraints = {
      video: {
        facingMode: { ideal: 'environment' },
        width: { ideal: 1920 },
        height: { ideal: 1080 },
      },
    }

    reader
      .decodeFromConstraints(constraints, videoRef.current, (result, _err, controls) => {
        if (!mounted) {
          controls?.stop()
          return
        }
        controlsRef.current = controls
        setCameraAtiva(true)
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
        <span className="text-sm">
          {cameraAtiva ? 'Aponte para o código de barras' : 'Iniciando câmera…'}
        </span>
        <button onClick={() => setEstado('manual')} className="text-sm underline">Digitar</button>
      </div>
      <div className="relative flex-1 flex items-center justify-center">
        <video ref={videoRef} className="w-full h-full object-cover" playsInline muted autoPlay />
        {/* Mira do scanner */}
        <div className="absolute inset-x-8 top-1/2 -translate-y-1/2 h-32 border-2 border-cyan-400 rounded-lg pointer-events-none">
          {/* Linha animada indicando que o scanner está lendo */}
          {cameraAtiva && estado === 'scanning' && (
            <div className="absolute inset-x-0 top-1/2 h-0.5 bg-cyan-400 shadow-[0_0_8px_2px_rgba(34,211,238,0.8)] animate-pulse" />
          )}
        </div>
        {/* Dica abaixo da mira */}
        {cameraAtiva && estado === 'scanning' && (
          <div className="absolute bottom-24 inset-x-0 text-center text-white/80 text-xs px-6">
            Mantenha o código de barras dentro do retângulo, parado, com boa iluminação.
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
 * Aceita digitação incremental: vai inserindo separadores conforme o usuário digita.
 */
function formatarLinhaDigitavel(raw) {
  const d = raw.replace(/\D/g, '')
  // Limites cumulativos: 5, 10, 15, 21, 26, 32, 33, 47
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
