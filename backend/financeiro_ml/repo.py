"""Escrita no cache. Upsert idempotente por (seller_id, order_id). 1 commit/order."""
from datetime import datetime


def upsert_order_row(session_factory, row: dict) -> None:
    from financeiro_ml.models_v2 import MLOrderCache, MLOrderItemCache
    import json
    s = session_factory()
    try:
        existing = s.query(MLOrderCache).filter_by(
            seller_id=row["seller_id"], order_id=row["order_id"]).first()
        fields = dict(
            date_created=row["date_created"], date_closed=row["date_closed"],
            date_last_updated=row["date_last_updated"], status=row["status"],
            status_detail=row["status_detail"], produto_total=row["produto_total"],
            frete_comprador=row["frete_comprador"], frete_vendedor=row["frete_vendedor"],
            tarifa_bruta=row["tarifa_bruta"], tarifa_refund=row["tarifa_refund"],
            refund_amount_partial=row["refund_amount_partial"], cupom_seller=row["cupom_seller"],
            modalidade_anuncio=row["modalidade_anuncio"], logistic_type=row["logistic_type"],
            shipping_mode=row["shipping_mode"], shipment_id=row["shipment_id"],
            breakdown_bucket=row["breakdown_bucket"],
            frete_incerto=1 if row.get("frete_incerto") else 0,
            synced_at=datetime.utcnow(),
        )
        if existing is None:
            s.add(MLOrderCache(seller_id=row["seller_id"], order_id=row["order_id"],
                               raw_json=row.get("raw_json", "{}"), **fields))
        else:
            for k, v in fields.items():
                setattr(existing, k, v)
            s.query(MLOrderItemCache).filter_by(
                seller_id=row["seller_id"], order_id=row["order_id"]).delete()
        for it in row["items"]:
            s.add(MLOrderItemCache(**it))
        s.commit()
    finally:
        s.close()
