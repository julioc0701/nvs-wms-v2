# Mercado Turbo — Análise Financeira (NVS-WMS)

> **Comece por aqui.** Este documento é o ponto único de entrada pro projeto. Se você chegou agora, leia tudo antes de mexer em código.

---

## 1. O que é este projeto

A Antigra (loja `NOVAESMOTOPEÇAS` no Mercado Livre) pagava assinatura mensal do SaaS **Mercado Turbo** principalmente pelo painel **"Resumo Financeiro"** — um dashboard que cruza vendas ML com cadastro local de custo/imposto e calcula margens.

Este projeto **replica esse painel dentro do NVS-WMS** (sistema próprio em FastAPI + React já em produção), eliminando a dependência do SaaS. O painel se chama internamente **"Análise Financeira"**.

### Por que internalizar
- ✂️ Eliminar custo recorrente do Mercado Turbo
- 🧩 Integrar com o resto do NVS (mesmo SKU, mesmo banco, mesmo login)
- 🔧 Liberdade de evolução (sem esperar features do SaaS)

### Escopo da fase 1 (que está implementada)
- Cards KPI: Vendas Aprovadas/Canceladas, Faturamento ML, Custo & Imposto, Tarifa, Frete Total, Margem de Contribuição
- Cards secundários: por Tipo de Frete, Qtd Vendas, Tickets Médios, Devoluções Parciais
- Filtros: Data início/fim, Status, SKU, MLB, Modalidade, Tipo de Frete, Custo & Imposto
- Pizza chart (composição % sobre Vendas Aprovadas)
- Tabela detalhada 15 colunas, paginada
- Export Excel/CSV
- Cadastro SKU custo/imposto (página própria + import Excel)

### Fora de escopo (não implementado)
- "Nivelar Custo & Imposto" / "Nivelar SKU" (edição em massa retroativa)
- "Reaver Dias Perdidos" — não precisa, cache enche sob demanda
- "Ranking de Produtos"
- Multicontas — só `NOVAESMOTOPEÇAS`

---

## 2. Estado atual (o que funciona)

Branch: `feature/financeiro-ml`. **Pronto pra merge após cadastro SKU completo.**

| Componente | Status |
|---|---|
| Sync ML → cache local | ✅ funcional (com retry, timezone BRT, paralelismo configurável) |
| Aggregator (cards + pizza + tabela) | ✅ funcional, **bate 100%** com MT no subset comparado |
| Cadastro SKU (CRUD + Excel import) | ✅ funcional |
| UI completa (página Análise Financeira + Cadastro SKU) | ✅ funcional |
| OAuth ML + refresh automático | ✅ funcional |
| 25 testes unitários | ✅ todos passando |

**Validado contra exports reais do MT (dois Excels de 26/05/2026):**
- Universe (presença de pedidos): **794/794 match** (100%)
- Cards globais cruzando subset:
  - Vendas Aprovadas: ✅ R$ 46.828,96 idêntico
  - Vendas Canceladas: ✅ R$ 1.295,30 idêntico
  - Frete Comprador/Vendedor: ✅ idêntico (centavos)
  - Tarifa: ✅ R$ 5.046 (diff +R$ 3 por timing)
  - Quantidades aprovadas/canceladas: ✅ idênticas
- Linhas individuais (749 pedidos primeira rodada): **100% match** em 6 colunas numéricas

### Bug aberto (próximo a atacar)
**SKU de variação não extraído**: para anúncios com variações de produto, o ML retorna `item_id_variation_id` em vez do SKU "humano" cadastrado pelo seller. Resultado: 44 linhas (5% das vendas hoje) sem cadastro de custo → MC inflada em ~R$ 1.000. Detalhes em §7.

---

## 3. Estrutura de arquivos

```
warehouse-picker v2/
│
├── Mercado Turbo/                          ← PASTA DO PROJETO (docs + ref)
│   ├── README.md                           ← este arquivo
│   ├── ESTUDO_RESUMO_FINANCEIRO.md         ← entendimento profundo + fórmulas
│   └── referencia/
│       └── MercadoTurbo_Financeiro_*.xlsx  ← snapshots do MT pra validação
│
├── docs/superpowers/
│   ├── specs/2026-05-26-mercado-turbo-resumo-financeiro-design.md
│   └── plans/2026-05-26-mercado-turbo-resumo-financeiro.md
│
├── backend/financeiro_ml/                  ← CÓDIGO BACKEND
│   ├── __init__.py
│   ├── models.py          — SQLAlchemy: MLTokens, SkuFinanceiro, MLOrderCache, MLOrderItemCache, MLDaySyncStatus
│   ├── client.py          — MLClient async (httpx + tenacity + OAuth refresh)
│   ├── sync.py            — ensure_period_synced (cache por dia)
│   ├── aggregator.py      — função pura aggregate() → cards/pizza/tabela
│   ├── sku_service.py     — CRUD do cadastro custo/imposto + import Excel
│   ├── router.py          — endpoints /api/financeiro-ml/*
│   └── tests/             — pytest, 25 testes
│
└── frontend/src/financeiro-ml/             ← CÓDIGO FRONTEND
    ├── api.js                              — wrappers fetch
    ├── pages/Resumo.jsx                    — Análise Financeira (painel principal)
    ├── pages/Skus.jsx                      — Cadastro Custo SKU
    └── components/
        ├── KPICards.jsx                    — 10 cards (5 coloridos + 5 brancos)
        ├── PizzaChart.jsx                  — donut Recharts
        ├── FiltrosBar.jsx                  — 9 filtros + checkbox + botão Buscar
        ├── TabelaVendas.jsx                — TanStack Table com sort + paginação
        └── Tooltip.jsx                     — wrapper Radix
```

**Tudo que diz respeito a "Mercado Turbo" tem prefixo `financeiro_ml` / `financeiro-ml` / `MLClient` pra ser facilmente identificável e — se necessário no futuro — removível em bloco.**

---

## 4. Arquitetura (alto nível)

```
[Mercado Livre API]
       ↑ (httpx async)
       │
[backend/financeiro_ml/client.py]    ← OAuth + refresh + retry (tenacity)
       ↓
[backend/financeiro_ml/sync.py]      ← orquestra cache por dia
       ↓
[SQLite warehouse_v3_local.db]
  - ml_orders_cache         (snapshot dos pedidos ML)
  - ml_order_items_cache    (items dos pedidos)
  - ml_day_sync_status      (auditoria de cobertura)
  - ml_tokens               (OAuth state)
  - sku_financeiro          (custo/imposto cadastrados localmente)
       ↑
[backend/financeiro_ml/aggregator.py] ← função pura: cards/pizza/tabela
       ↑
[backend/financeiro_ml/router.py]     ← POST /resumo, /export, CRUD /skus
       ↑ (JSON REST)
       │
[frontend/src/financeiro-ml/pages/Resumo.jsx] ← UI React
```

**Princípios:**
- Cliente ML isolado; resto do código nunca chama URL direto
- Aggregator é função pura (sem I/O) → unit testável
- Cache compartilha SQLite com o resto do NVS (mesma DB, mesma transação)
- Master-only via stub `require_master()` (ver §7 — pendência de auth real)

### Fluxo "Buscar" no painel
1. User preenche filtros, clica **Buscar**
2. Frontend faz `POST /api/financeiro-ml/resumo` com filtros
3. Router calcula período → chama `ensure_period_synced` que:
   - Lista os dias do período (estende 1 dia atrás pra cobrir vendas pagas hoje mas criadas ontem)
   - Pra cada dia: verifica freshness (hoje = 5min TTL; recente ≤7d = 24h; antigo = imutável)
   - Dias que precisam: chama ML `/orders/search` em paralelo (sem 5/dia + sem 10/order)
   - Pra cada order novo: 2-3 calls ML (/shipments, opcional /discounts, opcional /shipments/X/costs)
4. Router carrega orders + items + cadastro_sku do SQLite
5. Aplica filtros SQL (status, mlb, modalidade, tipo_frete, custo_imposto) e Python (custo_imposto, considerar_frete_comprador)
6. Chama `aggregate(orders, items, skus, considerar_frete_comprador)` → dict de KPIs
7. Aplica paginação à tabela
8. Retorna JSON
9. Frontend renderiza com TanStack Query

---

## 5. Bugs descobertos e corrigidos durante o desenvolvimento

Toda divergência ML × MT que tropeçamos virou um fix permanente. Documentação resumida — para os detalhes formais ver `ESTUDO_RESUMO_FINANCEIRO.md` §15.

| # | Bug | Causa raiz | Fix |
|---|---|---|---|
| 1 | `frete_vendedor` errado em 25% das vendas | Usávamos `shipping_option.list_cost` (cheio); MT usa `list_cost − cost` (subsídio absorvido) | Fórmula `max(0, list_cost - cost)` |
| 2 | `faturamento_ml` errado em 33% (com cupom) | Cupom ML invisível em `/orders/{id}` | Endpoint `/orders/{id}/discounts`, subtrai cupons type=coupon |
| 3a | Flex sem frete (5 casos) — Mercado Pontos puro | ML banca 100% via loyal subsidy; campo só em `/shipments/{id}/costs` | `receiver.save` quando `sender.cost = 0 AND type=loyal` |
| 3b | Pack rateado (2 casos) | Mesmo shipment cobrado em N orders do carrinho | Persistir `shipment_id`; agrupar e dividir frete por N orders |
| 3c | Flex ratio compartilhado (2 casos R$ 0,89) | ML banca ratio, seller absorve mandatory pequeno | `sender.save` quando `type=ratio AND sender.cost > 0 AND logistic_type=self_service` |
| 4a | 22 vendas faltando — timezone | ML retorna `date_created` em fuso `-04:00`; vendas da madrugada BRT caíam no dia anterior | `_to_brt_naive()` converte tudo pra `-03:00` antes de salvar |
| 4b | 7 vendas faltando — criadas em D-1 pagas em D | MT usa `date_closed`; nós usávamos `date_created` | Query `COALESCE(date_closed, date_created)`; sync estende 1 dia |
| 5 | Falso positivo loyal em Full c/ frete grátis | Aplicávamos `receiver.save` sempre que havia loyal, mas em Full+ratio o seller paga | Guarda `sender.cost == 0` antes de usar `receiver.save` |
| 6 | Card global incluía frete_comprador | Coluna do Excel inclui, card global NÃO | Card global = `Σ produto - cupom`; tabela mantém `produto + frete - cupom` |
| 7 | Sync engolia 400 erros silenciosamente | `asyncio.gather(return_exceptions=True)` mascarava `UnboundLocalError` em `logistic_type` | Reordenar variável; logging de erros engolidos |
| 8 | SKU de variação não extraído (44 linhas) | ML retorna `MLB...variation_id` em vez do SKU "humano"; estamos lendo da raiz do anúncio | **ABERTO** — ver §7 |

---

## 6. Como rodar

### Pré-requisitos
- macOS (também roda Linux). Windows não testado.
- Python 3.12 + .venv local em `.venv/`
- Node.js + npm em PATH (`nvm use` se necessário)

### Variáveis de ambiente (`.env` na raiz)
```bash
ML_CLIENT_ID=8806146527865119
ML_CLIENT_SECRET=<secret>
ML_USER_ID=221832146
ML_ACCESS_TOKEN=<refresh diariamente>
ML_REFRESH_TOKEN=<token>
ML_REDIRECT_URI=
ML_SYNC_MAX_DAYS_PARALLEL=5
ML_SYNC_MAX_ORDERS_PARALLEL=10
```

Os tokens iniciais foram copiados de `Devoluçao/.env` (outra app que usa a mesma conta ML). Depois do primeiro startup, o NVS gerencia refresh automaticamente via tabela `ml_tokens`.

### Iniciar
```bash
./start.command          # Mac (clique duplo OK)
# ou
./start.sh
```

- Backend: http://localhost:8003
- Frontend: http://localhost:5176
- Docs API: http://localhost:8003/docs

O script `start.sh` agora **mata automaticamente** processos que estejam segurando as portas (SIGTERM + 5s grace + SIGKILL).

### Parar
```bash
./stop.sh
```

### Testes
```bash
cd backend
pytest financeiro_ml/tests/ -v   # 25 testes
```

### Onde estão os logs
```
.run/start_backend.log      ← logs do uvicorn (busca por [BUSCAR])
.run/start_frontend.log     ← logs do vite
```

### Forçar re-sync do dia
Cache de hoje tem TTL de 5 minutos. Se precisar bypassar:
```bash
cd backend
python -c "
import sqlite3
from datetime import date, timedelta
c = sqlite3.connect('warehouse_v3_local.db')
c.execute('DELETE FROM ml_day_sync_status WHERE day IN (?, ?)', (str(date.today()), str(date.today()-timedelta(days=1))))
c.commit()
"
```
Próximo clique em Buscar vai puxar fresh do ML.

---

## 7. Pendências e próximos passos

### 🔴 Bloqueante pra fechamento (alta prioridade)
1. **Fix de SKU em anúncios com variação** (44 linhas, ~5% das vendas)
   - **O problema**: ML retorna `MLB5260901690_182781678874` em vez de `3XSUPORTBIKE` no `item.seller_sku` quando o anúncio tem variações
   - **Onde**: `backend/financeiro_ml/sync.py:_save_order`
   - **Fix proposto**: quando `item.variation_id` existe, fazer call extra a `/items/{item_id}/variations/{variation_id}` pra pegar o `seller_sku` correto. Adiciona ~1 call ML pra 5-10% das vendas.
   - **Custo de impacto**: enquanto não fixar, MC fica inflada ~R$ 1.000-2.000/dia (pq esses SKUs ficam sem cadastro de custo)

### 🟡 Importante (antes de produção)
2. **Auth real Master**
   - `require_master()` é stub que retorna `operator_id=1` sempre
   - Integrar com sistema de operadores do NVS (mesmo padrão do `/financeiro` boletos atual)

3. **Refinar `_save_order` em re-sync**
   - Quando order já existe, só atualizamos status/refund — frete e tarifa congelados. Se ML corrigir esses valores post-factum, perdemos a atualização. Aceitável agora; rever depois.

4. **Endpoint `/billing` pra tarifa pós-refund**
   - Hoje `tarifa_refund` está hardcoded 0. Refunds parciais reduzem tarifa proporcionalmente; precisaria consultar endpoint específico de billing pra preservar essa precisão. Impacto: baixo (raro).

### 🟢 Melhorias (não urgente)
5. **Botão "Forçar atualização"** no front pra bypass do cache 5min
6. **Cadastro de operador na coluna `updated_by`** do `sku_financeiro` (hoje hardcoded `operator_id=1`)
7. **Pizza chart**: melhorar visuals (cores, labels)

---

## 8. Decisões importantes (resumo)

| Decisão | Justificativa |
|---|---|
| Módulo isolado dentro do NVS (pasta `financeiro_ml/`) | Reusa infra (DB, auth, deploy) sem misturar arquivos com outros módulos |
| Cache local SQLite por dia + TTL | Evita custo ML rate-limit; UX rápida |
| Cliente ML async em httpx (não wrapper) | Wrappers Python pra ML estão abandonados; controle total |
| 1 conta só (`NOVAESMOTOPEÇAS`) | Simplifica autenticação e schema |
| Alíquota única de imposto por SKU | Antigra não diferencia por estado/regime |
| Fórmulas validadas contra Excel real do MT | Cada divergência foi caçada e corrigida; doc completo no ESTUDO §15 |
| Frontend usa TanStack Query/Table + Recharts + Radix Tooltip | Padrão moderno, headless, leve, MIT |

---

## 9. Cadastro inicial de SKUs (como foi feito)

Em 26/05/2026, importamos massivamente custos de **186 SKUs** lendo a coluna "Custo (-)" do Excel exportado do MT:

```python
# Script ad-hoc executado uma vez (não está versionado)
import pandas as pd
from decimal import Decimal
import sys; sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv('../.env')
import models  # registra Operator
from financeiro_ml.sku_service import upsert_sku

mt = pd.read_excel('../Mercado Turbo/referencia/MercadoTurbo_Financeiro_26_05_2026_a_26_05_2026.xlsx',
                    sheet_name='table-pedidos1')
mt.columns = ['order_id_raw'] + [f'c{i}' for i in range(24)]
mt['sku']   = mt['c8'].astype(str).str.strip()
mt['custo'] = pd.to_numeric(mt['c14'], errors='coerce').fillna(0)
mt['qtd']   = pd.to_numeric(mt['c12'], errors='coerce').fillna(0)

ok = mt[(mt['sku'].str.len() > 0) & (mt['custo'] > 0) & (mt['qtd'] > 0)].copy()
ok['custo_unit'] = (ok['custo'] / ok['qtd']).round(2)

for sku, custo in ok.groupby('sku')['custo_unit'].max().items():
    upsert_sku(sku, custo_unit=Decimal(str(custo)),
                imposto_pct=Decimal('9.00'), updated_by_id=1)
```

**Fórmula chave**: a coluna "Custo (-)" no Excel é o **total da linha** (`custo_unit × qty`). Pra obter o unitário cadastrado: dividir pela qty. Validado: SKU `BURRINHO` com qty=1 mostra 17,50, com qty=2 mostra 35,00 e com qty=3 mostra 52,50 — padrão proporcional confirma que é total. Cadastro correto: `custo_unit = 17,50`.

**Alíquota**: fixada em 9% pra todos os SKUs (decisão Antigra).

### Pra atualizar cadastro depois
Tem 3 caminhos:

a) **UI**: `/financeiro-ml/skus` permite editar SKU por SKU
b) **Import Excel**: na mesma página tem upload de planilha `(sku, custo_unit, imposto_pct)`
c) **Script ad-hoc** como o acima (massa)

---

## 10. Glossário ML / MT

| Termo | Significado |
|---|---|
| `MLB` | Mercado Livre Brasil. Prefixo de IDs de anúncio (ex `MLB4692782548`) |
| `order_id` | ID único da venda (formato `2000016...`). Chave do nosso cache |
| `seller_custom_field` | SKU "humano" cadastrado pelo vendedor no anúncio |
| `seller_sku` | Variante de campo (ML usa intercambiavelmente, mas pra anúncios com variação o SKU real fica em `/variations/{id}`) |
| `listing_type_id` | Modalidade do anúncio ML: `gold_special` (Premium), `gold_pro` (Clássico), `free` (Grátis) |
| `logistic_type` | Tipo logístico do shipment: `fulfillment` (Full), `self_service` (Flex), `drop_off` / `cross_docking` (Places/Coleta) |
| `shipping_mode` | `me1` (Mercado Envios 1), `me2` (Mercado Envios 2), `not_specified` |
| `shipping_option.cost` | Frete pago pelo comprador (após descontos ML) |
| `shipping_option.list_cost` | Frete "cheio" antes de descontos |
| `cupom_seller` | Desconto bancado pelo seller (campanha cupom ML). Reduz faturamento. |
| `loyal subsidy` | Mercado Pontos: ML banca frete |
| `ratio subsidy` | ML banca parte proporcional + seller absorve mandatory |
| `pack_id` | ID do carrinho (múltiplas vendas no mesmo pedido do comprador) |
| `shipment_id` | ID do envio. Multi-pack compartilham 1 shipment → MT rateia frete |

---

## 11. Onde olhar antes de fazer perguntas

1. **`Mercado Turbo/ESTUDO_RESUMO_FINANCEIRO.md`** — 15 seções com tudo: contexto, fórmulas validadas, decisões, glossário, validações
2. **`docs/superpowers/specs/2026-05-26-mercado-turbo-resumo-financeiro-design.md`** — design técnico detalhado
3. **`docs/superpowers/plans/2026-05-26-mercado-turbo-resumo-financeiro.md`** — 28 tasks TDD originais (referência histórica do build)
4. **Código** — comentários inline densos em `sync.py` e `aggregator.py` (cada fix tem o "porquê")
5. **Logs** — `[BUSCAR]` no `.run/start_backend.log` mostra cada etapa de uma busca end-to-end com timing

---

## 12. Resumo executivo (TLDR)

- Painel "Análise Financeira" funcional dentro do NVS, substitui o Mercado Turbo
- Backend em `backend/financeiro_ml/`, frontend em `frontend/src/financeiro-ml/`
- Validado contra Excel real do MT: 100% match em colunas principais
- 25 testes unitários passando
- 1 bug aberto (SKU variação) impacta ~5% das vendas — fix conhecido, ~1 call ML extra
- 186 SKUs já cadastrados com custo + 9% imposto
- Branch `feature/financeiro-ml` — depois do fix do bug 8, merge → main → deploy via `nvs-production`
