from datetime import datetime, timedelta


def test_acquire_when_free(fin_db):
    db, m = fin_db
    from financeiro_ml.lock import acquire_seller_lock, release_seller_lock
    assert acquire_seller_lock(db.FinSessionLocal, seller_id=1, holder="poller", ttl_sec=120) is True
    release_seller_lock(db.FinSessionLocal, seller_id=1, holder="poller")


def test_second_acquire_blocked_while_held(fin_db):
    db, m = fin_db
    from financeiro_ml.lock import acquire_seller_lock
    assert acquire_seller_lock(db.FinSessionLocal, seller_id=1, holder="poller", ttl_sec=120) is True
    # outro holder não consegue enquanto a lease é válida
    assert acquire_seller_lock(db.FinSessionLocal, seller_id=1, holder="backfill", ttl_sec=120) is False


def test_expired_lease_is_takeable(fin_db):
    db, m = fin_db
    from financeiro_ml.lock import acquire_seller_lock
    # cria lock já vencido manualmente
    s = db.FinSessionLocal()
    s.add(m.MLSellerLock(seller_id=1, holder="old", leased_until=datetime.utcnow() - timedelta(seconds=10)))
    s.commit(); s.close()
    assert acquire_seller_lock(db.FinSessionLocal, seller_id=1, holder="poller", ttl_sec=120) is True


def test_renew_extends_lease(fin_db):
    db, m = fin_db
    from financeiro_ml.lock import acquire_seller_lock, renew_seller_lock
    acquire_seller_lock(db.FinSessionLocal, seller_id=1, holder="poller", ttl_sec=1)
    assert renew_seller_lock(db.FinSessionLocal, seller_id=1, holder="poller", ttl_sec=120) is True
    s = db.FinSessionLocal()
    row = s.query(m.MLSellerLock).filter_by(seller_id=1).first()
    assert row.leased_until > datetime.utcnow() + timedelta(seconds=60)
    s.close()
