import pytest
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, init_db
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


def test_non_master_is_forbidden(client):
    r = client.get("/api/financeiro-ml/skus", headers=WORKER_HEADERS)
    assert r.status_code == 403
