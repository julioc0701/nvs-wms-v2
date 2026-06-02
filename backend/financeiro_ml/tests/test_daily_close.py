from datetime import date, datetime, timedelta

import pytest


class FakeDailyClient:
    def __init__(self):
        self.order_calls = 0
        self.billing_calls = []

    async def search_orders(self, *, date_from, date_to, offset=0, limit=50, last_updated_from=None):
        self.order_calls += 1
        if offset > 0:
            return {"results": []}
        return {"results": [_order(101), _order(102)]}

    async def get_billing_period_details(self, *, key, document_type, limit, from_id):
        self.billing_calls.append((key, document_type, limit, from_id))
        return {
            "total": 2,
            "last_id": 20 if from_id == 0 else from_id,
            "results": [_billing_line(10), _billing_line(20)] if from_id == 0 else [],
        }

    async def get_billing_order_details(self, *, seller_id, order_ids):
        self.billing_calls.append(("order_details", seller_id, tuple(order_ids)))
        return {
            "results": [
                {
                    "order_id": order_id,
                    "details": [_billing_line(order_id + 10000, order_id=order_id)],
                }
                for order_id in order_ids
            ]
        }


class RateLimitedOrdersClient:
    async def search_orders(self, **kwargs):
        from financeiro_ml.client import MLRateLimited
        raise MLRateLimited("/orders/search")


def _order(order_id):
    return {
        "id": order_id,
        "status": "paid",
        "tags": [],
        "shipping": {"id": order_id + 9000},
        "payments": [{"shipping_cost": 12.5}],
        "order_items": [{
            "item": {"id": f"MLB{order_id}", "title": "Item", "seller_sku": f"SKU{order_id}"},
            "unit_price": 100,
            "quantity": 1,
            "sale_fee": 10,
        }],
        "date_created": "2026-06-01T10:00:00.000-03:00",
    }


def _billing_line(detail_id, *, order_id=101):
    return {
        "charge_info": {
            "detail_id": detail_id,
            "creation_date_time": "2026-06-01T10:00:00",
            "transaction_detail": "Tarifa de envio",
            "detail_amount": 8.05,
            "detail_type": "CHARGE",
            "detail_sub_type": "CME",
        },
        "sales_info": {"order_id": order_id},
        "shipping_info": {"shipment_id": order_id + 9000},
        "marketplace_info": {"marketplace": "SHIPPING"},
    }


@pytest.mark.asyncio
async def test_daily_close_cycle_persists_orders_and_billing(fin_db):
    db, m = fin_db
    from financeiro_ml.daily_close import run_daily_close_cycle

    result = await run_daily_close_cycle(
        db.FinSessionLocal,
        client=FakeDailyClient(),
        seller_id=1,
        day=date(2026, 6, 1),
        max_order_pages=5,
        billing_pages_per_cycle=1,
        billing_sleep_sec=0,
    )

    assert result.status == "consolidated"
    assert result.phase == "consolidated"
    assert result.orders_count == 2
    assert result.billing_job_id is not None
    assert result.billing_pages_done == 1
    assert result.billing_lines_done == 2

    s = db.FinSessionLocal()
    try:
        job = s.query(m.MLDailyCloseJob).first()
        assert job.orders_run_id is not None
        assert job.billing_job_id is not None
        assert s.query(m.MLCanaryOrderSnapshot).count() == 2
        assert s.query(m.MLBillingPeriodLine).count() == 2
        billing_job = s.query(m.MLBillingPeriodJob).filter_by(id=job.billing_job_id).first()
        assert billing_job.period_key == "2026-06-01"
        assert billing_job.document_type == "ORDER_DETAILS"
    finally:
        s.close()


@pytest.mark.asyncio
async def test_daily_close_rate_limit_sets_cooldown(fin_db):
    db, m = fin_db
    from financeiro_ml.daily_close import run_daily_close_cycle

    result = await run_daily_close_cycle(
        db.FinSessionLocal,
        client=RateLimitedOrdersClient(),
        seller_id=1,
        day=date(2026, 6, 1),
        cooldown_min=15,
    )

    assert result.status == "paused"
    assert result.phase == "orders"
    assert result.next_retry_at is not None
    assert result.next_retry_at > datetime.utcnow() + timedelta(minutes=10)

    s = db.FinSessionLocal()
    try:
        job = s.query(m.MLDailyCloseJob).first()
        assert job.status == "paused"
        assert job.next_retry_at is not None
    finally:
        s.close()


def test_daily_close_period_key_and_yesterday(monkeypatch):
    from zoneinfo import ZoneInfo
    from financeiro_ml.daily_close import period_key_for, yesterday_brt

    assert period_key_for(date(2026, 6, 2)) == "2026-06-01"
    now = datetime(2026, 6, 3, 3, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
    assert yesterday_brt(now) == date(2026, 6, 2)


@pytest.mark.asyncio
async def test_daily_close_force_orders_clears_stale_billing_job(fin_db):
    db, m = fin_db
    from financeiro_ml.daily_close import run_daily_close_cycle

    first = await run_daily_close_cycle(
        db.FinSessionLocal,
        client=FakeDailyClient(),
        seller_id=1,
        day=date(2026, 6, 1),
        billing_pages_per_cycle=1,
        billing_sleep_sec=0,
    )

    s = db.FinSessionLocal()
    try:
        stale_billing_job_id = first.billing_job_id
        assert stale_billing_job_id is not None
    finally:
        s.close()

    second = await run_daily_close_cycle(
        db.FinSessionLocal,
        client=FakeDailyClient(),
        seller_id=1,
        day=date(2026, 6, 1),
        billing_pages_per_cycle=1,
        billing_sleep_sec=0,
        force_orders=True,
    )

    s = db.FinSessionLocal()
    try:
        job = s.query(m.MLDailyCloseJob).filter_by(id=first.job_id).first()
        assert second.billing_job_id != stale_billing_job_id
        assert job.billing_job_id == second.billing_job_id
        assert job.status == "consolidated"
    finally:
        s.close()


@pytest.mark.asyncio
async def test_daily_close_force_orders_creates_new_orders_run(fin_db):
    db, m = fin_db
    from financeiro_ml.daily_close import run_daily_close_cycle

    first = await run_daily_close_cycle(
        db.FinSessionLocal,
        client=FakeDailyClient(),
        seller_id=1,
        day=date(2026, 6, 1),
        billing_pages_per_cycle=1,
        billing_sleep_sec=0,
    )
    s = db.FinSessionLocal()
    try:
        first_orders_run_id = s.query(m.MLDailyCloseJob).filter_by(id=first.job_id).first().orders_run_id
    finally:
        s.close()

    second = await run_daily_close_cycle(
        db.FinSessionLocal,
        client=FakeDailyClient(),
        seller_id=1,
        day=date(2026, 6, 1),
        billing_pages_per_cycle=1,
        billing_sleep_sec=0,
        force_orders=True,
    )

    s = db.FinSessionLocal()
    try:
        job = s.query(m.MLDailyCloseJob).filter_by(id=first.job_id).first()
        assert second.job_id == first.job_id
        assert job.orders_run_id is not None
        assert job.orders_run_id != first_orders_run_id
        assert s.query(m.MLCanaryRun).count() == 2
    finally:
        s.close()


def test_daily_close_reconciliation_audit_counts_billing_matches(fin_db):
    db, m = fin_db
    from financeiro_ml.billing_reconciliation import audit_daily_close_reconciliation

    s = db.FinSessionLocal()
    try:
        daily = m.MLDailyCloseJob(
            seller_id=1,
            day=date(2026, 6, 1),
            status="consolidated",
            phase="consolidated",
            orders_run_id=10,
            billing_job_id=20,
        )
        billing_job = m.MLBillingPeriodJob(
            id=20,
            seller_id=1,
            period_key="2026-06-01",
            document_type="BILL",
            status="done",
            limit=100,
        )
        s.add_all([daily, billing_job])
        s.flush()
        s.add_all([
            m.MLCanaryOrderSnapshot(
                run_id=10,
                seller_id=1,
                order_id=101,
                shipment_id=9101,
                order_status="paid",
                ingest_status="snapshot",
                missing_flags="[]",
                raw_json="{}",
            ),
            m.MLCanaryOrderSnapshot(
                run_id=10,
                seller_id=1,
                order_id=102,
                shipment_id=9102,
                order_status="paid",
                ingest_status="snapshot",
                missing_flags='["pending_seller_shipping"]',
                raw_json="{}",
            ),
            m.MLBillingPeriodLine(
                seller_id=1,
                detail_id=500,
                period_key="2026-06-01",
                document_type="BILL",
                detail_amount=8.05,
                order_id=101,
                shipment_id=9101,
                raw_json="{}",
            ),
        ])
        s.commit()
        job_id = daily.id
    finally:
        s.close()

    result = audit_daily_close_reconciliation(db.FinSessionLocal, job_id=job_id)

    assert result["orders_total"] == 2
    assert result["billing_lines_total"] == 1
    assert result["matched_orders"] == 1
    assert result["missing_orders"] == 1
    assert result["shipments_to_probe_sample"] == [9102]


def test_billing_linkage_audit_finds_candidate_paths_in_raw_json(fin_db):
    db, m = fin_db
    from financeiro_ml.billing_reconciliation import audit_billing_linkage_fields

    s = db.FinSessionLocal()
    try:
        daily = m.MLDailyCloseJob(
            seller_id=1,
            day=date(2026, 6, 1),
            status="consolidated",
            phase="consolidated",
            orders_run_id=10,
            billing_job_id=20,
        )
        billing_job = m.MLBillingPeriodJob(
            id=20,
            seller_id=1,
            period_key="2026-06-01",
            document_type="BILL",
            status="done",
            limit=100,
        )
        s.add_all([daily, billing_job])
        s.flush()
        s.add_all([
            m.MLCanaryOrderSnapshot(
                run_id=10,
                seller_id=1,
                order_id=101,
                shipment_id=9101,
                order_status="paid",
                ingest_status="snapshot",
                missing_flags="[]",
                raw_json="{}",
            ),
            m.MLBillingPeriodLine(
                seller_id=1,
                detail_id=500,
                period_key="2026-06-01",
                document_type="BILL",
                detail_amount=8.05,
                order_id=999,
                shipment_id=9999,
                raw_json='{"sales_info":{"real_order_id":"101"},"shipping_info":{"real_shipment_id":"9101"},"charge_info":{"detail_id":500}}',
            ),
        ])
        s.commit()
        job_id = daily.id
    finally:
        s.close()

    result = audit_billing_linkage_fields(db.FinSessionLocal, job_id=job_id)

    assert result["stored_order_id_overlap_count"] == 0
    assert result["stored_shipment_id_overlap_count"] == 0
    assert result["order_candidate_paths"][0]["path"] == "sales_info.real_order_id"
    assert result["shipment_candidate_paths"][0]["path"] == "shipping_info.real_shipment_id"


def test_daily_close_order_id_diff_compares_excel_reference(fin_db):
    db, m = fin_db
    from financeiro_ml.billing_reconciliation import compare_daily_close_order_ids

    s = db.FinSessionLocal()
    try:
        daily = m.MLDailyCloseJob(
            seller_id=1,
            day=date(2026, 6, 1),
            status="consolidated",
            phase="consolidated",
            orders_run_id=10,
        )
        s.add(daily)
        s.flush()
        s.add_all([
            m.MLCanaryOrderSnapshot(
                run_id=10,
                seller_id=1,
                order_id=101,
                shipment_id=9101,
                order_status="paid",
                ingest_status="snapshot",
                missing_flags="[]",
                raw_json="{}",
            ),
            m.MLCanaryOrderSnapshot(
                run_id=10,
                seller_id=1,
                order_id=102,
                shipment_id=9102,
                order_status="paid",
                ingest_status="snapshot",
                missing_flags="[]",
                raw_json='{"date_created":"2026-06-01T00:10:00.000-03:00","date_closed":"2026-06-01T00:12:00.000-03:00","date_last_updated":"2026-06-01T00:13:00.000-03:00","status":"paid"}',
            ),
        ])
        s.commit()
        job_id = daily.id
    finally:
        s.close()

    result = compare_daily_close_order_ids(
        db.FinSessionLocal,
        job_id=job_id,
        reference_order_ids=["#101", "#103"],
    )

    assert result["ml_orders_count"] == 2
    assert result["reference_orders_count"] == 2
    assert result["matched_count"] == 1
    assert result["only_ml_sample"] == [102]
    assert result["only_ml_details_sample"][0]["date_created"] == "2026-06-01T00:10:00.000-03:00"
    assert result["only_ml_details_sample"][0]["date_last_updated"] == "2026-06-01T00:13:00.000-03:00"
    assert result["only_reference_sample"] == [103]
