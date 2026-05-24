import { useEffect } from 'react'

/**
 * Dialog genérico de confirmação para o módulo Financeiro.
 * Usado para "Marcar como pago", "Reabrir", "Excluir".
 *
 * Props:
 *  - icon: nó React opcional (SVG) para o badge superior
 *  - iconBg / iconColor: classes Tailwind do badge ("bg-green-100"/"text-green-600")
 *  - titulo: string
 *  - detalhes: nó React (cards/textos com info do boleto)
 *  - pergunta: string final ("Deseja prosseguir?")
 *  - confirmLabel / confirmClasses: texto e cor do botão de ação
 *  - onConfirm / onCancel
 */
export default function FinanceiroConfirmDialog({
  icon,
  iconBg = 'bg-cyan-100',
  iconColor = 'text-cyan-600',
  titulo,
  detalhes,
  pergunta,
  confirmLabel = 'CONFIRMAR',
  confirmClasses = 'bg-cyan-600 hover:bg-cyan-700 shadow-cyan-200',
  onConfirm,
  onCancel,
}) {
  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'Enter') onConfirm()
      if (e.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onConfirm, onCancel])

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onCancel}
    >
      <div
        className="bg-white rounded-3xl p-6 sm:p-8 w-full w-[min(95vw,28rem)] shadow-2xl overflow-y-auto max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 mb-6">
          <div className={`w-12 h-12 ${iconBg} rounded-full flex items-center justify-center ${iconColor} shrink-0`}>
            {icon}
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold text-gray-800">{titulo}</h2>
        </div>

        {detalhes && (
          <div className="bg-gray-50 rounded-2xl p-5 mb-6">
            {detalhes}
          </div>
        )}

        {pergunta && (
          <p className="text-gray-600 mb-8 leading-relaxed">{pergunta}</p>
        )}

        <div className="flex gap-4">
          <button
            onClick={onCancel}
            className="flex-1 py-4 rounded-xl border-2 border-gray-300 text-lg font-bold text-gray-500 hover:bg-gray-100 transition-colors"
          >
            CANCELAR
          </button>
          <button
            onClick={onConfirm}
            className={`flex-1 py-4 rounded-xl text-white text-lg font-bold shadow-lg active:scale-95 transition-all ${confirmClasses}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
