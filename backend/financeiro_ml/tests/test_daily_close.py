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


def _billing_line(detail_id):
    return {
        "charge_info": {
            "detail_id": detail_id,
            "creation_date_time": "2026-06-01T10:00:00",
            "transaction_detail": "Tarifa de envio",
            "detail_amount": 8.05,
            "detail_type": "CHARGE",
            "detail_sub_type": "CME",
        },
        "sales_info": {"order_id": 101},
        "shipping_info": {"shipment_id": 9101},
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

    assert result.status == "running"
    assert result.phase == "billing"
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
