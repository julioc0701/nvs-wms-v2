import { useState } from 'react'

const today = () => new Date().toISOString().slice(0, 10)

export function FiltrosBar({ onBuscar, loading }) {
  const [filtros, setFiltros] = useState({
    data_inicio: today(),
    data_fim: today(),
    sku: '',
    mlb: '',
    status: 'todos',
    modalidade: 'todos',
    tipo_frete: 'todos',
    custo_imposto: 'todos',
    considerar_frete_comprador: false,
    page: 1,
    page_size: 50,
  })

  const set = (key, value) => setFiltros((f) => ({ ...f, [key]: value, page: 1 }))

  return (
    <div className="border rounded-lg p-4 bg-white">
      <h3 className="text-sm font-semibold mb-3">Filtrar Busca</h3>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        <label className="text-xs">
          Data Início
          <input type="date" value={filtros.data_inicio} onChange={(e) => set('data_inicio', e.target.value)}
                 className="block w-full mt-1 border rounded px-2 py-1" />
        </label>
        <label className="text-xs">
          Data Fim
          <input type="date" value={filtros.data_fim} onChange={(e) => set('data_fim', e.target.value)}
                 className="block w-full mt-1 border rounded px-2 py-1" />
        </label>
        <label className="text-xs">
          SKU
          <input value={filtros.sku} onChange={(e) => set('sku', e.target.value)}
                 className="block w-full mt-1 border rounded px-2 py-1" />
        </label>
        <label className="text-xs">
          Nº Pedido / MLB
          <input value={filtros.mlb} onChange={(e) => set('mlb', e.target.value)}
                 className="block w-full mt-1 border rounded px-2 py-1" />
        </label>
        <label className="text-xs">
          Status Venda
          <select value={filtros.status} onChange={(e) => set('status', e.target.value)}
                  className="block w-full mt-1 border rounded px-2 py-1">
            <option value="todos">Todos</option>
            <option value="aprovado">Aprovados</option>
            <option value="cancelado">Cancelados</option>
          </select>
        </label>
        <label className="text-xs">
          Modalidade (Anúncio)
          <select value={filtros.modalidade} onChange={(e) => set('modalidade', e.target.value)}
                  className="block w-full mt-1 border rounded px-2 py-1">
            <option value="todos">Todos</option>
            <option value="premium">Premium</option>
            <option value="classico">Clássico</option>
            <option value="gratis">Grátis</option>
          </select>
        </label>
        <label className="text-xs">
          Tipo do Frete
          <select value={filtros.tipo_frete} onChange={(e) => set('tipo_frete', e.target.value)}
                  className="block w-full mt-1 border rounded px-2 py-1">
            <option value="todos">Todos</option>
            <option value="me1">Mercado Envios 1</option>
            <option value="me2">Mercado Envios 2</option>
            <option value="sem_me">S/ Mercado Envios</option>
            <option value="full">FULL</option>
            <option value="flex">Flex</option>
            <option value="outro">Outro (a Combinar)</option>
          </select>
        </label>
        <label className="text-xs">
          Custo & Imposto
          <select value={filtros.custo_imposto} onChange={(e) => set('custo_imposto', e.target.value)}
                  className="block w-full mt-1 border rounded px-2 py-1">
            <option value="todos">Todos</option>
            <option value="sem_custo">Somente sem Custo</option>
            <option value="sem_imposto">Somente sem Imposto</option>
            <option value="sem_custo_imposto">Somente sem Custo e Imposto</option>
          </select>
        </label>
        <label className="text-xs flex items-center gap-2 mt-4">
          <input type="checkbox" checked={filtros.considerar_frete_comprador}
                 onChange={(e) => set('considerar_frete_comprador', e.target.checked)} />
          Considerar frete comprador
        </label>
      </div>
      <button onClick={() => onBuscar(filtros)} disabled={loading}
              className="mt-3 px-4 py-2 bg-violet-600 text-white rounded hover:bg-violet-700 disabled:opacity-50">
        {loading ? 'Buscando…' : 'Buscar'}
      </button>
    </div>
  )
}
