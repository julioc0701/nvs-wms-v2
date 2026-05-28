import pytest
from datetime import date


@pytest.mark.asyncio
async def test_post_backfill_creates_job(fin_db, monkeypatch):
    db, m = fin_db
    # injeta a fila de escrita do runtime
    import financeiro_ml.worker as worker
    import asyncio
    worker._RUNTIME["queue"] = asyncio.Queue()

    from financeiro_ml.router import create_backfill, BackfillParams
    resp = await create_backfill(BackfillParams(seller_id=1, day_from=date(2026,1,1), day_to=date(2026,1,3)),
                                 operator_id=1)
    assert "job_id" in resp
    s = db.FinSessionLocal()
    assert s.query(m.MLBackfillJob).count() == 1
    s.close()
    assert worker._RUNTIME["queue"].qsize() == 1   # task enfileirada


@pytest.mark.asyncio
async def test_get_backfill_progress(fin_db):
    db, m = fin_db
    from financeiro_ml.backfill import create_job
    job_id = create_job(db.FinSessionLocal, seller_id=1, day_from=date(2026,1,1), day_to=date(2026,1,3))
    from financeiro_ml.router import get_backfill_status
    resp = await get_backfill_status(job_id, operator_id=1)
    assert resp["status"] == "pending"
    assert resp["progress_total"] == 3
