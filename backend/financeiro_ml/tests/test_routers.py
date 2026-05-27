import pytest
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, init_db
from datetime import datetime
from decimal import Decimal
from models import Operator
from financeiro_ml.models import MLOrderCache, MLOrderItemCache, SkuFinanceiro


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    with SessionLocal() as s:
        if not s.query(Operator).filter_by(id=999).first():
            s.add(Operator(id=999, name="Master", badge="TEST_MASTER", pin_code="1234"))
        if not s.query(Operator).filter_by(id=998).first():
            s.add(Operator(id=998, name="Worker", badge="TEST_WORKER", pin_code="1234"))
        s.query(MLOrderItemCache).filter(MLOrderItemCache.order_id.in_([101, 202])).delete(synchronize_session=False)
        s.query(MLOrderCache).filter(MLOrderCache.order_id.in_([101, 202])).delete(synchronize_session=False)
        s.query(SkuFinanceiro).filter(
            SkuFinanceiro.sku.in_(["SKU_TEST", "A", "B", "X", "SKU_A", "SKU_B"])
        ).delete(synchronize_session=False)
        s.commit()


@pytest.fixture
def client():
    return TestClient(app)


MASTER_HEADERS = {"X-Operator-Id": "999"}
WORKER_HEADERS = {"X-Operator-Id": "998"}


def test_put_sku_creates(client):
    r = client.put("/api/financeiro-ml/skus/SKU_TEST",
                    json={"custo_unit": "10.50", "imposto_pct": "8.00"},
                    headers=MASTER_HEADERS)
    assert r.status_code == 200
    with SessionLocal() as s:
        assert s.query(SkuFinanceiro).filter_by(sku="SKU_TEST").first() is not None


def test_get_skus_lists(client):
    client.put("/api/financeiro-ml/skus/A", json={"custo_unit": "1", "imposto_pct": "9"}, headers=MASTER_HEADERS)
    client.put("/api/financeiro-ml/skus/B", json={"custo_unit": "2", "imposto_pct": "9"}, headers=MASTER_HEADERS)
    r = client.get("/api/financeiro-ml/skus", headers=MASTER_HEADERS)
    assert r.status_code == 200
    skus = {item["sku"] for item in r.json()["items"]}
    assert "A" in skus and "B" in skus


def test_delete_sku(client):
    client.put("/api/financeiro-ml/skus/X", json={"custo_unit": "1", "imposto_pct": "9"}, headers=MASTER_HEADERS)
    r = client.delete("/api/financeiro-ml/skus/X", headers=MASTER_HEADERS)
    assert r.status_code == 200
    r2 = client.delete("/api/financeiro-ml/skus/X", headers=MASTER_HEADERS)
    assert r2.status_code == 404


from unittest.mock import patch, AsyncMock
from datetime import date


def test_resumo_returns_cards(client):
    async def fake_sync(*a, **k):
        return {"dias_sincronizados": 0, "dias_falhos": 0, "total_orders": 0}
    with patch("financeiro_ml.router.ensure_period_synced", new=AsyncMock(side_effect=fake_sync)):
        r = client.post("/api/financeiro-ml/resumo", json={
            "data_inicio": str(date.today()),
            "data_fim": str(date.today()),
        }, headers=MASTER_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert "cards" in body
    assert "pizza" in body
    assert "tabela" in body


def _insert_order(session, order_id, sku, produto_total):
    session.add(MLOrderCache(
        order_id=order_id,
        date_created=datetime(2026, 5, 26, 12, 0),
        date_closed=datetime(2026, 5, 26, 12, 5),
        status="paid",
        status_detail=None,
        produto_total=Decimal(str(produto_total)),
        frete_comprador=Decimal("0"),
        frete_vendedor=Decimal("0"),
        tarifa_bruta=Decimal("0"),
        tarifa_refund=Decimal("0"),
        refund_amount_partial=Decimal("0"),
        cupom_seller=Decimal("0"),
        modalidade_anuncio="gold_pro",
        logistic_type="fulfillment",
        shipping_mode="me2",
        shipment_id=order_id,
        breakdown_bucket="full",
        raw_json="{}",
        synced_at=datetime.utcnow(),
    ))
    session.add(MLOrderItemCache(
        order_id=order_id,
        item_id=f"MLB{order_id}",
        title=f"Produto {sku}",
        seller_sku=sku,
        quantity=1,
        unit_price=Decimal(str(produto_total)),
        category_id=None,
    ))


def test_resumo_sku_filter_limits_cards_and_rows(client):
    with SessionLocal() as s:
        s.add(SkuFinanceiro(sku="SKU_A", custo_unit=Decimal("10"), imposto_pct=Decimal("0"), updated_by=999))
        s.add(SkuFinanceiro(sku="SKU_B", custo_unit=Decimal("20"), imposto_pct=Decimal("0"), updated_by=999))
        _insert_order(s, 101, "SKU_A", "100")
        _insert_order(s, 202, "SKU_B", "200")
        s.commit()

    with patch("financeiro_ml.router.ensure_period_synced", new=AsyncMock(return_value={
        "dias_sincronizados": 0, "dias_falhos": 0, "total_orders": 0,
    })):
        r = client.post("/api/financeiro-ml/resumo", json={
            "data_inicio": "2026-05-26",
            "data_fim": "2026-05-26",
            "sku": "SKU_A",
        }, headers=MASTER_HEADERS)

    assert r.status_code == 200
    body = r.json()
    assert body["cards"]["vendas_aprovadas"] == 100
    assert body["pagination"]["total"] == 1
    assert body["tabela"][0]["sku"] == "SKU_A"


def test_export_accepts_more_than_page_size_limit(client):
    with patch("financeiro_ml.router.ensure_period_synced", new=AsyncMock(return_value={
        "dias_sincronizados": 0, "dias_falhos": 0, "total_orders": 0,
    })):
        r = client.post("/api/financeiro-ml/export?formato=csv", json={
            "data_inicio": str(date.today()),
            "data_fim": str(date.today()),
        }, headers=MASTER_HEADERS)

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")


def test_non_master_is_forbidden(client):
    r = client.get("/api/financeiro-ml/skus", headers=WORKER_HEADERS)
    assert r.status_code == 403
