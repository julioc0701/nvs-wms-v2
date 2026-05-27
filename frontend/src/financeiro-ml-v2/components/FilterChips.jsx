import { useState } from 'react'
import { X, Plus } from 'lucide-react'

const STATUS_LABELS = {
  todos: null,
  aprovado: 'Aprovados',
  cancelado: 'Cancelados',
}

const MODALIDADE_LABELS = {
  todos: null,
  premium: 'Premium',
  classico: 'Clássico',
  gratis: 'Grátis',
}

const FRETE_LABELS = {
  todos: null,
  me1: 'ME1',
  me2: 'ME2',
  sem_me: 'S/ME',
  full: 'FULL',
  flex: 'FLEX',
  outro: 'Outro',
}

const CI_LABELS = {
  todos: null,
  sem_custo: 'Sem custo',
  sem_imposto: 'Sem imposto',
  sem_custo_imposto: 'Sem custo e imposto',
}

function buildActiveChips(filters) {
  const chips = []
  if (STATUS_LABELS[filters.status]) {
    chips.push({ key: 'status', label: `Status: ${STATUS_LABELS[filters.status]}` })
  }
  if (MODALIDADE_LABELS[filters.modalidade]) {
    chips.push({ key: 'modalidade', label: MODALIDADE_LABELS[filters.modalidade] })
  }
  if (FRETE_LABELS[filters.tipo_frete]) {
    chips.push({ key: 'tipo_frete', label: FRETE_LABELS[filters.tipo_frete] })
  }
  if (CI_LABELS[filters.custo_imposto]) {
    chips.push({ key: 'custo_imposto', label: CI_LABELS[filters.custo_imposto] })
  }
  if (filters.sku) chips.push({ key: 'sku', label: `SKU: ${filters.sku}` })
  if (filters.mlb) chips.push({ key: 'mlb', label: `MLB: ${filters.mlb}` })
  if (filters.considerar_frete_comprador) {
    chips.push({ key: 'considerar_frete_comprador', label: 'Inclui frete comp.' })
  }
  return chips
}

const RESET_VALUES = {
  status: 'todos',
  modalidade: 'todos',
  tipo_frete: 'todos',
  custo_imposto: 'todos',
  sku: '',
  mlb: '',
  considerar_frete_comprador: false,
}

export function FilterChips({ filters, onChange }) {
  const [popoverOpen, setPopoverOpen] = useState(false)
  const chips = buildActiveChips(filters)

  const removeChip = (key) => {
    onChange({ ...filters, [key]: RESET_VALUES[key], page: 1 })
  }

  const updateFilter = (key, value) => {
    onChange({ ...filters, [key]: value, page: 1 })
  }

  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {chips.map((chip) => (
        <span
          key={chip.key}
          className="flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-white border border-[var(--fmlv2-border-strong)] text-[var(--fmlv2-ink-2)]"
        >
          {chip.label}
          <button
            onClick={() => removeChip(chip.key)}
            className="text-[var(--fmlv2-muted)] hover:text-[var(--fmlv2-neg)]"
            aria-label={`Remover filtro ${chip.label}`}
          >
            <X size={11} />
          </button>
        </span>
      ))}

      <div className="relative">
        <button
          onClick={() => setPopoverOpen((v) => !v)}
          className="flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium border border-dashed border-[var(--fmlv2-border-strong)] text-[var(--fmlv2-muted)] hover:bg-white"
        >
          <Plus size={11} /> Filtro
        </button>

        {popoverOpen && (
          <div className="absolute right-0 top-full mt-1 z-20 w-72 bg-white border border-[var(--fmlv2-border)] rounded-lg shadow-lg p-3 grid grid-cols-1 gap-2.5 text-xs">
            <label className="block">
              <span className="text-[var(--fmlv2-muted)]">Status</span>
              <select
                value={filters.status}
                onChange={(e) => updateFilter('status', e.target.value)}
                className="block w-full mt-1 border border-[var(--fmlv2-border)] rounded px-2 py-1"
              >
                <option value="todos">Todos</option>
                <option value="aprovado">Aprovados</option>
                <option value="cancelado">Cancelados</option>
              </select>
            </label>

            <label className="block">
              <span className="text-[var(--fmlv2-muted)]">Modalidade</span>
              <select
                value={filters.modalidade}
                onChange={(e) => updateFilter('modalidade', e.target.value)}
                className="block w-full mt-1 border border-[var(--fmlv2-border)] rounded px-2 py-1"
              >
                <option value="todos">Todos</option>
                <option value="premium">Premium</option>
                <option value="classico">Clássico</option>
                <option value="gratis">Grátis</option>
              </select>
            </label>

            <label className="block">
              <span className="text-[var(--fmlv2-muted)]">Tipo do Frete</span>
              <select
                value={filters.tipo_frete}
                onChange={(e) => updateFilter('tipo_frete', e.target.value)}
                className="block w-full mt-1 border border-[var(--fmlv2-border)] rounded px-2 py-1"
              >
                <option value="todos">Todos</option>
                <option value="me1">Mercado Envios 1</option>
                <option value="me2">Mercado Envios 2</option>
                <option value="sem_me">S/ Mercado Envios</option>
                <option value="full">FULL</option>
                <option value="flex">Flex</option>
                <option value="outro">Outro</option>
              </select>
            </label>

            <label className="block">
              <span className="text-[var(--fmlv2-muted)]">Custo & Imposto</span>
              <select
                value={filters.custo_imposto}
                onChange={(e) => updateFilter('custo_imposto', e.target.value)}
                className="block w-full mt-1 border border-[var(--fmlv2-border)] rounded px-2 py-1"
              >
                <option value="todos">Todos</option>
                <option value="sem_custo">Somente sem Custo</option>
                <option value="sem_imposto">Somente sem Imposto</option>
                <option value="sem_custo_imposto">Somente sem ambos</option>
              </select>
            </label>

            <label className="block">
              <span className="text-[var(--fmlv2-muted)]">SKU</span>
              <input
                value={filters.sku}
                onChange={(e) => updateFilter('sku', e.target.value)}
                className="block w-full mt-1 border border-[var(--fmlv2-border)] rounded px-2 py-1"
              />
            </label>

            <label className="block">
              <span className="text-[var(--fmlv2-muted)]">Nº Pedido / MLB</span>
              <input
                value={filters.mlb}
                onChange={(e) => updateFilter('mlb', e.target.value)}
                className="block w-full mt-1 border border-[var(--fmlv2-border)] rounded px-2 py-1"
              />
            </label>

            <label className="flex items-center gap-2 mt-1">
              <input
                type="checkbox"
                checked={filters.considerar_frete_comprador}
                onChange={(e) => updateFilter('considerar_frete_comprador', e.target.checked)}
              />
              <span>Considerar frete comprador</span>
            </label>

            <button
              onClick={() => setPopoverOpen(false)}
              className="mt-1 px-3 py-1.5 bg-[var(--fmlv2-ink-2)] text-white rounded text-xs hover:opacity-90"
            >
              Fechar
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
