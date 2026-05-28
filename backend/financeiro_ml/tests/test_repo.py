from decimal import Decimal
from datetime import datetime


def _row(seller_id=1, order_id=100, status="paid", produto="100"):
    return {
        "seller_id": seller_id, "order_id": order_id,
        "date_created": datetime(2026,5,20,10), "date_closed": datetime(2026,5,20,11),
        "date_last_updated": datetime(2026,5,20,11,30), "status": status, "status_detail": None,
        "produto_total": Decimal(produto), "frete_comprador": Decimal("0"),
        "frete_vendedor": Decimal("0"), "tarifa_bruta": Decimal("0"), "tarifa_refund": Decimal("0"),
        "refund_amount_partial": Decimal("0"), "cupom_seller": Decimal("0"),
        "modalidade_anuncio": "gold_pro", "logistic_type": None, "shipping_mode": None,
        "shipment_id": None, "breakdown_bucket": "outros", "frete_incerto": False,
        "items": [{"seller_id": seller_id, "order_id": order_id, "item_id": "MLB1",
                   "title": "A", "seller_sku": "X", "quantity": 1, "unit_price": Decimal("100"),
                   "category_id": "CAT1"}],
    }


def test_upsert_inserts_new(fin_db):
    db, m = fin_db
    from financeiro_ml.repo import upsert_order_row
    upsert_order_row(db.FinSessionLocal, _row())
    s = db.FinSessionLocal()
    assert s.query(m.MLOrderCache).count() == 1
    assert s.query(m.MLOrderItemCache).count() == 1
    s.close()


def test_upsert_idempotent_updates_in_place(fin_db):
    db, m = fin_db
    from financeiro_ml.repo import upsert_order_row
    upsert_order_row(db.FinSessionLocal, _row(status="paid", produto="100"))
    upsert_order_row(db.FinSessionLocal, _row(status="cancelled", produto="100"))
    s = db.FinSessionLocal()
    assert s.query(m.MLOrderCache).count() == 1            # não duplica
    assert s.query(m.MLOrderCache).first().status == "cancelled"  # status atualizado
    assert s.query(m.MLOrderItemCache).count() == 1         # itens não duplicam
    s.close()


def test_upsert_isolates_by_seller(fin_db):
    db, m = fin_db
    from financeiro_ml.repo import upsert_order_row
    upsert_order_row(db.FinSessionLocal, _row(seller_id=1, order_id=100))
    upsert_order_row(db.FinSessionLocal, _row(seller_id=2, order_id=100))
    s = db.FinSessionLocal()
    assert s.query(m.MLOrderCache).count() == 2  # mesmo order_id, sellers diferentes
    s.close()
