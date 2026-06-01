# BÍBLIA — Robô financeiro_ml (Mercado Turbo) — Estabilização do 429

> Documento de handoff para uma equipe nova assumir o projeto.
> Data: 2026-06-01. Cobre TODO o trabalho, análise, validações e ações deste ciclo.
> Loja única (P0): seller_id **221832146** (financeiro_ml / Mercado Turbo).

---

## 0. TL;DR (leia isto primeiro)

- **Sintoma:** o robô que busca dados financeiros do Mercado Livre trava em produção há ~1 semana com erro **429**. O painel (que só lê cache) funciona o tempo todo.
- **Causa raiz (PROVADA):** o 429 é um **bloqueio de borda do AWS CloudFront** (CDN na frente da API do ML), disparado por **RAJADA** de chamadas. **NÃO é castigo/ban de IP. NÃO é o rate-limit por Client-ID do ML.** Acontece *antes* de a requisição chegar na API do ML.
- **De onde vem a rajada:** pra cada venda, o robô faz **1 chamada `/shipments/{id}` por pedido** (pra achar o *frete vendedor*). Em backfill de muitos dias, isso vira **milhares de chamadas de enfiada** → CloudFront corta.
- **O que já está em produção (Fase 1):** janela do poller reduzida **14→7 dias** + **freio duro** no 429 (para o ciclo na hora em vez de seguir martelando). **Deploy feito, robô ligado, freio funcionando.** O doom-loop acabou.
- **Fato novo medido em prod:** o CloudFront corta a rajada cedo — tripou com **~35 chamadas** a partir do IP de datacenter. Per-pedido **não dá volume** nesse ambiente.
- **Direção da solução:** **híbrido** — relatório de faturamento **em lote** (download de período fechado) pro histórico (mata a rajada) + `/shipments` **ao vivo, gota a gota** só pros pedidos frescos do mês corrente.
- **Fio solto principal:** confirmar o endpoint de **download** do relatório de faturamento (tentativa deu 403). É a peça que destrava o caminho em lote.

---

## 1. Arquitetura do sistema (contexto)

- **Padrão CQRS-pobre:**
  - **Painel** (`/api/financeiro-ml/resumo`) **só lê o cache** (0 chamadas ao ML). Por isso funciona mesmo com o robô travado.
  - **Robô** (poller + worker) **busca do ML e enche o cache**.
- **Stack:** FastAPI + SQLite (backend, porta 8001) / React + Vite (frontend) / deploy no **Railway** pela branch **main** (auto-build).
- **Produção:** projeto Railway `virtuous-unity`, serviço **nvs-wms-v2**, URL `https://nvs-wms-v2-production.up.railway.app`, router montado em `/api/financeiro-ml`.
- **Bancos:** o robô v2 escreve no banco do financeiro (`FINANCEIRO_ML_DATABASE_URL`) via `FinSessionLocal`. (Cuidado: existe tabela v1 antiga — ver §12 observabilidade.)

### Arquivos-chave (`backend/financeiro_ml/`)
| Arquivo | Papel |
|---|---|
| `client.py` | Cliente ML async (OAuth, refresh, throttle global, backoff 429). |
| `poller.py` | A cada ~6h enfileira 1 PollTask por seller cobrindo a janela fresca. |
| `worker.py` | Worker único (escritor). Processa dias: search + enriquecimento (shipment) + upsert. Trata 429. |
| `freshness.py` | Decide quais dias re-sincronizar. Define `FRESH_WINDOW_DAYS`. |
| `sync.py` | Sync v1 (local). Mesma lógica de rajada (get_shipment por pedido). |
| `calc.py` | `build_order_row`: cálculo puro de um pedido → linha do cache. |
| `aggregator.py` | Agrega pro painel. **Faz o rateio de frete por carrinho/pack** (importante, §7). |
| `router.py` | Endpoints (resumo, export, backfill, _debug/*). |

---

## 2. O problema

- Robô em produção trava com **429** há ~1 semana, em ciclo: busca → leva 429 → insiste → fica pior.
- O **painel não quebra** (lê cache). Só o robô (que busca no ML) apanha.
- **Mistério que confundiu por dias:** *local funciona, produção não*, com **o mesmo código**.

---

## 3. CAUSA RAIZ — bloqueio de borda CloudFront (PROVADO)

O 429 **NÃO** é:
- ❌ Ban/castigo de IP (seria **403**, não 429).
- ❌ O rate-limit documentado por Client-ID da API do ML.
- ❌ Token/escopo errado.

O 429 **É**:
- ✅ **AWS CloudFront** (CDN/borda na frente da API do ML) **cortando uma RAJADA** de requisições, **antes** de chegar na API do ML.

### Evidência (capturada nos headers do 429)
- `server: CloudFront`
- `x-cache: "Error from cloudfront"`
- corpo **vazio** (não é o JSON de rate-limit da API ML).
- Chamada **isolada** passa: `200`, `x-cache: "Miss from cloudfront"`.

### Por que local funciona e produção não (mesmo código)
- **Local** = IP **residencial** → CloudFront é mais tolerante; e muitos dias já estão em cache (poucas chamadas).
- **Produção** = IP de **datacenter** → CloudFront é durão; e o robô varre tudo de uma vez (rajada).
- **Não dá pra "rodar produção da casa".** A solução tem que **eliminar a rajada**, não trocar o IP.

> Instrumentação que provou isso: `client.py::_diag_429()` captura `cf-ray/server/x-cache/content-type/body` em todo 429. O endpoint `_debug/probe-search` faz 1 chamada isolada e reporta `egress_ip` (via ipify) + headers.

---

## 4. De onde nasce a rajada (no código)

Pra montar a margem de cada venda, falta **1 número**: o **frete do vendedor**.

- De **`/orders/search`** (50 pedidos/página) já vêm: **tarifa de venda** (`sale_fee`), **frete comprador** (`payments[].shipping_cost`), valores, status, sku.
- Só o **frete vendedor** precisa de **`/shipments/{id}` por pedido** (`frete_vendedor = max(0, list_cost − cost)`).

Fluxo do robô (`worker.py`):
1. Poller enfileira a janela (era 14 dias, agora 7).
2. Worker, por dia: `search` paginado → pra cada pedido **novo/alterado**, chama `_enrich_and_build` → **`get_shipment`** (+ às vezes `get_shipment_costs`/`get_order_discounts`).
3. `_unchanged_in_cache` pula pedido já em cache sem mudança (poupa chamadas em regime).

**A rajada = backfill / cache frio:** quando há muitos pedidos novos em muitos dias, são **milhares de `/shipments` de enfiada** → CloudFront corta.

---

## 5. War rooms / análise dos especialistas — conclusões

- O **frete vendedor por pedido** é a única coisa que força a rajada; todo o resto vem de 1 `search`.
- **Não há multiget de `/shipments`** documentado → 1 chamada por pedido é inevitável **pela via per-pedido**.
- O candidato para pegar frete **em lote** = **Relatórios de Faturamento (billing)** por período.
- Régua e diagnóstico: o gargalo é a **borda CloudFront por rajada**, não a cota por Client-ID.

---

## 6. Validações feitas (com dados reais de produção)

### 6.1 O relatório de billing dá o frete por pedido (confirmado)
Endpoint: `GET /billing/integration/periods/key/{KEY}/group/ML/details?document_type=BILL`
- Cada linha tem: `charge_info` (`transaction_detail`, `detail_amount`, `detail_sub_type`), `sales_info[].order_id`, `shipping_info` (`shipping_id`, `receiver_shipping_cost`), `items_info`.
- Exige permissão funcional **"Faturamento"** (escopo `urn:ml:mktp:invoices`) + **re-autorizar** o token (escopo congela no grant).
- **Rate limit do billing: 5 req/min.**

**Frete vendedor (billing) × ao-vivo (`/shipments`): 3/3 EXATO** → 8,05 / 6,55 / 6,75.

### 6.2 Dia inteiro 31/05–01/06 — nosso sistema × planilha de referência do MT
988 pedidos cruzados (planilha em `Mercado Turbo/referencia/`):

| Campo | Bate | Observação |
|---|---|---|
| Valor Unit | **100%** | da busca |
| Tarifa de Venda | **100%** | da busca (`sale_fee`) |
| SKU | **100%** | da busca |
| Status | **100%** | paid→Pago, cancelled→Cancelado |
| Id Frete | **100%** | `shipping.id` |
| Frete Comprador | **98,6%** | 14 diffs = subsídio Flex/loyal (app trata via `shipment_costs`, `calc.py:60-75`) |
| Frete Vendedor | **98,8%** | 12 diffs = **carrinho/pack** (app divide o frete via `aggregator.py:124`, "rateio de pack"); nosso teste cru = exatamente 2× o do MT |
| Faturamento ML | — | **coluna derivada do MT**, não é campo cru do ML |
| Custo / Imposto / Margem | — | **dados internos do MT** (cadastro de custo), não vêm do ML |

**Conclusão:** nossa lógica reproduz o MT. As pequenas diferenças NÃO são erro — são dois refinamentos que o app **já tem** (rateio de pack + fallback de subsídio) e o script de teste cru não aplicou.

### 6.3 Timing do extrato (quanto o ML demora pra fechar o frete)
Medido em **750 cobranças reais**:
- **Lag venda→cobrança: mediana 1 dia, p90 4 dias, máx 48 (outliers/cancelamentos).**
- O frete posta **rápido e diariamente** (charge_date ≈ sale_date + 1 dia).

---

## 7. Caminho do relatório em lote (billing) — descobertas técnicas

- **Paginação capada:** offset acima de ~8–10 mil → **422**; cursor (`last_id`) **satura** (sempre volta do começo, 2024-10-31). O período de junho tem **~66.000 linhas** → **não dá pra alcançar os dias recentes navegando**. (E o robô bateria no mesmo muro.)
- **Filtros `sort`/`date_from` são ignorados** nesse endpoint.
- **A porta certa = baixar o ARQUIVO do período:**
  - `GET /billing/integration/periods/key/{KEY}/documents?group=ML&document_type=BILL` lista os documentos/faturas.
  - **Período FECHADO** (ex.: abril, key `2026-04-01`): documentos com `document_status: "BILLED"` e **`files: [{ file_id, reference_number }]`** → **arquivo completo pra download, sem o muro de 10k.**
  - **Período ABERTO** (mês corrente, junho `2026-06-01`): `files: []` (só é gerado quando o mês fecha, ~dia 13 do mês seguinte).
- **FIO SOLTO:** tentativas de baixar o arquivo (`/documents/{id}/files/{file_id}` e variações) deram **403/404**. Falta acertar o **endereço/permissão de download**. **É a peça que falta pra fechar o caminho em lote.**

---

## 8. A solução (direção acordada)

**Híbrido — não muda o cache/CQRS do front, muda só COMO o robô busca o frete:**

1. **Histórico (meses fechados):** **baixar o arquivo do relatório** do período → todo o frete de uma vez, **zero rajada**. Mata a rajada de backfill (a que derrubava produção).
2. **Mês corrente (frescos):** `/shipments` **ao vivo**, só dos pedidos **novos**, **gota a gota** (lotes pequenos com intervalo). Dado o quão sensível é o CloudFront (§11), tem que ser **muito gentil**.

---

## 9. Ações já executadas (Fase 1) — DEPLOYADO EM PRODUÇÃO

**Objetivo:** atacar a rajada com a menor mudança possível, com rede de segurança.

| Mudança | Arquivo | Detalhe |
|---|---|---|
| Janela do poller **14→7** | `freshness.py` | `FRESH_WINDOW_DAYS` agora lê env `FINANCEIRO_ML_FRESH_WINDOW_DAYS` (default 7). Metade do volume por ciclo. |
| **Freio duro no 429** | `worker.py` | No 429 do poll, **para o ciclo** (`break`) em vez de pular o dia e seguir (`continue`). Insistir só prolonga o bloqueio. |
| Testes ajustados | `tests/test_worker.py`, `tests/test_poller.py` | **98 testes passando.** |

- Commit **`18239d4`** na `main` → Railway buildou → deployment `1913e88f` **Active**.
- `ENABLE_FINANCEIRO_ML_ROBOT` setado **`true`** (robô ligado).

### Resultado observado em produção (log do robô)
```
[WARNING] worker.429 seller=221832146 day=2026-06-01 — freio: parando ciclo
[INFO]    worker.task_done seller=221832146 kind=poll days=7 ml_calls=35
```
- ✅ Janela 7 no ar (`days=7`).
- ✅ **Freio funcionou:** fez 35 chamadas, levou 429, **parou o ciclo**. **Acabou o doom-loop.**
- ⚠️ O CloudFront cortou a rajada com **~35 chamadas** (IP de datacenter). Per-pedido **não dá volume** aqui.

---

## 10. Estado atual (em 2026-06-01)

- **Robô:** ON e **seguro** (freio garante que não martela). A cada ~6h tenta um pouco e para se levar 429.
- **CloudFront:** corta a rajada cedo (~35 chamadas) a partir do IP de datacenter.
- **Painel:** funcionando (lê cache).
- **Conclusão prática:** estabilizamos o sangramento (sem doom-loop), mas **per-pedido não enche dados em volume** nesse ambiente → o volume tem que vir do **relatório em lote**.

---

## 11. Próximos passos / fios soltos (para a equipe nova)

1. **[P0] Destravar o download do relatório de billing.** Resolver o 403 do `files/{file_id}`. Confirmar formato (CSV/XLSX), parsear, e bater o frete por `order_id`. Isso habilita o histórico em lote → mata a rajada de verdade.
2. **[P1] Fase 2 — trickle pro mês corrente.** Implementar **teto de enriquecimentos por ciclo** (`_sync_day` aceitando budget) + lotes pequenos com intervalo + freio. Espalha o `/shipments` dos pedidos frescos sem rajada.
3. **[P1] Observabilidade.** O endpoint `_debug/sync-status` lê a tabela **v1 antiga** (`database.SessionLocal` + `financeiro_ml.models`), **não** o que o robô v2 escreve (`FinSessionLocal` + `models_v2`). Mostra dados velhos. **Criar um sync-status v2** pra enxergar o robô de verdade.
4. **[P2] `ML_THROTTLE_INTERVAL_SEC`.** Já existe em prod (valor não lido neste ciclo). Avaliar se desacelerar o ritmo ajuda — mas o sinal é que o CloudFront corta por **rajada/volume curto**, então só desacelerar pode não bastar; o lote é o fix estrutural.
5. **[P2] Frete vendedor do histórico 100% via billing?** Se o relatório em lote cobre o frete dos meses fechados, dá pra **eliminar `/shipments` no histórico** e deixá-lo só pro mês corrente.

---

## 12. Referências e config de produção

### Variáveis de ambiente relevantes (Railway, serviço nvs-wms-v2)
- `ENABLE_FINANCEIRO_ML_ROBOT` — liga/desliga o runtime (worker+poller). Se `false`, **nem o worker sobe** → `/backfill` cria job mas não processa.
- `FINANCEIRO_ML_FRESH_WINDOW_DAYS` — janela do poller (default 7).
- `ML_THROTTLE_INTERVAL_SEC` — intervalo entre chamadas ao ML (throttle global).
- `FINANCEIRO_ML_DATABASE_URL` — banco do robô v2.
- `ML_CLIENT_ID` / `ML_CLIENT_SECRET` / `ML_ACCESS_TOKEN` / `ML_REDIRECT_URI` — OAuth.

### Endpoints úteis (debug — sob `/api/financeiro-ml`)
- `GET  /_debug/sync-status` — status por dia (⚠️ lê v1, ver §11.3).
- `POST /_debug/probe-search` — 1 busca isolada + egress IP + headers (diagnóstico de 429).
- `POST /backfill` — cria job de backfill (precisa do runtime ligado).
- `POST /resumo`, `POST /export` — painel (lê cache).

### Documentação destilada
- `Mercado Turbo/ML_DOC_OFICIAL/` — doc oficial do ML destilada (frete, faturamento, rate-limit, relatórios).
- `Mercado Turbo/referencia/` — planilhas de referência do MT + comparativos gerados (`NossoLado_*`).
- Handoff anterior: `Mercado Turbo/HANDOFF_FINANCEIRO_ML_2026-05-30.md`.

### OAuth / billing (lembretes)
- Ativar permissão funcional **"Faturamento"** no DevCenter **e re-autorizar** (token novo pega o escopo `urn:ml:mktp:invoices`).
- `refresh_token` é rotativo (uso único). BR permite 1 app por holder.

---

## 13. Princípios de operação (para não repetir erros)

- **Deploy** é pela `main` → Railway auto-build. Toda ida pra prod exige **OK explícito** do dono.
- **Mudar config de prod** (variáveis Railway, ligar/desligar robô) exige **OK explícito** — não é coberto por uma autorização genérica.
- **Local nunca reproduz o 429.** Verde local = sem bug bobo; a verdade do bloqueio só aparece em prod.
- **Nunca martelar o ML em rajada.** O freio é inegociável: 429 → parar, não insistir.
- O 429 é **CloudFront por rajada** — não é IP, não é token, não é cota por Client-ID.

---

## 14. TUDO que foi estudado do Mercado Livre

### 14.1 Documentação oficial destilada — `Mercado Turbo/ML_DOC_OFICIAL/`
Notas em palavras próprias (não cópia) da doc em `developers.mercadolivre.com.br/pt_br/`, lidas pelo navegador logado (o portal bloqueia WebFetch).

| Arquivo | Conteúdo |
|---|---|
| `00-INDICE.md` | Índice + achados que mudaram o diagnóstico. |
| `01-criar-aplicacao.md` | DevCenter: criar/configurar aplicação. |
| `02-permissoes-funcionais.md` | Escopos/permissões funcionais do app. |
| `03-autenticacao-autorizacao.md` | OAuth. **Achado: 403 = IP/scope; 429 = rate.** |
| `04-gerenciar-ips.md` | Lista branca de IPs (opt-in, só parceiro). |
| `05-consideracoes-design.md` | Boas práticas de integração. |
| `06-rate-limit-429-faq.md` | Rate limit / FAQ do 429. |
| `07-notificacoes-webhook.md` | Webhooks (spec completa — relevante só pra SaaS/multi-loja). |
| `08-developer-partner-program.md` | DPP (exige GMV altíssimo — fora de alcance). |
| `09-frete-e-faturamento.md` | **Frete do vendedor**: `GET /shipments/{id}/costs` → `senders[].cost` (oficial). Faturamento em lote. |
| `10-relatorios-faturamento.md` | **Relatórios de faturamento (billing) por período** — testado ao vivo. |

### 14.2 Outros documentos de estudo do ML no repo (`Mercado Turbo/`)
- `ML_API_NOTAS.md` — notas de API (origem do "~300/min", que NÃO está na doc — é suposição).
- `INCIDENTE_PRODUCAO_2026-05-27.md` — o incidente original do 429.
- `ESTUDO_RESUMO_FINANCEIRO.md` — estudo do cálculo de margem.
- `SPEC_FINANCEIRO_ML_V2_2026-05-28.md` — spec da v2.
- `HANDOFF_FINANCEIRO_ML_2026-05-28.md` e `..._2026-05-30.md` — handoffs anteriores.

### 14.3 Conhecimento de API consolidado (endpoints e o que cada um dá)
- **`GET /orders/search`** — busca por `seller` + `order.date_created.from/to`, paginado (offset/limit 50). Filtro honrado é **`order.date_last_updated.from`** (`order.last_updated.from` é IGNORADO). Há `search_type=scan` + `scroll_id` (sem teto de offset >1000) — não misturar com offset.
- **`GET /orders/{id}`** — traz `order_items[].sale_fee` (tarifa), `unit_price`, `quantity`, `seller_sku`; `payments[].shipping_cost` (frete comprador); `total_amount`, `paid_amount`; `status`; `shipping.id`.
- **`GET /shipments/{id}`** — `shipping_option.cost` (comprador) e `list_cost` → **frete vendedor = max(0, list_cost − cost)**.
- **`GET /shipments/{id}/costs`** — `senders[].cost` (o que o vendedor pagou, fonte oficial pra conciliação), `receiver.cost`, descontos loyal/ratio (subsídio Flex).
- **`GET /orders/{id}/discounts`** — cupons (type=coupon → reduz líquido do seller). Sem desconto = 404.
- **`GET /billing/integration/monthly/periods`** — lista os ~12 períodos (cada um com `key`, ex `2026-05-01`).
- **`GET /billing/integration/periods/key/{KEY}/group/ML/details?document_type=BILL`** — **linhas por pedido** (charge + order_id + shipping). Paginação capada ~10k.
- **`GET /billing/integration/periods/key/{KEY}/documents?group=ML&document_type=BILL`** — documentos/faturas do período, com `count_details` e **`files[]`** (download nos fechados).
- **`POST /oauth/token`** — refresh (rotativo, uso único).
- **Escopos:** `orders-shipments`, `comunication`, `publish-sync`, `ads`, `metrics`, `offers`, **`invoices`** (= permissão "Faturamento", necessária pro billing).

### 14.4 Regras/limites de rate aprendidos
- **API ML:** limite **por Client-ID + por endpoint** (a doc não dá o número; `client.py` assume ~300/min). 403 = IP/scope; 429 = rate.
- **Billing:** **5 requisições/minuto** (documentado e medido — bate "Rate limit exceeded: 5 requests per minute").
- **CloudFront (borda):** corta **rajada** independente da cota da API (ver §3). É o que derruba o robô.
- **OAuth:** escopo **congela no grant** — ativar permissão exige **re-autorizar** (token novo). BR = 1 app por titular. `refresh_token` rotativo.
- **Deprecando:** campo `save` (subsídio) sendo descontinuado; pedidos novos podem vir sem `shipping` no JSON (header `x-format-new`).

### 14.5 Comportamentos descobertos AO VIVO (testes reais nesta sessão)
- 429 = **CloudFront** (headers `server: CloudFront`, `x-cache: Error from cloudfront`, corpo vazio); chamada isolada = 200 (`Miss from cloudfront`).
- Billing **details**: estrutura por pedido confirmada; frete = ao-vivo (3/3 exato).
- Billing **paginação capada ~10k** (offset 422 acima; cursor `last_id` satura). Período de mês ~66k linhas.
- Billing **documentos**: período FECHADO = `BILLED` + `files[{file_id}]`; período ABERTO = `files: []`.
- **Download do arquivo = 403** (endpoint/permissão a confirmar — fio solto).
- **Lag** venda→cobrança no extrato: mediana 1d, p90 4d.
- Em prod, o CloudFront tripou a rajada com **~35 chamadas** (IP de datacenter).

---

## 15. ONDE está todo o programa (mapa de arquivos)

### 15.1 Repositório
- **Máquina do Julio (dir principal de trabalho):** `/Users/julio/Documents/Antigra/warehouse-picker v2`
- **Git remoto:** `github.com:julioc0701/nvs-wms-v2.git` — branch de deploy: **`main`**.
- **Mapa geral do código (ler primeiro):** `CODEBASE.md` (na raiz) — rotas, modelos, arquivos.
- **Produção:** Railway projeto `virtuous-unity` → serviço **`nvs-wms-v2`** → URL `nvs-wms-v2-production.up.railway.app` (auto-build da `main`).

### 15.2 Backend — `backend/`
- `main.py` — app FastAPI; monta os routers (financeiro_ml em `/api/financeiro-ml`); liga o runtime do robô se `ENABLE_FINANCEIRO_ML_ROBOT=true`.
- `database.py` — banco PRINCIPAL (operação geral).
- `financeiro_ml/` — **o robô e o módulo financeiro** (detalhe em 15.3).
- `routers/` — demais endpoints (ex.: `tiny.py` = integração Tiny ERP, muito tagarela nos logs).
- `services/` — serviços (`marker_sync.py`, `sync_engine.py`, etc.).
- `mas_core/`, `parsers/` — núcleo/parsers do WMS.
- `static/` — estáticos servidos.
- `tests/` — testes do backend (fora do financeiro_ml).
- `logs/`, `scratch/` — runtime/rascunho.

### 15.3 O robô financeiro — `backend/financeiro_ml/`
| Arquivo | Papel |
|---|---|
| `router.py` | Endpoints `/api/financeiro-ml/*` (resumo, export, backfill, `_debug/*`). |
| `client.py` | Cliente ML async: OAuth/refresh, throttle global, backoff 429, `_diag_429`. |
| `worker.py` | **Worker único (escritor).** Processa dias: search + enrich (shipment) + upsert. **A rajada e o freio estão aqui.** |
| `poller.py` | Enfileira a janela fresca a cada ~6h. |
| `freshness.py` | `FRESH_WINDOW_DAYS` (janela, agora 7) + decide o que re-sincronizar. |
| `calc.py` | `build_order_row` — cálculo puro de um pedido. |
| `aggregator.py` | Agrega pro painel + **rateio de frete por carrinho/pack** (`:124`). |
| `sync.py` | Sync v1 (local) — mesma lógica de rajada. |
| `backfill.py` | Jobs de backfill (histórico sob demanda). |
| `repo.py` | `upsert_order_row`, `set_day_status`. |
| `lock.py` | Lock durável por seller (evita 2 escritores). |
| `db.py` | Sessão do banco do financeiro (`FinSessionLocal`). |
| `models.py` / `models_v2.py` | Modelos **v1** (antigo) e **v2** (atual — o robô usa v2). |
| `migrate_v1_to_v2.py` | Migração v1→v2 no boot (só roda com robô ligado). |
| `sku_service.py` | Cadastro de custo por SKU (cuidado: split-brain v1/v2, ver memória war room). |
| `throttle.py` | Throttle por seller (dead code candidato). |
| `tests/` | Suíte do módulo (`test_worker.py`, `test_poller.py`, `test_freshness.py`, ... — 98 testes). |

### 15.4 Frontend — `frontend/src`
- React + Vite. O painel financeiro consome `/api/financeiro-ml/resumo` (lê cache).

### 15.5 Documentação e dados — `Mercado Turbo/`
- `ML_DOC_OFICIAL/` — doc oficial do ML destilada (§14.1).
- `referencia/` — planilha de referência do MT (`MercadoTurbo_Financeiro_*.xlsx`) + comparativos gerados (`NossoLado_*.xlsx`).
- `HANDOFF_FINANCEIRO_ML_2026-06-01.md` — **este documento (a bíblia).**
- `HANDOFF_*_2026-05-28/30.md`, `SPEC_*`, `INCIDENTE_*`, `ML_API_NOTAS.md`, `ESTUDO_RESUMO_FINANCEIRO.md`, `AGENTS.md`, `README.md`.

### 15.6 Memória do agente (contexto acumulado entre sessões)
- `/Users/julio/.claude/projects/-Users-julio-Documents-Antigra-warehouse-picker-v2/memory/`
  - `project_war_room_429.md` — histórico completo do diagnóstico do 429 (com o veredito final no topo).
  - `MEMORY.md` (índice), `project_stack.md`, `deploy_rules.md`, `tiny_erp_rules.md`, etc.
