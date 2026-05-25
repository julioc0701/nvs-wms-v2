import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Eye, CheckCircle2, Plus } from 'lucide-react'
import { api } from '../api/client'
import { nomeBanco, urgenciaVencimento } from '../utils/boletoBancos'
import FinanceiroDrawer from '../components/FinanceiroDrawer'
import FinanceiroConfirmDialog from '../components/dialogs/FinanceiroConfirmDialog'

export default function FinanceiroPainel() {
  const navigate = useNavigate()
  const operador = JSON.parse(localStorage.getItem('operator') || 'null')
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768

  useEffect(() => {
    if (!operador || operador.name !== 'Master') navigate('/sessions')
  }, [operador, navigate])

  const [filtros, setFiltros] = useState({
    status: 'registrado',
    vencimento_de: '',
    vencimento_ate: '',
    valor_min: '',
    valor_max: '',
  })
  const [dados, setDados] = useState({ boletos: [], total: 0, valor_total: 0 })
  const [carregando, setCarregando] = useState(false)
  const [selecionado, setSelecionado] = useState(null)
  const [pagarDialog, setPagarDialog] = useState(null)

  async function carregar() {
    setCarregando(true)
    try {
      const r = await api.listarBoletos(filtros)
      setDados(r)
    } finally {
      setCarregando(false)
    }
  }

  useEffect(() => {
    carregar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(filtros)])

  async function confirmarPagar() {
    await api.pagarBoleto(pagarDialog.id, operador.id)
    setPagarDialog(null)
    carregar()
  }

  function abrirDetalhe(boleto) {
    if (isMobile) {
      navigate(`/financeiro/boleto/${boleto.id}`)
    } else {
      setSelecionado(boleto)
    }
  }

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4 md:mb-6">
        <div>
          <h1 className="text-xl md:text-2xl font-bold">Financeiro — Boletos a Pagar</h1>
          <div className="text-sm text-slate-600 mt-1">
            {dados.total} {dados.total === 1 ? 'boleto' : 'boletos'} · R$ {dados.valor_total.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
          </div>
        </div>
        <button
          onClick={() => navigate('/financeiro/scan')}
          className="flex items-center justify-center gap-2 bg-cyan-600 hover:bg-cyan-500 text-white px-4 py-3 rounded-xl font-bold shadow"
        >
          <Plus size={20} /> Adicionar boleto
        </button>
      </div>

      {/* Filtros */}
      <div className="bg-white rounded-lg shadow p-3 md:p-4 mb-4 grid grid-cols-2 md:grid-cols-5 gap-2 md:gap-3 text-sm">
        <select
          value={filtros.status}
          onChange={(e) => setFiltros({ ...filtros, status: e.target.value })}
          className="border rounded p-2 col-span-2 md:col-span-1"
        >
          <option value="">Todos status</option>
          <option value="registrado">Registrados</option>
          <option value="pago">Pagos</option>
        </select>
        <input
          type="date"
          value={filtros.vencimento_de}
          onChange={(e) => setFiltros({ ...filtros, vencimento_de: e.target.value })}
          className="border rounded p-2"
          placeholder="De"
        />
        <input
          type="date"
          value={filtros.vencimento_ate}
          onChange={(e) => setFiltros({ ...filtros, vencimento_ate: e.target.value })}
          className="border rounded p-2"
          placeholder="Até"
        />
        <input
          type="number"
          step="0.01"
          value={filtros.valor_min}
          onChange={(e) => setFiltros({ ...filtros, valor_min: e.target.value })}
          className="border rounded p-2"
          placeholder="R$ mín"
        />
        <input
          type="number"
          step="0.01"
          value={filtros.valor_max}
          onChange={(e) => setFiltros({ ...filtros, valor_max: e.target.value })}
          className="border rounded p-2"
          placeholder="R$ máx"
        />
      </div>

      {/* Lista: tabela desktop, cards mobile */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        {carregando && (
          <div className="p-6 text-center text-slate-500">Carregando…</div>
        )}
        {!carregando && dados.boletos.length === 0 && (
          <div className="p-6 text-center text-slate-500">Nenhum boleto encontrado.</div>
        )}

        {/* Cards no mobile */}
        {!carregando && dados.boletos.length > 0 && (
          <div className="md:hidden divide-y">
            {dados.boletos.map((b) => {
              const urg = urgenciaVencimento(b.vencimento)
              return (
                <button
                  key={b.id}
                  onClick={() => abrirDetalhe(b)}
                  className="w-full text-left p-4 hover:bg-slate-50 active:bg-slate-100 transition-colors"
                >
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <div className="font-semibold text-slate-900 line-clamp-2">
                      {b.beneficiario_razao_social || b.beneficiario_texto || '—'}
                    </div>
                    <div className="font-mono font-bold text-slate-900 whitespace-nowrap">
                      {b.valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-slate-600">
                    <span>Venc. {new Date(b.vencimento + 'T00:00:00').toLocaleDateString('pt-BR')}</span>
                    <span className={`px-2 py-0.5 rounded ${urg.classes}`}>{urg.label}</span>
                    <span className="ml-auto">{b.banco_emissor}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-2">
                    <span className={`px-2 py-0.5 rounded text-xs ${b.status === 'pago' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>
                      {b.status}
                    </span>
                    <span className="text-xs text-slate-500">por {b.capturado_por_nome}</span>
                  </div>
                </button>
              )
            })}
          </div>
        )}

        {/* Tabela no desktop */}
        {!carregando && dados.boletos.length > 0 && (
          <table className="hidden md:table w-full text-sm">
            <thead className="bg-slate-100 text-left">
              <tr>
                <th className="p-3">Empresa</th>
                <th className="p-3 text-right">Valor</th>
                <th className="p-3">Vencimento</th>
                <th className="p-3">Banco</th>
                <th className="p-3">Capturado por</th>
                <th className="p-3">Status</th>
                <th className="p-3">Ações</th>
              </tr>
            </thead>
            <tbody>
              {dados.boletos.map((b) => {
                const urg = urgenciaVencimento(b.vencimento)
                return (
                  <tr key={b.id} className="border-t hover:bg-slate-50">
                    <td className="p-3">{b.beneficiario_razao_social || b.beneficiario_texto || '—'}</td>
                    <td className="p-3 text-right font-mono">
                      {b.valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                    </td>
                    <td className="p-3">
                      {new Date(b.vencimento + 'T00:00:00').toLocaleDateString('pt-BR')}
                      <span className={`ml-2 text-xs px-2 py-0.5 rounded ${urg.classes}`}>
                        {urg.label}
                      </span>
                    </td>
                    <td className="p-3">{b.banco_emissor} · {nomeBanco(b.banco_emissor)}</td>
                    <td className="p-3">{b.capturado_por_nome}</td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded text-xs ${b.status === 'pago' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>
                        {b.status}
                      </span>
                    </td>
                    <td className="p-3 flex gap-2">
                      <button onClick={() => abrirDetalhe(b)} title="Ver detalhe">
                        <Eye size={18} className="text-slate-600 hover:text-cyan-600" />
                      </button>
                      {b.status === 'registrado' && (
                        <button onClick={() => setPagarDialog(b)} title="Marcar como pago">
                          <CheckCircle2 size={18} className="text-slate-600 hover:text-green-600" />
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Drawer só no desktop */}
      {selecionado && (
        <FinanceiroDrawer
          boleto={selecionado}
          onClose={() => setSelecionado(null)}
          onChange={() => { carregar(); setSelecionado(null) }}
        />
      )}

      {/* Dialog de pagar do desktop */}
      {pagarDialog && (
        <FinanceiroConfirmDialog
          titulo="Marcar como pago?"
          iconBg="bg-green-100"
          iconColor="text-green-600"
          icon={<CheckCircle2 size={28} strokeWidth={2.5} />}
          detalhes={
            <>
              <p className="text-gray-500 text-xs uppercase font-bold tracking-wider mb-1">EMPRESA</p>
              <p className="text-xl font-black text-gray-800 mb-4">
                {pagarDialog.beneficiario_razao_social || pagarDialog.beneficiario_texto || '—'}
              </p>
              <div className="grid grid-cols-2 gap-4 border-t border-gray-200 pt-4">
                <div>
                  <p className="text-gray-500 text-xs uppercase font-bold tracking-wider">VALOR</p>
                  <p className="text-lg font-bold text-green-700">
                    {pagarDialog.valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                  </p>
                </div>
                <div>
                  <p className="text-gray-500 text-xs uppercase font-bold tracking-wider">VENCIMENTO</p>
                  <p className="text-lg font-bold text-gray-700">
                    {new Date(pagarDialog.vencimento + 'T00:00:00').toLocaleDateString('pt-BR')}
                  </p>
                </div>
              </div>
            </>
          }
          pergunta="Após confirmar, o boleto sai da lista de pendentes. Você pode reabrir depois pelo painel de detalhe."
          confirmLabel="MARCAR COMO PAGO"
          confirmClasses="bg-green-600 hover:bg-green-700 shadow-green-200"
          onConfirm={confirmarPagar}
          onCancel={() => setPagarDialog(null)}
        />
      )}
    </div>
  )
}
