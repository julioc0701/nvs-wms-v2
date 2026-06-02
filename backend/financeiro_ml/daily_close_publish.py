"""Publica fechamento diario consolidado no cache usado pelo painel."""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from financeiro_ml.aggregator import _logistic_bucket


@dataclass
class PublishDailyCloseResult:
    job_id: int
    status: str
    orders_published: int
    items_published: int
    error_message: str | None = None

    def as_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "orders_published": self.orders_published,
            "items_published": self.items_published,
            "error_message": self.error_message,
        }


def publish_daily_close_to_cache(session_factory, *, job_id: int) -> PublishDailyCloseResult:
    """Copia snapshots+Billing consolidados para MLOrderCache/MLOrderItemCache."""
    from financeiro_ml.billing_reconciliation import audit_daily_close_reconciliation
    from financeiro_ml.models_v2 import (
        MLBillingPeriodJob,
        MLBillingPeriodLine,
        MLCanaryOrderSnapshot,
        MLDailyCloseJob,
        MLDaySyncStatus,
        MLOrderCache,
        MLOrderItemCache,
    )

    audit = audit_daily_close_reconciliation(session_factory, job_id=job_id)
    if not audit:
        return PublishDailyCloseResult(job_id, "not_found", 0, 0, "job nao encontrado")
    if audit.get("daily_close_status") != "consolidated" or audit.get("billing_status") != "done":
        return PublishDailyCloseResult(job_id, "blocked", 0, 0, "fechamento ainda nao consolidado")
    if int(audit.get("orders_total") or 0) != int(audit.get("matched_orders") or -1):
        return PublishDailyCloseResult(job_id, "blocked", 0, 0, "Billing nao cobre 100% dos pedidos")

    s = session_factory()
    try:
        job = s.query(MLDailyCloseJob).filter_by(id=job_id).first()
        if job is None or not job.orders_run_id or not job.billing_job_id:
            return PublishDailyCloseResult(job_id, "not_found", 0, 0, "job incompleto")
        billing_job = s.query(MLBillingPeriodJob).filter_by(id=job.billing_job_id).first()
        if billing_job is None:
            return PublishDailyCloseResult(job_id, "not_found", 0, 0, "billing job nao encontrado")

        snapshots = (
            s.query(MLCanaryOrderSnapshot)
            .filter_by(run_id=job.orders_run_id, seller_id=job.seller_id)
            .all()
        )
        lines = (
            s.query(MLBillingPeriodLine)
            .filter_by(
                seller_id=job.seller_id,
                period_key=billing_job.period_key,
                document_type=billing_job.document_type,
            )
            .all()
        )
        billing_by_order = _billing_summary_by_order(lines)

        orders_published = 0
        items_published = 0
        for snap in snapshots:
            order = json.loads(snap.raw_json or "{}")
            summary = billing_by_order.get(int(snap.order_id), {})
            cache_row = _cache_row_from_order(job.seller_id, order, summary)
            existing = (
                s.query(MLOrderCache)
                .filter_by(seller_id=job.seller_id, order_id=snap.order_id)
                .first()
            )
            if existing is None:
                existing = MLOrderCache(seller_id=job.seller_id, order_id=snap.order_id)
                s.add(existing)
            for key, value in cache_row.items():
                setattr(existing, key, value)

            s.query(MLOrderItemCache).filter_by(
                seller_id=job.seller_id,
                order_id=snap.order_id,
            ).delete()
            for item in _item_rows_from_order(job.seller_id, order):
                s.add(MLOrderItemCache(**item))
                items_published += 1
            orders_published += 1

        day_status = (
            s.query(MLDaySyncStatus)
            .filter_by(seller_id=job.seller_id, day=job.day)
            .first()
        )
        if day_status is None:
            day_status = MLDaySyncStatus(seller_id=job.seller_id, day=job.day)
            s.add(day_status)
        day_status.last_synced_at = datetime.utcnow()
        day_status.orders_count = orders_published
        day_status.status = "ok"
        day_status.next_retry_at = None
        day_status.error_message = "daily_close_consolidated"

        s.commit()
        return PublishDailyCloseResult(job_id, "published", orders_published, items_published)
    finally:
        s.close()


def _billing_summary_by_order(lines: list[Any]) -> dict[int, dict[str, Decimal]]:
    result: dict[int, dict[str, Decimal]] = defaultdict(lambda: {
        "frete_vendedor": Decimal("0"),
        "frete_comprador": Decimal("0"),
    })
    for line in lines:
        if not line.order_id:
            continue
        raw = json.loads(line.raw_json or "{}")
        amount = Decimal(str(line.detail_amount or 0))
        marketplace = (raw.get("marketplace_info") or {}).get("marketplace")
        shipping = raw.get("shipping_info") or {}
        if marketplace == "SHIPPING":
            result[int(line.order_id)]["frete_vendedor"] += amount
        receiver_cost = shipping.get("receiver_shipping_cost")
        if receiver_cost is not None:
            current = result[int(line.order_id)]["frete_comprador"]
            candidate = Decimal(str(receiver_cost or 0))
            if candidate > current:
                result[int(line.order_id)]["frete_comprador"] = candidate
    return result


def _cache_row_from_order(seller_id: int, order: dict, billing: dict[str, Decimal]) -> dict:
    produto_total = Decimal("0")
    tarifa_bruta = Decimal("0")
    for item in order.get("order_items") or []:
        qty = Decimal(str(item.get("quantity") or 0))
        produto_total += Decimal(str(item.get("unit_price") or 0)) * qty
        tarifa_bruta += Decimal(str(item.get("sale_fee") or 0)) * qty

    frete_comprador = _payments_shipping_cost(order)
    billing_fc = billing.get("frete_comprador") or Decimal("0")
    if frete_comprador == 0 and billing_fc > 0:
        frete_comprador = billing_fc

    refund_total = Decimal("0")
    for payment in order.get("payments") or []:
        refund_total += Decimal(str(payment.get("transaction_amount_refunded") or 0))
    refund_partial = Decimal("0") if order.get("status") == "cancelled" else refund_total

    shipping = order.get("shipping") or {}
    logistic_type = shipping.get("logistic_type")
    shipping_mode = shipping.get("mode")
    first_item = (order.get("order_items") or [{}])[0].get("item") or {}

    return {
        "date_created": _to_brt_naive(order.get("date_created")),
        "date_closed": _to_brt_naive(order.get("date_closed")),
        "date_last_updated": _to_brt_naive(order.get("last_updated") or order.get("date_last_updated")),
        "status": order.get("status") or "",
        "status_detail": order.get("status_detail"),
        "produto_total": produto_total,
        "frete_comprador": frete_comprador,
        "frete_vendedor": max(Decimal("0"), billing.get("frete_vendedor") or Decimal("0")),
        "tarifa_bruta": tarifa_bruta,
        "tarifa_refund": Decimal("0"),
        "refund_amount_partial": refund_partial,
        "cupom_seller": Decimal("0"),
        "modalidade_anuncio": first_item.get("listing_type_id"),
        "logistic_type": logistic_type,
        "shipping_mode": shipping_mode,
        "shipment_id": shipping.get("id"),
        "breakdown_bucket": _logistic_bucket(logistic_type, shipping_mode),
        "frete_incerto": 0,
        "raw_json": json.dumps({"seller_id": seller_id, **order}),
        "synced_at": datetime.utcnow(),
    }


def _item_rows_from_order(seller_id: int, order: dict) -> list[dict]:
    rows = []
    for item_row in order.get("order_items") or []:
        item = item_row.get("item") or {}
        rows.append({
            "seller_id": seller_id,
            "order_id": int(order["id"]),
            "item_id": item.get("id") or str(order["id"]),
            "title": item.get("title") or "",
            "seller_sku": item.get("seller_sku") or item.get("seller_custom_field"),
            "quantity": int(item_row.get("quantity") or 0),
            "unit_price": Decimal(str(item_row.get("unit_price") or 0)),
            "category_id": item.get("category_id"),
        })
    return rows


def _payments_shipping_cost(order: dict) -> Decimal:
    total = Decimal("0")
    for payment in order.get("payments") or []:
        total += Decimal(str(payment.get("shipping_cost") or 0))
    return total


def _to_brt_naive(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
