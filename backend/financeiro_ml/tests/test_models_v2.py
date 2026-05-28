import importlib
from datetime import datetime, date


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("FINANCEIRO_ML_DATABASE_URL", f"sqlite:///{tmp_path}/fin.db")
    import financeiro_ml.db as db
    importlib.reload(db)
    import financeiro_ml.models_v2 as m
    importlib.reload(m)
    db.FinBase.metadata.create_all(bind=db.fin_engine)
    return db, m


def test_order_cache_composite_pk_seller_order(tmp_path, monkeypatch):
    db, m = _fresh_db(tmp_path, monkeypatch)
    s = db.FinSessionLocal()
    s.add(m.MLOrderCache(seller_id=1, order_id=999, date_created=datetime(2026,5,1),
                         status="paid", raw_json="{}", synced_at=datetime.utcnow()))
    s.add(m.MLOrderCache(seller_id=2, order_id=999, date_created=datetime(2026,5,1),
                         status="paid", raw_json="{}", synced_at=datetime.utcnow()))
    s.commit()
    assert s.query(m.MLOrderCache).count() == 2
    s.close()


def test_day_sync_status_unique_per_seller_day(tmp_path, monkeypatch):
    db, m = _fresh_db(tmp_path, monkeypatch)
    s = db.FinSessionLocal()
    s.add(m.MLDaySyncStatus(seller_id=1, day=date(2026,5,1),
                            last_synced_at=datetime.utcnow(), orders_count=10, status="ok"))
    s.add(m.MLDaySyncStatus(seller_id=2, day=date(2026,5,1),
                            last_synced_at=datetime.utcnow(), orders_count=5, status="ok"))
    s.commit()
    assert s.query(m.MLDaySyncStatus).count() == 2
    s.close()


def test_seller_lock_and_backfill_job_tables_exist(tmp_path, monkeypatch):
    db, m = _fresh_db(tmp_path, monkeypatch)
    s = db.FinSessionLocal()
    s.add(m.MLSellerLock(seller_id=1, holder=None, leased_until=None))
    s.add(m.MLBackfillJob(seller_id=1, day_from=date(2026,1,1), day_to=date(2026,5,1),
                          status="pending", created_at=datetime.utcnow()))
    s.commit()
    assert s.query(m.MLSellerLock).count() == 1
    assert s.query(m.MLBackfillJob).count() == 1
    s.close()


def test_fixture_fin_db_works(fin_db):
    db, m = fin_db
    s = db.FinSessionLocal()
    assert s.query(m.MLOrderCache).count() == 0
    s.close()
