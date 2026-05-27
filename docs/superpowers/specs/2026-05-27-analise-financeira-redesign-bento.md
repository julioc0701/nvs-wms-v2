# Análise Financeira — Redesign Visual (Plano B Híbrido / Bento)

**Data:** 2026-05-27
**Branch atual:** `feature/financeiro-ml`
**Status:** Spec aprovado pendente · plano de implementação não escrito ainda
**Motivação:** Eliminar risco jurídico de plágio visual do Mercado Turbo

---

## 1. Objetivo

Redesenhar **apenas o visual** do painel `Análise Financeira — Mercado Livre` (rota atual `/financeiro-ml/resumo`) para que ele deixe de parecer cópia do SaaS Mercado Turbo, mantendo **100% da funcionalidade, dos dados exibidos e do backend**.

A nova versão é entregue em **rota paralela** (`/financeiro-ml/resumo-v2`) numa **pasta espelho** isolada. Versão atual (v1) permanece intocada e funcional durante todo o processo. Após validação do user, v1 é desativada em commit único.

## 2. Fora de escopo

Não faz parte deste trabalho:

- Qualquer alteração em `backend/financeiro_ml/` (router, sync, aggregator, client, sku_service, models)
- Adição, remoção ou alteração de KPIs, filtros ou colunas de tabela
- Mudança de endpoints REST consumidos
- Fix do bug 8 (SKU variação) — projeto separado
- Auth real Master — projeto separado
- Cadastro SKU page (`/financeiro-ml/skus`) — fora deste redesign
- Mobile-first ou PWA — desktop continua único alvo

## 3. Risco mitigado

O painel v1 é estruturalmente e visualmente quase idêntico ao Mercado Turbo:

- Fundo azul-claro pastel
- 5 KPI cards coloridos rainbow no topo (rosa/laranja/amarelo/azul/verde)
- 5 cards brancos secundários abaixo
- Bloco "Filtrar Busca" branco com 8 inputs
- Donut "Representação Gráfica" 5 fatias à direita
- Tabela 15 colunas embaixo
- Botões verde "Exportar Excel" / azul "Exportar CSV"

O redesign quebra essa identidade visual mantendo todos os dados. Diferenciação acontece em 3 eixos:

1. **Hierarquia**: deixa de tratar 10 KPIs como iguais. Hero gigante (Margem) + tiles assimétricos.
2. **Layout**: deixa de ser linear top-down. Bento grid (Apple/Linear/Stripe Atlas 2024-26).
3. **Paleta**: deixa de ser pastel-rainbow. Monocromática azul/marinho com gradient hero, sparklines verdes/vermelhos discretos pra deltas.

## 4. Arquitetura de coexistência

Estratégia: **rota nova + pasta espelho**. Sem feature flag, sem context provider, sem branching condicional. Karpathy: cópia de arquivos é mais auditável que abstração.

### 4.1 Backend
Zero alteração. Endpoints REST atuais servem v1 e v2 simultaneamente:

- `POST /api/financeiro-ml/resumo`
- `GET /api/financeiro-ml/skus`
- `POST /api/financeiro-ml/export`
- (todos os outros já existentes)

### 4.2 Frontend — pasta nova

```
frontend/src/financeiro-ml-v2/           ← pasta espelho nova
├── api.js                                ← cópia 1:1 de financeiro-ml/api.js (mesmos wrappers fetch)
├── pages/
│   └── Resumo.jsx                        ← redesenhado, importa componentes locais
└── components/
    ├── TopNav.jsx                        ← brand + preset de data + cmd-K
    ├── BentoGrid.jsx                     ← grid container CSS Grid
    ├── HeroTile.jsx                      ← Margem gigante + area chart Recharts
    ├── MediumTile.jsx                    ← Faturamento/Frete com breakdown + sparkline
    ├── SmallTile.jsx                     ← KPI compacto (Custo, Tarifa, Frete, Qtd)
    ├── DonutTile.jsx                     ← Composição (donut Recharts existente, repaint)
    ├── FilterChips.jsx                   ← chips + popover "+ Filtro"
    ├── DataTable.jsx                     ← tabela 13 colunas (TanStack Table existente)
    ├── DateRangePicker.jsx               ← presets Hoje/7d/30d/Mês + custom
    └── tokens.css                        ← variáveis CSS da paleta + tipografia
```

`financeiro-ml/` antiga permanece em disco intocada até decisão final.

### 4.3 Roteamento

`App.jsx` ganha 1 linha:

```jsx
<Route path="/financeiro-ml/resumo-v2" element={<ResumoV2 />} />
```

Rota antiga `/financeiro-ml/resumo` continua apontando pra v1.

### 4.4 Menu / navegação

Item novo no sidebar (apenas pra Julio, role master): **"Análise Financeira (beta)"** levando a `/resumo-v2`. Item antigo permanece com label original. Após aprovação:

1. Atualizar `App.jsx` pra apontar `/financeiro-ml/resumo` → `<ResumoV2 />`
2. Remover item "(beta)" do sidebar
3. Deletar `frontend/src/financeiro-ml/` (v1)
4. Renomear `financeiro-ml-v2/` → `financeiro-ml/`

Tudo em 1 commit reversível com `git revert`.

## 5. Design tokens

### 5.1 Paleta

Definida em `tokens.css` como CSS custom properties:

| Token | Hex | Uso |
|---|---|---|
| `--canvas` | `#E6EEF7` | Background da página (azul muito claro) |
| `--surface` | `#F4F8FC` | Cards secundários, filterbar, header de tabela |
| `--surface-2` | `#FFFFFF` | Cards principais (tiles bento, tabela rows) |
| `--border` | `#C5D5E6` | Bordas padrão |
| `--border-strong` | `#94B0CC` | Bordas em hover/focus/destaque |
| `--ink` | `#0A2240` | Marinho profundo — números hero, headlines |
| `--ink-2` | `#1B4F8A` | Marinho médio — accent, botões primários, chips, links |
| `--ink-3` | `#4A7BB0` | Marinho claro — fatia secundária do donut, sparklines neutras |
| `--text` | `#0E2A47` | Texto padrão |
| `--muted` | `#5A7796` | Labels, metadata, texto secundário |
| `--pos` | `#15803D` | Deltas positivos, MC%, "lucro" |
| `--neg` | `#B91C1C` | Deltas negativos, MC% baixo, alerta |
| `--accent-light` | `#6FE8A5` | Highlight do chart hero (curva área verde sobre marinho) |

Regra: **superfície nunca tem cor saturada**. Cor entra só em números (delta), badge (frete) e curva (sparkline).

### 5.2 Tipografia

| Famí­lia | Onde | CDN/source |
|---|---|---|
| **Inter** | UI geral (labels, tabs, headlines) | Google Fonts (já comum em Vite) |
| **JetBrains Mono** | Todos os números em R$, percentuais, IDs (MLB/order) | Google Fonts |

Escala:
- `text-xs` 11px — labels uppercase, metadata
- `text-sm` 12px — texto secundário, células de tabela
- `text-base` 13px — texto padrão
- `text-md` 15px — títulos de seção
- `text-lg` 17px — títulos de cards
- `text-xl` 24px — small tile big-num
- `text-2xl` 32px — hero satellites
- `text-3xl` 42px — hero big-value

Todo número com `font-variant-numeric: tabular-nums` pra alinhamento vertical.

### 5.3 Spacing

Escala 4px: `4 / 8 / 12 / 14 / 16 / 18 / 20 / 24`. Tiles bento: `gap: 10px`. Padding interno de tile: `14px` (small), `16px` (medium), `20px` (hero).

### 5.4 Border radius

`6px` (chips, botões pequenos), `8px` (filterbar), `10px` (tiles), `12px` (table-section), `14px` (mockup-frame externo).

### 5.5 Sombra

Uma única sombra discreta na frame externa (`0 12px 32px rgba(10, 34, 64, 0.12)`). Tiles internos sem sombra — separação por border.

## 6. Layout

### 6.1 Top navigation slim

Barra horizontal no topo, altura ~50px:
- Esquerda: brand "Análise Financeira · Mercado Livre · 914 vendas no período"
- Direita: preset de data (Hoje · 7d · 30d · Mês) + hint ⌘K "Buscar"

### 6.2 Bento grid

Grid CSS de 6 colunas, `grid-auto-rows: 90px`, gap 10px. Grid expande verticalmente conforme necessário (auto-flow). Tiles posicionados via `grid-column: span N` e `grid-row: span N` na ordem do DOM:

| # | Tile | span cols | span rows | Posição resultante |
|---|---|---|---|---|
| 1 | **Hero** (Margem) | 3 | 3 | rows 1-3, cols 1-3 |
| 2 | **Medium** Faturamento | 3 | 2 | rows 1-2, cols 4-6 |
| 3 | **Donut** Composição | 2 | 2 | rows 3-4, cols 4-5 |
| 4 | **Small** Custo+Imp | 1 | 1 | row 3, col 6 |
| 5 | **Small** Tarifa | 1 | 1 | row 4, col 6 |
| 6 | **Small** Frete Total | 1 | 1 | row 5, col 1-… (auto-flow) |
| 7 | **Small** Qtd Vendas | 1 | 1 | (auto-flow) |

Wireframe ASCII (4 linhas visíveis):

```
┌─────────────────────────────┬──────────────────────────┐
│                             │   Faturamento ML         │
│   HERO                      │   R$ 55.962              │
│   Margem R$ 10.950          │   Aprov · Cancel + spark │
│   20,1% ↑                   ├──────────────┬───────────┤
│   [area chart]              │  Composição  │ Custo+Imp │
│                             │  (donut +    ├───────────┤
│                             │   legenda)   │  Tarifa   │
└─────────────────────────────┴──────────────┴───────────┘
[small Frete Total]  [small Qtd Vendas]  ...auto-flow
```

A ordem visual final pode ser ajustada na implementação se o auto-flow gerar buracos indesejáveis; alternativa é grid-template-areas explícitas (decisão delegada ao plano).

### 6.3 Tabela completa abaixo

Separador visual sutil (seta ▼ "continua") + bloco `<section class="table-section">` com:

- Header: título "Vendas detalhadas" + meta "914 resultados" + filterbar inline (chips + "+Filtro" + Colunas + Exportar)
- Body: tabela com 13 colunas — Anúncio·SKU, Data, Frete (badge), Valor Un., Qtd, Faturamento, Custo, Imposto, Tarifa, Frete Comp., Frete Vend., MC, MC%
- Footer: paginação 50/100/200 + range + navegação

Tabela mantém scroll horizontal em viewports < 1280px.

### 6.4 Responsivo

Faixas (Tailwind):
- **`lg` (1024+)**: layout completo (bento 6 cols + tabela 13 cols)
- **`md` (768-1023)**: bento colapsa pra 2 colunas (hero full width, demais empilhados); tabela vira scroll horizontal
- **`sm` (< 768)**: não suportado oficialmente (uso desktop)

## 7. Componentes — comportamento

### 7.1 TopNav
- Brand fixo
- Contagem de vendas atualiza ao trocar filtro
- Preset de data: clicar dispara nova consulta `/resumo`
- ⌘K: abre Command palette (popover) com search por SKU/MLB/Anúncio

### 7.2 HeroTile
- Fundo: gradient linear marinho `--ink → --ink-2`
- Big value: Margem em R$, atualiza com filtro
- pct-big: MC% global, cor `--accent-light` se positivo
- Area chart Recharts (componente `<AreaChart>` já disponível): pontos = MC diária do período
- Tooltip ao hover no chart mostra dia + valor

### 7.3 MediumTile (Faturamento, Frete)
- Tag uppercase + big-num + breakdown 2 valores (Aprov./Cancel. ou Comp./Vend.)
- Sparkline Recharts `<LineChart>` 300×40
- Click no tile abre drawer lateral com detalhamento (fase 2; v2 inicial só mostra)

### 7.4 SmallTile (Custo+Imp, Tarifa, Frete, Qtd)
- Tag + big-num + delta (↑/↓ % vs período anterior)
- Cor do delta: `--pos` ou `--neg`
- Sem sparkline (mantém compacto)

### 7.5 DonutTile (Composição)
- Donut Recharts (reaproveita `PizzaChart.jsx` existente, repinta com palette nova)
- Centro: MC% global em destaque
- Legenda à direita: 5 itens (Custo · Imposto · Tarifa · Frete vendedor · Margem) com dot quadrado, nome e % tabular

### 7.6 FilterChips
- Chip = filtro ativo (ex: "Status: Aprovados", "FULL")
- Cada chip tem `×` pra remover
- "+ Filtro" abre popover com 8 campos (mantém os mesmos do v1)
- Toggle "Considerar frete comprador" vira chip on/off
- Padrão de chip: borda `--border-strong`, texto `--ink-2`

### 7.7 DataTable
- TanStack Table v8 (já instalado)
- Colunas: 13 fixas (mesmas do v1, ordem e nomes preservados)
- Frete vira badge colorido por tipo: FULL azul (`--ink-2`), FLEX amarelo, ME1 teal, demais cinza
- MC e MC% pintados conforme valor: alto `--pos`, baixo `--neg`
- Sort por coluna, paginação 50/100/200
- Row hover: `--surface`
- Botão "⚙ Colunas" abre popover com column-visibility toggle
- Botão "↓ Exportar" abre menu Excel/CSV
- Sem expand-row na v2 inicial (deixa pra v3 se valer)

### 7.8 DateRangePicker (embedado no TopNav)
- Presets: Hoje · 7d · 30d · Mês corrente · Custom
- "Custom" abre 2 inputs `<input type="date">` nativos
- Mantém comportamento de "Buscar" único do v1 (1 click = 1 fetch)
- Componente standalone em `components/DateRangePicker.jsx` mas renderizado dentro do `<TopNav />` (não tem barra separada)

## 8. Estados

| Estado | Tratamento |
|---|---|
| Loading inicial | Skeleton dos tiles (placeholder cinza animado via Tailwind `animate-pulse`) |
| Loading durante refetch | Overlay sutil sobre bento + spinner discreto no botão de data |
| Erro de API | Banner vermelho no topo do bento com mensagem + botão "Tentar novamente" |
| Empty (0 vendas no período) | Bento com valores zerados + mensagem "Nenhuma venda nesse período" no lugar da tabela |
| Sem cache (primeira busca) | Mensagem "Sincronizando com Mercado Livre — pode levar até 15s" + skeleton |

## 9. Acessibilidade

- Contraste WCAG AA: todas as combinações `--ink` sobre `--surface-2`, `--text` sobre `--canvas`, `--muted` sobre `--surface` atendem ≥4.5:1
- Foco visível: outline `2px solid --ink-2` em todos os interativos
- Aria-labels nos botões de ícone (⚙, ↓, +)
- Tabela com `<th scope="col">` e captions
- Atalhos: ⌘K abre command palette; Esc fecha popovers

## 10. Stack adicional

Bibliotecas novas a adicionar (validadas pelos especialistas):

| Lib | Função | Peso | Fonte |
|---|---|---|---|
| `class-variance-authority` | Variants tipadas pra tiles e badges | ~1.7 kB | npm |
| `@formkit/auto-animate` | Microanimações em listas (table, chips) | ~3.3 kB | npm |

**Total adicional ≈ 5 kB gzipped.**

NÃO adicionar:
- Framer Motion (over-engineering — auto-animate basta)
- shadcn/ui como dependência (copy-paste de padrões só)
- Headless UI (Radix já cobre)
- react-number-format (Intl nativo basta)

Reusar:
- Recharts (já instalado) pra hero area chart, sparklines, donut
- TanStack Table v8 (já instalado) pra DataTable
- Radix Tooltip (já instalado) pra hover info
- Tailwind (já instalado) pra layout
- lucide-react (já instalado) pra ícones (⚙ Settings, ↓ Download, + Plus, × X)

Formatação BRL: utilitário local `formatBRL(value)` usando `Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })`.

## 11. Plano de rollout

1. **Fase 1 — Build paralelo (1-2 dias)**
   - Criar `frontend/src/financeiro-ml-v2/` espelhando estrutura
   - Implementar componentes em ordem: tokens.css → TopNav → HeroTile → MediumTile → SmallTile → DonutTile → BentoGrid → FilterChips → DateRangePicker → DataTable → Resumo.jsx
   - Adicionar rota `/resumo-v2` no `App.jsx`
   - Adicionar item de menu "(beta)" no sidebar

2. **Fase 2 — Validação com Julio**
   - Julio usa v2 em paralelo com v1 por N dias
   - Ajustes via iteração (lista de TODOs no spec)

3. **Fase 3 — Cutover**
   - Trocar rota `/resumo` → `<ResumoV2 />`
   - Remover item "(beta)" do sidebar
   - Deletar `financeiro-ml/` antiga
   - Renomear `financeiro-ml-v2/` → `financeiro-ml/`
   - 1 commit reversível

## 12. Testes

Como o redesign é puramente visual e reusa componentes lógicos existentes:

- **Sem novos testes unitários** de aggregator/sync/sku_service (não muda)
- **Teste manual estruturado** em `docs/superpowers/specs/2026-05-27-test-checklist-bento.md` (gerado junto com plano):
  - Cada KPI bate com v1 (valores idênticos para o mesmo filtro)
  - Cada coluna da tabela bate com v1
  - Filtros aplicam corretamente (chip add/remove)
  - Preset de data dispara nova busca
  - Export Excel/CSV continua funcional
  - Responsivo lg/md/sm
  - Acessibilidade básica (Tab navigation, contrast)
- **Smoke test E2E opcional**: rota `/resumo-v2` carrega sem console errors

## 13. Riscos

| Risco | Mitigação |
|---|---|
| User não se adapta à hierarquia bento | v1 fica vivo por N dias; cutover só após OK |
| Hero gradient marinho parece pesado | Token `--ink` ajustável; gradient pode virar flat se incomodar |
| Tabela com scroll horizontal em laptops | Column-visibility toggle permite esconder colunas |
| Sparklines com pouco dado (1-2 pontos) | Substituir por dash placeholder neutro |
| ⌘K command palette adiciona complexidade | Marcar como Fase 2 se atrasar entrega inicial |

## 14. Referências (research dos especialistas)

- Apple Vision OS / Linear / Stripe Atlas — bento grid asymmetric
- Mercury / Vercel Analytics — KPI hero + secundários monocromos
- Tremor (Vercel) — padrões React+Tailwind+Recharts pra fintech
- shadcn-admin (satnaing/shadcn-admin, 11k★) — referência de layout/sidebar
- Radix Colors — paleta semântica acessível
- Mockups completos preservados em `.superpowers/brainstorm/11076-1779884711/content/`:
  - `direcao-azul-marinho.html` — Plano A (hierárquico linear) — descartado
  - `plano-b-bento.html` — Plano B original (tabela em aba) — descartado
  - `plano-b-hibrido.html` — **Plano B Híbrido — aprovado**

## 15. Glossário do redesign

| Termo | Significado |
|---|---|
| **Bento grid** | Layout asymmetric inspirado em caixas bento japonesas; tiles de tamanhos variados num grid |
| **Hero tile** | Tile maior do bento (3×3) ocupando 25% da viewport; KPI principal |
| **Sparkline** | Mini-chart de linha sem eixos, mostrando tendência num espaço pequeno |
| **Chip** | Tag clicável representando filtro ativo, removível via `×` |
| **Token CSS** | Variável CSS centralizada em `tokens.css` (cor, espaçamento, tipografia) |
| **v1 / v2** | v1 = código atual em `financeiro-ml/`; v2 = redesign em `financeiro-ml-v2/` |
