import { useState, useMemo } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
} from '@tanstack/react-table'
import { Settings, Download } from 'lucide-react'

const fmt = (n) =>
  new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n ?? 0)

const FRETE_BADGE_STYLE = {
  full: { bg: '#E0E7F5', fg: '#1B4F8A' },
  flex: { bg: '#FEF3C7', fg: '#92400E' },
  me1:  { bg: '#E0F2F1', fg: '#0F766E' },
  me2:  { bg: '#E0F2F1', fg: '#0F766E' },
}

function FreteBadge({ value }) {
  const key = (value || '').toLowerCase()
  const style = FRETE_BADGE_STYLE[key] || { bg: '#E5E7EB', fg: '#4B5563' }
  return (
    <span
      className="inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase"
      style={{ background: style.bg, color: style.fg }}
    >
      {value || '—'}
    </span>
  )
}

function McCell({ value }) {
  const v = Number(value) || 0
  const color = v >= 0 ? 'var(--fmlv2-pos)' : 'var(--fmlv2-neg)'
  return <span style={{ color, fontWeight: 600 }}>{fmt(v)}</span>
}

function McPctCell({ value }) {
  const v = Number(value) || 0
  // Faixas: >=13 verde · 10-12,99 amarelo · <10 vermelho
  let color = 'var(--fmlv2-neg)'
  if (v >= 13) color = 'var(--fmlv2-pos)'
  else if (v >= 10) color = '#D97706'
  return <span style={{ color, fontWeight: 600 }}>{fmt(v)}%</span>
}

const COLUMNS = [
  {
    accessorKey: 'anuncio',
    header: 'Anúncio · SKU',
    cell: (i) => (
      <div className="flex flex-col leading-tight">
        <span className="text-[12px] text-[var(--fmlv2-text)] truncate max-w-[300px]">
          {i.getValue()}
        </span>
        <span className="fmlv2-mono text-[10px] text-[var(--fmlv2-muted)]">
          {i.row.original.sku || '—'}
        </span>
      </div>
    ),
  },
  { accessorKey: 'data',         header: 'Data',         cell: (i) => i.getValue()?.slice(0, 10) },
  { accessorKey: 'frete_label',  header: 'Frete',        cell: (i) => <FreteBadge value={i.getValue()} /> },
  { accessorKey: 'valor_unit',   header: 'Valor Un.',    cell: (i) => fmt(i.getValue()), isNum: true },
  { accessorKey: 'qty',          header: 'Qtd',          cell: (i) => i.getValue(),       isNum: true },
  { accessorKey: 'faturamento_ml', header: 'Faturamento', cell: (i) => fmt(i.getValue()), isNum: true },
  { accessorKey: 'custo',        header: 'Custo',        cell: (i) => fmt(i.getValue()), isNum: true },
  { accessorKey: 'imposto',      header: 'Imposto',      cell: (i) => fmt(i.getValue()), isNum: true },
  { accessorKey: 'tarifa',       header: 'Tarifa',       cell: (i) => fmt(i.getValue()), isNum: true },
  { accessorKey: 'frete_comprador', header: 'Frete Comp.', cell: (i) => fmt(i.getValue()), isNum: true },
  { accessorKey: 'frete_vendedor', header: 'Frete Vend.', cell: (i) => fmt(i.getValue()), isNum: true },
  { accessorKey: 'mc',           header: 'MC',           cell: (i) => <McCell value={i.getValue()} />, isNum: true },
  { accessorKey: 'mc_pct',       header: 'MC %',         cell: (i) => <McPctCell value={i.getValue()} />, isNum: true },
]

const ALL_COL_KEYS = COLUMNS.map((c) => c.accessorKey)
const EMPTY_DATA = Object.freeze([])  // referência estável pra useReactTable não disparar effects

export function DataTable({ data, pagination, chips, onPageChange, onPageSizeChange, onExport }) {
  const [sorting, setSorting] = useState([])
  const [visibleCols, setVisibleCols] = useState(() =>
    Object.fromEntries(ALL_COL_KEYS.map((k) => [k, true]))
  )
  const [colMenuOpen, setColMenuOpen] = useState(false)
  const [exportMenuOpen, setExportMenuOpen] = useState(false)

  const filteredCols = useMemo(
    () => COLUMNS.filter((c) => visibleCols[c.accessorKey]),
    [visibleCols]
  )

  // Estabiliza referência de data: array novo a cada render dispara loop com TanStack Table sob StrictMode (issue #4566)
  const tableData = useMemo(
    () => (Array.isArray(data) && data.length ? data : EMPTY_DATA),
    [data]
  )

  // TanStack FAQ: row models devem ser memoizados — chamar a cada render gera ruído sob StrictMode
  const coreRowModel   = useMemo(() => getCoreRowModel(),   [])
  const sortedRowModel = useMemo(() => getSortedRowModel(), [])

  const table = useReactTable({
    data: tableData,
    columns: filteredCols,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel:   coreRowModel,
    getSortedRowModel: sortedRowModel,
  })

  return (
    <div className="rounded-xl bg-white border border-[var(--fmlv2-border)] overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 bg-[var(--fmlv2-surface)] border-b border-[var(--fmlv2-border)]">
        <div>
          <div className="text-[15px] font-semibold text-[var(--fmlv2-ink)] tracking-tight">
            Vendas detalhadas
          </div>
          <div className="text-[11px] text-[var(--fmlv2-muted)]">
            {pagination?.total ?? 0} resultados · todas as colunas de custo, imposto, frete e margem
          </div>
        </div>
        <div className="flex-1" />
        {chips}
        <div className="relative">
          <button
            onClick={() => setColMenuOpen((v) => !v)}
            className="flex items-center gap-1 px-2 py-1 text-[11px] font-medium text-white bg-[var(--fmlv2-ink-2)] border border-[var(--fmlv2-ink-2)] rounded hover:opacity-90"
          >
            <Settings size={12} /> Colunas
          </button>
          {colMenuOpen && (
            <div className="absolute right-0 top-full mt-1 z-20 w-48 bg-white border border-[var(--fmlv2-border)] rounded-lg shadow-lg p-2 max-h-80 overflow-y-auto">
              {COLUMNS.map((c) => (
                <label key={c.accessorKey} className="flex items-center gap-2 text-xs py-1 px-1 hover:bg-[var(--fmlv2-surface)] rounded">
                  <input
                    type="checkbox"
                    checked={visibleCols[c.accessorKey]}
                    onChange={(e) =>
                      setVisibleCols((s) => ({ ...s, [c.accessorKey]: e.target.checked }))
                    }
                  />
                  {c.header}
                </label>
              ))}
            </div>
          )}
        </div>
        <div className="relative">
          <button
            onClick={() => setExportMenuOpen((v) => !v)}
            className="flex items-center gap-1 px-2 py-1 text-[11px] font-medium text-white bg-[var(--fmlv2-ink-2)] border border-[var(--fmlv2-ink-2)] rounded hover:opacity-90"
          >
            <Download size={12} /> Exportar
          </button>
          {exportMenuOpen && (
            <div className="absolute right-0 top-full mt-1 z-20 w-32 bg-white border border-[var(--fmlv2-border)] rounded-lg shadow-lg overflow-hidden">
              <button
                onClick={() => { setExportMenuOpen(false); onExport('excel') }}
                className="block w-full text-left px-3 py-2 text-xs hover:bg-[var(--fmlv2-surface)]"
              >
                📊 Excel
              </button>
              <button
                onClick={() => { setExportMenuOpen(false); onExport('csv') }}
                className="block w-full text-left px-3 py-2 text-xs hover:bg-[var(--fmlv2-surface)]"
              >
                📄 CSV
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-[11px]">
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="bg-[var(--fmlv2-surface)]">
                {hg.headers.map((h) => {
                  const colDef = h.column.columnDef
                  const isNum = colDef.isNum
                  return (
                    <th
                      key={h.id}
                      onClick={h.column.getToggleSortingHandler()}
                      className={`px-3 py-2 font-semibold text-[10px] uppercase tracking-[0.05em] text-[var(--fmlv2-muted)] border-b border-[var(--fmlv2-border)] cursor-pointer ${
                        isNum ? 'text-right' : 'text-left'
                      }`}
                    >
                      {flexRender(colDef.header, h.getContext())}
                      {{ asc: ' ↑', desc: ' ↓' }[h.column.getIsSorted()] ?? ''}
                    </th>
                  )
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                className="hover:bg-[var(--fmlv2-surface)] border-b border-[var(--fmlv2-border)] last:border-b-0"
              >
                {row.getVisibleCells().map((cell) => {
                  const isNum = cell.column.columnDef.isNum
                  return (
                    <td
                      key={cell.id}
                      className={`px-3 py-2.5 ${
                        isNum ? 'text-right fmlv2-mono' : 'text-left'
                      }`}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pagination && (
        <div className="flex items-center gap-2 px-4 py-2.5 bg-[var(--fmlv2-surface)] border-t border-[var(--fmlv2-border)] text-[11px] text-[var(--fmlv2-muted)]">
          <div>
            Mostrando {(pagination.page - 1) * pagination.page_size + 1}–
            {Math.min(pagination.page * pagination.page_size, pagination.total)} de {pagination.total}
          </div>
          <div className="ml-auto flex items-center gap-1">
            <select
              value={pagination.page_size}
              onChange={(e) => onPageSizeChange(parseInt(e.target.value))}
              className="border border-[var(--fmlv2-border)] rounded px-1.5 py-0.5 bg-white"
            >
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
            </select>
            <span className="mx-1 text-[var(--fmlv2-border-strong)]">|</span>
            <button
              disabled={pagination.page <= 1}
              onClick={() => onPageChange(pagination.page - 1)}
              className="px-2 py-0.5 border border-[var(--fmlv2-border)] rounded bg-white disabled:opacity-40"
            >
              ‹
            </button>
            <span className="px-2 py-0.5 bg-[var(--fmlv2-ink-2)] text-white rounded">
              {pagination.page}
            </span>
            <span>/ {pagination.total_pages}</span>
            <button
              disabled={pagination.page >= pagination.total_pages}
              onClick={() => onPageChange(pagination.page + 1)}
              className="px-2 py-0.5 border border-[var(--fmlv2-border)] rounded bg-white disabled:opacity-40"
            >
              ›
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
