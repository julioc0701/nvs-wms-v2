import { useEffect, useRef, useState } from 'react'

export default function ShortageDialog({ item, onConfirm, onCancel }) {
  const [qty, setQty] = useState(item.qty_picked)
  const [notes, setNotes] = useState('')
  const inputRef = useRef()

  useEffect(() => { inputRef.current?.select() }, [])

  function handleKey(e) {
    if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA') onConfirm(Number(qty), notes)
    if (e.key === 'Escape') onCancel()
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-3xl p-10 w-full max-w-md shadow-2xl overflow-y-auto max-h-[90vh]" onKeyDown={handleKey}>
        <h2 className="text-4xl font-bold text-orange-600 mb-2">⚠ FALTA DE ESTOQUE</h2>
        <p className="text-xl text-gray-600 mb-1">{item.sku}</p>
        <p className="text-lg text-gray-500 mb-6">{item.description}</p>

        <p className="text-xl mb-1">Necessário: <strong>{item.qty_required}</strong></p>
        <p className="text-xl mb-6">Separado até agora: <strong>{item.qty_picked}</strong></p>

        <div className="mb-6">
          <label className="block text-xl font-medium mb-2">Quantos você encontrou?</label>
          <input
            ref={inputRef}
            type="number"
            min={0}
            max={item.qty_required}
            value={qty}
            onChange={e => setQty(e.target.value)}
            className="w-full text-4xl text-center border-4 border-orange-400 rounded-xl p-3 mb-2 focus:outline-none focus:border-orange-600"
          />
          <p className="text-lg text-gray-500">Faltando: <strong>{item.qty_required - qty}</strong></p>
        </div>

        <div className="mb-8">
          <label className="block text-xl font-medium mb-2">Observação (Opcional)</label>
          <textarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            placeholder="Ex: Faltou apenas o reparo do kit..."
            className="w-full text-lg border-2 border-gray-300 rounded-xl p-3 focus:outline-none focus:border-orange-400 min-h-[100px]"
          />
        </div>

        <div className="flex gap-4">
          <button onClick={onCancel}
            className="flex-1 py-4 rounded-xl border-2 border-gray-300 text-xl hover:bg-gray-100">
            CANCELAR
          </button>
          <button onClick={() => onConfirm(Number(qty), notes)}
            className="flex-1 py-4 rounded-xl bg-orange-500 text-white text-xl font-bold hover:bg-orange-600">
            CONFIRMAR
          </button>
        </div>
      </div>
    </div>
  )
}
