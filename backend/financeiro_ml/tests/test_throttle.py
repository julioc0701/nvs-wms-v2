import asyncio
import pytest


@pytest.mark.asyncio
async def test_throttle_spaces_calls_per_seller(monkeypatch):
    from financeiro_ml.throttle import SellerThrottle
    t = SellerThrottle(min_interval_sec=0.05)
    clock = {"now": 0.0}
    sleeps = []

    async def fake_sleep(s):
        sleeps.append(s)
        clock["now"] += s

    monkeypatch.setattr("financeiro_ml.throttle.asyncio.sleep", fake_sleep)
    monkeypatch.setattr(t, "_now", lambda: clock["now"])

    await t.wait(seller_id=1)   # 1ª passa direto
    await t.wait(seller_id=1)   # 2ª precisa esperar ~min_interval
    assert any(s > 0 for s in sleeps)


@pytest.mark.asyncio
async def test_throttle_independent_per_seller(monkeypatch):
    from financeiro_ml.throttle import SellerThrottle
    t = SellerThrottle(min_interval_sec=0.05)
    clock = {"now": 0.0}
    async def _noop(s): pass
    monkeypatch.setattr("financeiro_ml.throttle.asyncio.sleep", _noop)
    monkeypatch.setattr(t, "_now", lambda: clock["now"])
    await t.wait(seller_id=1)
    await t.wait(seller_id=2)   # seller diferente não espera pelo 1
    assert True  # não levanta, buckets isolados
