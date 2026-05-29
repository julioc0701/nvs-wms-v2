import pytest


class _FakeResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, data=None):
        return self._resp


@pytest.mark.asyncio
async def test_exchange_saves_tokens_in_fin_db(fin_db, monkeypatch):
    db, m = fin_db
    monkeypatch.setenv("ML_CLIENT_ID", "cid")
    monkeypatch.setenv("ML_CLIENT_SECRET", "secret")
    monkeypatch.setenv("ML_REDIRECT_URI", "https://www.youtube.com")
    monkeypatch.setenv("ML_USER_ID", "555")

    resp = _FakeResp(200, {"access_token": "ACC", "refresh_token": "REF", "expires_in": 21600})
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _FakeClient(resp))

    from financeiro_ml.router import ml_oauth_exchange, OAuthExchangeParams
    res = await ml_oauth_exchange(OAuthExchangeParams(code="TG-abc"), operator_id=1)
    assert res["ok"] is True
    assert res["seller_id"] == 555

    s = db.FinSessionLocal()
    row = s.query(m.MLTokens).filter_by(seller_id=555).first()
    assert row.access_token == "ACC"
    assert row.refresh_token == "REF"
    s.close()


@pytest.mark.asyncio
async def test_exchange_returns_error_without_saving(fin_db, monkeypatch):
    db, m = fin_db
    monkeypatch.setenv("ML_CLIENT_ID", "cid")
    monkeypatch.setenv("ML_CLIENT_SECRET", "secret")
    monkeypatch.setenv("ML_REDIRECT_URI", "https://www.youtube.com")
    monkeypatch.setenv("ML_USER_ID", "555")

    resp = _FakeResp(400, {"error": "invalid_grant", "message": "invalid"})
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: _FakeClient(resp))

    from financeiro_ml.router import ml_oauth_exchange, OAuthExchangeParams
    res = await ml_oauth_exchange(OAuthExchangeParams(code="TG-bad"), operator_id=1)
    assert res["ok"] is False
    assert res["ml_status"] == 400

    s = db.FinSessionLocal()
    assert s.query(m.MLTokens).filter_by(seller_id=555).count() == 0
    s.close()
