import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { nomeBanco, urgenciaVencimento } from '../utils/boletoBancos'

export default function FinanceiroConfirmar() {
  const navigate = useNavigate()
  const [dados, setDados] = useState(null)
  const [codigo, setCodigo] = useState('')
  const [empresa, setEmpresa] = useState('')
  const [observacao, setObservacao] = useState('')
  const [fotoB64, setFotoB64] = useState(null)
  const [sugestoes, setSugestoes] = useState([])
  const [duplicata, setDuplicata] = useState(null)
  const [salvando, setSalvando] = useState(false)
  const fileInputRef = useRef(null)

  useEffect(() => {
    const dadosStr = sessionStorage.getItem('boletoScanResult')
    const codStr = sessionStorage.getItem('boletoScanCodigo')
    if (!dadosStr) {
      navigate('/financeiro/scan')
      return
    }
    const d = JSON.parse(dadosStr)
    setDados(d)
    setCodigo(codStr || d.codigo_barras)
    // Prioridade pra pré-preencher empresa:
    //   1. Beneficiário sugerido (aprendizado prévio) — confiança alta
    //   2. Beneficiário extraído pela IA/PDF — auto-detectado nessa captura
    if (d.beneficiario_sugerido) {
      setEmpresa(d.beneficiario_sugerido.razao_social)
    } else if (d.beneficiario_extraido) {
      setEmpresa(d.beneficiario_extraido)
    }
    if (d.duplicata) setDuplicata(d.duplicata)
  }, [navigate])

  async function buscarSugestoes(q) {
    setEmpresa(q)
    if (q.length < 2) {
      setSugestoes([])
      return
    }
    const r = await api.listarBeneficiarios(q)
    setSugestoes(r)
  }

  async function comprimirFoto(file) {
    return new Promise((resolve) => {
      const img = new Image()
      const reader = new FileReader()
      reader.onload = (e) => {
        img.onload = () => {
          const canvas = document.createElement('canvas')
          const maxLado = 1200
          const escala = Math.min(1, maxLado / Math.max(img.width, img.height))
          canvas.width = img.width * escala
          canvas.height = img.height * escala
          canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height)
          resolve(canvas.toDataURL('image/jpeg', 0.75))
        }
        img.src = e.target.result
      }
      reader.readAsDataURL(file)
    })
  }

  async function salvar() {
    if (!empresa.trim()) {
      alert('Informe a empresa')
      return
    }
    if (duplicata) {
      alert('Este boleto já foi registrado.')
      return
    }
    setSalvando(true)
    try {
      const op = JSON.parse(localStorage.getItem('operator') || 'null')
      if (!op) throw new Error('Faça login antes')
      await api.criarBoleto({
        codigo_ou_linha: codigo,
        operator_id: op.id,
        beneficiario_texto: empresa.trim(),
        observacao: observacao || null,
        foto_base64: fotoB64,
      })
      sessionStorage.removeItem('boletoScanResult')
      sessionStorage.removeItem('boletoScanCodigo')
      navigate('/financeiro')
    } catch (e) {
      alert(`Erro: ${e.message}`)
    } finally {
      setSalvando(false)
    }
  }

  if (!dados) return null
  const urg = urgenciaVencimento(dados.vencimento)

  return (
    <div className="min-h-screen bg-slate-50 p-4">
      <button onClick={() => navigate('/financeiro/scan')} className="text-sm text-slate-600 mb-4">
        ← Voltar ao scan
      </button>
      <h1 className="text-xl font-bold mb-4">Confirmar boleto</h1>

      {duplicata && (
        <div className="bg-red-50 border-2 border-red-300 rounded-2xl p-4 mb-4">
          <div className="flex items-center gap-3 mb-1">
            <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center text-red-600 shrink-0 text-xl">
              ⚠
            </div>
            <h2 className="text-lg font-bold text-red-700">Este boleto já consta registrado</h2>
          </div>
          <p className="text-sm text-red-700/80 ml-13">
            Capturado em {new Date(duplicata.capturado_em).toLocaleString('pt-BR')}.
            Não é possível salvar a mesma cobrança duas vezes.
          </p>
        </div>
      )}
      {dados.dv_ok === false && (
        <div className="bg-orange-100 border border-orange-300 rounded p-3 mb-4 text-sm">
          ⚠ DV do código não bate — pode ser typo ou erro de leitura. Confira valor e vencimento antes de salvar.
        </div>
      )}

      <div className="bg-white rounded-lg shadow p-4 mb-4 space-y-3">
        <Linha label="Banco" valor={`${dados.banco} — ${nomeBanco(dados.banco)}`} />
        <Linha
          label="Valor"
          valor={dados.valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
        />
        <Linha
          label="Vencimento"
          valor={
            <>
              {new Date(dados.vencimento + 'T00:00:00').toLocaleDateString('pt-BR')}{' '}
              <span className={`text-xs ml-2 px-2 py-0.5 rounded ${urg.classes}`}>
                {urg.label}
              </span>
            </>
          }
        />
      </div>

      <div className="space-y-3">
        <div className="relative">
          <label className="text-sm text-slate-600 flex items-center gap-2">
            Empresa
            {dados.beneficiario_extraido && !dados.beneficiario_sugerido && (
              <span className="text-xs bg-cyan-100 text-cyan-700 px-2 py-0.5 rounded">
                ✨ auto-detectado, confira
              </span>
            )}
            {dados.beneficiario_sugerido && (
              <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">
                ↺ usado anteriormente
              </span>
            )}
          </label>
          <input
            value={empresa}
            onChange={(e) => buscarSugestoes(e.target.value)}
            className="w-full mt-1 p-2 border rounded"
            placeholder="Razão social"
          />
          {sugestoes.length > 0 && (
            <ul className="absolute z-10 bg-white border w-full mt-1 rounded shadow max-h-48 overflow-auto">
              {sugestoes.map((s) => (
                <li
                  key={s.id}
                  onClick={() => { setEmpresa(s.razao_social); setSugestoes([]) }}
                  className="p-2 hover:bg-slate-100 cursor-pointer text-sm"
                >
                  {s.razao_social}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <label className="text-sm text-slate-600">Observação (opcional)</label>
          <textarea
            value={observacao}
            onChange={(e) => setObservacao(e.target.value)}
            className="w-full mt-1 p-2 border rounded"
            rows={2}
          />
        </div>

        <div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            onChange={async (e) => {
              const f = e.target.files?.[0]
              if (f) setFotoB64(await comprimirFoto(f))
            }}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="px-4 py-2 border rounded text-sm"
          >
            {fotoB64 ? '✓ Foto anexada — trocar' : 'Anexar foto (opcional)'}
          </button>
        </div>

        <button
          onClick={salvar}
          disabled={salvando || !!duplicata}
          className="w-full py-3 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-400 text-white rounded font-medium"
        >
          {salvando ? 'Salvando…' : 'Salvar'}
        </button>
      </div>
    </div>
  )
}

function Linha({ label, valor }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-sm text-slate-600">{label}</span>
      <span className="font-medium">{valor}</span>
    </div>
  )
}
