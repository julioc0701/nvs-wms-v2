"""Job controlado para baixar Billing por periodo com checkpoint.

Uso esperado em producao: rodar poucas paginas por chamada, salvar o cursor
next_from_id e continuar depois sem repetir o periodo inteiro.
"""
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from financeiro_ml.client import MLRateLimited


@dataclass
class BillingPeriodRunResult:
    job_id: int
    status: str
    pages_processed: int
    lines_processed: int
    next_from_id: int
    total_results: int | None
    error_message: str | None = None

    def as_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "pages_processed": self.pages_processed,
            "lines_processed": self.lines_processed,
            "next_from_id": self.next_from_id,
            "total_results": self.total_results,
            "error_message": self.error_message,
        }


def create_billing_period_job(
    session_factory,
    *,
    seller_id: int,
    period_key: str,
    document_type: str = "BILL",
    limit: int = 100,
) -> int:
    from financeiro_ml.models_v2 import MLBillingPeriodJob

    s = session_factory()
    try:
        job = MLBillingPeriodJob(
            seller_id=seller_id,
            period_key=period_key,
            document_type=document_type,
            limit=limit,
            status="pending",
            next_from_id=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        s.add(job)
        s.commit()
        return job.id
    finally:
        s.close()


def get_billing_period_job(session_factory, job_id: int) -> dict | None:
    from financeiro_ml.models_v2 import MLBillingPeriodJob

    s = session_factory()
    try:
        job = s.query(MLBillingPeriodJob).filter_by(id=job_id).first()
        if job is None:
            return None
        return {
            "id": job.id,
            "seller_id": job.seller_id,
            "period_key": job.period_key,
            "document_type": job.document_type,
            "status": job.status,
            "limit": job.limit,
            "next_from_id": job.next_from_id,
            "pages_done": job.pages_done,
            "lines_done": job.lines_done,
            "total_results": job.total_results,
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        }
    finally:
        s.close()


async def run_billing_period_job(
    session_factory,
    *,
    client,
    job_id: int,
    max_pages: int = 3,
) -> BillingPeriodRunResult:
    from financeiro_ml.models_v2 import MLBillingPeriodJob

    job = _load_job(session_factory, job_id)
    if job is None:
        return BillingPeriodRunResult(
            job_id=job_id,
            status="not_found",
            pages_processed=0,
            lines_processed=0,
            next_from_id=0,
            total_results=None,
            error_message="job nao encontrado",
        )
    if job["status"] == "done":
        return BillingPeriodRunResult(
            job_id=job_id,
            status="done",
            pages_processed=0,
            lines_processed=0,
            next_from_id=job["next_from_id"],
            total_results=job["total_results"],
        )

    _mark_job_running(session_factory, job_id)
    pages_processed = 0
    lines_processed = 0
    next_from_id = int(job["next_from_id"] or 0)
    total_results = job["total_results"]

    try:
        for _ in range(max_pages):
            payload = await client.get_billing_period_details(
                key=job["period_key"],
                document_type=job["document_type"],
                limit=job["limit"],
                from_id=next_from_id,
            )
            raw_results = payload.get("results") or []
            total_results = _as_int(payload.get("total"), total_results)
            page_last_id = _as_int(payload.get("last_id"), None)

            if not raw_results:
                _finish_job(session_factory, job_id, status="done", total_results=total_results)
                return BillingPeriodRunResult(
                    job_id=job_id,
                    status="done",
                    pages_processed=pages_processed,
                    lines_processed=lines_processed,
                    next_from_id=next_from_id,
                    total_results=total_results,
                )

            saved = _save_billing_lines(
                session_factory,
                seller_id=job["seller_id"],
                period_key=job["period_key"],
                document_type=job["document_type"],
                rows=raw_results,
            )
            pages_processed += 1
            lines_processed += saved
            next_from_id = page_last_id or _last_detail_id(raw_results) or next_from_id
            _bump_job(
                session_factory,
                job_id,
                next_from_id=next_from_id,
                pages_delta=1,
                lines_delta=saved,
                total_results=total_results,
            )

            if len(raw_results) < job["limit"] or not next_from_id:
                _finish_job(session_factory, job_id, status="done", total_results=total_results)
                return BillingPeriodRunResult(
                    job_id=job_id,
                    status="done",
                    pages_processed=pages_processed,
                    lines_processed=lines_processed,
                    next_from_id=next_from_id,
                    total_results=total_results,
                )

        current = _load_job(session_factory, job_id)
        status = current["status"] if current else "running"
        return BillingPeriodRunResult(
            job_id=job_id,
            status=status,
            pages_processed=pages_processed,
            lines_processed=lines_processed,
            next_from_id=next_from_id,
            total_results=total_results,
        )
    except MLRateLimited as exc:
        _set_job_error(session_factory, job_id, status="rate_limited", error="429 Too Many Requests")
        return BillingPeriodRunResult(
            job_id=job_id,
            status="rate_limited",
            pages_processed=pages_processed,
            lines_processed=lines_processed,
            next_from_id=next_from_id,
            total_results=total_results,
            error_message=str(exc),
        )
    except Exception as exc:
        _set_job_error(session_factory, job_id, status="failed", error=f"{type(exc).__name__}: {exc}")
        return BillingPeriodRunResult(
            job_id=job_id,
            status="failed",
            pages_processed=pages_processed,
            lines_processed=lines_processed,
            next_from_id=next_from_id,
            total_results=total_results,
            error_message=str(exc),
        )


def _load_job(session_factory, job_id: int) -> dict | None:
    from financeiro_ml.models_v2 import MLBillingPeriodJob

    s = session_factory()
    try:
        job = s.query(MLBillingPeriodJob).filter_by(id=job_id).first()
        if job is None:
            return None
        return {
            "id": job.id,
            "seller_id": job.seller_id,
            "period_key": job.period_key,
            "document_type": job.document_type,
            "status": job.status,
            "limit": job.limit,
            "next_from_id": job.next_from_id,
            "total_results": job.total_results,
        }
    finally:
        s.close()


def _mark_job_running(session_factory, job_id: int) -> None:
    from financeiro_ml.models_v2 import MLBillingPeriodJob

    s = session_factory()
    try:
        job = s.query(MLBillingPeriodJob).filter_by(id=job_id).first()
        if job:
            job.status = "running"
            job.claimed_at = job.claimed_at or datetime.utcnow()
            job.updated_at = datetime.utcnow()
            job.error_message = None
            s.commit()
    finally:
        s.close()


def _bump_job(
    session_factory,
    job_id: int,
    *,
    next_from_id: int,
    pages_delta: int,
    lines_delta: int,
    total_results: int | None,
) -> None:
    from financeiro_ml.models_v2 import MLBillingPeriodJob

    s = session_factory()
    try:
        job = s.query(MLBillingPeriodJob).filter_by(id=job_id).first()
        if job:
            job.next_from_id = next_from_id
            job.pages_done += pages_delta
            job.lines_done += lines_delta
            job.total_results = total_results
            job.status = "running"
            job.updated_at = datetime.utcnow()
            s.commit()
    finally:
        s.close()


def _finish_job(session_factory, job_id: int, *, status: str, total_results: int | None) -> None:
    from financeiro_ml.models_v2 import MLBillingPeriodJob

    s = session_factory()
    try:
        job = s.query(MLBillingPeriodJob).filter_by(id=job_id).first()
        if job:
            job.status = status
            job.total_results = total_results
            job.finished_at = datetime.utcnow()
            job.updated_at = datetime.utcnow()
            s.commit()
    finally:
        s.close()


def _set_job_error(session_factory, job_id: int, *, status: str, error: str) -> None:
    from financeiro_ml.models_v2 import MLBillingPeriodJob

    s = session_factory()
    try:
        job = s.query(MLBillingPeriodJob).filter_by(id=job_id).first()
        if job:
            job.status = status
            job.error_message = error[:4000]
            job.updated_at = datetime.utcnow()
            s.commit()
    finally:
        s.close()


def _save_billing_lines(
    session_factory,
    *,
    seller_id: int,
    period_key: str,
    document_type: str,
    rows: list[dict[str, Any]],
) -> int:
    from financeiro_ml.models_v2 import MLBillingPeriodLine

    saved = 0
    s = session_factory()
    try:
        for raw in rows:
            charge = raw.get("charge_info") or {}
            detail_id = _as_int(charge.get("detail_id"), None)
            if detail_id is None:
                continue
            line = s.query(MLBillingPeriodLine).filter_by(
                seller_id=seller_id,
                detail_id=detail_id,
            ).first()
            if line is None:
                line = MLBillingPeriodLine(seller_id=seller_id, detail_id=detail_id)
                s.add(line)
            line.period_key = period_key
            line.document_type = document_type
            line.creation_date_time = _parse_datetime(charge.get("creation_date_time"))
            line.transaction_detail = charge.get("transaction_detail")
            line.detail_type = charge.get("detail_type")
            line.detail_sub_type = charge.get("detail_sub_type")
            line.detail_amount = _as_decimal(charge.get("detail_amount"))
            line.marketplace = (raw.get("marketplace_info") or {}).get("marketplace")
            line.order_id = _extract_order_id(raw)
            line.shipment_id = _extract_shipment_id(raw)
            line.raw_json = json.dumps(raw)
            line.synced_at = datetime.utcnow()
            saved += 1
        s.commit()
        return saved
    finally:
        s.close()


def _extract_order_id(raw: dict[str, Any]) -> int | None:
    sales = _first_mapping(raw.get("sales_info"))
    items = _first_mapping(raw.get("items_info"))
    candidates = [
        sales.get("order_id"),
        sales.get("sale_id"),
        items.get("order_id"),
    ]
    for value in candidates:
        parsed = _as_int(value, None)
        if parsed is not None:
            return parsed
    return None


def _extract_shipment_id(raw: dict[str, Any]) -> int | None:
    shipping = _first_mapping(raw.get("shipping_info"))
    for value in [shipping.get("shipment_id"), shipping.get("shipping_id")]:
        parsed = _as_int(value, None)
        if parsed is not None:
            return parsed
    return None


def _first_mapping(value) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
    return {}


def _last_detail_id(rows: list[dict[str, Any]]) -> int | None:
    for raw in reversed(rows):
        parsed = _as_int((raw.get("charge_info") or {}).get("detail_id"), None)
        if parsed is not None:
            return parsed
    return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _as_int(value, default: int | None = 0) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None
