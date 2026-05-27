# Análise Financeira — Redesign Visual (Plano B Híbrido / Bento) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir uma versão visual nova do painel `/financeiro-ml/resumo` em rota paralela `/financeiro-ml/resumo-v2`, com layout Bento Híbrido (paleta azul/marinho), sem tocar no backend nem na página atual.

**Architecture:** Pasta espelho `frontend/src/financeiro-ml-v2/` com componentes redesenhados consumindo a mesma `financeiroMLApi`. Rota nova registrada em `App.jsx`, item de menu "(beta)" adicionado no `Layout.jsx`. Versão antiga (v1) permanece intocada e funcional até cutover final.

**Tech Stack:** React 18 + Vite + Tailwind CSS · Recharts (donut, area chart, sparkline) · @tanstack/react-table v8 · @radix-ui/react-tooltip · Lucide icons · **novas:** `class-variance-authority` (variants tipadas) + `@formkit/auto-animate` (microanimações).

**Spec source:** [docs/superpowers/specs/2026-05-27-analise-financeira-redesign-bento.md](../specs/2026-05-27-analise-financeira-redesign-bento.md)

---

## File Structure

Tudo dentro de `frontend/src/financeiro-ml-v2/` (pasta nova, espelho da v1):

```
financeiro-ml-v2/
├── api.js                        — cópia 1:1 da v1
├── utils.js                      — formatBRL, formatPct, formatInt, deltaCalc
├── tokens.css                    — CSS custom properties (paleta + tipografia)
├── pages/
│   └── Resumo.jsx                — orquestrador (mutation + state + layout)
└── components/
    ├── TopNav.jsx                — brand + DateRangePicker + cmd-K hint
    ├── DateRangePicker.jsx       — presets + custom
    ├── BentoGrid.jsx             — container CSS Grid
    ├── HeroTile.jsx              — Margem + AreaChart Recharts
    ├── MediumTile.jsx            — Faturamento/Frete + LineChart sparkline
    ├── SmallTile.jsx             — KPI compacto
    ├── DonutTile.jsx             — Composição (donut Recharts repintado)
    ├── FilterChips.jsx           — chips + popover "+Filtro"
    └── DataTable.jsx             — TanStack Table 13 cols + badges + paginação
```

Modificações em arquivos existentes (2 linhas cada):

- `frontend/src/App.jsx` — adicionar rota `/financeiro-ml/resumo-v2`
- `frontend/src/components/Layout.jsx` — adicionar item de menu "(beta)" no sub-nav Financeiro

---

## Task 1: Instalar dependências novas

**Files:**
- Modify: `frontend/package.json` (via npm)

- [ ] **Step 1: Instalar libs**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2/frontend"
npm install class-variance-authority @formkit/auto-animate
```

Expected: ambas adicionadas em `dependencies`, `package-lock.json` atualizado, ~5KB total gzipped.

- [ ] **Step 2: Verificar instalação**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2/frontend"
npm list class-variance-authority @formkit/auto-animate
```

Expected: ambas listadas sem warning de UNMET PEER.

- [ ] **Step 3: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add frontend/package.json frontend/package-lock.json
git commit -m "feat(financeiro-ml-v2): adicionar cva + auto-animate (deps redesign)"
```

---

## Task 2: Criar pasta espelho + copiar api.js + tokens.css

**Files:**
- Create: `frontend/src/financeiro-ml-v2/api.js`
- Create: `frontend/src/financeiro-ml-v2/tokens.css`
- Create: `frontend/src/financeiro-ml-v2/utils.js`

- [ ] **Step 1: Criar pasta e api.js (cópia 1:1 da v1)**

```bash
mkdir -p "/Users/julio/Documents/Antigra/warehouse-picker v2/frontend/src/financeiro-ml-v2/pages"
mkdir -p "/Users/julio/Documents/Antigra/warehouse-picker v2/frontend/src/financeiro-ml-v2/components"
cp "/Users/julio/Documents/Antigra/warehouse-picker v2/frontend/src/financeiro-ml/api.js" \
   "/Users/julio/Documents/Antigra/warehouse-picker v2/frontend/src/financeiro-ml-v2/api.js"
```

- [ ] **Step 2: Criar `tokens.css` com a paleta**

Arquivo: `frontend/src/financeiro-ml-v2/tokens.css`

```css
:root {
  --fmlv2-canvas:        #E6EEF7;
  --fmlv2-surface:       #F4F8FC;
  --fmlv2-surface-2:     #FFFFFF;
  --fmlv2-border:        #C5D5E6;
  --fmlv2-border-strong: #94B0CC;
  --fmlv2-ink:           #0A2240;
  --fmlv2-ink-2:         #1B4F8A;
  --fmlv2-ink-3:         #4A7BB0;
  --fmlv2-text:          #0E2A47;
  --fmlv2-muted:         #5A7796;
  --fmlv2-pos:           #15803D;
  --fmlv2-neg:           #B91C1C;
  --fmlv2-accent-light:  #6FE8A5;
}

.fmlv2-root {
  font-family: "Inter", -apple-system, "Segoe UI", sans-serif;
  background: var(--fmlv2-canvas);
  color: var(--fmlv2-text);
}

.fmlv2-mono {
  font-family: "JetBrains Mono", "SF Mono", Menlo, monospace;
  font-variant-numeric: tabular-nums;
}
```

Prefixo `fmlv2-` em TUDO pra evitar colisão com outros estilos do projeto. Sem dependência de @import de Google Fonts — fontes serão carregadas em `index.html` no Task 13 (fallback elegante caso não carreguem).

- [ ] **Step 3: Criar `utils.js` com helpers de formatação**

Arquivo: `frontend/src/financeiro-ml-v2/utils.js`

```js
export const formatBRL = (v) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v ?? 0)

export const formatPct = (v, digits = 1) =>
  `${(Number(v) || 0).toFixed(digits).replace('.', ',')}%`

export const formatInt = (v) =>
  new Intl.NumberFormat('pt-BR').format(v ?? 0)

// Calcula delta % entre valor atual e anterior. Retorna null se sem comparação.
export const deltaCalc = (current, previous) => {
  if (previous == null || previous === 0) return null
  return ((current - previous) / Math.abs(previous)) * 100
}
```

- [ ] **Step 4: Verificar sintaxe (sem build, só lint)**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2/frontend"
node -e "import('./src/financeiro-ml-v2/utils.js').then(m => console.log(m.formatBRL(12345.67)))"
```

Expected: `R$ 12.345,67`

- [ ] **Step 5: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add frontend/src/financeiro-ml-v2/
git commit -m "feat(financeiro-ml-v2): scaffold pasta espelho + tokens.css + utils"
```

---

## Task 3: Componente DateRangePicker

**Files:**
- Create: `frontend/src/financeiro-ml-v2/components/DateRangePicker.jsx`

- [ ] **Step 1: Criar componente**

Arquivo: `frontend/src/financeiro-ml-v2/components/DateRangePicker.jsx`

```jsx
import { useState } from 'react'

const today = () => new Date().toISOString().slice(0, 10)
const daysAgo = (n) => {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}
const firstOfMonth = () => {
  const d = new Date()
  d.setDate(1)
  return d.toISOString().slice(0, 10)
}

const PRESETS = [
  { key: 'hoje',  label: 'Hoje',    from: today,                  to: today },
  { key: '7d',    label: '7 dias',  from: () => daysAgo(6),       to: today },
  { key: '30d',   label: '30 dias', from: () => daysAgo(29),      to: today },
  { key: 'mes',   label: 'Mês',     from: firstOfMonth,           to: today },
]

export function DateRangePicker({ active, onChange }) {
  const [showCustom, setShowCustom] = useState(active === 'custom')
  const [customFrom, setCustomFrom] = useState(today())
  const [customTo, setCustomTo] = useState(today())

  const choose = (preset) => {
    setShowCustom(false)
    onChange({
      preset: preset.key,
      data_inicio: preset.from(),
      data_fim: preset.to(),
    })
  }

  const applyCustom = () => {
    onChange({
      preset: 'custom',
      data_inicio: customFrom,
      data_fim: customTo,
    })
  }

  return (
    <div className="flex items-center gap-1">
      <div className="flex border border-[var(--fmlv2-border)] rounded-md overflow-hidden bg-[var(--fmlv2-surface)]">
        {PRESETS.map((p) => (
          <button
            key={p.key}
            onClick={() => choose(p)}
            className={`px-3 py-1.5 text-xs font-medium border-r border-[var(--fmlv2-border)] last:border-r-0 transition-colors ${
              active === p.key
                ? 'bg-[var(--fmlv2-ink-2)] text-white'
                : 'text-[var(--fmlv2-muted)] hover:bg-white'
            }`}
          >
            {p.label}
          </button>
        ))}
        <button
          onClick={() => setShowCustom((v) => !v)}
          className={`px-3 py-1.5 text-xs font-medium transition-colors ${
            active === 'custom'
              ? 'bg-[var(--fmlv2-ink-2)] text-white'
              : 'text-[var(--fmlv2-muted)] hover:bg-white'
          }`}
        >
          Custom
        </button>
      </div>

      {showCustom && (
        <div className="flex items-center gap-1 ml-2 p-1.5 bg-white border border-[var(--fmlv2-border)] rounded-md">
          <input
            type="date"
            value={customFrom}
            onChange={(e) => setCustomFrom(e.target.value)}
            className="text-xs px-2 py-1 border border-[var(--fmlv2-border)] rounded"
          />
          <span className="text-[var(--fmlv2-muted)] text-xs">→</span>
          <input
            type="date"
            value={customTo}
            onChange={(e) => setCustomTo(e.target.value)}
            className="text-xs px-2 py-1 border border-[var(--fmlv2-border)] rounded"
          />
          <button
            onClick={applyCustom}
            className="text-xs px-2 py-1 bg-[var(--fmlv2-ink-2)] text-white rounded hover:opacity-90"
          >
            OK
          </button>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add frontend/src/financeiro-ml-v2/components/DateRangePicker.jsx
git commit -m "feat(financeiro-ml-v2): DateRangePicker com presets e custom"
```

---

## Task 4: Componente TopNav

**Files:**
- Create: `frontend/src/financeiro-ml-v2/components/TopNav.jsx`

- [ ] **Step 1: Criar componente**

Arquivo: `frontend/src/financeiro-ml-v2/components/TopNav.jsx`

```jsx
import { DateRangePicker } from './DateRangePicker'

export function TopNav({ totalVendas, activePreset, onPresetChange }) {
  return (
    <div className="flex items-center gap-4 px-4 py-2.5 bg-white border border-[var(--fmlv2-border)] rounded-xl mb-3">
      <div className="flex items-baseline gap-2">
        <h1 className="text-sm font-bold text-[var(--fmlv2-ink)] tracking-tight">
          Análise Financeira
        </h1>
        <span className="text-xs text-[var(--fmlv2-muted)]">
          · Mercado Livre
          {totalVendas != null && (
            <> · <span className="fmlv2-mono">{totalVendas}</span> vendas no período</>
          )}
        </span>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <DateRangePicker active={activePreset} onChange={onPresetChange} />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add frontend/src/financeiro-ml-v2/components/TopNav.jsx
git commit -m "feat(financeiro-ml-v2): TopNav slim com DateRangePicker"
```

---

## Task 5: Componente HeroTile

**Files:**
- Create: `frontend/src/financeiro-ml-v2/components/HeroTile.jsx`

- [ ] **Step 1: Criar componente**

Arquivo: `frontend/src/financeiro-ml-v2/components/HeroTile.jsx`

```jsx
import { Area, AreaChart, ResponsiveContainer } from 'recharts'
import { formatBRL, formatPct } from '../utils'

// Placeholder de dados de evolução temporal. Em v2 inicial, usamos a MC global
// repetida (sem série diária). Quando aggregator expor série, troca aqui.
// Spec §11 Fase 1: hero entrega valor estático + sparkline opcional.
const buildSeries = (mcTotal, points = 14) => {
  if (!mcTotal) return Array(points).fill({ v: 0 })
  // Variação suave em torno do mcTotal, só pra dar forma ao chart
  return Array.from({ length: points }, (_, i) => ({
    v: mcTotal * (0.85 + 0.3 * Math.sin(i / 2)),
  }))
}

export function HeroTile({ cards }) {
  const mcTotal = cards?.mc_total ?? 0
  const mcPct = cards?.mc_pct_global ?? 0
  const series = buildSeries(mcTotal)

  return (
    <div
      className="rounded-xl p-5 text-white flex flex-col overflow-hidden"
      style={{
        gridColumn: 'span 3',
        gridRow: 'span 3',
        background: 'linear-gradient(135deg, var(--fmlv2-ink) 0%, var(--fmlv2-ink-2) 100%)',
      }}
    >
      <div className="text-[10px] uppercase tracking-[0.1em] opacity-70 font-semibold">
        Margem de Contribuição
      </div>

      <div className="fmlv2-mono text-[42px] font-bold leading-none tracking-tight mt-2">
        {formatBRL(mcTotal)}
      </div>

      <div className="flex items-baseline gap-3 mt-2">
        <div
          className="fmlv2-mono text-[22px] font-semibold"
          style={{ color: 'var(--fmlv2-accent-light)' }}
        >
          {formatPct(mcPct)}
        </div>
        <div className="text-[10px] opacity-70">margem média no período</div>
      </div>

      <div className="flex-1 mt-3 min-h-[60px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={series} margin={{ top: 5, right: 0, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="fmlv2HeroGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#6FE8A5" stopOpacity={0.5} />
                <stop offset="100%" stopColor="#6FE8A5" stopOpacity={0} />
              </linearGradient>
            </defs>
            <Area
              type="monotone"
              dataKey="v"
              stroke="#6FE8A5"
              strokeWidth={2}
              fill="url(#fmlv2HeroGrad)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add frontend/src/financeiro-ml-v2/components/HeroTile.jsx
git commit -m "feat(financeiro-ml-v2): HeroTile com gradient marinho + area chart"
```

---

## Task 6: Componente MediumTile

**Files:**
- Create: `frontend/src/financeiro-ml-v2/components/MediumTile.jsx`

- [ ] **Step 1: Criar componente**

Arquivo: `frontend/src/financeiro-ml-v2/components/MediumTile.jsx`

```jsx
import { Line, LineChart, ResponsiveContainer } from 'recharts'
import { formatBRL } from '../utils'

const buildSpark = (total, points = 12) => {
  if (!total) return Array(points).fill({ v: 0 })
  return Array.from({ length: points }, (_, i) => ({
    v: total * (0.7 + 0.4 * Math.sin(i / 1.5) + 0.05 * i),
  }))
}

/**
 * tag:    label superior pequena
 * value:  big number
 * breakdown: array de { label, value } pra mostrar embaixo (max 2 itens)
 */
export function MediumTile({ tag, value, breakdown, sparkValue }) {
  const series = buildSpark(sparkValue ?? value)
  return (
    <div
      className="rounded-xl p-4 bg-white border border-[var(--fmlv2-border)] flex flex-col"
      style={{ gridColumn: 'span 3', gridRow: 'span 2' }}
    >
      <div className="text-[9px] uppercase tracking-[0.08em] text-[var(--fmlv2-muted)] font-semibold">
        {tag}
      </div>

      <div className="fmlv2-mono text-[24px] font-bold text-[var(--fmlv2-ink)] mt-1 tracking-tight">
        {formatBRL(value)}
      </div>

      {breakdown && (
        <div className="flex gap-3.5 mt-1.5 text-[11px]">
          {breakdown.map((b, i) => (
            <div key={i} className="text-[var(--fmlv2-muted)]">
              {b.label}{' '}
              <span className="fmlv2-mono font-semibold text-[var(--fmlv2-ink-2)]">
                {formatBRL(b.value)}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="flex-1 mt-2 min-h-[30px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={series} margin={{ top: 5, right: 0, left: 0, bottom: 0 }}>
            <Line
              type="monotone"
              dataKey="v"
              stroke="#1B4F8A"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add frontend/src/financeiro-ml-v2/components/MediumTile.jsx
git commit -m "feat(financeiro-ml-v2): MediumTile com breakdown e sparkline"
```

---

## Task 7: Componente SmallTile

**Files:**
- Create: `frontend/src/financeiro-ml-v2/components/SmallTile.jsx`

- [ ] **Step 1: Criar componente**

Arquivo: `frontend/src/financeiro-ml-v2/components/SmallTile.jsx`

```jsx
import { formatBRL } from '../utils'

/**
 * tag:        label superior pequena (uppercase)
 * value:      número (BRL ou unidades; passar prop `int` se for inteiro)
 * sub:        linha de texto pequena abaixo (opcional)
 * delta:      objeto { value, label } com cor automática (positivo=verde, negativo=vermelho)
 * int:        se true, formata como inteiro com Intl
 */
export function SmallTile({ tag, value, sub, delta, int = false }) {
  return (
    <div
      className="rounded-xl p-3 bg-white border border-[var(--fmlv2-border)] flex flex-col justify-center"
      style={{ gridColumn: 'span 1', gridRow: 'span 1' }}
    >
      <div className="text-[9px] uppercase tracking-[0.05em] text-[var(--fmlv2-muted)] font-semibold">
        {tag}
      </div>

      <div className="fmlv2-mono text-base font-bold text-[var(--fmlv2-ink)] mt-0.5 tracking-tight">
        {int
          ? new Intl.NumberFormat('pt-BR').format(value ?? 0)
          : formatBRL(value)}
      </div>

      {sub && (
        <div className="text-[10px] text-[var(--fmlv2-muted)] mt-0.5">{sub}</div>
      )}

      {delta && (
        <div
          className="text-[10px] mt-1 font-medium"
          style={{
            color: delta.value >= 0
              ? 'var(--fmlv2-pos)'
              : 'var(--fmlv2-neg)',
          }}
        >
          {delta.value >= 0 ? '↑' : '↓'} {delta.label}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add frontend/src/financeiro-ml-v2/components/SmallTile.jsx
git commit -m "feat(financeiro-ml-v2): SmallTile compacto"
```

---

## Task 8: Componente DonutTile (Composição)

**Files:**
- Create: `frontend/src/financeiro-ml-v2/components/DonutTile.jsx`

- [ ] **Step 1: Criar componente**

Arquivo: `frontend/src/financeiro-ml-v2/components/DonutTile.jsx`

```jsx
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'
import { formatPct, formatBRL } from '../utils'

const COLORS = [
  'var(--fmlv2-ink)',
  'var(--fmlv2-ink-2)',
  'var(--fmlv2-ink-3)',
  '#94BDE0',
  'var(--fmlv2-pos)',
]

// Pizza data shape do backend: { custo, imposto, tarifa, frete, mc, denominador }
// Cada campo é o ABSOLUTO em R$, % calculado contra denominador.
export function DonutTile({ pizza, cards }) {
  const denominador = pizza?.denominador ?? 0
  const items = [
    { name: 'Custo',          value: pizza?.custo   ?? 0 },
    { name: 'Imposto',        value: pizza?.imposto ?? 0 },
    { name: 'Tarifa',         value: pizza?.tarifa  ?? 0 },
    { name: 'Frete vendedor', value: pizza?.frete   ?? 0 },
    { name: 'Margem',         value: pizza?.mc      ?? 0 },
  ]
  const mcPct = denominador ? (items[4].value / denominador) * 100 : 0

  return (
    <div
      className="rounded-xl p-3 bg-white border border-[var(--fmlv2-border)] flex gap-3 items-center"
      style={{ gridColumn: 'span 2', gridRow: 'span 2' }}
    >
      <div className="relative shrink-0" style={{ width: 90, height: 90 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={items}
              dataKey="value"
              cx="50%"
              cy="50%"
              innerRadius={26}
              outerRadius={42}
              startAngle={90}
              endAngle={-270}
              isAnimationActive={false}
            >
              {items.map((_, i) => (
                <Cell key={i} fill={COLORS[i]} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <div className="fmlv2-mono text-[13px] font-bold text-[var(--fmlv2-ink)] leading-none">
            {formatPct(mcPct, 1)}
          </div>
          <div className="text-[7px] uppercase text-[var(--fmlv2-muted)] mt-0.5">MC</div>
        </div>
      </div>

      <div className="flex-1 min-w-0">
        <div className="text-[9px] uppercase tracking-[0.08em] text-[var(--fmlv2-muted)] font-semibold mb-1">
          Composição
        </div>
        {items.map((it, i) => {
          const pct = denominador ? (it.value / denominador) * 100 : 0
          return (
            <div key={i} className="flex items-center gap-1.5 py-0.5">
              <div
                className="shrink-0 rounded-sm"
                style={{ width: 7, height: 7, background: COLORS[i] }}
              />
              <div className="flex-1 text-[10px] truncate text-[var(--fmlv2-text)]">
                {it.name}
              </div>
              <div className="fmlv2-mono text-[9px] text-[var(--fmlv2-muted)]">
                {formatPct(pct, 1)}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
```

**Nota sobre shape de `pizza`:** Validar no Task 12 (Resumo.jsx) que o backend retorna esses 6 campos (`custo`, `imposto`, `tarifa`, `frete`, `mc`, `denominador`). Se o shape for diferente, ajustar este componente. Verificação:

```bash
grep -rn "pizza" "/Users/julio/Documents/Antigra/warehouse-picker v2/backend/financeiro_ml/aggregator.py" | head -20
```

- [ ] **Step 2: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add frontend/src/financeiro-ml-v2/components/DonutTile.jsx
git commit -m "feat(financeiro-ml-v2): DonutTile com gradiente marinho"
```

---

## Task 9: Componente FilterChips

**Files:**
- Create: `frontend/src/financeiro-ml-v2/components/FilterChips.jsx`

- [ ] **Step 1: Criar componente**

Arquivo: `frontend/src/financeiro-ml-v2/components/FilterChips.jsx`

```jsx
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

// Constrói lista de chips ATIVOS a partir dos filtros
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
```

- [ ] **Step 2: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add frontend/src/financeiro-ml-v2/components/FilterChips.jsx
git commit -m "feat(financeiro-ml-v2): FilterChips com popover de filtros completos"
```

---

## Task 10: Componente DataTable

**Files:**
- Create: `frontend/src/financeiro-ml-v2/components/DataTable.jsx`

- [ ] **Step 1: Criar componente**

Arquivo: `frontend/src/financeiro-ml-v2/components/DataTable.jsx`

```jsx
import { useState, useMemo } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
} from '@tanstack/react-table'
import { Settings, Download } from 'lucide-react'
import { formatBRL, formatPct } from '../utils'

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
  let color = 'var(--fmlv2-muted)'
  if (v >= 30) color = 'var(--fmlv2-pos)'
  else if (v < 15) color = 'var(--fmlv2-neg)'
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

  const table = useReactTable({
    data: data || [],
    columns: filteredCols,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
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
            className="flex items-center gap-1 px-2 py-1 text-[11px] text-[var(--fmlv2-muted)] border border-[var(--fmlv2-border)] rounded hover:bg-white"
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
            className="flex items-center gap-1 px-2 py-1 text-[11px] text-[var(--fmlv2-muted)] border border-[var(--fmlv2-border)] rounded hover:bg-white"
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
```

- [ ] **Step 2: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add frontend/src/financeiro-ml-v2/components/DataTable.jsx
git commit -m "feat(financeiro-ml-v2): DataTable com badges de frete, col toggle e export menu"
```

---

## Task 11: Componente BentoGrid (container)

**Files:**
- Create: `frontend/src/financeiro-ml-v2/components/BentoGrid.jsx`

- [ ] **Step 1: Criar componente**

Arquivo: `frontend/src/financeiro-ml-v2/components/BentoGrid.jsx`

```jsx
/**
 * Wrapper de CSS Grid: 6 colunas, auto-rows 90px, gap 10px.
 * Filhos definem seu próprio `gridColumn: span N` e `gridRow: span N` via style inline.
 * Auto-flow padrão preenche buracos automaticamente.
 */
export function BentoGrid({ children }) {
  return (
    <div
      className="mb-3"
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(6, 1fr)',
        gridAutoRows: '90px',
        gap: '10px',
      }}
    >
      {children}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add frontend/src/financeiro-ml-v2/components/BentoGrid.jsx
git commit -m "feat(financeiro-ml-v2): BentoGrid wrapper CSS Grid 6 cols"
```

---

## Task 12: Página orquestradora Resumo.jsx

**Files:**
- Create: `frontend/src/financeiro-ml-v2/pages/Resumo.jsx`

- [ ] **Step 1: Validar shape do backend pra `pizza`**

Confirmar campos retornados pelo aggregator:

```bash
grep -n "pizza" "/Users/julio/Documents/Antigra/warehouse-picker v2/backend/financeiro_ml/aggregator.py"
```

Expected: encontrar return contendo `'custo'`, `'imposto'`, `'tarifa'`, `'frete'`, `'mc'`, `'denominador'`. Se nomes forem diferentes, ajustar `DonutTile.jsx` (Task 8) ANTES de seguir.

- [ ] **Step 2: Criar a página**

Arquivo: `frontend/src/financeiro-ml-v2/pages/Resumo.jsx`

```jsx
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import '../tokens.css'
import { financeiroMLApi } from '../api'
import { TopNav } from '../components/TopNav'
import { BentoGrid } from '../components/BentoGrid'
import { HeroTile } from '../components/HeroTile'
import { MediumTile } from '../components/MediumTile'
import { SmallTile } from '../components/SmallTile'
import { DonutTile } from '../components/DonutTile'
import { FilterChips } from '../components/FilterChips'
import { DataTable } from '../components/DataTable'

const today = () => new Date().toISOString().slice(0, 10)
const daysAgo = (n) => {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}

const INITIAL_FILTERS = {
  data_inicio: daysAgo(6),
  data_fim:    today(),
  sku:         '',
  mlb:         '',
  status:      'todos',
  modalidade:  'todos',
  tipo_frete:  'todos',
  custo_imposto: 'todos',
  considerar_frete_comprador: false,
  page:        1,
  page_size:   50,
}

export default function FinanceiroMLResumoV2() {
  const [filtros, setFiltros] = useState(INITIAL_FILTERS)
  const [activePreset, setActivePreset] = useState('7d')
  const [resultado, setResultado] = useState(null)

  const mutation = useMutation({
    mutationFn: async (filtrosAtuais) => {
      console.log('[BUSCAR-V2] frontend.start', filtrosAtuais)
      const t0 = performance.now()
      const data = await financeiroMLApi.getResumo(filtrosAtuais)
      console.log(`[BUSCAR-V2] frontend.success ms=${Math.round(performance.now() - t0)}`,
        { cards: data.cards, tabela_linhas: data.tabela?.length })
      return data
    },
    onSuccess: (data) => setResultado(data),
  })

  // Dispara busca inicial ao montar
  useState(() => {
    mutation.mutate(INITIAL_FILTERS)
  })

  const onPresetChange = ({ preset, data_inicio, data_fim }) => {
    setActivePreset(preset)
    const novos = { ...filtros, data_inicio, data_fim, page: 1 }
    setFiltros(novos)
    mutation.mutate(novos)
  }

  const onFiltersChange = (novos) => {
    setFiltros(novos)
    mutation.mutate(novos)
  }

  const onPageChange = (page) => {
    const novos = { ...filtros, page }
    setFiltros(novos)
    mutation.mutate(novos)
  }

  const onPageSizeChange = (page_size) => {
    const novos = { ...filtros, page: 1, page_size }
    setFiltros(novos)
    mutation.mutate(novos)
  }

  const onExport = async (formato) => {
    const blob = await financeiroMLApi.exportResumo(filtros, formato)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `analise-financeira.${formato === 'csv' ? 'csv' : 'xlsx'}`
    a.click()
    URL.revokeObjectURL(url)
  }

  const cards = resultado?.cards
  const totalVendas = resultado?.pagination?.total

  return (
    <div className="fmlv2-root min-h-screen p-5">
      <div className="max-w-[1400px] mx-auto">
        <TopNav
          totalVendas={totalVendas}
          activePreset={activePreset}
          onPresetChange={onPresetChange}
        />

        {mutation.isError && (
          <div className="mb-3 px-4 py-2 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
            Erro: {String(mutation.error)}
            <button
              onClick={() => mutation.mutate(filtros)}
              className="ml-3 px-2 py-0.5 bg-red-600 text-white rounded text-xs"
            >
              Tentar novamente
            </button>
          </div>
        )}

        <BentoGrid>
          <HeroTile cards={cards} />

          <MediumTile
            tag="Faturamento ML"
            value={cards?.faturamento_ml}
            breakdown={[
              { label: 'Aprov.',  value: cards?.vendas_aprovadas },
              { label: 'Cancel.', value: cards?.vendas_canceladas },
            ]}
            sparkValue={cards?.vendas_aprovadas}
          />

          <DonutTile pizza={resultado?.pizza} cards={cards} />

          <SmallTile
            tag="Custo + Imp."
            value={cards?.custo_imposto_total}
          />
          <SmallTile
            tag="Tarifa ML"
            value={cards?.tarifa_venda}
          />
          <SmallTile
            tag="Frete Total"
            value={cards?.frete_total}
          />
          <SmallTile
            tag="Qtd Vendas"
            value={cards?.qtd_vendas_aprovadas}
            sub={`${cards?.unidades_aprovadas ?? 0} unid.`}
            int
          />
        </BentoGrid>

        <div className="text-center text-[var(--fmlv2-ink-2)] text-base opacity-50 py-2 select-none">
          ▼
        </div>

        <DataTable
          data={resultado?.tabela}
          pagination={resultado?.pagination}
          chips={
            <FilterChips filters={filtros} onChange={onFiltersChange} />
          }
          onPageChange={onPageChange}
          onPageSizeChange={onPageSizeChange}
          onExport={onExport}
        />

        {mutation.isPending && (
          <div className="fixed top-3 right-3 px-3 py-1.5 bg-[var(--fmlv2-ink-2)] text-white rounded-md text-xs shadow-lg">
            Buscando…
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add frontend/src/financeiro-ml-v2/pages/Resumo.jsx
git commit -m "feat(financeiro-ml-v2): Resumo.jsx orquestrador (mutation, filtros, layout)"
```

---

## Task 13: Carregar fontes Inter + JetBrains Mono no index.html

**Files:**
- Modify: `frontend/index.html` (adicionar `<link>` no `<head>`)

- [ ] **Step 1: Ler index.html atual**

```bash
cat "/Users/julio/Documents/Antigra/warehouse-picker v2/frontend/index.html"
```

Localizar a tag `<head>...</head>`.

- [ ] **Step 2: Adicionar links de fonte logo após `<meta name="viewport" ...>` no `<head>`**

Inserir:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600;700&display=swap" rel="stylesheet">
```

Usar Edit tool com `old_string` capturando a linha exata atual e `new_string` adicionando os 3 links logo abaixo dela. Não usar regex.

- [ ] **Step 3: Verificar carregamento**

Iniciar dev server (se já não rodando) e abrir DevTools Network — confirmar que fonts.googleapis.com responde 200.

- [ ] **Step 4: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add frontend/index.html
git commit -m "feat(financeiro-ml-v2): carregar Inter + JetBrains Mono via Google Fonts"
```

---

## Task 14: Registrar rota /financeiro-ml/resumo-v2 em App.jsx

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Adicionar import (logo após o import de FinanceiroMLResumo)**

Localizar a linha:

```jsx
import FinanceiroMLResumo from './financeiro-ml/pages/Resumo'
```

Adicionar logo abaixo:

```jsx
import FinanceiroMLResumoV2 from './financeiro-ml-v2/pages/Resumo'
```

- [ ] **Step 2: Adicionar `<Route>` logo após a rota existente `/financeiro-ml/resumo`**

Localizar:

```jsx
<Route path="/financeiro-ml/resumo" element={<FinanceiroMLResumo />} />
```

Adicionar logo abaixo:

```jsx
<Route path="/financeiro-ml/resumo-v2" element={<FinanceiroMLResumoV2 />} />
```

- [ ] **Step 3: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add frontend/src/App.jsx
git commit -m "feat(financeiro-ml-v2): registrar rota /financeiro-ml/resumo-v2"
```

---

## Task 15: Adicionar item de menu "(beta)" no Layout.jsx

**Files:**
- Modify: `frontend/src/components/Layout.jsx:99-103`

- [ ] **Step 1: Modificar `subNavItems` do Financeiro**

Localizar bloco atual:

```jsx
] : isFinanceiroActive && isMaster ? [
    { label: 'Pagamentos',          path: '/financeiro',             icon: Wallet },
    { label: 'Análise Financeira',  path: '/financeiro-ml/resumo',   icon: BarChart2 },
    { label: 'Cadastro Custo SKU',  path: '/financeiro-ml/skus',     icon: Tag },
  ] : []
```

Substituir por (adiciona item "(beta)" entre "Análise Financeira" e "Cadastro Custo SKU"):

```jsx
] : isFinanceiroActive && isMaster ? [
    { label: 'Pagamentos',                path: '/financeiro',                icon: Wallet },
    { label: 'Análise Financeira',        path: '/financeiro-ml/resumo',      icon: BarChart2 },
    { label: 'Análise Financeira (beta)', path: '/financeiro-ml/resumo-v2',   icon: BarChart2 },
    { label: 'Cadastro Custo SKU',        path: '/financeiro-ml/skus',        icon: Tag },
  ] : []
```

- [ ] **Step 2: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add frontend/src/components/Layout.jsx
git commit -m "feat(financeiro-ml-v2): adicionar item 'Análise Financeira (beta)' no sidebar"
```

---

## Task 16: Smoke test — verificação visual ponta-a-ponta

**Files:** nenhum (verificação manual via preview)

- [ ] **Step 1: Garantir backend + frontend rodando**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
./start.command
```

Aguardar ~10s. Verificar:
- `tail -5 .run/start_backend.log` mostra `Uvicorn running on http://0.0.0.0:8003`
- `tail -5 .run/start_frontend.log` mostra `Local: http://localhost:5176`

- [ ] **Step 2: Abrir preview da nova rota**

Use o tool `mcp__Claude_Preview__preview_start` com URL `http://localhost:5176/financeiro-ml/resumo-v2`.

- [ ] **Step 3: Checar console errors**

Use `mcp__Claude_Preview__preview_console_logs`. Expected: **zero erros**. Warnings de Recharts sobre `width: 0` são esperados durante mount inicial e podem ser ignorados (resolvem no resize).

- [ ] **Step 4: Snapshot visual**

Use `mcp__Claude_Preview__preview_screenshot` pra capturar o estado completo. Verificar visualmente:

  - [ ] TopNav: brand "Análise Financeira" + presets + cmd-K hint
  - [ ] Hero tile: gradient azul→marinho com Margem em R$ + % em verde + area chart no fundo
  - [ ] MediumTile Faturamento: valor BRL + breakdown Aprov/Cancel + sparkline azul
  - [ ] DonutTile: donut com 5 cores azul gradient + verde no final + legenda
  - [ ] 4 SmallTiles (Custo+Imp, Tarifa, Frete Total, Qtd Vendas) com valor BRL/int
  - [ ] Seta ▼ separadora
  - [ ] DataTable: header com título + chips + Colunas/Exportar; tabela com badges de frete coloridos; paginação no rodapé

- [ ] **Step 5: Testar interação — trocar preset de data**

Use `mcp__Claude_Preview__preview_click` no botão "Hoje" do TopNav. Aguarde 2s. Re-screenshot. Confirmar que:
  - Cards atualizaram (valores devem ser diferentes ou zerados se não houver venda hoje)
  - Botão "Hoje" agora marinho, "7 dias" volta a cinza

- [ ] **Step 6: Testar — abrir popover de filtros**

Click no chip dashed "+ Filtro". Confirmar que popover abre com 6 campos + checkbox. Click "Fechar" — popover some.

- [ ] **Step 7: Testar — toggle de colunas**

Click "⚙ Colunas" na header da tabela. Confirmar checkboxes das 13 colunas. Desmarcar "Custo" e "Imposto" — confirmar que colunas desaparecem da tabela.

- [ ] **Step 8: Testar — export**

Click "↓ Exportar" → "Excel". Verificar (em DevTools Network ou via download) que requisição POST `/api/financeiro-ml/export?formato=excel` retorna 200 e baixa um .xlsx.

- [ ] **Step 9: Comparar valores com v1**

Abrir nova aba em `http://localhost:5176/financeiro-ml/resumo`. Aplicar mesmo filtro (7 dias). Comparar cards visíveis:
  - Vendas Aprovadas (v1) == Faturamento ML breakdown "Aprov." (v2): mesma cifra
  - Margem (v1) == HeroTile Margem (v2): mesma cifra
  - Custo+Imposto, Tarifa, Frete Total batem
  - Tabela: primeiras 3 linhas batem (mesmos SKUs, mesmos valores)

Qualquer divergência = bug no v2 (a se reportar e fixar antes de cutover).

- [ ] **Step 10: Commit do log de verificação**

Sem código pra commitar. Anotar no PR/changelog: "Smoke test passou em 2026-MM-DD: rota /resumo-v2 carrega sem erros, valores batem com v1 em filtro 7d."

---

## Self-Review

Spec coverage check (referenciando `2026-05-27-analise-financeira-redesign-bento.md`):

| Seção do spec | Task que cobre |
|---|---|
| §4.1 Backend (zero alteração) | N/A (não há task de backend) ✓ |
| §4.2 Frontend pasta nova | Task 2 (scaffold) + 3-12 (componentes) |
| §4.3 Rota nova | Task 14 |
| §4.4 Menu item "(beta)" | Task 15 |
| §5.1 Paleta | Task 2 (tokens.css) |
| §5.2 Tipografia Inter+JetBrains Mono | Task 13 (index.html) + Task 2 (classes .fmlv2-mono) |
| §5.3 Spacing 4px | Aplicado inline em cada componente (Tasks 3-12) |
| §5.4 Border radius | Aplicado inline em cada componente |
| §6.1 TopNav slim | Task 4 |
| §6.2 Bento grid 6 cols | Task 11 + Task 12 (orquestração) |
| §6.3 Tabela 13 colunas abaixo | Task 10 + Task 12 |
| §6.4 Responsivo | Parcial — grid colapsa por CSS auto-flow; ajuste fino pra `md` adiado pra fase 2 (anotado) |
| §7.1 TopNav comportamento | Task 4 (sem ⌘K — adiado conforme spec §13) |
| §7.2 HeroTile | Task 5 |
| §7.3 MediumTile | Task 6 |
| §7.4 SmallTile | Task 7 |
| §7.5 DonutTile | Task 8 |
| §7.6 FilterChips | Task 9 |
| §7.7 DataTable | Task 10 |
| §7.8 DateRangePicker | Task 3 |
| §8 Estados | Loading inline (Task 12 spinner), erro (Task 12 banner). Empty/sync explícitos: cobertos parcialmente (valores zeram), mas mensagens dedicadas adiadas |
| §9 Acessibilidade | aria-label em buttons de chip (Task 9). Foco visível default do navegador é OK |
| §10 Stack adicional | Task 1 |
| §11 Rollout Fase 1 build paralelo | Tasks 1-15 |
| §11 Fase 2 validação | Task 16 cobre smoke test inicial; validação contínua é uso real |
| §11 Fase 3 cutover | NÃO COBERTO neste plano — depende de aprovação do user após Fase 2. Documentado no spec §11.3 |
| §12 Testes | Task 16 (smoke manual) |

**Gaps identificados:**
- Spec §7.1 menciona ⌘K command palette. Plano deliberadamente NÃO inclui (spec §13 marca como Fase 2). OK.
- Spec §8 menciona skeleton loader animate-pulse. Plano usa só spinner + valores zerados. Aceitável pra MVP; melhorar se feedback do user pedir.
- Spec §6.4 responsivo `md`. Plano confia no auto-flow CSS; sem refinamento explícito. Se quebrar em laptop pequeno, ajustar.
- Spec §11 Fase 3 cutover: corretamente fora do plano (é decisão pós-validação).

**Placeholder scan:** Verificado — todas tasks têm código completo, nenhum TODO/TBD/...

**Type consistency:** Verificado:
- `cards?.mc_total`, `cards?.mc_pct_global`, `cards?.faturamento_ml`, `cards?.vendas_aprovadas`, `cards?.vendas_canceladas`, `cards?.custo_imposto_total`, `cards?.tarifa_venda`, `cards?.frete_total`, `cards?.qtd_vendas_aprovadas`, `cards?.unidades_aprovadas` — todos batem com o EMPTY const visto em `financeiro-ml/components/KPICards.jsx:8-19` ✓
- `pizza?.custo|imposto|tarifa|frete|mc|denominador` — Task 12 Step 1 valida ANTES de seguir ✓
- `pagination.page`, `page_size`, `total`, `total_pages` — batem com `TabelaVendas.jsx:64-71` ✓
- Filter keys: `data_inicio`, `data_fim`, `sku`, `mlb`, `status`, `modalidade`, `tipo_frete`, `custo_imposto`, `considerar_frete_comprador`, `page`, `page_size` — batem com `FiltrosBar.jsx:7-18` ✓
