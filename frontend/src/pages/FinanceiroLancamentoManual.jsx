import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Plus, Camera, FileText, Wallet } from 'lucide-react'
import { api } from '../api/client'

/**
 * Lançamento manual — usado pra registrar pagamentos sem boleto bancário
 * (despesa, PIX fornecedor, taxa, etc.). Acessado via /financeiro/lancamento-manual.
 *
 * Campos:
 *   - Categoria (dropdown com opção "+ Nova categoria" inline)
 *   - Empresa/fornecedor (texto livre)
 *   - Valor
 *   - Vencimento
 *   - Chave PIX (se categoria for de PIX)
 *   - Descrição (opcional)
 *   - Anexo (foto ou PDF do comprovante, opcional)
 */
export default function FinanceiroLancamentoManual() {
  const navigate = useNavigate()
  const operador = JSON.parse(localStorage.getItem('operator') || 'null')

  const [categorias, setCategorias] = useState([])
  const [categoriaId, setCategoriaId] = useState(null)
  const [criandoCategoria, setCriandoCategoria] = useState(false)
  const [nomeNovaCategoria, setNomeNovaCategoria] = useState('')
  const [empresa, setEmpresa] = useState('')
  const [valor, setValor] = useState('')
  const [vencimento, setVencimento] = useState('')
  const [chavePix, setChavePix] = useState('')
  const [descricao, setDescricao] = useState('')
  const [observacao, setObservacao] = useState('')
  const [anexoB64, setAnexoB64] = useState(null)
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState(null)
  const anexoInputRef = useRef(null)

  useEffect(() => {
    api.listarCategorias().then(setCategorias).catch(() => {})
  }, [])

  const categoriaSelecionada = categorias.find((c) => c.id === categoriaId)
  const isPix = categoriaSelecionada?.nome?.toLowerCase().includes('pix')

  async function comprimirAnexo(file) {
    if (file.type === 'application/pdf') {
      // PDFs não comprime — converte direto pra base64
      return new Promise((resolve) => {
        const reader = new FileReader()
        reader.onload = (e) => resolve(e.target.result)
        reader.readAsDataURL(file)
      })
    }
    // Imagem: comprime
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

  async function criarNovaCategoria() {
    if (!nomeNovaCategoria.trim()) return
    try {
      const nova = await api.criarCategoria({
        nome: nomeNovaCategoria.trim(),
        criada_por: operador?.id,
      })
      setCategorias([...categorias, { ...nova, ativa: true }].sort((a, b) => a.ordem - b.ordem))
      setCategoriaId(nova.id)
      setCriandoCategoria(false)
      setNomeNovaCategoria('')
    } catch (e) {
      setErro(e.message)
    }
  }

  async function salvar() {
    setErro(null)
    if (!categoriaId) return setErro('Escolha uma categoria')
    if (!empresa.trim()) return setErro('Informe a empresa/fornecedor')
    const valorNum = parseFloat(valor.replace(',', '.'))
    if (!valorNum || valorNum <= 0) return setErro('Valor inválido')
    if (!vencimento) return setErro('Informe o vencimento')

    setSalvando(true)
    try {
      await api.criarLancamentoManual({
        operator_id: operador.id,
        categoria_id: categoriaId,
        beneficiario_texto: empresa.trim(),
        valor: valorNum,
        vencimento,
        chave_pix: chavePix.trim() || null,
        descricao: descricao.trim() || null,
        observacao: observacao.trim() || null,
        foto_base64: anexoB64,
      })
      navigate('/financeiro')
    } catch (e) {
      setErro(e.message)
    } finally {
      setSalvando(false)
    }
  }

  return (
    <div className="min-h-screen md:grid md:grid-cols-2">
      {/* ── ESQUERDA: identidade visual (só desktop) ────────────────────────── */}
      <aside
        className="hidden md:flex relative overflow-hidden flex-col justify-between p-12 text-white"
        style={{
          background:
            'linear-gradient(135deg, #1e3a8a 0%, #2563eb 50%, #38bdf8 100%)',
        }}
      >
        <div className="absolute -right-20 -top-20 w-72 h-72 rounded-full bg-white/10" />
        <div className="absolute -left-10 bottom-10 w-48 h-48 rounded-full bg-white/5" />

        <button
          onClick={() => navigate('/financeiro/scan')}
          className="relative z-10 flex items-center gap-2 text-white/80 hover:text-white text-sm font-semibold w-fit"
        >
          <ArrowLeft size={18} /> Voltar
        </button>

        <div className="relative z-10 space-y-5 max-w-md">
          <div className="w-14 h-14 rounded-2xl bg-white/15 backdrop-blur flex items-center justify-center">
            <Wallet size={28} />
          </div>
          <div>
            <h1 className="text-4xl font-black tracking-tight mb-3">
              Novo lançamento manual
            </h1>
            <p className="text-blue-100/90 text-base leading-relaxed">
              Registre despesas, PIX para fornecedor ou funcionário,
              taxas, reembolsos, contas de consumo e qualquer outro
              pagamento que não tenha boleto bancário.
            </p>
          </div>
          <div className="pt-4 space-y-2 text-sm text-blue-100/70">
            <p>📎 Anexe foto ou PDF do comprovante</p>
            <p>🏷️ Categorize automaticamente</p>
            <p>📊 Aparece junto dos boletos no painel</p>
          </div>
        </div>

        <p className="relative z-10 text-xs text-blue-100/50">
          NVS · Módulo Financeiro
        </p>
      </aside>

      {/* ── DIREITA (desktop) / ÚNICA (mobile) ─────────────────────────────── */}
      <main
        className="min-h-screen md:bg-white"
        style={{
          background: 'linear-gradient(135deg, #ffffff 0%, #60a5fa 35%, #1e3a8a 100%)',
        }}
      >
        {/* Header mobile (só aparece em mobile) */}
        <div className="md:hidden sticky top-0 bg-white/85 backdrop-blur border-b border-slate-200 z-10 px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate('/financeiro/scan')} className="p-1 -ml-1">
            <ArrowLeft size={22} />
          </button>
          <h1 className="text-base font-bold flex-1">Novo lançamento manual</h1>
        </div>

        <div className="p-4 md:p-12 max-w-md md:max-w-lg mx-auto md:mx-0">
          <div className="bg-white rounded-2xl shadow-xl shadow-blue-900/10 p-5 md:p-0 md:shadow-none md:bg-transparent space-y-4">
        {/* Categoria */}
        <div>
          <label className="text-sm font-semibold text-slate-700 mb-1 block">
            Categoria <span className="text-red-500">*</span>
          </label>
          {!criandoCategoria ? (
            <>
              <select
                value={categoriaId || ''}
                onChange={(e) => {
                  if (e.target.value === '__nova__') {
                    setCriandoCategoria(true)
                  } else {
                    setCategoriaId(parseInt(e.target.value))
                  }
                }}
                className="w-full p-3 border-2 border-slate-300 focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100 outline-none rounded-lg text-base bg-white transition-colors"
              >
                <option value="">— Escolha —</option>
                {categorias.map((c) => (
                  <option key={c.id} value={c.id}>{c.nome}</option>
                ))}
                <option value="__nova__">＋ Nova categoria…</option>
              </select>
            </>
          ) : (
            <div className="flex gap-2">
              <input
                value={nomeNovaCategoria}
                onChange={(e) => setNomeNovaCategoria(e.target.value)}
                className="flex-1 p-3 border-2 border-slate-300 focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100 outline-none rounded-lg bg-white transition-colors"
                placeholder="Nome da categoria"
                autoFocus
              />
              <button
                onClick={criarNovaCategoria}
                className="px-4 py-2 bg-cyan-600 text-white rounded-lg font-bold"
              >
                Criar
              </button>
              <button
                onClick={() => { setCriandoCategoria(false); setNomeNovaCategoria('') }}
                className="px-3 py-2 text-slate-500"
              >
                ✕
              </button>
            </div>
          )}
        </div>

        {/* Empresa */}
        <div>
          <label className="text-sm font-semibold text-slate-700 mb-1 block">
            Empresa / fornecedor <span className="text-red-500">*</span>
          </label>
          <input
            value={empresa}
            onChange={(e) => setEmpresa(e.target.value)}
            className="w-full p-3 border-2 border-slate-300 focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100 outline-none rounded-lg text-base bg-white transition-colors"
            placeholder="Ex: João da Silva, Energisa, Imobiliária X"
          />
        </div>

        {/* Valor + Vencimento */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-sm font-semibold text-slate-700 mb-1 block">
              Valor (R$) <span className="text-red-500">*</span>
            </label>
            <input
              value={valor}
              onChange={(e) => setValor(e.target.value)}
              className="w-full p-3 border-2 border-slate-300 focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100 outline-none rounded-lg text-base bg-white transition-colors"
              placeholder="0,00"
              inputMode="decimal"
            />
          </div>
          <div>
            <label className="text-sm font-semibold text-slate-700 mb-1 block">
              Vencimento <span className="text-red-500">*</span>
            </label>
            <input
              type="date"
              value={vencimento}
              onChange={(e) => setVencimento(e.target.value)}
              className="w-full p-3 border-2 border-slate-300 focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100 outline-none rounded-lg text-base bg-white transition-colors"
            />
          </div>
        </div>

        {/* Chave PIX (só pra PIX) */}
        {isPix && (
          <div>
            <label className="text-sm font-semibold text-slate-700 mb-1 block">
              Chave PIX
            </label>
            <input
              value={chavePix}
              onChange={(e) => setChavePix(e.target.value)}
              className="w-full p-3 border-2 border-slate-300 focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100 outline-none rounded-lg text-base bg-white transition-colors"
              placeholder="CPF, CNPJ, e-mail, celular ou chave aleatória"
            />
          </div>
        )}

        {/* Descrição */}
        <div>
          <label className="text-sm font-semibold text-slate-700 mb-1 block">
            Descrição
          </label>
          <input
            value={descricao}
            onChange={(e) => setDescricao(e.target.value)}
            className="w-full p-3 border-2 border-slate-300 focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100 outline-none rounded-lg text-base bg-white transition-colors"
            placeholder="Ex: Conta de luz mai/26, Reembolso almoço cliente"
          />
        </div>

        {/* Observação */}
        <div>
          <label className="text-sm font-semibold text-slate-700 mb-1 block">
            Observação
          </label>
          <textarea
            value={observacao}
            onChange={(e) => setObservacao(e.target.value)}
            className="w-full p-3 border-2 border-slate-300 focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100 outline-none rounded-lg text-base bg-white transition-colors"
            rows={2}
          />
        </div>

        {/* Anexo */}
        <div>
          <label className="text-sm font-semibold text-slate-700 mb-1 block">
            Anexo (foto ou PDF do comprovante)
          </label>
          <input
            ref={anexoInputRef}
            type="file"
            accept="image/*,application/pdf"
            onChange={async (e) => {
              const f = e.target.files?.[0]
              if (f) setAnexoB64(await comprimirAnexo(f))
              e.target.value = ''
            }}
            className="hidden"
          />
          <button
            onClick={() => anexoInputRef.current?.click()}
            className="w-full p-3 border-2 border-dashed border-slate-400 rounded-lg text-sm text-slate-600 hover:bg-slate-50 bg-white transition-colors flex items-center justify-center gap-2"
          >
            {anexoB64 ? (
              <>✓ Anexo carregado — clique para trocar</>
            ) : (
              <><Camera size={16} /> / <FileText size={16} /> Anexar comprovante</>
            )}
          </button>
        </div>

        {erro && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">
            {erro}
          </div>
        )}

        {/* Salvar */}
        <button
          onClick={salvar}
          disabled={salvando}
          className="w-full py-4 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-400 text-white rounded-xl font-bold text-base shadow"
        >
          {salvando ? 'Salvando…' : 'Salvar lançamento'}
        </button>
        </div>
        </div>
      </main>
    </div>
  )
}
