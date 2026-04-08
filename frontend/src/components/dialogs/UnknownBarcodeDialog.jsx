import { useEffect } from 'react'

export default function UnknownBarcodeDialog({ barcode, currentSku, onAdd, onSkip }) {
  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'Enter') onAdd()
      if (e.key === 'Escape') onSkip()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onAdd, onSkip])

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-3xl p-10 w-full max-w-md shadow-2xl">
        <h2 className="text-4xl font-bold text-yellow-600 mb-4">❓ CÓDIGO OU SKU DESCONHECIDO</h2>
        <p className="text-xl mb-2">Código: <code className="bg-gray-100 px-2 py-1 rounded font-mono">{barcode}</code></p>
        <p className="text-xl mb-8">SKU atual: <strong>{currentSku}</strong></p>

        <p className="text-2xl font-medium mb-8">Vincular este código ao SKU atual?</p>

        <div className="flex gap-4">
          <button onClick={onSkip}
            className="flex-1 py-4 rounded-xl border-2 border-gray-300 text-xl hover:bg-gray-100">
            CANCELAR
          </button>
          <button onClick={onAdd}
            className="flex-1 py-4 rounded-xl bg-yellow-500 text-white text-xl font-bold hover:bg-yellow-600">
            SIM, VINCULAR
          </button>
        </div>
      </div>
    </div>
  )
}
