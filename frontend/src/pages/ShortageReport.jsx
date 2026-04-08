import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import MarketplaceLogo from '../components/MarketplaceLogo'
import Card from '../components/ui/Card'
import PageHeader from '../components/ui/PageHeader'
import SkeletonRows from '../components/ui/SkeletonRows'
import { AlertTriangle, PackageX } from 'lucide-react'
import { useFeedback } from '../components/ui/FeedbackProvider'

export default function ShortageReport() {
  const navigate = useNavigate()
  const { askPrompt, notify } = useFeedback()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getShortageReport()
      .then(setItems)
      .finally(() => setLoading(false))
  }, [])

  const totalShortage = items.reduce((s, i) => s + i.shortage_qty, 0)

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-8 max-w-6xl mx-auto">
      <PageHeader
        title="Relatório de Faltas"
        subtitle="SKUs com falta de estoque em listas ativas e concluídas"
        backLabel="Sessões"
        onBack={() => navigate('/sessions')}
        right={
          <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-red-50 border border-red-100 text-red-700 text-sm font-semibold">
            <AlertTriangle size={16} />
            Total faltante: {totalShortage} unidades
          </div>
        }
      />

      <Card className="mt-6 p-6">
        {loading && (
          <SkeletonRows rows={6} />
        )}

        {!loading && items.length === 0 && (
          <div className="text-center text-slate-400 py-14">
            <PackageX size={48} className="mx-auto mb-3 text-emerald-500" />
            <p className="text-xl font-bold text-emerald-700">Nenhuma falta registrada</p>
            <p className="text-sm mt-1">Operação está sem pendências de shortage no momento.</p>
          </div>
        )}

        {!loading && items.length > 0 && (
          <>
            <div className="flex justify-between items-center mb-4">
              <p className="text-sm text-slate-500 font-medium">
                {items.length} SKU{items.length !== 1 ? 's' : ''} com falta
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">
                    <th className="pb-3 pr-4">SKU</th>
                    <th className="pb-3 pr-4">Descrição</th>
                    <th className="pb-3 pr-4">Lista</th>
                    <th className="pb-3 pr-4">Observação</th>
                    <th className="pb-3 text-right text-red-600">Qtd Faltante</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {items.map(item => (
                    <tr key={`${item.sku}-${item.session_code}`} className="hover:bg-slate-50 transition-colors">
                      <td className="py-3 pr-4 font-mono font-semibold whitespace-nowrap">
                        {item.sku}
                      </td>
                      <td className="py-3 pr-4 text-slate-700">
                        {item.description || '—'}
                      </td>
                      <td className="py-3 pr-4">
                        <span className="font-mono text-xs bg-blue-50 text-blue-700 border border-blue-100 px-2 flex items-center gap-1 py-0.5 rounded-full whitespace-nowrap w-max">
                          <MarketplaceLogo marketplace={item.marketplace} size={14} /> {item.session_code || '—'}
                        </span>
                      </td>
                      <td className="py-3 pr-4">
                        <div
                          onClick={async () => {
                            const newNotes = await askPrompt({
                              title: `Observação do SKU ${item.sku}`,
                              message: 'Adicionar/Editar observação',
                              initialValue: item.notes || '',
                              placeholder: 'Digite a observação',
                              confirmText: 'Salvar',
                            })
                            if (newNotes === null) return
                            try {
                              await api.updateShortageNotes(item.sku, newNotes.trim() || null)
                              setItems(prev => prev.map(i => i.sku === item.sku ? { ...i, notes: newNotes.trim() || null } : i))
                            } catch (e) {
                              notify('Erro ao atualizar: ' + e.message, 'error')
                            }
                          }}
                          className="truncate max-w-[250px] cursor-pointer text-blue-600 hover:text-blue-800 italic group hover:bg-blue-50 p-1 rounded transition-colors"
                          title={item.notes || 'Clique para adicionar observação'}
                        >
                          <span className="mr-1 opacity-0 group-hover:opacity-100 transition-opacity">✏️</span>
                          {item.notes || <span className="text-slate-300">clique para add</span>}
                        </div>
                      </td>
                      <td className="py-3 text-right">
                        <span className="font-bold text-red-600 text-base">
                          -{item.shortage_qty}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}
