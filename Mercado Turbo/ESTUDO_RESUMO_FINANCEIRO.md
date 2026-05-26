# Estudo — Resumo Financeiro (Mercado Turbo → NVS-WMS)

> Documento de **entendimento** da funcionalidade "Resumo Financeiro" do Mercado Turbo (MT).
> Objetivo: subsidiar a futura migração dessa feature pra dentro do NVS-WMS, eliminando dependência do MT.
> **Status: estudo. Nada construído ainda.**
> Última atualização: 2026-05-26

---

## 1. Contexto e Motivação

- Antigra paga assinatura do **Mercado Turbo** (SaaS Java/JSF) pra usar várias funcionalidades sobre vendas Mercado Livre.
- Custo recorrente alto. Objetivo: migrar features pro NVS-WMS gradualmente.
- **Primeira feature alvo**: o painel "Resumo Financeiro" — monitor de vendas ML com cards de KPI, filtros, gráfico e tabela detalhada.
- NVS-WMS hoje **não tem integração direta com ML** (apenas Tiny ERP). Esse estudo abre caminho ML API.
- Conta única: NOVAESMOTOPEÇAS (`ml_user_id = 221832146`).

---

## 2. O que o painel faz (descoberto via DevTools ao vivo)

URL: `https://app.mercadoturbo.com.br/sistema/financeiro/resumofinanceiro`

### 2.1 Layout

- Topo: cards KPI agregados (Vendas Aprovadas, Faturamento ML, Custo & Imposto, Tarifa, Frete Total, Margem Contribuição, Breakdown Logístico, Quantidades, Tickets Médios, Devoluções Parciais)
- Meio esquerdo: bloco "Filtrar Busca" (10 filtros)
- Meio direito: gráfico pizza "Representação Gráfica" (composição % sobre Vendas Aprovadas)
- Baixo: barra de ações (Nivelar Custo & Imposto, Nivelar SKU, Ranking de Produtos, Reaver Dias Perdidos, Export Excel/CSV) + tabela paginada com 15 colunas por venda

### 2.2 Stack técnica do MT

- Backend: **Java + Jakarta Faces (JSF) + PrimeFaces**.
- Server-rendered: o clique "Buscar" dispara **1 POST JSF partial ajax** na própria URL → resposta HTML/XML ~370KB que substitui blocos da página. **Sem API REST exposta.**
- Cache client-side: `localStorage` armazena coisas como `mt:anuncios:total:221832146` e `mt:visitas:221832146:56:day:?:withToday`.
- ViewState JSF em campos hidden — todo state é server-side.

Implicação: não dá pra "espionar endpoints REST" do MT pra copiar. Só entendemos pela UI, valores exibidos e tooltips. **Vamos copiar a lógica, não a chamada.**

---

## 3. Cards / KPIs — Fórmulas confirmadas

### 3.1 Vendas Aprovadas / Faturamento ML / Vendas Canceladas

Tooltip oficial MT: *"Vendas Aprovadas considera o valor do produto + frete pago pelo comprador."*

- `Vendas Aprovadas = Σ (produto + frete_comprador)` onde `status = aprovada`
- `Vendas Canceladas = Σ (produto + frete_comprador)` onde a venda foi **totalmente cancelada** e o comprador recebeu o dinheiro de volta (não importa se também devolveu o produto). **Devoluções parciais não entram aqui** — vão pro card próprio.
- `Faturamento ML = Vendas Aprovadas + Vendas Canceladas`

Validado por aritmética: 18.583,38 + 626,99 = 19.210,37 ✅ (mesmo print).

### 3.2 Custo & Imposto

Tooltip: *"Valores vinculados aos SKUs cadastrados na página 'Meus Produtos'."*

- `Custo = Σ (custo_unit_cadastrado × qty_vendida)` por linha de venda no filtro
- `Imposto = Σ (imposto_pct_cadastrado × faturamento_linha)`
- Fonte 100% local — sem dado do ML.
- **Se SKU não tem cadastro, custo=0 e imposto=0** → MC dessa linha vira artificialmente alta. UI futura precisa indicar "linha sem cadastro" pra Julio saber o número é falso.

### 3.3 Tarifa de Venda

Tooltip: *"Tarifa de venda cobrada pelo Mercado Livre em suas vendas. Valor da tarifa de venda descontado a devolução parcial."*

- `Tarifa exibida = Σ (sale_fee_bruto − refund_tarifa_parcial)`
- Quando há devolução parcial, ML reembolsa proporcionalmente a tarifa. O card mostra **líquido**.
- Implementação: armazenar `tarifa_bruta` e `tarifa_refund` separados.

### 3.4 Frete Total / Comprador / Vendedor

Tooltip: *"Soma dos fretes pagos em todas as suas VENDAS APROVADAS. O valor pago pelo comprador e o valor descontado de você pelo Mercado Livre."*

- `Frete Total = Σ (frete_comprador + frete_vendedor)` **só vendas aprovadas** (canceladas não contam).
- `frete_comprador` = pago pelo comprador (vem de `shipping.cost` no ML).
- `frete_vendedor` = descontado do seller pelo ML (campo a confirmar quando integrar — `shipping.list_cost` ou `shipping_options`).

### 3.5 Margem de Contribuição

Tooltip: *"É o valor total de: VENDAS APROVADAS - CUSTOS & IMPOSTO - TARIFA DE VENDA - FRETE VENDEDOR - DEVOLUÇÃO PARCIAL. (...) não é subtraído o valor de frete do comprador caso o frete seja da modalidade ME1 ou a combinar."*

```
MC = Vendas_Aprovadas − Custo − Imposto − Tarifa_Venda − Frete_Vendedor − Devolução_Parcial − Frete_Comprador
     (Frete_Comprador NÃO é subtraído se modalidade ∈ {ME1, "Outro (a Combinar)"})
```

**Validação por linha exemplo** (SKU 577, Full, qty=1):
- Valor unit: 26,99 · Frete Comprador: 18,99 · Custo: 8,46 · Imposto: 2,43 · Tarifa: 3,24 · Frete Vendedor: 6,55
- Vendas Aprovadas linha = 26,99 + 18,99 = **45,98** ✓ (bate com coluna "Faturamento ML")
- MC = 45,98 − 8,46 − 2,43 − 3,24 − 6,55 − 18,99 = **6,31** ✓
- MC% = 6,31 / 26,99 (= produto puro) = **23,38%** ✓

### 3.6 Breakdown Logístico

Cards: Places/Coleta · Flex · Full · ME1 · Outros · Total

- Cada um = `Σ Vendas_Aprovadas` filtrado por `logistic_type` do shipment ML.
- Mapeamento provável (validar):
  - `drop_off` → Places/Coleta
  - `self_service` → Flex
  - `fulfillment` → Full
  - `ME1` legacy
  - resto → Outros
- Soma deve bater Vendas Aprovadas total. Verificado no print: 722,49 + 165,99 + 17.694,90 + 0 + 0 = 18.583,38 ✅

### 3.7 Quantidades

- `Qtd Vendas Aprovadas`: count distinto de pedidos com status aprovada · "(N unidades)" = Σ qty itens
- `Qtd Total Vendas`: count Aprovadas + Canceladas
- `Qtd Vendas Canceladas`: count + Σ qty itens canceladas

### 3.8 Tickets Médios

- `Ticket Médio Venda = Vendas_Aprovadas / Qtd_Vendas_Aprovadas`
- `Ticket Médio MC = MC / Qtd_Vendas_Aprovadas` (mostra também MC% global pra leitura rápida)

### 3.9 Devoluções Parciais

- `Σ refund_amount` em pedidos com refund parcial + `count(pedidos com refund)`.
- Devolução parcial = comprador recebeu reembolso mas a venda **não foi cancelada totalmente**.

### 3.10 Pizza — Representação Gráfica

Asterisco oficial: *"O frete pago pelo comprador não é considerado no gráfico e no cálculo percentual."*

- Denominador (validado por aritmética) = **`Vendas_Aprovadas`** (= produto + frete_comprador, **não** subtraindo frete_comprador no denominador).
- Fatias (numeradores):
  - Custo / Vendas_Aprovadas
  - Imposto / Vendas_Aprovadas
  - Tarifa / Vendas_Aprovadas
  - **Frete = só Frete_Vendedor** / Vendas_Aprovadas (frete comprador zerado no gráfico)
  - MC / Vendas_Aprovadas

Verificado: 47,63 + 9,00 + 10,97 + 15,54 + 16,85 = 99,99% ≈ 100% ✅

---

## 4. Filtros — Vocabulário oficial

Extraído direto dos `<select>` do MT.

| Filtro | Opções |
|---|---|
| Data Início / Data Fim | Calendário (obrigatório por convenção) |
| Nº Pedido / Carrinho | Texto livre (busca por `order_id`) |
| Título ou MLB | Texto livre (busca por título do anúncio ou `MLB...`) |
| SKU | Texto livre |
| Status Venda | Todos · Aprovados · Cancelados |
| **Modalidade** | Todos · Premium · Clássico · Grátis ← **tipo do anúncio ML** (`listing_type_id`: gold_special / gold_pro / free). NÃO é envio. |
| Tipo do Frete | Todos · Mercado Envios 1 · Mercado Envios 2 · S/ Mercado Envios · FULL · Flex · Outro (a Combinar) |
| Custo & Imposto | Todos · Somente sem Custo · Somente sem Imposto · Somente sem Custo e sem Imposto |
| Multicontas | Lista de contas ML registradas (no nosso caso: 1 só — NOVAESMOTOPEÇAS) |
| Paginação | 50 / 100 / 200 |

**Form fields do POST (capturados via XHR interceptor):**

```
calendar-data-inicial_input
calendar-data-final_input
j_idt1788  (Nº Pedido)
j_idt1790  (Título/MLB)
input-filtro-sku
j_idt1793_input  (Status Venda)
j_idt1798_input  (Modalidade)
j_idt1804_input  (Tipo Frete)
j_idt1813_input  (Custo & Imposto)
select-multicontas
jakarta.faces.ViewState  (token JSF)
```

---

## 5. Tabela detalhada (por linha de venda)

15 colunas, paginação 50/100/200, ordenação por qualquer coluna:

`Anúncio · Conta · SKU · Data · Frete · Valor Unit. · Qtd. · Faturamento ML · Custo (-) · Imposto (-) · Tarifa de Venda (-) · Frete Comprador (-) · Frete Vendedor (-) · Margem Contrib. (=) · MC em %`

- `Anúncio`: título do anúncio (clicável → copia título / MLB).
- `SKU`: do cadastro `seller_custom_field` ou variation no ML (string livre, mistura numérico `502, 509` com mnemônico `VISEIRAFLYCRI`).
- `Order ID`: clicável também — formato cru ML `2000016614536174` (prefixo `2000…`).
- Cores na UI: Custo/Imposto/Tarifa em vermelho-laranja (saídas), Frete Vendedor em azul, MC e MC% em verde quando positivos.

---

## 6. Ações da barra de ferramentas

### 6.1 Nivelar Custo & Imposto (split-button)

Sub-opções:
- **Nivelar**: aplica retroativamente o cadastro atual de `custo_unit`/`imposto_pct` em pedidos já carregados que ainda não tinham valor. Recalcula MC sem buscar ML.
- **Reprocessar**: re-busca os dados no ML pro período filtrado (refresh do cache).

### 6.2 Nivelar SKU (modal "Nivelar SKU por MLB")

Use case: ML mandou venda com SKU em branco ou errado. Corrige em massa.

Inputs do modal:
- `ID Anúncio (MLB)` — obrigatório
- `Data início` / `Data fim` — período
- `SKU` — novo valor a aplicar
- Checkbox: *"Realizar este procedimento em todas as contas do multicontas"*

Aviso: *"Esse processo pode demorar alguns minutos a depender da quantidade de vendas desse anúncio."*

### 6.3 Ranking de Produtos

Não inspecionado a fundo. Pelo nome e tooltip do MT, é uma view derivada: ranking dos SKUs/anúncios mais vendidos (por receita, qty ou margem) dentro do filtro atual.

### 6.4 Reaver Dias Perdidos (modal)

**Achado mais importante do estudo.**

Texto: *"Importe vendas do Mercado Livre que não foram processadas no Mercado Turbo durante o período em que sua assinatura esteve inativa ou ainda não estava ativa."*

- Limite: até 12 meses atrás
- Custo: **paga créditos** (Julio tem 341 ¢ no momento da inspeção). "Verificar Custo" antes de executar.
- Botões: Executar · Histórico de Importações · Fechar
- Restrição: "Selecione apenas dias do mesmo mês para realizar a importação."

**Implicação arquitetural enorme:**
MT funciona como **banco local sob assinatura**. Quando o seller paga, o MT consome ML e cacheia. Quando o seller pausa a assinatura, MT deixa de puxar — daí os "dias perdidos" que ele cobra pra reaver.

**No NVS isso desaparece**: não há modelo de créditos. Quando o usuário filtrar um período não cacheado, o backend bate no ML API direto, cacheia e retorna. Sem limite de 12 meses, sem custo extra além da própria infra do ML API (rate limit gratuito).

### 6.5 Export

Excel · CSV. Snapshot do filtro atual.

---

## 7. Cadastro de SKU (Custo + Imposto)

- No MT vive em "Meus Produtos" (página separada).
- No NVS atual **não existe** cadastro de custo. A tabela `barcodes` armazena `(barcode, sku, description, is_primary)` mas é 1 SKU → N EANs (sku repetido).
- Direção do estudo (não construído): tabela nova com PK `sku` e 2 campos novos (`custo_unit`, `imposto_pct`), 1 linha por SKU.
- Alíquota: **única por SKU** (não varia por estado/regime). Decisão tomada com Julio.

---

## 8. Diferenças MT → NVS já decididas

| Tópico | Mercado Turbo | NVS-WMS futuro |
|---|---|---|
| Stack | Java JSF, server-rendered | Python FastAPI + React (atual) |
| Cobrança | Assinatura mensal + créditos por importação retroativa | Zero — infra própria, só consome ML API gratuita |
| Limite histórico | 12 meses | Sem limite (ML API permite) |
| Multicontas | Sim, múltiplas | **Só 1 conta** (NOVAESMOTOPEÇAS) — simplifica muito |
| Auth ML | Própria deles | Reusar `Devoluçao/` que já tem OAuth + refresh funcionando |
| "Reaver Dias Perdidos" | Botão dedicado pago | Automático ao filtrar período não cacheado |
| Cadastro SKU custo/imposto | "Meus Produtos" | Tabela `sku_financeiro` (a criar) |
| Fonte de dados secundária | Toda própria | Aproveitamento das tabelas NVS existentes (operators, sessions) onde fizer sentido |
| UI | PrimeFaces server-rendered | React + Vite, página `MercadoTurboFinanceiro.jsx` (provisório) |

---

## 9. Decisões arquiteturais aprovadas com Julio

1. **Pasta do projeto**: `warehouse-picker v2/Mercado Turbo/` (criada vazia, esse doc inaugura).
2. **Mantra 100% ativo** para esse projeto até comando explícito de desligar (memória persistente).
3. **Abordagem A escolhida** (vs B isolado e C dentro do Devoluçao): construir módulo dentro do NVS-WMS reusando lógica ML do `Devoluçao/`. Único banco SQLite, único deploy.
4. **Cache híbrido (C)**: banco local + botão Buscar dispara consulta. Backend decide se serve do cache ou bate no ML conforme cobertura do período.
5. **Data inicial obrigatória** no filtro — sem backfill automático grande.
6. **Conta única ML** (NOVAESMOTOPEÇAS) — sem complexidade de multiconta.
7. **Escopo fase 1**: todos os cards/filtros/tabela do print. Ações de massa (Nivelar/Ranking/Reaver) ficam pra fase 2.
8. **Alíquota única por SKU** — não varia por contexto.

---

## 10. Endpoints ML API previstos (a confirmar quando partir pra design)

Reutilizar lógica do `Devoluçao/app.py` (`ml_get()` com refresh token automático).

| Endpoint | Para que |
|---|---|
| `/oauth/token` | Refresh token (já implementado) |
| `/orders/search?seller={user_id}&order.date_created.from/to=...` | Listar vendas do período |
| `/orders/{id}` | Detalhes — sale_fee, payments, status_detail |
| `/shipments/{id}` | Frete comprador/vendedor, modalidade logística |
| `/items/{id}` | Título, SKU (`seller_custom_field`/variations), `listing_type_id` (modalidade do anúncio) |
| `/orders/{id}/refunds` (ou claims) | Devoluções parciais e valores |
| `/billing/sales/{id}` ou `payments/{id}` | Tarifa final pós-refund parcial |

---

## 11. Stack de bibliotecas escolhida

Análise do que NVS-WMS já possui vs lacunas. Decisões aprovadas pelo Julio em 2026-05-26.

### Já existem no projeto (reusar)

**Backend** (`backend/requirements.txt`):
`fastapi`, `sqlalchemy`, `httpx`, `openpyxl` (Excel export ✓), `python-dotenv`, `uvicorn`, `pdfplumber`, `pymupdf`, `aiofiles`

**Frontend** (`frontend/package.json`):
`react 18`, `react-router-dom`, `tailwindcss`, `lucide-react`, `gsap`, `clsx`, `tailwind-merge`

**Devoluçao** (referência, não importável — usa Flask+requests):
Padrão de OAuth ML + refresh token automático. Vamos **reescrever em httpx async**, não importar.

### Libs novas (5 ao todo)

| Lib | Onde | Pra que | Por que escolhida |
|---|---|---|---|
| `tenacity` | backend (pip) | Retry/backoff em chamadas ML API (rate limit, falhas transientes) | Padrão da indústria Python. Decorator limpo, configurável. |
| `recharts` | frontend (npm) | Card "Representação Gráfica" (donut 5 fatias) | Declarativo (combina com React), MIT, donut em ~10 linhas. Alternativas (Chart.js/ApexCharts) são imperativas — pior DX. |
| `@tanstack/react-table` v8 | frontend (npm) | Tabela 15 colunas com sort + paginação + filtros | Headless (zero CSS, combina com Tailwind), ~14KB, MIT. ag-Grid é pago, MUI DataGrid puxa MUI inteiro. |
| `@tanstack/react-query` v5 | frontend (npm) | Estado dos calls API + cache cliente (casa com cache híbrido server-side) | Padrão moderno. Cache automático, dedupe, retry, refetch. |
| `@radix-ui/react-tooltip` | frontend (npm) | Tooltips dos cards (espelha UX do MT) | Acessível (a11y nativo), headless, ~5KB. |

### Decisões explícitas de **não** adicionar

- **Wrapper Python ML** (meli-sdk-python etc): SDKs abandonados ou desatualizados. Escrever fino em httpx puro (~200 linhas) custa menos e dá controle total.
- **`cachetools`** em memória: SQLite já é nosso cache. Adicionar camada em memória seria over-engineering.
- **`react-datepicker` / `react-day-picker`**: `<input type="date">` HTML5 nativo é suficiente pro MVP. Funciona em desktop e mobile. Polish fica pra fase 2.
- **`ag-Grid`** / **MUI DataGrid**: pesados ou pagos. TanStack Table resolve.
- **`SWR`**: TanStack Query tem features superiores pro nosso caso.

### Comando único pra instalar (quando partir pra design)

```bash
# backend
pip install tenacity

# frontend
npm install recharts @tanstack/react-table @tanstack/react-query @radix-ui/react-tooltip
```

---

## 12. Decisões dos pontos abertos

Resolvidos com Julio em 2026-05-26.

### ✅ Decididos agora

| # | Tópico | Decisão |
|---|---|---|
| 1 | UI cadastro SKU custo/imposto | **Página nova dedicada** no menu (separada do MasterData). Listagem + edição inline + import Excel em massa. |
| 2 | Permissões do painel | **Apenas Master** vê (mesmo padrão do Financeiro Boletos atual). |
| 3 | Botão de busca | **1 botão único "Buscar"** — não há botão "Atualizar" separado. Buscar já faz a coisa certa (cache + completa lacunas + serve). |
| 4 | Formato do cache | **Granularidade = 1 dia**. Política de freshness: <br>• **Hoje** → sempre re-busca ML (dado vivo). <br>• **Ontem até 7 dias atrás** → cache, mas re-sync se última atualização > 24h. <br>• **8+ dias** → cache imutável (pedidos ML estáveis). <br><br>**Fluxo Buscar**: backend quebra período em dias → pra cada dia checa cache → dias faltantes/stale são puxados do ML em paralelo → salva cache → agrega → devolve. Resultado: primeira busca de mês novo ~15s, recorrentes ~200ms. Sem créditos, sem limite 12 meses. |

### 🟡 Adiados pra fase de testes ML (depois do primeiro fetch funcionar)

São perguntas que só conseguimos responder quando o módulo já estiver puxando dados reais.

| # | Tópico | Estratégia |
|---|---|---|
| 5 | Checkbox "Considerar frete comprador" | Replicar UX do MT, validar comportamento exato com pedido real (provável: impacta denominador do MC% global). |
| 6 | Mapeamento "Tipo do Frete" → ML | Dropdown tem 7 rótulos (ME1, ME2, S/ Mercado Envios, FULL, Flex, "Outro (a Combinar)"). ML responde via `shipping.logistic_type` + `shipping.mode`. Descobrir combinações exatas inspecionando 1 pedido de cada tipo no ML API. |
| 7 | Campos ML pra `frete_vendedor` | Provável: `shipping.list_cost` ou `shipping_options.cost`. Confirmar com payload real. |
| 8 | Distinguir cancelada total vs devolução parcial | Hipótese: total → `order.status = "cancelled"`. Parcial → `order.status = "paid"` + 1+ registros em `order.refunds`/`claims` com valor < total. Validar com pedido real. |

---

## 13. Como esse doc evolui

- Esse arquivo é **referência viva**. Quando partirmos pra design (`docs/superpowers/specs/`), referenciamos esse estudo.
- Quando algo for confirmado/refinado, atualiza aqui.
- Quando começar a construir, esse doc fica como histórico de "o que MT fazia".
