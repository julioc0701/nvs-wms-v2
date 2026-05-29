# SPEC — Financeiro ML / Mercado Turbo v2 (greenfield)

**Data:** 2026-05-28 · **Status:** rascunho p/ aprovação do dono (Julio) · **Autoria:** mesa de especialistas (Arquiteto + Backend + ML-API) coordenada pelo Claude.

> Este é o documento de **design** (o "como vai ser construído"). NÃO é código. O **plano de execução passo-a-passo com testes** é escrito DEPOIS da aprovação desta spec.

---

## 0. Resumo pra quem não é técnico (1 minuto)

Hoje o painel financeiro **trava** porque, quando você clica "Buscar", ele sai correndo atrás dos dados no Mercado Livre na hora — e às vezes o Mercado Livre bloqueia (erro 429).

O novo jeito (o mesmo que o concorrente usa, confirmado por inspeção): um **robô trabalha sozinho no fundo**, busca as vendas e **guarda já calculadas**. O painel só **lê o que está guardado** — aparece na hora, nunca trava. Período grande que ainda não foi buscado: o sistema diz *"buscando, te aviso"*, trabalha no fundo e **avisa quando fica pronto**.

**Custo zero (beta):** continua no banco SQLite, só que feito do jeito certo. Trocar pra um banco mais robusto (Postgres) fica pra quando sair do beta — e será fácil porque o financeiro fica isolado.

**Não joga nada fora à toa:** apaga só o encanamento que trava; **preserva** os dados já guardados, os aprendizados e a inteligência de cálculo já validada. Constrói o novo **ao lado**, valida, e só então desliga o velho.

---

## 1. Objetivo, escopo e não-objetivos

**Objetivo:** painel financeiro ML estável e rápido, que nunca trava nem dispara o crawl do ML no clique do usuário, pronto pra multi-conta (multi-seller).

**Escopo:**
- Separar leitura (painel) de escrita (robô) — CQRS pobre.
- Robô periódico (janela recente sempre fresca) + backfill sob demanda (período grande em background, com aviso quando pronto).
- Escrita serializada (1 worker) + lock durável por seller + banco SQLite isolado e seguro.
- Schema multi-seller desde já.
- Preservar dados existentes + inteligência de cálculo validada.

**Não-objetivos (agora):**
- Postgres (fica pós-beta).
- Webhooks como gatilho (complemento opcional futuro; o poll cobre o caso — ver `ML_API_NOTAS.md` §4).
- Reescrever a lógica de cálculo financeiro (será **migrada**, não recriada).
- Mudar o frontend além de: chamar a nova rota read-only + tela de status do backfill (polling).

---

## 2. Decisões travadas (dono) + ajustes da mesa

| # | Decisão do dono | Ajuste técnico da mesa |
|---|-----------------|------------------------|
| 1 | Banco custo zero (SQLite), beta | SQLite **isolado** (arquivo `.db` próprio + engine própria) + `PRAGMA busy_timeout` + WAL. Postgres pós-beta / no dia da 2ª réplica. |
| 2 | Robô no molde do que já existe | **Copiar o padrão** de `services/sync_engine.py` (loop, recover de órfãos), **NÃO importar** o arquivo (é amarrado ao Tiny). |
| 3 | Janela curta fresca + período grande no fundo c/ aviso | Janela 7-14d a cada ~6h (delta). Backfill = tabela de jobs + **polling REST** (NÃO websocket, NÃO `BackgroundTasks`). |
| — | "Só o robô escreve" | **Insuficiente sozinho:** há 2 produtores (poller + backfill). Solução: **fila de escrita** com **1 worker único** (produtores só enfileiram). |
| — | Cadeado por seller | **Durável em tabela** (CAS + lease/TTL), não `asyncio.Lock` — cobre o caso da **2ª réplica no deploy rolling** do Railway. |
| — | Greenfield "sem lixo" | Apaga encanamento; **preserva** dados + aprendizados + cálculo. Constrói ao lado → valida → corta. |

---

## 3. Arquitetura geral

Tudo roda **no mesmo processo uvicorn** (1 réplica Railway). API de leitura = handlers REST normais. Scheduler e worker = `asyncio.Task` criadas no `lifespan`.

```
                          uvicorn (1 processo, lifespan)
  ┌──────────────────────────────────────────────────────────────────────┐
  │  [API LEITURA]  GET /resumo, /export, /backfill/{id}                   │
  │   (CQRS: NUNCA dispara crawl) ───────── lê ─────────►  ┌─────────────┐ │
  │                                                        │ financeiro_ │ │
  │  [SCHEDULER] asyncio loop (startup)                    │  ml.db      │ │
  │   tick ~10min ──┐                                      │ (isolado,   │ │
  │                 ├─► enfileira Task ──► [asyncio.Queue] │  WAL,       │ │
  │  [API BACKFILL]─┘   POST /backfill          │         │  busy_      │ │
  │                                             ▼         │  timeout)   │ │
  │                                    [WORKER ÚNICO] ──── escreve ──────►│ │
  │                                     1 job/vez:        └─────────────┘ │
  │                                     ├ adquire lock_seller (CAS+lease) │
  │                                     ├ chama ML (throttle+backoff)     │
  │                                     └ grava cache + status job/dia    │
  │  Tabelas de controle no MESMO .db: ml_backfill_jobs, ml_seller_lock  │
  └──────────────────────────────────────────────────────────────────────┘
```

**Princípio:** produtores (scheduler + backfill) **só enfileiram**; o worker é o **único escritor**; a API **só lê**. Isso elimina "database is locked" na raiz (um único escritor de cada vez).

---

## 4. Modelo de dados (schema novo, multi-seller)

DB próprio (`financeiro_ml.db`), engine isolada. `seller_id` em **toda** tabela operacional. Timestamps em **BRT naive** (preservar `_to_brt_naive`).

```sql
-- Tokens OAuth POR SELLER (substitui MLTokens id=1 global)
CREATE TABLE ml_tokens (
  seller_id     INTEGER PRIMARY KEY,        -- = user_id ML
  client_id     TEXT,                        -- app ML (isolar por ambiente/seller)
  access_token  TEXT NOT NULL,
  refresh_token TEXT NOT NULL,
  expires_at    DATETIME NOT NULL,
  refresh_locked_until DATETIME,             -- lease do refresh por seller
  updated_at    DATETIME NOT NULL
);

-- Cache de pedidos (valores JÁ CALCULADOS — não recalcular no read)
CREATE TABLE ml_orders_cache (
  seller_id      INTEGER NOT NULL,
  order_id       INTEGER NOT NULL,
  date_created   DATETIME NOT NULL,
  date_closed    DATETIME,
  date_last_updated DATETIME,                -- cursor delta
  status         VARCHAR(30) NOT NULL,
  status_detail  VARCHAR(100),
  produto_total  NUMERIC(12,2) NOT NULL DEFAULT 0,
  frete_comprador NUMERIC(10,2) NOT NULL DEFAULT 0,
  frete_vendedor  NUMERIC(10,2) NOT NULL DEFAULT 0,
  tarifa_bruta    NUMERIC(10,2) NOT NULL DEFAULT 0,
  tarifa_refund   NUMERIC(10,2) NOT NULL DEFAULT 0,
  refund_amount_partial NUMERIC(10,2) NOT NULL DEFAULT 0,
  cupom_seller    NUMERIC(10,2) NOT NULL DEFAULT 0,
  modalidade_anuncio VARCHAR(30),
  logistic_type   VARCHAR(30),
  shipping_mode   VARCHAR(30),
  shipment_id     INTEGER,
  breakdown_bucket VARCHAR(20),
  raw_json        TEXT NOT NULL,
  synced_at       DATETIME NOT NULL,
  PRIMARY KEY (seller_id, order_id)
);
CREATE INDEX ix_orders_ref  ON ml_orders_cache (seller_id, date_closed, date_created);
CREATE INDEX ix_orders_dlu  ON ml_orders_cache (seller_id, date_last_updated);
CREATE INDEX ix_orders_ship ON ml_orders_cache (seller_id, shipment_id);

CREATE TABLE ml_order_items_cache (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  seller_id   INTEGER NOT NULL,
  order_id    INTEGER NOT NULL,
  item_id     VARCHAR(30) NOT NULL,
  title       VARCHAR(500) NOT NULL,
  seller_sku  VARCHAR(100),
  quantity    INTEGER NOT NULL,
  unit_price  NUMERIC(10,2) NOT NULL,
  category_id VARCHAR(30),
  UNIQUE (seller_id, order_id, item_id)
);
CREATE INDEX ix_items_order ON ml_order_items_cache (seller_id, order_id);

-- Status/cursor de sync por (seller, dia) — corrige o unique global atual
CREATE TABLE ml_day_sync_status (
  seller_id      INTEGER NOT NULL,
  day            DATE NOT NULL,
  last_synced_at DATETIME NOT NULL,
  orders_count   INTEGER NOT NULL DEFAULT 0,
  status         VARCHAR(20) NOT NULL,       -- ok|failed|rate_limited|partial|imported_unverified
  next_retry_at  DATETIME,                   -- backoff: só re-tenta após isso
  error_message  TEXT,
  PRIMARY KEY (seller_id, day)
);

-- Jobs de backfill (o front faz polling REST disto)
CREATE TABLE ml_backfill_jobs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  seller_id   INTEGER NOT NULL,
  day_from    DATE NOT NULL,
  day_to      DATE NOT NULL,
  status      VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending|running|done|failed|cancelled
  progress_done  INTEGER NOT NULL DEFAULT 0,           -- dias concluídos
  progress_total INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  created_at  DATETIME NOT NULL,
  claimed_at  DATETIME,
  finished_at DATETIME
);
CREATE INDEX ix_jobs_status ON ml_backfill_jobs (status, created_at);

-- Lock durável por seller (CAS + lease/TTL) — cobre poller E backfill
CREATE TABLE ml_seller_lock (
  seller_id    INTEGER PRIMARY KEY,
  holder       VARCHAR(60),                  -- ex 'poller' | 'backfill:job=12'
  leased_until DATETIME                      -- TTL absoluto; expirado = livre
);
```

### Camada de banco isolada
Novo `backend/financeiro_ml/db.py` — NÃO importar `database.SessionLocal`. Engine própria apontando p/ `FINANCEIRO_ML_DATABASE_URL` (Railway: `sqlite:////data/financeiro_ml.db`, mesmo volume, arquivo distinto). PRAGMAs via `event.listens_for(engine,"connect")`, aplicados **em cada conexão**: `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000`. Expõe `FinSessionLocal`/`fin_engine`; `MLClient` recebe o factory por injeção (já parametrizável).

---

## 5. Robô + scheduler + worker de escrita

```
lifespan startup:
  recover_orphan_jobs()              # jobs 'running' → 'pending' (copia recover_stale_runs)
  WRITE_QUEUE = asyncio.Queue()
  spawn write_worker(WRITE_QUEUE)
  spawn poller_loop(WRITE_QUEUE)

poller_loop:                         # intervalo ~10min (delta é leve)
  while not STOP:
    for seller in active_sellers:
      enqueue PollTask(seller, dias = hoje .. hoje-N)   # N = janela fresca 7-14d
    sleep(interval)

write_worker:                        # serializa TODA a escrita
  while True:
    task = await queue.get()
    if not acquire_seller_lock(task.seller, ttl=120s): requeue; continue
    if breaker_open(task.seller):    # circuit-breaker por seller
      requeue_later; release; continue
    try:
      for day in task.days:          # SEQUENCIAL (throttle é o gate de req/s)
        cursor = max(date_last_updated visto) - 1h
        page = await client.search_or_scan(seller, day, cursor)
        rows = [build_order_row(o) for o in page]    # cálculo PURO, sem I/O
        upsert(rows); update ml_day_sync_status(seller, day, 'ok')
        if backfill: job.progress_done += 1; renova lease (heartbeat)
    except MLRateLimited:
      backoff+jitter; marca dia rate_limited + next_retry_at; abre breaker; break
    finally:
      release_seller_lock(task.seller)
```

Mata o `asyncio.gather` paralelo com commit-por-pedido (1 commit/dia em batch). Throttle global e refresh-lock continuam como **defesa secundária**; o lock por-seller é o gate primário.

### Lock durável por seller (CAS + lease)
```sql
UPDATE ml_seller_lock
   SET holder=:who, leased_until=:now_plus_ttl
 WHERE seller_id=:sid AND (holder IS NULL OR leased_until < :now);
-- rowcount==1 → adquiriu; ==0 → outro segura (pula/re-enfileira)
```
Renovação (heartbeat) em jobs longos; lease vencida é tomável (cobre crash sem deadlock). **Por que durável:** no deploy rolling do Railway sobem 2 réplicas por segundos → dois pollers do mesmo seller → 429 + corrupção. O lock em tabela atravessa processos.

### Backfill "avisa quando pronto"
- `POST /backfill {seller_id, day_from, day_to}` → cria job `pending`, retorna `{job_id}` na hora, enfileira.
- `GET /backfill/{job_id}` → `{status, progress_done, progress_total, error_message}`. Front faz **polling a cada ~3s**: `pending/running` = barra de progresso; `done` = recarrega `/resumo`; `failed` = mensagem + botão retry.
- Claim atômico via CAS (`UPDATE ... WHERE id=? AND status='pending'`, checa rowcount).
- Recover no startup: jobs `running` órfãos → `pending`.

---

## 6. Regras da API ML (o que o cliente precisa respeitar)

### Paginação: scan vs offset
- **offset/limit:** simples, mas **teto ~1000** — dia cheio (1138 pedidos observados!) **perde pedidos em silêncio**. Usar SÓ quando a janela é comprovadamente <1000 (ex.: delta do ciclo de 6h, que traz dezenas).
- **search_type=scan + scroll_id:** obrigatório p/ qualquer janela com potencial >1000 (backfill, dia cheio). `scroll_id` TTL ~5min, **não misturar com offset**, concorrência = 1 (serial), renovar antes do TTL. Itera até `results` vazio.

### Cursor delta (anti-perda)
- Filtro honrado: **`order.date_last_updated.from`** (`order.last_updated.from` é IGNORADO).
- `cursor = max(date_last_updated VISTO) − 1h`. Nunca `utcnow()` puro (perde mudanças no gap + clock skew).
- Enviar cursor com offset explícito `-03:00`; persistir BRT-naive. Não misturar naive-UTC com filtro -03:00 (cria buraco de 3h).
- Idempotência por `(seller_id, order_id)` (upsert) — reprocessar pela margem é inofensivo.
- Mudança de status (refund/cancel) **bumpa** `date_last_updated` → reentra no delta → upsert reescreve. Por isso janela fresca de 7-14d a cada ~6h.

### Rate limit: throttle + backoff
- **Throttle por seller** (não global): `~3 req/s/seller` (≈180/min, margem). Trocar o throttle module-level atual por token-bucket por `seller_id`.
- **Backoff exponencial + jitter no 429** (a doc pede; hoje é fail-fast puro): `base=2s, cap=60s, max_attempts=5, full jitter`. Sem `Retry-After` no corpo → usar a fórmula.
- **Circuit-breaker por seller** (`closed/open/half-open`): estoura attempts → `open` por `cooldown=300s` → `half-open` (1 req de teste) → sucesso → `closed`. Reabre sozinho (não fica preso até o próximo ciclo).

### OAuth multi-seller
- Tokens **por seller** (acabar com `MLTokens.first()`). Refresh single-use rotativo: persistir novo access+refresh atômico.
- **Lock de refresh por seller** (não global) — `asyncio.Lock` por `seller_id` ou lease em `refresh_locked_until`.
- **Cross-invalidation:** refresh só vale o último, atado ao `client_id`. Dois ambientes/processos com o MESMO par → cascata `invalid_grant`. Mitigar: **app/client_id separado por ambiente** + processo único de refresh por seller.

### Estimativa de carga (1 seller)
- N+1 ≈ **2-4 calls/pedido** (search + shipments + costs condicional + discounts condicional + variation condicional).
- **Ciclo diário (delta 7-14d):** ~dezenas de pedidos → ~160 calls → **~1 min** a 3 req/s. Folgado p/ intervalo de 6h.
- **1º backfill 14d cheio (~16k pedidos):** ~48k calls → **~4,5h** em background (single worker). Cortar N+1 (cache de terminal) baixa o multiplicador em re-syncs.

---

## 7. Inventário — APAGA vs PRESERVA

### APAGA (encanamento que trava/quebra)
- `sync.py:ensure_period_synced` + acoplamento `router.py:127` (sync inline no read).
- `sync.py:_sync_single_day` loop offset + `asyncio.gather` com commit-por-pedido. Reescrever sequencial sob worker único; offset>1000 → scan.
- `sync.py:_days_needing_sync` — manter a **política** (today=5min, recentes=24h, antigos ok=skip), reimplementar por `(seller_id,day)` + `next_retry_at` (backoff, fim do loop quente de 429).
- `models.py` inteiro — recriar com `seller_id` (o `MLDaySyncStatus.day unique` é o bug que quebra multi-seller).
- Throttle global + `_refresh_lock` global do `client.py` — manter como **blindagem secundária**; gate primário vira lock/throttle por seller.

### PRESERVA (inteligência validada — migrar quase intacta)
- `aggregator.py` **inteiro**: `compute_line_mc`, regra ME1/Outros, imposto líquido ponderado por cupom, rateio de pack por shipment, cards/pizza/tabela, `_logistic_bucket`. Só passa `seller_id` no filtro.
- `sync.py:_save_order` (cálculo de frete) → migrar p/ `build_order_row()` puro (sem commit):
  - `frete_vendedor = max(0, list_cost − cost)`.
  - loyal: `cost==0` + `loyal` em `receiver.discounts` + `sender.cost==0` → `fc = receiver.save`.
  - ratio: `ratio` + `sender.cost>0` + `sender.save>0` + `self_service` (Flex) → `fc = sender.save`.
  - cupom_seller: só com tag `order_has_discount`; soma `amounts.seller` de `details[type=coupon]`.
  - refund parcial: soma `transaction_amount_refunded`; zera se `cancelled`.
  - tarifa_bruta = `sale_fee × quantity`.
- `_looks_human_sku` + `_seller_sku_from_item` (heurística SKU humano vs `MLBxxx_yyy`).
- `_to_brt_naive`, regra `coalesce(date_closed, date_created)`.
- `Mercado Turbo/ML_API_NOTAS.md` (fonte única — não re-fetchar doc).
- **Dados em produção:** migrar linhas existentes carimbando `seller_id` do seller default (evita re-buscar → evita 429).

### BUGS a corrigir na migração (não repetir)
1. **Cursor com campo errado:** hoje deriva de `last_synced_at` (relógio nosso) e lê `last_updated or date_last_updated` ambíguo. Corrigir p/ `max(date_last_updated)` do dado.
2. **Refund parcial deixa tarifa cheia** (`tarifa_refund=0` hardcoded + TODO): estornar tarifa proporcional quando disponível.
3. **Frete grátis Full "engolido" → 0:** revisar se 0 é o valor de negócio correto ou subsídio não capturado.
4. **`get_shipment_costs` engole erro → frete 0 silencioso:** logar e marcar incerteza em vez de assumir 0.

---

## 8. Plano de transição (construir ao lado → validar → cortar)

1. **Fase 0 — Ao lado:** novo `financeiro_ml.db` + camada isolada, sem tocar no velho. Velho segue servindo o painel.
2. **Fase 1 — Migrar dados:** copiar `ml_orders_cache`/`items`/`day_sync`/`tokens` do `.db` atual → novo, carimbando `seller_id` do seller default. **Não re-buscar nada** (zero risco de 429). Cursor herdado de `max(date_last_updated)` do próprio cache. Dias sem status conhecido entram como `pending` (reconciliados aos poucos) — **nunca** marcar `ok` sem ter buscado.
3. **Fase 2 — Portar cálculo:** `aggregator.py` + `build_order_row()` sem I/O.
4. **Fase 3 — Motor:** worker único + fila + lock por seller (CAS/lease) + recover no startup.
5. **Fase 4 — Poller:** loop no lifespan (delta por `date_last_updated`, janela 7-14d).
6. **Fase 5 — Backfill:** tabela de jobs + endpoints REST + polling no front.
7. **Fase 6 — Read-only:** router `/resumo` só lê (cortar `ensure_period_synced`).
8. **Fase 7 — Validar:** comparar `/resumo` novo vs velho no mesmo período (cards, tabela, MC%) + os 7 pedidos de referência do handoff. Diferença = bug, corrige antes de cortar.
9. **Fase 8 — Cortar:** front aponta pro novo; velho congelado N dias como fallback; depois remove.

---

## 9. Riscos + mitigação (ranqueados)

1. **2 réplicas no rolling deploy → 429/corrupção** (maior, era invisível). → `ml_seller_lock` durável (CAS+lease).
2. **Dia >1000 quebra offset** (perde pedido em silêncio). → `search_type=scan` obrigatório; nunca misturar com offset.
3. **429 por seller.** → throttle/lock por seller + backoff+jitter + circuit-breaker + baixa concorrência.
4. **import-cache cria cursor falso → buraco permanente.** → import NUNCA grava status `ok`; usa `imported_unverified` (não conta como fresco) + reconcilia `count(orders) == orders_count`.
5. **Cursor perde mudança tardia (>14d).** → backfill agendado de janela maior + re-sync sob demanda.
6. **refresh single-use cross-env.** → tokens isolados por seller/ambiente (apps ML separados).
7. **WAL no volume Railway.** → writer único garante; `wal_autocheckpoint` + monitorar tamanho; Postgres no dia da 2ª réplica.
8. **Migração de dados perde/duplica.** → transação + validar `count` antes/depois + `seller_id` default explícito.

---

## 10. Referências (embasamento da mesa)

- SQLite WAL (readers não bloqueiam writer; 1 writer/vez): sqlite.org/wal.html
- SQLite `busy_timeout` PRAGMA: sqlite.org/pragma.html#pragma_busy_timeout
- Lease/fencing tokens (lock distribuído correto): Kleppmann, "How to do distributed locking"
- Backoff + full jitter: AWS Builders' Library, "Timeouts, retries and backoff with jitter"
- ML Orders/paginação scan+scroll_id, OAuth refresh, rate-limit 429: ver `Mercado Turbo/ML_API_NOTAS.md` (fonte destilada)
- Padrão poller ML multi-conta (token-bucket por seller + worker único): CapyOps/integradores ML
- FastAPI lifespan p/ tasks de background: fastapi.tiangolo.com/advanced/events/

---

## 11. Decisões do dono (TRAVADAS 2026-05-28)

1. **Janela fresca:** **14 dias** (pega quase toda mudança de status).
2. **Intervalo do poller:** **6h** (4x/dia).
3. **Onde mora o novo módulo:** **in-place faseado** dentro do `financeiro_ml/` atual (evita rota duplicada).
4. **Primeiro backfill:** **sob demanda** (usuário pede período grande; sem carga automática no boot).

Próximo passo: **plano de execução passo-a-passo com testes** (TDD), tarefa por tarefa.
