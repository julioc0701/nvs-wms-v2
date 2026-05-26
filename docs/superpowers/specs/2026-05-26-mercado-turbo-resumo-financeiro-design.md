# Spec — Resumo Financeiro Mercado Livre

> Design document para implementar o painel "Resumo Financeiro" dentro do NVS-WMS, replicando a funcionalidade equivalente do Mercado Turbo.
> Referência completa do entendimento: [`Mercado Turbo/ESTUDO_RESUMO_FINANCEIRO.md`](../../../Mercado%20Turbo/ESTUDO_RESUMO_FINANCEIRO.md)
> Data: 2026-05-26
> Status: rascunho aguardando aprovação

---

## 1. Objetivo

Criar dentro do NVS-WMS uma página que substitui o "Resumo Financeiro" do Mercado Turbo. Permite ao Master:

- Visualizar 13 cards de KPI sobre vendas Mercado Livre num período (Vendas Aprovadas, Faturamento ML, Custo & Imposto, Tarifa, Frete Total, Margem de Contribuição, Breakdown Logístico, Quantidades, Tickets Médios, Devoluções Parciais, Pizza %).
- Filtrar por Data, Nº Pedido, Título/MLB, SKU, Status, Modalidade do anúncio, Tipo de Frete, Custo & Imposto.
- Ver tabela detalhada de 15 colunas por venda, paginada (50/100/200).
- Exportar Excel/CSV.
- Cadastrar custo unitário e alíquota de imposto por SKU em página dedicada (necessário pra cálculo de MC).

Resultado pra Antigra: eliminar dependência do MT pra essa feature → economia da assinatura mensal.

---

## 2. Fora de escopo (fase 1)

- "Nivelar Custo & Imposto" (ação retroativa em massa).
- "Nivelar SKU por MLB" (correção de SKU em massa).
- "Ranking de Produtos".
- "Reaver Dias Perdidos" — não precisa, o cache enche sob demanda.
- Multiconta — só NOVAESMOTOPEÇAS.
- Shopee, Pós-Venda, Métricas externas ao Resumo.

Esses itens ficam pra fase 2+ (spec separada).

---

## 3. Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                      Frontend (React + Vite)                    │
│                                                                 │
│  /financeiro-ml/resumo  ──┐                                     │
│  /financeiro-ml/skus    ──┤── api client (fetch + TanStack)     │
│                            └── Recharts (donut) · TanStack      │
│                                Table (tabela) · Radix Tooltip   │
└─────────────────────────────────┬───────────────────────────────┘
                                  │ JSON REST
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                  FastAPI Backend (porta 8001)                   │
│                                                                 │
│  routers/financeiro_ml.py    ← endpoints REST                   │
│  services/                                                      │
│    ml_client.py              ← httpx async + OAuth refresh      │
│    ml_sync.py                ← orquestra cache/fetch por dia    │
│    ml_aggregator.py          ← calcula cards e pizza            │
│    sku_financeiro_service.py ← CRUD do cadastro custo/imposto   │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
        ┌──────────────────────────────────────────┐
        │  SQLite — warehouse_v3_local.db          │
        │  + ml_tokens                             │
        │  + sku_financeiro                        │
        │  + ml_orders_cache                       │
        │  + ml_order_items_cache                  │
        │  + ml_day_sync_status                    │
        └──────────────────────────────────────────┘

                  Mercado Livre API
                  (api.mercadolibre.com)
```

**Princípios:**

- Cliente ML é um módulo **isolado** com interface clara. Resto do backend usa só funções de alto nível (`fetch_orders_for_day(date)`), nunca chama URL direto.
- Aggregator recebe lista de orders do cache e devolve dict de KPIs — função pura, sem I/O. Fácil de testar.
- Frontend é "burro" — recebe JSON pronto do backend, só renderiza. Nenhum cálculo de MC/MC% no client.

---

## 4. Modelo de dados

Todas as tabelas vivem em `warehouse_v3_local.db` (único banco). Migrações inline em `database.py → init_db()` (mesmo padrão do resto do projeto).

### 4.1 `ml_tokens` (estado OAuth)

| Coluna | Tipo | Nota |
|---|---|---|
| `id` | INTEGER PK | Fixo = 1 (single row) |
| `access_token` | TEXT NOT NULL | |
| `refresh_token` | TEXT NOT NULL | |
| `user_id` | INTEGER NOT NULL | ml_user_id (221832146 hoje) |
| `expires_at` | DATETIME NOT NULL | Quando o access_token expira |
| `updated_at` | DATETIME NOT NULL | |

Seed inicial via `.env` (ML_ACCESS_TOKEN etc) — primeiro startup lê env, salva na tabela. Daí em diante a tabela é fonte da verdade.

### 4.2 `sku_financeiro` (cadastro custo/imposto)

| Coluna | Tipo | Nota |
|---|---|---|
| `sku` | VARCHAR(100) PK | Mesma string usada em `barcodes.sku` |
| `custo_unit` | DECIMAL(10,2) NOT NULL | Preço de custo unitário em R$ |
| `imposto_pct` | DECIMAL(5,2) NOT NULL | Alíquota % (ex: 8.50) |
| `updated_at` | DATETIME NOT NULL | |
| `updated_by` | INTEGER NOT NULL FK operators.id | Quem editou por último |

**Decisões:**
- Sem soft delete — apagar = apagar. Pra "remover custo" o usuário coloca 0.
- Alíquota única (não varia por estado/regime).
- PK em `sku` (string) — assume SKU é único globalmente. Já é a convenção do NVS.

### 4.3 `ml_orders_cache` (1 linha por pedido ML)

| Coluna | Tipo | Nota |
|---|---|---|
| `order_id` | BIGINT PK | ID cru do ML (formato `2000...`) |
| `date_created` | DATETIME NOT NULL | Index — usado em filtros |
| `date_closed` | DATETIME | NULL se ainda não fechou |
| `status` | VARCHAR(30) NOT NULL | `paid` / `cancelled` / `confirmed` etc — texto ML cru |
| `status_detail` | VARCHAR(100) | Razão se cancelado |
| `produto_total` | DECIMAL(12,2) NOT NULL | Σ(unit_price × qty) dos itens |
| `frete_comprador` | DECIMAL(10,2) NOT NULL DEFAULT 0 | `shipping.cost` |
| `frete_vendedor` | DECIMAL(10,2) NOT NULL DEFAULT 0 | `shipping.list_cost` (a confirmar em testes) |
| `tarifa_bruta` | DECIMAL(10,2) NOT NULL DEFAULT 0 | Σ `marketplace_fee` ou `sale_fee` por item |
| `tarifa_refund` | DECIMAL(10,2) NOT NULL DEFAULT 0 | Parte de tarifa devolvida em refunds parciais |
| `refund_amount_partial` | DECIMAL(10,2) NOT NULL DEFAULT 0 | Σ refunds parciais (não inclui cancelamento total) |
| `modalidade_anuncio` | VARCHAR(30) | `gold_special` / `gold_pro` / `free` — `listing_type_id` |
| `logistic_type` | VARCHAR(30) | `fulfillment` / `self_service` / `drop_off` / `cross_docking` / NULL |
| `shipping_mode` | VARCHAR(30) | `me1` / `me2` / `not_specified` |
| `breakdown_bucket` | VARCHAR(20) | Derivado no insert: `full` / `flex` / `places_coleta` / `me1` / `outros`. Mapeamento inicial: `fulfillment → full`, `self_service → flex`, `drop_off/cross_docking → places_coleta`, `shipping_mode = me1 → me1`, resto → `outros`. Refinar quando testes ML revelarem combinações reais (ESTUDO §12 ponto 6). |
| `raw_json` | TEXT NOT NULL | Dump completo da resposta `/orders/{id}` pra debug |
| `synced_at` | DATETIME NOT NULL | Quando puxou |
| `synced_run_id` | INTEGER FK ml_day_sync_status.id | Liga ao run que populou |

Índices:
- `(date_created)` — filtros por período
- `(status)` — filtros aprovado/cancelado
- `(logistic_type, shipping_mode)` — filtros tipo de frete

### 4.4 `ml_order_items_cache` (1 linha por item dentro de uma order)

Tabela separada porque uma order pode ter N itens (qty > 1 ou múltiplos produtos).

| Coluna | Tipo | Nota |
|---|---|---|
| `id` | INTEGER PK | |
| `order_id` | BIGINT NOT NULL FK ml_orders_cache.order_id | |
| `item_id` | VARCHAR(30) NOT NULL | MLB do anúncio |
| `title` | VARCHAR(500) NOT NULL | Título do anúncio |
| `seller_sku` | VARCHAR(100) | NULL se ML não enviou SKU. **Indexado.** |
| `quantity` | INTEGER NOT NULL | |
| `unit_price` | DECIMAL(10,2) NOT NULL | |
| `category_id` | VARCHAR(30) | Pra futuro filtro por categoria |

Índices:
- `(seller_sku)` — filtros por SKU + join com `sku_financeiro`
- `(order_id)` — agregação

### 4.5 `ml_day_sync_status` (auditoria de cobertura do cache)

| Coluna | Tipo | Nota |
|---|---|---|
| `id` | INTEGER PK | |
| `day` | DATE UNIQUE NOT NULL | O dia coberto |
| `last_synced_at` | DATETIME NOT NULL | |
| `orders_count` | INTEGER NOT NULL | Quantos orders esse dia tem no cache |
| `status` | VARCHAR(20) NOT NULL | `ok` / `partial_error` / `failed` |
| `error_message` | TEXT | NULL em sucesso |

**Política de freshness lida pelo serviço (ver §6):**
- Se `day = hoje`: sempre re-sync.
- Se `day in [hoje-7, hoje-1]` e `last_synced_at > 24h`: re-sync.
- Se `day < hoje-7`: imutável, nunca re-sync (a menos que `status = failed`).

---

## 5. Cliente ML async (`services/ml_client.py`)

Substitui o padrão `requests` síncrono do `Devoluçao/app.py` por `httpx` async, mantendo a mesma estratégia de refresh token.

### 5.1 Interface pública

```python
class MLClient:
    """Cliente HTTP para Mercado Livre. Singleton no app."""

    async def get_order(self, order_id: int) -> dict:
        """GET /orders/{id} — detalhe completo."""

    async def search_orders(self, *, date_from: datetime, date_to: datetime,
                            offset: int = 0, limit: int = 50) -> dict:
        """GET /orders/search — lista paginada do seller no período."""

    async def get_shipment(self, shipment_id: int) -> dict:
        """GET /shipments/{id} — frete, modalidade logística."""

    async def get_item(self, item_id: str) -> dict:
        """GET /items/{id} — título, SKU, listing_type_id."""

    async def get_billing(self, order_id: int) -> dict:
        """Tarifa final pós-refund — endpoint a confirmar em testes."""
```

### 5.2 Auth e refresh

- Singleton mantém `access_token` em memória.
- Cada chamada checa `expires_at - now() < 60s` → dispara refresh antes.
- Refresh é `POST /oauth/token` com `grant_type=refresh_token`. Atualiza tabela `ml_tokens`.
- Se ML responder 401 mesmo com token fresh: 1 retry forçando refresh; segundo 401 = erro propagado.

### 5.3 Retry e rate limit

- Wrapper `tenacity.retry` em todos os métodos:
  - Backoff exponencial: 1s, 2s, 4s (max 3 tentativas).
  - Retry só em 5xx, 429 (rate limit), timeout.
  - 4xx (exceto 429) = erro permanente, não re-tenta.

### 5.4 Logging

- Loga cada chamada: método, path, status, latência.
- Em erro: loga response body (truncado) pra debug.
- Não loga `access_token` em log.

---

## 6. Serviço de sync (`services/ml_sync.py`)

Orquestra o fluxo do botão "Buscar". Função única exposta:

```python
async def ensure_period_synced(date_from: date, date_to: date) -> SyncReport:
    """
    Garante que o cache cobre todo o período pedido.
    Retorna relatório com quantos dias foram (re)sincronizados.

    Algoritmo:
      1. Lista dias entre date_from e date_to inclusive.
      2. Pra cada dia, lê ml_day_sync_status.
      3. Aplica política de freshness:
         - day == today: sempre sync.
         - day in [today-7, today-1] AND last_synced_at < now-24h: sync.
         - day < today-7 AND status != 'failed': pula.
         - Resto: sync.
      4. Dias a sincronizar rodam em paralelo (asyncio.gather, max 5 concurrent
         pra não estourar rate limit).
      5. Pra cada dia: chama ml_client.search_orders com janela do dia,
         pagina até esgotar, faz get_order detalhado pra cada novo order,
         get_shipment + get_item conforme necessário, calcula breakdown_bucket,
         normaliza e salva em ml_orders_cache + ml_order_items_cache.
      6. Atualiza ml_day_sync_status (status='ok' ou 'failed').
    """
```

**Idempotência:** se o mesmo order_id voltar 2x (pedido editado), faz UPSERT.

**Concorrência:** max 5 dias em paralelo. Dentro de cada dia, max 10 orders em paralelo pra detalhar. Configurável via env vars.

**Erro parcial:** se um dia falha, marca `failed` mas continua os outros. UI exibe alerta.

---

## 7. Serviço de agregação (`services/ml_aggregator.py`)

Função pura. Recebe lista de orders (já cacheada) + filtros + cadastro `sku_financeiro` → devolve dict pronto pro frontend.

```python
def aggregate(orders: list[OrderCacheRow],
              items: list[ItemCacheRow],
              sku_financeiro: dict[str, SkuFinanceiroRow],
              filters: FilterParams) -> ResumoFinanceiroResponse:
    """
    Sem I/O. Sem chamadas a DB. Recebe dados, devolve dict.
    Implementa as fórmulas validadas na seção 3 do ESTUDO.
    """
```

Garante que mudanças em fórmula tocam só esse arquivo. Fácil de testar (unit tests com fixtures).

**Quem orquestra:** o router carrega `orders + items + sku_financeiro` do DB, monta `FilterParams` a partir do body, e chama `aggregate()`. Função em si não toca DB.

**Cálculo de MC por linha (referência rápida do ESTUDO §3.5):**

```
base_mc = (modalidade_envio in {'me1', 'outros'}) ? vendas_aprovadas_linha
                                                  : produto_puro_linha

MC = base_mc − custo − imposto − tarifa_liquida − frete_vendedor − refund_parcial
MC% = MC / produto_puro_linha
```

A condicional ME1/Outros (a combinar) é a única exceção. Resto é fórmula direta.

**Saída esperada (schema simplificado):**

```python
class ResumoFinanceiroResponse:
    cards: CardsKPI            # 13 cards
    pizza: list[PizzaSlice]    # 5 fatias com label, valor, pct
    tabela: list[OrderRow]     # cada linha pronta com MC, MC% etc
    pagination: PaginationMeta # total, page, page_size, total_pages
    sync_report: SyncReport    # quantos dias sincronizados nesse fetch
```

---

## 8. API REST (`routers/financeiro_ml.py`)

Prefix `/api/financeiro-ml`. Todas as rotas exigem usuário **Master** (mesmo middleware que `financeiro` boletos).

### 8.1 Resumo Financeiro

| Método | Rota | Descrição |
|---|---|---|
| POST | `/resumo` | Body: filtros (data_inicio obrigatório, data_fim obrigatório, sku?, mlb?, status?, modalidade?, tipo_frete?, custo_imposto?, page, page_size, considerar_frete_comprador). Resposta: `ResumoFinanceiroResponse`. **Dispara sync se necessário** (pode demorar segundos na 1ª chamada). |
| GET | `/export?formato=excel\|csv&<filtros>` | Stream do arquivo gerado server-side via `openpyxl` (já no projeto) ou CSV puro. Mesma agregação, sem paginação. |

### 8.2 Cadastro SKU custo/imposto

| Método | Rota | Descrição |
|---|---|---|
| GET | `/skus?q=&page=&page_size=` | Lista paginada. `q` busca por SKU. |
| PUT | `/skus/{sku}` | Body: `{custo_unit, imposto_pct}`. Cria ou atualiza. |
| DELETE | `/skus/{sku}` | Remove cadastro. |
| POST | `/skus/import-excel` | Multipart upload `.xlsx` com colunas `sku, custo_unit, imposto_pct`. Faz upsert em lote. Resposta: `{created, updated, errors[]}`. |

### 8.3 Health / Admin

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | Testa token ML válido. Útil pra alertar se refresh falhou. |
| GET | `/sync-status?date_from=&date_to=` | Mostra cobertura do cache num período (debug). |

### 8.4 Schemas Pydantic — convenções

- Datas no formato ISO 8601 (`YYYY-MM-DD`).
- Valores monetários como `Decimal` no backend, `number` no JSON com 2 casas.
- Filtros opcionais aceitam `null` ou ausentes (significam "Todos").

---

## 9. Frontend

### 9.1 Rotas e arquivos

```
frontend/src/pages/
  FinanceiroMLResumo.jsx       ← painel principal (espelho do MT)
  FinanceiroMLSkus.jsx         ← cadastro custo/imposto

frontend/src/components/financeiro-ml/
  KPICards.jsx                 ← 13 cards
  PizzaChart.jsx               ← donut Recharts
  FiltrosBar.jsx               ← filtros + botão Buscar
  TabelaVendas.jsx             ← TanStack Table
  SkuRow.jsx, SkuEditModal.jsx, SkuImportExcelDialog.jsx
```

Rotas adicionadas em `App.jsx`:
- `/financeiro-ml/resumo` → `FinanceiroMLResumo`
- `/financeiro-ml/skus` → `FinanceiroMLSkus`

Menu lateral ganha nova entrada "Financeiro ML" (visível só pro Master).

### 9.2 Fluxo "Buscar" no client

1. Usuário preenche filtros, clica Buscar.
2. Front dispara mutation TanStack Query `POST /api/financeiro-ml/resumo`.
3. Durante o request: skeleton nos cards, spinner no botão. Backend pode demorar segundos.
4. Resposta chega: hidrata todos os cards, pizza, tabela.
5. Query é cacheada client-side por hash dos filtros — se o usuário trocar de aba e voltar, volta na mesma view sem refetch.

### 9.3 Componentes-chave

- **`KPICards`**: 13 cards. Cada um aceita props `{label, value, sub?, tooltip?}`. Tooltip via `@radix-ui/react-tooltip`.
- **`PizzaChart`**: `<PieChart>` da Recharts, 5 fatias. Tooltip ao hover. Asterisco fixo embaixo: *"O frete pago pelo comprador não é considerado no gráfico."*
- **`TabelaVendas`**: TanStack Table v8. Sort por qualquer coluna, paginação 50/100/200 controlada pelo backend (server-side pagination).
- **`FiltrosBar`**: inputs `<input type="date">` HTML5 nativos, selects nativos. Tudo controlled. Botão Buscar dispara a mutation.

### 9.4 Página cadastro SKU

- Lista paginada de SKUs cadastrados.
- Busca por SKU/descrição.
- Editar inline (custo e imposto) com debounce 500ms → PUT automático.
- Botão "Importar Excel" abre dialog: arrasta arquivo → preview das primeiras 5 linhas → confirma → POST.
- Botão "Exportar Excel" baixa cadastro atual (útil pra edição em massa offline).

---

## 10. Testes

### 10.1 Backend

Pasta `backend/tests/financeiro_ml/`:

- `test_aggregator.py` — fixtures de orders com casos exemplo (Full c/ frete comprador, Flex c/ frete vendedor, ME1, cancelada, devolução parcial). Cobre todas as fórmulas validadas no ESTUDO §3.
- `test_ml_client.py` — usa `respx` (mock httpx) pra simular respostas ML. Testa refresh token, retry em 429/5xx, sucesso.
- `test_ml_sync.py` — testa política de freshness, idempotência (mesmo order 2x), concorrência (5 dias paralelos).
- `test_routers.py` — testa rotas REST com `TestClient`. Cobre permissão Master, validação Pydantic, filtros aplicados corretamente.

### 10.2 Frontend

- Unit tests dos componentes puros (`KPICards`, `PizzaChart`) com Vitest + React Testing Library.
- Integração: mock TanStack Query response → renderiza tela completa → asserções sobre presença de cards/valores.

### 10.3 Smoke test manual

Pré-checklist antes de merge:
1. Filtrar período 1 dia (hoje) → recebe dados frescos.
2. Filtrar mesmo período de novo → resposta cacheada, < 500ms.
3. Filtrar período histórico (60 dias) → demora primeira vez, rápido depois.
4. Cadastrar custo de 1 SKU → re-filtrar → MC daquele SKU agora aparece.
5. Cancelar uma venda no ML → re-filtrar período de hoje → venda muda de Aprovada pra Cancelada.

---

## 11. Plano de rollout

### 11.1 Sem feature flag

Módulo novo isolado, não toca código existente. Lançamento direto após:
- Testes passando
- Backfill manual de 1 mês de dados pra validação
- Confirmação de Julio que os números batem com o MT (com tolerância de centavos por arredondamento)

### 11.2 Migração de dados

- `sku_financeiro`: começa vazio. Julio importa via Excel a planilha que ele já mantém no MT (pode exportar do MT, ajustar colunas, importar aqui).
- `ml_orders_cache`: começa vazio. Enche sob demanda.
- `ml_tokens`: seed inicial via `.env` (ML_ACCESS_TOKEN etc), depois auto-gerencia.

### 11.3 Deploy

- Migração inline em `database.py → init_db()` cria as 5 tabelas novas no startup.
- Deploy via `publicar_producao.bat` na branch `nvs-production`. Sem downtime (SQLite migração instantânea).
- `.env` em produção precisa de:
  - `ML_CLIENT_ID`, `ML_CLIENT_SECRET`, `ML_REDIRECT_URI`
  - `ML_USER_ID`, `ML_ACCESS_TOKEN`, `ML_REFRESH_TOKEN` (seed)
  - `ML_SYNC_MAX_DAYS_PARALLEL=5` (opcional)
  - `ML_SYNC_MAX_ORDERS_PARALLEL=10` (opcional)

### 11.4 Como medir sucesso

- Após 1 semana: dashboard interno mostra X consultas/dia, Y% cache hit rate, Z chamadas ML/dia.
- Antigra cancela assinatura MT (ou degrada plano) → economia mensal validada.

---

## 12. Riscos e mitigações

| Risco | Impacto | Mitigação |
|---|---|---|
| Token ML expira e refresh falha | Painel para de funcionar | Endpoint `/health` + alerta. Backup: reseedar via `.env`. |
| Rate limit ML (1000 req/h aproximado) | Sync lento ou erros | Retry com backoff (tenacity). Paralelismo configurável. |
| Pedido ML retorna campo inesperado | Crash do aggregator | `raw_json` salvo pra debug. Aggregator com defensive defaults. |
| Cadastro SKU desatualizado | MC errada silenciosa | UI da tabela mostra ícone "sem cadastro" na linha → Julio sabe que MC é fake. |
| Banco SQLite cresce muito | Performance degrada | `raw_json` toma maior espaço; podemos arquivar/compactar dados > 1 ano. (Não pra fase 1.) |
| Pedido alterado retroativamente no ML | Cache fica desatualizado | Política "8+ dias = imutável" tem o trade-off. Em prática raríssimo no ML. |

---

## 13. Dúvidas que se resolvem em testes (herdadas do ESTUDO §12)

Mantidas aqui pra rastreabilidade — não bloqueiam a spec, mas precisam ser respondidas no primeiro PR.

- Confirmar campos ML pra `frete_vendedor` (provável: `shipping.list_cost`).
- Distinguir cancelamento total vs devolução parcial (provável: `order.status` vs `order.refunds`).
- Mapear 7 rótulos do dropdown "Tipo do Frete" pros valores reais de `shipping.logistic_type` + `shipping.mode`.
- Comportamento exato do checkbox "Considerar frete comprador" no card MC.

Quando o primeiro fetch funcionar, abrir 1 pedido de cada tipo e atualizar o ESTUDO + esta spec com as descobertas. Não é blocker.

---

## 14. Próximos passos

1. **Revisão desta spec pelo Julio.**
2. Após aprovação: gerar `docs/superpowers/plans/2026-05-XX-mercado-turbo-resumo-financeiro.md` quebrando em tasks executáveis.
3. Execução por subagents (TDD por módulo).
4. Smoke test manual.
5. Deploy.
