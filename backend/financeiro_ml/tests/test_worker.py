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


# ---- Fase A: robô enxuto ----

def test_cursor_falls_back_to_last_synced_when_dlu_null(fin_db):
    """Dia migrado (ok) com date_last_updated NULL → cursor usa last_synced_at,
    em vez de None (que dispararia re-varredura do dia inteiro)."""
    db, m = fin_db
    from datetime import date, datetime, timedelta
    from financeiro_ml.worker import WriteWorker
    s = db.FinSessionLocal()
    s.add(m.MLOrderCache(seller_id=1, order_id=500, date_created=datetime(2026, 5, 20, 10),
                         date_last_updated=None, status="paid", raw_json="{}"))
    synced = datetime(2026, 5, 25, 12, 0, 0)
    s.add(m.MLDaySyncStatus(seller_id=1, day=date(2026, 5, 20), last_synced_at=synced,
                            orders_count=1, status="ok"))
    s.commit(); s.close()
    w = WriteWorker(session_factory=db.FinSessionLocal, client_factory=lambda sid: None)
    assert w._cursor_for(1, date(2026, 5, 20)) == synced - timedelta(hours=1)


@pytest.mark.asyncio
async def test_enrich_skipped_when_order_unchanged(fin_db):
    """Pedido já em cache com mesmo date_last_updated → não re-busca shipment."""
    db, m = fin_db
    from financeiro_ml.worker import WriteWorker, PollTask
    from financeiro_ml.calc import _to_brt_naive
    dlu = _to_brt_naive("2026-05-20T11:30:00.000-03:00")
    s = db.FinSessionLocal()
    s.add(m.MLOrderCache(seller_id=1, order_id=100, date_created=datetime(2026, 5, 20, 10),
                         date_last_updated=dlu, status="paid", raw_json="{}"))
    s.commit(); s.close()

    class FC:
        def __init__(self): self.shipment_calls = 0
        async def search_orders(self, **kw):
            return {"results": [_order_payload(100)]} if kw.get("offset", 0) == 0 else {"results": []}
        async def get_shipment(self, sid):
            self.shipment_calls += 1; return {}
        async def get_shipment_costs(self, sid): return {}
        async def get_order_discounts(self, oid): return {"details": []}

    fc = FC()
    worker = WriteWorker(session_factory=db.FinSessionLocal, client_factory=lambda sid: fc)
    q = asyncio.Queue(); await q.put(PollTask(seller_id=1, days=[date(2026, 5, 20)]))
    runner = asyncio.create_task(worker.run(q)); await q.join(); worker.stop(); await runner
    assert fc.shipment_calls == 0


@pytest.mark.asyncio
async def test_poll_skips_fresh_recent_day(fin_db):
    """Dia recente já ok e sincronizado agora → freshness pula, zero chamada ML."""
    db, m = fin_db
    from financeiro_ml.worker import WriteWorker, PollTask
    today = date.today()
    s = db.FinSessionLocal()
    s.add(m.MLDaySyncStatus(seller_id=1, day=today, last_synced_at=datetime.utcnow(),
                            orders_count=5, status="ok"))
    s.commit(); s.close()

    class FC:
        def __init__(self): self.search_calls = 0
        async def search_orders(self, **kw):
            self.search_calls += 1; return {"results": []}
        async def get_shipment(self, sid): return {}
        async def get_shipment_costs(self, sid): return {}
        async def get_order_discounts(self, oid): return {"details": []}

    fc = FC()
    worker = WriteWorker(session_factory=db.FinSessionLocal, client_factory=lambda sid: fc)
    q = asyncio.Queue(); await q.put(PollTask(seller_id=1, days=[today]))
    runner = asyncio.create_task(worker.run(q)); await q.join(); worker.stop(); await runner
    assert fc.search_calls == 0
