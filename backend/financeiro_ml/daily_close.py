"""Fechamento diario do Financeiro ML.

MVP operacional: roda D-1 em ciclos curtos, com checkpoint e cooldown.
Nao usa o enriquecimento antigo por shipment em massa.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from financeiro_ml.client import MLRateLimited

log = logging.getLogger("financeiro_ml.daily_close")

DEFAULT_TZ = "America/Sao_Paulo"


@dataclass
class DailyCloseCycleResult:
    job_id: int
    seller_id: int
    day: date
    status: str
    phase: str
    orders_count: int
    billing_job_id: int | None
    billing_pages_done: int
    billing_lines_done: int
    pending_shipments: int
    next_retry_at: datetime | None
    error_message: str | None = None

    def as_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "seller_id": self.seller_id,
            "day": self.day.isoformat(),
            "status": self.status,
            "phase": self.phase,
            "orders_count": self.orders_count,
            "billing_job_id": self.billing_job_id,
            "billing_pages_done": self.billing_pages_done,
            "billing_lines_done": self.billing_lines_done,
            "pending_shipments": self.pending_shipments,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "error_message": self.error_message,
        }


def period_key_for(day: date) -> str:
    return date(day.year, day.month, 1).isoformat()


def yesterday_brt(now: datetime | None = None) -> date:
    tz = ZoneInfo(os.getenv("ML_DAILY_CLOSE_TIMEZONE", DEFAULT_TZ))
    current = now.astimezone(tz) if now else datetime.now(tz)
    return current.date() - timedelta(days=1)


def create_or_get_daily_close_job(session_factory, *, seller_id: int, day: date) -> int:
    from financeiro_ml.models_v2 import MLDailyCloseJob

    s = session_factory()
    try:
        job = s.query(MLDailyCloseJob).filter_by(seller_id=seller_id, day=day).first()
        if job is None:
            job = MLDailyCloseJob(
                seller_id=seller_id,
                day=day,
                status="pending",
                phase="created",
                priority=10,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            s.add(job)
            s.commit()
        return job.id
    finally:
        s.close()


def get_daily_close_job(session_factory, job_id: int) -> dict | None:
    from financeiro_ml.models_v2 import MLDailyCloseJob

    s = session_factory()
    try:
        job = s.query(MLDailyCloseJob).filter_by(id=job_id).first()
        return _job_dict(job) if job else None
    finally:
        s.close()


def get_daily_close_job_for_day(session_factory, *, seller_id: int, day: date) -> dict | None:
    from financeiro_ml.models_v2 import MLDailyCloseJob

    s = session_factory()
    try:
        job = s.query(MLDailyCloseJob).filter_by(seller_id=seller_id, day=day).first()
        return _job_dict(job) if job else None
    finally:
        s.close()


def list_daily_close_jobs(session_factory, *, limit: int = 20) -> list[dict]:
    from financeiro_ml.models_v2 import MLDailyCloseJob

    s = session_factory()
    try:
        rows = (
            s.query(MLDailyCloseJob)
            .order_by(MLDailyCloseJob.day.desc(), MLDailyCloseJob.id.desc())
            .limit(limit)
            .all()
        )
        return [_job_dict(row) for row in rows]
    finally:
        s.close()


async def run_daily_close_cycle(
    session_factory,
    *,
    client,
    seller_id: int,
    day: date,
    max_order_pages: int = 40,
    orders_search_lookback_days: int = 1,
    billing_pages_per_cycle: int = 5,
    billing_sleep_sec: float = 2,
    cooldown_min: int = 30,
    force_orders: bool = False,
) -> DailyCloseCycleResult:
    job_id = create_or_get_daily_close_job(session_factory, seller_id=seller_id, day=day)
    job = _load_job(session_factory, job_id)
    if job is None:
        raise RuntimeError("daily close job nao encontrado")

    now = datetime.utcnow()
    if job["next_retry_at"] and job["next_retry_at"] > now and not force_orders:
        return _result_from_job(job, status=job["status"], phase=job["phase"])

    if force_orders:
        _update_job_fields(
            session_factory,
            job_id,
            orders_run_id=None,
            orders_count=0,
            pending_shipments=0,
            status="pending",
            phase="created",
            finished_at=None,
            error_message=None,
            next_retry_at=None,
        )
        job = _load_job(session_factory, job_id)

    _mark_job(session_factory, job_id, status="running", phase="orders")

    if not job["orders_run_id"]:
        from financeiro_ml.canary import run_orders_search_canary

        orders_result = await run_orders_search_canary(
            session_factory=session_factory,
            client=client,
            seller_id=seller_id,
            day=day,
            max_pages=max_order_pages,
            search_lookback_days=orders_search_lookback_days,
        )
        if orders_result.status in {"rate_limited", "failed"}:
            _pause_job(
                session_factory,
                job_id,
                phase="orders",
                error=orders_result.error_message or orders_result.status,
                cooldown_min=cooldown_min,
            )
            return _result_from_job(_load_job(session_factory, job_id))
        _update_job_fields(
            session_factory,
            job_id,
            orders_run_id=orders_result.run_id,
            orders_count=orders_result.orders_count,
            pending_shipments=orders_result.pending_shipments + orders_result.pending_shipping_costs,
            status="running",
            phase="billing",
        )
        job = _load_job(session_factory, job_id)

    billing_job_id = job["billing_job_id"]
    if not billing_job_id:
        from financeiro_ml.billing_period import create_billing_period_job

        billing_job_id = create_billing_period_job(
            session_factory,
            seller_id=seller_id,
            period_key=period_key_for(day),
            document_type="BILL",
            limit=int(os.getenv("ML_BILLING_PAGE_LIMIT", "100")),
        )
        _update_job_fields(
            session_factory,
            job_id,
            billing_job_id=billing_job_id,
            status="running",
            phase="billing",
        )

    from financeiro_ml.billing_period import get_billing_period_job, run_billing_period_job

    billing_result = await run_billing_period_job(
        session_factory,
        client=client,
        job_id=billing_job_id,
        max_pages=billing_pages_per_cycle,
        sleep_sec=billing_sleep_sec,
    )
    billing_status = get_billing_period_job(session_factory, billing_job_id) or {}
    if billing_result.status == "rate_limited":
        _pause_job(
            session_factory,
            job_id,
            phase="billing",
            error="429 Too Many Requests",
            cooldown_min=cooldown_min,
        )
    elif billing_result.status == "failed":
        _update_job_fields(
            session_factory,
            job_id,
            status="failed",
            phase="billing_failed",
            error_message=billing_result.error_message,
        )
    else:
        # Billing completo fecha a primeira versao do D-1. Cruzamento/excecoes entram
        # como fase posterior; ate la, orders+billing ja ficam persistidos.
        final_status = "consolidated" if billing_result.status == "done" else "running"
        final_phase = "consolidated" if billing_result.status == "done" else "billing"
        _update_job_fields(
            session_factory,
            job_id,
            status=final_status,
            phase=final_phase,
            billing_pages_done=int(billing_status.get("pages_done") or 0),
            billing_lines_done=int(billing_status.get("lines_done") or 0),
            finished_at=datetime.utcnow() if final_status == "consolidated" else None,
            error_message=None,
            next_retry_at=None,
        )

    return _result_from_job(_load_job(session_factory, job_id))


async def daily_close_loop(session_factory, *, client_factory, stop_event: asyncio.Event):
    if os.getenv("ML_DAILY_CLOSE_ENABLED", "true").strip().lower() not in {"1", "true", "yes"}:
        return

    interval_sec = int(os.getenv("ML_DAILY_CLOSE_LOOP_SEC", "600"))
    seller_env = os.getenv("ML_USER_ID")
    while not stop_event.is_set():
        try:
            seller_ids = _seller_ids(session_factory, fallback=seller_env)
            target_day = yesterday_brt()
            if _within_daily_window():
                for seller_id in seller_ids:
                    client = client_factory(seller_id)
                    await run_daily_close_cycle(
                        session_factory,
                        client=client,
                        seller_id=seller_id,
                        day=target_day,
                        max_order_pages=int(os.getenv("ML_DAILY_ORDER_MAX_PAGES", "40")),
                        orders_search_lookback_days=int(os.getenv("ML_DAILY_ORDER_LOOKBACK_DAYS", "1")),
                        billing_pages_per_cycle=int(os.getenv("ML_BILLING_PAGES_PER_CYCLE", "5")),
                        billing_sleep_sec=float(os.getenv("ML_BILLING_SLEEP_SEC", "2")),
                        cooldown_min=int(os.getenv("ML_429_COOLDOWN_MIN", "30")),
                    )
        except Exception:
            log.exception("daily_close.loop_error")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_sec)
        except asyncio.TimeoutError:
            pass


def _within_daily_window(now: datetime | None = None) -> bool:
    tz = ZoneInfo(os.getenv("ML_DAILY_CLOSE_TIMEZONE", DEFAULT_TZ))
    current = now.astimezone(tz) if now else datetime.now(tz)
    start_h, start_m = _parse_hhmm(os.getenv("ML_DAILY_CLOSE_START", os.getenv("ML_DAILY_CLOSE_TIME", "03:00")))
    end_h, end_m = _parse_hhmm(os.getenv("ML_DAILY_CLOSE_END", "06:00"))
    start = time(start_h, start_m)
    end = time(end_h, end_m)
    current_t = current.time().replace(second=0, microsecond=0)
    if start <= end:
        return start <= current_t <= end
    return current_t >= start or current_t <= end


def _parse_hhmm(value: str) -> tuple[int, int]:
    hour, minute = value.split(":", 1)
    return int(hour), int(minute)


def _seller_ids(session_factory, fallback: str | None = None) -> list[int]:
    from financeiro_ml.poller import active_sellers

    sellers = active_sellers(session_factory)
    if sellers:
        return sellers
    if fallback:
        return [int(fallback)]
    return []


def _load_job(session_factory, job_id: int) -> dict | None:
    from financeiro_ml.models_v2 import MLDailyCloseJob

    s = session_factory()
    try:
        job = s.query(MLDailyCloseJob).filter_by(id=job_id).first()
        return _job_dict(job) if job else None
    finally:
        s.close()


def _job_dict(job) -> dict:
    return {
        "id": job.id,
        "seller_id": job.seller_id,
        "day": job.day,
        "status": job.status,
        "phase": job.phase,
        "priority": job.priority,
        "orders_run_id": job.orders_run_id,
        "billing_job_id": job.billing_job_id,
        "orders_count": job.orders_count,
        "billing_pages_done": job.billing_pages_done,
        "billing_lines_done": job.billing_lines_done,
        "pending_shipments": job.pending_shipments,
        "error_message": job.error_message,
        "next_retry_at": job.next_retry_at,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "finished_at": job.finished_at,
    }


def _mark_job(session_factory, job_id: int, *, status: str, phase: str) -> None:
    _update_job_fields(session_factory, job_id, status=status, phase=phase, updated_at=datetime.utcnow())


def _pause_job(session_factory, job_id: int, *, phase: str, error: str, cooldown_min: int) -> None:
    _update_job_fields(
        session_factory,
        job_id,
        status="paused",
        phase=phase,
        error_message=error,
        next_retry_at=datetime.utcnow() + timedelta(minutes=cooldown_min),
    )


def _update_job_fields(session_factory, job_id: int, **fields) -> None:
    from financeiro_ml.models_v2 import MLDailyCloseJob

    s = session_factory()
    try:
        job = s.query(MLDailyCloseJob).filter_by(id=job_id).first()
        if job:
            for key, value in fields.items():
                if value is not None or key in {
                    "orders_run_id",
                    "finished_at",
                    "next_retry_at",
                    "error_message",
                }:
                    setattr(job, key, value)
            job.updated_at = datetime.utcnow()
            s.commit()
    finally:
        s.close()


def _result_from_job(job: dict, *, status: str | None = None, phase: str | None = None) -> DailyCloseCycleResult:
    return DailyCloseCycleResult(
        job_id=job["id"],
        seller_id=job["seller_id"],
        day=job["day"],
        status=status or job["status"],
        phase=phase or job["phase"],
        orders_count=job["orders_count"],
        billing_job_id=job["billing_job_id"],
        billing_pages_done=job["billing_pages_done"],
        billing_lines_done=job["billing_lines_done"],
        pending_shipments=job["pending_shipments"],
        next_retry_at=job["next_retry_at"],
        error_message=job["error_message"],
    )
