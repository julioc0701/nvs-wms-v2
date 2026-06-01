from datetime import date

import pytest


class FakeClient:
    def __init__(self, pages):
        self.pages = pages
        self.calls = 0

    async def search_orders(self, **kwargs):
        page = self.pages[self.calls] if self.calls < len(self.pages) else {"results": []}
        self.calls += 1
        return page

    async def get_shipment(self, shipment_id):
        raise AssertionError("canario orders-search nao deve chamar shipments")

    async def get_shipment_costs(self, shipment_id):
        raise AssertionError("canario orders-search nao deve chamar shipment costs")


def _order(order_id, shipment_id=None, tags=None, shipping_cost=12.5):
    return {
        "id": order_id,
        "status": "paid",
        "tags": tags or [],
        "shipping": {"id": shipment_id} if shipment_id else {},
        "payments": [{"shipping_cost": shipping_cost}],
        "order_items": [{
            "item": {"id": f"MLB{order_id}", "title": "Item", "seller_sku": f"SKU{order_id}"},
            "unit_price": 100,
            "quantity": 1,
            "sale_fee": 10,
        }],
        "date_created": "2026-06-01T10:00:00.000-03:00",
    }


@pytest.mark.asyncio
async def test_orders_search_canary_persists_snapshots_and_pending_tasks(fin_db):
    db, m = fin_db
    from financeiro_ml.canary import run_orders_search_canary

    client = FakeClient([
        {"results": [
            _order(101, shipment_id=5001),
            _order(102, shipment_id=5002, tags=["order_has_discount"], shipping_cost=0),
            _order(103),
        ]},
        {"results": []},
    ])

    result = await run_orders_search_canary(
        session_factory=db.FinSessionLocal,
        client=client,
        seller_id=1,
        day=date(2026, 6, 1),
        max_pages=5,
    )

    assert result.status == "ok"
    assert result.orders_count == 3
    assert result.pages_count == 1
    assert result.pending_shipments == 2
    assert result.pending_discounts == 1
    assert result.pending_shipping_costs == 1

    s = db.FinSessionLocal()
    try:
        assert s.query(m.MLCanaryRun).count() == 1
        assert s.query(m.MLCanaryOrderSnapshot).count() == 3
        tasks = s.query(m.MLCanaryPendingTask).all()
        assert {(t.kind, t.ref_id) for t in tasks} == {
            ("seller_shipping", "5001"),
            ("seller_shipping", "5002"),
            ("shipping_cost", "5002"),
            ("discount", "102"),
        }
        assert s.query(m.MLOrderCache).count() == 0
    finally:
        s.close()


@pytest.mark.asyncio
async def test_orders_search_canary_ignores_duplicate_orders_across_pages(fin_db):
    db, m = fin_db
    from financeiro_ml.canary import run_orders_search_canary

    page1 = [_order(101, shipment_id=5001, tags=["order_has_discount"], shipping_cost=0)] * 50
    page2 = [_order(101, shipment_id=5001, tags=["order_has_discount"], shipping_cost=0)]
    client = FakeClient([
        {"results": page1},
        {"results": page2},
        {"results": []},
    ])

    result = await run_orders_search_canary(
        session_factory=db.FinSessionLocal,
        client=client,
        seller_id=1,
        day=date(2026, 6, 1),
        max_pages=5,
    )

    assert result.status == "ok"
    assert result.orders_count == 1
    assert result.pages_count == 2
    assert result.pending_shipments == 1
    assert result.pending_discounts == 1
    assert result.pending_shipping_costs == 1

    s = db.FinSessionLocal()
    try:
        assert s.query(m.MLCanaryOrderSnapshot).count() == 1
        tasks = s.query(m.MLCanaryPendingTask).all()
        assert {(t.kind, t.ref_id) for t in tasks} == {
            ("seller_shipping", "5001"),
            ("shipping_cost", "5001"),
            ("discount", "101"),
        }
    finally:
        s.close()


@pytest.mark.asyncio
async def test_orders_search_canary_records_rate_limited(fin_db):
    db, m = fin_db
    from financeiro_ml.canary import run_orders_search_canary
    from financeiro_ml.client import MLRateLimited

    class RateLimitedClient:
        async def search_orders(self, **kwargs):
            raise MLRateLimited("/orders/search")

    result = await run_orders_search_canary(
        session_factory=db.FinSessionLocal,
        client=RateLimitedClient(),
        seller_id=1,
        day=date(2026, 6, 1),
        max_pages=1,
    )

    assert result.status == "rate_limited"
    assert result.orders_count == 0
    s = db.FinSessionLocal()
    try:
        run = s.query(m.MLCanaryRun).first()
        assert run.status == "rate_limited"
        assert "orders/search" in run.error_message
    finally:
        s.close()


def test_get_canary_run_summary(fin_db):
    db, _ = fin_db
    from financeiro_ml.canary import get_canary_run
    from financeiro_ml.models_v2 import MLCanaryRun, MLCanaryPendingTask

    s = db.FinSessionLocal()
    try:
        run = MLCanaryRun(seller_id=1, day=date(2026, 6, 1), status="ok",
                          orders_count=2, pages_count=1, pending_shipments=1)
        s.add(run)
        s.commit()
        s.add(MLCanaryPendingTask(run_id=run.id, seller_id=1, kind="seller_shipping", ref_id="5001"))
        s.commit()
        run_id = run.id
    finally:
        s.close()

    summary = get_canary_run(db.FinSessionLocal, run_id)
    assert summary["orders_count"] == 2
    assert summary["pending_by_kind"]["seller_shipping"]["pending"] == 1


@pytest.mark.asyncio
async def test_billing_order_details_canary_summarizes_links(fin_db):
    db, _ = fin_db
    from financeiro_ml.canary import run_billing_order_details_canary
    from financeiro_ml.models_v2 import MLCanaryRun, MLCanaryOrderSnapshot

    class BillingClient:
        async def get_billing_order_details(self, *, seller_id, order_ids):
            assert seller_id == 1
            assert order_ids == [101, 102]
            return {
                "total": 2,
                "results": [{
                    "order_id": 101,
                    "payment_info": [{
                        "details": [{
                            "charge_info": {
                                "transaction_detail": "Cargo por Mercado Envios",
                                "detail_type": "CHARGE",
                                "detail_sub_type": "CME",
                                "detail_amount": 8.05,
                            },
                            "sales_info": [{"order_id": 101}],
                            "shipping_info": {
                                "shipping_id": "5001",
                                "pack_id": "7001",
                                "receiver_shipping_cost": 0,
                            },
                            "items_info": [{"order_id": 101, "item_id": "MLB101"}],
                            "marketplace_info": {"marketplace": "SHIPPING"},
                        }]
                    }]
                }, {
                    "order_id": 102,
                    "payment_info": [],
                }],
            }

    s = db.FinSessionLocal()
    try:
        run = MLCanaryRun(seller_id=1, day=date(2026, 6, 1), status="ok")
        s.add(run)
        s.commit()
        s.add(MLCanaryOrderSnapshot(
            run_id=run.id, seller_id=1, order_id=101,
            ingest_status="base_imported", raw_json="{}"))
        s.add(MLCanaryOrderSnapshot(
            run_id=run.id, seller_id=1, order_id=102,
            ingest_status="base_imported", raw_json="{}"))
        s.commit()
        run_id = run.id
    finally:
        s.close()

    result = await run_billing_order_details_canary(
        session_factory=db.FinSessionLocal,
        client=BillingClient(),
        run_id=run_id,
        seller_id=1,
        max_orders=2,
    )

    assert result.status == "ok"
    assert result.requested_orders == [101, 102]
    assert result.order_ids_found == [101, 102]
    assert result.shipping_ids_found == ["5001"]
    assert result.pack_ids_found == ["7001"]
    assert result.shipping_total_by_order == {"101": 8.05}
    assert result.shipping_charge_lines[0]["detail_amount"] == 8.05
    assert result.shipping_charge_lines[0]["order_ids"] == [101]


@pytest.mark.asyncio
async def test_billing_order_ids_canary_uses_explicit_ids():
    from financeiro_ml.canary import run_billing_order_ids_canary

    class BillingClient:
        async def get_billing_order_details(self, *, seller_id, order_ids):
            assert seller_id == 1
            assert order_ids == [102, 101]
            return {
                "total": 1,
                "results": [{
                    "order_id": 102,
                    "charge_info": {
                        "transaction_detail": "Tarifa de envio extra ou intermunicipal",
                        "detail_amount": 15.5,
                    },
                    "sales_info": [{"order_id": 102}],
                    "shipping_info": {"shipping_id": "5002"},
                    "marketplace_info": {"marketplace": "SHIPPING"},
                }],
            }

    result = await run_billing_order_ids_canary(
        client=BillingClient(),
        seller_id=1,
        order_ids=[102, 101, 102],
    )

    assert result.status == "ok"
    assert result.requested_orders == [102, 101]
    assert result.shipping_total_by_order == {"102": 15.5}


@pytest.mark.asyncio
async def test_probe_shipment_costs_summarizes_sender_cost():
    from financeiro_ml.canary import probe_shipment_costs

    class ShipmentCostClient:
        async def _get(self, path):
            assert path == "/shipments/5001/costs"
            return {
                "gross_amount": 20.94,
                "senders": [{"cost": 7.95, "save": 1.0}],
                "receiver": {"cost": 12.99, "save": 0},
            }

    result = await probe_shipment_costs(
        client=ShipmentCostClient(),
        entries=[{"order_id": 101, "shipment_id": "5001"}],
        sleep_sec=0,
    )

    assert result.status == "ok"
    assert result.results[0]["sender_cost"] == 7.95
    assert result.results[0]["receiver_cost"] == 12.99


@pytest.mark.asyncio
async def test_probe_billing_period_details_returns_page_summary():
    from financeiro_ml.canary import probe_billing_period_details

    class BillingPeriodClient:
        async def get_billing_period_details(self, *, key, document_type, limit, from_id):
            assert key == "2026-06-01"
            assert document_type == "BILL"
            assert limit == 10
            assert from_id == 0
            return {
                "total": 2,
                "last_id": 123,
                "results": [{"id": 122}, {"id": 123}],
            }

    result = await probe_billing_period_details(
        client=BillingPeriodClient(),
        key="2026-06-01",
        limit=10,
        from_id=0,
    )

    assert result.status == "ok"
    assert result.total_results == 2
    assert result.next_from_id == 123
    assert result.sample_count == 2


@pytest.mark.asyncio
async def test_process_canary_pending_marks_done(fin_db):
    db, m = fin_db
    from financeiro_ml.canary import process_canary_pending
    from financeiro_ml.models_v2 import MLCanaryRun, MLCanaryPendingTask

    class ShipmentClient:
        async def get_shipment(self, shipment_id):
            return {"id": shipment_id, "shipping_option": {"cost": 1, "list_cost": 2}}

    s = db.FinSessionLocal()
    try:
        run = MLCanaryRun(seller_id=1, day=date(2026, 6, 1), status="ok")
        s.add(run)
        s.commit()
        s.add(MLCanaryPendingTask(run_id=run.id, seller_id=1, kind="seller_shipping", ref_id="5001"))
        s.commit()
        run_id = run.id
    finally:
        s.close()

    result = await process_canary_pending(
        session_factory=db.FinSessionLocal,
        client=ShipmentClient(),
        run_id=run_id,
        max_tasks=1,
    )

    assert result.status == "ok"
    assert result.succeeded == 1
    s = db.FinSessionLocal()
    try:
        task = s.query(m.MLCanaryPendingTask).filter_by(run_id=run_id).first()
        assert task.status == "done"
        assert '"shipping_option"' in task.result_json
    finally:
        s.close()


@pytest.mark.asyncio
async def test_process_canary_pending_stops_on_429(fin_db):
    db, m = fin_db
    from financeiro_ml.canary import process_canary_pending
    from financeiro_ml.client import MLRateLimited
    from financeiro_ml.models_v2 import MLCanaryRun, MLCanaryPendingTask

    class RateLimitedShipmentClient:
        async def get_shipment(self, shipment_id):
            raise MLRateLimited("/shipments/5001")

    s = db.FinSessionLocal()
    try:
        run = MLCanaryRun(seller_id=1, day=date(2026, 6, 1), status="ok")
        s.add(run)
        s.commit()
        s.add(MLCanaryPendingTask(run_id=run.id, seller_id=1, kind="seller_shipping", ref_id="5001"))
        s.add(MLCanaryPendingTask(run_id=run.id, seller_id=1, kind="seller_shipping", ref_id="5002"))
        s.commit()
        run_id = run.id
    finally:
        s.close()

    result = await process_canary_pending(
        session_factory=db.FinSessionLocal,
        client=RateLimitedShipmentClient(),
        run_id=run_id,
        max_tasks=2,
    )

    assert result.status == "blocked_rate_limit"
    assert result.rate_limited is True
    assert result.processed == 1
    s = db.FinSessionLocal()
    try:
        run = s.query(m.MLCanaryRun).filter_by(id=run_id).first()
        tasks = s.query(m.MLCanaryPendingTask).order_by(m.MLCanaryPendingTask.id).all()
        assert run.status == "blocked_rate_limit"
        assert tasks[0].status == "rate_limited"
        assert tasks[1].status == "pending"
    finally:
        s.close()
