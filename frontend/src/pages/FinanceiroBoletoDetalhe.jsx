import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Copy, CheckCircle2, RotateCcw, Trash2, Pencil } from 'lucide-react'
import { api } from '../api/client'
import { nomeBanco, urgenciaVencimento } from '../utils/boletoBancos'
import FinanceiroConfirmDialog from '../components/dialogs/FinanceiroConfirmDialog'

/**
 * Detalhe de boleto fullscreen — usado no mobile (sai do flow do drawer
 * lateral do desktop). URL: /financeiro/boleto/:id
 *
 * Carrega via API; ações de editar/pagar/reabrir/excluir reutilizam o
 * dialog estilizado e voltam pra /financeiro depois.
 */
export default function FinanceiroBoletoDetalhe() {
  const navigate = useNavigate()
  const { id } = useParams()
  const operador = JSON.parse(localStorage.getItem('operator') || 'null')

  const [boleto, setBoleto] = useState(null)
  const [carregando, setCarregando] = useState(true)
  const [editando, setEditando] = useState(false)
  const [empresa, setEmpresa] = useState('')
  const [obs, setObs] = useState('')
  const [confirmAcao, setConfirmAcao] = useState(null)
  const [erro, setErro] = useState(null)

  async function carregar() {
    setCarregando(true)
    try {
      const b = await api.detalharBoleto(id)
      setBoleto(b)
      setEmpresa(b.beneficiario_razao_social || b.beneficiario_texto || '')
      setObs(b.observacao || '')
    } catch (e) {
      setErro(e.message)
    } finally {
      setCarregando(false)
    }
  }

  useEffect(() => {
    carregar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  async function salvarEdicao() {
    await api.editarBoleto(boleto.id, { beneficiario_texto: empresa, observacao: obs })
    setEditando(false)
    await carregar()
  }

  async function executarAcao() {
    if (confirmAcao === 'pagar') await api.pagarBoleto(boleto.id, operador.id)
    if (confirmAcao === 'reabrir') await api.reabrirBoleto(boleto.id)
    if (confirmAcao === 'excluir') {
      await api.excluirBoleto(boleto.id)
      setConfirmAcao(null)
      navigate('/financeiro')
      return
    }
    setConfirmAcao(null)
    await carregar()
  }

  function copiarLinha() {
    navigator.clipboard?.writeText(boleto.linha_digitavel)
  }

  if (carregando) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-slate-500">Carregando…</div>
      </div>
    )
  }

  if (erro || !boleto) {
    return (
      <div className="min-h-screen bg-slate-50 p-4">
        <button onClick={() => navigate('/financeiro')} className="text-sm text-slate-600 mb-4 flex items-center gap-2">
          <ArrowLeft size={16} /> Voltar
        </button>
        <div className="bg-red-50 border border-red-200 rounded p-4 text-red-700 text-sm">
          {erro || 'Boleto não encontrado'}
        </div>
      </div>
    )
  }

  const empresaLabel = boleto.beneficiario_razao_social || boleto.beneficiario_texto || '—'
  const valorFmt = boleto.valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
  const vencFmt = new Date(boleto.vencimento + 'T00:00:00').toLocaleDateString('pt-BR')
  const urg = urgenciaVencimento(boleto.vencimento)

  const dialogConfig = {
    pagar: {
      titulo: 'Marcar como pago?',
      iconBg: 'bg-green-100',
      iconColor: 'text-green-600',
      icon: <CheckCircle2 size={28} strokeWidth={2.5} />,
      confirmLabel: 'MARCAR COMO PAGO',
      confirmClasses: 'bg-green-600 hover:bg-green-700 shadow-green-200',
      pergunta: 'O boleto sai da lista de pendentes. Pode ser reaberto depois.',
    },
    reabrir: {
      titulo: 'Reabrir boleto?',
      iconBg: 'bg-amber-100',
      iconColor: 'text-amber-600',
      icon: <RotateCcw size={28} strokeWidth={2.5} />,
      confirmLabel: 'REABRIR',
      confirmClasses: 'bg-amber-600 hover:bg-amber-700 shadow-amber-200',
      pergunta: 'O boleto volta para pendente e some o registro de pagamento.',
    },
    excluir: {
      titulo: 'Excluir boleto?',
      iconBg: 'bg-red-100',
      iconColor: 'text-red-600',
      icon: <Trash2 size={28} strokeWidth={2.5} />,
      confirmLabel: 'EXCLUIR',
      confirmClasses: 'bg-red-600 hover:bg-red-700 shadow-red-200',
      pergunta: 'Esta ação é definitiva. O registro e a foto (se houver) serão removidos.',
    },
  }
  const cfg = confirmAcao ? dialogConfig[confirmAcao] : null

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="sticky top-0 bg-white border-b z-10 px-4 py-3 flex items-center gap-3">
        <button onClick={() => navigate('/financeiro')} className="p-1 -ml-1">
          <ArrowLeft size={22} />
        </button>
        <div className="flex-1">
          <h1 className="text-base font-bold">Boleto #{boleto.id}</h1>
          <span className={`text-xs px-2 py-0.5 rounded ${boleto.status === 'pago' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>
            {boleto.status}
          </span>
        </div>
      </div>

      {/* Conteúdo */}
      <div className="p-4 space-y-4">
        {/* Empresa */}
        <div className="bg-white rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-slate-500 uppercase tracking-wider font-semibold">Empresa</span>
            {!editando && (
              <button onClick={() => setEditando(true)} className="text-cyan-600 text-sm flex items-center gap-1">
                <Pencil size={14} /> Editar
              </button>
            )}
          </div>
          {editando ? (
            <input
              value={empresa}
              onChange={(e) => setEmpresa(e.target.value)}
              className="w-full border rounded p-2 text-lg"
              autoFocus
            />
          ) : (
            <div className="text-xl font-bold text-slate-900">{empresaLabel}</div>
          )}
        </div>

        {/* Valor + Vencimento */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-white rounded-xl p-4 shadow-sm">
            <div className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-1">Valor</div>
            <div className="text-2xl font-bold text-slate-900">{valorFmt}</div>
          </div>
          <div className="bg-white rounded-xl p-4 shadow-sm">
            <div className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-1">Vencimento</div>
            <div className="text-xl font-bold text-slate-900">{vencFmt}</div>
            <span className={`text-xs mt-1 inline-block px-2 py-0.5 rounded ${urg.classes}`}>
              {urg.label}
            </span>
          </div>
        </div>

        {/* Banco */}
        <div className="bg-white rounded-xl p-4 shadow-sm">
          <div className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-1">Banco</div>
          <div className="font-semibold">{boleto.banco_emissor} · {nomeBanco(boleto.banco_emissor)}</div>
        </div>

        {/* Linha digitável */}
        <div className="bg-white rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-slate-500 uppercase tracking-wider font-semibold">Linha digitável</span>
            <button onClick={copiarLinha} className="text-cyan-600 text-sm flex items-center gap-1">
              <Copy size={14} /> Copiar
            </button>
          </div>
          <code className="text-xs break-all text-slate-700 font-mono">{boleto.linha_digitavel}</code>
        </div>

        {/* Observação */}
        <div className="bg-white rounded-xl p-4 shadow-sm">
          <div className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-2">Observação</div>
          {editando ? (
            <textarea
              value={obs}
              onChange={(e) => setObs(e.target.value)}
              className="w-full border rounded p-2"
              rows={3}
            />
          ) : (
            <div className="text-slate-700">{obs || <span className="text-slate-400">—</span>}</div>
          )}
        </div>

        {/* Foto */}
        {boleto.foto_path && (
          <div className="bg-white rounded-xl p-4 shadow-sm">
            <div className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-2">Foto</div>
            <a href={api.fotoBoletoUrl(boleto.id)} target="_blank" rel="noreferrer">
              <img src={api.fotoBoletoUrl(boleto.id)} alt="Boleto" className="w-full rounded border" />
            </a>
          </div>
        )}

        {/* Audit */}
        <div className="bg-white rounded-xl p-4 shadow-sm space-y-2">
          <div>
            <div className="text-xs text-slate-500 uppercase tracking-wider font-semibold">Capturado</div>
            <div className="text-sm">
              {boleto.capturado_por_nome} em {new Date(boleto.capturado_em).toLocaleString('pt-BR')}
            </div>
          </div>
          {boleto.pago_em && (
            <div className="border-t pt-2">
              <div className="text-xs text-slate-500 uppercase tracking-wider font-semibold">Pago</div>
              <div className="text-sm">
                {boleto.pago_por_nome} em {new Date(boleto.pago_em).toLocaleString('pt-BR')}
              </div>
            </div>
          )}
        </div>

        {/* Ações */}
        <div className="space-y-2 pt-2 pb-8">
          {editando ? (
            <div className="flex gap-2">
              <button
                onClick={() => { setEditando(false); setEmpresa(boleto.beneficiario_razao_social || boleto.beneficiario_texto || ''); setObs(boleto.observacao || '') }}
                className="flex-1 py-3 border-2 border-slate-300 text-slate-600 rounded-xl font-bold"
              >
                CANCELAR
              </button>
              <button
                onClick={salvarEdicao}
                className="flex-1 py-3 bg-cyan-600 text-white rounded-xl font-bold shadow"
              >
                SALVAR EDIÇÃO
              </button>
            </div>
          ) : (
            <>
              <button
                onClick={() => setConfirmAcao(boleto.status === 'registrado' ? 'pagar' : 'reabrir')}
                className={`w-full py-3 rounded-xl font-bold text-white shadow ${boleto.status === 'registrado' ? 'bg-green-600 hover:bg-green-700 shadow-green-200' : 'bg-amber-600 hover:bg-amber-700 shadow-amber-200'}`}
              >
                {boleto.status === 'registrado' ? 'MARCAR COMO PAGO' : 'REABRIR'}
              </button>
              <button
                onClick={() => setConfirmAcao('excluir')}
                className="w-full py-3 border-2 border-red-300 text-red-600 rounded-xl font-bold"
              >
                EXCLUIR
              </button>
            </>
          )}
        </div>
      </div>

      {cfg && (
        <FinanceiroConfirmDialog
          {...cfg}
          detalhes={
            <>
              <p className="text-gray-500 text-xs uppercase font-bold tracking-wider mb-1">EMPRESA</p>
              <p className="text-xl font-black text-gray-800 mb-4">{empresaLabel}</p>
              <div className="grid grid-cols-2 gap-4 border-t border-gray-200 pt-4">
                <div>
                  <p className="text-gray-500 text-xs uppercase font-bold tracking-wider">VALOR</p>
                  <p className="text-lg font-bold text-gray-700">{valorFmt}</p>
                </div>
                <div>
                  <p className="text-gray-500 text-xs uppercase font-bold tracking-wider">VENCIMENTO</p>
                  <p className="text-lg font-bold text-gray-700">{vencFmt}</p>
                </div>
              </div>
            </>
          }
          onConfirm={executarAcao}
          onCancel={() => setConfirmAcao(null)}
        />
      )}
    </div>
  )
}
