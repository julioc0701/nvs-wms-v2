import { useEffect } from 'react'

export default function TransferConfirmDialog({ sku, ownerName, onConfirm, onCancel }) {
  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'Enter') onConfirm()
      if (e.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onConfirm, onCancel])

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-3xl p-8 w-full max-w-md shadow-2xl">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center text-blue-600">
            <svg xmlns="http://www.w3.org/2000/svg" className="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M16 3h5v5" />
              <path d="M8 21H3v-5" />
              <path d="M21 3l-7 7" />
              <path d="M3 21l7-7" />
            </svg>
          </div>
          <h2 className="text-3xl font-bold text-gray-800">Transferir Item?</h2>
        </div>

        <div className="bg-gray-50 rounded-2xl p-5 mb-8">
          <p className="text-gray-500 text-sm mb-1 uppercase font-bold tracking-wider">SKU ALVO</p>
          <p className="text-2xl font-black text-blue-600 mb-4">{sku}</p>
          
          <div className="border-t border-gray-200 pt-4">
            <p className="text-gray-500 text-sm mb-1 uppercase font-bold tracking-wider">LOCALIZAÇÃO ATUAL</p>
            <p className="text-lg font-medium text-gray-700">Na lista de: <span className="font-bold text-gray-900 border-b-2 border-orange-300">{ownerName}</span></p>
            <p className="text-xs text-orange-600 mt-1 font-semibold italic">Este item ainda não foi iniciado.</p>
          </div>
        </div>

        <p className="text-gray-600 mb-8 leading-relaxed">
          Deseja trazer este item para uma <strong>LISTA EXTRA</strong> no seu nome agora?
        </p>

        <div className="flex gap-4">
          <button onClick={onCancel}
            className="flex-1 py-4 rounded-xl border-2 border-gray-300 text-xl font-bold text-gray-500 hover:bg-gray-100 transition-colors">
            CANCELAR
          </button>
          <button onClick={onConfirm}
            className="flex-1 py-4 rounded-xl bg-blue-600 text-white text-xl font-bold shadow-lg shadow-blue-200 hover:bg-blue-700 active:scale-95 transition-all">
            SIM, PUXAR
          </button>
        </div>
      </div>
    </div>
  )
}
