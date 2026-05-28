import pytest


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload; self.status_code = status
    def json(self): return self._p
    def raise_for_status(self): pass


@pytest.mark.asyncio
async def test_scan_iterates_until_empty(monkeypatch, fin_db):
    db, m = fin_db
    from datetime import datetime, timedelta
    s = db.FinSessionLocal()
    s.add(m.MLTokens(seller_id=1, access_token="A", refresh_token="R",
                     expires_at=datetime.utcnow()+timedelta(hours=5), updated_at=datetime.utcnow()))
    s.commit(); s.close()

    from financeiro_ml.client import MLClient
    c = MLClient(session_factory=db.FinSessionLocal, client_id="c", client_secret="s", seller_id=1)

    pages = [
        {"scroll_id": "SC1", "results": [{"id": 1}, {"id": 2}]},
        {"scroll_id": "SC1", "results": [{"id": 3}]},
        {"scroll_id": "SC1", "results": []},
    ]
    calls = {"i": 0}

    async def fake_get(path, params=None):
        p = pages[calls["i"]]; calls["i"] += 1
        return p

    monkeypatch.setattr(c, "_get", fake_get)

    collected = []
    async for order in c.scan_orders(date_from=datetime(2026,1,1), date_to=datetime(2026,5,28)):
        collected.append(order["id"])
    assert collected == [1, 2, 3]
