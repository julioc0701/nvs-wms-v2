"""Lock durável por seller (CAS + lease/TTL). Atravessa processos — cobre o caso
das 2 réplicas no rolling deploy do Railway, onde asyncio.Lock (por-processo)
não protege. Lease vencida é tomável (sem deadlock em crash)."""
from datetime import datetime, timedelta
from sqlalchemy import text


def acquire_seller_lock(session_factory, *, seller_id: int, holder: str, ttl_sec: int) -> bool:
    now = datetime.utcnow()
    leased_until = now + timedelta(seconds=ttl_sec)
    s = session_factory()
    try:
        # Garante a linha (insert idempotente) sem sobrescrever lease válida
        s.execute(text(
            "INSERT INTO ml_seller_lock (seller_id, holder, leased_until) "
            "VALUES (:sid, NULL, NULL) "
            "ON CONFLICT(seller_id) DO NOTHING"
        ), {"sid": seller_id})
        res = s.execute(text(
            "UPDATE ml_seller_lock SET holder=:who, leased_until=:lu "
            "WHERE seller_id=:sid AND (holder IS NULL OR leased_until IS NULL OR leased_until < :now)"
        ), {"who": holder, "lu": leased_until, "sid": seller_id, "now": now})
        s.commit()
        return res.rowcount == 1
    finally:
        s.close()


def renew_seller_lock(session_factory, *, seller_id: int, holder: str, ttl_sec: int) -> bool:
    leased_until = datetime.utcnow() + timedelta(seconds=ttl_sec)
    s = session_factory()
    try:
        res = s.execute(text(
            "UPDATE ml_seller_lock SET leased_until=:lu WHERE seller_id=:sid AND holder=:who"
        ), {"lu": leased_until, "sid": seller_id, "who": holder})
        s.commit()
        return res.rowcount == 1
    finally:
        s.close()


def release_seller_lock(session_factory, *, seller_id: int, holder: str) -> None:
    s = session_factory()
    try:
        s.execute(text(
            "UPDATE ml_seller_lock SET holder=NULL, leased_until=NULL "
            "WHERE seller_id=:sid AND holder=:who"
        ), {"sid": seller_id, "who": holder})
        s.commit()
    finally:
        s.close()
