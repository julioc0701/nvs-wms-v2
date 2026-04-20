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
      <div className="bg-white rounded-3xl p-6 sm:p-10 w-full w-[min(95vw,28rem)] shadow-2xl overflow-y-auto max-h-[90vh]">
        <h2 className="text-xl sm:text-2xl md:text-3xl font-bold text-yellow-600 mb-4">❓ CÓDIGO OU SKU DESCONHECIDO</h2>
        <p className="text-base sm:text-xl mb-2">Código: <code className="bg-gray-100 px-2 py-1 rounded font-mono break-all text-sm sm:text-base">{barcode}</code></p>
        <p className="text-base sm:text-xl mb-8">SKU atual: <strong className="break-all">{currentSku}</strong></p>

        <p className="text-lg sm:text-2xl font-medium mb-8">Vincular este código ao SKU atual?</p>

        <div className="flex gap-4">
          <button onClick={onSkip}
            className="flex-1 py-4 min-h-[44px] rounded-xl border-2 border-gray-300 text-xl hover:bg-gray-100 active:scale-95 transition-all">
            CANCELAR
          </button>
          <button onClick={onAdd}
            className="flex-1 py-4 min-h-[44px] rounded-xl bg-yellow-500 text-white text-xl font-bold hover:bg-yellow-600 active:scale-95 transition-all">
            SIM, VINCULAR
          </button>
        </div>
      </div>
    </div>
  )
}
