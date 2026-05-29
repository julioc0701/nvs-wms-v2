import pytest
import httpx
import financeiro_ml.client as client_mod
from financeiro_ml.client import MLClient, MLRateLimited


class _Resp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)


class _FakeHttp:
    """Sequência de respostas COMPARTILHADA; cada get() consome a próxima.
    Não copia a lista — o _get cria um AsyncClient por tentativa, então o
    progresso tem que persistir entre instâncias."""
    def __init__(self, responses):
        self._responses = responses

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, params=None, headers=None):
        return self._responses.pop(0)


def _make_client():
    c = MLClient(session_factory=lambda: None, client_id="x", client_secret="y", seller_id=1)
    return c


@pytest.mark.asyncio
async def test_429_retries_then_succeeds(monkeypatch):
    c = _make_client()
    monkeypatch.setattr(c, "_ensure_fresh_token", lambda: _async("tok"))
    monkeypatch.setattr(client_mod, "_global_throttle", lambda: _async(None))
    monkeypatch.setattr(client_mod.asyncio, "sleep", lambda *_: _async(None))
    seq = [_Resp(429), _Resp(429), _Resp(200, {"ok": True})]
    monkeypatch.setattr(client_mod.httpx, "AsyncClient", lambda *a, **k: _FakeHttp(seq))

    out = await c._get("/orders/search")
    assert out == {"ok": True}


@pytest.mark.asyncio
async def test_429_gives_up_after_max(monkeypatch):
    c = _make_client()
    monkeypatch.setattr(c, "_ensure_fresh_token", lambda: _async("tok"))
    monkeypatch.setattr(client_mod, "_global_throttle", lambda: _async(None))
    monkeypatch.setattr(client_mod.asyncio, "sleep", lambda *_: _async(None))
    seq = [_Resp(429) for _ in range(10)]
    monkeypatch.setattr(client_mod.httpx, "AsyncClient", lambda *a, **k: _FakeHttp(seq))

    with pytest.raises(MLRateLimited):
        await c._get("/orders/search")


def _async(value):
    async def _coro():
        return value
    return _coro()
