import pytest
from datetime import datetime, timedelta


@pytest.mark.asyncio
async def test_ensure_token_reads_per_seller(fin_db, monkeypatch):
    db, m = fin_db
    s = db.FinSessionLocal()
    s.add(m.MLTokens(seller_id=555, client_id="cid", access_token="ACC555",
                     refresh_token="REF555", expires_at=datetime.utcnow() + timedelta(hours=5),
                     updated_at=datetime.utcnow()))
    s.add(m.MLTokens(seller_id=777, client_id="cid", access_token="ACC777",
                     refresh_token="REF777", expires_at=datetime.utcnow() + timedelta(hours=5),
                     updated_at=datetime.utcnow()))
    s.commit(); s.close()

    from financeiro_ml.client import MLClient
    c = MLClient(session_factory=db.FinSessionLocal, client_id="cid", client_secret="sec", seller_id=555)
    tok = await c._ensure_fresh_token()
    assert tok == "ACC555"

    c2 = MLClient(session_factory=db.FinSessionLocal, client_id="cid", client_secret="sec", seller_id=777)
    tok2 = await c2._ensure_fresh_token()
    assert tok2 == "ACC777"


@pytest.mark.asyncio
async def test_refresh_lock_is_per_seller():
    from financeiro_ml.client import MLClient
    l1 = MLClient._refresh_lock_for(1)
    l1b = MLClient._refresh_lock_for(1)
    l2 = MLClient._refresh_lock_for(2)
    assert l1 is l1b      # mesmo seller → mesmo lock
    assert l1 is not l2   # sellers diferentes → locks diferentes
