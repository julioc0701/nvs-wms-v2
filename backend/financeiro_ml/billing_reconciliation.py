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

        ml_snapshots_by_id: dict[int, Any] = {}
        if job.orders_run_id:
            rows = (
                s.query(MLCanaryOrderSnapshot)
                .filter_by(run_id=job.orders_run_id, seller_id=job.seller_id)
                .all()
            )
            ml_snapshots_by_id = {int(row.order_id): row for row in rows if row.order_id is not None}
        ml_ids = set(ml_snapshots_by_id.keys())

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
            "only_ml_details_sample": [
                _snapshot_order_timing(ml_snapshots_by_id[order_id])
                for order_id in only_ml[:sample_limit]
                if order_id in ml_snapshots_by_id
            ],
            "only_reference_sample": only_reference[:sample_limit],
            "matched_sample": matched[:sample_limit],
            "diagnosis": _order_id_diff_diagnosis(len(only_ml), len(only_reference)),
        }
    finally:
        s.close()


def audit_billing_linkage_fields(session_factory, *, job_id: int, sample_limit: int = 20) -> dict | None:
    """Procura no raw_json do Billing quais campos batem com pedidos/fretes salvos.

    Nao chama ML. Serve para descobrir se o vinculo esta em outro path do JSON
    ou se as linhas de Billing baixadas nao pertencem ao universo do job.
    """
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

        orders = []
        if job.orders_run_id:
            orders = (
                s.query(MLCanaryOrderSnapshot)
                .filter_by(run_id=job.orders_run_id, seller_id=job.seller_id)
                .all()
            )
        order_ids = {int(row.order_id) for row in orders if row.order_id is not None}
        shipment_ids = {int(row.shipment_id) for row in orders if row.shipment_id is not None}

        billing_job = None
        if job.billing_job_id:
            billing_job = s.query(MLBillingPeriodJob).filter_by(id=job.billing_job_id).first()

        billing_query = s.query(MLBillingPeriodLine).filter_by(seller_id=job.seller_id)
        if billing_job is not None:
            billing_query = billing_query.filter_by(
                period_key=billing_job.period_key,
                document_type=billing_job.document_type,
            )
        billing_lines = billing_query.all()

        path_stats: dict[str, dict[str, Any]] = {}
        line_samples = []
        extracted_order_values = set()
        extracted_shipment_values = set()

        for line in billing_lines:
            if line.order_id is not None:
                extracted_order_values.add(int(line.order_id))
            if line.shipment_id is not None:
                extracted_shipment_values.add(int(line.shipment_id))

            raw = _safe_json_dict(line.raw_json)
            if len(line_samples) < sample_limit:
                line_samples.append(_billing_line_sample(line, raw))

            for path, value in _flatten_json(raw):
                parsed = _normalize_order_id(value)
                if parsed is None:
                    continue
                stat = path_stats.setdefault(path, {
                    "path": path,
                    "numeric_values_count": 0,
                    "order_matches": 0,
                    "shipment_matches": 0,
                    "sample_values": [],
                })
                stat["numeric_values_count"] += 1
                if parsed in order_ids:
                    stat["order_matches"] += 1
                if parsed in shipment_ids:
                    stat["shipment_matches"] += 1
                if len(stat["sample_values"]) < 5:
                    stat["sample_values"].append(parsed)

        order_candidate_paths = sorted(
            [stat for stat in path_stats.values() if stat["order_matches"] > 0],
            key=lambda item: item["order_matches"],
            reverse=True,
        )
        shipment_candidate_paths = sorted(
            [stat for stat in path_stats.values() if stat["shipment_matches"] > 0],
            key=lambda item: item["shipment_matches"],
            reverse=True,
        )

        extracted_order_overlap = sorted(extracted_order_values & order_ids)
        extracted_shipment_overlap = sorted(extracted_shipment_values & shipment_ids)

        return {
            "job_id": job.id,
            "seller_id": job.seller_id,
            "day": job.day.isoformat() if job.day else None,
            "orders_run_id": job.orders_run_id,
            "billing_job_id": job.billing_job_id,
            "billing_status": billing_job.status if billing_job else None,
            "billing_period_key": billing_job.period_key if billing_job else None,
            "orders_total": len(order_ids),
            "shipments_total": len(shipment_ids),
            "billing_lines_total": len(billing_lines),
            "stored_order_id_values_count": len(extracted_order_values),
            "stored_shipment_id_values_count": len(extracted_shipment_values),
            "stored_order_id_overlap_count": len(extracted_order_overlap),
            "stored_shipment_id_overlap_count": len(extracted_shipment_overlap),
            "stored_order_id_overlap_sample": extracted_order_overlap[:sample_limit],
            "stored_shipment_id_overlap_sample": extracted_shipment_overlap[:sample_limit],
            "order_candidate_paths": order_candidate_paths[:sample_limit],
            "shipment_candidate_paths": shipment_candidate_paths[:sample_limit],
            "billing_line_samples": line_samples,
            "diagnosis": _billing_linkage_diagnosis(
                len(billing_lines),
                len(extracted_order_overlap),
                len(extracted_shipment_overlap),
                order_candidate_paths,
                shipment_candidate_paths,
            ),
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


def _snapshot_order_timing(snapshot: Any) -> dict:
    raw = _safe_json_dict(snapshot.raw_json)
    return {
        "order_id": int(snapshot.order_id),
        "shipment_id": int(snapshot.shipment_id) if snapshot.shipment_id else None,
        "status": raw.get("status") or snapshot.order_status,
        "date_created": raw.get("date_created"),
        "date_closed": raw.get("date_closed"),
        "date_last_updated": raw.get("date_last_updated"),
        "date_cancelled": raw.get("date_cancelled"),
        "tags": raw.get("tags") or [],
    }


def _safe_json_dict(value: str | None) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return {}
    return {}


def _flatten_json(value: Any, prefix: str = ""):
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            yield from _flatten_json(child, path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            path = f"{prefix}[]" if prefix else "[]"
            yield from _flatten_json(child, path)
            if index >= 20:
                break
    else:
        yield prefix, value


def _billing_line_sample(line: Any, raw: dict) -> dict:
    charge = raw.get("charge_info") or {}
    sales = raw.get("sales_info")
    shipping = raw.get("shipping_info")
    items = raw.get("items_info")
    return {
        "detail_id": int(line.detail_id),
        "stored_order_id": int(line.order_id) if line.order_id else None,
        "stored_shipment_id": int(line.shipment_id) if line.shipment_id else None,
        "detail_type": line.detail_type,
        "detail_sub_type": line.detail_sub_type,
        "detail_amount": str(line.detail_amount) if line.detail_amount is not None else None,
        "transaction_detail": line.transaction_detail,
        "charge_info": {
            "detail_id": charge.get("detail_id"),
            "creation_date_time": charge.get("creation_date_time"),
            "transaction_detail": charge.get("transaction_detail"),
            "detail_type": charge.get("detail_type"),
            "detail_sub_type": charge.get("detail_sub_type"),
            "detail_amount": charge.get("detail_amount"),
        },
        "sales_info": sales,
        "shipping_info": shipping,
        "items_info": items,
    }


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


def _billing_linkage_diagnosis(
    billing_lines_count: int,
    stored_order_overlap_count: int,
    stored_shipment_overlap_count: int,
    order_candidate_paths: list[dict],
    shipment_candidate_paths: list[dict],
) -> str:
    if billing_lines_count == 0:
        return "Nao ha linhas de Billing salvas para auditar."
    if stored_order_overlap_count or stored_shipment_overlap_count:
        return "Os campos armazenados ja batem com pedidos/fretes; a conciliacao deve usar esses indices."
    if order_candidate_paths or shipment_candidate_paths:
        return "O vinculo existe no raw_json em outro campo; ajustar extrator do Billing."
    return "Nenhum campo do Billing salvo bate com os pedidos/fretes do job; provavel periodo/cursor de Billing incorreto ou lancamentos fora do dia."


def _recommendation(missing_orders: int, shipments_to_probe: list[int]) -> str:
    if missing_orders <= 0:
        return "Billing cobriu todos os pedidos capturados; nao precisa chamar shipment em massa."
    if shipments_to_probe:
        return "Consultar shipment costs somente dos pedidos nao cobertos pelo Billing, em fila lenta."
    return "Investigar pedidos sem vinculo por order_id/shipment_id antes de chamar shipment."
