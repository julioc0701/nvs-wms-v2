import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { cn } from '../lib/utils'
import { Camera, Keyboard, Loader2, RefreshCw, FileText, PenLine, ChevronRight } from 'lucide-react'
import { api } from '../api/client'

/**
 * Tela de captura de boleto.
 *
 * 2 caminhos:
 *   1. Tirar foto → câmera nativa do celular/desktop → backend usa Gemini Vision
 *      para extrair a linha digitável → parser FEBRABAN valida → confirmar.
 *   2. Digitar código manualmente → máscara incremental → confirmar.
 *
 * Sem stream de vídeo, sem ZXing/ZBar. A câmera nativa do dispositivo
 * faz autofoco e captura uma imagem estática de alta qualidade.
 */
export default function FinanceiroScan() {
  const navigate = useNavigate()
  // Estados: 'home' (2 botões) | 'preview' (foto tirada) | 'lendo' | 'falhou' | 'manual'
  const [estado, setEstado] = useState('home')
  const [fotoB64, setFotoB64] = useState(null)
  const [erro, setErro] = useState(null)
  const fileInputRef = useRef(null)
  const pdfInputRef = useRef(null)
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768

  async function comprimirFoto(file) {
    return new Promise((resolve) => {
      const img = new Image()
      const reader = new FileReader()
      reader.onload = (e) => {
        img.onload = () => {
          const canvas = document.createElement('canvas')
          const maxLado = 1600
          const escala = Math.min(1, maxLado / Math.max(img.width, img.height))
          canvas.width = img.width * escala
          canvas.height = img.height * escala
          canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height)
          resolve(canvas.toDataURL('image/jpeg', 0.85))
        }
        img.src = e.target.result
      }
      reader.readAsDataURL(file)
    })
  }

  async function onArquivoEscolhido(e) {
    const file = e.target.files?.[0]
    if (!file) return
    const dataUrl = await comprimirFoto(file)
    setFotoB64(dataUrl)
    setEstado('preview')
    e.target.value = '' // permite re-selecionar mesma foto
  }

  async function processarFoto() {
    setEstado('lendo')
    setErro(null)
    try {
      const dados = await api.scanBoletoFoto(fotoB64)
      sessionStorage.setItem('boletoScanResult', JSON.stringify(dados))
      sessionStorage.setItem('boletoScanCodigo', dados.codigo_barras)
      navigate('/financeiro/confirmar')
    } catch (e) {
      setErro(e.message)
      setEstado('falhou')
    }
  }

  async function processarPdf(file) {
    setEstado('lendo')
    setErro(null)
    try {
      const dados = await api.scanBoletoPdf(file)
      sessionStorage.setItem('boletoScanResult', JSON.stringify(dados))
      sessionStorage.setItem('boletoScanCodigo', dados.codigo_barras)
      navigate('/financeiro/confirmar')
    } catch (e) {
      setErro(e.message)
      setEstado('falhou')
    }
  }

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

  // ── Renderizações por estado ─────────────────────────────────────────────

  if (estado === 'manual') {
    return (
      <ScanManualFallback
        erro={erro}
        onSubmit={processarManual}
        onVoltar={() => { setErro(null); setEstado('home') }}
      />
    )
  }

  if (estado === 'lendo') {
    return (
      <TelaCheia>
        <Loader2 size={48} className="animate-spin text-cyan-400 mb-4" />
        <h2 className="text-xl text-white mb-2">Lendo boleto…</h2>
        <p className="text-white/60 text-sm">A IA está extraindo os dados da foto</p>
      </TelaCheia>
    )
  }

  if (estado === 'preview') {
    return (
      <TelaCheia>
        <h2 className="text-lg text-white mb-3">Boleto fotografado</h2>
        <img
          src={fotoB64}
          alt="Boleto"
          className="max-w-md w-full max-h-[60vh] object-contain border border-slate-700 rounded mb-4"
        />
        <div className="flex gap-3 w-full max-w-md">
          <button
            onClick={() => { setFotoB64(null); setEstado('home') }}
            className="flex-1 py-3 border-2 border-slate-600 text-slate-300 rounded-xl font-semibold"
          >
            Tirar outra
          </button>
          <button
            onClick={processarFoto}
            className="flex-1 py-3 bg-cyan-600 hover:bg-cyan-500 text-white rounded-xl font-bold"
          >
            Continuar
          </button>
        </div>
      </TelaCheia>
    )
  }

  if (estado === 'falhou') {
    return (
      <TelaCheia>
        <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center mb-4">
          <span className="text-3xl">⚠</span>
        </div>
        <h2 className="text-xl text-white mb-2">Não foi possível ler</h2>
        <p className="text-red-300 text-sm text-center max-w-md mb-6 px-4">
          {erro || 'Tente uma foto mais nítida e bem iluminada.'}
        </p>
        <div className="flex flex-col gap-3 w-full max-w-md">
          <button
            onClick={() => { setErro(null); setFotoB64(null); setEstado('home') }}
            className="py-3 bg-cyan-600 hover:bg-cyan-500 text-white rounded-xl font-bold flex items-center justify-center gap-2"
          >
            <RefreshCw size={20} /> Tirar nova foto
          </button>
          <button
            onClick={() => { setErro(null); setEstado('manual') }}
            className="py-3 border-2 border-slate-600 text-slate-300 rounded-xl font-semibold flex items-center justify-center gap-2"
          >
            <Keyboard size={20} /> Digitar código manualmente
          </button>
        </div>
      </TelaCheia>
    )
  }

  // estado === 'home'
  return (
    <TelaCheia>
      <button
        onClick={() => navigate('/financeiro')}
        className="absolute top-4 left-4 text-sm text-slate-400 flex items-center gap-1.5"
      >
        ← Voltar
      </button>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={onArquivoEscolhido}
        className="hidden"
      />
      <input
        ref={pdfInputRef}
        type="file"
        accept="application/pdf"
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) processarPdf(f)
          e.target.value = ''
        }}
        className="hidden"
      />

      <div className="w-full max-w-md px-4 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">Novo lançamento</h1>
          <p className="text-sm text-slate-400">Como você quer registrar?</p>
        </div>

        {/* Card primário — PDF (recomendado, só desktop) ou Foto (mobile) */}
        {!isMobile ? (
          <button
            onClick={() => pdfInputRef.current?.click()}
            className="w-full bg-gradient-to-br from-cyan-500/15 to-cyan-700/10 hover:from-cyan-500/25 hover:to-cyan-700/20 active:scale-[0.98] border border-cyan-500/40 rounded-2xl p-5 transition-all flex items-center gap-4 text-left"
          >
            <div className="w-12 h-12 rounded-xl bg-cyan-500/20 flex items-center justify-center text-cyan-300 shrink-0">
              <FileText size={26} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-white font-bold text-base">Anexar PDF do boleto</div>
              <div className="text-cyan-200/70 text-xs mt-0.5">Mais rápido e preciso</div>
            </div>
            <ChevronRight size={20} className="text-cyan-300/70 shrink-0" />
          </button>
        ) : (
          <button
            onClick={() => fileInputRef.current?.click()}
            className="w-full bg-gradient-to-br from-cyan-500/15 to-cyan-700/10 hover:from-cyan-500/25 hover:to-cyan-700/20 active:scale-[0.98] border border-cyan-500/40 rounded-2xl p-5 transition-all flex items-center gap-4 text-left"
          >
            <div className="w-12 h-12 rounded-xl bg-cyan-500/20 flex items-center justify-center text-cyan-300 shrink-0">
              <Camera size={26} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-white font-bold text-base">Tirar foto do boleto</div>
              <div className="text-cyan-200/70 text-xs mt-0.5">A IA lê e preenche os dados</div>
            </div>
            <ChevronRight size={20} className="text-cyan-300/70 shrink-0" />
          </button>
        )}

        {/* Divisor */}
        <div className="flex items-center gap-3 pt-2">
          <div className="flex-1 h-px bg-slate-700/50" />
          <span className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold">
            Outras opções
          </span>
          <div className="flex-1 h-px bg-slate-700/50" />
        </div>

        {/* Lista de outras opções */}
        <div className="bg-slate-800/30 rounded-2xl border border-slate-700/50 overflow-hidden">
          {/* Foto (no desktop, já que PDF é primário; no mobile esse é primário) */}
          {!isMobile && (
            <OpcaoItem
              icon={<Camera size={22} />}
              titulo="Foto do boleto"
              subtitulo="A IA lê e preenche os dados"
              onClick={() => fileInputRef.current?.click()}
            />
          )}

          {/* PDF no mobile vira opção secundária (raramente usado em celular) */}
          {isMobile && (
            <OpcaoItem
              icon={<FileText size={22} />}
              titulo="Anexar PDF do boleto"
              subtitulo="Leitura direta do arquivo"
              onClick={() => pdfInputRef.current?.click()}
            />
          )}

          <OpcaoItem
            icon={<Keyboard size={22} />}
            titulo="Digitar código manualmente"
            subtitulo="Linha digitável de 47 dígitos"
            onClick={() => setEstado('manual')}
          />

          <OpcaoItem
            icon={<PenLine size={22} />}
            titulo="Lançamento manual"
            subtitulo="Despesa, PIX, fornecedor, etc."
            onClick={() => navigate('/financeiro/lancamento-manual')}
            ultimo
          />
        </div>
      </div>
    </TelaCheia>
  )
}

function OpcaoItem({ icon, titulo, subtitulo, onClick, ultimo }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-3 px-4 py-3.5 hover:bg-slate-700/30 active:bg-slate-700/50 transition-colors text-left',
        !ultimo && 'border-b border-slate-700/40'
      )}
    >
      <div className="w-9 h-9 rounded-lg bg-slate-700/40 flex items-center justify-center text-slate-300 shrink-0">
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-slate-100 font-semibold text-sm">{titulo}</div>
        <div className="text-slate-400 text-xs mt-0.5 line-clamp-1">{subtitulo}</div>
      </div>
      <ChevronRight size={18} className="text-slate-500 shrink-0" />
    </button>
  )
}

function TelaCheia({ children }) {
  return (
    <div className="fixed inset-0 bg-slate-900 z-50 flex flex-col items-center justify-center p-4 overflow-auto">
      {children}
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
    <TelaCheia>
      <h2 className="text-lg mb-3 text-center text-white">Digite ou cole a linha digitável</h2>
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
        <button onClick={onVoltar} className="px-4 py-2 border border-slate-700 text-slate-300 rounded">
          Voltar
        </button>
        <button
          onClick={() => onSubmit(valor)}
          disabled={!ok}
          className="px-6 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded"
        >
          Continuar
        </button>
      </div>
    </TelaCheia>
  )
}
