import asyncio
import pytest
from datetime import date, datetime, timedelta


def test_active_sellers_from_tokens(fin_db):
    db, m = fin_db
    s = db.FinSessionLocal()
    s.add(m.MLTokens(seller_id=555, access_token="a", refresh_token="r",
                     expires_at=datetime.utcnow()+timedelta(hours=5), updated_at=datetime.utcnow()))
    s.commit(); s.close()
    from financeiro_ml.poller import active_sellers
    assert active_sellers(db.FinSessionLocal) == [555]


def test_build_poll_tasks_uses_14d_window(fin_db):
    db, m = fin_db
    from financeiro_ml.poller import build_poll_tasks
    tasks = build_poll_tasks([555], today=date(2026, 5, 28))
    assert len(tasks) == 1
    t = tasks[0]
    assert t.seller_id == 555
    assert t.days[0] == date(2026, 5, 15)   # 28 - 13 = 15 (14 dias inclusivo)
    assert t.days[-1] == date(2026, 5, 28)
    assert len(t.days) == 14
