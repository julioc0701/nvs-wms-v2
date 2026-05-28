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
