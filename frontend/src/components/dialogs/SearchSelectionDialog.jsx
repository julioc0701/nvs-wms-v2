import { useEffect } from 'react'
import MarketplaceLogo from '../MarketplaceLogo'

export default function SearchSelectionDialog({ candidates, onSelect, onCancel }) {
  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onCancel])

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
      <div className="bg-white rounded-3xl shadow-2xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[90vh]">
        <div className="p-6 bg-gray-50 border-b border-gray-200">
          <h2 className="text-3xl font-bold text-gray-800">Selecione o Item</h2>
          <p className="text-gray-500">Múltiplos itens encontrados para sua busca.</p>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          <div className="space-y-3">
            {candidates.map((item) => (
              <button
                key={`${item.session_id}-${item.sku}`}
                onClick={() => onSelect(item)}
                className="w-full bg-white border-2 border-gray-100 rounded-2xl p-4 text-left hover:border-blue-500 hover:bg-blue-50 transition-all group flex items-start gap-4"
              >
                <div className="flex-1">
                  <div className="flex justify-between items-start mb-1">
                    <span className="text-xl font-black text-gray-900 group-hover:text-blue-600 transition-colors">
                      {item.sku}
                    </span>
                    <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${
                      item.status === 'complete' ? 'bg-green-100 text-green-700' :
                      item.status === 'pending' ? 'bg-gray-100 text-gray-600' :
                      'bg-blue-100 text-blue-700'
                    }`}>
                      {item.status}
                    </span>
                  </div>
                  <p className="text-gray-600 font-medium mb-3 line-clamp-2">{item.description}</p>
                  
                  <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm">
                    <div className="flex items-center gap-1.5 text-gray-500">
                      <span className="font-bold text-gray-400">LISTA:</span>
                      <code className="bg-gray-100 px-2 py-0.5 rounded font-mono font-bold text-gray-700 flex items-center gap-1.5">
                        <MarketplaceLogo marketplace={item.marketplace} size={14} />
                        {item.session_code}
                      </code>
                    </div>
                    <div className="flex items-center gap-1.5 text-gray-500">
                      <span className="font-bold text-gray-400">OPERADOR:</span>
                      <span className="font-bold text-gray-700 uppercase">{item.operator_name}</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-gray-500">
                      <span className="font-bold text-gray-400">QTD:</span>
                      <span className="font-bold text-gray-700">{item.qty_picked}/{item.qty_required}</span>
                    </div>
                  </div>
                </div>
                
                <div className="self-center">
                  <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center text-gray-400 group-hover:bg-blue-600 group-hover:text-white transition-all">
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="9 18 15 12 9 6" />
                    </svg>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="p-4 bg-gray-50 border-t border-gray-200">
          <button
            onClick={onCancel}
            className="w-full py-4 text-xl font-bold text-gray-500 hover:bg-gray-200 rounded-2xl transition-colors"
          >
            CANCELAR
          </button>
        </div>
      </div>
    </div>
  )
}
