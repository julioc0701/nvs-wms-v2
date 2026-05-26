import pytest
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, init_db
from models import Operator
from financeiro_ml.models import SkuFinanceiro


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    with SessionLocal() as s:
        if not s.query(Operator).filter_by(id=1).first():
            s.add(Operator(id=1, name="Test", badge="T", pin_code="1234"))
            s.commit()
        s.query(SkuFinanceiro).delete()
        s.commit()


@pytest.fixture
def client():
    return TestClient(app)


def test_put_sku_creates(client):
    r = client.put("/api/financeiro-ml/skus/SKU_TEST",
                    json={"custo_unit": "10.50", "imposto_pct": "8.00"})
    assert r.status_code == 200
    with SessionLocal() as s:
        assert s.query(SkuFinanceiro).filter_by(sku="SKU_TEST").first() is not None


def test_get_skus_lists(client):
    client.put("/api/financeiro-ml/skus/A", json={"custo_unit": "1", "imposto_pct": "9"})
    client.put("/api/financeiro-ml/skus/B", json={"custo_unit": "2", "imposto_pct": "9"})
    r = client.get("/api/financeiro-ml/skus")
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 2


def test_delete_sku(client):
    client.put("/api/financeiro-ml/skus/X", json={"custo_unit": "1", "imposto_pct": "9"})
    r = client.delete("/api/financeiro-ml/skus/X")
    assert r.status_code == 200
    r2 = client.delete("/api/financeiro-ml/skus/X")
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
        })
    assert r.status_code == 200
    body = r.json()
    assert "cards" in body
    assert "pizza" in body
    assert "tabela" in body
