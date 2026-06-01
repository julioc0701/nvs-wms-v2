"""Canario V2 Light: busca base por data sem enriquecer shipments.

Este modulo nao alimenta o cache usado pelo painel. Ele grava em tabelas
proprias para provar volume, pendencias e comportamento em producao sem
contaminar margem financeira.
"""
from __future__ import annotations

import json
import asyncio
from dataclasses import dataclass
from datetime import date, datetime, time

from financeiro_ml.client import MLRateLimited


@dataclass
class OrdersSearchCanaryResult:
    run_id: int
    seller_id: int
    day: date
    status: str
    orders_count: int
    pages_count: int
    pending_shipments: int
    pending_discounts: int
    pending_shipping_costs: int
    error_message: str | None = None

    def as_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "seller_id": self.seller_id,
            "day": self.day.isoformat(),
            "status": self.status,
            "orders_count": self.orders_count,
            "pages_count": self.pages_count,
            "pending_shipments": self.pending_shipments,
            "pending_discounts": self.pending_discounts,
            "pending_shipping_costs": self.pending_shipping_costs,
            "error_message": self.error_message,
        }


@dataclass
class PendingCanaryResult:
    run_id: int
    status: str
    processed: int
    succeeded: int
    failed: int
    rate_limited: bool
    stopped_on: str | None = None

    def as_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "processed": self.processed,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "rate_limited": self.rate_limited,
            "stopped_on": self.stopped_on,
        }


@dataclass
class BillingOrderDetailsCanaryResult:
    run_id: int
    status: str
    requested_orders: list[int]
    total_results: int
    order_ids_found: list[int]
    shipping_ids_found: list[str]
    pack_ids_found: list[str]
    shipping_total_by_order: dict[str, float]
    shipping_charge_lines: list[dict]
    error_message: str | None = None

    def as_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "requested_orders": self.requested_orders,
            "total_results": self.total_results,
            "order_ids_found": self.order_ids_found,
            "shipping_ids_found": self.shipping_ids_found,
            "pack_ids_found": self.pack_ids_found,
            "shipping_total_by_order": self.shipping_total_by_order,
            "shipping_charge_lines": self.shipping_charge_lines,
            "error_message": self.error_message,
        }


def _missing_flags(order: dict) -> list[str]:
    flags = []
    shipment_id = (order.get("shipping") or {}).get("id")
    if shipment_id:
        flags.append("pending_seller_shipping")
    if "order_has_discount" in (order.get("tags") or []):
        flags.append("pending_discount")
    shipping_cost = 0
    for pay in order.get("payments") or []:
        shipping_cost += pay.get("shipping_cost") or 0
    if shipment_id and shipping_cost == 0:
        flags.append("pending_shipping_cost")
    return flags


async def run_billing_order_details_canary(
    *,
    session_factory,
    client,
    run_id: int,
    seller_id: int,
    max_orders: int = 5,
) -> BillingOrderDetailsCanaryResult:
    """Consulta Billing Reports por poucos order_ids ja coletados no canario."""
    from financeiro_ml.models_v2 import MLCanaryOrderSnapshot

    s = session_factory()
    try:
        rows = (
            s.query(MLCanaryOrderSnapshot.order_id)
            .filter_by(run_id=run_id, seller_id=seller_id)
            .order_by(MLCanaryOrderSnapshot.id.asc())
            .limit(max_orders)
            .all()
        )
    finally:
        s.close()

    order_ids = [int(r[0]) for r in rows]
    if not order_ids:
        return BillingOrderDetailsCanaryResult(
            run_id=run_id,
            status="empty",
            requested_orders=[],
            total_results=0,
            order_ids_found=[],
            shipping_ids_found=[],
            pack_ids_found=[],
            shipping_total_by_order={},
            shipping_charge_lines=[],
            error_message="run sem snapshots para testar billing",
        )

    try:
        payload = await client.get_billing_order_details(
            seller_id=seller_id,
            order_ids=order_ids,
        )
        summary = _summarize_billing_order_details(payload)
        return BillingOrderDetailsCanaryResult(
            run_id=run_id,
            status="ok",
            requested_orders=order_ids,
            total_results=summary["total_results"],
            order_ids_found=summary["order_ids_found"],
            shipping_ids_found=summary["shipping_ids_found"],
            pack_ids_found=summary["pack_ids_found"],
            shipping_total_by_order=summary["shipping_total_by_order"],
            shipping_charge_lines=summary["shipping_charge_lines"],
            error_message=None,
        )
    except MLRateLimited as exc:
        return BillingOrderDetailsCanaryResult(
            run_id=run_id,
            status="rate_limited",
            requested_orders=order_ids,
            total_results=0,
            order_ids_found=[],
            shipping_ids_found=[],
            pack_ids_found=[],
            shipping_total_by_order={},
            shipping_charge_lines=[],
            error_message=str(exc),
        )
    except Exception as exc:
        return BillingOrderDetailsCanaryResult(
            run_id=run_id,
            status="failed",
            requested_orders=order_ids,
            total_results=0,
            order_ids_found=[],
            shipping_ids_found=[],
            pack_ids_found=[],
            shipping_total_by_order={},
            shipping_charge_lines=[],
            error_message=f"{type(exc).__name__}: {str(exc)[:300]}",
        )


async def run_billing_order_ids_canary(
    *,
    client,
    seller_id: int,
    order_ids: list[int],
) -> BillingOrderDetailsCanaryResult:
    """Consulta Billing Reports por order_ids explicitos."""
    clean_order_ids = []
    seen = set()
    for order_id in order_ids:
        oid = int(order_id)
        if oid not in seen:
            seen.add(oid)
            clean_order_ids.append(oid)

    if not clean_order_ids:
        return BillingOrderDetailsCanaryResult(
            run_id=0,
            status="empty",
            requested_orders=[],
            total_results=0,
            order_ids_found=[],
            shipping_ids_found=[],
            pack_ids_found=[],
            shipping_total_by_order={},
            shipping_charge_lines=[],
            error_message="nenhum order_id informado",
        )

    try:
        payload = await client.get_billing_order_details(
            seller_id=seller_id,
            order_ids=clean_order_ids,
        )
        summary = _summarize_billing_order_details(payload, max_lines=80)
        return BillingOrderDetailsCanaryResult(
            run_id=0,
            status="ok",
            requested_orders=clean_order_ids,
            total_results=summary["total_results"],
            order_ids_found=summary["order_ids_found"],
            shipping_ids_found=summary["shipping_ids_found"],
            pack_ids_found=summary["pack_ids_found"],
            shipping_total_by_order=summary["shipping_total_by_order"],
            shipping_charge_lines=summary["shipping_charge_lines"],
            error_message=None,
        )
    except MLRateLimited as exc:
        return BillingOrderDetailsCanaryResult(
            run_id=0,
            status="rate_limited",
            requested_orders=clean_order_ids,
            total_results=0,
            order_ids_found=[],
            shipping_ids_found=[],
            pack_ids_found=[],
            shipping_total_by_order={},
            shipping_charge_lines=[],
            error_message=str(exc),
        )
    except Exception as exc:
        return BillingOrderDetailsCanaryResult(
            run_id=0,
            status="failed",
            requested_orders=clean_order_ids,
            total_results=0,
            order_ids_found=[],
            shipping_ids_found=[],
            pack_ids_found=[],
            shipping_total_by_order={},
            shipping_charge_lines=[],
            error_message=f"{type(exc).__name__}: {str(exc)[:300]}",
        )


def _summarize_billing_order_details(payload: dict, max_lines: int = 20) -> dict:
    results = payload.get("results") or []
    order_ids: set[int] = set()
    shipping_ids: set[str] = set()
    pack_ids: set[str] = set()
    shipping_lines: list[dict] = []
    shipping_total_by_order: dict[str, float] = {}

    def walk(node):
        if isinstance(node, dict):
            if node.get("order_id") is not None:
                try:
                    order_ids.add(int(node["order_id"]))
                except (TypeError, ValueError):
                    pass
            if node.get("shipping_id") is not None:
                shipping_ids.add(str(node["shipping_id"]))
            if node.get("pack_id") is not None:
                pack_ids.add(str(node["pack_id"]))

            charge = node.get("charge_info") or {}
            shipping = node.get("shipping_info") or {}
            marketplace = (node.get("marketplace_info") or {}).get("marketplace")
            text = " ".join(str(charge.get(k) or "") for k in (
                "transaction_detail",
                "detail_sub_type",
                "concept_type",
            )).lower()
            is_shipping = (
                "envio" in text
                or "shipping" in text
                or "frete" in text
                or marketplace == "SHIPPING"
                or bool(shipping)
            )
            if charge and is_shipping:
                line_order_ids = _order_ids_in(node)
                shipping_lines.append({
                    "order_ids": line_order_ids,
                    "shipping_id": str(shipping.get("shipping_id")) if shipping.get("shipping_id") is not None else None,
                    "pack_id": str(shipping.get("pack_id")) if shipping.get("pack_id") is not None else None,
                    "transaction_detail": charge.get("transaction_detail"),
                    "detail_type": charge.get("detail_type"),
                    "detail_sub_type": charge.get("detail_sub_type"),
                    "detail_amount": charge.get("detail_amount"),
                    "marketplace": marketplace,
                })
                if marketplace == "SHIPPING":
                    for order_id in line_order_ids:
                        key = str(order_id)
                        shipping_total_by_order[key] = round(
                            shipping_total_by_order.get(key, 0) + float(charge.get("detail_amount") or 0),
                            2,
                        )

            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(results)
    return {
        "total_results": payload.get("total") if payload.get("total") is not None else len(results),
        "order_ids_found": sorted(order_ids),
        "shipping_ids_found": sorted(shipping_ids),
        "pack_ids_found": sorted(pack_ids),
        "shipping_total_by_order": dict(sorted(shipping_total_by_order.items())),
        "shipping_charge_lines": shipping_lines[:max_lines],
    }


def _order_ids_in(node: dict) -> list[int]:
    found: set[int] = set()

    def walk(value):
        if isinstance(value, dict):
            if value.get("order_id") is not None:
                try:
                    found.add(int(value["order_id"]))
                except (TypeError, ValueError):
                    pass
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(node)
    return sorted(found)


def _status_for(flags: list[str]) -> str:
    if not flags:
        return "base_imported"
    if "pending_seller_shipping" in flags:
        return "pending_seller_shipping"
    if "pending_discount" in flags:
        return "pending_discount"
    if "pending_shipping_cost" in flags:
        return "pending_shipping_cost"
    return "base_imported"


async def run_orders_search_canary(
    *,
    session_factory,
    client,
    seller_id: int,
    day: date,
    max_pages: int = 20,
) -> OrdersSearchCanaryResult:
    """Busca um dia via /orders/search e registra pendencias sem chamar shipments."""
    from financeiro_ml.models_v2 import (
        MLCanaryRun,
        MLCanaryOrderSnapshot,
        MLCanaryPendingTask,
    )

    s = session_factory()
    try:
        run = MLCanaryRun(seller_id=seller_id, day=day, status="running")
        s.add(run)
        s.commit()
        run_id = run.id
    finally:
        s.close()

    day_start = datetime.combine(day, time.min)
    day_end = datetime.combine(day, time.max)
    orders_count = 0
    pages_count = 0
    seen_order_ids: set[str] = set()
    pending_shipments: set[str] = set()
    pending_discounts: set[str] = set()
    pending_shipping_costs: set[str] = set()
    error_message = None
    status = "ok"

    try:
        offset = 0
        while pages_count < max_pages:
            page = await client.search_orders(
                date_from=day_start,
                date_to=day_end,
                offset=offset,
                limit=50,
            )
            pages_count += 1
            results = page.get("results", [])
            if not results:
                break
            persisted_count = _persist_page(
                session_factory=session_factory,
                run_id=run_id,
                seller_id=seller_id,
                orders=results,
                seen_order_ids=seen_order_ids,
                pending_shipments=pending_shipments,
                pending_discounts=pending_discounts,
                pending_shipping_costs=pending_shipping_costs,
            )
            orders_count += persisted_count
            if len(results) < 50:
                break
            offset += 50
        else:
            status = "partial"
            error_message = f"max_pages atingido ({max_pages})"
    except MLRateLimited as exc:
        status = "rate_limited"
        error_message = str(exc)
    except Exception as exc:
        status = "failed"
        error_message = f"{type(exc).__name__}: {str(exc)[:300]}"

    _finish_run(
        session_factory=session_factory,
        run_id=run_id,
        status=status,
        orders_count=orders_count,
        pages_count=pages_count,
        pending_shipments=len(pending_shipments),
        pending_discounts=len(pending_discounts),
        pending_shipping_costs=len(pending_shipping_costs),
        error_message=error_message,
    )
    return OrdersSearchCanaryResult(
        run_id=run_id,
        seller_id=seller_id,
        day=day,
        status=status,
        orders_count=orders_count,
        pages_count=pages_count,
        pending_shipments=len(pending_shipments),
        pending_discounts=len(pending_discounts),
        pending_shipping_costs=len(pending_shipping_costs),
        error_message=error_message,
    )


def _persist_page(
    *,
    session_factory,
    run_id: int,
    seller_id: int,
    orders: list[dict],
    seen_order_ids: set[str],
    pending_shipments: set[str],
    pending_discounts: set[str],
    pending_shipping_costs: set[str],
) -> int:
    from financeiro_ml.models_v2 import MLCanaryOrderSnapshot, MLCanaryPendingTask

    s = session_factory()
    try:
        persisted_count = 0
        for order in orders:
            order_ref = str(order["id"])
            if order_ref in seen_order_ids:
                continue
            seen_order_ids.add(order_ref)
            shipment_id = (order.get("shipping") or {}).get("id")
            flags = _missing_flags(order)
            s.add(MLCanaryOrderSnapshot(
                run_id=run_id,
                seller_id=seller_id,
                order_id=order["id"],
                shipment_id=shipment_id,
                order_status=order.get("status"),
                ingest_status=_status_for(flags),
                missing_flags=json.dumps(flags),
                raw_json=json.dumps(order),
            ))
            persisted_count += 1
            if shipment_id and "pending_seller_shipping" in flags:
                ref = str(shipment_id)
                if ref not in pending_shipments:
                    pending_shipments.add(ref)
                    s.add(MLCanaryPendingTask(
                        run_id=run_id,
                        seller_id=seller_id,
                        kind="seller_shipping",
                        ref_id=ref,
                    ))
            if shipment_id and "pending_shipping_cost" in flags:
                ref = str(shipment_id)
                if ref not in pending_shipping_costs:
                    pending_shipping_costs.add(ref)
                    s.add(MLCanaryPendingTask(
                        run_id=run_id,
                        seller_id=seller_id,
                        kind="shipping_cost",
                        ref_id=ref,
                    ))
            if "pending_discount" in flags:
                if order_ref not in pending_discounts:
                    pending_discounts.add(order_ref)
                    s.add(MLCanaryPendingTask(
                        run_id=run_id,
                        seller_id=seller_id,
                        kind="discount",
                        ref_id=order_ref,
                    ))
        s.commit()
        return persisted_count
    finally:
        s.close()


def _finish_run(
    *,
    session_factory,
    run_id: int,
    status: str,
    orders_count: int,
    pages_count: int,
    pending_shipments: int,
    pending_discounts: int,
    pending_shipping_costs: int,
    error_message: str | None,
) -> None:
    from financeiro_ml.models_v2 import MLCanaryRun

    s = session_factory()
    try:
        run = s.query(MLCanaryRun).filter_by(id=run_id).first()
        if run:
            run.status = status
            run.orders_count = orders_count
            run.pages_count = pages_count
            run.pending_shipments = pending_shipments
            run.pending_discounts = pending_discounts
            run.pending_shipping_costs = pending_shipping_costs
            run.error_message = error_message
            run.finished_at = datetime.utcnow()
            s.commit()
    finally:
        s.close()


def get_canary_run(session_factory, run_id: int) -> dict | None:
    from financeiro_ml.models_v2 import MLCanaryRun, MLCanaryPendingTask

    s = session_factory()
    try:
        run = s.query(MLCanaryRun).filter_by(id=run_id).first()
        if run is None:
            return None
        pending_by_kind = {}
        rows = s.query(MLCanaryPendingTask.kind, MLCanaryPendingTask.status).filter_by(run_id=run_id).all()
        for kind, task_status in rows:
            pending_by_kind.setdefault(kind, {}).setdefault(task_status, 0)
            pending_by_kind[kind][task_status] += 1
        return {
            "run_id": run.id,
            "seller_id": run.seller_id,
            "day": run.day.isoformat(),
            "status": run.status,
            "orders_count": run.orders_count,
            "pages_count": run.pages_count,
            "pending_shipments": run.pending_shipments,
            "pending_discounts": run.pending_discounts,
            "pending_shipping_costs": run.pending_shipping_costs,
            "error_message": run.error_message,
            "pending_by_kind": pending_by_kind,
        }
    finally:
        s.close()


async def process_canary_pending(
    *,
    session_factory,
    client,
    run_id: int,
    max_tasks: int = 5,
    sleep_sec: float = 0.0,
) -> PendingCanaryResult:
    """Processa poucas pendencias do canario, uma por vez.

    Para no primeiro 429. Este fluxo e manual/diagnostico; nao e worker automatico.
    """
    from financeiro_ml.models_v2 import MLCanaryRun, MLCanaryPendingTask

    processed = succeeded = failed = 0
    stopped_on = None
    rate_limited = False

    tasks = _pending_tasks(session_factory, run_id, max_tasks)
    for idx, task_id in enumerate(tasks):
        s = session_factory()
        try:
            task = s.query(MLCanaryPendingTask).filter_by(id=task_id).first()
            if task is None or task.status != "pending":
                continue
            task.status = "running"
            task.attempts += 1
            task.updated_at = datetime.utcnow()
            s.commit()
            kind = task.kind
            ref_id = task.ref_id
        finally:
            s.close()

        try:
            payload = await _call_pending(client, kind=kind, ref_id=ref_id)
            _mark_task(
                session_factory,
                task_id=task_id,
                status="done",
                result_json=json.dumps(payload)[:4000],
            )
            processed += 1
            succeeded += 1
        except MLRateLimited as exc:
            _mark_task(
                session_factory,
                task_id=task_id,
                status="rate_limited",
                last_error=str(exc),
            )
            _mark_run_status(session_factory, run_id, "blocked_rate_limit", str(exc))
            processed += 1
            rate_limited = True
            stopped_on = ref_id
            break
        except Exception as exc:
            _mark_task(
                session_factory,
                task_id=task_id,
                status="failed",
                last_error=f"{type(exc).__name__}: {str(exc)[:300]}",
            )
            processed += 1
            failed += 1

        if sleep_sec > 0 and idx < len(tasks) - 1:
            await asyncio.sleep(sleep_sec)

    if not rate_limited:
        _mark_run_status(session_factory, run_id, "pending_processed", None)

    return PendingCanaryResult(
        run_id=run_id,
        status="blocked_rate_limit" if rate_limited else "ok",
        processed=processed,
        succeeded=succeeded,
        failed=failed,
        rate_limited=rate_limited,
        stopped_on=stopped_on,
    )


def _pending_tasks(session_factory, run_id: int, max_tasks: int) -> list[int]:
    from financeiro_ml.models_v2 import MLCanaryPendingTask

    s = session_factory()
    try:
        rows = (
            s.query(MLCanaryPendingTask.id)
            .filter_by(run_id=run_id, status="pending")
            .order_by(MLCanaryPendingTask.created_at.asc(), MLCanaryPendingTask.id.asc())
            .limit(max_tasks)
            .all()
        )
        return [r[0] for r in rows]
    finally:
        s.close()


async def _call_pending(client, *, kind: str, ref_id: str) -> dict:
    if kind == "seller_shipping":
        return await client.get_shipment(int(ref_id))
    if kind == "shipping_cost":
        return await client.get_shipment_costs(int(ref_id))
    if kind == "discount":
        return await client.get_order_discounts(int(ref_id))
    raise ValueError(f"tipo de pendencia desconhecido: {kind}")


def _mark_task(
    session_factory,
    *,
    task_id: int,
    status: str,
    last_error: str | None = None,
    result_json: str | None = None,
) -> None:
    from financeiro_ml.models_v2 import MLCanaryPendingTask

    s = session_factory()
    try:
        task = s.query(MLCanaryPendingTask).filter_by(id=task_id).first()
        if task:
            task.status = status
            task.last_error = last_error
            task.result_json = result_json
            task.updated_at = datetime.utcnow()
            s.commit()
    finally:
        s.close()


def _mark_run_status(session_factory, run_id: int, status: str, error_message: str | None) -> None:
    from financeiro_ml.models_v2 import MLCanaryRun

    s = session_factory()
    try:
        run = s.query(MLCanaryRun).filter_by(id=run_id).first()
        if run:
            run.status = status
            run.error_message = error_message
            s.commit()
    finally:
        s.close()
