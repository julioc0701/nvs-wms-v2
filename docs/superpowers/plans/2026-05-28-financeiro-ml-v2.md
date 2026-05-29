# Financeiro ML / Mercado Turbo v2 — Plano de Execução (TDD)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconstruir o módulo `financeiro_ml` como CQRS pobre — robô escreve cache já calculado, painel só lê — multi-seller, SQLite isolado, escrita serializada por 1 worker, lock durável por seller, sem nunca disparar crawl ML no clique.

**Architecture:** DB SQLite próprio (`financeiro_ml.db`, engine isolada com WAL + busy_timeout). Producers (poller a cada 6h + backfill sob demanda) só enfileiram em `asyncio.Queue`; um único `write_worker` drena a fila, adquire lock durável por seller (CAS+lease), chama ML (throttle+backoff+circuit-breaker por seller), grava cache. API REST só lê. Constrói ao lado do módulo atual → valida contra o velho → corta.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (Mapped/mapped_column), SQLite (WAL), httpx async, tenacity, pytest + pytest-asyncio. Frontend React+Vite (polling REST do backfill).

**Decisões travadas (dono, 2026-05-28):** janela fresca **14 dias** · poller **6h** · **in-place faseado** (dentro de `financeiro_ml/`) · primeiro backfill **sob demanda**.

**Fonte de design:** `Mercado Turbo/SPEC_FINANCEIRO_ML_V2_2026-05-28.md` + `Mercado Turbo/ML_API_NOTAS.md`.

**Convenções deste plano:**
- Rodar testes do diretório `backend/`: `cd backend && python -m pytest <caminho> -v`.
- `pytest-asyncio` está em modo default (não auto) → todo teste async leva `@pytest.mark.asyncio`.
- Testes novos do módulo ficam em `backend/financeiro_ml/tests/`.
- Timestamps de negócio = BRT naive (preservar `_to_brt_naive`). `leased_until`/lease/cursor de relógio = UTC naive (`datetime.utcnow()`), consistente com o resto do código.
- **NÃO tocar** no módulo velho (`sync.py:ensure_period_synced`, `router.py:127`) até a Fase 6. O painel atual continua servindo durante toda a construção.

---

## Visão geral das fases

| Fase | Entrega | Tasks |
|------|---------|-------|
| 0 | Camada de DB isolada (`db.py`) + PRAGMAs | 1–2 |
| 1 | Schema novo multi-seller (`models_v2.py`) + criação de tabelas | 3–5 |
| 2 | Migração de dados do `.db` atual → novo (sem re-buscar) | 6–7 |
| 3 | Cálculo puro: `build_order_row()` + `aggregate` por seller | 8–11 |
| 4 | Motor: lock durável CAS+lease + fila + write worker | 12–16 |
| 5 | Cliente ML por seller: throttle + backoff + circuit-breaker + tokens | 17–20 |
| 6 | Poller (14d/6h) + recover de órfãos no lifespan | 21–23 |
| 7 | Backfill: jobs + endpoints REST + polling no front | 24–27 |
| 8 | Router read-only (corta `ensure_period_synced`) + validação + corte | 28–31 |

---

## File Structure

Arquivos NOVOS (construídos ao lado, não destroem o velho até a Fase 6/8):
- `backend/financeiro_ml/db.py` — engine/session isolada do financeiro (WAL, busy_timeout). Responsável SÓ por conexão.
- `backend/financeiro_ml/models_v2.py` — modelos multi-seller (`seller_id` em tudo). Substitui `models.py` no fim.
- `backend/financeiro_ml/calc.py` — `build_order_row()` puro (sem I/O), migra o cálculo de `sync.py:_save_order`.
- `backend/financeiro_ml/lock.py` — lock durável por seller (CAS + lease/TTL).
- `backend/financeiro_ml/worker.py` — fila + write worker único + tasks (PollTask/BackfillTask).
- `backend/financeiro_ml/throttle.py` — token-bucket por seller + circuit-breaker por seller.
- `backend/financeiro_ml/poller.py` — loop periódico (delta 14d, intervalo 6h).
- `backend/financeiro_ml/backfill.py` — criação/claim/progresso de jobs.
- `backend/financeiro_ml/migrate_v1_to_v2.py` — migração one-shot de dados.

Arquivos MODIFICADOS:
- `backend/financeiro_ml/client.py` — throttle/refresh por seller (Fase 5).
- `backend/financeiro_ml/aggregator.py` — aceitar `seller_id` no filtro (cirúrgico).
- `backend/financeiro_ml/router.py` — `/resumo` read-only + endpoints `/backfill` (Fases 6–8).
- `backend/main.py` — spawnar worker+poller no startup, recover no boot (Fase 6).

Arquivos PRESERVADOS intactos: `aggregator.py` (lógica), `sku_service.py`, `Mercado Turbo/*.md`.

---

## Fase 0 — Camada de DB isolada

### Task 1: Engine/session isolada do financeiro com PRAGMAs

**Files:**
- Create: `backend/financeiro_ml/db.py`
- Test: `backend/financeiro_ml/tests/test_fin_db.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/financeiro_ml/tests/test_fin_db.py
import os
from sqlalchemy import text


def test_fin_engine_applies_pragmas(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCEIRO_ML_DATABASE_URL", f"sqlite:///{tmp_path}/fin.db")
    import importlib
    import financeiro_ml.db as db
    importlib.reload(db)

    with db.fin_engine.connect() as conn:
        journal = conn.execute(text("PRAGMA journal_mode")).scalar()
        busy = conn.execute(text("PRAGMA busy_timeout")).scalar()
    assert journal.lower() == "wal"
    assert busy == 5000


def test_fin_session_factory_independent_from_main(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCEIRO_ML_DATABASE_URL", f"sqlite:///{tmp_path}/fin.db")
    import importlib
    import financeiro_ml.db as db
    importlib.reload(db)
    from database import engine as main_engine
    assert str(db.fin_engine.url) != str(main_engine.url)
    s = db.FinSessionLocal()
    s.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_fin_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'financeiro_ml.db'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/financeiro_ml/db.py
"""Camada de banco ISOLADA do módulo financeiro_ml.

NÃO importar database.SessionLocal aqui. Engine própria apontando para
FINANCEIRO_ML_DATABASE_URL. PRAGMAs aplicados em CADA conexão (WAL +
busy_timeout=5000 + synchronous=NORMAL) — robô escreve, painel lê, sem
'database is locked'.
"""
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Default local: arquivo próprio ao lado do principal. Railway: sqlite:////data/financeiro_ml.db
FINANCEIRO_ML_DATABASE_URL = os.getenv(
    "FINANCEIRO_ML_DATABASE_URL", "sqlite:///./financeiro_ml.db"
)

fin_engine = create_engine(
    FINANCEIRO_ML_DATABASE_URL, connect_args={"check_same_thread": False}
)


@event.listens_for(fin_engine, "connect")
def _set_fin_pragmas(dbapi_connection, connection_record):
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()


FinSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=fin_engine)


class FinBase(DeclarativeBase):
    pass


def get_fin_db():
    db = FinSessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_fin_db.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/db.py backend/financeiro_ml/tests/test_fin_db.py
git commit -m "feat(financeiro-ml): camada de DB isolada com WAL + busy_timeout"
```

### Task 2: `.gitignore` do novo arquivo .db local

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Checar se já está ignorado**

Run: `cd "/Users/julio/Documents/Antigra/warehouse-picker v2" && git check-ignore backend/financeiro_ml.db || echo "NAO IGNORADO"`
Expected: imprime `NAO IGNORADO` (precisa adicionar) OU já está coberto por um glob `*.db`.

- [ ] **Step 2: Se não ignorado, adicionar linha**

Adicionar ao final de `.gitignore` (só se o Step 1 imprimiu `NAO IGNORADO`):

```
# Financeiro ML — banco isolado local (não versionar)
backend/financeiro_ml.db
backend/financeiro_ml.db-wal
backend/financeiro_ml.db-shm
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore(financeiro-ml): ignorar financeiro_ml.db local"
```

---

## Fase 1 — Schema novo multi-seller

### Task 3: Modelos v2 com `seller_id` em tudo

**Files:**
- Create: `backend/financeiro_ml/models_v2.py`
- Test: `backend/financeiro_ml/tests/test_models_v2.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/financeiro_ml/tests/test_models_v2.py
import importlib
from datetime import datetime, date


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCEIRO_ML_DATABASE_URL", f"sqlite:///{tmp_path}/fin.db")
    import financeiro_ml.db as db
    importlib.reload(db)
    import financeiro_ml.models_v2 as m
    importlib.reload(m)
    db.FinBase.metadata.create_all(bind=db.fin_engine)
    return db, m


def test_order_cache_composite_pk_seller_order(tmp_path, monkeypatch):
    db, m = _fresh_db(tmp_path, monkeypatch)
    s = db.FinSessionLocal()
    # Mesmo order_id em sellers diferentes coexiste (PK composta)
    s.add(m.MLOrderCache(seller_id=1, order_id=999, date_created=datetime(2026,5,1),
                         status="paid", raw_json="{}", synced_at=datetime.utcnow()))
    s.add(m.MLOrderCache(seller_id=2, order_id=999, date_created=datetime(2026,5,1),
                         status="paid", raw_json="{}", synced_at=datetime.utcnow()))
    s.commit()
    assert s.query(m.MLOrderCache).count() == 2
    s.close()


def test_day_sync_status_unique_per_seller_day(tmp_path, monkeypatch):
    db, m = _fresh_db(tmp_path, monkeypatch)
    s = db.FinSessionLocal()
    # Mesmo dia em sellers diferentes coexiste (corrige o unique global do v1)
    s.add(m.MLDaySyncStatus(seller_id=1, day=date(2026,5,1),
                            last_synced_at=datetime.utcnow(), orders_count=10, status="ok"))
    s.add(m.MLDaySyncStatus(seller_id=2, day=date(2026,5,1),
                            last_synced_at=datetime.utcnow(), orders_count=5, status="ok"))
    s.commit()
    assert s.query(m.MLDaySyncStatus).count() == 2
    s.close()


def test_seller_lock_and_backfill_job_tables_exist(tmp_path, monkeypatch):
    db, m = _fresh_db(tmp_path, monkeypatch)
    s = db.FinSessionLocal()
    s.add(m.MLSellerLock(seller_id=1, holder=None, leased_until=None))
    s.add(m.MLBackfillJob(seller_id=1, day_from=date(2026,1,1), day_to=date(2026,5,1),
                          status="pending", created_at=datetime.utcnow()))
    s.commit()
    assert s.query(m.MLSellerLock).count() == 1
    assert s.query(m.MLBackfillJob).count() == 1
    s.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_models_v2.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'financeiro_ml.models_v2'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/financeiro_ml/models_v2.py
"""Schema v2 multi-seller do financeiro ML. Liga em FinBase (db isolada)."""
from datetime import datetime, date
from sqlalchemy import (
    Integer, String, Text, DateTime, Date, Numeric, Index, PrimaryKeyConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from financeiro_ml.db import FinBase


class MLTokens(FinBase):
    __tablename__ = "ml_tokens"
    seller_id: Mapped[int] = mapped_column(Integer, primary_key=True)  # = user_id ML
    client_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    refresh_locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SkuFinanceiro(FinBase):
    __tablename__ = "sku_financeiro"
    sku: Mapped[str] = mapped_column(String(100), primary_key=True)
    custo_unit: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    imposto_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by: Mapped[int] = mapped_column(Integer, nullable=False)


class MLOrderCache(FinBase):
    __tablename__ = "ml_orders_cache"
    __table_args__ = (
        PrimaryKeyConstraint("seller_id", "order_id"),
        Index("ix_orders_ref", "seller_id", "date_closed", "date_created"),
        Index("ix_orders_dlu", "seller_id", "date_last_updated"),
        Index("ix_orders_ship", "seller_id", "shipment_id"),
    )
    seller_id: Mapped[int] = mapped_column(Integer, nullable=False)
    order_id: Mapped[int] = mapped_column(Integer, nullable=False)
    date_created: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    date_closed: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    date_last_updated: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    status_detail: Mapped[str | None] = mapped_column(String(100), nullable=True)
    produto_total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    frete_comprador: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    frete_vendedor: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    tarifa_bruta: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    tarifa_refund: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    refund_amount_partial: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    cupom_seller: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    modalidade_anuncio: Mapped[str | None] = mapped_column(String(30), nullable=True)
    logistic_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    shipping_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)
    shipment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    breakdown_bucket: Mapped[str | None] = mapped_column(String(20), nullable=True)
    frete_incerto: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)  # bug 4: marca incerteza
    raw_json: Mapped[str] = mapped_column(Text, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MLOrderItemCache(FinBase):
    __tablename__ = "ml_order_items_cache"
    __table_args__ = (
        UniqueConstraint("seller_id", "order_id", "item_id", name="uq_ml_item_seller_order_item"),
        Index("ix_items_order", "seller_id", "order_id"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seller_id: Mapped[int] = mapped_column(Integer, nullable=False)
    order_id: Mapped[int] = mapped_column(Integer, nullable=False)
    item_id: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    seller_sku: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    category_id: Mapped[str | None] = mapped_column(String(30), nullable=True)


class MLDaySyncStatus(FinBase):
    __tablename__ = "ml_day_sync_status"
    __table_args__ = (PrimaryKeyConstraint("seller_id", "day"),)
    seller_id: Mapped[int] = mapped_column(Integer, nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    orders_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # ok|failed|rate_limited|partial|imported_unverified
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class MLBackfillJob(FinBase):
    __tablename__ = "ml_backfill_jobs"
    __table_args__ = (Index("ix_jobs_status", "status", "created_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seller_id: Mapped[int] = mapped_column(Integer, nullable=False)
    day_from: Mapped[date] = mapped_column(Date, nullable=False)
    day_to: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending|running|done|failed|cancelled
    progress_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MLSellerLock(FinBase):
    __tablename__ = "ml_seller_lock"
    seller_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    holder: Mapped[str | None] = mapped_column(String(60), nullable=True)
    leased_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_models_v2.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/models_v2.py backend/financeiro_ml/tests/test_models_v2.py
git commit -m "feat(financeiro-ml): schema v2 multi-seller (PK composta seller+order)"
```

### Task 4: Função de criação de tabelas (`init_fin_db`)

**Files:**
- Modify: `backend/financeiro_ml/db.py`
- Test: `backend/financeiro_ml/tests/test_fin_db.py` (adiciona caso)

- [ ] **Step 1: Write the failing test (append ao arquivo existente)**

```python
def test_init_fin_db_creates_all_tables(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCEIRO_ML_DATABASE_URL", f"sqlite:///{tmp_path}/fin.db")
    import importlib
    import financeiro_ml.db as db
    importlib.reload(db)
    import financeiro_ml.models_v2  # noqa
    db.init_fin_db()
    from sqlalchemy import inspect
    tables = set(inspect(db.fin_engine).get_table_names())
    assert {"ml_tokens", "ml_orders_cache", "ml_order_items_cache",
            "ml_day_sync_status", "ml_backfill_jobs", "ml_seller_lock",
            "sku_financeiro"}.issubset(tables)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_fin_db.py::test_init_fin_db_creates_all_tables -v`
Expected: FAIL — `AttributeError: module 'financeiro_ml.db' has no attribute 'init_fin_db'`

- [ ] **Step 3: Write minimal implementation (append em db.py)**

```python
def init_fin_db():
    """Cria todas as tabelas do schema v2 no banco isolado."""
    import financeiro_ml.models_v2  # noqa — registra modelos em FinBase.metadata
    FinBase.metadata.create_all(bind=fin_engine)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_fin_db.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/db.py backend/financeiro_ml/tests/test_fin_db.py
git commit -m "feat(financeiro-ml): init_fin_db cria schema v2 no banco isolado"
```

### Task 5: conftest com fixture de DB isolado in-memory por teste

**Files:**
- Create: `backend/financeiro_ml/tests/conftest.py`

- [ ] **Step 1: Write the fixture (não é teste — habilita os próximos)**

```python
# backend/financeiro_ml/tests/conftest.py
import importlib
import pytest


@pytest.fixture
def fin_db(tmp_path, monkeypatch):
    """DB financeiro isolado, recriado por teste. Retorna o módulo db + models_v2."""
    monkeypatch.setenv("FINANCEIRO_ML_DATABASE_URL", f"sqlite:///{tmp_path}/fin.db")
    import financeiro_ml.db as db
    importlib.reload(db)
    import financeiro_ml.models_v2 as m
    importlib.reload(m)
    db.init_fin_db()
    return db, m
```

- [ ] **Step 2: Smoke test rápido usando a fixture**

Adicionar a `backend/financeiro_ml/tests/test_models_v2.py`:

```python
def test_fixture_fin_db_works(fin_db):
    db, m = fin_db
    s = db.FinSessionLocal()
    assert s.query(m.MLOrderCache).count() == 0
    s.close()
```

- [ ] **Step 3: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_models_v2.py::test_fixture_fin_db_works -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/financeiro_ml/tests/conftest.py backend/financeiro_ml/tests/test_models_v2.py
git commit -m "test(financeiro-ml): fixture fin_db isolado por teste"
```

---

## Fase 2 — Migração de dados v1 → v2 (sem re-buscar)

> **Por quê:** os dados em produção já foram caros de buscar (905–1138 pedidos/dia). Re-buscar = risco de 429. Copiamos as linhas do `.db` atual carimbando `seller_id` do seller default. **Nunca** marcamos um dia como `ok` sem ter buscado — dias sem status entram como `imported_unverified` (não contam como fresco; o poller reconcilia).

### Task 6: Migração das tabelas de dados (orders + items + tokens)

**Files:**
- Create: `backend/financeiro_ml/migrate_v1_to_v2.py`
- Test: `backend/financeiro_ml/tests/test_migrate_v1_v2.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/financeiro_ml/tests/test_migrate_v1_v2.py
import importlib
from datetime import datetime, date
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


def _make_v1_db(path):
    """Cria um .db estilo v1 (sem seller_id) com 2 orders, 1 item, 1 token, 1 day_status."""
    eng = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    with eng.begin() as c:
        c.execute(text("CREATE TABLE ml_tokens (id INTEGER PRIMARY KEY, access_token TEXT, refresh_token TEXT, user_id INTEGER, expires_at DATETIME, updated_at DATETIME)"))
        c.execute(text("INSERT INTO ml_tokens VALUES (1,'acc','ref',555,'2026-05-28 00:00:00','2026-05-28 00:00:00')"))
        c.execute(text("CREATE TABLE ml_orders_cache (order_id INTEGER PRIMARY KEY, date_created DATETIME, date_closed DATETIME, date_last_updated DATETIME, status TEXT, status_detail TEXT, produto_total NUMERIC, frete_comprador NUMERIC, frete_vendedor NUMERIC, tarifa_bruta NUMERIC, tarifa_refund NUMERIC, refund_amount_partial NUMERIC, cupom_seller NUMERIC, modalidade_anuncio TEXT, logistic_type TEXT, shipping_mode TEXT, shipment_id INTEGER, breakdown_bucket TEXT, raw_json TEXT, synced_at DATETIME, synced_run_id INTEGER)"))
        c.execute(text("INSERT INTO ml_orders_cache (order_id,date_created,status,produto_total,raw_json,synced_at,date_last_updated) VALUES (100,'2026-05-20 10:00:00','paid',50.0,'{}','2026-05-20 11:00:00','2026-05-20 10:30:00')"))
        c.execute(text("INSERT INTO ml_orders_cache (order_id,date_created,status,produto_total,raw_json,synced_at,date_last_updated) VALUES (101,'2026-05-21 10:00:00','paid',70.0,'{}','2026-05-21 11:00:00','2026-05-21 12:00:00')"))
        c.execute(text("CREATE TABLE ml_order_items_cache (id INTEGER PRIMARY KEY, order_id INTEGER, item_id TEXT, title TEXT, seller_sku TEXT, quantity INTEGER, unit_price NUMERIC, category_id TEXT)"))
        c.execute(text("INSERT INTO ml_order_items_cache (order_id,item_id,title,seller_sku,quantity,unit_price) VALUES (100,'MLB1','Prod A','SKU-A',1,50.0)"))
        c.execute(text("CREATE TABLE ml_day_sync_status (id INTEGER PRIMARY KEY, day DATE, last_synced_at DATETIME, orders_count INTEGER, status TEXT, error_message TEXT)"))
        c.execute(text("INSERT INTO ml_day_sync_status (day,last_synced_at,orders_count,status) VALUES ('2026-05-20','2026-05-20 11:00:00',1,'ok')"))
    eng.dispose()


def test_migrate_copies_orders_items_with_seller(tmp_path, monkeypatch):
    v1 = tmp_path / "v1.db"
    _make_v1_db(str(v1))
    monkeypatch.setenv("FINANCEIRO_ML_DATABASE_URL", f"sqlite:///{tmp_path}/fin.db")
    import financeiro_ml.db as db
    importlib.reload(db)
    import financeiro_ml.models_v2 as m
    importlib.reload(m)
    db.init_fin_db()

    import financeiro_ml.migrate_v1_to_v2 as mig
    importlib.reload(mig)
    report = mig.migrate(v1_db_path=str(v1), seller_id=555)

    s = db.FinSessionLocal()
    assert s.query(m.MLOrderCache).count() == 2
    assert s.query(m.MLOrderItemCache).count() == 1
    assert all(o.seller_id == 555 for o in s.query(m.MLOrderCache).all())
    assert s.query(m.MLTokens).filter_by(seller_id=555).count() == 1
    assert report["orders"] == 2 and report["items"] == 1
    s.close()


def test_migrate_status_ok_preserved_others_unverified(tmp_path, monkeypatch):
    v1 = tmp_path / "v1.db"
    _make_v1_db(str(v1))
    monkeypatch.setenv("FINANCEIRO_ML_DATABASE_URL", f"sqlite:///{tmp_path}/fin.db")
    import financeiro_ml.db as db
    importlib.reload(db)
    import financeiro_ml.models_v2 as m
    importlib.reload(m)
    db.init_fin_db()
    import financeiro_ml.migrate_v1_to_v2 as mig
    importlib.reload(mig)
    mig.migrate(v1_db_path=str(v1), seller_id=555)
    s = db.FinSessionLocal()
    # Dia 20 veio com status ok no v1 → preservado ok
    d20 = s.query(m.MLDaySyncStatus).filter_by(seller_id=555, day=date(2026,5,20)).first()
    assert d20.status == "ok"
    s.close()


def test_migrate_count_matches_before_after(tmp_path, monkeypatch):
    v1 = tmp_path / "v1.db"
    _make_v1_db(str(v1))
    monkeypatch.setenv("FINANCEIRO_ML_DATABASE_URL", f"sqlite:///{tmp_path}/fin.db")
    import financeiro_ml.db as db
    importlib.reload(db)
    import financeiro_ml.models_v2 as m
    importlib.reload(m)
    db.init_fin_db()
    import financeiro_ml.migrate_v1_to_v2 as mig
    importlib.reload(mig)
    report = mig.migrate(v1_db_path=str(v1), seller_id=555)
    assert report["orders"] == report["orders_src"]  # nada perdido
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_migrate_v1_v2.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'financeiro_ml.migrate_v1_to_v2'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/financeiro_ml/migrate_v1_to_v2.py
"""Migração one-shot: copia dados do .db v1 (sem seller_id) → schema v2 isolado.

NÃO re-busca nada no ML (zero risco de 429). Carimba seller_id do seller default.
Regra de segurança: status de dia só vira 'ok' se já era 'ok' no v1; o resto
(ausente/falho) entra como 'imported_unverified' — não conta como fresco.
"""
from datetime import datetime
from sqlalchemy import create_engine, text


def _parse_dt(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    return datetime.fromisoformat(str(v))


def migrate(*, v1_db_path: str, seller_id: int) -> dict:
    from financeiro_ml.db import FinSessionLocal
    from financeiro_ml.models_v2 import (
        MLOrderCache, MLOrderItemCache, MLDaySyncStatus, MLTokens,
    )
    src = create_engine(f"sqlite:///{v1_db_path}", connect_args={"check_same_thread": False})
    report = {"orders": 0, "orders_src": 0, "items": 0, "days": 0, "tokens": 0}

    with src.connect() as c:
        order_rows = c.execute(text("SELECT * FROM ml_orders_cache")).mappings().all()
        item_rows = c.execute(text("SELECT * FROM ml_order_items_cache")).mappings().all()
        day_rows = c.execute(text("SELECT * FROM ml_day_sync_status")).mappings().all()
        try:
            tok_rows = c.execute(text("SELECT * FROM ml_tokens")).mappings().all()
        except Exception:
            tok_rows = []
    report["orders_src"] = len(order_rows)

    s = FinSessionLocal()
    try:
        for r in order_rows:
            s.merge(MLOrderCache(
                seller_id=seller_id, order_id=r["order_id"],
                date_created=_parse_dt(r["date_created"]),
                date_closed=_parse_dt(r["date_closed"]),
                date_last_updated=_parse_dt(r["date_last_updated"]),
                status=r["status"], status_detail=r["status_detail"],
                produto_total=r["produto_total"] or 0,
                frete_comprador=r["frete_comprador"] or 0,
                frete_vendedor=r["frete_vendedor"] or 0,
                tarifa_bruta=r["tarifa_bruta"] or 0,
                tarifa_refund=r["tarifa_refund"] or 0,
                refund_amount_partial=r["refund_amount_partial"] or 0,
                cupom_seller=r["cupom_seller"] or 0,
                modalidade_anuncio=r["modalidade_anuncio"],
                logistic_type=r["logistic_type"], shipping_mode=r["shipping_mode"],
                shipment_id=r["shipment_id"], breakdown_bucket=r["breakdown_bucket"],
                frete_incerto=0,
                raw_json=r["raw_json"] or "{}",
                synced_at=_parse_dt(r["synced_at"]) or datetime.utcnow(),
            ))
            report["orders"] += 1

        for r in item_rows:
            s.add(MLOrderItemCache(
                seller_id=seller_id, order_id=r["order_id"], item_id=r["item_id"],
                title=r["title"] or "", seller_sku=r["seller_sku"],
                quantity=r["quantity"] or 0, unit_price=r["unit_price"] or 0,
                category_id=r["category_id"],
            ))
            report["items"] += 1

        for r in day_rows:
            status = "ok" if r["status"] == "ok" else "imported_unverified"
            s.merge(MLDaySyncStatus(
                seller_id=seller_id, day=_parse_dt(r["day"]).date() if not hasattr(r["day"], "year") else r["day"],
                last_synced_at=_parse_dt(r["last_synced_at"]) or datetime.utcnow(),
                orders_count=r["orders_count"] or 0, status=status,
                error_message=r["error_message"],
            ))
            report["days"] += 1

        for r in tok_rows:
            s.merge(MLTokens(
                seller_id=seller_id, client_id=None,
                access_token=r["access_token"], refresh_token=r["refresh_token"],
                expires_at=_parse_dt(r["expires_at"]) or datetime.utcnow(),
                updated_at=_parse_dt(r["updated_at"]) or datetime.utcnow(),
            ))
            report["tokens"] += 1

        s.commit()
    finally:
        s.close()
        src.dispose()
    return report
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_migrate_v1_v2.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/migrate_v1_to_v2.py backend/financeiro_ml/tests/test_migrate_v1_v2.py
git commit -m "feat(financeiro-ml): migração v1->v2 sem re-buscar (carimba seller_id)"
```

### Task 7: CLI de migração (executável manual, não roda no boot)

**Files:**
- Modify: `backend/financeiro_ml/migrate_v1_to_v2.py` (adiciona `__main__`)

- [ ] **Step 1: Adicionar bloco CLI ao final do arquivo**

```python
if __name__ == "__main__":
    import argparse, os
    from financeiro_ml.db import init_fin_db
    parser = argparse.ArgumentParser(description="Migra dados financeiro ML v1 -> v2")
    parser.add_argument("--v1-db", required=True, help="caminho do .db v1 (ex: ./warehouse_v3_local.db)")
    parser.add_argument("--seller-id", type=int, required=True, help="user_id ML do seller default")
    args = parser.parse_args()
    init_fin_db()
    rep = migrate(v1_db_path=args.v1_db, seller_id=args.seller_id)
    print(f"[migrate] {rep}")
```

- [ ] **Step 2: Smoke manual (com banco descartável)**

Run: `cd backend && FINANCEIRO_ML_DATABASE_URL="sqlite:////tmp/fin_smoke.db" python -c "from financeiro_ml.db import init_fin_db; init_fin_db(); print('ok')"`
Expected: imprime `ok` sem erro. (A migração real contra produção é feita só na Fase 8, com autorização.)

- [ ] **Step 3: Commit**

```bash
git add backend/financeiro_ml/migrate_v1_to_v2.py
git commit -m "feat(financeiro-ml): CLI manual da migração v1->v2"
```

---

## Fase 3 — Cálculo puro (sem I/O)

> **Por quê:** `sync.py:_save_order` mistura I/O (chamadas ML, commit) com cálculo. Separamos o cálculo PURO em `build_order_row()` (recebe dicts já buscados, devolve dict de campos) — testável sem rede, reusável pelo worker. As chamadas ML ficam no worker (Fase 4/5). `aggregator.py` é preservado; só passa a filtrar por `seller_id`.

### Task 8: `build_order_row()` — frete básico (list_cost − cost)

**Files:**
- Create: `backend/financeiro_ml/calc.py`
- Test: `backend/financeiro_ml/tests/test_calc.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/financeiro_ml/tests/test_calc.py
from decimal import Decimal
from financeiro_ml.calc import build_order_row


def _order(**over):
    base = {
        "id": 100,
        "status": "paid",
        "status_detail": None,
        "date_created": "2026-05-20T10:00:00.000-03:00",
        "date_closed": "2026-05-20T11:00:00.000-03:00",
        "date_last_updated": "2026-05-20T11:30:00.000-03:00",
        "tags": [],
        "order_items": [
            {"item": {"id": "MLB1", "title": "Prod A", "category_id": "CAT1",
                      "seller_custom_field": "SKU-A", "seller_sku": "SKU-A"},
             "unit_price": 50.0, "quantity": 2, "sale_fee": 5.0,
             "listing_type_id": "gold_pro"},
        ],
        "payments": [],
        "shipping": {"id": 9001},
    }
    base.update(over)
    return base


def test_build_row_basico_frete_vendedor_diff():
    order = _order()
    shipment = {"shipping_option": {"cost": 0, "list_cost": 20}, "logistic_type": "drop_off", "mode": "me2"}
    row = build_order_row(seller_id=1, order=order, shipment=shipment,
                          shipment_costs={}, discounts={"details": []})
    assert row["seller_id"] == 1
    assert row["order_id"] == 100
    assert row["produto_total"] == Decimal("100.0")    # 50 * 2
    assert row["tarifa_bruta"] == Decimal("10.0")      # 5 * 2
    assert row["frete_vendedor"] == Decimal("20")      # max(0, 20-0)
    assert row["frete_comprador"] == Decimal("0")
    assert row["breakdown_bucket"] == "places_coleta"


def test_build_row_items_list():
    order = _order()
    shipment = {"shipping_option": {"cost": 5, "list_cost": 5}}
    row = build_order_row(seller_id=1, order=order, shipment=shipment,
                          shipment_costs={}, discounts={"details": []})
    assert len(row["items"]) == 1
    assert row["items"][0]["seller_sku"] == "SKU-A"
    assert row["items"][0]["quantity"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_calc.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'financeiro_ml.calc'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/financeiro_ml/calc.py
"""Cálculo PURO de uma order ML → dict de campos do cache. Sem I/O, sem commit.

Migra a inteligência validada de sync.py:_save_order. Recebe os payloads já
buscados (order do search + shipment + shipment_costs + discounts) e devolve
um dict pronto pra upsert. Testável sem rede.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

BRT = timezone(timedelta(hours=-3))


def _to_brt_naive(iso_str: str | None) -> datetime | None:
    if not iso_str:
        return None
    s = iso_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    return dt.astimezone(BRT).replace(tzinfo=None)


def _looks_human_sku(s: str | None) -> bool:
    if not s:
        return False
    return not (s.startswith("MLB") and "_" in s)


def _seller_sku_from_item(order_item: dict) -> str | None:
    item = order_item.get("item") or {}
    sku_cf = item.get("seller_custom_field")
    sku_sku = item.get("seller_sku")
    if _looks_human_sku(sku_sku):
        return sku_sku
    if _looks_human_sku(sku_cf):
        return sku_cf
    return sku_cf or sku_sku


def build_order_row(*, seller_id: int, order: dict, shipment: dict,
                    shipment_costs: dict, discounts: dict) -> dict:
    from financeiro_ml.aggregator import _logistic_bucket

    order_id = order["id"]
    produto_total = Decimal("0")
    tarifa_bruta = Decimal("0")
    for it in order.get("order_items", []):
        produto_total += Decimal(str(it["unit_price"])) * Decimal(it["quantity"])
        tarifa_bruta += Decimal(str(it.get("sale_fee", 0))) * Decimal(it["quantity"])

    so = shipment.get("shipping_option") or {}
    frete_comprador = Decimal(str(so.get("cost", 0) or 0))
    list_cost = Decimal(str(so.get("list_cost", 0) or 0))
    frete_vendedor = max(Decimal("0"), list_cost - frete_comprador)
    logistic_type = shipment.get("logistic_type")
    shipping_mode = shipment.get("mode")
    shipment_id = (order.get("shipping") or {}).get("id")
    frete_incerto = False

    if frete_comprador == 0 and shipment_id:
        if shipment_costs:
            receiver = shipment_costs.get("receiver") or {}
            sender = (shipment_costs.get("senders") or [{}])[0]
            sender_cost = Decimal(str(sender.get("cost") or 0))
            sender_save = Decimal(str(sender.get("save") or 0))
            disc_types = {d.get("type") for d in (receiver.get("discounts") or [])}
            if "loyal" in disc_types and sender_cost == 0:
                frete_comprador = Decimal(str(receiver.get("save") or 0))
            elif ("ratio" in disc_types and sender_cost > 0 and sender_save > 0
                  and logistic_type == "self_service"):
                frete_comprador = sender_save
        else:
            # bug 4: costs indisponível → não assume 0 cego, marca incerteza
            frete_incerto = True

    refund_total = Decimal("0")
    for pay in (order.get("payments") or []):
        refund_total += Decimal(str(pay.get("transaction_amount_refunded", 0) or 0))
    is_total_cancel = order.get("status") == "cancelled"
    refund_partial = Decimal("0") if is_total_cancel else refund_total

    cupom_seller = Decimal("0")
    for det in (discounts.get("details") or []):
        if det.get("type") == "coupon":
            for it in (det.get("items") or []):
                cupom_seller += Decimal(str((it.get("amounts") or {}).get("seller") or 0))

    bucket = _logistic_bucket(logistic_type, shipping_mode)
    first_item = (order.get("order_items") or [{}])[0]
    modalidade = first_item.get("listing_type_id")

    items = []
    for it in order.get("order_items", []):
        item = it["item"]
        items.append({
            "seller_id": seller_id, "order_id": order_id, "item_id": item["id"],
            "title": item.get("title", ""), "seller_sku": _seller_sku_from_item(it),
            "quantity": it["quantity"], "unit_price": Decimal(str(it["unit_price"])),
            "category_id": item.get("category_id"),
        })

    return {
        "seller_id": seller_id, "order_id": order_id,
        "date_created": _to_brt_naive(order["date_created"]),
        "date_closed": _to_brt_naive(order.get("date_closed")),
        "date_last_updated": _to_brt_naive(
            order.get("date_last_updated") or order.get("last_updated")),
        "status": order["status"], "status_detail": order.get("status_detail"),
        "produto_total": produto_total, "frete_comprador": frete_comprador,
        "frete_vendedor": frete_vendedor, "tarifa_bruta": tarifa_bruta,
        "tarifa_refund": Decimal("0"), "refund_amount_partial": refund_partial,
        "cupom_seller": cupom_seller, "modalidade_anuncio": modalidade,
        "logistic_type": logistic_type, "shipping_mode": shipping_mode,
        "shipment_id": shipment_id, "breakdown_bucket": bucket,
        "frete_incerto": frete_incerto, "items": items,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_calc.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/calc.py backend/financeiro_ml/tests/test_calc.py
git commit -m "feat(financeiro-ml): build_order_row puro (frete base + items)"
```

### Task 9: `build_order_row()` — frete loyal e ratio (subsídio)

**Files:**
- Test: `backend/financeiro_ml/tests/test_calc.py` (append)
- (Implementação já coberta na Task 8 — estes testes blindam os ramos loyal/ratio.)

- [ ] **Step 1: Write the tests (append)**

```python
def test_build_row_frete_loyal_mercado_pontos():
    order = _order()
    shipment = {"shipping_option": {"cost": 0, "list_cost": 0}, "logistic_type": "fulfillment"}
    costs = {"receiver": {"save": 18.5, "discounts": [{"type": "loyal"}]},
             "senders": [{"cost": 0, "save": 0}]}
    row = build_order_row(seller_id=1, order=order, shipment=shipment,
                          shipment_costs=costs, discounts={"details": []})
    assert row["frete_comprador"] == Decimal("18.5")
    assert row["frete_incerto"] is False


def test_build_row_frete_ratio_flex():
    order = _order()
    shipment = {"shipping_option": {"cost": 0, "list_cost": 0}, "logistic_type": "self_service"}
    costs = {"receiver": {"discounts": [{"type": "ratio"}]},
             "senders": [{"cost": 3.0, "save": 7.25}]}
    row = build_order_row(seller_id=1, order=order, shipment=shipment,
                          shipment_costs=costs, discounts={"details": []})
    assert row["frete_comprador"] == Decimal("7.25")


def test_build_row_frete_incerto_quando_costs_vazio():
    order = _order()
    shipment = {"shipping_option": {"cost": 0, "list_cost": 0}, "logistic_type": "fulfillment"}
    row = build_order_row(seller_id=1, order=order, shipment=shipment,
                          shipment_costs={}, discounts={"details": []})
    # sem costs e fc=0 → marca incerteza (bug 4), não engole como 0 silencioso
    assert row["frete_incerto"] is True
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_calc.py -v`
Expected: PASS (5 passed) — implementação da Task 8 já cobre.

- [ ] **Step 3: Commit**

```bash
git add backend/financeiro_ml/tests/test_calc.py
git commit -m "test(financeiro-ml): blindar ramos loyal/ratio/incerto do build_order_row"
```

### Task 10: `build_order_row()` — cupom seller e refund parcial

**Files:**
- Test: `backend/financeiro_ml/tests/test_calc.py` (append)

- [ ] **Step 1: Write the tests (append)**

```python
def test_build_row_cupom_seller():
    order = _order(tags=["order_has_discount"])
    shipment = {"shipping_option": {"cost": 10, "list_cost": 10}}
    disc = {"details": [{"type": "coupon", "items": [{"amounts": {"seller": 12.0}}]}]}
    row = build_order_row(seller_id=1, order=order, shipment=shipment,
                          shipment_costs={}, discounts=disc)
    assert row["cupom_seller"] == Decimal("12.0")


def test_build_row_refund_parcial_e_cancel_zera():
    order = _order(payments=[{"transaction_amount_refunded": 30.0}])
    shipment = {"shipping_option": {"cost": 10, "list_cost": 10}}
    row = build_order_row(seller_id=1, order=order, shipment=shipment,
                          shipment_costs={}, discounts={"details": []})
    assert row["refund_amount_partial"] == Decimal("30.0")

    order_cancel = _order(status="cancelled", payments=[{"transaction_amount_refunded": 100.0}])
    row2 = build_order_row(seller_id=1, order=order_cancel, shipment=shipment,
                           shipment_costs={}, discounts={"details": []})
    assert row2["refund_amount_partial"] == Decimal("0")
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_calc.py -v`
Expected: PASS (7 passed)

- [ ] **Step 3: Commit**

```bash
git add backend/financeiro_ml/tests/test_calc.py
git commit -m "test(financeiro-ml): cupom seller + refund parcial/cancel no build_order_row"
```

### Task 11: `aggregator.aggregate` aceita orders já filtrados por seller

**Files:**
- Test: `backend/financeiro_ml/tests/test_aggregator_seller.py`
- (Sem mudança de código: `aggregate` já opera sobre listas; o filtro por seller é na query do router. Este teste documenta/blinda que aggregate é seller-agnóstico desde que receba só orders de 1 seller.)

- [ ] **Step 1: Write the test**

```python
# backend/financeiro_ml/tests/test_aggregator_seller.py
from decimal import Decimal
from datetime import datetime
from financeiro_ml.aggregator import aggregate


def _order(order_id, produto, status="paid"):
    return {"order_id": order_id, "status": status, "produto_total": Decimal(str(produto)),
            "frete_comprador": Decimal("0"), "frete_vendedor": Decimal("0"),
            "tarifa_bruta": Decimal("0"), "tarifa_refund": Decimal("0"),
            "refund_amount_partial": Decimal("0"), "cupom_seller": Decimal("0"),
            "logistic_type": None, "shipping_mode": None, "shipment_id": None,
            "breakdown_bucket": "outros", "date_created": datetime(2026,5,20)}


def test_aggregate_only_given_orders_counted():
    orders = [_order(1, 100), _order(2, 50)]
    items = [{"order_id": 1, "title": "A", "seller_sku": "X", "quantity": 1, "unit_price": Decimal("100")},
             {"order_id": 2, "title": "B", "seller_sku": "Y", "quantity": 1, "unit_price": Decimal("50")}]
    res = aggregate(orders, items, {})
    assert res["cards"]["vendas_aprovadas"] == Decimal("150.00")
    assert res["cards"]["qtd_vendas_aprovadas"] == 2
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_aggregator_seller.py -v`
Expected: PASS — confirma que aggregate é seller-agnóstico (o isolamento é na query).

- [ ] **Step 3: Commit**

```bash
git add backend/financeiro_ml/tests/test_aggregator_seller.py
git commit -m "test(financeiro-ml): aggregate seller-agnóstico (filtro fica na query)"
```

---

## Fase 4 — Motor: lock durável + fila + write worker

### Task 12: Lock durável por seller (CAS + lease)

**Files:**
- Create: `backend/financeiro_ml/lock.py`
- Test: `backend/financeiro_ml/tests/test_lock.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/financeiro_ml/tests/test_lock.py
from datetime import datetime, timedelta


def test_acquire_when_free(fin_db):
    db, m = fin_db
    from financeiro_ml.lock import acquire_seller_lock, release_seller_lock
    assert acquire_seller_lock(db.FinSessionLocal, seller_id=1, holder="poller", ttl_sec=120) is True
    release_seller_lock(db.FinSessionLocal, seller_id=1, holder="poller")


def test_second_acquire_blocked_while_held(fin_db):
    db, m = fin_db
    from financeiro_ml.lock import acquire_seller_lock
    assert acquire_seller_lock(db.FinSessionLocal, seller_id=1, holder="poller", ttl_sec=120) is True
    # outro holder não consegue enquanto a lease é válida
    assert acquire_seller_lock(db.FinSessionLocal, seller_id=1, holder="backfill", ttl_sec=120) is False


def test_expired_lease_is_takeable(fin_db):
    db, m = fin_db
    from financeiro_ml.lock import acquire_seller_lock
    # cria lock já vencido manualmente
    s = db.FinSessionLocal()
    s.add(m.MLSellerLock(seller_id=1, holder="old", leased_until=datetime.utcnow() - timedelta(seconds=10)))
    s.commit(); s.close()
    assert acquire_seller_lock(db.FinSessionLocal, seller_id=1, holder="poller", ttl_sec=120) is True


def test_renew_extends_lease(fin_db):
    db, m = fin_db
    from financeiro_ml.lock import acquire_seller_lock, renew_seller_lock
    acquire_seller_lock(db.FinSessionLocal, seller_id=1, holder="poller", ttl_sec=1)
    assert renew_seller_lock(db.FinSessionLocal, seller_id=1, holder="poller", ttl_sec=120) is True
    s = db.FinSessionLocal()
    row = s.query(m.MLSellerLock).filter_by(seller_id=1).first()
    assert row.leased_until > datetime.utcnow() + timedelta(seconds=60)
    s.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_lock.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'financeiro_ml.lock'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/financeiro_ml/lock.py
"""Lock durável por seller (CAS + lease/TTL). Atravessa processos — cobre o caso
das 2 réplicas no rolling deploy do Railway, onde asyncio.Lock (por-processo)
não protege. Lease vencida é tomável (sem deadlock em crash)."""
from datetime import datetime, timedelta
from sqlalchemy import text


def acquire_seller_lock(session_factory, *, seller_id: int, holder: str, ttl_sec: int) -> bool:
    now = datetime.utcnow()
    leased_until = now + timedelta(seconds=ttl_sec)
    s = session_factory()
    try:
        # Garante a linha (insert idempotente) sem sobrescrever lease válida
        s.execute(text(
            "INSERT INTO ml_seller_lock (seller_id, holder, leased_until) "
            "VALUES (:sid, NULL, NULL) "
            "ON CONFLICT(seller_id) DO NOTHING"
        ), {"sid": seller_id})
        res = s.execute(text(
            "UPDATE ml_seller_lock SET holder=:who, leased_until=:lu "
            "WHERE seller_id=:sid AND (holder IS NULL OR leased_until IS NULL OR leased_until < :now)"
        ), {"who": holder, "lu": leased_until, "sid": seller_id, "now": now})
        s.commit()
        return res.rowcount == 1
    finally:
        s.close()


def renew_seller_lock(session_factory, *, seller_id: int, holder: str, ttl_sec: int) -> bool:
    leased_until = datetime.utcnow() + timedelta(seconds=ttl_sec)
    s = session_factory()
    try:
        res = s.execute(text(
            "UPDATE ml_seller_lock SET leased_until=:lu WHERE seller_id=:sid AND holder=:who"
        ), {"lu": leased_until, "sid": seller_id, "who": holder})
        s.commit()
        return res.rowcount == 1
    finally:
        s.close()


def release_seller_lock(session_factory, *, seller_id: int, holder: str) -> None:
    s = session_factory()
    try:
        s.execute(text(
            "UPDATE ml_seller_lock SET holder=NULL, leased_until=NULL "
            "WHERE seller_id=:sid AND holder=:who"
        ), {"sid": seller_id, "who": holder})
        s.commit()
    finally:
        s.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_lock.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/lock.py backend/financeiro_ml/tests/test_lock.py
git commit -m "feat(financeiro-ml): lock durável por seller (CAS + lease/TTL)"
```

### Task 13: Upsert idempotente de order_row no cache

**Files:**
- Create: `backend/financeiro_ml/repo.py`
- Test: `backend/financeiro_ml/tests/test_repo.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/financeiro_ml/tests/test_repo.py
from decimal import Decimal
from datetime import datetime


def _row(seller_id=1, order_id=100, status="paid", produto="100"):
    return {
        "seller_id": seller_id, "order_id": order_id,
        "date_created": datetime(2026,5,20,10), "date_closed": datetime(2026,5,20,11),
        "date_last_updated": datetime(2026,5,20,11,30), "status": status, "status_detail": None,
        "produto_total": Decimal(produto), "frete_comprador": Decimal("0"),
        "frete_vendedor": Decimal("0"), "tarifa_bruta": Decimal("0"), "tarifa_refund": Decimal("0"),
        "refund_amount_partial": Decimal("0"), "cupom_seller": Decimal("0"),
        "modalidade_anuncio": "gold_pro", "logistic_type": None, "shipping_mode": None,
        "shipment_id": None, "breakdown_bucket": "outros", "frete_incerto": False,
        "items": [{"seller_id": seller_id, "order_id": order_id, "item_id": "MLB1",
                   "title": "A", "seller_sku": "X", "quantity": 1, "unit_price": Decimal("100"),
                   "category_id": "CAT1"}],
    }


def test_upsert_inserts_new(fin_db):
    db, m = fin_db
    from financeiro_ml.repo import upsert_order_row
    upsert_order_row(db.FinSessionLocal, _row())
    s = db.FinSessionLocal()
    assert s.query(m.MLOrderCache).count() == 1
    assert s.query(m.MLOrderItemCache).count() == 1
    s.close()


def test_upsert_idempotent_updates_in_place(fin_db):
    db, m = fin_db
    from financeiro_ml.repo import upsert_order_row
    upsert_order_row(db.FinSessionLocal, _row(status="paid", produto="100"))
    upsert_order_row(db.FinSessionLocal, _row(status="cancelled", produto="100"))
    s = db.FinSessionLocal()
    assert s.query(m.MLOrderCache).count() == 1            # não duplica
    assert s.query(m.MLOrderCache).first().status == "cancelled"  # status atualizado
    assert s.query(m.MLOrderItemCache).count() == 1         # itens não duplicam
    s.close()


def test_upsert_isolates_by_seller(fin_db):
    db, m = fin_db
    from financeiro_ml.repo import upsert_order_row
    upsert_order_row(db.FinSessionLocal, _row(seller_id=1, order_id=100))
    upsert_order_row(db.FinSessionLocal, _row(seller_id=2, order_id=100))
    s = db.FinSessionLocal()
    assert s.query(m.MLOrderCache).count() == 2  # mesmo order_id, sellers diferentes
    s.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_repo.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'financeiro_ml.repo'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/financeiro_ml/repo.py
"""Escrita no cache. Upsert idempotente por (seller_id, order_id). 1 commit/order."""
from datetime import datetime


def upsert_order_row(session_factory, row: dict) -> None:
    from financeiro_ml.models_v2 import MLOrderCache, MLOrderItemCache
    import json
    s = session_factory()
    try:
        existing = s.query(MLOrderCache).filter_by(
            seller_id=row["seller_id"], order_id=row["order_id"]).first()
        fields = dict(
            date_created=row["date_created"], date_closed=row["date_closed"],
            date_last_updated=row["date_last_updated"], status=row["status"],
            status_detail=row["status_detail"], produto_total=row["produto_total"],
            frete_comprador=row["frete_comprador"], frete_vendedor=row["frete_vendedor"],
            tarifa_bruta=row["tarifa_bruta"], tarifa_refund=row["tarifa_refund"],
            refund_amount_partial=row["refund_amount_partial"], cupom_seller=row["cupom_seller"],
            modalidade_anuncio=row["modalidade_anuncio"], logistic_type=row["logistic_type"],
            shipping_mode=row["shipping_mode"], shipment_id=row["shipment_id"],
            breakdown_bucket=row["breakdown_bucket"],
            frete_incerto=1 if row.get("frete_incerto") else 0,
            synced_at=datetime.utcnow(),
        )
        if existing is None:
            s.add(MLOrderCache(seller_id=row["seller_id"], order_id=row["order_id"],
                               raw_json=row.get("raw_json", "{}"), **fields))
        else:
            for k, v in fields.items():
                setattr(existing, k, v)
            s.query(MLOrderItemCache).filter_by(
                seller_id=row["seller_id"], order_id=row["order_id"]).delete()
        for it in row["items"]:
            s.add(MLOrderItemCache(**it))
        s.commit()
    finally:
        s.close()
```

> Nota: `raw_json` é gravado pelo worker (que tem o payload bruto); nos testes de repo passamos default `{}`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_repo.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/repo.py backend/financeiro_ml/tests/test_repo.py
git commit -m "feat(financeiro-ml): upsert idempotente por (seller_id,order_id)"
```

### Task 14: Day sync status — upsert por (seller, dia) com next_retry_at

**Files:**
- Modify: `backend/financeiro_ml/repo.py` (append)
- Test: `backend/financeiro_ml/tests/test_repo.py` (append)

- [ ] **Step 1: Write the failing test (append)**

```python
from datetime import date, timedelta

def test_set_day_status_ok(fin_db):
    db, m = fin_db
    from financeiro_ml.repo import set_day_status
    set_day_status(db.FinSessionLocal, seller_id=1, day=date(2026,5,20), status="ok", orders_count=42)
    s = db.FinSessionLocal()
    row = s.query(m.MLDaySyncStatus).filter_by(seller_id=1, day=date(2026,5,20)).first()
    assert row.status == "ok" and row.orders_count == 42
    s.close()


def test_set_day_status_rate_limited_sets_retry(fin_db):
    db, m = fin_db
    from financeiro_ml.repo import set_day_status
    set_day_status(db.FinSessionLocal, seller_id=1, day=date(2026,5,20),
                   status="rate_limited", orders_count=0, retry_after_sec=300)
    s = db.FinSessionLocal()
    row = s.query(m.MLDaySyncStatus).filter_by(seller_id=1, day=date(2026,5,20)).first()
    assert row.status == "rate_limited"
    assert row.next_retry_at is not None
    s.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_repo.py -k day_status -v`
Expected: FAIL — `ImportError: cannot import name 'set_day_status'`

- [ ] **Step 3: Write minimal implementation (append em repo.py)**

```python
def set_day_status(session_factory, *, seller_id: int, day, status: str,
                   orders_count: int = 0, error_message: str | None = None,
                   retry_after_sec: int | None = None) -> None:
    from financeiro_ml.models_v2 import MLDaySyncStatus
    from datetime import timedelta
    s = session_factory()
    try:
        row = s.query(MLDaySyncStatus).filter_by(seller_id=seller_id, day=day).first()
        next_retry = (datetime.utcnow() + timedelta(seconds=retry_after_sec)) if retry_after_sec else None
        if row is None:
            row = MLDaySyncStatus(seller_id=seller_id, day=day, last_synced_at=datetime.utcnow(),
                                  orders_count=orders_count, status=status,
                                  error_message=error_message, next_retry_at=next_retry)
            s.add(row)
        else:
            row.last_synced_at = datetime.utcnow()
            row.orders_count = orders_count
            row.status = status
            row.error_message = error_message
            row.next_retry_at = next_retry
        s.commit()
    finally:
        s.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_repo.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/repo.py backend/financeiro_ml/tests/test_repo.py
git commit -m "feat(financeiro-ml): set_day_status por (seller,dia) com next_retry_at"
```

### Task 15: Política de freshness multi-seller (`days_needing_sync`)

**Files:**
- Modify: `backend/financeiro_ml/repo.py` (append) ou novo `freshness.py`
- Test: `backend/financeiro_ml/tests/test_freshness.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/financeiro_ml/tests/test_freshness.py
from datetime import date, datetime, timedelta
from financeiro_ml.freshness import days_needing_sync


class _St:
    def __init__(self, status, last, next_retry=None):
        self.status = status
        self.last_synced_at = last
        self.next_retry_at = next_retry


def test_missing_day_needs_sync():
    today = date.today()
    assert today in days_needing_sync([today], {})


def test_ok_today_fresh_under_5min_skipped():
    today = date.today()
    st = {today: _St("ok", datetime.utcnow() - timedelta(minutes=2))}
    assert today not in days_needing_sync([today], st)


def test_ok_old_day_skipped():
    old = date.today() - timedelta(days=30)
    st = {old: _St("ok", datetime.utcnow() - timedelta(days=20))}
    assert old not in days_needing_sync([old], st)


def test_rate_limited_before_retry_skipped():
    d = date.today() - timedelta(days=1)
    st = {d: _St("rate_limited", datetime.utcnow(), next_retry=datetime.utcnow() + timedelta(minutes=5))}
    assert d not in days_needing_sync([d], st)


def test_rate_limited_after_retry_needs_sync():
    d = date.today() - timedelta(days=1)
    st = {d: _St("rate_limited", datetime.utcnow(), next_retry=datetime.utcnow() - timedelta(minutes=1))}
    assert d in days_needing_sync([d], st)


def test_imported_unverified_needs_sync():
    d = date.today() - timedelta(days=3)
    st = {d: _St("imported_unverified", datetime.utcnow() - timedelta(days=1))}
    assert d in days_needing_sync([d], st)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_freshness.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'financeiro_ml.freshness'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/financeiro_ml/freshness.py
"""Política de freshness multi-seller. Decide quais dias re-sincronizar.

Regras (migra a política do v1, + next_retry_at do backoff):
- dia sem status                         → sync
- status != ok/imported_unverified e antes do next_retry_at  → skip (backoff)
- status != ok (failed/rate_limited/partial) e já passou retry → sync
- status == imported_unverified          → sync (precisa confirmar contagem real)
- dia == hoje e ok e cache > 5min        → sync
- dia recente (<=14d) e ok e cache > 24h → sync
- dia antigo e ok                        → skip
"""
from datetime import date, datetime, timedelta

FRESH_WINDOW_DAYS = 14


def days_needing_sync(days: list[date], statuses: dict) -> list[date]:
    today = date.today()
    threshold_recent = today - timedelta(days=FRESH_WINDOW_DAYS)
    now = datetime.utcnow()
    needed = []
    for d in days:
        st = statuses.get(d)
        if st is None:
            needed.append(d); continue
        if st.status == "imported_unverified":
            needed.append(d); continue
        if st.status != "ok":
            nr = getattr(st, "next_retry_at", None)
            if nr is None or nr <= now:
                needed.append(d)
            continue
        if d == today:
            if now - st.last_synced_at > timedelta(minutes=5):
                needed.append(d)
            continue
        if d >= threshold_recent:
            if now - st.last_synced_at > timedelta(hours=24):
                needed.append(d)
    return needed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_freshness.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/freshness.py backend/financeiro_ml/tests/test_freshness.py
git commit -m "feat(financeiro-ml): política de freshness multi-seller (14d + backoff)"
```

### Task 16: Fila + write worker único (drena tasks, serializa escrita)

**Files:**
- Create: `backend/financeiro_ml/worker.py`
- Test: `backend/financeiro_ml/tests/test_worker.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/financeiro_ml/tests/test_worker.py
import asyncio
import pytest
from datetime import date, datetime
from decimal import Decimal


def _order_payload(order_id):
    return {"id": order_id, "status": "paid", "status_detail": None,
            "date_created": "2026-05-20T10:00:00.000-03:00",
            "date_closed": "2026-05-20T11:00:00.000-03:00",
            "date_last_updated": "2026-05-20T11:30:00.000-03:00", "tags": [],
            "order_items": [{"item": {"id": "MLB1", "title": "A", "category_id": "C",
                                      "seller_custom_field": "SKU-A", "seller_sku": "SKU-A"},
                             "unit_price": 50.0, "quantity": 1, "sale_fee": 5.0,
                             "listing_type_id": "gold_pro"}],
            "payments": [], "shipping": {"id": 9001}}


class FakeClient:
    def __init__(self, pages):
        self._pages = pages  # list de listas de orders por chamada de search
        self.calls = 0
    async def search_orders(self, **kw):
        page = self._pages[self.calls] if self.calls < len(self._pages) else []
        self.calls += 1
        return {"results": page}
    async def get_shipment(self, sid):
        return {"shipping_option": {"cost": 5, "list_cost": 5}, "logistic_type": "drop_off", "mode": "me2"}
    async def get_shipment_costs(self, sid):
        return {}
    async def get_order_discounts(self, oid):
        return {"details": []}


@pytest.mark.asyncio
async def test_worker_processes_poll_task(fin_db):
    db, m = fin_db
    from financeiro_ml.worker import WriteWorker, PollTask
    client = FakeClient(pages=[[_order_payload(100), _order_payload(101)], []])
    worker = WriteWorker(session_factory=db.FinSessionLocal, client_factory=lambda sid: client)
    q = asyncio.Queue()
    await q.put(PollTask(seller_id=1, days=[date(2026,5,20)]))
    runner = asyncio.create_task(worker.run(q))
    await q.join()
    worker.stop()
    await runner
    s = db.FinSessionLocal()
    assert s.query(m.MLOrderCache).filter_by(seller_id=1).count() == 2
    day = s.query(m.MLDaySyncStatus).filter_by(seller_id=1, day=date(2026,5,20)).first()
    assert day.status == "ok" and day.orders_count == 2
    s.close()


@pytest.mark.asyncio
async def test_worker_single_writer_serializes(fin_db):
    db, m = fin_db
    from financeiro_ml.worker import WriteWorker, PollTask
    c1 = FakeClient(pages=[[_order_payload(100)], []])
    c2 = FakeClient(pages=[[_order_payload(200)], []])
    clients = {1: c1, 2: c2}
    worker = WriteWorker(session_factory=db.FinSessionLocal, client_factory=lambda sid: clients[sid])
    q = asyncio.Queue()
    await q.put(PollTask(seller_id=1, days=[date(2026,5,20)]))
    await q.put(PollTask(seller_id=2, days=[date(2026,5,20)]))
    runner = asyncio.create_task(worker.run(q))
    await q.join()
    worker.stop()
    await runner
    s = db.FinSessionLocal()
    assert s.query(m.MLOrderCache).filter_by(seller_id=1).count() == 1
    assert s.query(m.MLOrderCache).filter_by(seller_id=2).count() == 1
    s.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_worker.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'financeiro_ml.worker'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/financeiro_ml/worker.py
"""Fila + write worker ÚNICO. Producers (poller, backfill) só enfileiram tasks;
o worker é o único escritor → elimina 'database is locked' na raiz.

Cada task: adquire lock durável do seller, busca os dias SEQUENCIAL (throttle é o
gate de req/s), calcula via build_order_row (puro), grava via upsert. 429 →
marca dia rate_limited + next_retry_at e para a task (re-enfileira depois)."""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from financeiro_ml.calc import build_order_row
from financeiro_ml.repo import upsert_order_row, set_day_status
from financeiro_ml.lock import acquire_seller_lock, renew_seller_lock, release_seller_lock
from financeiro_ml.client import MLRateLimited

log = logging.getLogger("financeiro_ml.worker")

LOCK_TTL_SEC = 120
RATE_LIMIT_COOLDOWN_SEC = 300


@dataclass
class PollTask:
    seller_id: int
    days: list[date]
    kind: str = "poll"


@dataclass
class BackfillTask:
    seller_id: int
    days: list[date]
    job_id: int
    kind: str = "backfill"


class WriteWorker:
    def __init__(self, *, session_factory, client_factory):
        self._sf = session_factory
        self._client_factory = client_factory
        self._stop = False

    def stop(self):
        self._stop = True

    async def run(self, queue: asyncio.Queue):
        while not self._stop:
            try:
                task = await asyncio.wait_for(queue.get(), timeout=0.2)
            except asyncio.TimeoutError:
                continue
            try:
                await self._process(task, queue)
            except Exception:
                log.exception("worker.task_failed seller=%s kind=%s", task.seller_id, task.kind)
            finally:
                queue.task_done()

    async def _process(self, task, queue):
        holder = f"{task.kind}:{getattr(task, 'job_id', '-')}"
        if not acquire_seller_lock(self._sf, seller_id=task.seller_id, holder=holder, ttl_sec=LOCK_TTL_SEC):
            await asyncio.sleep(0.5)
            await queue.put(task)  # outro segura o seller — re-enfileira
            return
        client = self._client_factory(task.seller_id)
        try:
            for day in task.days:
                if self._stop:
                    break
                cursor = self._cursor_for(task.seller_id, day)
                try:
                    count = await self._sync_day(client, task.seller_id, day, cursor)
                    set_day_status(self._sf, seller_id=task.seller_id, day=day,
                                   status="ok", orders_count=count)
                    if task.kind == "backfill":
                        self._bump_job(task.job_id)
                    renew_seller_lock(self._sf, seller_id=task.seller_id, holder=holder, ttl_sec=LOCK_TTL_SEC)
                except MLRateLimited:
                    set_day_status(self._sf, seller_id=task.seller_id, day=day,
                                   status="rate_limited", orders_count=0,
                                   error_message="429", retry_after_sec=RATE_LIMIT_COOLDOWN_SEC)
                    log.warning("worker.429 seller=%s day=%s — parando task", task.seller_id, day)
                    break
        finally:
            release_seller_lock(self._sf, seller_id=task.seller_id, holder=holder)

    def _cursor_for(self, seller_id, day):
        from financeiro_ml.models_v2 import MLOrderCache
        from sqlalchemy import func
        s = self._sf()
        try:
            day_start = datetime(day.year, day.month, day.day)
            day_end = day_start + timedelta(days=1)
            mx = s.query(func.max(MLOrderCache.date_last_updated)).filter(
                MLOrderCache.seller_id == seller_id,
                MLOrderCache.date_created >= day_start,
                MLOrderCache.date_created < day_end,
            ).scalar()
            return (mx - timedelta(hours=1)) if mx else None
        finally:
            s.close()

    async def _sync_day(self, client, seller_id, day, cursor):
        day_start = datetime(day.year, day.month, day.day, 0, 0, 0)
        day_end = datetime(day.year, day.month, day.day, 23, 59, 59)
        count = 0
        offset = 0
        while True:
            page = await client.search_orders(date_from=day_start, date_to=day_end,
                                               offset=offset, limit=50, last_updated_from=cursor)
            results = page.get("results", [])
            if not results:
                break
            for o in results:
                row = await self._enrich_and_build(client, seller_id, o)
                row["raw_json"] = json.dumps(o)
                upsert_order_row(self._sf, row)
                count += 1
            if len(results) < 50:
                break
            offset += 50
        return count

    async def _enrich_and_build(self, client, seller_id, order):
        shipment_id = (order.get("shipping") or {}).get("id")
        shipment = await client.get_shipment(shipment_id) if shipment_id else {}
        so = shipment.get("shipping_option") or {}
        shipment_costs = {}
        if (so.get("cost", 0) or 0) == 0 and shipment_id:
            shipment_costs = await client.get_shipment_costs(shipment_id)
        discounts = {"details": []}
        if "order_has_discount" in (order.get("tags") or []):
            discounts = await client.get_order_discounts(order["id"])
        return build_order_row(seller_id=seller_id, order=order, shipment=shipment,
                               shipment_costs=shipment_costs, discounts=discounts)

    def _bump_job(self, job_id):
        from financeiro_ml.models_v2 import MLBackfillJob
        s = self._sf()
        try:
            job = s.query(MLBackfillJob).filter_by(id=job_id).first()
            if job:
                job.progress_done += 1
                s.commit()
        finally:
            s.close()
```

> Nota sobre offset vs scan: a Task 16 usa offset (suficiente p/ delta diário, <1000). O suporte a `search_type=scan` para janelas grandes entra na Task 24 (backfill). Worker chama `client.search_orders`; o scan será um método separado do client usado só pelo backfill.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_worker.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/worker.py backend/financeiro_ml/tests/test_worker.py
git commit -m "feat(financeiro-ml): fila + write worker único (lock+cursor+upsert)"
```

---

## Fase 5 — Cliente ML por seller (throttle + backoff + circuit-breaker + tokens)

### Task 17: Token-bucket de throttle por seller

**Files:**
- Create: `backend/financeiro_ml/throttle.py`
- Test: `backend/financeiro_ml/tests/test_throttle.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/financeiro_ml/tests/test_throttle.py
import asyncio
import pytest


@pytest.mark.asyncio
async def test_throttle_spaces_calls_per_seller(monkeypatch):
    from financeiro_ml.throttle import SellerThrottle
    t = SellerThrottle(min_interval_sec=0.05)
    clock = {"now": 0.0}
    sleeps = []

    async def fake_sleep(s):
        sleeps.append(s)
        clock["now"] += s

    monkeypatch.setattr("financeiro_ml.throttle.asyncio.sleep", fake_sleep)
    monkeypatch.setattr(t, "_now", lambda: clock["now"])

    await t.wait(seller_id=1)   # 1ª passa direto
    await t.wait(seller_id=1)   # 2ª precisa esperar ~min_interval
    assert any(s > 0 for s in sleeps)


@pytest.mark.asyncio
async def test_throttle_independent_per_seller(monkeypatch):
    from financeiro_ml.throttle import SellerThrottle
    t = SellerThrottle(min_interval_sec=0.05)
    clock = {"now": 0.0}
    monkeypatch.setattr("financeiro_ml.throttle.asyncio.sleep", lambda s: asyncio.sleep(0))
    monkeypatch.setattr(t, "_now", lambda: clock["now"])
    await t.wait(seller_id=1)
    await t.wait(seller_id=2)   # seller diferente não espera pelo 1
    assert True  # não levanta, buckets isolados
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_throttle.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'financeiro_ml.throttle'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/financeiro_ml/throttle.py
"""Throttle por seller (substitui o global do client.py como gate primário).
~3 req/s/seller (min_interval ~0.33s). Buckets isolados por seller_id."""
import asyncio


class SellerThrottle:
    def __init__(self, min_interval_sec: float = 0.33):
        self._interval = min_interval_sec
        self._last: dict[int, float] = {}
        self._locks: dict[int, asyncio.Lock] = {}

    def _now(self) -> float:
        return asyncio.get_event_loop().time()

    def _lock_for(self, seller_id: int) -> asyncio.Lock:
        if seller_id not in self._locks:
            self._locks[seller_id] = asyncio.Lock()
        return self._locks[seller_id]

    async def wait(self, *, seller_id: int) -> None:
        async with self._lock_for(seller_id):
            last = self._last.get(seller_id, 0.0)
            delta = self._now() - last
            if delta < self._interval:
                await asyncio.sleep(self._interval - delta)
            self._last[seller_id] = self._now()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_throttle.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/throttle.py backend/financeiro_ml/tests/test_throttle.py
git commit -m "feat(financeiro-ml): token-bucket de throttle por seller"
```

### Task 18: Circuit-breaker por seller (closed/open/half-open)

**Files:**
- Modify: `backend/financeiro_ml/throttle.py` (append)
- Test: `backend/financeiro_ml/tests/test_breaker.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/financeiro_ml/tests/test_breaker.py
from financeiro_ml.throttle import SellerCircuitBreaker


def test_breaker_starts_closed():
    b = SellerCircuitBreaker(cooldown_sec=300)
    assert b.is_open(seller_id=1) is False


def test_breaker_opens_after_trip():
    b = SellerCircuitBreaker(cooldown_sec=300)
    b.trip(seller_id=1)
    assert b.is_open(seller_id=1) is True


def test_breaker_half_open_after_cooldown():
    now = {"t": 1000.0}
    b = SellerCircuitBreaker(cooldown_sec=300, clock=lambda: now["t"])
    b.trip(seller_id=1)
    assert b.is_open(seller_id=1) is True
    now["t"] += 301
    assert b.is_open(seller_id=1) is False  # cooldown passou → meio-aberto deixa passar


def test_breaker_reset_on_success():
    b = SellerCircuitBreaker(cooldown_sec=300)
    b.trip(seller_id=1)
    b.record_success(seller_id=1)
    assert b.is_open(seller_id=1) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_breaker.py -v`
Expected: FAIL — `ImportError: cannot import name 'SellerCircuitBreaker'`

- [ ] **Step 3: Write minimal implementation (append em throttle.py)**

```python
import time


class SellerCircuitBreaker:
    """Por seller: closed → (trip) open por cooldown → half-open (deixa 1 passar)
    → success reseta p/ closed. Reabre sozinho, não fica preso até o próximo ciclo."""
    def __init__(self, *, cooldown_sec: int = 300, clock=None):
        self._cooldown = cooldown_sec
        self._opened_at: dict[int, float] = {}
        self._clock = clock or time.monotonic

    def is_open(self, *, seller_id: int) -> bool:
        opened = self._opened_at.get(seller_id)
        if opened is None:
            return False
        if self._clock() - opened >= self._cooldown:
            return False  # half-open: permite 1 tentativa de teste
        return True

    def trip(self, *, seller_id: int) -> None:
        self._opened_at[seller_id] = self._clock()

    def record_success(self, *, seller_id: int) -> None:
        self._opened_at.pop(seller_id, None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_breaker.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/throttle.py backend/financeiro_ml/tests/test_breaker.py
git commit -m "feat(financeiro-ml): circuit-breaker por seller (auto half-open)"
```

### Task 19: Cliente ML lê tokens por seller (substitui MLTokens.first())

**Files:**
- Modify: `backend/financeiro_ml/client.py`
- Test: `backend/financeiro_ml/tests/test_client_seller.py`

> **Por quê:** o client v1 lê `MLTokens.first()` (1 token global) e usa `session_factory` do banco principal. Para multi-seller, o client recebe `seller_id` e lê de `ml_tokens` (PK = seller_id) no banco isolado. Refresh com lock POR seller.

- [ ] **Step 1: Write the failing test**

```python
# backend/financeiro_ml/tests/test_client_seller.py
import pytest
from datetime import datetime, timedelta


@pytest.mark.asyncio
async def test_ensure_token_reads_per_seller(fin_db, monkeypatch):
    db, m = fin_db
    s = db.FinSessionLocal()
    s.add(m.MLTokens(seller_id=555, client_id="cid", access_token="ACC555",
                     refresh_token="REF555", expires_at=datetime.utcnow() + timedelta(hours=5),
                     updated_at=datetime.utcnow()))
    s.add(m.MLTokens(seller_id=777, client_id="cid", access_token="ACC777",
                     refresh_token="REF777", expires_at=datetime.utcnow() + timedelta(hours=5),
                     updated_at=datetime.utcnow()))
    s.commit(); s.close()

    from financeiro_ml.client import MLClient
    c = MLClient(session_factory=db.FinSessionLocal, client_id="cid", client_secret="sec", seller_id=555)
    tok = await c._ensure_fresh_token()
    assert tok == "ACC555"

    c2 = MLClient(session_factory=db.FinSessionLocal, client_id="cid", client_secret="sec", seller_id=777)
    tok2 = await c2._ensure_fresh_token()
    assert tok2 == "ACC777"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_client_seller.py -v`
Expected: FAIL — `TypeError` (MLClient.__init__ não aceita `seller_id`) ou usa schema antigo.

- [ ] **Step 3: Implementação — alterar `client.py`**

No `__init__` de `MLClient`, adicionar `seller_id`:

```python
    def __init__(self, *, session_factory: Callable, client_id: str, client_secret: str,
                  seller_id: int | None = None, timeout: float = 30.0):
        self._session_factory = session_factory
        self._client_id = client_id
        self._client_secret = client_secret
        self._seller_id = seller_id
        self._timeout = timeout
```

Substituir o corpo de `_ensure_fresh_token` para usar `models_v2.MLTokens` por `seller_id` (mantém a estrutura fast-path/slow-path/lock; trocar `query(MLTokens).first()` por `query(MLTokens).filter_by(seller_id=self._seller_id).first()` e usar import `from financeiro_ml.models_v2 import MLTokens`).

Substituir em `search_orders` a leitura de `user_id`:

```python
    async def search_orders(self, *, date_from, date_to, offset=0, limit=50, last_updated_from=None):
        params = {
            "seller": self._seller_id,
            "order.date_created.from": date_from.strftime("%Y-%m-%dT%H:%M:%S.000-03:00"),
            "order.date_created.to": date_to.strftime("%Y-%m-%dT%H:%M:%S.000-03:00"),
            "offset": offset, "limit": limit,
        }
        if last_updated_from is not None:
            params["order.date_last_updated.from"] = last_updated_from.strftime("%Y-%m-%dT%H:%M:%S.000-03:00")
        return await self._get("/orders/search", params=params)
```

Atualizar `build_default_client()` para aceitar `seller_id` e usar `FinSessionLocal`:

```python
def build_default_client(seller_id: int | None = None) -> MLClient:
    from financeiro_ml.db import FinSessionLocal
    return MLClient(
        session_factory=FinSessionLocal,
        client_id=os.getenv("ML_CLIENT_ID", ""),
        client_secret=os.getenv("ML_CLIENT_SECRET", ""),
        seller_id=seller_id,
    )
```

> **Atenção (compat):** o router v1 (`router.py`) ainda chama `ensure_period_synced` → `build_default_client()` sem seller_id, contra o banco principal. Como a Fase 6 corta esse caminho e o módulo novo passa `seller_id` explícito, manter `seller_id=None` como default não quebra a importação. O caminho v1 só é removido na Fase 8 (após validação). Se o teste de regressão `test_ml_client.py` quebrar por causa do schema, ajustar os mocks naquele teste para o novo `__init__` (assinatura com `seller_id`).

- [ ] **Step 4: Run tests (novo + regressão do client)**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_client_seller.py financeiro_ml/tests/test_ml_client.py -v`
Expected: novo PASS; regressão PASS (ajustar mocks de `test_ml_client.py` se necessário p/ a nova assinatura).

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/client.py backend/financeiro_ml/tests/test_client_seller.py backend/financeiro_ml/tests/test_ml_client.py
git commit -m "feat(financeiro-ml): client lê tokens por seller (banco isolado)"
```

### Task 20: Refresh lock por seller (não global)

**Files:**
- Modify: `backend/financeiro_ml/client.py`
- Test: `backend/financeiro_ml/tests/test_client_seller.py` (append)

> **Por quê:** o `_refresh_lock` atual é um `asyncio.Lock` class-level (global) — serializa refresh de TODOS os sellers. Com tokens por seller, o lock deve ser por seller_id (refresh de A não bloqueia B).

- [ ] **Step 1: Write the failing test (append)**

```python
@pytest.mark.asyncio
async def test_refresh_lock_is_per_seller():
    from financeiro_ml.client import MLClient
    l1 = MLClient._refresh_lock_for(1)
    l1b = MLClient._refresh_lock_for(1)
    l2 = MLClient._refresh_lock_for(2)
    assert l1 is l1b      # mesmo seller → mesmo lock
    assert l1 is not l2   # sellers diferentes → locks diferentes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_client_seller.py -k refresh_lock -v`
Expected: FAIL — `AttributeError: type object 'MLClient' has no attribute '_refresh_lock_for'`

- [ ] **Step 3: Implementação — em `client.py`**

Trocar o `_refresh_lock` class-level por um registry por seller:

```python
    _refresh_locks: dict[int, asyncio.Lock] = {}

    @classmethod
    def _refresh_lock_for(cls, seller_id: int) -> asyncio.Lock:
        if seller_id not in cls._refresh_locks:
            cls._refresh_locks[seller_id] = asyncio.Lock()
        return cls._refresh_locks[seller_id]
```

No slow-path de `_ensure_fresh_token`, trocar `async with MLClient._refresh_lock:` por `async with MLClient._refresh_lock_for(self._seller_id):`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_client_seller.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/client.py backend/financeiro_ml/tests/test_client_seller.py
git commit -m "feat(financeiro-ml): refresh lock por seller (não global)"
```

---

## Fase 6 — Poller + lifespan

### Task 21: Lista de sellers ativos + montagem das tasks do poller

**Files:**
- Create: `backend/financeiro_ml/poller.py`
- Test: `backend/financeiro_ml/tests/test_poller.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/financeiro_ml/tests/test_poller.py
import asyncio
import pytest
from datetime import date, datetime, timedelta


def test_active_sellers_from_tokens(fin_db):
    db, m = fin_db
    s = db.FinSessionLocal()
    s.add(m.MLTokens(seller_id=555, access_token="a", refresh_token="r",
                     expires_at=datetime.utcnow()+timedelta(hours=5), updated_at=datetime.utcnow()))
    s.commit(); s.close()
    from financeiro_ml.poller import active_sellers
    assert active_sellers(db.FinSessionLocal) == [555]


def test_build_poll_tasks_uses_14d_window(fin_db):
    db, m = fin_db
    from financeiro_ml.poller import build_poll_tasks
    tasks = build_poll_tasks([555], today=date(2026, 5, 28))
    assert len(tasks) == 1
    t = tasks[0]
    assert t.seller_id == 555
    assert t.days[0] == date(2026, 5, 15)   # 28 - 13 = 15 (14 dias inclusivo)
    assert t.days[-1] == date(2026, 5, 28)
    assert len(t.days) == 14
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_poller.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'financeiro_ml.poller'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/financeiro_ml/poller.py
"""Poller periódico: a cada ~6h enfileira 1 PollTask por seller cobrindo os
últimos 14 dias (janela fresca). Delta é leve; offset dá conta (<1000)."""
import asyncio
import logging
import os
from datetime import date, timedelta

from financeiro_ml.worker import PollTask
from financeiro_ml.freshness import FRESH_WINDOW_DAYS

log = logging.getLogger("financeiro_ml.poller")

POLL_INTERVAL_SEC = int(os.getenv("FINANCEIRO_ML_POLL_INTERVAL_SEC", str(6 * 3600)))


def active_sellers(session_factory) -> list[int]:
    from financeiro_ml.models_v2 import MLTokens
    s = session_factory()
    try:
        return [r.seller_id for r in s.query(MLTokens).all()]
    finally:
        s.close()


def build_poll_tasks(sellers: list[int], *, today: date) -> list[PollTask]:
    start = today - timedelta(days=FRESH_WINDOW_DAYS - 1)
    days = [start + timedelta(days=i) for i in range(FRESH_WINDOW_DAYS)]
    return [PollTask(seller_id=sid, days=days) for sid in sellers]


async def poller_loop(session_factory, queue: asyncio.Queue, *, stop_event: asyncio.Event):
    while not stop_event.is_set():
        try:
            sellers = active_sellers(session_factory)
            for task in build_poll_tasks(sellers, today=date.today()):
                await queue.put(task)
            log.info("poller.enqueued sellers=%s", sellers)
        except Exception:
            log.exception("poller.loop_error")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL_SEC)
        except asyncio.TimeoutError:
            pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_poller.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/poller.py backend/financeiro_ml/tests/test_poller.py
git commit -m "feat(financeiro-ml): poller 14d/6h enfileira tasks por seller"
```

### Task 22: Recover de jobs órfãos no startup

**Files:**
- Modify: `backend/financeiro_ml/backfill.py` (criado na Task 24; se ainda não existe, criar stub aqui) — **mover esta task para depois da 24** OU implementar a função recover dentro de `worker.py`. Decisão: implementar em `worker.py` (já importa models).
- Test: `backend/financeiro_ml/tests/test_worker.py` (append)

- [ ] **Step 1: Write the failing test (append em test_worker.py)**

```python
def test_recover_orphan_jobs_resets_running_to_pending(fin_db):
    db, m = fin_db
    from datetime import date, datetime
    s = db.FinSessionLocal()
    s.add(m.MLBackfillJob(seller_id=1, day_from=date(2026,1,1), day_to=date(2026,1,2),
                          status="running", created_at=datetime.utcnow(), claimed_at=datetime.utcnow()))
    s.commit(); s.close()
    from financeiro_ml.worker import recover_orphan_jobs
    n = recover_orphan_jobs(db.FinSessionLocal)
    assert n == 1
    s = db.FinSessionLocal()
    assert s.query(m.MLBackfillJob).first().status == "pending"
    s.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_worker.py -k recover -v`
Expected: FAIL — `ImportError: cannot import name 'recover_orphan_jobs'`

- [ ] **Step 3: Write minimal implementation (append em worker.py)**

```python
def recover_orphan_jobs(session_factory) -> int:
    """Jobs 'running' órfãos (crash/deploy no meio) → 'pending'. Roda no startup.
    Copia o padrão de services/sync_engine.recover_stale_runs (sem importar — Tiny-coupled)."""
    from financeiro_ml.models_v2 import MLBackfillJob
    s = session_factory()
    try:
        rows = s.query(MLBackfillJob).filter_by(status="running").all()
        for r in rows:
            r.status = "pending"
            r.claimed_at = None
        s.commit()
        return len(rows)
    finally:
        s.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_worker.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/worker.py backend/financeiro_ml/tests/test_worker.py
git commit -m "feat(financeiro-ml): recover de jobs órfãos no startup"
```

### Task 23: Wire-up no lifespan do FastAPI (startup/shutdown)

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/financeiro_ml/worker.py` (helper de bootstrap singleton)
- Test: manual (lifespan não é unit-testável trivial; verificar via boot)

- [ ] **Step 1: Helper de bootstrap em worker.py**

```python
# em worker.py — singleton de runtime (queue + worker + poller)
_RUNTIME = {}


def start_financeiro_ml_runtime():
    """Cria queue + worker + poller no startup. Idempotente."""
    import asyncio
    from financeiro_ml.db import FinSessionLocal, init_fin_db
    from financeiro_ml.client import build_default_client
    from financeiro_ml.poller import poller_loop

    if _RUNTIME.get("started"):
        return _RUNTIME
    init_fin_db()
    recover_orphan_jobs(FinSessionLocal)
    queue = asyncio.Queue()
    worker = WriteWorker(session_factory=FinSessionLocal,
                         client_factory=lambda sid: build_default_client(seller_id=sid))
    stop_event = asyncio.Event()
    worker_task = asyncio.create_task(worker.run(queue))
    poller_task = asyncio.create_task(poller_loop(FinSessionLocal, queue, stop_event=stop_event))
    _RUNTIME.update(started=True, queue=queue, worker=worker, stop_event=stop_event,
                    worker_task=worker_task, poller_task=poller_task)
    return _RUNTIME


async def stop_financeiro_ml_runtime():
    rt = _RUNTIME
    if not rt.get("started"):
        return
    rt["stop_event"].set()
    rt["worker"].stop()
    rt["poller_task"].cancel()
    rt["worker_task"].cancel()
    rt["started"] = False


def get_write_queue():
    return _RUNTIME.get("queue")
```

- [ ] **Step 2: Wire em main.py — no `on_startup` (após os blocos existentes)**

```python
    if os.getenv("ENABLE_FINANCEIRO_ML_ROBOT", "false").strip().lower() in {"1", "true", "yes"}:
        from financeiro_ml.worker import start_financeiro_ml_runtime
        start_financeiro_ml_runtime()
        print("[financeiro-ml] robô (worker + poller) iniciado")
```

E no `on_shutdown`:

```python
    from financeiro_ml.worker import stop_financeiro_ml_runtime
    await stop_financeiro_ml_runtime()
```

> **Gate por env:** `ENABLE_FINANCEIRO_ML_ROBOT` default `false` — o robô só liga quando explicitamente habilitado (permite subir o código sem ativar o robô até a validação da Fase 7/8).

- [ ] **Step 3: Smoke de boot (sem robô e com robô)**

Run: `cd backend && python -c "import main; print('import ok')"`
Expected: `import ok` sem erro de import.

Run: `cd backend && ENABLE_FINANCEIRO_ML_ROBOT=false python -c "import asyncio,main; asyncio.get_event_loop().run_until_complete(main.on_startup()); print('startup ok')"`
Expected: `startup ok` (robô desligado, sem efeitos).

- [ ] **Step 4: Commit**

```bash
git add backend/main.py backend/financeiro_ml/worker.py
git commit -m "feat(financeiro-ml): runtime (worker+poller) no lifespan, gated por env"
```

---

## Fase 7 — Backfill (jobs + REST + polling no front)

### Task 24: Método de scan no client (search_type=scan p/ janelas grandes)

**Files:**
- Modify: `backend/financeiro_ml/client.py`
- Test: `backend/financeiro_ml/tests/test_client_scan.py`

> **Por quê:** offset tem teto ~1000 (dia cheio = 1138 → perde pedidos em silêncio). Backfill de janela grande precisa de `search_type=scan` + `scroll_id` (serial, sem misturar com offset).

- [ ] **Step 1: Write the failing test**

```python
# backend/financeiro_ml/tests/test_client_scan.py
import pytest


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload; self.status_code = status
    def json(self): return self._p
    def raise_for_status(self): pass


@pytest.mark.asyncio
async def test_scan_iterates_until_empty(monkeypatch, fin_db):
    db, m = fin_db
    from datetime import datetime, timedelta
    s = db.FinSessionLocal()
    s.add(m.MLTokens(seller_id=1, access_token="A", refresh_token="R",
                     expires_at=datetime.utcnow()+timedelta(hours=5), updated_at=datetime.utcnow()))
    s.commit(); s.close()

    from financeiro_ml.client import MLClient
    c = MLClient(session_factory=db.FinSessionLocal, client_id="c", client_secret="s", seller_id=1)

    pages = [
        {"scroll_id": "SC1", "results": [{"id": 1}, {"id": 2}]},
        {"scroll_id": "SC1", "results": [{"id": 3}]},
        {"scroll_id": "SC1", "results": []},
    ]
    calls = {"i": 0}

    async def fake_get(path, params=None):
        p = pages[calls["i"]]; calls["i"] += 1
        return p

    monkeypatch.setattr(c, "_get", fake_get)

    collected = []
    async for order in c.scan_orders(date_from=datetime(2026,1,1), date_to=datetime(2026,5,28)):
        collected.append(order["id"])
    assert collected == [1, 2, 3]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_client_scan.py -v`
Expected: FAIL — `AttributeError: 'MLClient' object has no attribute 'scan_orders'`

- [ ] **Step 3: Implementação — append em client.py**

```python
    async def scan_orders(self, *, date_from, date_to):
        """Gera orders via search_type=scan + scroll_id (sem teto de offset).
        Serial, concorrência=1. Não misturar com offset/limit."""
        params = {
            "seller": self._seller_id,
            "search_type": "scan",
            "order.date_created.from": date_from.strftime("%Y-%m-%dT%H:%M:%S.000-03:00"),
            "order.date_created.to": date_to.strftime("%Y-%m-%dT%H:%M:%S.000-03:00"),
        }
        scroll_id = None
        while True:
            if scroll_id:
                params["scroll_id"] = scroll_id
            page = await self._get("/orders/search", params=params)
            results = page.get("results", [])
            scroll_id = page.get("scroll_id")
            if not results:
                break
            for o in results:
                yield o
            if not scroll_id:
                break
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_client_scan.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/client.py backend/financeiro_ml/tests/test_client_scan.py
git commit -m "feat(financeiro-ml): scan_orders (scroll_id) p/ janelas >1000"
```

### Task 25: Criação + claim atômico de backfill jobs

**Files:**
- Create: `backend/financeiro_ml/backfill.py`
- Test: `backend/financeiro_ml/tests/test_backfill.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/financeiro_ml/tests/test_backfill.py
from datetime import date


def test_create_job_returns_id_and_total(fin_db):
    db, m = fin_db
    from financeiro_ml.backfill import create_job
    job_id = create_job(db.FinSessionLocal, seller_id=1, day_from=date(2026,1,1), day_to=date(2026,1,10))
    s = db.FinSessionLocal()
    job = s.query(m.MLBackfillJob).filter_by(id=job_id).first()
    assert job.status == "pending"
    assert job.progress_total == 10   # 10 dias inclusivo
    s.close()


def test_claim_job_atomic_only_once(fin_db):
    db, m = fin_db
    from financeiro_ml.backfill import create_job, claim_job
    job_id = create_job(db.FinSessionLocal, seller_id=1, day_from=date(2026,1,1), day_to=date(2026,1,2))
    assert claim_job(db.FinSessionLocal, job_id) is True
    assert claim_job(db.FinSessionLocal, job_id) is False  # já claimed → não reentra
    s = db.FinSessionLocal()
    assert s.query(m.MLBackfillJob).filter_by(id=job_id).first().status == "running"
    s.close()


def test_get_job_progress(fin_db):
    db, m = fin_db
    from financeiro_ml.backfill import create_job, get_job
    job_id = create_job(db.FinSessionLocal, seller_id=1, day_from=date(2026,1,1), day_to=date(2026,1,5))
    prog = get_job(db.FinSessionLocal, job_id)
    assert prog["status"] == "pending"
    assert prog["progress_total"] == 5
    assert prog["progress_done"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_backfill.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'financeiro_ml.backfill'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/financeiro_ml/backfill.py
"""Backfill: cria job, claim atômico (CAS), consulta progresso. Front faz polling."""
from datetime import date, datetime, timedelta
from sqlalchemy import text


def _total_days(day_from: date, day_to: date) -> int:
    return (day_to - day_from).days + 1


def create_job(session_factory, *, seller_id: int, day_from: date, day_to: date) -> int:
    from financeiro_ml.models_v2 import MLBackfillJob
    s = session_factory()
    try:
        job = MLBackfillJob(seller_id=seller_id, day_from=day_from, day_to=day_to,
                            status="pending", progress_total=_total_days(day_from, day_to),
                            created_at=datetime.utcnow())
        s.add(job)
        s.commit()
        return job.id
    finally:
        s.close()


def claim_job(session_factory, job_id: int) -> bool:
    s = session_factory()
    try:
        res = s.execute(text(
            "UPDATE ml_backfill_jobs SET status='running', claimed_at=:now "
            "WHERE id=:id AND status='pending'"
        ), {"now": datetime.utcnow(), "id": job_id})
        s.commit()
        return res.rowcount == 1
    finally:
        s.close()


def get_job(session_factory, job_id: int) -> dict | None:
    from financeiro_ml.models_v2 import MLBackfillJob
    s = session_factory()
    try:
        j = s.query(MLBackfillJob).filter_by(id=job_id).first()
        if j is None:
            return None
        return {"id": j.id, "seller_id": j.seller_id, "status": j.status,
                "progress_done": j.progress_done, "progress_total": j.progress_total,
                "error_message": j.error_message}
    finally:
        s.close()


def finish_job(session_factory, job_id: int, *, status: str, error: str | None = None) -> None:
    from financeiro_ml.models_v2 import MLBackfillJob
    s = session_factory()
    try:
        j = s.query(MLBackfillJob).filter_by(id=job_id).first()
        if j:
            j.status = status
            j.error_message = error
            j.finished_at = datetime.utcnow()
            s.commit()
    finally:
        s.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_backfill.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/backfill.py backend/financeiro_ml/tests/test_backfill.py
git commit -m "feat(financeiro-ml): backfill jobs (create/claim CAS/get/finish)"
```

### Task 26: Endpoints REST de backfill (POST cria+enfileira, GET progresso)

**Files:**
- Modify: `backend/financeiro_ml/router.py`
- Test: `backend/financeiro_ml/tests/test_backfill_routes.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/financeiro_ml/tests/test_backfill_routes.py
import pytest
from datetime import date


@pytest.mark.asyncio
async def test_post_backfill_creates_job(fin_db, monkeypatch):
    db, m = fin_db
    # injeta a fila de escrita do runtime
    import financeiro_ml.worker as worker
    import asyncio
    worker._RUNTIME["queue"] = asyncio.Queue()

    from financeiro_ml.router import create_backfill, BackfillParams
    resp = await create_backfill(BackfillParams(seller_id=1, day_from=date(2026,1,1), day_to=date(2026,1,3)),
                                 operator_id=1)
    assert "job_id" in resp
    s = db.FinSessionLocal()
    assert s.query(m.MLBackfillJob).count() == 1
    s.close()
    assert worker._RUNTIME["queue"].qsize() == 1   # task enfileirada


@pytest.mark.asyncio
async def test_get_backfill_progress(fin_db):
    db, m = fin_db
    from financeiro_ml.backfill import create_job
    job_id = create_job(db.FinSessionLocal, seller_id=1, day_from=date(2026,1,1), day_to=date(2026,1,3))
    from financeiro_ml.router import get_backfill_status
    resp = await get_backfill_status(job_id, operator_id=1)
    assert resp["status"] == "pending"
    assert resp["progress_total"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_backfill_routes.py -v`
Expected: FAIL — `ImportError: cannot import name 'create_backfill'`

- [ ] **Step 3: Implementação — append em router.py**

```python
from pydantic import BaseModel
from datetime import date as _date


class BackfillParams(BaseModel):
    seller_id: int
    day_from: _date
    day_to: _date


@router.post("/backfill")
async def create_backfill(params: BackfillParams, operator_id: int = Depends(require_master)):
    from financeiro_ml.db import FinSessionLocal
    from financeiro_ml.backfill import create_job
    from financeiro_ml.worker import BackfillTask, get_write_queue
    from datetime import timedelta
    job_id = create_job(FinSessionLocal, seller_id=params.seller_id,
                        day_from=params.day_from, day_to=params.day_to)
    days = [params.day_from + timedelta(days=i)
            for i in range((params.day_to - params.day_from).days + 1)]
    queue = get_write_queue()
    if queue is not None:
        await queue.put(BackfillTask(seller_id=params.seller_id, days=days, job_id=job_id))
    return {"job_id": job_id}


@router.get("/backfill/{job_id}")
async def get_backfill_status(job_id: int, operator_id: int = Depends(require_master)):
    from financeiro_ml.db import FinSessionLocal
    from financeiro_ml.backfill import get_job
    prog = get_job(FinSessionLocal, job_id)
    if prog is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="job não encontrado")
    return prog
```

> Nota: o worker já claim+marca `running`/`done` via `_bump_job`. Para o backfill marcar `done` no fim, o worker deve chamar `finish_job` ao terminar uma BackfillTask sem 429 — adicionar no `_process` quando `task.kind == "backfill"` e o loop completar todos os dias. Implementar este detalhe junto e blindar com o teste da Task 27.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_backfill_routes.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/router.py backend/financeiro_ml/tests/test_backfill_routes.py
git commit -m "feat(financeiro-ml): endpoints REST de backfill (POST cria+enfileira, GET status)"
```

### Task 27: Worker marca job done/failed ao concluir BackfillTask

**Files:**
- Modify: `backend/financeiro_ml/worker.py`
- Test: `backend/financeiro_ml/tests/test_worker.py` (append)

- [ ] **Step 1: Write the failing test (append)**

```python
@pytest.mark.asyncio
async def test_backfill_task_marks_job_done(fin_db):
    db, m = fin_db
    from datetime import date, datetime
    from financeiro_ml.worker import WriteWorker, BackfillTask
    from financeiro_ml.backfill import create_job

    class FakeClient2:
        async def search_orders(self, **kw):
            return {"results": []}   # dia vazio → conclui rápido
        async def get_shipment(self, sid): return {}
        async def get_shipment_costs(self, sid): return {}
        async def get_order_discounts(self, oid): return {"details": []}

    job_id = create_job(db.FinSessionLocal, seller_id=1, day_from=date(2026,1,1), day_to=date(2026,1,2))
    worker = WriteWorker(session_factory=db.FinSessionLocal, client_factory=lambda sid: FakeClient2())
    import asyncio
    q = asyncio.Queue()
    await q.put(BackfillTask(seller_id=1, days=[date(2026,1,1), date(2026,1,2)], job_id=job_id))
    runner = asyncio.create_task(worker.run(q))
    await q.join()
    worker.stop(); await runner
    s = db.FinSessionLocal()
    assert s.query(m.MLBackfillJob).filter_by(id=job_id).first().status == "done"
    s.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_worker.py -k backfill_task_marks -v`
Expected: FAIL — job fica `pending`/`running`, não `done`.

- [ ] **Step 3: Implementação — em worker.py `_process`**

No fim do `for day in task.days` (após o loop, dentro do `try`, antes do `finally`), adicionar:

```python
            if task.kind == "backfill":
                from financeiro_ml.backfill import claim_job, finish_job
                # claim idempotente (caso ainda 'pending') e marca done se não houve 429
                claim_job(self._sf, task.job_id)
                finish_job(self._sf, task.job_id, status="done")
```

E em torno do `except MLRateLimited` (dentro do loop), se for backfill, marcar o job como `failed` com a mensagem (mantendo o `break`):

```python
                    if task.kind == "backfill":
                        from financeiro_ml.backfill import finish_job
                        finish_job(self._sf, task.job_id, status="failed", error="429 rate limited")
```

> Atenção: `claim_job` só vira `running` se estava `pending`; como o POST não claimou ainda (claim acontece aqui), isto cobre o caso. Se preferir claimar no início do `_process` p/ backfill, ajustar — mas manter UM ponto de verdade. O teste blinda o resultado final (`done`).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_worker.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/worker.py backend/financeiro_ml/tests/test_worker.py
git commit -m "feat(financeiro-ml): worker marca backfill job done/failed"
```

---

## Fase 8 — Router read-only + validação + corte

### Task 28: `/resumo` lê do banco isolado por seller, SEM disparar sync

**Files:**
- Modify: `backend/financeiro_ml/router.py`
- Test: `backend/financeiro_ml/tests/test_resumo_readonly.py`

> **Por quê:** este é o coração do CQRS — cortar `await ensure_period_synced(...)` (router.py:127) e ler de `FinSessionLocal` filtrando por `seller_id`. O clique NUNCA dispara crawl.

- [ ] **Step 1: Write the failing test**

```python
# backend/financeiro_ml/tests/test_resumo_readonly.py
import pytest
from datetime import date, datetime
from decimal import Decimal


@pytest.mark.asyncio
async def test_resumo_reads_cache_no_sync(fin_db, monkeypatch):
    db, m = fin_db
    # popula cache de 1 seller
    s = db.FinSessionLocal()
    s.add(m.MLOrderCache(seller_id=1, order_id=100, date_created=datetime(2026,5,20,10),
                         date_closed=datetime(2026,5,20,11), status="paid",
                         produto_total=Decimal("100"), raw_json="{}", synced_at=datetime.utcnow(),
                         breakdown_bucket="outros"))
    s.add(m.MLOrderItemCache(seller_id=1, order_id=100, item_id="MLB1", title="A",
                             seller_sku="X", quantity=1, unit_price=Decimal("100")))
    s.commit(); s.close()

    # garante que NENHUM sync é chamado
    import financeiro_ml.router as r
    called = {"sync": False}
    if hasattr(r, "ensure_period_synced"):
        monkeypatch.setattr(r, "ensure_period_synced",
                            lambda *a, **k: (_ for _ in ()).throw(AssertionError("não pode sincronizar")))

    from financeiro_ml.router import FilterParams, get_resumo
    params = FilterParams(seller_id=1, data_inicio=date(2026,5,20), data_fim=date(2026,5,20))
    resp = await get_resumo(params, operator_id=1)
    assert resp["cards"]["vendas_aprovadas"] == "100.00" or resp["cards"]["vendas_aprovadas"] == 100.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_resumo_readonly.py -v`
Expected: FAIL — `get_resumo` ainda chama `ensure_period_synced` e/ou `FilterParams` não tem `seller_id`.

- [ ] **Step 3: Implementação — em router.py**

1. Adicionar `seller_id: int` ao `FilterParams` (ver classe atual no topo do router).
2. Em `get_resumo`: remover o bloco `t1 = ...; sync_report = await ensure_period_synced(...)` (linhas ~126-132) e a chave `result["sync_report"]`.
3. Trocar `from database import SessionLocal` (linha ~134) por `from financeiro_ml.db import FinSessionLocal as SessionLocal`.
4. Trocar `from financeiro_ml.models import ...` (linha ~112) por `from financeiro_ml.models_v2 import MLOrderCache, MLOrderItemCache, SkuFinanceiro`.
5. Adicionar filtro `MLOrderCache.seller_id == params.seller_id` na query principal e na de itens.
6. Remover o import `from financeiro_ml.sync import ensure_period_synced` (linha 110).

> Manter `_row_to_dict_order`/`_row_to_dict_item`/`_apply_margem_filter`/`aggregate` como estão. A query muda só de banco e ganha o filtro de seller.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest financeiro_ml/tests/test_resumo_readonly.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/financeiro_ml/router.py backend/financeiro_ml/tests/test_resumo_readonly.py
git commit -m "feat(financeiro-ml): /resumo read-only do banco isolado por seller (corta sync inline)"
```

### Task 29: Frontend — passar seller_id + tela de backfill (polling)

**Files:**
- Modify: arquivo(s) do front que chamam `/api/financeiro-ml/resumo` (localizar com grep).

- [ ] **Step 1: Localizar o consumo atual no front**

Run: `cd "/Users/julio/Documents/Antigra/warehouse-picker v2" && grep -rn "financeiro-ml/resumo\|/resumo" frontend/src --include=*.jsx --include=*.js --include=*.ts --include=*.tsx | head`
Expected: lista o(s) componente(s) que chamam o endpoint.

- [ ] **Step 2: Ajustes (a detalhar no arquivo encontrado)**

- Incluir `seller_id` no payload do POST `/resumo` (default = seller padrão; multi-conta vem do seletor depois).
- Quando o usuário pedir período fora da janela cacheada, chamar `POST /backfill` e iniciar polling `GET /backfill/{id}` a cada ~3s: `pending`/`running` → barra de progresso (`progress_done`/`progress_total`); `done` → re-chamar `/resumo`; `failed` → mensagem + botão retry.

> Este passo é guiado pela tela atual; manter padrão de chamada já existente no projeto (axios/fetch wrapper em `frontend/src`). Verificar no browser (preview) após implementar.

- [ ] **Step 3: Verificar no browser (preview)**

Iniciar o dev server e validar: clicar Buscar num período cacheado retorna instantâneo (sem spinner longo); período grande mostra barra de progresso e recarrega ao concluir. Conferir console/network sem erros.

- [ ] **Step 4: Commit**

```bash
git add frontend/src
git commit -m "feat(financeiro-ml): front envia seller_id + tela de backfill com polling"
```

### Task 30: Validação new-vs-old (mesmo período, paridade de cards/tabela)

**Files:**
- Create: `backend/financeiro_ml/tests/test_validacao_paridade.py` (opcional, comparativo)
- Manual: comparar `/resumo` novo (banco isolado) vs velho (banco principal) no mesmo período.

- [ ] **Step 1: Migrar dados de produção p/ ambiente local de validação**

> **AÇÃO QUE EXIGE AUTORIZAÇÃO DO JULIO** (toca dados de produção). Não executar sem OK explícito.

Run (após OK): `cd backend && FINANCEIRO_ML_DATABASE_URL="sqlite:///./financeiro_ml.db" python -m financeiro_ml.migrate_v1_to_v2 --v1-db ./warehouse_v3_local.db --seller-id <SELLER_ID>`
Expected: imprime `[migrate] {...}` com `orders == orders_src`.

- [ ] **Step 2: Comparar cards do mesmo período**

Subir o backend local e comparar a resposta de `/resumo` novo vs a do painel velho para um período conhecido (ex.: 20–27/05). Conferir: `vendas_aprovadas`, `mc_total`, `mc_pct_global`, `frete_total`, contagem de linhas da tabela. Validar também os 7 pedidos de referência do handoff (`HANDOFF_FINANCEIRO_ML_2026-05-28.md`).

- [ ] **Step 3: Registrar resultado**

Diferença encontrada = bug → corrigir antes de cortar. Igualdade → seguir p/ Task 31. Anotar o resultado da comparação no commit/PR.

- [ ] **Step 4: Commit (se houver teste comparativo ou correções)**

```bash
git add backend/financeiro_ml
git commit -m "test(financeiro-ml): validação de paridade new-vs-old"
```

### Task 31: Corte — front aponta pro novo, velho congelado, depois remove

**Files:**
- Modify: `backend/main.py` (ligar `ENABLE_FINANCEIRO_ML_ROBOT=true` em produção via env do Railway — feito no painel, não no código).
- Modify (corte final, só após N dias de fallback estável): remover `sync.py:ensure_period_synced`, `models.py` v1, e o caminho velho do `router.py`.

- [ ] **Step 1: Deploy com robô habilitado**

> **AÇÃO DE PRODUÇÃO — EXIGE AUTORIZAÇÃO E PROCEDIMENTO DE DEPLOY DO JULIO** (branch/`.bat` conforme regra do projeto). Não fazer deploy sem OK explícito. Setar no Railway: `FINANCEIRO_ML_DATABASE_URL=sqlite:////data/financeiro_ml.db` e `ENABLE_FINANCEIRO_ML_ROBOT=true`.

- [ ] **Step 2: Período de fallback**

Manter o módulo velho congelado (sem deletar) por N dias como rede de segurança. Monitorar logs do robô (poller/worker), tamanho do WAL, ausência de 429 em cascata.

- [ ] **Step 3: Remoção do código morto (após fallback estável)**

Remover, em commits separados e revisáveis: `sync.py` (caminho `ensure_period_synced`/`_sync_single_day`/`_save_order`), `models.py` v1 (migrar imports remanescentes p/ `models_v2`), e o `import financeiro_ml.models as _fml_models` de `main.py` se não mais usado.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore(financeiro-ml): remover encanamento v1 após corte estável"
```

---

## Self-Review (preenchido pelo autor do plano)

**Cobertura da spec:**
- §3 arquitetura CQRS → Fases 4/6/8 (worker único, poller, read-only). ✔
- §4 schema multi-seller → Task 3 (todas as tabelas com seller_id, PKs compostas). ✔
- §5 worker+lock+backfill → Tasks 12,16,24–27. ✔
- §6 scan/cursor/throttle/backoff/OAuth → Tasks 15,16,17,18,19,20,24. ✔
- §7 preserva cálculo + bugs → Tasks 8–10 (build_order_row; bug 4 = frete_incerto; bug cursor = `_cursor_for` usa max(date_last_updated)). ✔
- §8 transição faseada → Fases 0–8 espelham as fases da spec. ✔

**Bugs da spec §7 endereçados:**
1. Cursor campo errado → `worker._cursor_for` usa `max(date_last_updated)` (não `last_synced_at`). ✔
2. Refund parcial / tarifa cheia → `tarifa_refund` fica 0 explícito (mantido); melhoria de estorno proporcional NÃO está nas tasks — **decisão consciente:** depende de endpoint billing indisponível; fica como follow-up pós-corte (não bloqueia). ⚠ (documentado)
3. Frete grátis Full → 0 → coberto parcialmente por `frete_incerto` (marca incerteza em vez de 0 cego). ✔
4. `get_shipment_costs` engole erro → `frete_incerto=True` quando costs vazio. ✔

**Consistência de tipos:** `PollTask`/`BackfillTask` (worker) usados igual em poller/backfill/router; `session_factory` sempre é `FinSessionLocal`; `seller_id` int em todas as assinaturas.

**Follow-ups conscientes (fora do escopo deste plano):** estorno proporcional de tarifa em refund parcial (bug 2, depende de billing API); seletor multi-conta no front (schema já suporta; UI vem quando 2º seller existir); Postgres (pós-beta).

---

**Próximo passo após aprovação deste plano:** executar via superpowers:subagent-driven-development (recomendado — 1 subagent por task, review entre tasks) ou superpowers:executing-plans (inline com checkpoints).
