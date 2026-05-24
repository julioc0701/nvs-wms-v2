import { useState } from 'react'
import { X, Copy } from 'lucide-react'
import { api } from '../api/client'
import { nomeBanco } from '../utils/boletoBancos'

export default function FinanceiroDrawer({ boleto, onClose, onChange }) {
  const operador = JSON.parse(localStorage.getItem('operator') || 'null')
  const [editando, setEditando] = useState(false)
  const [empresa, setEmpresa] = useState(boleto.beneficiario_razao_social || boleto.beneficiario_texto || '')
  const [obs, setObs] = useState(boleto.observacao || '')

  async function salvar() {
    await api.editarBoleto(boleto.id, { beneficiario_texto: empresa, observacao: obs })
    onChange()
  }

  async function togglePago() {
    if (boleto.status === 'registrado') {
      await api.pagarBoleto(boleto.id, operador.id)
    } else {
      await api.reabrirBoleto(boleto.id)
    }
    onChange()
  }

  async function excluir() {
    if (!confirm('Excluir definitivamente este boleto?')) return
    await api.excluirBoleto(boleto.id)
    onChange()
  }

  function copiarLinha() {
    navigator.clipboard?.writeText(boleto.linha_digitavel)
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-40 flex justify-end" onClick={onClose}>
      <div
        className="bg-white w-full max-w-md h-full overflow-auto shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="font-bold">Boleto #{boleto.id}</h2>
          <button onClick={onClose}><X size={20} /></button>
        </div>

        <div className="p-4 space-y-4 text-sm">
          <Campo label="Empresa">
            {editando ? (
              <input value={empresa} onChange={(e) => setEmpresa(e.target.value)} className="w-full border rounded p-2" />
            ) : (
              empresa || '—'
            )}
          </Campo>

          <Campo label="Valor">
            {boleto.valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
          </Campo>

          <Campo label="Vencimento">
            {new Date(boleto.vencimento + 'T00:00:00').toLocaleDateString('pt-BR')}
          </Campo>

          <Campo label="Banco">
            {boleto.banco_emissor} · {nomeBanco(boleto.banco_emissor)}
          </Campo>

          <Campo label="Linha digitável">
            <div className="flex items-center gap-2">
              <code className="text-xs break-all">{boleto.linha_digitavel}</code>
              <button onClick={copiarLinha} title="Copiar"><Copy size={14} /></button>
            </div>
          </Campo>

          <Campo label="Observação">
            {editando ? (
              <textarea value={obs} onChange={(e) => setObs(e.target.value)} className="w-full border rounded p-2" rows={3} />
            ) : (
              obs || '—'
            )}
          </Campo>

          {boleto.foto_path && (
            <Campo label="Foto">
              <a href={api.fotoBoletoUrl(boleto.id)} target="_blank" rel="noreferrer">
                <img src={api.fotoBoletoUrl(boleto.id)} alt="Boleto" className="w-full rounded border" />
              </a>
            </Campo>
          )}

          <Campo label="Capturado">
            {boleto.capturado_por_nome} em {new Date(boleto.capturado_em).toLocaleString('pt-BR')}
          </Campo>

          {boleto.pago_em && (
            <Campo label="Pago">
              {boleto.pago_por_nome} em {new Date(boleto.pago_em).toLocaleString('pt-BR')}
            </Campo>
          )}
        </div>

        <div className="p-4 border-t flex flex-wrap gap-2">
          {!editando ? (
            <button onClick={() => setEditando(true)} className="px-4 py-2 border rounded text-sm">Editar</button>
          ) : (
            <button onClick={salvar} className="px-4 py-2 bg-cyan-600 text-white rounded text-sm">Salvar edição</button>
          )}
          <button
            onClick={togglePago}
            className={`px-4 py-2 rounded text-sm text-white ${boleto.status === 'registrado' ? 'bg-green-600' : 'bg-amber-600'}`}
          >
            {boleto.status === 'registrado' ? 'Marcar como pago' : 'Reabrir'}
          </button>
          <button onClick={excluir} className="px-4 py-2 bg-red-600 text-white rounded text-sm ml-auto">
            Excluir
          </button>
        </div>
      </div>
    </div>
  )
}

function Campo({ label, children }) {
  return (
    <div>
      <div className="text-xs uppercase text-slate-500 mb-1">{label}</div>
      <div>{children}</div>
    </div>
  )
}
