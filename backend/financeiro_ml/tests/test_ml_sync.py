import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

from database import SessionLocal, init_db
from financeiro_ml.models import MLOrderCache, MLOrderItemCache
from financeiro_ml.sync import _days_needing_sync, _date_range, _save_order


def test_date_range_inclusive():
    days = _date_range(date(2026, 5, 1), date(2026, 5, 3))
    assert days == [date(2026, 5, 1), date(2026, 5, 2), date(2026, 5, 3)]


def test_today_stale_5min_needs_sync():
    """Hoje: cache de 5 minutos. Re-sync se passou desse limite."""
    today = date.today()
    statuses = {today: MagicMock(last_synced_at=datetime.utcnow() - timedelta(minutes=6), status="ok")}
    result = _days_needing_sync([today], statuses)
    assert result == [today]


def test_today_fresh_under_5min_skipped():
    """Hoje cacheado há menos de 5 minutos: skip (cache hit)."""
    today = date.today()
    statuses = {today: MagicMock(last_synced_at=datetime.utcnow() - timedelta(minutes=2), status="ok")}
    result = _days_needing_sync([today], statuses)
    assert result == []


def test_old_day_not_needed_if_ok():
    old = date.today() - timedelta(days=30)
    statuses = {old: MagicMock(last_synced_at=datetime.utcnow() - timedelta(days=29), status="ok")}
    result = _days_needing_sync([old], statuses)
    assert result == []


def test_old_day_failed_needs_retry():
    old = date.today() - timedelta(days=30)
    statuses = {old: MagicMock(last_synced_at=datetime.utcnow() - timedelta(days=29), status="failed")}
    result = _days_needing_sync([old], statuses)
    assert result == [old]


def test_recent_day_stale_24h_needs_sync():
    recent = date.today() - timedelta(days=3)
    statuses = {recent: MagicMock(last_synced_at=datetime.utcnow() - timedelta(hours=25), status="ok")}
    result = _days_needing_sync([recent], statuses)
    assert result == [recent]


def test_recent_day_fresh_skipped():
    recent = date.today() - timedelta(days=3)
    statuses = {recent: MagicMock(last_synced_at=datetime.utcnow() - timedelta(hours=5), status="ok")}
    result = _days_needing_sync([recent], statuses)
    assert result == []


def test_missing_day_needs_sync():
    target = date.today() - timedelta(days=2)
    result = _days_needing_sync([target], {})
    assert result == [target]


def _order_payload(order_id, *, status="paid", sku="SKU_ROOT", variation_id=None):
    item = {
        "id": "MLB123",
        "title": "Produto Teste",
        "seller_custom_field": sku,
        "seller_sku": sku,
        "category_id": "CAT",
    }
    if variation_id is not None:
        item["variation_id"] = variation_id
        item["seller_sku"] = f"MLB123_{variation_id}"
        item["seller_custom_field"] = None
    return {
        "id": order_id,
        "date_created": "2026-05-26T12:00:00.000-03:00",
        "date_closed": "2026-05-26T12:01:00.000-03:00",
        "status": status,
        "status_detail": None,
        "shipping": {"id": 999},
        "payments": [],
        "tags": [],
        "order_items": [{
            "item": item,
            "quantity": 1,
            "unit_price": 100,
            "sale_fee": 10,
            "listing_type_id": "gold_pro",
        }],
    }


class FakeClient:
    async def get_shipment(self, shipment_id):
        return {
            "id": shipment_id,
            "logistic_type": "fulfillment",
            "mode": "me2",
            "shipping_option": {"cost": 0, "list_cost": 0},
        }

    async def get_shipment_costs(self, shipment_id):
        return {}

    async def get_order_discounts(self, order_id):
        return {"details": []}

    async def get_variation(self, item_id, variation_id):
        return {"id": variation_id, "seller_custom_field": "SKU_VARIACAO"}


@pytest.fixture(autouse=True)
def setup_db_for_save_order():
    init_db()
    def _clean():
        with SessionLocal() as s:
            s.query(MLOrderItemCache).filter(MLOrderItemCache.order_id.in_([123, 456])).delete(synchronize_session=False)
            s.query(MLOrderCache).filter(MLOrderCache.order_id.in_([123, 456])).delete(synchronize_session=False)
            s.commit()
    _clean()
    yield
    _clean()  # teardown: não deixa lixo no DB


@pytest.mark.asyncio
async def test_save_order_updates_existing_status_on_refresh():
    client = FakeClient()
    await _save_order(client, _order_payload(123, status="paid"))
    await _save_order(client, _order_payload(123, status="cancelled"), force_refresh=True)

    with SessionLocal() as s:
        row = s.query(MLOrderCache).filter_by(order_id=123).one()
        assert row.status == "cancelled"
        assert row.tarifa_bruta == Decimal("10.00")


@pytest.mark.asyncio
async def test_save_order_uses_variation_seller_sku():
    await _save_order(FakeClient(), _order_payload(456, variation_id=789))

    with SessionLocal() as s:
        item = s.query(MLOrderItemCache).filter_by(order_id=456).one()
        assert item.seller_sku == "SKU_VARIACAO"


@pytest.mark.asyncio
async def test_sync_day_delta_passa_last_updated():
    """Em modo delta, _sync_single_day repassa last_updated_from pro search_orders."""
    from financeiro_ml.sync import _sync_single_day
    from financeiro_ml.models import MLDaySyncStatus

    captured = {}

    class Cap:
        async def search_orders(self, **kw):
            captured.update(kw)
            return {"results": [], "paging": {"total": 0}}

    cursor = datetime(2026, 5, 28, 10, 0, 0)
    d = date(2099, 1, 2)
    try:
        await _sync_single_day(Cap(), d, last_updated_from=cursor)
        assert captured.get("last_updated_from") == cursor
    finally:
        with SessionLocal() as s:
            s.query(MLDaySyncStatus).filter_by(day=d).delete(synchronize_session=False)
            s.commit()


@pytest.mark.asyncio
async def test_sync_day_429_marca_rate_limited_e_propaga():
    """Circuit breaker: 429 marca o dia como rate_limited e relança MLRateLimited."""
    from financeiro_ml.sync import _sync_single_day
    from financeiro_ml.client import MLRateLimited
    from financeiro_ml.models import MLDaySyncStatus

    class RL:
        async def search_orders(self, **kw):
            raise MLRateLimited("/orders/search")

    d = date(2099, 1, 1)
    try:
        with pytest.raises(MLRateLimited):
            await _sync_single_day(RL(), d)
        with SessionLocal() as s:
            st = s.query(MLDaySyncStatus).filter_by(day=d).one()
            assert st.status == "rate_limited"
    finally:
        with SessionLocal() as s:
            s.query(MLDaySyncStatus).filter_by(day=d).delete(synchronize_session=False)
            s.commit()
