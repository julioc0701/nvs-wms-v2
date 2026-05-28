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
