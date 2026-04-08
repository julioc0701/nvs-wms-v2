import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useFeedback } from '../components/ui/FeedbackProvider'

function TrashIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6M14 11v6" />
      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    </svg>
  )
}

function KeyIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" />
    </svg>
  )
}

export default function OperatorsManagement() {
  const navigate = useNavigate()
  const { askConfirm } = useFeedback()
  const [operators, setOperators] = useState([])
  const [loading, setLoading] = useState(true)

  // Add Operator State
  const [showAdd, setShowAdd] = useState(false)
  const [newName, setNewName] = useState('')
  const [newPin, setNewPin] = useState('')

  // Edit PIN State
  const [editOp, setEditOp] = useState(null)
  const [editPin, setEditPin] = useState('')

  // Error/Success messages
  const [msg, setMsg] = useState({ type: '', text: '' })

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try {
      const ops = await api.getOperators()
      setOperators(ops)
    } catch (err) {
      showMessage('error', err.message || 'Erro ao carregar operadores')
    } finally {
      setLoading(false)
    }
  }

  function showMessage(type, text) {
    setMsg({ type, text })
    setTimeout(() => setMsg({ type: '', text: '' }), 4000)
  }

  async function handleAdd(e) {
    e.preventDefault()
    if (!newName.trim() || !newPin.trim()) return
    try {
      await api.createOperator(newName.trim(), null, newPin.trim())
      setShowAdd(false)
      setNewName('')
      setNewPin('')
      showMessage('success', 'Operador criado com sucesso!')
      load()
    } catch (err) {
      showMessage('error', err.message)
    }
  }

  async function handleUpdatePin(e) {
    e.preventDefault()
    if (!editPin.trim()) return
    try {
      await api.updateOperatorPin(editOp.id, editPin.trim())
      setEditOp(null)
      setEditPin('')
      showMessage('success', 'PIN alterado com sucesso!')
      load()
    } catch (err) {
      showMessage('error', err.message)
    }
  }

  async function handleDelete(op) {
    const accepted = await askConfirm({
      title: 'Excluir operador',
      message: `Tem certeza que deseja excluir permanentemente o operador "${op.name}"?`,
      confirmText: 'Excluir',
      cancelText: 'Cancelar',
      variant: 'danger',
    })
    if (!accepted) return
    try {
      await api.deleteOperator(op.id)
      showMessage('success', `Operador ${op.name} removido.`)
      load()
    } catch (err) {
      showMessage('error', err.message)
    }
  }

  return (
    <div className="min-h-screen bg-gray-100 p-8 max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-4xl font-bold">Gestão de Operadores</h1>
          <p className="text-gray-500 mt-2">Adicione ou remova permissões de login com PIN</p>
        </div>
        <button onClick={() => navigate('/supervisor')} className="text-blue-500 hover:underline text-lg">
          ← Voltar pro Painel
        </button>
      </div>

      {msg.text && (
        <div className={`mb-6 p-4 rounded-xl text-lg font-medium text-center ${msg.type === 'error' ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
          {msg.text}
        </div>
      )}

      {/* Main Card */}
      <div className="bg-white rounded-2xl shadow overflow-hidden">
        <div className="p-6 border-b border-gray-100 flex justify-between items-center bg-gray-50">
          <h2 className="text-2xl font-bold text-gray-800">Operadores Ativos ({operators.length})</h2>
          <button
            onClick={() => setShowAdd(true)}
            className="px-5 py-2.5 bg-blue-600 text-white rounded-xl font-bold hover:bg-blue-700 transition-colors shadow-sm"
          >
            ➕ Novo Operador
          </button>
        </div>

        {loading ? (
          <p className="text-center py-12 text-gray-400">Carregando operadores...</p>
        ) : operators.length === 0 ? (
          <p className="text-center py-12 text-gray-400">Nenhum operador cadastrado.</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {operators.map(op => (
              <li key={op.id} className="p-6 flex items-center justify-between hover:bg-gray-50 transition-colors">
                <div>
                  <h3 className="text-xl font-bold text-gray-800">{op.name}</h3>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-sm font-mono text-gray-500 bg-gray-100 px-2 py-0.5 rounded">ID: {op.id}</span>
                    <span className="text-sm text-gray-400">PIN: ****</span>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <button
                    onClick={() => setEditOp(op)}
                    className="flex items-center gap-2 px-4 py-2 text-blue-600 font-semibold bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors"
                    title="Alterar Senha"
                  >
                    <KeyIcon /> Resetar PIN
                  </button>
                  <button
                    onClick={() => handleDelete(op)}
                    className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                    title="Excluir Operador"
                  >
                    <TrashIcon />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Add Modal */}
      {showAdd && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-3xl shadow-2xl p-8 max-w-sm w-full">
            <h2 className="text-2xl font-bold text-center mb-6">Novo Operador</h2>
            <form onSubmit={handleAdd} className="flex flex-col gap-5">
              <div>
                <label className="block text-sm font-bold text-gray-700 mb-1 uppercase tracking-wider">Nome Completo</label>
                <input
                  type="text"
                  required autoFocus
                  value={newName}
                  onChange={e => setNewName(e.target.value)}
                  className="w-full text-lg border-2 border-gray-200 focus:border-blue-500 rounded-xl p-3 outline-none"
                  placeholder="Ex: João Silva"
                />
              </div>
              <div>
                <label className="block text-sm font-bold text-gray-700 mb-1 uppercase tracking-wider">PIN (Senha)</label>
                <input
                  type="number"
                  required
                  value={newPin}
                  onChange={e => setNewPin(e.target.value)}
                  className="w-full text-2xl tracking-widest text-center border-2 border-gray-200 focus:border-blue-500 rounded-xl p-3 outline-none font-mono font-bold"
                  placeholder="1234"
                />
              </div>
              <div className="grid grid-cols-2 gap-3 mt-4">
                <button type="button" onClick={() => setShowAdd(false)} className="py-3 rounded-xl border-2 border-gray-200 font-bold text-gray-600 hover:bg-gray-50">
                  CANCELAR
                </button>
                <button type="submit" className="py-3 rounded-xl bg-blue-600 font-bold text-white hover:bg-blue-700">
                  SALVAR
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit PIN Modal */}
      {editOp && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-3xl shadow-2xl p-8 max-w-sm w-full">
            <h2 className="text-2xl font-bold text-center mb-2">Resetar Senha</h2>
            <p className="text-center text-gray-500 mb-6 font-medium">Operador: <span className="text-gray-800">{editOp.name}</span></p>
            
            <form onSubmit={handleUpdatePin} className="flex flex-col gap-6">
              <div>
                <label className="block text-sm font-bold text-gray-700 mb-1 uppercase tracking-wider">Novo PIN</label>
                <input
                  type="number"
                  required autoFocus
                  value={editPin}
                  onChange={e => setEditPin(e.target.value)}
                  className="w-full text-3xl tracking-widest text-center border-2 border-gray-300 focus:border-blue-500 rounded-xl p-4 outline-none font-mono font-bold"
                  placeholder="****"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <button type="button" onClick={() => setEditOp(null)} className="py-3 rounded-xl border-2 border-gray-200 font-bold text-gray-600 hover:bg-gray-50">
                  CANCELAR
                </button>
                <button type="submit" className="py-3 rounded-xl bg-blue-600 font-bold text-white hover:bg-blue-700">
                  ALTERAR
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
