import { useEffect } from 'react'

export default function WrongSkuDialog({ scannedItem, expectedSku, onConfirm, onCancel }) {
  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'Enter') onConfirm()
      if (e.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onConfirm, onCancel])

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-3xl p-6 sm:p-10 w-full w-[min(95vw,28rem)] shadow-2xl overflow-y-auto max-h-[90vh]">
        <h2 className="text-2xl sm:text-3xl md:text-4xl font-bold text-red-600 mb-6">⚠ PRODUTO DIFERENTE</h2>

        <div className="bg-red-50 rounded-xl p-4 mb-4">
          <p className="text-sm sm:text-lg text-gray-500">Escaneado</p>
          <p className="text-lg sm:text-2xl font-bold break-all">{scannedItem?.sku}</p>
          <p className="text-sm sm:text-lg text-gray-600">{scannedItem?.description}</p>
        </div>

        <div className="bg-gray-50 rounded-xl p-4 mb-8">
          <p className="text-sm sm:text-lg text-gray-500">Esperado</p>
          <p className="text-lg sm:text-2xl font-bold break-all">{expectedSku}</p>
        </div>

        <p className="text-base sm:text-xl font-medium mb-6">Confirmar substituição?</p>

        <div className="flex gap-4">
          <button onClick={onCancel}
            className="flex-1 py-4 min-h-[44px] rounded-xl border-2 border-gray-300 text-xl hover:bg-gray-100 active:scale-95 transition-all">
            CANCELAR
          </button>
          <button onClick={onConfirm}
            className="flex-1 py-4 min-h-[44px] rounded-xl bg-red-500 text-white text-xl font-bold hover:bg-red-600 active:scale-95 transition-all">
            CONFIRMAR
          </button>
        </div>
      </div>
    </div>
  )
}
