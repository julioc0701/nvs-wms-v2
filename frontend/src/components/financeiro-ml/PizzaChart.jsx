import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts'

const COLORS = {
  Custo: '#f97316',
  Imposto: '#dc2626',
  Tarifa: '#eab308',
  Frete: '#3b82f6',
  MC: '#10b981',
}

export function PizzaChart({ pizza }) {
  if (!pizza || pizza.length === 0) {
    return <div className="text-gray-400 text-sm">Sem dados pra exibir.</div>
  }
  const data = pizza.map((s) => ({ name: s.label, value: parseFloat(s.valor), pct: s.pct }))

  return (
    <div className="border rounded-lg p-4 bg-white">
      <h3 className="text-sm font-semibold mb-2">Representação Gráfica</h3>
      <ResponsiveContainer width="100%" height={240}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90}
               label={(d) => `${d.pct.toFixed(1)}%`}>
            {data.map((d) => (
              <Cell key={d.name} fill={COLORS[d.name] || '#888'} />
            ))}
          </Pie>
          <Tooltip formatter={(v) => `R$ ${v.toFixed(2)}`} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
      <p className="text-xs text-gray-500 mt-2">* O frete pago pelo comprador não é considerado no gráfico.</p>
    </div>
  )
}
