import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useFeedback } from '../components/ui/FeedbackProvider'

// ── Modal de edição ──────────────────────────────────────────────────────────

function EditModal({ product, onClose, onSaved }) {
  const [description, setDescription] = useState(product.description || '')
  const [barcodes, setBarcodes] = useState(product.barcodes || [])
  const [newBarcode, setNewBarcode] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const inputRef = useRef()

  useEffect(() => { inputRef.current?.focus() }, [])

  async function handleSaveDescription() {
    setSaving(true)
    setError(null)
    try {
      await api.updateProduct(product.sku, description || null)
      onSaved()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleAddBarcode() {
    const bc = newBarcode.trim()
    if (!bc) return
    setSaving(true)
    setError(null)
    try {
      await api.addBarcodeToProduct(product.sku, bc)
      setNewBarcode('')
      setBarcodes(prev => [...prev, { barcode: bc, is_primary: true, learned: false }])
      onSaved()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleRemoveBarcode(barcode) {
    setSaving(true)
    setError(null)
    try {
      await api.removeBarcodeFromProduct(product.sku, barcode)
      setBarcodes(prev => prev.filter(b => b.barcode !== barcode))
      onSaved()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onKeyDown={e => e.key === 'Escape' && onClose()}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg overflow-y-auto max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div>
            <p className="text-xs text-gray-400 uppercase tracking-wide font-semibold">Editando produto</p>
            <h2 className="text-xl font-bold font-mono">{product.sku}</h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-2xl leading-none">&times;</button>
        </div>

        <div className="px-6 py-5 flex flex-col gap-5">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-2 text-sm">{error}</div>
          )}

          {/* Descrição */}
          <div>
            <label className="block text-sm font-semibold text-gray-600 mb-1">Descrição</label>
            <div className="flex gap-2">
              <input
                ref={inputRef}
                type="text"
                value={description}
                onChange={e => setDescription(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSaveDescription()}
                placeholder="Ex: Caixa de Papelão 40x30x20"
                className="flex-1 border-2 border-gray-200 focus:border-blue-400 rounded-xl px-3 py-2 text-sm outline-none transition-colors"
              />
              <button
                onClick={handleSaveDescription}
                disabled={saving}
                className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold px-4 py-2 rounded-xl text-sm transition-colors"
              >
                Salvar
              </button>
            </div>
          </div>

          {/* Códigos de barras */}
          <div>
            <label className="block text-sm font-semibold text-gray-600 mb-2">Códigos de Barras</label>
            <div className="flex flex-wrap gap-2 mb-3 min-h-[36px]">
              {barcodes.filter(b => b.barcode !== product.sku).map(bc => (
                <span
                  key={bc.barcode}
                  className={`flex items-center gap-1 font-mono text-xs px-2 py-1 rounded-lg ${
                    bc.learned ? 'bg-blue-50 text-blue-700 border border-blue-200' : 'bg-gray-100 text-gray-700'
                  }`}
                >
                  {bc.barcode}
                  <button
                    onClick={() => handleRemoveBarcode(bc.barcode)}
                    disabled={saving}
                    className="ml-1 text-gray-400 hover:text-red-500 font-bold leading-none disabled:opacity-50"
                    title="Remover código"
                  >
                    &times;
                  </button>
                </span>
              ))}
              {barcodes.filter(b => b.barcode !== product.sku).length === 0 && (
                <span className="text-xs text-gray-400 italic">Nenhum código cadastrado</span>
              )}
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                value={newBarcode}
                onChange={e => setNewBarcode(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleAddBarcode()}
                placeholder="Novo código de barras (EAN)"
                className="flex-1 border-2 border-gray-200 focus:border-green-400 rounded-xl px-3 py-2 text-sm outline-none transition-colors font-mono"
              />
              <button
                onClick={handleAddBarcode}
                disabled={saving || !newBarcode.trim()}
                className="bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white font-semibold px-4 py-2 rounded-xl text-sm transition-colors"
              >
                + Adicionar
              </button>
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-t flex justify-end">
          <button onClick={onClose} className="px-5 py-2 rounded-xl border-2 border-gray-200 hover:bg-gray-50 text-sm font-medium transition-colors">
            Fechar
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Modal de novo produto ─────────────────────────────────────────────────────

function NewProductModal({ onClose, onSaved }) {
  const [sku, setSku] = useState('')
  const [description, setDescription] = useState('')
  const [barcodeInput, setBarcodeInput] = useState('')
  const [barcodes, setBarcodes] = useState([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const skuRef = useRef()

  useEffect(() => { skuRef.current?.focus() }, [])

  function addBarcode() {
    const bc = barcodeInput.trim()
    if (!bc || barcodes.includes(bc)) return
    setBarcodes(prev => [...prev, bc])
    setBarcodeInput('')
  }

  async function handleSave() {
    if (!sku.trim()) { setError('SKU obrigatório'); return }
    setSaving(true)
    setError(null)
    try {
      await api.createProduct(sku.trim(), description.trim() || null, barcodes)
      onSaved()
      onClose()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onKeyDown={e => e.key === 'Escape' && onClose()}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg overflow-y-auto max-h-[90vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-xl font-bold">Novo Produto</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-2xl leading-none">&times;</button>
        </div>

        <div className="px-6 py-5 flex flex-col gap-4">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-2 text-sm">{error}</div>
          )}

          <div>
            <label className="block text-sm font-semibold text-gray-600 mb-1">SKU <span className="text-red-500">*</span></label>
            <input
              ref={skuRef}
              type="text"
              value={sku}
              onChange={e => setSku(e.target.value.toUpperCase())}
              placeholder="Ex: PROD-001"
              className="w-full border-2 border-gray-200 focus:border-blue-400 rounded-xl px-3 py-2 text-sm outline-none transition-colors font-mono"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-600 mb-1">Descrição</label>
            <input
              type="text"
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Ex: Caixa de Papelão 40x30x20"
              className="w-full border-2 border-gray-200 focus:border-blue-400 rounded-xl px-3 py-2 text-sm outline-none transition-colors"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-600 mb-2">Códigos de Barras (EAN)</label>
            <div className="flex flex-wrap gap-2 mb-2 min-h-[32px]">
              {barcodes.map(bc => (
                <span key={bc} className="flex items-center gap-1 bg-gray-100 text-gray-700 font-mono text-xs px-2 py-1 rounded-lg">
                  {bc}
                  <button onClick={() => setBarcodes(p => p.filter(b => b !== bc))} className="text-gray-400 hover:text-red-500 font-bold leading-none">&times;</button>
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                value={barcodeInput}
                onChange={e => setBarcodeInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addBarcode()}
                placeholder="Digite o EAN e pressione Enter"
                className="flex-1 border-2 border-gray-200 focus:border-green-400 rounded-xl px-3 py-2 text-sm outline-none transition-colors font-mono"
              />
              <button
                onClick={addBarcode}
                disabled={!barcodeInput.trim()}
                className="bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white font-semibold px-4 py-2 rounded-xl text-sm transition-colors"
              >
                +
              </button>
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-t flex gap-3 justify-end">
          <button onClick={onClose} className="px-5 py-2 rounded-xl border-2 border-gray-200 hover:bg-gray-50 text-sm font-medium transition-colors">
            Cancelar
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !sku.trim()}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold px-6 py-2 rounded-xl text-sm transition-colors"
          >
            {saving ? 'Salvando...' : 'Criar Produto'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Página principal ──────────────────────────────────────────────────────────

export default function MasterData() {
  const navigate = useNavigate()
  const { notify } = useFeedback()
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [editProduct, setEditProduct] = useState(null)
  const [showNew, setShowNew] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const timerRef = useRef(null)

  useEffect(() => { load('') }, [])

  async function load(q) {
    setLoading(true)
    try {
      const res = await api.listBarcodes(q)
      if (Array.isArray(res)) {
        setItems(res.filter(b => b.is_primary !== false))
        setTotal(res.filter(b => b.is_primary !== false).length)
      } else {
        setItems(res.items || [])
        setTotal(res.total ?? res.results ?? 0)
      }
    } catch {
      setItems([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  function handleSearch(e) {
    const v = e.target.value
    setSearch(v)
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => load(v), 350)
  }

  async function handleDelete(sku) {
    setDeleting(true)
    try {
      await api.deleteProduct(sku)
      setDeleteConfirm(null)
      load(search)
    } catch (e) {
      notify(e.message, 'error')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col">

      {/* Modais */}
      {editProduct && (
        <EditModal
          product={editProduct}
          onClose={() => setEditProduct(null)}
          onSaved={() => load(search)}
        />
      )}
      {showNew && (
        <NewProductModal
          onClose={() => setShowNew(false)}
          onSaved={() => load(search)}
        />
      )}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6">
            <h2 className="text-lg font-bold text-red-600 mb-2">Excluir produto?</h2>
            <p className="text-gray-600 text-sm mb-1">SKU: <span className="font-mono font-bold">{deleteConfirm}</span></p>
            <p className="text-gray-500 text-sm mb-6">Todos os códigos de barras vinculados serão removidos. Esta ação não pode ser desfeita.</p>
            <div className="flex gap-3">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="flex-1 py-2 rounded-xl border-2 border-gray-200 hover:bg-gray-50 text-sm font-medium"
              >
                Cancelar
              </button>
              <button
                onClick={() => handleDelete(deleteConfirm)}
                disabled={deleting}
                className="flex-1 py-2 rounded-xl bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white font-semibold text-sm"
              >
                {deleting ? 'Excluindo...' : 'Excluir'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="bg-white shadow px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold">Master Data — Produtos Cadastrados</h1>
          <p className="text-gray-500 text-sm mt-0.5">
            {loading ? 'Carregando...' : `${total} produtos cadastrados no total`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowNew(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-4 py-2 rounded-xl text-sm transition-colors"
          >
            + Novo Produto
          </button>
          <button
            onClick={() => navigate('/supervisor')}
            className="text-gray-400 hover:text-gray-700 text-lg"
          >
            ← Voltar
          </button>
        </div>
      </div>

      <div className="flex-1 p-6 max-w-5xl mx-auto w-full flex flex-col gap-4">

        {/* Search */}
        <div className="bg-white rounded-2xl shadow p-4">
          <input
            type="text"
            autoFocus
            placeholder="🔍  Buscar por SKU ou código de barras (EAN)..."
            value={search}
            onChange={handleSearch}
            className="w-full border-2 border-gray-200 focus:border-blue-400 rounded-xl p-3 text-base outline-none transition-colors"
          />
          {search && !loading && (
            <p className="text-xs text-gray-400 mt-2 pl-1">
              {items.length} resultado(s) para &quot;{search}&quot;
            </p>
          )}
        </div>

        {/* Table */}
        <div className="bg-white rounded-2xl shadow overflow-hidden">

          <div className="px-5 py-3 bg-gray-50 border-b flex justify-between items-center">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              {loading
                ? 'Carregando...'
                : search
                  ? `${items.length} resultado(s)`
                  : `${items.length} de ${total} produtos`
              }
            </span>
            {!search && total > items.length && (
              <span className="text-xs text-orange-500 font-medium">
                Use a busca para encontrar um produto específico
              </span>
            )}
          </div>

          {loading ? (
            <div className="text-center text-gray-400 py-16 text-xl">Carregando...</div>
          ) : items.length === 0 ? (
            <div className="text-center text-gray-400 py-16">
              {search
                ? <><p className="text-xl mb-2">Nenhum produto encontrado</p><p className="text-sm">Tente outro SKU ou código de barras</p></>
                : <><p className="text-xl mb-2">Nenhum produto cadastrado</p><p className="text-sm">Clique em &quot;+ Novo Produto&quot; ou importe o Excel no Supervisor</p></>
              }
            </div>
          ) : (
            <div className="overflow-x-auto">
          <table className="w-full min-w-[600px] text-sm">
              <thead>
                <tr className="text-gray-500 uppercase text-xs tracking-wide border-b bg-gray-50">
                  <th className="text-left px-5 py-3 font-semibold w-[18%]">SKU</th>
                  <th className="text-left px-5 py-3 font-semibold w-[30%]">Descrição</th>
                  <th className="text-left px-5 py-3 font-semibold">Código(s) de Barras</th>
                  <th className="px-5 py-3 w-[80px]"></th>
                </tr>
              </thead>
              <tbody>
                {items.map((b, idx) => (
                  <tr
                    key={b.sku}
                    className={`border-t border-gray-100 ${idx % 2 === 0 ? 'bg-white' : 'bg-gray-50/40'}`}
                  >
                    <td className="px-5 py-3 font-mono font-bold text-gray-800 align-top">{b.sku}</td>
                    <td className="px-5 py-3 text-gray-700 align-top">
                      {b.description
                        ? b.description
                        : <span className="text-gray-300 italic text-xs">sem descrição</span>
                      }
                    </td>
                    <td className="px-5 py-3 align-top">
                      <div className="flex flex-wrap gap-1">
                        {(b.barcodes ?? [{ barcode: b.barcode, is_primary: true, learned: false }]).map(bc => (
                          <span
                            key={bc.barcode}
                            title={bc.learned ? 'Aprendido durante bipagem' : 'Importado'}
                            className={`font-mono text-xs px-2 py-1 rounded ${
                              bc.learned
                                ? 'bg-blue-50 text-blue-700 border border-blue-200'
                                : 'bg-gray-100 text-gray-700'
                            }`}
                          >
                            {bc.barcode}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 align-top">
                      <div className="flex gap-1 justify-end">
                        <button
                          onClick={() => setEditProduct(b)}
                          title="Editar produto"
                          className="p-1.5 rounded-lg text-gray-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
                        >
                          ✏️
                        </button>
                        <button
                          onClick={() => setDeleteConfirm(b.sku)}
                          title="Excluir produto"
                          className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                        >
                          🗑️
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          )}
        </div>

      </div>
    </div>
  )
}
