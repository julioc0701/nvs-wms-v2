import pytest
from datetime import date, datetime
from decimal import Decimal


@pytest.mark.asyncio
async def test_resumo_reads_cache_no_sync(fin_db, monkeypatch):
    db, m = fin_db
    # popula cache de 1 seller
    s = db.FinSessionLocal()
    s.add(m.MLOrderCache(seller_id=1, order_id=100, date_created=datetime(2026,5,20,10),
                         date_closed=datetime(2026,5,20,11), status="paid",
                         produto_total=Decimal("100"), raw_json="{}", synced_at=datetime.utcnow(),
                         breakdown_bucket="outros"))
    s.add(m.MLOrderItemCache(seller_id=1, order_id=100, item_id="MLB1", title="A",
                             seller_sku="X", quantity=1, unit_price=Decimal("100")))
    s.commit(); s.close()

    # garante que NENHUM sync é chamado
    import financeiro_ml.router as r
    called = {"sync": False}
    if hasattr(r, "ensure_period_synced"):
        monkeypatch.setattr(r, "ensure_period_synced",
                            lambda *a, **k: (_ for _ in ()).throw(AssertionError("não pode sincronizar")))

    from financeiro_ml.router import FilterParams, get_resumo
    params = FilterParams(seller_id=1, data_inicio=date(2026,5,20), data_fim=date(2026,5,20))
    resp = await get_resumo(params, operator_id=1)
    assert resp["cards"]["vendas_aprovadas"] == "100.00" or resp["cards"]["vendas_aprovadas"] == 100.0
