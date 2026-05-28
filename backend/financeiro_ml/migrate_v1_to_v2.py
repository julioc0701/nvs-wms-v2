"""Migração one-shot: copia dados do .db v1 (sem seller_id) -> schema v2 isolado.

NÃO re-busca nada no ML (zero risco de 429). Carimba seller_id do seller default.
Regra de segurança: status de dia só vira 'ok' se já era 'ok' no v1; o resto
(ausente/falho) entra como 'imported_unverified' — não conta como fresco.
"""
from datetime import datetime
from sqlalchemy import create_engine, text


def _parse_dt(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    return datetime.fromisoformat(str(v))


def migrate(*, v1_db_path: str, seller_id: int) -> dict:
    from financeiro_ml.db import FinSessionLocal
    from financeiro_ml.models_v2 import (
        MLOrderCache, MLOrderItemCache, MLDaySyncStatus, MLTokens,
    )
    src = create_engine(f"sqlite:///{v1_db_path}", connect_args={"check_same_thread": False})
    report = {"orders": 0, "orders_src": 0, "items": 0, "days": 0, "tokens": 0}

    with src.connect() as c:
        order_rows = c.execute(text("SELECT * FROM ml_orders_cache")).mappings().all()
        item_rows = c.execute(text("SELECT * FROM ml_order_items_cache")).mappings().all()
        day_rows = c.execute(text("SELECT * FROM ml_day_sync_status")).mappings().all()
        try:
            tok_rows = c.execute(text("SELECT * FROM ml_tokens")).mappings().all()
        except Exception:
            tok_rows = []
    report["orders_src"] = len(order_rows)

    s = FinSessionLocal()
    try:
        for r in order_rows:
            s.merge(MLOrderCache(
                seller_id=seller_id, order_id=r["order_id"],
                date_created=_parse_dt(r["date_created"]),
                date_closed=_parse_dt(r["date_closed"]),
                date_last_updated=_parse_dt(r["date_last_updated"]),
                status=r["status"], status_detail=r["status_detail"],
                produto_total=r["produto_total"] or 0,
                frete_comprador=r["frete_comprador"] or 0,
                frete_vendedor=r["frete_vendedor"] or 0,
                tarifa_bruta=r["tarifa_bruta"] or 0,
                tarifa_refund=r["tarifa_refund"] or 0,
                refund_amount_partial=r["refund_amount_partial"] or 0,
                cupom_seller=r["cupom_seller"] or 0,
                modalidade_anuncio=r["modalidade_anuncio"],
                logistic_type=r["logistic_type"], shipping_mode=r["shipping_mode"],
                shipment_id=r["shipment_id"], breakdown_bucket=r["breakdown_bucket"],
                frete_incerto=0,
                raw_json=r["raw_json"] or "{}",
                synced_at=_parse_dt(r["synced_at"]) or datetime.utcnow(),
            ))
            report["orders"] += 1

        for r in item_rows:
            s.add(MLOrderItemCache(
                seller_id=seller_id, order_id=r["order_id"], item_id=r["item_id"],
                title=r["title"] or "", seller_sku=r["seller_sku"],
                quantity=r["quantity"] or 0, unit_price=r["unit_price"] or 0,
                category_id=r["category_id"],
            ))
            report["items"] += 1

        for r in day_rows:
            status = "ok" if r["status"] == "ok" else "imported_unverified"
            s.merge(MLDaySyncStatus(
                seller_id=seller_id, day=_parse_dt(r["day"]).date() if not hasattr(r["day"], "year") else r["day"],
                last_synced_at=_parse_dt(r["last_synced_at"]) or datetime.utcnow(),
                orders_count=r["orders_count"] or 0, status=status,
                error_message=r["error_message"],
            ))
            report["days"] += 1

        for r in tok_rows:
            s.merge(MLTokens(
                seller_id=seller_id, client_id=None,
                access_token=r["access_token"], refresh_token=r["refresh_token"],
                expires_at=_parse_dt(r["expires_at"]) or datetime.utcnow(),
                updated_at=_parse_dt(r["updated_at"]) or datetime.utcnow(),
            ))
            report["tokens"] += 1

        s.commit()
    finally:
        s.close()
        src.dispose()
    return report


if __name__ == "__main__":
    import argparse
    from financeiro_ml.db import init_fin_db
    parser = argparse.ArgumentParser(description="Migra dados financeiro ML v1 -> v2")
    parser.add_argument("--v1-db", required=True, help="caminho do .db v1 (ex: ./warehouse_v3_local.db)")
    parser.add_argument("--seller-id", type=int, required=True, help="user_id ML do seller default")
    args = parser.parse_args()
    init_fin_db()
    rep = migrate(v1_db_path=args.v1_db, seller_id=args.seller_id)
    print(f"[migrate] {rep}")
