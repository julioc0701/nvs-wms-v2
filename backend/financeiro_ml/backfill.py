"""Backfill: cria job, claim atômico (CAS), consulta progresso. Front faz polling."""
from datetime import date, datetime, timedelta
from sqlalchemy import text


def _total_days(day_from: date, day_to: date) -> int:
    return (day_to - day_from).days + 1


def create_job(session_factory, *, seller_id: int, day_from: date, day_to: date) -> int:
    from financeiro_ml.models_v2 import MLBackfillJob
    s = session_factory()
    try:
        job = MLBackfillJob(seller_id=seller_id, day_from=day_from, day_to=day_to,
                            status="pending", progress_total=_total_days(day_from, day_to),
                            created_at=datetime.utcnow())
        s.add(job)
        s.commit()
        return job.id
    finally:
        s.close()


def claim_job(session_factory, job_id: int) -> bool:
    s = session_factory()
    try:
        res = s.execute(text(
            "UPDATE ml_backfill_jobs SET status='running', claimed_at=:now "
            "WHERE id=:id AND status='pending'"
        ), {"now": datetime.utcnow(), "id": job_id})
        s.commit()
        return res.rowcount == 1
    finally:
        s.close()


def get_job(session_factory, job_id: int) -> dict | None:
    from financeiro_ml.models_v2 import MLBackfillJob
    s = session_factory()
    try:
        j = s.query(MLBackfillJob).filter_by(id=job_id).first()
        if j is None:
            return None
        return {"id": j.id, "seller_id": j.seller_id, "status": j.status,
                "progress_done": j.progress_done, "progress_total": j.progress_total,
                "error_message": j.error_message}
    finally:
        s.close()


def finish_job(session_factory, job_id: int, *, status: str, error: str | None = None) -> None:
    from financeiro_ml.models_v2 import MLBackfillJob
    s = session_factory()
    try:
        j = s.query(MLBackfillJob).filter_by(id=job_id).first()
        if j:
            j.status = status
            j.error_message = error
            j.finished_at = datetime.utcnow()
            s.commit()
    finally:
        s.close()
