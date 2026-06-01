"""Auditoria entre pedidos capturados e linhas do Billing ML.

Nao chama Mercado Livre. Usa apenas o que ja foi salvo no banco financeiro.
"""
import json
from decimal import Decimal
from typing import Any


def audit_daily_close_reconciliation(session_factory, *, job_id: int, sample_limit: int = 20) -> dict | None:
    from financeiro_ml.models_v2 import (
        MLBillingPeriodJob,
        MLBillingPeriodLine,
        MLCanaryOrderSnapshot,
        MLDailyCloseJob,
    )

    s = session_factory()
    try:
        job = s.query(MLDailyCloseJob).filter_by(id=job_id).first()
        if job is None:
            return None

        billing_job = None
        if job.billing_job_id:
            billing_job = s.query(MLBillingPeriodJob).filter_by(id=job.billing_job_id).first()

        orders = []
        if job.orders_run_id:
            orders = (
                s.query(MLCanaryOrderSnapshot)
                .filter_by(run_id=job.orders_run_id, seller_id=job.seller_id)
                .all()
            )

        billing_query = s.query(MLBillingPeriodLine).filter_by(seller_id=job.seller_id)
        if billing_job is not None:
            billing_query = billing_query.filter_by(
                period_key=billing_job.period_key,
                document_type=billing_job.document_type,
            )
        billing_lines = billing_query.all()

        lines_by_order: dict[int, list[Any]] = {}
        lines_by_shipment: dict[int, list[Any]] = {}
        amount_by_order: dict[int, Decimal] = {}
        amount_by_shipment: dict[int, Decimal] = {}

        for line in billing_lines:
            amount = Decimal(str(line.detail_amount or 0))
            if line.order_id:
                lines_by_order.setdefault(int(line.order_id), []).append(line)
                amount_by_order[int(line.order_id)] = amount_by_order.get(int(line.order_id), Decimal("0")) + amount
            if line.shipment_id:
                lines_by_shipment.setdefault(int(line.shipment_id), []).append(line)
                amount_by_shipment[int(line.shipment_id)] = amount_by_shipment.get(int(line.shipment_id), Decimal("0")) + amount

        matched_by_order = 0
        matched_by_shipment_only = 0
        missing = []
        shipments_to_probe: list[int] = []

        for order in orders:
            order_id = int(order.order_id)
            shipment_id = int(order.shipment_id) if order.shipment_id else None
            has_order_match = order_id in lines_by_order
            has_shipment_match = bool(shipment_id and shipment_id in lines_by_shipment)

            if has_order_match:
                matched_by_order += 1
                continue
            if has_shipment_match:
                matched_by_shipment_only += 1
                continue

            if shipment_id:
                shipments_to_probe.append(shipment_id)
            if len(missing) < sample_limit:
                missing.append({
                    "order_id": order_id,
                    "shipment_id": shipment_id,
                    "status": order.order_status,
                    "missing_flags": _safe_json_list(order.missing_flags),
                })

        matched_orders = matched_by_order + matched_by_shipment_only
        orders_total = len(orders)
        missing_orders = max(0, orders_total - matched_orders)
        coverage_percent = round((matched_orders / orders_total) * 100, 2) if orders_total else 0
        unique_shipments_to_probe = sorted(set(shipments_to_probe))

        return {
            "job_id": job.id,
            "seller_id": job.seller_id,
            "day": job.day.isoformat() if job.day else None,
            "daily_close_status": job.status,
            "orders_run_id": job.orders_run_id,
            "billing_job_id": job.billing_job_id,
            "billing_status": billing_job.status if billing_job else None,
            "billing_period_key": billing_job.period_key if billing_job else None,
            "orders_total": orders_total,
            "billing_lines_total": len(billing_lines),
            "billing_lines_with_order_id": sum(1 for line in billing_lines if line.order_id),
            "billing_lines_with_shipment_id": sum(1 for line in billing_lines if line.shipment_id),
            "matched_orders": matched_orders,
            "matched_by_order_id": matched_by_order,
            "matched_by_shipment_id_only": matched_by_shipment_only,
            "missing_orders": missing_orders,
            "coverage_percent": coverage_percent,
            "shipments_to_probe_count": len(unique_shipments_to_probe),
            "shipments_to_probe_sample": unique_shipments_to_probe[:sample_limit],
            "missing_orders_sample": missing,
            "recommendation": _recommendation(missing_orders, unique_shipments_to_probe),
        }
    finally:
        s.close()


def compare_daily_close_order_ids(
    session_factory,
    *,
    job_id: int,
    reference_order_ids: list[int | str],
    sample_limit: int = 50,
) -> dict | None:
    """Compara IDs capturados pelo robo com uma referencia externa, ex. Excel MT."""
    from financeiro_ml.models_v2 import MLCanaryOrderSnapshot, MLDailyCloseJob

    s = session_factory()
    try:
        job = s.query(MLDailyCloseJob).filter_by(id=job_id).first()
        if job is None:
            return None

        ml_ids: set[int] = set()
        if job.orders_run_id:
            rows = (
                s.query(MLCanaryOrderSnapshot.order_id)
                .filter_by(run_id=job.orders_run_id, seller_id=job.seller_id)
                .all()
            )
            ml_ids = {int(row[0]) for row in rows if row[0] is not None}

        reference_ids = {_normalize_order_id(value) for value in reference_order_ids}
        reference_ids.discard(None)
        reference_ids = {int(value) for value in reference_ids if value is not None}

        only_ml = sorted(ml_ids - reference_ids)
        only_reference = sorted(reference_ids - ml_ids)
        matched = sorted(ml_ids & reference_ids)

        return {
            "job_id": job.id,
            "seller_id": job.seller_id,
            "day": job.day.isoformat() if job.day else None,
            "orders_run_id": job.orders_run_id,
            "ml_orders_count": len(ml_ids),
            "reference_orders_count": len(reference_ids),
            "matched_count": len(matched),
            "only_ml_count": len(only_ml),
            "only_reference_count": len(only_reference),
            "only_ml_sample": only_ml[:sample_limit],
            "only_reference_sample": only_reference[:sample_limit],
            "matched_sample": matched[:sample_limit],
            "diagnosis": _order_id_diff_diagnosis(len(only_ml), len(only_reference)),
        }
    finally:
        s.close()


def _safe_json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except Exception:
        return []
    return []


def _normalize_order_id(value: int | str | None) -> int | None:
    if value is None:
        return None
    text = str(value).strip().replace("#", "")
    if not text or text.lower() == "nan":
        return None
    if "." in text:
        text = text.split(".", 1)[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None
    return int(digits)


def _order_id_diff_diagnosis(only_ml_count: int, only_reference_count: int) -> str:
    if only_ml_count == 0 and only_reference_count == 0:
        return "Mesmo universo de pedidos; a diferenca restante e financeira/campos."
    if only_ml_count > 0 and only_reference_count == 0:
        return "Mercado Livre trouxe pedidos que nao estavam no Excel; provavel diferenca de horario/atualizacao da exportacao."
    if only_ml_count == 0 and only_reference_count > 0:
        return "Excel tem pedidos que o robo nao capturou; investigar filtro de data/status."
    return "Ha diferenca dos dois lados; investigar horario da exportacao e criterio de status/data."


def _recommendation(missing_orders: int, shipments_to_probe: list[int]) -> str:
    if missing_orders <= 0:
        return "Billing cobriu todos os pedidos capturados; nao precisa chamar shipment em massa."
    if shipments_to_probe:
        return "Consultar shipment costs somente dos pedidos nao cobertos pelo Billing, em fila lenta."
    return "Investigar pedidos sem vinculo por order_id/shipment_id antes de chamar shipment."
