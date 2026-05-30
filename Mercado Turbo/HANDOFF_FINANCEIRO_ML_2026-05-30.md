# HANDOFF — Financeiro ML / Mercado Turbo v2

**Data:** 2026-05-30 · **Para:** equipe que vai assumir o projeto · **Substitui/atualiza:** `HANDOFF_FINANCEIRO_ML_2026-05-28.md`

> Documento de transferência. Lê na ordem. Ao final, tu sabe o que é o projeto, o que foi estudado, o que foi desenhado, o que foi construído, o que está em produção, o que está quebrado, por quê, e o que fazer a seguir. **Honestidade total, inclusive dos erros cometidos** — pra equipe nova não repetir.

---

## 0. Resumo executivo (3 minutos)

**O produto:** painel financeiro das vendas do Mercado Livre (clone do concorrente "Mercado Turbo"). Mostra, por período, faturamento / custo / imposto / tarifa / frete / margem de contribuição. Multi-conta (multi-seller) no desenho.

**O problema histórico (incidente 27/05/2026):** o painel antigo buscava os dados no ML **no clique do usuário** → o ML bloqueava com **erro 429 (rate limit)** → painel travava, cards zerados. Inutilizável.

**A solução desenhada (greenfield v2):** arquitetura **CQRS pobre** — um **robô no fundo** busca os dados e guarda já calculados; o **painel só lê** o que está guardado (aparece na hora, nunca trava). É exatamente o que o concorrente faz (confirmado por inspeção de rede).

**Estado em 2026-05-30:**
- ✅ Painel novo **em produção**, lê o cache, mostra histórico correto, **não trava**.
- ✅ Migração dos dados v1→v2 feita (7.446 pedidos), **sem re-buscar no ML**.
- ✅ Token OAuth (estava morto) **recuperado**; robô autentica.
- ⚠️ **O 429 ainda aparece** quando o robô puxa dados — o IP de produção está com **penalidade acumulada** (de testes excessivos) e/ou o **limite do app é baixo**. Robô puxa alguns pedidos e toma 429.
- 🔧 Conserto de **backoff+jitter no 429** já deployado (robô não desiste mais), mas o 429 persiste com poucas chamadas → sinal de que falta **aumento de cota (parceria)** ou **webhook**.

**Decisão estratégica em aberto (levantada pelo dono):** o caminho atual é "1 loja com polling". Pra **SaaS** (várias lojas), o certo é **botão Conectar conta (OAuth produtizado) + webhooks (ML empurra) + programa de parceiros**. O dono já criou a solução **NVS TECH** no programa de parceiros do ML (partners.mercadolivre.com.br).

---

## 1. Documentos-fonte (ler junto com este)

Todos em `Mercado Turbo/`:
- `INCIDENTE_PRODUCAO_2026-05-27.md` — o incidente original, diagnóstico de 429 passo a passo. **Fonte primária do problema.**
- `ESTUDO_RESUMO_FINANCEIRO.md` — estudo do cálculo financeiro (margem, frete, tarifa, imposto).
- `ML_API_NOTAS.md` — **notas destiladas da doc oficial do ML** (auth, rate limit, scan, webhooks, shipments). Portal bloqueia WebFetch → **não re-buscar a doc, ler aqui.**
- `SPEC_FINANCEIRO_ML_V2_2026-05-28.md` — **o desenho da mesa de especialistas** (arquitetura, schema, robô, riscos).
- `HANDOFF_FINANCEIRO_ML_2026-05-28.md` — handoff anterior.
- Plano de execução: `docs/superpowers/plans/2026-05-28-financeiro-ml-v2.md` (31 tasks TDD).

---

## 2. Linha do tempo

1. **27/05/2026 — Incidente.** 1º deploy do módulo em produção. Ao clicar "Buscar", **todos os 8 dias falharam** (429 em cascata + 401 por refresh de token paralelo). Cards zerados. Documentado em `INCIDENTE_PRODUCAO_2026-05-27.md`.
2. **28/05 — Estudo.** Mesa de especialistas (Arquiteto + Backend + ML-API) estudou:
   - A **doc oficial do ML** (lida via Chrome MCP, conta logada) → destilada em `ML_API_NOTAS.md`.
   - O **concorrente Mercado Turbo** (inspeção F12/Network) → confirmou que o painel deles **não chama o ML no clique** (zero request a api.mercadolibre.com); crawl é background.
   - O **cálculo financeiro** existente → `ESTUDO_RESUMO_FINANCEIRO.md`.
   - Resultado: **SPEC** (`SPEC_FINANCEIRO_ML_V2_2026-05-28.md`).
3. **28/05 — Plano.** SPEC virou plano de 31 tasks TDD (`docs/superpowers/plans/`).
4. **28–30/05 — Execução** (sessão deste handoff). Tasks 1–29 implementadas; migração de produção; recuperação do token; deploy; conserto de 429. **Tasks 30/31 (validação e corte) executadas parcialmente em produção.**

---

## 3. Estudo da API do ML (o que a equipe PRECISA saber) — de `ML_API_NOTAS.md`

### 3.1 Autenticação (OAuth) — **só existe um jeito**
- Fluxo: `authorization_code` (troca **code → token**) → depois `refresh_token`.
- `access_token` dura **6h** (`expires_in: 21600`). `refresh_token` renova.
- **CRÍTICO — refresh_token é uso único e rotativo:** *"só pode ser usado UMA VEZ, e só pelo client_id associado; depois de usado, vira inválido"*. Cada refresh devolve **novo access + novo refresh** — tem que persistir o novo.
- **Cross-invalidation (causa do 401 do incidente):** o mesmo refresh_token em 2 lugares (ex: local e prod, ou 2 processos) → o primeiro que renovar **mata a cópia do outro** → cascata `invalid_grant`. Mitigação: **app/client_id separado por ambiente** + 1 processo de refresh por seller.
- `redirect_uri` tem que bater **EXATO** com o registrado no app. Auth BR: `auth.mercadolivre.com.br/authorization`.
- **Bling/Olist/Mercado Turbo usam exatamente esse OAuth** — a diferença é que eles embrulham num botão "Conectar conta". Não existe método secreto diferente.

### 3.2 Rate limit / 429 — **a dor central**
- Doc oficial é **vaga** (sem RPM concreto). Empírico/comunidade: **~1.500 req/min por seller** + um teto **por aplicação por hora** (`max_requests_per_hour`, configurável, não exposto na UI).
- Escopo: *"controle por Client ID e por endpoint"* — mas empírico mostra componente **por seller** também. Tratar **seller** como dimensão de throttle/lock.
- **Receita oficial pro 429:** **backoff exponencial + jitter + reduzir concorrência + distribuir** (não martelar). Sem header `Retry-After`.
- **Penalidade acumulada:** IP que toma muitos 429 fica **penalizado** e toma 429 com pouquíssimas chamadas; reseta com o tempo (~horas/24h). **IP de datacenter (Railway) é tratado com mão mais pesada que IP residencial** — por isso "funciona local, falha em prod".
- **Aumento de cota:** canal oficial = contatar integrações comerciais / **programa de parceiros** com evidência de uso legítimo.

### 3.3 Paginação — scan vs offset
- `offset/limit`: simples, mas **teto ~1000**. Dia cheio (1.100+ pedidos) **perde pedido em silêncio**.
- `search_type=scan` + `scroll_id` (TTL ~5min, não misturar com offset, serial): **obrigatório** pra qualquer janela com potencial >1000 (backfill, dia cheio).

### 3.4 Cursor delta (anti-perda, economiza chamada)
- Filtro honrado: **`order.date_last_updated.from`** (`order.last_updated.from` é **IGNORADO** — validado live).
- `cursor = max(date_last_updated visto) − 1h`. Mudança de status (cancel/refund) **bumpa** `date_last_updated` → reentra no delta. Por isso janela fresca de 14 dias.

### 3.5 Webhooks / Notifications
- Tópico **`orders_v2`**: notifica **criação E mudança** de vendas. Payload `{resource:"/orders/{id}", topic, attempts}` → fazer GET no resource.
- Callback público no app deve responder **200**; retry 8x em 1h; perdidas recuperáveis via `GET /missed_feeds`.
- **Decisão da mesa (pra 1 loja):** webhook é **complemento opcional**, não substitui o poll (não dá histórico; exige endpoint público + dedup). **Mas pra SaaS multi-loja, webhook vira essencial** (polling N lojas não escala).

### 3.6 Shipments / frete (cálculo)
- `GET /shipments/{id}` → `shipping_option{cost,list_cost}`, `logistic_type`, `mode`.
- `GET /shipments/{id}/costs` → `receiver{save,cost}`, `senders[]{cost,save}` (subsídio Flex/Pontos).
- Regra: `frete_vendedor = max(0, list_cost − cost)`; loyal → `fc = receiver.save`; ratio (Flex) → `fc = sender.save`.

---

## 4. O que a mesa de especialistas DESENHOU (SPEC §3–§6)

**Arquitetura CQRS pobre** num único processo uvicorn:
- **API de leitura** (`/resumo`, `/export`, `/backfill/{id}`) — **nunca** chama o ML; só lê o banco isolado.
- **Robô** = `asyncio.Task` no lifespan: **scheduler (poller)** + **1 worker único de escrita** + **fila** (`asyncio.Queue`).
- **Princípio:** produtores (poller + backfill) só **enfileiram**; o worker é o **único escritor** → mata "database is locked" e bursts paralelos.

**Banco isolado** `financeiro_ml.db` (engine própria, WAL, `busy_timeout`), `seller_id` em toda tabela. No Railway: `sqlite:////data/financeiro_ml.db` (volume persistente).

**Defesas contra 429 (SPEC §6) — IMPORTANTE, ver §7 deste handoff:**
1. **Throttle por seller** (token-bucket ~3 req/s), substituindo o global.
2. **Backoff exponencial + jitter no 429** (base 2s, cap 60s, máx 5, full jitter) — *"a doc pede; hoje é fail-fast puro"*.
3. **Circuit-breaker por seller** (closed→open→half-open, cooldown 300s, religa sozinho).
4. **scan** pra backfill/dia cheio.
5. **Lock durável por seller** (CAS + lease em tabela) — cobre as 2 réplicas do rolling deploy do Railway.

**Transição:** construir ao lado → migrar dados (sem re-buscar) → validar new-vs-old → cortar (painel aponta pro novo, velho congelado, depois remove).

---

## 5. O plano (31 tasks TDD)

`docs/superpowers/plans/2026-05-28-financeiro-ml-v2.md`. Resumo das fases:
- **Tasks 1–7:** banco isolado, schema multi-seller, migração v1→v2.
- **Tasks 8–11:** portar cálculo (`build_order_row` puro + `aggregate`).
- **Tasks 12–23:** motor — lock durável, worker único, fila, throttle por seller, circuit-breaker, freshness 14d, poller 6h, OAuth por seller, recover de órfãos, wire-up no lifespan.
- **Tasks 24–27:** scan, backfill jobs, endpoints REST, worker marca done/failed.
- **Task 28:** `/resumo` read-only por seller.
- **Task 29:** front envia seller_id + tela de backfill.
- **Task 30:** validação new-vs-old. **Task 31:** corte + deploy.

---

## 6. O que foi REALMENTE construído e deployado (commits)

Tudo em `backend/financeiro_ml/` + `frontend/src/financeiro-ml-v2/`. Deploy = branch **`main`** (push → Railway builda. **NÃO** é `nvs-production`). Projeto Railway: `virtuous-unity`. Repo: `github.com/julioc0701/nvs-wms-v2`.

Commits desta sessão (cronológico):
- `dce1ff9` scan_orders (scroll_id)
- `21691aa`/`260ba4a`/`fd27cdb` backfill jobs + endpoints + worker done/failed
- `98cf7d1` `/resumo` read-only do banco isolado por seller (cortou sync inline)
- `2c5520a` front envia seller_id + tela de backfill com polling
- `b118590` migração v1→v2 **também copia sku_financeiro** (custo/imposto — tinha ficado de fora → margem zerava)
- `c9e7827` **beta virou painel oficial, painel v1 removido** (rota `/financeiro-ml/resumo` aponta pro componente novo; `resumo-v2` redireciona; menu "Análise Financeira" único; "Cadastro Custo SKU" mantido)
- `70a6dac` **migração v1→v2 automática no boot** (one-shot, guard idempotente, lê do banco principal `DATABASE_URL`, nunca re-busca no ML)
- `c23ef08` deploy
- `0f1950b` **endpoint `/_debug/ml-oauth-exchange`** (troca code→token e grava no **banco isolado**; conserta o `reset-tokens` antigo que gravava no banco errado)
- `8293cba` **429 com backoff exponencial + jitter** (SPEC §6; robô não desiste no 1º 429)

**Estado dos testes:** 94 passando (`cd backend && python -m pytest financeiro_ml/tests/ -q`).

---

## 7. ⚠️ LACUNAS entre o plano e o build (LER COM ATENÇÃO)

A mesa desenhou as defesas de 429, mas **parte foi escrita e NÃO ligada**:

| Defesa SPEC §6 | Status real no código | Impacto |
|---|---|---|
| Throttle **por seller** (token-bucket) | `throttle.py` (`SellerThrottle`) **existe mas NÃO é importado fora dos testes**. O worker usa o **throttle global antigo (0.25s)** via `client._get`. | Pra 1 seller funciona; pra multi-seller é incorreto (não isola). |
| **Backoff+jitter no 429** | Era **fail-fast** (desistia no 1º 429). **CORRIGIDO nesta sessão** (`8293cba`) dentro de `client._get`. | Agora absorve 429 transitório. |
| **Circuit-breaker por seller** | `throttle.py` (`SellerCircuitBreaker`) **existe mas NÃO é ligado** no worker. O worker só marca o dia `rate_limited` + `next_retry_at` e segue. | Funciona via `next_retry_at` (heal a cada 6h), mas sem o breaker self-healing rápido desenhado. |
| **scan no backfill** | `scan_orders` existe (`client.py`), mas o worker `_sync_day` usa **offset** (offset+=50). | Dia >1000 pedidos perde dado em silêncio no backfill. Pro delta diário (poucos pedidos) é ok. |

**Tasks 17/18 estão marcadas "completas" no plano, mas a fiação ficou pendente.** A equipe nova deve: ligar `SellerThrottle`+`SellerCircuitBreaker` no worker, e trocar offset→scan no `_sync_day` do backfill.

---

## 8. A saga do token OAuth (o que travou o robô em prod)

1. O robô lê tokens do **banco isolado** (`FinSessionLocal` + `models_v2.MLTokens`, por `seller_id`).
2. A migração copia `ml_tokens` do banco principal (que o v1 mantinha). **Mas o token de produção estava MORTO** (`invalid_grant`) — provavelmente por cross-invalidation (mesmo refresh_token usado em mais de um lugar; ver §3.1). O painel de prod **nunca funcionou** desde 27/05 por causa disso.
3. **Recuperação (feita nesta sessão):**
   - Descoberto que o `/_debug/reset-tokens` antigo gravava no **banco PRINCIPAL** (v1), não no isolado → inútil pro robô novo. Por isso foi criado **`/_debug/ml-oauth-exchange`** (`0f1950b`).
   - Fluxo OAuth manual: montou-se a URL de autorização (`client_id=5638937489789159`, `redirect_uri=https://www.youtube.com`), o dono autorizou logado na loja, copiou o `code`, e o endpoint trocou por token novo gravando no banco isolado. **Funcionou** (`ok:true`, seller 221832146).
4. **Pré-requisito que estava faltando:** `ML_REDIRECT_URI` no Railway estava **em branco** → preenchido com `https://www.youtube.com` (tem que bater com o registrado no app).

**Pendência:** o `reset-tokens` antigo (banco errado) ainda existe em `router.py:430` — confunde. Remover ou apontar pro banco isolado.

---

## 9. O problema do 429 — análise honesta e status atual

**Fato medido (30/05):** com o token novo + backoff, o robô **puxou dados reais** (dia 30 = 29 vendas, R$1.836) mas **tomou 429 de novo após ~60 chamadas** e o job marcou `failed`. 60 chamadas é **muito pouco** (limite normal ~1500/min) → indica:
- **(a)** IP de produção ainda **penalizado** (de testes excessivos — ver §10), e/ou
- **(b)** `max_requests_per_hour` do app **baixo** (não visível na UI).

**O que JÁ está certo:** painel read-only (não chama ML no clique); cálculo portado; cache migrado (sem cold-start dos 284k históricos); backoff no 429; token funcionando.

**O que falta pra matar o 429 de vez:**
1. **Parar de cutucar** e deixar a penalidade do IP resetar (horas).
2. Se o robô **leve** (delta automático 6h) continuar tomando 429 → o limite do app é genuinamente baixo → **aumento de cota via parceria** (NVS TECH) **ou webhook**.
3. Ligar throttle/breaker por seller (§7) e scan no backfill.

**Importante:** 429 **não dá pra eliminar 100%** (é limite externo do ML). O objetivo é torná-lo **inofensivo**: robô raramente provoca (delta leve), e quando provoca, absorve no fundo (backoff/breaker) sem o usuário ver. O painel lê o cache e **nunca trava** — isso já está garantido.

---

## 10. Erros cometidos NESTA sessão (pra equipe nova não repetir)

1. **Testes de backfill em excesso em produção** → cada 429 reinicia a penalidade do IP. Eu (assistente) fui a principal fonte de manter o ML irritado. **Regra: NÃO disparar backfill repetido em prod; usar o delta leve e medir.**
2. **Tasks 17/18 marcadas completas sem a fiação** (throttle/breaker existem mas desconectados). **Sempre validar build-vs-spec, não só "task feita".**
3. Sugestão precipitada de **webhook como "solução"** contrariando a SPEC (§1 não-objetivo pra 1 loja) — webhook é certo pra **SaaS**, não pra "consertar 1 loja agora". Não confundir os dois contextos.
4. `reset-tokens` antigo gravava no banco errado (não percebido até debugar). **Validar que cada endpoint usa `FinSessionLocal`, não `database.SessionLocal`.**

---

## 11. A questão estratégica: SaaS (levantada pelo dono)

O dono observou: Bling/Olist/Mercado Turbo conectam com **1 clique**, sem o usuário gerar token/URL. **Está certo.** Esclarecimentos:

- **Mecanismo de auth é o mesmo OAuth** — eles só **produtizam** num botão "Conectar conta" + callback automático + refresh automático por seller. O que fizemos na mão é a versão crua.
- **Pro SaaS, construir:**
  1. **Botão "Conectar conta ML"** → redirect → callback automático (reusa o `ml-oauth-exchange` já criado, disparado pelo redirect em vez de colar o code).
  2. **Tokens por seller** (schema já suporta) com refresh automático.
  3. **Webhooks `orders_v2`** (ML empurra) — essencial em escala (polling N lojas não escala e multiplica 429).
- **Programa de parceiros (NVS TECH):** já criado em `partners.mercadolivre.com.br`. É **status/credencial** (níveis/medalhas; requisitos: GMV de vendedores, assessment de segurança ≥65%, iniciativas com Integration Expert). **Diferente de webhook** — partner = comercial/limites; webhook = técnico/dados. Os dois juntos formam o SaaS maduro.

---

## 12. Estado atual de produção (snapshot 2026-05-30)

- **Painel:** `https://nvs-wms-v2-production.up.railway.app/financeiro-ml/resumo` — funciona, lê cache, mostra histórico (ex: 20–27/05 = R$423.533 / 7.081 vendas aprovadas).
- **Robô:** ligado (`ENABLE_FINANCEIRO_ML_ROBOT=true`), autentica, puxa — mas tomando 429 (ver §9).
- **Dados no cache:** ~7.446 pedidos (20→28/05 migrados) + dia 30 parcial (29). Dias 28/29 incompletos (vítimas do 429/penalidade).
- **`sku_financeiro` em prod = 0** (a migração copia do banco principal, que **não tinha** os 215 SKUs que existiam no `.db` local de dev). **Consequência: margem de contribuição em prod está inflada** (sem custo subtraído). Pendência: cadastrar/importar os custos de SKU em prod (tela "Cadastro Custo SKU" tem import Excel).

---

## 13. Recomendações priorizadas pro próximo time

**P0 — deixar a loja do dono estável (curto prazo):**
1. **Parar de disparar backfill** em prod. Deixar a penalidade do IP resetar (horas/1 dia).
2. Monitorar (read-only) se o **delta automático (6h)** mantém os dias frescos sem 429. Medir nº de chamadas/ciclo.
3. **Ligar `SellerThrottle` + `SellerCircuitBreaker`** no worker (§7). Trocar offset→**scan** no `_sync_day`.
4. Resolver `sku_financeiro=0` em prod (importar custos) → margem correta.

**P1 — se o 429 persistir mesmo no delta leve:**
5. **Aumento de cota** via parceria NVS TECH (canal oficial) **e/ou** subir `ML_THROTTLE_INTERVAL_SEC`.

**P2 — caminho SaaS (médio prazo):**
6. **Webhook `orders_v2`** (endpoint público + dedup + `missed_feeds`) — corta chamadas, near-real-time, escala multi-loja.
7. **Botão "Conectar conta ML"** (OAuth produtizado, reusa `ml-oauth-exchange`).
8. **Postgres** (sair do SQLite quando entrar a 2ª loja / 2ª réplica).

**Higiene técnica:**
9. Remover `/_debug/reset-tokens` antigo (banco errado) ou apontar pro isolado.
10. Remover encanamento v1 morto (`sync.py:ensure_period_synced`, `models.py` v1) — Task 31 Step 3, só após fallback estável.

---

## 14. Referência técnica

**Arquivos `backend/financeiro_ml/`:** `db.py` (engine isolada), `models_v2.py` (schema v2), `migrate_v1_to_v2.py` (migração + `maybe_migrate_on_boot`), `calc.py`+`aggregator.py` (cálculo portado), `client.py` (ML async + OAuth + **backoff 429**), `worker.py` (worker único + `_sync_day`), `poller.py` (loop 6h/14d), `lock.py` (lock durável), `throttle.py` (**SellerThrottle/CircuitBreaker — DESCONECTADOS**), `backfill.py` (jobs), `freshness.py`, `repo.py` (upsert), `router.py` (endpoints), `sync.py`+`models.py` (**v1 morto, ainda presente**).

**Endpoints REST** (`/api/financeiro-ml/`, todos exigem header `X-Operator-Id` de operador Master): `POST /resumo`, `POST /export`, `GET/PUT/DELETE /skus`, `POST /skus/import-excel`, `POST /backfill`, `GET /backfill/{id}`, `GET /health`, `POST /_debug/ml-oauth-exchange`, `GET /_debug/test-token`, `GET /_debug/sync-status` (lê banco v1 — desatualizado), `POST /_debug/reset-tokens` (banco v1 — não usar), `POST /_debug/import-cache`.

**Env vars no Railway (app `nvs-wms-v2`):**
- Novas v2: `FINANCEIRO_ML_DATABASE_URL=sqlite:////data/financeiro_ml.db`, `ENABLE_FINANCEIRO_ML_ROBOT=true`.
- ML (já existiam): `ML_CLIENT_ID`, `ML_CLIENT_SECRET`, `ML_USER_ID=221832146`, `ML_ACCESS_TOKEN`, `ML_REFRESH_TOKEN`, `ML_REDIRECT_URI=https://www.youtube.com`, `ML_SYNC_*`, `ML_THROTTLE_INTERVAL_SEC`.
- Tuning 429 (novas, opcionais): `ML_429_BACKOFF_BASE_SEC` (2), `ML_429_BACKOFF_CAP_SEC` (60), `ML_429_MAX_ATTEMPTS` (5).
- Banco principal: `DATABASE_URL=sqlite:////data/warehouse_v3_local.db` (volume `/data`).

**Credenciais ML:** `seller_id` = `ML_USER_ID` = **221832146** (a loja — mesmo em local e prod). `ML_CLIENT_ID` = `5638937489789159`. Refresh token é **uso único** — não compartilhar entre ambientes (cross-invalidation).

**Deploy:** `publicar_producao.command`/`.bat` → push na `main` → Railway builda. Esperar **"Active"** no dashboard antes de validar (senão atende código velho).

**Migração de produção:** roda **automática no boot** (`maybe_migrate_on_boot`, em `start_financeiro_ml_runtime`) — copia do banco principal pro isolado, uma vez só, se o isolado estiver vazio. Nunca re-busca no ML.

---

## 15. Decisões/riscos em aberto

1. **429 em prod:** castigo residual de IP vs limite baixo do app — resolver por **descanso + cota de parceiro + webhook**. (P0/P1)
2. **throttle/breaker por seller desconectados** (§7). (P0)
3. **scan vs offset no backfill** — risco de perder pedido em dia >1000. (P0)
4. **`sku_financeiro=0` em prod** → margem inflada. (P0)
5. **Webhook + connect-button** pro SaaS. (P2)
6. **Postgres** quando entrar 2ª loja/réplica (WAL no volume Railway é risco com 2 writers). (P2)
7. **refresh_token uso único** — garantir **um app/client_id por ambiente** e **um processo de refresh por seller**.

---

**Fim do handoff.** Dúvidas: ler `SPEC` (desenho) + `ML_API_NOTAS` (regras do ML) + `INCIDENTE` (o problema). O cálculo financeiro está em `ESTUDO_RESUMO_FINANCEIRO.md`.
