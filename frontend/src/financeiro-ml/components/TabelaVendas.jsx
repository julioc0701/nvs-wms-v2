import { useReactTable, getCoreRowModel, getSortedRowModel, flexRender } from '@tanstack/react-table'
import { useState } from 'react'

const fmt = (n) => new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n ?? 0)

const columns = [
  { accessorKey: 'anuncio', header: 'Anúncio' },
  { accessorKey: 'sku', header: 'SKU' },
  { accessorKey: 'data', header: 'Data', cell: (i) => i.getValue()?.slice(0, 10) },
  { accessorKey: 'frete_label', header: 'Frete' },
  { accessorKey: 'valor_unit', header: 'Valor Unit.', cell: (i) => fmt(i.getValue()) },
  { accessorKey: 'qty', header: 'Qtd.' },
  { accessorKey: 'faturamento_ml', header: 'Faturamento ML', cell: (i) => fmt(i.getValue()) },
  { accessorKey: 'custo', header: 'Custo (-)', cell: (i) => fmt(i.getValue()) },
  { accessorKey: 'imposto', header: 'Imposto (-)', cell: (i) => fmt(i.getValue()) },
  { accessorKey: 'tarifa', header: 'Tarifa (-)', cell: (i) => fmt(i.getValue()) },
  { accessorKey: 'frete_comprador', header: 'Frete Comp. (-)', cell: (i) => fmt(i.getValue()) },
  { accessorKey: 'frete_vendedor', header: 'Frete Vend. (-)', cell: (i) => fmt(i.getValue()) },
  { accessorKey: 'mc', header: 'MC (=)', cell: (i) => fmt(i.getValue()) },
  { accessorKey: 'mc_pct', header: 'MC %', cell: (i) => `${fmt(i.getValue())}%` },
]

export function TabelaVendas({ data, pagination, onPageChange, onPageSizeChange }) {
  const [sorting, setSorting] = useState([])
  const table = useReactTable({
    data: data || [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  return (
    <div className="border rounded-lg bg-white overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((h) => (
                <th key={h.id} className="px-3 py-2 text-left font-semibold cursor-pointer"
                    onClick={h.column.getToggleSortingHandler()}>
                  {flexRender(h.column.columnDef.header, h.getContext())}
                  {{ asc: ' ↑', desc: ' ↓' }[h.column.getIsSorted()] ?? ''}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id} className="border-t hover:bg-gray-50">
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="px-3 py-2">
                  {flexRender(cell.column.columnDef.cell ?? cell.column.columnDef.accessorKey, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {pagination && (
        <div className="flex items-center justify-between p-2 border-t bg-gray-50 text-xs">
          <span>
            {(pagination.page - 1) * pagination.page_size + 1}–
            {Math.min(pagination.page * pagination.page_size, pagination.total)} de {pagination.total}
          </span>
          <div className="flex gap-2 items-center">
            <button disabled={pagination.page <= 1} onClick={() => onPageChange(pagination.page - 1)}
                    className="px-2 py-1 border rounded disabled:opacity-50">‹</button>
            <span>{pagination.page} / {pagination.total_pages}</span>
            <button disabled={pagination.page >= pagination.total_pages}
                    onClick={() => onPageChange(pagination.page + 1)}
                    className="px-2 py-1 border rounded disabled:opacity-50">›</button>
            <select value={pagination.page_size} onChange={(e) => onPageSizeChange(parseInt(e.target.value))}
                    className="border rounded px-1 py-0.5 ml-2">
              <option value="50">50</option>
              <option value="100">100</option>
              <option value="200">200</option>
            </select>
          </div>
        </div>
      )}
    </div>
  )
}
