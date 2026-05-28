from datetime import date


def test_create_job_returns_id_and_total(fin_db):
    db, m = fin_db
    from financeiro_ml.backfill import create_job
    job_id = create_job(db.FinSessionLocal, seller_id=1, day_from=date(2026,1,1), day_to=date(2026,1,10))
    s = db.FinSessionLocal()
    job = s.query(m.MLBackfillJob).filter_by(id=job_id).first()
    assert job.status == "pending"
    assert job.progress_total == 10   # 10 dias inclusivo
    s.close()


def test_claim_job_atomic_only_once(fin_db):
    db, m = fin_db
    from financeiro_ml.backfill import create_job, claim_job
    job_id = create_job(db.FinSessionLocal, seller_id=1, day_from=date(2026,1,1), day_to=date(2026,1,2))
    assert claim_job(db.FinSessionLocal, job_id) is True
    assert claim_job(db.FinSessionLocal, job_id) is False  # já claimed → não reentra
    s = db.FinSessionLocal()
    assert s.query(m.MLBackfillJob).filter_by(id=job_id).first().status == "running"
    s.close()


def test_get_job_progress(fin_db):
    db, m = fin_db
    from financeiro_ml.backfill import create_job, get_job
    job_id = create_job(db.FinSessionLocal, seller_id=1, day_from=date(2026,1,1), day_to=date(2026,1,5))
    prog = get_job(db.FinSessionLocal, job_id)
    assert prog["status"] == "pending"
    assert prog["progress_total"] == 5
    assert prog["progress_done"] == 0
