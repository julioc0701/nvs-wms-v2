# Auto-Separation Job Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Geração automática de listas de separação Tiny (1 ML + 1 Shopee) seg-sex às 06:00 BR, com retry, banner em falha, e endpoint manual `run-now` para teste.

**Architecture:** Adicionar 3º loop ao scheduler existente (`sync_engine.py`). Lógica isolada em novo módulo `services/auto_separation.py`. Estado persistente em nova tabela `auto_separation_state`. Distinção visual auto/manual via sufixo " - Aut"/" - Man" no nome (controlado por novo campo `source` em `TinyPickingList`).

**Tech Stack:** Python 3.13 (asyncio), FastAPI, SQLAlchemy, SQLite, React/Vite (frontend). Sem dependências novas (unittest builtin para testes, pytz já indireto via SQLAlchemy).

---

## File Structure

**New files:**
- `backend/services/auto_separation.py` — Core logic (executar_job, helpers)
- `backend/test_auto_separation.py` — Unit tests (standalone script + unittest)

**Modified files:**
- `backend/models.py` — Add `source` column to `TinyPickingList`; add `AutoSeparationState` model
- `backend/database.py` — Migration: ALTER TABLE + CREATE TABLE + initial row
- `backend/services/sync_engine.py` — Add `auto_separation_loop` + register in `start_local_scheduler`
- `backend/routers/tiny.py` — Set `source='manual'` in existing `create_picking_list`; add 2 new endpoints
- `frontend/src/api/client.js` — 2 new API methods
- `frontend/src/pages/SeparacaoOlist.jsx` — Banner UI when job failed

**Plan saved to:** `docs/superpowers/plans/2026-05-18-auto-separation.md`

---

## Task 1: Backend models — Add `source` column + `AutoSeparationState` model

**Files:**
- Modify: `backend/models.py` (TinyPickingList class + new AutoSeparationState class at end)

- [ ] **Step 1: Add `source` column to TinyPickingList**

Modify `backend/models.py`, find the `class TinyPickingList(Base):` block (around line 263) and add the `source` column right after `status`:

```python
class TinyPickingList(Base):
    """Lista de Separação Mestre criada a partir de múltiplos pedidos do Tiny."""
    __tablename__ = "tiny_picking_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pendente") # pendente, em_andamento, concluida
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual | auto
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    items: Mapped[list["TinyPickingListItem"]] = relationship(back_populates="list", cascade="all, delete-orphan")
```

- [ ] **Step 2: Add `AutoSeparationState` model at end of models.py**

Append at end of `backend/models.py`:

```python
class AutoSeparationState(Base):
    """Estado singleton do job de geração automática de listas (id=1 sempre).
    Rastreia última execução, status, e falhas consecutivas pra exibir banner."""
    __tablename__ = "auto_separation_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str] = mapped_column(String(30), default="never_ran")
    # never_ran | success | failed_visible | no_docs
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    last_error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ex: "ml=30 shopee=12" ou "ml=ok shopee=fail (timeout)"
```

- [ ] **Step 3: Verifica que models.py compila sem erro de sintaxe**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2/backend"
"../.venv/bin/python" -c "from models import TinyPickingList, AutoSeparationState; print('OK')"
```

Expected: `OK`. Se der `ImportError`, revisar a sintaxe da classe `AutoSeparationState`.

- [ ] **Step 4: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add backend/models.py
git commit -m "feat(auto-sep): add source column + AutoSeparationState model"
```

---

## Task 2: Backend migration — `database.py` ALTER + CREATE + initial row

**Files:**
- Modify: `backend/database.py` — `init_db()` function, add migration block

- [ ] **Step 1: Add `AutoSeparationState` to the import in `init_db()`**

In `backend/database.py`, find the line that imports models inside `init_db()` (around line 142) and add `AutoSeparationState`:

```python
def init_db():
    from models import Operator, Session, PickingItem, Barcode, Label, ScanEvent, Printer, PrintJob, TinyOrderSync, AgentMemory, AgentRun, OrderOperational, SyncRun, TinyPickingList, TinyPickingListItem, Shortage, TinySeparationStatus, TinySeparationItemCache, TinySeparationHeader, TinyErpSendLog, AutoSeparationState  # noqa
    Base.metadata.create_all(bind=engine)
```

- [ ] **Step 2: Add migration block for `source` column in TinyPickingList**

Find the existing migration `MIGRATION PARA SHORTAGES` block (around line 303). The `tiny_picking_lists` migration goes RIGHT BEFORE the `# MIGRATION PARA SHORTAGES` line. Insert this new block:

```python
            # MIGRATION: source column em tiny_picking_lists (auto | manual)
            tpl_cols = [c["name"] for c in insp.get_columns("tiny_picking_lists")]
            if "source" not in tpl_cols:
                conn.execute(text("ALTER TABLE tiny_picking_lists ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'manual'"))
                conn.commit()
                print("--- DATABASE MIGRATION: source added to tiny_picking_lists ---")
```

This uses `insp.get_columns("tiny_picking_lists")` (plural — note the table name). É independente do `items_cols` que está mais acima e se refere a `tiny_picking_list_items` (singular_items).

- [ ] **Step 3: Add migration block for `auto_separation_state` table + initial row**

After the existing `tiny_erp_send_logs` migration block (around line 387), add:

```python
        # ── AUTO SEPARATION STATE (singleton para banner de falha + idempotência) ──
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS auto_separation_state (
                id                    INTEGER PRIMARY KEY,
                last_run_at           DATETIME,
                last_status           VARCHAR(30) NOT NULL DEFAULT 'never_ran',
                consecutive_failures  INTEGER NOT NULL DEFAULT 0,
                last_error_msg        TEXT,
                last_summary          TEXT
            )
        """))
        # Garante linha inicial (id=1) — singleton
        conn.execute(text("""
            INSERT OR IGNORE INTO auto_separation_state (id, last_status, consecutive_failures)
            VALUES (1, 'never_ran', 0)
        """))
        conn.commit()
        print("--- DATABASE MIGRATION: auto_separation_state table + initial row verified ---")
```

- [ ] **Step 4: Reset shell + restart backend locally and check logs**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
ls .run/ 2>/dev/null
# Se houver start_backend.pid, vai precisar reiniciar manualmente o backend.
# Skip esse passo se você só vai validar via teste unitário no Task 4.
```

Expected (when backend starts): logs mostrarão:
- `--- DATABASE MIGRATION: source added to tiny_picking_lists ---`
- `--- DATABASE MIGRATION: auto_separation_state table + initial row verified ---`

- [ ] **Step 5: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add backend/database.py
git commit -m "feat(auto-sep): migration source col + auto_separation_state table"
```

---

## Task 3: Backend core logic — `services/auto_separation.py`

**Files:**
- Create: `backend/services/auto_separation.py`

- [ ] **Step 1: Create empty file with imports**

Create `backend/services/auto_separation.py`:

```python
"""Geração automática de listas de separação Tiny (seg-sex 06:00 BR).

Fluxo:
1. Verifica se já rodou hoje (via AutoSeparationState)
2. Para cada marketplace ('ml', 'shopee'): busca docs aguardando + cria lista
3. Skip silencioso quando marketplace sem docs
4. Retry 1x em falha; se 2ª falha → state.last_status='failed_visible'
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta, time as dtime
from typing import Optional

from sqlalchemy.orm import Session as DBSession

from database import SessionLocal
from models import (
    AutoSeparationState,
    TinyPickingList,
    TinyPickingListItem,
    TinySeparationStatus,
    TinySeparationItemCache,
)
from services.tiny_service import TinyService

log = logging.getLogger(__name__)

# Marketplace → idFormaEnvio (do código Tiny existente)
MARKETPLACE_FORMAS = {
    "ml": "735794407",       # Mercado Envios
    "shopee": "735725326",   # Shopee
}
```

- [ ] **Step 2: Add helper `_get_state` + `_save_state`**

Append:

```python
def _get_state(db: DBSession) -> AutoSeparationState:
    """Pega o singleton AutoSeparationState (id=1). Garantido existir pela migration."""
    state = db.query(AutoSeparationState).filter(AutoSeparationState.id == 1).first()
    if not state:
        # Defensivo — migration deveria ter inserido. Cria aqui se faltou.
        state = AutoSeparationState(id=1, last_status="never_ran", consecutive_failures=0)
        db.add(state)
        db.flush()
    return state


def _already_ran_today(state: AutoSeparationState) -> bool:
    """Verifica se já rodou hoje (mesma data calendário em BR)."""
    if not state.last_run_at:
        return False
    # Para simplicidade, compara data UTC (job roda 06:00 BR = 09:00 UTC).
    # Diferença de dia entre BR e UTC só ocorre entre 21:00-23:59 BR — fora do horário do job.
    return state.last_run_at.date() == datetime.utcnow().date()
```

- [ ] **Step 3: Add core function `_fetch_docs_for_marketplace`**

Append:

```python
async def _fetch_docs_for_marketplace(
    service: TinyService,
    marketplace: str,
    data_inicial: str,
    data_final: str,
    db: DBSession,
) -> list[dict]:
    """Busca docs aguardando separação no Tiny para um marketplace.
    Retorna lista de docs FILTRADOS — exclui docs já em em_separacao local."""
    forma_id = MARKETPLACE_FORMAS.get(marketplace)
    if not forma_id:
        log.warning(f"[AUTO_SEP] Marketplace desconhecido: {marketplace}")
        return []

    resp = await service.search_separations(
        pagina=1,
        data_inicial=data_inicial,
        data_final=data_final,
    )
    all_docs = resp.get("separacoes", [])
    # Filtra por marketplace via idFormaEnvio
    marketplace_docs = [
        s.get("separacao") or s
        for s in all_docs
        if str((s.get("separacao") or s).get("idFormaEnvio") or "") == forma_id
    ]
    if not marketplace_docs:
        return []

    # Filtra docs que já estão em em_separacao localmente
    sep_ids = [str(d.get("id")) for d in marketplace_docs if d.get("id")]
    if not sep_ids:
        return []
    em_sep = db.query(TinySeparationStatus.separation_id).filter(
        TinySeparationStatus.separation_id.in_(sep_ids),
        TinySeparationStatus.status.in_(("em_separacao", "concluida", "enviada_erp", "erro_envio_erp"))
    ).all()
    em_sep_set = {row[0] for row in em_sep}
    return [d for d in marketplace_docs if str(d.get("id")) not in em_sep_set]
```

- [ ] **Step 4: Add `_create_list_for_marketplace`**

Append:

```python
async def _create_list_for_marketplace(
    service: TinyService,
    marketplace: str,
    docs: list[dict],
    db: DBSession,
) -> dict:
    """Cria TinyPickingList consolidada para um marketplace.
    Retorna dict com info da lista criada."""
    # 1. Garante que itens estão em cache (warm + fetch)
    sep_ids = [str(d.get("id")) for d in docs if d.get("id")]
    cached = db.query(TinySeparationItemCache).filter(
        TinySeparationItemCache.separation_id.in_(sep_ids)
    ).all()
    cached_ids = {c.separation_id for c in cached}
    missing_ids = [sid for sid in sep_ids if sid not in cached_ids]
    if missing_ids:
        # Fetch e cacheia — usa helper interno do tiny router
        from routers.tiny import _fetch_and_cache
        await _fetch_and_cache(missing_ids, service, db)
        cached = db.query(TinySeparationItemCache).filter(
            TinySeparationItemCache.separation_id.in_(sep_ids)
        ).all()

    # 2. Consolida itens
    from routers.tiny import _consolidate_from_cache
    items = _consolidate_from_cache(sep_ids, cached)
    if not items:
        log.info(f"[AUTO_SEP] {marketplace}: 0 itens consolidados, skip")
        return {"marketplace": marketplace, "list_id": None, "docs": 0}

    # 3. Gera nome com sufixo " - Aut"
    seq = db.query(TinyPickingList).count() + 1
    now_local = datetime.now()
    list_name = f"L{seq} - {now_local.strftime('%d/%m/%Y %H:%M')} - Aut"

    # 4. Cria mestre da lista (source='auto')
    new_list = TinyPickingList(
        name=list_name,
        status="pendente",
        source="auto",
        created_at=datetime.utcnow()
    )
    db.add(new_list)
    db.flush()

    # 5. Adiciona itens
    for it in items:
        db.add(TinyPickingListItem(
            list_id=new_list.id,
            sku=it["sku"],
            description=it["description"],
            quantity=it["quantity"],
            location=it["location"],
            source_separation_ids=",".join(it["source_ids"])
        ))

    # 6. Marca docs como em_separacao
    for sep_id in sep_ids:
        existing = db.query(TinySeparationStatus).filter(
            TinySeparationStatus.separation_id == str(sep_id)
        ).first()
        if existing:
            existing.status = "em_separacao"
            existing.list_id = new_list.id
        else:
            db.add(TinySeparationStatus(
                separation_id=str(sep_id),
                status="em_separacao",
                list_id=new_list.id
            ))

    return {
        "marketplace": marketplace,
        "list_id": new_list.id,
        "list_name": new_list.name,
        "docs": len(sep_ids),
        "items": len(items),
    }
```

- [ ] **Step 5: Add main `executar_job` orchestrator**

Append:

```python
async def executar_job(token: str, force: bool = False) -> dict:
    """Executa o job completo:
    - Verifica idempotência (já rodou hoje?)
    - Para cada marketplace busca docs e cria listas
    - Atualiza state (success / failed_visible / no_docs)

    force=True ignora 'já rodou hoje' — usado pelo endpoint run-now.

    Retorna dict com sumário da execução.
    """
    db = SessionLocal()
    summary = {"status": "unknown", "lists": [], "errors": []}
    try:
        state = _get_state(db)

        if not force and _already_ran_today(state):
            log.info("[AUTO_SEP] Já rodou hoje (skip — não força)")
            return {"status": "skipped_already_ran", "lists": []}

        # Calcula janela: hoje - 6 dias (= 7 dias incluindo hoje)
        today = datetime.now()
        data_final = today.strftime("%d/%m/%Y")
        data_inicial = (today - timedelta(days=6)).strftime("%d/%m/%Y")
        log.info(f"[AUTO_SEP] Iniciando — janela {data_inicial} a {data_final}")

        service = TinyService(token=token)
        any_success = False
        any_failure = False
        summary_parts = []

        for marketplace in ("ml", "shopee"):
            try:
                docs = await _fetch_docs_for_marketplace(
                    service, marketplace, data_inicial, data_final, db
                )
                if not docs:
                    log.info(f"[AUTO_SEP] {marketplace}: 0 docs aguardando — skip silencioso")
                    summary_parts.append(f"{marketplace}=0")
                    any_success = True  # Sem docs não é falha
                    continue

                result = await _create_list_for_marketplace(service, marketplace, docs, db)
                db.commit()  # commit por marketplace (atômico)
                summary["lists"].append(result)
                summary_parts.append(f"{marketplace}={result['docs']}")
                any_success = True
                log.info(f"[AUTO_SEP] {marketplace}: lista {result['list_name']} criada com {result['docs']} docs")

            except Exception as exc:
                db.rollback()
                msg = f"{marketplace}: {exc}"
                log.exception(f"[AUTO_SEP] Falha em {marketplace}")
                summary["errors"].append(msg)
                summary_parts.append(f"{marketplace}=fail")
                any_failure = True

        # Atualiza state com base no resultado
        state = _get_state(db)
        state.last_run_at = datetime.utcnow()
        state.last_summary = " ".join(summary_parts)
        if any_failure and not any_success:
            state.consecutive_failures += 1
            state.last_error_msg = "; ".join(summary["errors"])[:500]
            if state.consecutive_failures >= 2:
                state.last_status = "failed_visible"
                summary["status"] = "failed_visible"
            else:
                state.last_status = "success"  # falha única não é "visible" ainda
                summary["status"] = "failed_single"
        else:
            # Pelo menos 1 marketplace OK (ou skip silencioso). Reset failures.
            state.consecutive_failures = 0
            state.last_error_msg = None
            if not summary["lists"]:
                state.last_status = "no_docs"
                summary["status"] = "no_docs"
            else:
                state.last_status = "success"
                summary["status"] = "success"
        db.commit()
        return summary
    except Exception as outer:
        log.exception(f"[AUTO_SEP] Falha geral: {outer}")
        try:
            state = _get_state(db)
            state.consecutive_failures += 1
            state.last_error_msg = str(outer)[:500]
            if state.consecutive_failures >= 2:
                state.last_status = "failed_visible"
            db.commit()
        except Exception:
            pass
        return {"status": "error", "error": str(outer)}
    finally:
        db.close()
```

- [ ] **Step 6: Add helper `should_run_now` for the loop**

Append:

```python
def should_run_now() -> bool:
    """Retorna True se for hora de rodar o job:
    - Dia da semana = seg(0) a sex(4)
    - Horário (BR) entre 06:00 e 06:30 (janela de 30min)
    - Não considera idempotência aqui (essa parte é checada dentro de executar_job)

    Nota: 'horário BR' é assumido = America/Sao_Paulo (UTC-3, sem DST hoje).
    Como Railway roda em UTC, comparamos: BR 06:00 = UTC 09:00.
    """
    now_utc = datetime.utcnow()
    # BR = UTC - 3 (sem horário de verão atualmente)
    now_br = now_utc - timedelta(hours=3)

    # Seg = 0, Sex = 4
    if now_br.weekday() > 4:
        return False

    # Janela 06:00 - 06:30 BR
    if now_br.hour != 6:
        return False
    if now_br.minute >= 30:
        return False

    return True
```

- [ ] **Step 7: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add backend/services/auto_separation.py
git commit -m "feat(auto-sep): core logic em services/auto_separation.py"
```

---

## Task 4: Backend tests — `test_auto_separation.py`

**Files:**
- Create: `backend/test_auto_separation.py`

- [ ] **Step 1: Write failing tests (TDD)**

Create `backend/test_auto_separation.py`:

```python
"""Testes do job de geração automática de listas.

Uso:
    cd backend
    python test_auto_separation.py

Ou via unittest:
    cd backend
    python -m unittest test_auto_separation -v
"""
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

# Garante imports do backend
sys.path.insert(0, os.path.dirname(__file__))


class TestShouldRunNow(unittest.TestCase):
    """Testa o predicate de horário."""

    def setUp(self):
        from services.auto_separation import should_run_now
        self.should_run_now = should_run_now

    @patch("services.auto_separation.datetime")
    def test_segunda_06h15_BR_returns_true(self, mock_dt):
        # 09:15 UTC = 06:15 BR, segunda-feira (weekday 0)
        mock_dt.utcnow.return_value = datetime(2026, 5, 18, 9, 15)
        # Garante que outras chamadas a datetime ainda funcionem
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        # timedelta também precisa funcionar
        from datetime import timedelta as real_td
        with patch("services.auto_separation.timedelta", real_td):
            self.assertTrue(self.should_run_now())

    @patch("services.auto_separation.datetime")
    def test_sabado_returns_false(self, mock_dt):
        # 06:15 BR num sábado
        mock_dt.utcnow.return_value = datetime(2026, 5, 16, 9, 15)
        from datetime import timedelta as real_td
        with patch("services.auto_separation.timedelta", real_td):
            self.assertFalse(self.should_run_now())

    @patch("services.auto_separation.datetime")
    def test_segunda_05h59_returns_false(self, mock_dt):
        # 08:59 UTC = 05:59 BR
        mock_dt.utcnow.return_value = datetime(2026, 5, 18, 8, 59)
        from datetime import timedelta as real_td
        with patch("services.auto_separation.timedelta", real_td):
            self.assertFalse(self.should_run_now())

    @patch("services.auto_separation.datetime")
    def test_segunda_06h30_returns_false(self, mock_dt):
        # 09:30 UTC = 06:30 BR (limite superior — exclusivo)
        mock_dt.utcnow.return_value = datetime(2026, 5, 18, 9, 30)
        from datetime import timedelta as real_td
        with patch("services.auto_separation.timedelta", real_td):
            self.assertFalse(self.should_run_now())


class TestAlreadyRanToday(unittest.TestCase):
    """Testa o predicate de idempotência."""

    def test_state_sem_last_run_returns_false(self):
        from services.auto_separation import _already_ran_today
        from models import AutoSeparationState
        state = AutoSeparationState(id=1, last_run_at=None)
        self.assertFalse(_already_ran_today(state))

    def test_state_last_run_hoje_returns_true(self):
        from services.auto_separation import _already_ran_today
        from models import AutoSeparationState
        state = AutoSeparationState(id=1, last_run_at=datetime.utcnow())
        self.assertTrue(_already_ran_today(state))

    def test_state_last_run_ontem_returns_false(self):
        from services.auto_separation import _already_ran_today
        from models import AutoSeparationState
        state = AutoSeparationState(id=1, last_run_at=datetime.utcnow() - timedelta(days=1))
        self.assertFalse(_already_ran_today(state))


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Run the tests, expect them to PASS**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2/backend"
"../.venv/bin/python" -m unittest test_auto_separation -v 2>&1 | tail -20
```

Expected: 7 tests passed (4 should_run_now + 3 already_ran_today).

If FAILS:
- Check that `services/auto_separation.py` is in PYTHONPATH (sys.path.insert handles this)
- Check imports — module name `services.auto_separation` should resolve

- [ ] **Step 3: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add backend/test_auto_separation.py
git commit -m "test(auto-sep): unittest para should_run_now + already_ran_today"
```

---

## Task 5: Backend scheduler — integrate `auto_separation_loop` in `sync_engine.py`

**Files:**
- Modify: `backend/services/sync_engine.py` (add loop function + register in start)

- [ ] **Step 1: Add loop function**

In `backend/services/sync_engine.py`, after the `erp_sync_loop` function (around line 630), add:

```python
async def auto_separation_loop(token: str) -> None:
    """Loop que checa a cada minuto se é hora de rodar o job de auto-separação.
    Janela: seg-sex 06:00-06:30 BR. Idempotência via AutoSeparationState."""
    global SCHEDULER_STOP
    from services.auto_separation import should_run_now, executar_job

    log.info("[AUTO_SEP] Loop iniciado — checa janela 06:00-06:30 BR seg-sex")
    last_attempt_at = None

    while not SCHEDULER_STOP:
        try:
            if should_run_now():
                # Evita re-tentar em ciclo curto se acabou de rodar
                now = datetime.utcnow()
                if last_attempt_at and (now - last_attempt_at) < timedelta(minutes=10):
                    pass
                else:
                    last_attempt_at = now
                    log.info("[AUTO_SEP] Janela atingida — executando job")
                    result = await executar_job(token, force=False)
                    log.info(f"[AUTO_SEP] Resultado: {result.get('status')} — {result.get('lists', [])}")

                    # Retry interno: se falhou (não 'success' nem 'skipped' nem 'no_docs'), tenta de novo em 5min
                    if result.get("status") in ("failed_single", "error"):
                        log.warning(f"[AUTO_SEP] Falha — agendando retry em 5min")
                        await asyncio.sleep(300)
                        if not SCHEDULER_STOP:
                            retry_result = await executar_job(token, force=True)
                            log.info(f"[AUTO_SEP] Retry: {retry_result.get('status')}")
        except Exception as exc:
            log.exception(f"[AUTO_SEP] Erro inesperado no loop: {exc}")
        await asyncio.sleep(60)  # checa a cada minuto
```

- [ ] **Step 2: Add `AUTO_SEP_TASK` global**

At top of `sync_engine.py` (around line 17), add:

```python
SCHEDULER_TASK: asyncio.Task | None = None
ERP_SYNC_TASK: asyncio.Task | None = None
AUTO_SEP_TASK: asyncio.Task | None = None  # NEW
SCHEDULER_STOP = False
```

- [ ] **Step 3: Register loop in `start_local_scheduler`**

Modify `start_local_scheduler` (around line 661):

```python
def start_local_scheduler(token: str) -> asyncio.Task | None:
    global SCHEDULER_TASK, ERP_SYNC_TASK, AUTO_SEP_TASK, SCHEDULER_STOP
    if not token:
        log.warning("Scheduler local não iniciado: TINY_API_TOKEN ausente")
        return None
    if SCHEDULER_TASK and not SCHEDULER_TASK.done():
        return SCHEDULER_TASK
    SCHEDULER_STOP = False
    SCHEDULER_TASK = asyncio.create_task(scheduler_loop(token))
    ERP_SYNC_TASK = asyncio.create_task(erp_sync_loop(token))
    AUTO_SEP_TASK = asyncio.create_task(auto_separation_loop(token))
    log.info("Scheduler local de sync + ERP auto-send + auto-separação iniciado")
    return SCHEDULER_TASK
```

- [ ] **Step 4: Register in `stop_local_scheduler` too**

Modify `stop_local_scheduler` (around line 675):

```python
async def stop_local_scheduler() -> None:
    global SCHEDULER_TASK, ERP_SYNC_TASK, AUTO_SEP_TASK, SCHEDULER_STOP
    SCHEDULER_STOP = True
    for task in (SCHEDULER_TASK, ERP_SYNC_TASK, AUTO_SEP_TASK):
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    SCHEDULER_TASK = None
    ERP_SYNC_TASK = None
    AUTO_SEP_TASK = None
```

- [ ] **Step 5: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add backend/services/sync_engine.py
git commit -m "feat(auto-sep): integra auto_separation_loop no scheduler"
```

---

## Task 6: Backend — marca listas manuais com `source='manual'`

**Files:**
- Modify: `backend/routers/tiny.py` (existing `create_picking_list` endpoint)

- [ ] **Step 1: Adicionar `source='manual'` na criação de TinyPickingList no fluxo manual**

Em `backend/routers/tiny.py`, encontrar onde `TinyPickingList` é criado no endpoint manual (linha ~727):

```python
        # 3. Cria o mestre da lista
        new_list = TinyPickingList(
            name=list_name,
            status="pendente",
            created_at=datetime.utcnow()
        )
```

Trocar por:

```python
        # 3. Cria o mestre da lista
        new_list = TinyPickingList(
            name=list_name,
            status="pendente",
            source="manual",
            created_at=datetime.utcnow()
        )
```

E mudar a geração do nome (linha ~724) pra incluir sufixo " - Man":

```python
        # 2. Gera nome sequencial L{N} - DD/MM/YYYY HH:MM - Man
        if req.name:
            list_name = req.name
        else:
            seq = db.query(TinyPickingList).count() + 1
            now_local = datetime.now()
            list_name = f"L{seq} - {now_local.strftime('%d/%m/%Y %H:%M')} - Man"
```

- [ ] **Step 2: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add backend/routers/tiny.py
git commit -m "feat(auto-sep): listas manuais marcadas com source=manual + sufixo - Man"
```

---

## Task 7: Backend endpoints — `GET /status` + `POST /run-now`

**Files:**
- Modify: `backend/routers/tiny.py` (adicionar 2 endpoints)

- [ ] **Step 1: Adicionar endpoint `GET /tiny/auto-separation/status`**

No final de `backend/routers/tiny.py`, adicionar:

```python
# ── AUTO SEPARATION ENDPOINTS ────────────────────────────────────────────────

@router.get("/auto-separation/status")
async def get_auto_separation_status(db: Session = Depends(get_db)):
    """Retorna o estado atual do job. Usado pelo banner do frontend."""
    from models import AutoSeparationState
    state = db.query(AutoSeparationState).filter(AutoSeparationState.id == 1).first()
    if not state:
        return {
            "last_run_at": None,
            "last_status": "never_ran",
            "consecutive_failures": 0,
            "last_error_msg": None,
            "last_summary": None,
            "show_banner": False,
        }
    return {
        "last_run_at": state.last_run_at.isoformat() if state.last_run_at else None,
        "last_status": state.last_status,
        "consecutive_failures": state.consecutive_failures,
        "last_error_msg": state.last_error_msg,
        "last_summary": state.last_summary,
        "show_banner": state.last_status == "failed_visible",
    }


@router.post("/auto-separation/run-now")
async def run_auto_separation_now(db: Session = Depends(get_db)):
    """Executa o job imediatamente (força — ignora 'já rodou hoje').
    Útil pra QA e recuperação manual após falha."""
    from services.auto_separation import executar_job
    if not TINY_TOKEN:
        raise HTTPException(status_code=400, detail="TINY_API_TOKEN não configurado")
    result = await executar_job(TINY_TOKEN, force=True)
    return result
```

- [ ] **Step 2: Restart backend local e testar manualmente**

```bash
# Local — reinicia backend e testa
curl http://localhost:8001/api/tiny/auto-separation/status 2>&1 | head -5
```

Expected: JSON com `last_status: "never_ran"` (já que ainda não rodou nada).

- [ ] **Step 3: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add backend/routers/tiny.py
git commit -m "feat(auto-sep): endpoints GET status + POST run-now"
```

---

## Task 8: Frontend client.js — novos métodos API

**Files:**
- Modify: `frontend/src/api/client.js`

- [ ] **Step 1: Adicionar 2 métodos novos**

Em `frontend/src/api/client.js`, na seção de Tiny endpoints (perto do `getShortages` linha 201), adicionar:

```javascript
  // Auto-Separation Job
  getAutoSeparationStatus: () => req('GET', '/tiny/auto-separation/status'),
  runAutoSeparationNow: () => req('POST', '/tiny/auto-separation/run-now', {}),
```

- [ ] **Step 2: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add frontend/src/api/client.js
git commit -m "feat(auto-sep): client.js - API methods status + run-now"
```

---

## Task 9: Frontend banner — `SeparacaoOlist.jsx`

**Files:**
- Modify: `frontend/src/pages/SeparacaoOlist.jsx`

- [ ] **Step 1: Adicionar state + fetch do status**

Em `SeparacaoOlist.jsx`, adicionar perto dos outros `useState` (linha ~67):

```javascript
  const [autoSepStatus, setAutoSepStatus] = useState(null)
  const [bannerDismissed, setBannerDismissed] = useState(false)
```

Adicionar `useEffect` que faz fetch (perto dos outros useEffects, linha ~299):

```javascript
  useEffect(() => {
    // Busca status do job auto pra mostrar banner se falhou
    api.getAutoSeparationStatus()
      .then(setAutoSepStatus)
      .catch(() => {})
  }, [])
```

- [ ] **Step 2: Renderizar banner no topo do conteúdo**

Em `SeparacaoOlist.jsx`, logo após `<h1>` (linha ~398) e antes do `{backfilling && ...}`, adicionar:

```jsx
      {autoSepStatus?.show_banner && !bannerDismissed && (
        <div className="mx-2 mb-4 flex items-center gap-3 px-4 py-3 bg-amber-50 border border-amber-200 rounded-xl text-xs font-semibold text-amber-800">
          <AlertCircle size={14} className="shrink-0" />
          <span className="flex-1">
            Geração automática falhou hoje
            {autoSepStatus.last_run_at && ` (${new Date(autoSepStatus.last_run_at).toLocaleTimeString('pt-BR', {hour:'2-digit', minute:'2-digit'})})`}
            . Gere manualmente abaixo ou aguarde retry.
          </span>
          <button
            onClick={() => setBannerDismissed(true)}
            className="p-1 hover:bg-amber-100 rounded transition-colors"
            title="Dispensar aviso"
          >
            <X size={14} />
          </button>
        </div>
      )}
```

- [ ] **Step 3: Verificar `AlertCircle` e `X` estão importados**

No topo de `SeparacaoOlist.jsx`, verificar imports do `lucide-react`:

```bash
grep "from 'lucide-react'" "/Users/julio/Documents/Antigra/warehouse-picker v2/frontend/src/pages/SeparacaoOlist.jsx" | head
```

Esperado: a linha já contém `AlertCircle` e `X`. Se não, adicionar.

Olhando o código atual (linha 5-11), o import já tem `X` e `AlertCircle`. ✓

- [ ] **Step 4: Commit**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
git add frontend/src/pages/SeparacaoOlist.jsx
git commit -m "feat(auto-sep): banner sutil em SeparacaoOlist quando job falha 2x"
```

---

## Task 10: Validação end-to-end local + deploy PRD

- [ ] **Step 1: Restart backend local e rodar testes unitários**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2/backend"
"../.venv/bin/python" -m unittest test_auto_separation -v
```

Expected: 7 tests passed.

- [ ] **Step 2: Testar endpoint `run-now` localmente (chamada real ao Tiny)**

Backend precisa estar rodando local. Testar:

```bash
curl -X POST http://localhost:8001/api/tiny/auto-separation/run-now -H "Content-Type: application/json"
```

Expected (caso de sucesso típico):
```json
{
  "status": "success",
  "lists": [
    {"marketplace": "ml", "list_id": 123, "list_name": "L42 - 18/05/2026 14:30 - Aut", "docs": 30, "items": 250},
    {"marketplace": "shopee", "list_id": 124, "list_name": "L43 - 18/05/2026 14:30 - Aut", "docs": 12, "items": 80}
  ]
}
```

Caso 0 docs disponíveis:
```json
{"status": "no_docs", "lists": []}
```

- [ ] **Step 3: Verificar lista criada no banco**

```bash
"../.venv/bin/python" -c "
import sys; sys.path.insert(0, '.')
from database import SessionLocal
from models import TinyPickingList
db = SessionLocal()
for plist in db.query(TinyPickingList).order_by(TinyPickingList.id.desc()).limit(3):
    print(f'{plist.id} | {plist.name} | source={plist.source}')
db.close()
"
```

Expected: ver listas mais recentes, as recém-criadas com `source=auto` e sufixo `- Aut` no nome.

- [ ] **Step 4: Verificar GET /status retorna last_status=success**

```bash
curl http://localhost:8001/api/tiny/auto-separation/status
```

Expected: `last_status: "success"`, `consecutive_failures: 0`, `show_banner: false`.

- [ ] **Step 5: Deploy PRD**

```bash
cd "/Users/julio/Documents/Antigra/warehouse-picker v2"
./publicar_producao.bat  # ou equivalente no macOS
```

Aguardar Railway re-deploy (~2-3 min).

- [ ] **Step 6: Validação pós-deploy no PRD**

1. Verificar logs do Railway:
   - `--- DATABASE MIGRATION: source added to tiny_picking_lists ---`
   - `--- DATABASE MIGRATION: auto_separation_state table + initial row verified ---`
   - `[AUTO_SEP] Loop iniciado — checa janela 06:00-06:30 BR seg-sex`

2. Testar `run-now` no PRD via curl:
   ```bash
   curl -X POST https://nvs-wms-v2-production.up.railway.app/api/tiny/auto-separation/run-now
   ```

3. Abrir painel de Separação no navegador → ver listas criadas com sufixo "- Aut"

4. Verificar status:
   ```bash
   curl https://nvs-wms-v2-production.up.railway.app/api/tiny/auto-separation/status
   ```

- [ ] **Step 7: Plano de rollout — Fase 2**

Após validação OK na Fase 1 (manual), Fase 2 = deixar agendamento rodar autônomo na próxima seg-sex 06:00 BR.

Monitorar 1ª semana:
- Diariamente checar logs Railway por `[AUTO_SEP]` entries
- Confirmar criação de listas seg-sex
- Verificar painel de Separação sem banner inesperado

---

## Notas técnicas

**Timezone**: usa cálculo manual `UTC - 3` (sem horário de verão atualmente no Brasil). Se voltar DST no futuro, trocar pra usar `zoneinfo.ZoneInfo("America/Sao_Paulo")` (já disponível no Python 3.9+).

**Idempotência**: protegida em 3 camadas — (1) `_already_ran_today` no `executar_job`, (2) janela de 30min do `should_run_now`, (3) `last_attempt_at` no loop. Backend reiniciar dentro da janela = `_already_ran_today` retorna True → no-op.

**Backfill de dados existentes**: listas antigas pré-deploy terão `source='manual'` (default da migration). Nomes antigos NÃO ganham sufixo " - Man" automaticamente (só novas). Isso é OK — quem importa pra operação é o que vier depois.

**Sem dependência nova**: tudo usa stdlib + libs já existentes no projeto.
